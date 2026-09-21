"""The quest state transitions a playing session makes. Pure: no world, no clock, no draw.

`terrain_time` owns the quest *lifecycle* -- what the world does to an offer as time
passes: opening it from a hook, expiring it on its window, reaping it when its giver or its
target is gone. This module owns the two transitions a *player* makes, which the world has
no business inventing: taking an offer, and letting one go.

Split out for the reason `terrain_time_schedule` is split out. Everything here is a
function of a quest record and a day, so it is decided and tested without generating a
world, and `terrain_quest_api` is left holding only the request envelope, the copy and the
operation record.

**`taken` is not a new state.** It has existed in the lifecycle since the clock landed and
is already honoured -- a taken quest does not expire on its offer window -- but no request
field set it, so a game that accepted a quest for its player wrote that state into the
persisted document by hand. This module is the missing writer, not a new vocabulary.

**No randomness, by construction.** Neither transition draws, so neither can key an RNG
stream on a call ordinal. A quest's one random quantity, its offer window, is drawn once by
`terrain_time._quest_step` from the absolute step index and is never redrawn here.
"""

import math

from .terrain_errors import (invalid_choice, over_capacity, refused_by_world, unknown_field,
                             wrong_type)

TAKE = 'take'
ABANDON = 'abandon'
ACTIONS = (TAKE, ABANDON)

# The two lifecycle states a quest can still be acted on from. The same pair
# `terrain_time._quest_step` treats as live and `_apply_resolutions` allows a resolution
# against; a third opinion about what "still open" means is exactly the drift this reuses
# its way out of.
OPEN_STATES = ('offered', 'taken')

# The same bound `advance-time` puts on `resolutions`. One session cannot take a thousand
# quests in one instant, and a shared ceiling means a caller batching both does not have to
# learn two numbers.
MAX_ACTIONS = 1024

FIELDS = ('quest_id', 'action', 'day')


def validate_actions(actions):
    """Shape-only validation of an `actions` array: no world, no quest ids, no state.

    Returns the normalised list -- every item a dict of exactly `quest_id`, `action` and a
    `day` that is either a finite number or `None`, meaning "whatever the world clock says".
    Everything that needs the world is refused later, by `terrain_quest_api`, so a malformed
    request costs nothing but this function.
    """
    if not isinstance(actions, list):
        raise wrong_type('actions', actions,
                         {'type': 'array', 'description': 'a list of quest actions'})
    if len(actions) > MAX_ACTIONS:
        raise over_capacity('actions', len(actions), MAX_ACTIONS, 'quest actions per request')
    out = []
    for item in actions:
        if not isinstance(item, dict):
            raise wrong_type('actions[]', item,
                             {'type': 'object',
                              'description': 'an object with quest_id, action and an optional day'})
        extra = sorted(set(item) - set(FIELDS))
        if extra:
            raise unknown_field(extra[0], FIELDS, noun='quest action field')
        quest_id = item.get('quest_id')
        if not isinstance(quest_id, str) or not quest_id:
            raise wrong_type('quest_id', quest_id,
                             {'type': 'string', 'description': 'the hook id a quest is keyed on'})
        if item.get('action') not in ACTIONS:
            raise invalid_choice('action', item.get('action'), {'choices': list(ACTIONS)})
        day = item.get('day')
        if day is not None:
            # `bool` is an `int` in Python and `True` would sail through a numeric test as
            # day 1. Every other request boundary here checks the type identically.
            if isinstance(day, bool) or not isinstance(day, (int, float)) \
                    or not math.isfinite(day):
                raise wrong_type('day', day,
                                 {'type': 'number',
                                  'description': 'a finite day on the moon calendar'})
            if day < 0:
                raise wrong_type('day', day,
                                 {'type': 'number', 'min': 0,
                                  'description': 'a day at or after founding year 0'})
            day = float(day)
        out.append({'quest_id': quest_id, 'action': item['action'], 'day': day})
    return out


def transition(quest, action, day, alternatives=()):
    """`(new quest record, log entry)` for one action. `quest` is not mutated.

    Every refusal here is `refused_by_world`: the id was real and the request was well
    formed, and the world is what will not satisfy it. A caller that cannot tell that from a
    malformed argument keeps correcting a value that was never wrong.
    """
    state = quest.get('state')
    if state not in OPEN_STATES:
        raise refused_by_world('quest_id', quest.get('quest_id'),
                               'Quest %s is already %s and cannot be %sn.'
                               % (quest.get('quest_id'), state, action),
                               alternatives=list(alternatives))
    if action == TAKE:
        if state == 'taken':
            raise refused_by_world('quest_id', quest.get('quest_id'),
                                   'Quest %s has already been taken.' % quest.get('quest_id'),
                                   alternatives=list(alternatives))
        expires = quest.get('expires_day')
        if expires is not None and day > expires:
            # Not pedantry. `_quest_step` tests the window only while a quest is `offered`,
            # so a take applied after the window closed but before the next sweep would make
            # the offer immortal: it leaves `offered`, and the expiry branch is never reached
            # again.
            raise refused_by_world('quest_id', quest.get('quest_id'),
                                   'Quest %s was offered until day %s and day %s is past that; '
                                   'the world has already let it lapse.'
                                   % (quest.get('quest_id'), expires, day),
                                   alternatives=list(alternatives))
        out = dict(quest)
        out['state'] = 'taken'
        return out, {'day': day, 'quest_id': quest.get('quest_id'), 'event': 'taken'}
    out = dict(quest)
    out['state'] = 'abandoned'
    out['closed_day'] = day
    # Distinct from the `resolved` a resolution writes. A resolution is the game reporting
    # an outcome it played; this is the party putting the promise down, and a consumer
    # reading the board should be able to tell those apart without re-reading the log.
    out['closed_reason'] = 'abandoned'
    return out, {'day': day, 'quest_id': quest.get('quest_id'), 'event': 'abandoned'}
