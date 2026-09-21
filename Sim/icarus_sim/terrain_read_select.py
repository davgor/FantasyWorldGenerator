"""Pure selection over a world that already exists. The half of the read surface with no request.

A selector takes a world and plain arguments and returns rows. It validates nothing, raises
nothing versioned, mints nothing and mutates nothing, so every claim about *what is in a
world* is testable without building a request body -- the same split
`terrain_time_schedule` keeps from `terrain_time`, for the same reason: the determinism
argument and the join argument both live on this side, where they can be checked in
milliseconds.

**Every join here is the writer's own field, and the writing site is named beside it.**
Resolving a join is writing a second implementation of it, and a near miss -- `endswith`
for equality, a node where the writer keyed on an id, a positional index where the writer
wrote a foreign key -- answers a different question and looks correct. The comments name
files and lines so the next reader can check the mirror rather than re-deriving it. Where
two fields would agree on today's world and only one is the writer's, the writer's is used.

**Ids that renumber are never returned alone.** Hamlet, fortress, plot, nest and culture
ids are ordinals re-derived at every age boundary, so anything this module returns spells
out the terrain node as well. `Sim/npc_roster/sites.py` states the same rule and anchors
its own site keys on nodes for it.

Nothing here reads `STATE_KEYS` by restating it; it is imported, because the whole point of
the `blocks` read is to disagree with a world rather than with a copied list.
"""

import json
import math

from .terrain_erosion import sphere_grid
from .terrain_history import STATE_KEYS
from .terrain_liveness import liveness

SELECT_VERSION = 1

#: The categories `near` answers with, in a fixed order so a caller can rely on the keys.
NEAR_CATEGORIES = ('settlements', 'hamlets', 'fortresses', 'key_locations', 'beast_nests',
                   'ley_nodes', 'encounters')

#: The kinds of thing `place` resolves, in the order `place_ids` lists them.
PLACE_KINDS = ('city', 'hamlet', 'fortress', 'key_location')

#: Every state `terrain_time` writes into `quests.quests[].state`. Not widened here: this
#: module reads the board, and a state this vocabulary invents would be a state no writer
#: can produce. See `docs/conformance/time-advance.md`, "Artifacts it writes".
QUEST_STATES = ('offered', 'taken', 'expired', 'completed', 'failed', 'abandoned')

#: The person blocks, in the order `terrain_time._giver_index` walks them. First writer of
#: a uid wins, exactly as it does there, so giver resolution cannot disagree with the
#: capability that closes a quest when a giver is gone. `villains` is appended rather than
#: inserted, so every uid that index resolves resolves identically here.
PERSON_BLOCKS = (('heroes', 'heroes', 'people'), ('heroes', 'dreads', 'dreads'),
                 ('npcs', 'npcs', 'people'), ('villains', 'villains', 'people'))

#: Blocks whose ids survive an age advance, and blocks whose ids are ordinals that do not.
#: `docs/conformance/settlement-founding.md` and `Contracts/schemas/key-locations.schema.json`
#: both state their half; `board/backlog/SDET-SITE-ID-ORDINALS.md` states the other.
STABLE_PLACE_KINDS = frozenset({'city', 'key_location'})


# ------------------------------------------------------------------ the canonical encoding

def encode(value):
    """The bytes this value would occupy, in the encoding the transfer form uses.

    Sorted keys, no whitespace, UTF-8, NaN and Infinity refused -- the same four choices
    `fantasy_world_generator.world_handle.transfer_bytes` makes, stated here rather than
    imported because `icarus_sim` imports nothing from `fantasy_world_generator` and that
    arrow must not reverse.

    It is the same *encoding* and not the same *document*: the transfer form also drops
    `build_stages` at the top level and `timing_ms` at every depth, and that rule stays
    where it is written. So the number this returns for a block is what the block costs as
    the world carries it, which is what a caller deciding whether to ask for it needs.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def byte_size(value):
    """The encoded length, or `None` for a value JSON cannot carry.

    A world holding a NaN is a world no host can name, and saying which block holds it is
    more use than failing the whole report.
    """
    try:
        return len(encode(value))
    except (ValueError, TypeError, OverflowError):
        return None


def _json_type(value):
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, dict):
        return 'object'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, (int, float)):
        return 'number'
    return 'null'


def _declared_version(value):
    """`block['version']`, only when the block actually declares an integer one."""
    if not isinstance(value, dict):
        return None
    version = value.get('version')
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


# ------------------------------------------------------------------------------- blocks

def block_rows(world):
    """One row per top-level key this world carries, sorted by name.

    Walking the *world* rather than `STATE_KEYS` is the whole design. A report built from
    the registry would omit a block the world carries and the registry does not, which is
    precisely the `materialize_stage` failure `docs/conformance/nomads.md` and
    `docs/conformance/time-advance.md` both document -- a block missing from the tuple is
    reported at every stage as though it had always been there. Here it shows up as
    `registered: false` instead of not showing up.

    Sorted by name because that is the order the transfer bytes are written in
    (`sort_keys=True`), so the report lists blocks in the order they cross. A world dict's
    insertion order is an artefact of which pass ran first and is published nowhere.
    """
    registry = set(STATE_KEYS)
    rows = []
    for name in sorted(world):
        value = world[name]
        size = byte_size(value)
        rows.append({
            'name': name,
            'registered': name in registry,
            'version': _declared_version(value),
            'type': _json_type(value),
            'count': len(value) if isinstance(value, (dict, list)) else None,
            'bytes': size,
            'encodable': size is not None,
        })
    return rows


def block_summary(world):
    """The `blocks` answer: the rows, plus both directions of disagreement with the registry."""
    rows = block_rows(world)
    return {
        'blocks': rows,
        'total_bytes': sum(row['bytes'] for row in rows if row['bytes'] is not None),
        'unregistered': [row['name'] for row in rows if not row['registered']],
        'absent': sorted(set(STATE_KEYS) - set(world)),
        'unencodable': [row['name'] for row in rows if not row['encodable']],
        'registered_count': sum(1 for row in rows if row['registered']),
        'state_keys': len(STATE_KEYS),
    }


# ------------------------------------------------------------------------------ geometry

def grid_size(world):
    return (world.get('config') or {}).get('size')


def globe_radius(world):
    """The radius every distance in a world is measured against.

    `effective_config` first, falling back to `config`, which is the same precedence
    `terrain_patch.generate_patch` uses at `Sim/icarus_sim/terrain_patch.py:51`.
    """
    effective = world.get('effective_config')
    if isinstance(effective, dict) and 'globe_radius' in effective:
        return effective['globe_radius']
    return (world.get('config') or {}).get('globe_radius')


def _points(world):
    """The generator's own node list, from the generator's own function.

    `sphere_grid` is `lru_cache`d on `(n, radius)` and its result is shared by every
    caller in the tree, so this is a dictionary lookup after the first world.
    """
    return sphere_grid(grid_size(world), globe_radius(world))[0]


def node_count(world):
    """How many terrain nodes this world has. Nodes are numbered `0..count-1`."""
    return len(_points(world))


def node_cell(world, node):
    """`{node, x, z, direction}` for one terrain node.

    `x` and `z` index the layer grids; `direction` is the unit vector
    `terrain_globe.direction` gives that cell, which is what every placed thing in a world
    carries as its own `direction`.
    """
    from .terrain_globe import direction
    x, z = _points(world)[node]
    return {'node': node, 'x': x, 'z': z, 'direction': list(direction(x, z, grid_size(world)))}


def arc_distance_m(radius, a, b):
    """Great-circle metres between two unit directions.

    The same expression `terrain_erosion.sphere_grid` uses to measure a node's distance to
    its neighbours, clamp included. Two implementations of one distance is how a radius
    query starts disagreeing with the grid it is querying.
    """
    dot = sum(p * q for p, q in zip(a, b))
    return radius * math.acos(max(-1., min(1., dot)))


def layer_sample(world, x, z):
    """Every layer field at one cell, by the layer's own name.

    An exact read of `world['layers'][name][z][x]`, never a recomputation: a formula that
    re-derives a field drifts from the generator by a float, which is the defect
    `docs/conformance/settlement-founding.md` records for the eight terrain fields.
    """
    out = {}
    for name, grid in sorted((world.get('layers') or {}).items()):
        try:
            out[name] = grid[z][x]
        except (IndexError, TypeError, KeyError):
            continue
    return out


# ---------------------------------------------------------------------------------- near

def _near_settlements(world, measure):
    rows = []
    for site in (world.get('settlements') or {}).get('sites') or []:
        distance = measure(site.get('direction'), site.get('node'))
        if distance is None:
            continue
        rows.append({'uid': site.get('uid'), 'id': site.get('id'), 'kind': site.get('kind'),
                     'name': site.get('name'), 'node': site.get('node'),
                     'x': site.get('x'), 'z': site.get('z'),
                     'city_class': site.get('city_class'),
                     'population_profile': site.get('population_profile'),
                     'distance_m': distance})
    return rows


def _near_small_sites(world, measure, key):
    """`humans.hamlets` and `humans.fortresses`, written by `terrain_humans.record`
    (`Sim/icarus_sim/terrain_humans.py:157`). Their `id` is an ordinal that renumbers at an
    age boundary, so `node` rides along and `core_id` is reported as the positional index
    into `settlements.sites` that the writer stored -- `Sim/npc_roster/sites.py:66` states
    the same thing about the same field.

    `id_survives_an_age: False` is still the honest answer about the `id`, and the row now
    under-reports: the source record also carries a node-keyed `uid` that does survive. Adding
    it here is additive to a published read contract that belongs to PRODUCT-READ-SURFACE, so it
    is left to that lane rather than taken in passing; see board/done/SDET-SITE-ID-ORDINALS.md."""
    rows = []
    for record in (world.get('humans') or {}).get(key) or []:
        distance = measure(None, record.get('node'))
        if distance is None:
            continue
        rows.append({'id': record.get('id'), 'kind': record.get('kind'),
                     'node': record.get('node'), 'x': record.get('x'), 'z': record.get('z'),
                     'core_id': record.get('core_id'),
                     'population_profile': record.get('population_profile'),
                     'id_survives_an_age': False, 'distance_m': distance})
    return rows


def _near_key_locations(world, measure):
    rows = []
    for site in (world.get('key_locations') or {}).get('sites') or []:
        distance = measure(site.get('direction'), site.get('node'))
        if distance is None:
            continue
        rows.append({'id': site.get('id'), 'kind': site.get('kind'), 'name': site.get('name'),
                     'family': site.get('family'), 'node': site.get('node'),
                     'x': site.get('x'), 'z': site.get('z'),
                     # `tier` here is physical scale and `threat` is danger. They are
                     # different numbers on the same row and the schema says so; both are
                     # carried so a caller never has to pick the wrong one.
                     'tier': site.get('tier'), 'threat': site.get('threat'),
                     'state': site.get('state'), 'occupant': site.get('occupant'),
                     'distance_m': distance})
    return rows


def _near_nests(world, measure):
    rows = []
    for site in (world.get('beast_nests') or {}).get('sites') or []:
        distance = measure(site.get('direction'), site.get('node'))
        if distance is None:
            continue
        rows.append({'id': site.get('id'), 'species_id': site.get('species_id'),
                     'name': site.get('name'), 'node': site.get('node'),
                     'x': site.get('x'), 'z': site.get('z'),
                     # Creature tier: danger, one to five. Not the key-location tier.
                     'tier': site.get('tier'), 'family': site.get('family'),
                     'range_m': site.get('range_m'), 'distance_m': distance})
    return rows


def _near_ley_nodes(world, measure):
    """`magic.networks[school].nodes[]`, written by `terrain_leyline_history.py:112`.

    A ley node carries a `direction` and no terrain node at all, so it is placed by arc
    distance and reported without one. Schools are walked in `magic.school_order`, which is
    the order the writer built the dict in, so two reads of one world list them alike.
    """
    magic = world.get('magic') or {}
    networks = magic.get('networks') or {}
    order = [s for s in (magic.get('school_order') or []) if s in networks]
    order += [s for s in networks if s not in order]
    rows = []
    for school in order:
        network = networks[school] or {}
        for node in network.get('nodes') or []:
            distance = measure(node.get('direction'), None)
            if distance is None:
                continue
            rows.append({'id': node.get('id'), 'school': school,
                         'group': network.get('group'),
                         'intensity': node.get('intensity'),
                         'node': None, 'distance_m': distance})
    return rows


def _near_encounters(world, measure):
    """Occupancy rows, through the index `terrain_encounters.add_encounters` built for it.

    `by_node` is keyed on `str(node)` and holds indices into `occupancy`; each occupancy row
    holds `entry`, an index into `entries` (`Sim/icarus_sim/terrain_encounters.py:89`). All
    three steps are the writer's own, and the order within a node is the order it appended.
    A radius widens the set of nodes consulted; it never changes how a node is resolved.
    """
    block = world.get('encounters') or {}
    by_node = block.get('by_node') or {}
    occupancy = block.get('occupancy') or []
    entries = block.get('entries') or []
    rows = []
    for key in sorted(by_node, key=lambda k: int(k)):
        there = int(key)
        distance = measure(None, there)
        if distance is None:
            continue
        for index in by_node[key]:
            if not 0 <= index < len(occupancy):
                continue
            record = occupancy[index]
            entry = entries[record['entry']] if 0 <= record.get('entry', -1) < len(entries) else {}
            rows.append({'occupancy': index, 'node': record.get('node'),
                         'camp_id': record.get('camp_id'), 'camp_kind': record.get('camp_kind'),
                         'from_day': record.get('from_day'), 'to_day': record.get('to_day'),
                         'months': list(record.get('months') or []),
                         'group_uid': entry.get('group_uid'), 'source': entry.get('source'),
                         'group_kind': entry.get('kind'),
                         'disposition': entry.get('disposition'),
                         'threat_tier': entry.get('threat_tier'), 'size': entry.get('size'),
                         'distance_m': distance})
    return rows


def near_rows(world, node, radius_m):
    """Everything within `radius_m` of one terrain node, by category.

    Each category is ordered by distance and then by the order its writer produced it --
    a stable sort over the writer's own iteration, so a read never claims an order the
    generator did not have. `distance_m` is zero for anything standing on the node itself.
    """
    radius = globe_radius(world)
    here = node_cell(world, node)
    origin = here['direction']
    points = _points(world)
    size = grid_size(world)
    from .terrain_globe import direction as cell_direction

    def measure(vector, other_node):
        """Metres from the query node, or None when this row is outside the radius.

        **Two things standing on one node are at one node, by identity and not by
        arithmetic.** `acos` loses about half its digits next to a dot product of one, so a
        cell measured against itself geometrically comes out four tenths of a millimetre
        away on this world and scales with the radius. Answered from the node the writer
        stored, a zero-radius query means exactly what it says; answered from an arc
        length, it finds nothing at all and looks like an empty neighbourhood.

        Otherwise a row's own `direction` is preferred, because it is what its writer
        stored; a row with only a node is placed at that node's cell. A row with neither
        cannot be placed and is dropped rather than guessed at.
        """
        if other_node is not None and other_node == node:
            return 0.
        if vector is None and other_node is not None:
            if not 0 <= other_node < len(points):
                return None
            x, z = points[other_node]
            vector = cell_direction(x, z, size)
        if vector is None or len(vector) != 3:
            return None
        distance = arc_distance_m(radius, origin, vector)
        return distance if distance <= radius_m + 1e-9 else None

    rows = {
        'settlements': _near_settlements(world, measure),
        'hamlets': _near_small_sites(world, measure, 'hamlets'),
        'fortresses': _near_small_sites(world, measure, 'fortresses'),
        'key_locations': _near_key_locations(world, measure),
        'beast_nests': _near_nests(world, measure),
        'ley_nodes': _near_ley_nodes(world, measure),
        'encounters': _near_encounters(world, measure),
    }
    for category in rows:
        rows[category].sort(key=lambda row: row['distance_m'])
    return rows


# --------------------------------------------------------------------------------- place

def place_ids(world):
    """Every `(id, kind)` `place` accepts, in block order.

    Cities by `settlements.sites[].uid` (`terrain_history.py:266` mints it and
    `terrain_settlements.py:914` carries it across a rebuild), hamlets and fortresses by
    `humans.<list>[].id` (`terrain_humans.py:149`), key locations by
    `key_locations.sites[].id` (node-derived and documented stable in
    `Contracts/schemas/key-locations.schema.json`).
    """
    out = []
    for site in (world.get('settlements') or {}).get('sites') or []:
        if site.get('uid'):
            out.append((site['uid'], 'city'))
    humans = world.get('humans') or {}
    for key, kind in (('hamlets', 'hamlet'), ('fortresses', 'fortress')):
        for record in humans.get(key) or []:
            if record.get('id'):
                out.append((record['id'], kind))
    for site in (world.get('key_locations') or {}).get('sites') or []:
        if site.get('id'):
            out.append((site['id'], 'key_location'))
    return out


def find_place(world, place_id):
    """`(row, kind)` for one place id, matched on the exact field its writer wrote.

    Equality, never a prefix or a suffix test: `surface-city-0-10-x` and
    `surface-city-0-100-x` share a prefix, and `hamlet-1` is a suffix of `hamlet-11`.
    """
    for site in (world.get('settlements') or {}).get('sites') or []:
        if site.get('uid') == place_id:
            return site, 'city'
    humans = world.get('humans') or {}
    for key, kind in (('hamlets', 'hamlet'), ('fortresses', 'fortress')):
        for record in humans.get(key) or []:
            if record.get('id') == place_id:
                return record, kind
    for site in (world.get('key_locations') or {}).get('sites') or []:
        if site.get('id') == place_id:
            return site, 'key_location'
    return None, None


def _plan_summary(block_name, block, rows_key, id_field, wanted, writer):
    """A plan's identity, status and size -- never its body.

    `status` is carried verbatim from the plan row and is **not** one vocabulary. The three
    site planners write `complete | partial | unbuildable` and `key_locations` writes
    `complete | empty`, so the caller is told which block answered and the two are returned
    under different keys rather than merged.

    A city plan is most of a megabyte on a size-17 world and `place` is supposed to be
    kilobytes, so the plan is named and measured rather than shipped. `bytes` is what it
    would cost, so a caller deciding to fetch it is deciding with a number.
    """
    rows = (block or {}).get(rows_key)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if row.get(id_field) == wanted:
            return {'block': block_name, 'id_field': id_field, 'id': wanted,
                    'status': row.get('status'), 'version': row.get('version'),
                    'plots': len(row.get('plots') or []),
                    'unplaced': len(row.get('unplaced') or []),
                    'bytes': byte_size(row), 'writer': writer}
    return None


def _npc_site(world, uid):
    """The roster's own row for a site key, matched on `npcs.sites[].uid`.

    City keys are the settlement uid unchanged; hamlet and fortress keys are
    `hamlet-node-<node>` and `fortress-node-<node>`, minted at
    `Sim/npc_roster/sites.py:100` and `:116` because the ordinal ids renumber every age.
    That is why this takes a key rather than a place id.
    """
    for row in (world.get('npcs') or {}).get('sites') or []:
        if row.get('uid') == uid:
            return row
    return None


def _npc_posts(world, site_uid, limit):
    """The roster rows filed under one site key, in the order the roster sorted them.

    `npcs.people[].site_uid` is the field (`Sim/npc_roster/__init__.py:91`), and the list
    is already sorted by `(site_uid, building_id, uid)` at `:101`, so preserving order here
    preserves the writer's.

    Projected rather than copied: a capital holds hundreds of posts and the full records
    are what `person` is for. `post_count` is the true total either way.
    """
    posts, total = [], 0
    for person in (world.get('npcs') or {}).get('people') or []:
        if person.get('site_uid') != site_uid:
            continue
        total += 1
        if len(posts) < limit:
            posts.append({'uid': person.get('uid'), 'name': person.get('name'),
                          'post': person.get('post'), 'building_id': person.get('building_id'),
                          'status': person.get('status'), 'important': person.get('important'),
                          'hero_uid': person.get('hero_uid')})
    return posts, total


def place_document(world, place_id, max_posts):
    """One place with the rows that join to it resolved, or `None` if no such id exists."""
    row, kind = find_place(world, place_id)
    if row is None:
        return None
    joins = []
    resolved = {}
    node = row.get('node')
    sites = (world.get('settlements') or {}).get('sites') or []

    if kind == 'city':
        site_id = row.get('id')
        # `humans.cores[].site_id` is the key the writer stored (terrain_humans.py:222),
        # not the position of the core in its list. They coincide today because cores are
        # appended in site order; matching the field is what keeps that a coincidence
        # rather than a dependency.
        resolved['core'] = None
        for core in (world.get('humans') or {}).get('cores') or []:
            if core.get('site_id') == site_id:
                resolved['core'] = core
                break
        joins.append({'name': 'core', 'from': 'settlements.sites[].id',
                      'to': 'humans.cores[].site_id',
                      'writer': 'Sim/icarus_sim/terrain_humans.py:222'})
        seasonal = world.get('seasonal_food') or {}
        resolved['seasonal_food_model'] = resolved['seasonal_food_summary'] = None
        for model in seasonal.get('models') or []:
            if model.get('site_id') == site_id:
                resolved['seasonal_food_model'] = model
                break
        for summary in seasonal.get('cities') or []:
            if summary.get('site_id') == site_id:
                resolved['seasonal_food_summary'] = summary
                break
        joins.append({'name': 'seasonal_food', 'from': 'settlements.sites[].id',
                      'to': 'seasonal_food.models[].site_id',
                      'writer': 'Sim/icarus_sim/terrain_seasons.py:83'})
        resolved['plan'] = _plan_summary('city_plans', world.get('city_plans'), 'cities',
                                         'city_uid', place_id,
                                         'Sim/icarus_sim/city_planner.py:134')
        joins.append({'name': 'plan', 'from': 'settlements.sites[].uid',
                      'to': 'city_plans.cities[].city_uid',
                      'writer': 'Sim/icarus_sim/city_planner.py:134'})
        roster_key = place_id
    elif kind in ('hamlet', 'fortress'):
        # `core_id` is a POSITION in `settlements.sites`, not a uid. The small-site builder
        # stores `owner[i]` and the planners dereference it by index; `Sim/npc_roster/sites.py:66`
        # records the same trap. The site's own `id` equals that position, which
        # `docs/conformance/settlement-founding.md` makes an invariant, so the index is
        # checked against it rather than trusted.
        core_id = row.get('core_id')
        if isinstance(core_id, int) and 0 <= core_id < len(sites):
            core_site = sites[core_id]
            if core_site.get('id') == core_id:
                resolved['core_city'] = {'uid': core_site.get('uid'), 'id': core_site.get('id'),
                                         'node': core_site.get('node'),
                                         'name': core_site.get('name')}
        resolved.setdefault('core_city', None)
        joins.append({'name': 'core_city',
                      'from': 'humans.%s[].core_id' % ('hamlets' if kind == 'hamlet' else 'fortresses'),
                      'to': 'settlements.sites[] index',
                      'writer': 'Sim/icarus_sim/terrain_humans.py:149'})
        if kind == 'hamlet':
            resolved['plan'] = _plan_summary('hamlet_plans', world.get('hamlet_plans'),
                                             'hamlets', 'hamlet_id', place_id,
                                             'Sim/icarus_sim/hamlet_planner.py:112')
            joins.append({'name': 'plan', 'from': 'humans.hamlets[].id',
                          'to': 'hamlet_plans.hamlets[].hamlet_id',
                          'writer': 'Sim/icarus_sim/hamlet_planner.py:112'})
        else:
            resolved['plan'] = _plan_summary('castle_plans', world.get('castle_plans'),
                                             'castles', 'fortress_id', place_id,
                                             'Sim/icarus_sim/castle_planner.py:233')
            joins.append({'name': 'plan', 'from': 'humans.fortresses[].id',
                          'to': 'castle_plans.castles[].fortress_id',
                          'writer': 'Sim/icarus_sim/castle_planner.py:233'})
        roster_key = '%s-node-%s' % (kind, node)
    else:
        # Reported under its own key, not under `plan`. A key-location plan's `status` is
        # `complete | empty` -- does this plan have contents -- and a city, hamlet or castle
        # plan's is `complete | partial | unbuildable` -- was this plan fully placed. Two
        # questions, and `complete` is in both, which is the overload
        # `board/backlog/SDET-STATUS-VOCABULARY.md` records. Returning them under one key
        # would publish that collision at a new boundary and let a consumer compare them.
        resolved['location_plan'] = _plan_summary(
            'key_location_plans', world.get('key_location_plans'), 'plans', 'location_id',
            place_id, 'Sim/key_locations/core/exterior.py:190')
        joins.append({'name': 'location_plan', 'from': 'key_locations.sites[].id',
                      'to': 'key_location_plans.plans[].location_id',
                      'writer': 'Sim/key_locations/core/exterior.py:190'})
        # The roster staffs cities, hamlets and fortresses only; its `kind` vocabulary is
        # open and key locations are expected to join it later. Until they do, asking for
        # a roster key here would invent one.
        roster_key = None

    if roster_key is not None:
        resolved['npc_site'] = _npc_site(world, roster_key)
        posts, total = _npc_posts(world, roster_key, max_posts)
        resolved['npc_posts'] = posts
        resolved['post_count'] = total
        resolved['posts_truncated'] = total > len(posts)
        joins.append({'name': 'npc_posts', 'from': 'npcs.sites[].uid',
                      'to': 'npcs.people[].site_uid',
                      'writer': 'Sim/npc_roster/__init__.py:91'})
    else:
        resolved['npc_site'] = None
        resolved['npc_posts'] = []
        resolved['post_count'] = 0
        resolved['posts_truncated'] = False

    # Both plan keys are always present, and exactly one of them can ever be filled: a
    # place is of one kind and the two plan vocabularies never meet on one row.
    resolved.setdefault('plan', None)
    resolved.setdefault('location_plan', None)

    anchor = {'id': place_id, 'kind': kind, 'node': node,
              'x': row.get('x'), 'z': row.get('z'),
              'roster_key': roster_key,
              'id_survives_an_age': kind in STABLE_PLACE_KINDS}
    return {'anchor': anchor, 'place': row, 'resolved': resolved, 'joins': joins}


# -------------------------------------------------------------------------------- person

def person_index(world):
    """`uid -> (record, block)` for every person a world names.

    The first three entries of `PERSON_BLOCKS` and their first-writer-wins rule are
    `terrain_time._giver_index` (`Sim/icarus_sim/terrain_time.py:269`) exactly; `villains`
    is appended after them, so every uid that index resolves resolves to the same record
    here and a quest's giver cannot be reported as one person by the read and treated as
    another by the tick.

    A block that failed to generate carries `status: 'failed'` and no cast, and is skipped
    for the same reason `terrain_liveness.census` skips it: no people and a missing package
    are different facts.
    """
    index = {}
    for key, block, listing in PERSON_BLOCKS:
        container = world.get(key)
        if not isinstance(container, dict):
            continue
        if key != 'villains' and container.get('status') != 'ok':
            continue
        for record in container.get(listing) or []:
            if not isinstance(record, dict):
                continue
            uid = record.get('uid')
            if uid is not None and uid not in index:
                index[uid] = (record, block)
    return index


def _settlement_nodes(world):
    """`uid -> node` for the cities a world still has, and for the ones it used to have.

    A cast presence names a city uid, and an age advance ruins cities: the record moves from
    `settlements.sites` to `ruins`, keeping the same `uid` and the same `node`
    (`Sim/icarus_sim/terrain_history.py:366` mints the ruin's own `id` as `'ruin-' + uid`
    and leaves the city's `uid` on the row). `Sim/npc_roster/sites.py:194` handles the same
    case from the other direction, by trying `ruin-<uid>` against its own index; matching
    `ruins[].uid` is the same fact without the string surgery.

    Living cities are indexed first, so a uid that is somehow both resolves to the standing
    city rather than to its own ruin.
    """
    nodes = {site['uid']: site.get('node')
             for site in (world.get('settlements') or {}).get('sites') or []
             if site.get('uid')}
    for ruin in world.get('ruins') or []:
        if isinstance(ruin, dict) and ruin.get('uid') and ruin.get('node') is not None:
            nodes.setdefault(ruin['uid'], ruin['node'])
    return nodes


def person_anchor(world, record, block):
    """Where this person stands, spelled out as a terrain node wherever one is knowable.

    Three different blocks answer it three different ways and none of them is a guess:

    * `villains` carries `node` on the record (`Contracts/schemas/villains.schema.json`).
    * `npcs` carries `presence_node` when the person's true placement differs from the site
      they are filed under, and otherwise the node of their `site_uid` row. That precedence
      is the roster's own, at `Sim/npc_roster/__init__.py:194-197`.
    * `heroes` and `dreads` carry no node at all. Their `presence` and `home` are site refs
      in the cast's namespace, so the anchor is resolved by matching those uids against
      `settlements.sites[].uid` and then against `ruins[].uid`, presence first, which is the
      same precedence the roster applies when it decides where a cast member actually
      stands. A presence naming a camp, college, port, shrine or nest resolves to neither
      and is reported unresolved rather than approximated by the home.
    """
    if block == 'villains':
        return {'node': record.get('node'), 'source': 'villains.people[].node',
                'uid': record.get('seat_uid'), 'unresolved_uid': None}
    if block == 'npcs':
        if record.get('presence_node') is not None:
            return {'node': record.get('presence_node'), 'source': 'npcs.people[].presence_node',
                    'uid': record.get('presence_uid'), 'unresolved_uid': None}
        site = _npc_site(world, record.get('site_uid'))
        return {'node': (site or {}).get('node'), 'source': 'npcs.sites[].node',
                'uid': record.get('site_uid'),
                'unresolved_uid': None if site or not record.get('site_uid') else record.get('site_uid')}
    nodes = _settlement_nodes(world)
    presence = (record.get('presence') or {}).get('uid')
    home = (record.get('home') or {}).get('uid')
    standing = {site['uid'] for site in (world.get('settlements') or {}).get('sites') or []
                if site.get('uid')}
    for uid in (presence, home):
        if uid in nodes:
            return {'node': nodes[uid],
                    'source': 'settlements.sites[].uid' if uid in standing else 'ruins[].uid',
                    'uid': uid, 'unresolved_uid': None}
    return {'node': None, 'source': None, 'uid': presence or home,
            'unresolved_uid': presence or home}


def person_document(world, uid):
    """One person, with liveness resolved through the one predicate, or `None`."""
    entry = person_index(world).get(uid)
    if entry is None:
        return None
    record, block = entry
    return {'block': block, 'person': record,
            # `terrain_liveness.liveness` dispatches on the block, refuses a block handed
            # to it in place of a person, and reads an absent status as present. A caller
            # must never have to know which of the five `status` vocabularies applies.
            'liveness': liveness(record, block),
            'anchor': person_anchor(world, record, block)}


# -------------------------------------------------------------------------------- quests

def quest_rows(world, states, person_lookup):
    """The quest board with giver and anchor resolved, in the order the writer sorted it.

    `terrain_time._quest_step` sorts `quests.quests` by `quest_id` on every step
    (`Sim/icarus_sim/terrain_time.py:361`); this preserves that order rather than imposing
    one. `anchor` and `verb` are carried verbatim from the row -- they are the contract's
    own fields, derived once by the writer from `heroes.quest_hooks[]`, and re-deriving
    them here would be a second implementation of a rule that already exists.
    """
    board = (world.get('quests') or {}).get('quests') or []
    wanted = None if states is None else set(states)
    rows = []
    for quest in board:
        if wanted is not None and quest.get('state') not in wanted:
            continue
        giver_uid = quest.get('giver_uid')
        entry = person_lookup.get(giver_uid)
        giver = None
        if entry is not None:
            record, block = entry
            giver = {'uid': giver_uid, 'block': block,
                     'name': record.get('display_name') or record.get('name'),
                     'role': record.get('role') or record.get('post'),
                     'liveness': liveness(record, block),
                     'anchor': person_anchor(world, record, block)}
        rows.append({'quest_id': quest.get('quest_id'), 'state': quest.get('state'),
                     'giver_uid': giver_uid, 'giver': giver,
                     'anchor': quest.get('anchor'), 'verb': quest.get('verb'),
                     'stated_purpose': quest.get('stated_purpose'),
                     'unwitting': quest.get('unwitting'),
                     'offered_day': quest.get('offered_day'),
                     'expires_day': quest.get('expires_day'),
                     'closed_day': quest.get('closed_day'),
                     'closed_reason': quest.get('closed_reason')})
    return rows


def quest_counts(world):
    """How many quests stand in each state, over the whole board rather than a filtered view."""
    board = (world.get('quests') or {}).get('quests') or []
    counts = {state: 0 for state in QUEST_STATES}
    other = 0
    for quest in board:
        state = quest.get('state')
        if state in counts:
            counts[state] += 1
        else:
            other += 1
    counts['total'] = len(board)
    if other:
        counts['unknown_state'] = other
    return counts
