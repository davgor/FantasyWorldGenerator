"""Five bounded questions about a world that already exists. Glue over `terrain_read_select`.

Stateless JSON reads in the shape the nine mutators already use -- `{api_version, world,
...}` in, a document out -- so the glue a host writes to turn a handle into a world
document is the same glue it already has, and `icarus_sim` still never learns what a handle
is (`docs/decisions/026-world-handles-and-the-host-store.md`).

The point of the package is arithmetic. A generated seed-42 world is 7.8 MB as written at
size 17 and 116 MB at size 257, and the named consumer is a local model packaged inside the
game with finite context. It cannot hold a world, so before these reads existed every
question it had was answered by handing it the planet. Each read here answers in kilobytes.

**A closed verb set, not a query language.** Every request function in this tree allow-lists
its body keys and refuses an unknown one by name, and that refusal envelope is the best
thing the API has. A query language throws it away at exactly that boundary and commits the
repository to a parser and an evaluation model before it has a single reader. Five named
reads, each with its own allow-list, cost less and refuse better.

**What a read never does.**

* *Never mints a version.* Decision 026: reads produce no handle and no envelope. They
  answer with their own document.
* *Never mutates.* Every read works off the caller's object without writing to it; nothing
  here deep-copies because nothing here assigns.
* *Never regenerates.* `patch_request` rebuilds the entire submitted world from its `Config`
  before cutting a patch, which is why a patch costs what a generate costs. That is
  deliberate for `patch` and is the one thing a read whose whole purpose is to be orders
  cheaper than a generate must not copy.
* *Never invents a join.* Every join is resolved in `terrain_read_select`, against the field
  the writer wrote, with the writing site named in a comment beside it and repeated in the
  `joins` list of the answer.

**Bounded is a number, not a word.** `near` and `quests` refuse past a declared row ceiling
rather than truncating, because both have a remedy a caller can apply -- a smaller radius, a
narrower state filter. `place` has no such argument, so its roster posts are projected and
capped with the true count reported beside them; a truncation a caller can see is not a
truncation a caller can be misled by.
"""

from .terrain_errors import (invalid_choice, missing_block, out_of_range, over_capacity,
                             refused_by_world, unknown_field, unsupported_api, wrong_type)
from . import terrain_read_select as select

READ_API_VERSION = 1
READ_SCHEMA_VERSION = 1
SCHEMA_PREFIX = 'fantasy-world-generator.read.'

#: A `near` radius is capped at half this world's globe radius, the same relative ceiling
#: `terrain_patch.generate_patch` puts on a patch span. Relative rather than absolute
#: because an absolute metre bound means a different question on an 11 km world and a
#: 200 km one, which is the mistake `terrain_leyline_history` records for ley widths.
NEAR_RADIUS_FRACTION = .5

#: Row ceilings. A wide radius on a dense world is not bounded by construction, so the
#: bound is declared, refused past, and tested.
MAX_NEAR_ROWS = 512
MAX_QUEST_ROWS = 2048
MAX_PLACE_POSTS = 1024


def _body(body, allowed):
    """The three refusals every read shares, in the order every mutator makes them."""
    if not isinstance(body, dict):
        raise wrong_type('body', body, {'type': 'object', 'description': 'a request object'})
    unknown = sorted(set(body) - set(allowed))
    if unknown:
        raise unknown_field(unknown[0], sorted(allowed), noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != READ_API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (READ_API_VERSION,))
    world = body.get('world')
    if not isinstance(world, dict):
        raise wrong_type('world', world,
                         {'type': 'object', 'description': 'a generated world document'})
    return world


def _envelope(read, world):
    """What every read carries: what it is, and which world answered.

    Not a handle. Naming the world by its content is the host's job and stays on the far
    side of the boundary; these four fields are read straight off the document so a caller
    holding two answers can tell whether they came from the same generator.
    """
    clock = world.get('world_clock') if isinstance(world.get('world_clock'), dict) else {}
    config = world.get('config') if isinstance(world.get('config'), dict) else {}
    return {'schema': SCHEMA_PREFIX + read, 'schema_version': READ_SCHEMA_VERSION,
            'read': read, 'api_version': READ_API_VERSION,
            'source': {'generator_version': world.get('generator_version'),
                       'seed': config.get('seed'), 'size': config.get('size'),
                       'phase': config.get('phase'),
                       'day': clock.get('day'), 'age': clock.get('age')}}


def _require_block(world, name, message):
    if not isinstance(world.get(name), dict):
        raise missing_block(name, message)
    return world[name]


def _require_grid(world):
    """A world can only be asked what is near a node if it has nodes.

    Deliberately not `validate_time_world` or `validate_age_world`. Those answer whether a
    world can be *changed*, and carry contract requirements -- a recipe, a phase floor, a
    grid ceiling -- that describing a world does not need. A read that refused to describe
    a world it could describe would be a worse answer than the description.
    """
    size = select.grid_size(world)
    radius = select.globe_radius(world)
    if type(size) is not int or size < 2:
        raise missing_block('config', 'A near read needs the grid this world was built on; '
                            'config.size is %r.' % (size,))
    if not isinstance(radius, (int, float)) or isinstance(radius, bool) or radius <= 0:
        raise missing_block('effective_config', 'A near read measures in metres on this '
                            "world's globe; effective_config.globe_radius is %r." % (radius,))
    return size, radius


# ------------------------------------------------------------------------------- blocks

def blocks_request(body):
    """Which blocks this world carries, each one's declared version and its size in bytes.

    The read that makes every other read discoverable, the one a controller calls first,
    and the only one with no join -- which is why it is also the only one that cannot be
    subtly wrong.

    It walks the world and marks membership of `terrain_history.STATE_KEYS` in both
    directions. A report built by walking the registry instead would omit a block a world
    carries and the registry does not, which is the `materialize_stage` failure mode
    `docs/conformance/nomads.md` and `docs/conformance/time-advance.md` both document,
    arriving at a new surface.

    Cost is one serialisation of the world, because a byte count that was estimated would
    not be a byte count. On a world still carrying `build_stages` that is most of the work,
    and `build_stages` appears in the report as its own row so a caller can see why.
    """
    world = _body(body, ('api_version', 'world'))
    document = _envelope('blocks', world)
    document.update(select.block_summary(world))
    document['encoding'] = ('json; sorted keys; no whitespace; utf-8; NaN and Infinity '
                            'refused. The same encoding the transfer form uses; not the '
                            'same document, which also drops build_stages and every '
                            'timing_ms.')
    return document


# --------------------------------------------------------------------------------- near

def near_request(body):
    """What is at, or within a radius of, one terrain node.

    `encounters.by_node` already exists for exactly this question -- the nomads work
    shipped it so "a future quest handler can ask what is near here and when" -- and this
    is that handler's front door.
    """
    world = _body(body, ('api_version', 'world', 'node', 'radius_m'))
    if 'node' not in body:
        raise wrong_type('node', None,
                         {'type': 'integer',
                          'description': 'the terrain node this read is asking about'})
    node = body['node']
    if type(node) is not int:
        raise wrong_type('node', node, {'type': 'integer'})
    radius_m = body.get('radius_m', 0.)
    if type(radius_m) not in (int, float) or radius_m != radius_m or radius_m in (float('inf'), float('-inf')):
        raise wrong_type('radius_m', radius_m, {'type': 'number', 'units': 'm'})
    if radius_m < 0:
        raise out_of_range('radius_m', radius_m, {'type': 'number', 'min': 0, 'units': 'm'})

    size, radius = _require_grid(world)
    count = select.node_count(world)
    if not 0 <= node < count:
        raise refused_by_world('node', node,
                               'This world is grid size %d and carries %d terrain nodes, '
                               'numbered 0..%d.' % (size, count, count - 1))
    ceiling = radius * NEAR_RADIUS_FRACTION
    if radius_m > ceiling:
        raise refused_by_world('radius_m', radius_m,
                               'A near read reaches at most half this globe\'s radius '
                               '(%g m). This world has radius %g m.' % (ceiling, radius))

    rows = select.near_rows(world, node, float(radius_m))
    total = sum(len(v) for v in rows.values())
    if total > MAX_NEAR_ROWS:
        # Refused rather than truncated. A truncated answer to "what is near here" is a
        # wrong answer that looks complete, and the caller has a remedy it can apply.
        raise over_capacity('near.rows', total, MAX_NEAR_ROWS, 'rows per read; ask a smaller radius_m')

    cell = select.node_cell(world, node)
    document = _envelope('near', world)
    document['node'] = node
    document['radius_m'] = float(radius_m)
    document['radius_ceiling_m'] = ceiling
    document['row_ceiling'] = MAX_NEAR_ROWS
    document['rows'] = total
    document['cell'] = dict(cell, layers=select.layer_sample(world, cell['x'], cell['z']))
    document['near'] = rows
    document['joins'] = [
        {'name': 'encounters', 'from': 'encounters.by_node["<node>"]',
         'to': 'encounters.occupancy[].entry -> encounters.entries[]',
         'writer': 'Sim/icarus_sim/terrain_encounters.py:89'},
        {'name': 'distance', 'from': 'the node direction',
         'to': 'great-circle metres on effective_config.globe_radius',
         'writer': 'Sim/icarus_sim/terrain_erosion.py:30'},
    ]
    return document


# -------------------------------------------------------------------------------- place

def place_request(body):
    """One settlement, hamlet, fortress or key location by id, with its joins resolved.

    The joins are the generator's own and belong on this side of the boundary. A consumer
    reimplementing them has to be right about a vocabulary where `tier` means four things
    and `status` names five, against blocks that disagree on field names -- and a near miss
    answers a different question without raising.
    """
    world = _body(body, ('api_version', 'world', 'place_id'))
    place_id = body.get('place_id')
    if not isinstance(place_id, str) or not place_id:
        raise wrong_type('place_id', place_id,
                         {'type': 'string',
                          'description': 'a settlement uid, a hamlet or fortress id, or a '
                                         'key location id'})
    if not isinstance(world.get('settlements'), dict):
        raise missing_block('settlements', 'This world carries no settlements, so it has no '
                            'places to look in. Generate it through founding (phase 9).')
    found = select.place_document(world, place_id, MAX_PLACE_POSTS)
    if found is None:
        raise unknown_field(place_id, [pid for pid, _kind in select.place_ids(world)],
                            noun='place id')
    document = _envelope('place', world)
    document.update(found)
    document['post_ceiling'] = MAX_PLACE_POSTS
    return document


# ------------------------------------------------------------------------------- person

def person_request(body):
    """One hero, NPC or villain by uid, with liveness resolved through the one predicate.

    A caller must never have to know which of the five `status` vocabularies applies to the
    record it just received. `terrain_liveness.liveness` dispatches on the block a record
    came from, refuses a record carrying `people`, `quest_hooks` or `policy_revision`, and
    reads an absent status as present.
    """
    world = _body(body, ('api_version', 'world', 'uid'))
    uid = body.get('uid')
    if not isinstance(uid, str) or not uid:
        raise wrong_type('uid', uid, {'type': 'string',
                                      'description': 'a hero, dread, npc or villain uid'})
    if not any(isinstance(world.get(name), dict) for name in ('heroes', 'npcs', 'villains')):
        raise missing_block('heroes', 'This world carries no heroes, npcs or villains, so it '
                            'names no people. Generate it through the cast (phase 16).')
    found = select.person_document(world, uid)
    if found is None:
        raise unknown_field(uid, list(select.person_index(world)), noun='person uid')
    document = _envelope('person', world)
    document.update(found)
    return document


# ------------------------------------------------------------------------------- quests

def quests_request(body):
    """Open, taken and recently closed quests, with giver and anchor resolved.

    From the `quests` block the time capability writes and nothing else writes. A world
    that has never been advanced carries no board at all, and that is refused as
    `missing_block` rather than answered with an empty list: no quests and no quest
    lifecycle are different facts, and a controller that cannot tell them apart concludes
    the world is quiet when it has simply never had a clock.
    """
    world = _body(body, ('api_version', 'world', 'states'))
    states = body.get('states')
    if states is not None:
        if not isinstance(states, list):
            raise wrong_type('states', states,
                             {'type': 'array', 'description': 'quest states to include'})
        for state in states:
            if state not in select.QUEST_STATES:
                raise invalid_choice('states', state, {'choices': list(select.QUEST_STATES)})
    _require_block(world, 'quests',
                   'This world carries no quest board. It is written by the time '
                   'capability, so advance the world by at least a day first '
                   '(POST /world/advance-time).')
    rows = select.quest_rows(world, states, select.person_index(world))
    if len(rows) > MAX_QUEST_ROWS:
        raise over_capacity('quests.rows', len(rows), MAX_QUEST_ROWS,
                            'rows per read; narrow the states filter')
    document = _envelope('quests', world)
    document['quests'] = rows
    document['counts'] = select.quest_counts(world)
    document['states'] = None if states is None else list(states)
    document['row_ceiling'] = MAX_QUEST_ROWS
    document['joins'] = [
        {'name': 'giver', 'from': 'quests.quests[].giver_uid',
         'to': 'heroes.people[].uid / heroes.dreads[].uid / npcs.people[].uid',
         'writer': 'Sim/icarus_sim/terrain_time.py:269'},
        {'name': 'anchor', 'from': 'quests.quests[].anchor',
         'to': 'carried verbatim from heroes.quest_hooks[].target',
         'writer': 'Sim/icarus_sim/terrain_time.py:338'},
    ]
    return document


#: The five reads, by the name their route carries. A host dispatching on a verb reads this
#: rather than repeating the table.
READS = {
    'blocks': blocks_request,
    'near': near_request,
    'place': place_request,
    'person': person_request,
    'quests': quests_request,
}
