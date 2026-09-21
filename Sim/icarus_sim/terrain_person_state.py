"""Liveness changes a playing session makes to one person. Pure: no world, no clock, no draw.

A game loses a character, or finds one it thought lost. Four blocks record that fact in
three sets of words and a caller had no way to say it in one, so it wrote a block-local
word into the persisted document by hand -- which meant knowing which of `legend`, `dead`
and `fallen` the block in question uses, and getting the depth right, because
`hero_generator` and `npc_roster` both write a block-level `status` of `ok`/`failed` under
the same key name as the person-level one.

**The request speaks the predicate's pair and no new word.** `present` and `gone` are
`terrain_liveness`'s own published states, and `token` turns either into the word the block
actually uses. Nothing here invents a vocabulary; there are already five and a sixth
claiming to unify them would be the sixth.

**Every write goes through `liveness`, never around it.** The current state is read with
the predicate, the new word comes from its table, and the result is read back through the
predicate before it is returned. That is what makes the block/person depth collision a
raise instead of a silent wrong answer: `liveness` refuses a record carrying `people`,
`quest_hooks` or `policy_revision`, and a writer that formatted a string instead would
happily mark a failed package as a departed person.

**A no-op writes nothing.** Asking for the state a record is already in returns `None`
rather than a record with a freshly stamped `status`. An absent status reads as present
(`terrain_villains.is_standing` says so, and every world generated before the fall pair
landed depends on it), so stamping one in would add a key to a record for no reason and
move the bytes of a document whose reproducibility is a contract.
"""

import math

from .terrain_errors import invalid_choice, over_capacity, unknown_field, wrong_type
from .terrain_liveness import GONE, PRESENT, liveness, token

STATUSES = (PRESENT, GONE)

# The same ceiling `advance-time` puts on `resolutions` and the quest route puts on
# `actions`. One batch, one number to learn.
MAX_CHANGES = 1024

# A free-text note the caller writes for itself. Bounded because it is copied verbatim into
# `history.operations`, which is persisted and replayed, and an unbounded string there is an
# unbounded world document.
MAX_REASON = 200

FIELDS = ('uid', 'status', 'reason', 'day')


def validate_changes(changes):
    """Shape-only validation of a `changes` array: no world, no uids, no blocks.

    Returns the normalised list. Everything that needs a world -- whether the uid names
    anybody, and which block it names them in -- is refused later by `terrain_person_api`.
    """
    if not isinstance(changes, list):
        raise wrong_type('changes', changes,
                         {'type': 'array', 'description': 'a list of person state changes'})
    if len(changes) > MAX_CHANGES:
        raise over_capacity('changes', len(changes), MAX_CHANGES, 'person changes per request')
    out = []
    for item in changes:
        if not isinstance(item, dict):
            raise wrong_type('changes[]', item,
                             {'type': 'object',
                              'description': 'an object with uid, status, reason and day'})
        extra = sorted(set(item) - set(FIELDS))
        if extra:
            raise unknown_field(extra[0], FIELDS, noun='person change field')
        missing = [name for name in FIELDS if name not in item]
        if missing:
            raise unknown_field(missing[0], FIELDS, noun='person change field')
        uid = item['uid']
        if not isinstance(uid, str) or not uid:
            raise wrong_type('uid', uid,
                             {'type': 'string', 'description': 'the uid a person record carries'})
        if item['status'] not in STATUSES:
            # Named `status` because that is the field, but the vocabulary is the liveness
            # pair rather than any block's own words: a caller sending `dead` is told the
            # two states this boundary speaks and does not have to know which block the uid
            # will land in.
            raise invalid_choice('status', item['status'], {'choices': list(STATUSES)})
        reason = item['reason']
        if not isinstance(reason, str) or not reason.strip():
            raise wrong_type('reason', reason,
                             {'type': 'string',
                              'description': 'why this person changed state, for the record'})
        if len(reason) > MAX_REASON:
            raise over_capacity('reason', len(reason), MAX_REASON, 'characters')
        day = item['day']
        # `bool` is an `int`, and `True` would otherwise pass as day 1.
        if isinstance(day, bool) or not isinstance(day, (int, float)) or not math.isfinite(day):
            raise wrong_type('day', day,
                             {'type': 'number', 'description': 'a finite day on the moon calendar'})
        if day < 0:
            raise wrong_type('day', day,
                             {'type': 'number', 'min': 0,
                              'description': 'a day at or after founding year 0'})
        out.append({'uid': uid, 'status': item['status'], 'reason': reason, 'day': float(day)})
    return out


def plan(record, block, status):
    """`(new record or None, state before, state after)` for one person. Pure.

    `record` is not mutated. `None` in the first slot means the record already reads as
    `status` and nothing needs writing.

    `block` is the name of the list the record came from, not a guess at its shape --
    the same contract `liveness` takes, and the reason a block handed in here raises rather
    than being rewritten as though it were a person.
    """
    before = liveness(record, block)
    if before == status:
        return None, before, before
    out = dict(record)
    out['status'] = token(block, status)
    after = liveness(out, block)
    if after != status:
        # Unreachable while `token` is the inverse of `liveness`, and asserted rather than
        # assumed because the two tables live side by side and a future block added to one
        # and not the other would otherwise write a word that reads back as its opposite.
        raise ValueError('liveness translation for %r does not round-trip: wrote %r, read %r'
                         % (block, out['status'], after))
    return out, before, after
