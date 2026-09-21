"""Record that a person is gone, or back. Glue over `terrain_person_state`.

Stateless JSON API v1, in the shape the other request mutators use: a world goes in, a new
world comes out, the caller persists it. `POST /world/person-state`.

The caller names a `uid` and one of the two liveness states. This module finds which of the
four person lists that uid came from -- `heroes.people`, `heroes.dreads`, `npcs.people` or
`villains.people` -- and `terrain_person_state.plan` writes that block's own word through
`terrain_liveness`. The caller never names the block and never sees `legend`, `dead` or
`fallen` unless it reads the report.

**What this route deliberately does not do.** It writes one field on one record and nothing
else. It does not close the dead person's quests, decay a fallen villain's claim, write a
tombstone, update the roster mirror `npc_roster` copied out of `heroes` at generation time,
or remove anybody from a settlement's staffing. Two of those are the open question
`board/backlog/NPC-TOMBSTONES.md` and `board/backlog/VILLAIN-FALL-UNRECORDED.md` share --
what persists when someone stops existing -- and `board/README.md` requires those to be
answered together, not here. The rest already have an owner: `terrain_time._quest_step`
reads liveness on its next sweep and closes an offer whose giver is gone, exactly as it
does for a giver the world itself removed. The report says all of this in its `notes`,
because a consumer that discovers it from behaviour discovers it late.

**Purity, and the copy.** Every change is resolved and refused before anything is copied, so
there is no path on which a partly written world exists at all. Then only the top-level
blocks a change actually lands in are copied; everything else in the returned document is
the caller's own object, shared rather than duplicated, the way the instant band of
`advance-time` already shares what it does not write.
"""

import copy

from .terrain_errors import (missing_block, refused_by_world, unknown_field, unsupported_api,
                             wrong_type)
from .terrain_liveness import GONE, token
from .terrain_person_state import plan, validate_changes

PERSON_API_VERSION = 1

FIELDS = ('api_version', 'world', 'changes')

# Where a person record can live, as `(top-level key, list name, liveness block)`. The
# liveness block is not always the key: `dreads` is the antagonist cast inside `heroes` and
# `terrain_liveness` names it separately because it is a different list, not a different
# vocabulary.
SOURCES = (('heroes', 'people', 'heroes'),
           ('heroes', 'dreads', 'dreads'),
           ('npcs', 'people', 'npcs'),
           ('villains', 'people', 'villains'))


def _validate(body):
    """Everything judgeable before the world is read. Shape only."""
    if not isinstance(body, dict):
        raise wrong_type('body', body, {'type': 'object', 'description': 'a request object'})
    extra = sorted(set(body) - set(FIELDS))
    if extra:
        raise unknown_field(extra[0], FIELDS, noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != PERSON_API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (PERSON_API_VERSION,))
    return validate_changes(body.get('changes', []))


def index(world):
    """`uid -> [(key, listing, block, position)]`, over every person list this world carries.

    A list is skipped when its package failed, matching `terrain_liveness.census`: a block
    with `status: 'failed'` carries no people, and zero present people and no package at all
    are different facts.

    The value is a list rather than a single entry so a uid claimed by two blocks is
    *detected* rather than resolved by iteration order. No generated world has one today;
    that is a fact about the uid minters, not a guarantee any of them makes.
    """
    found = {}
    for key, listing, block in SOURCES:
        container = world.get(key)
        if not isinstance(container, dict):
            continue
        if key != 'villains' and container.get('status') != 'ok':
            continue
        people = container.get(listing)
        if not isinstance(people, list):
            continue
        for position, record in enumerate(people):
            if isinstance(record, dict) and isinstance(record.get('uid'), str):
                found.setdefault(record['uid'], []).append((key, listing, block, position))
    return found


def _notes(applied):
    """What a consumer would otherwise learn from behaviour, at the call that caused it."""
    notes = ['Nothing cascades from this call. The next tick closes an offer whose giver is '
             'gone, as it already does for a giver the world removed; everything else is '
             'untouched.']
    if any(row['block'] in ('heroes', 'dreads') for row in applied):
        notes.append('The npcs roster mirror of this person was not updated. npc_roster '
                     'copies the cast into npcs.people under a prefixed uid at generation '
                     'time and that copy is a snapshot; it is rebuilt at the next age '
                     'boundary.')
    if any(row['block'] == 'villains' and row['to_status'] == GONE for row in applied):
        notes.append('A villain marked gone keeps its claims, its held nodes and its absence '
                     'from villains.fallen. The bookkeeping an age boundary does around a '
                     'fall is not run here; see board/backlog/VILLAIN-FALL-UNRECORDED.md.')
    return notes


def person_state_request(body):
    """Stateless JSON API v1: apply liveness changes and return the new world.

    Same input, same output. Nothing here draws, so no stream is keyed on a call ordinal
    and two identical calls against one world produce identical bytes.
    """
    from .terrain_time import validate_time_world

    changes = _validate(body)
    world = body.get('world')
    # The same world gate the tick uses, for the same reason the quest route uses it: a
    # weaker question here would admit a world `advance-time` refuses a moment later.
    validate_time_world(world)

    known = index(world)
    if not known:
        raise missing_block('people', 'This world carries no person lists to change. heroes, '
                            'npcs and villains are written at generation; a world whose cast '
                            'packages failed has none.')

    # Resolve everything first. After this loop no refusal remains, so no path exists on
    # which a partly written world was ever built. The one raise below is `plan`'s internal
    # round-trip check, which cannot fire while `token` is the inverse of `liveness` -- and
    # if it ever did, the copy would be discarded with everything else.
    resolved = []
    for change in changes:
        where = known.get(change['uid'])
        if not where:
            raise unknown_field(change['uid'], sorted(known), noun='person')
        if len(where) > 1:
            raise refused_by_world('uid', change['uid'],
                                   'uid %s names a person in more than one block (%s), so this '
                                   'call cannot tell which one you mean.'
                                   % (change['uid'], ', '.join(sorted(w[2] for w in where))))
        resolved.append((change, where[0]))

    touched = sorted({entry[0] for _, entry in resolved})
    result = dict(world)
    for key in touched:
        result[key] = copy.deepcopy(world[key])

    applied, requested, report = [], [], []
    for change, (key, listing, block, position) in resolved:
        people = result[key][listing]
        record, before, after = plan(people[position], block, change['status'])
        row = {'uid': change['uid'], 'block': block, 'from_status': before,
               'to_status': after, 'token': token(block, after),
               'day': change['day'], 'reason': change['reason'],
               'changed': record is not None}
        if record is not None:
            people[position] = record
            applied.append(row)
            requested.append(dict(change))
        report.append(row)

    if not applied:
        # Nothing moved, so nothing is recorded and nothing is copied either. The blocks
        # deep-copied above are discarded with the rest of this result.
        result = dict(world)
        result['person_state'] = {'api_version': PERSON_API_VERSION, 'applied': 0,
                                  'changes': report, 'notes': _notes(applied)}
        return result

    result['person_state'] = {'api_version': PERSON_API_VERSION, 'applied': len(applied),
                              'changes': report, 'notes': _notes(applied)}
    history = dict(world.get('history') or {})
    history['operations'] = list(history.get('operations') or []) + [
        {'api_version': PERSON_API_VERSION, 'kind': 'person', 'changes': requested}]
    result['history'] = history
    return result
