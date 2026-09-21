"""Take and abandon a quest. Glue over `terrain_quest_actions`.

Stateless JSON API v1, in the shape the nine other request mutators already use: a world
goes in, a new world comes out, the caller persists it. `POST /world/quest`.

**Why a route rather than two more arrays on `advance-time`.** Taking a quest happens at an
instant, not over a span, and a caller that only wants to record an acceptance should not
have to name an elapsed time it does not mean. The operation record then says what
happened, instead of recording a player's decision as a side effect of a clock.

**It reuses the resolution array's validation rather than restating it.** Same capacity
bound, same refusal envelope, same unknown-`quest_id` refusal, and the same definition of
which states are still open. Two boundaries disagreeing about what an open quest is would
be the defect, not a style difference.

**What it does not do.** It does not move the clock, re-evaluate the ley field, open new
quests, expire old ones or touch any other block. Everything a quest's *state* implies for
the world happens on the next tick, where the lifecycle already lives: a giver who dies,
a target that is destroyed and an offer that lapses are all `terrain_time`'s to notice.

**The copy is structural, like the instant band's.** This route writes exactly two blocks,
`quests` and `history`, so exactly those two are copied and everything else in the returned
document is the caller's own object, shared rather than duplicated. A full deep copy grows
with the square of the grid, and a session that takes a quest cannot pay a two-second copy
of its terrain to record it. Nothing below is mutated in place, so the caller's world is
byte-identical after every call and after every refusal.
"""

import copy

from .terrain_errors import missing_block, unknown_field, unsupported_api, wrong_type
from .terrain_quest_actions import OPEN_STATES, transition, validate_actions

QUEST_API_VERSION = 1

FIELDS = ('api_version', 'world', 'actions')


def _validate(body):
    """Everything judgeable before the world is read. Shape only."""
    if not isinstance(body, dict):
        raise wrong_type('body', body, {'type': 'object', 'description': 'a request object'})
    extra = sorted(set(body) - set(FIELDS))
    if extra:
        raise unknown_field(extra[0], FIELDS, noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != QUEST_API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (QUEST_API_VERSION,))
    return validate_actions(body.get('actions', []))


def quest_request(body):
    """Stateless JSON API v1: apply a batch of quest actions and return the new world.

    Same input, same output. No action draws, so nothing here is keyed on a call ordinal
    and two identical calls against one world produce identical bytes.
    """
    from .terrain_time import clock, validate_time_world

    actions = _validate(body)
    world = body.get('world')
    # The same world gate the tick uses. A quest board only exists on a world the clock can
    # move, and asking a second, weaker question here would let a world through this route
    # that `advance-time` will refuse a moment later.
    validate_time_world(world)

    block = world.get('quests')
    if not isinstance(block, dict) or not isinstance(block.get('quests'), list):
        raise missing_block('quests', 'This world carries no quests to act on. Advance it by at '
                            'least one day first, which is what opens them.')

    now = clock(world)['day']
    if not actions:
        # Nothing changed, so nothing is recorded: the age band's estimate path sets this
        # precedent, and an operation log that grows on every no-op is an unbounded record
        # of nothing happening.
        result = dict(world)
        result['quest_actions'] = {'api_version': QUEST_API_VERSION, 'day': now,
                                   'applied': 0, 'actions': []}
        return result

    result = dict(world)
    result['quests'] = copy.deepcopy(block)
    quests = result['quests']['quests']
    # `log` is written by every board this capability opens, but a board a consumer
    # hand-persisted before the accept channel existed may not carry one, and a bare
    # KeyError here would be the one failure at this boundary with no envelope around it.
    result['quests'].setdefault('log', [])
    by_id = {quest['quest_id']: index for index, quest in enumerate(quests)
             if isinstance(quest, dict) and isinstance(quest.get('quest_id'), str)}

    applied = []
    for item in actions:
        quest_id = item['quest_id']
        if quest_id not in by_id:
            raise unknown_field(quest_id, sorted(by_id), noun='quest')
        day = now if item['day'] is None else item['day']
        index = by_id[quest_id]
        # Recomputed per action rather than once: a batch that closes three quests should
        # not keep offering them back as alternatives.
        alternatives = [q['quest_id'] for q in quests
                        if isinstance(q, dict) and q.get('state') in OPEN_STATES
                        and isinstance(q.get('quest_id'), str)]
        quest, entry = transition(quests[index], item['action'], day, alternatives)
        quests[index] = quest
        result['quests']['log'].append(entry)
        applied.append({'quest_id': quest_id, 'action': item['action'], 'day': day,
                        'state': quest['state']})

    result['quest_actions'] = {'api_version': QUEST_API_VERSION, 'day': now,
                               'applied': len(applied), 'actions': applied}
    history = dict(world.get('history') or {})
    history['operations'] = list(history.get('operations') or []) + [
        {'api_version': QUEST_API_VERSION, 'kind': 'quest',
         'actions': [{'quest_id': row['quest_id'], 'action': row['action'], 'day': row['day']}
                     for row in applied]}]
    # `history.replay` is left exactly as it was found. `advance_time_request` writes that
    # sentence and this route has nothing to add to it; rewording it here would make the
    # key flip between two strings depending on which call ran last, which is churn in the
    # bytes of a document whose byte-reproducibility is a contract.
    result['history'] = history
    return result
