"""Found a settlement the player chose, in a world that has to keep working around it.

The player acts in the game; an orchestrator interprets that action and calls this. The
player owns the layout -- where the buildings go is their design -- and the world owns the
metadata, which has to be indistinguishable in kind from a generated settlement or the
twenty-seven modules that read `settlements` start reading a site that is not quite a site.

Stateless in the shape the other request APIs use: a world goes in, a new world comes out,
the caller's object is never touched, and `history.operations` records the call.

## Three things this call refuses to do, each for a reason worth stating

**It does not let the caller set `city_class`.** That field is a per-civilization
*suitability rank*, not a size, and `validate_age_world` re-derives it and refuses the whole
world on a mismatch. So classification is recomputed over the full site list after insertion
-- and because it is a rank, founding a strong site can demote an incumbent. The response
says when that happened rather than letting a consumer discover it.

**It does not run the nest pass.** `terrain_nests._place` opens one sequential RNG over a
fixed cell order whose per-cell draw count depends on distance to the nearest settled thing,
so one new town changes the draw stream in every cell on the planet -- measured at 152 of 248
monster nests replaced, the furthest at the antipode. That is a determinism-contract
violation rather than an expense, which is why it is refused rather than made optional. The
next age advance re-rolls the bestiary anyway; the response says so, because a consumer
holding nest ids deserves the warning at the call that caused it.

**It does not pretend the rural layer is untouched.** `add_humans` re-derives hamlets and
fortresses from scratch in site order with length-at-append-time ids, so adding a city trades
ordinals among the settlements that were already there. Measured on a real world: one city
left eight `hamlet_plans` rows naming no hamlet and ten castellans re-anchored. The rebuild
is still correct -- those ids renumber at every age boundary by design -- but it is not
additive, and the response enumerates what moved.

## Three kinds, two id spaces

`kind` is `city`, `hamlet` or `fortress`. There is no `village`: `settlements.sites[].kind`
is the literal constant `'city'` everywhere in the tree, and small/medium/capital is
`city_class`, a per-civilization suitability rank rather than a size vocabulary. Asking for
one is refused by name rather than quietly given a city.

A city is minted by the generated uid rule verbatim, node-keyed, which survives an age
boundary. A hamlet or a fortress keeps the ordinal `hamlet-N` / `fortress-N` `id` its block
has always used -- `hamlet_plans` and `castle_plans` join on exactly that, and the id space
belongs to `SDET-SITE-ID-ORDINALS` rather than to this call -- and additionally carries the
node-and-kind `uid` `npc_roster` already mints for the same row, `hamlet-node-1062`. That
uid is the handle: the ordinal renumbers at every age boundary, so a player keep keyed on it
would change name under its owner.

## Rebuild: an argument, defaulting to no

The open question this call answers is whether founding rebuilds the dependent blocks
immediately, marks the world dirty for a later tick, or takes an argument. It takes an
argument, and the argument defaults to not rebuilding. Rebuilding is expensive and re-rolls
blocks a consumer may have cached; a dirty flag would put the cost somewhere a caller cannot
see and cannot decline. An argument makes the trade the caller's, at the call that caused it.
"""

import copy
import math
from time import perf_counter

from .terrain_errors import (cross_field, invalid_choice, missing_block, out_of_range,
                             refused_by_world, unknown_field, unsupported_api, wrong_type)

API_VERSION = 2

FIELDS = {'api_version', 'world', 'node', 'kind', 'role', 'civilization_id', 'name',
          'layout', 'population_estimate', 'rebuild'}

KINDS = ('city', 'hamlet', 'fortress')
ROLES = ('farming', 'resource')
REBUILD_CHOICES = ('humans', 'none')

# How far a rural site of each kind is kept from anything already standing, matching
# `terrain_humans.separated`, which spaces generated ones by exactly these metres.
RURAL_SPACING_M = {'hamlet': 120., 'fortress': 200.}

# Written onto a player site so the founding pass can tell it from one it placed itself.
# `terrain_settlements.carry_survivor` carries this key, and `city_layout`, across a
# rebuild for a site that has it -- which is what makes a player-authored layout survive.
# Imported from there rather than redeclared, because two constants that must agree and
# are spelled in two places eventually do not.
from .terrain_settlements import FOUNDED_BY as PLAYER_MARK, PLAYER  # noqa: E402


def _layer(world, name, x, z, default=None):
    grid = world.get('layers', {}).get(name)
    if not isinstance(grid, list):
        return default
    try:
        return grid[z][x]
    except (IndexError, TypeError):
        return default


def _validate(body):
    """Everything that can be judged before the world is copied."""
    if not isinstance(body, dict):
        raise wrong_type('request', body, {'type': 'object'})
    if set(body) - FIELDS:
        raise unknown_field(sorted(set(body) - FIELDS)[0], sorted(FIELDS), noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (API_VERSION,))

    world = body.get('world')
    if not isinstance(world, dict):
        raise wrong_type('world', world, {'type': 'object'})
    for block in ('layers', 'settlements', 'config', 'effective_config'):
        if not isinstance(world.get(block), dict):
            raise missing_block(block, 'Founding a settlement needs a generated recipe 3 '
                                'world; this one carries no %s block.' % block)
    if not isinstance(world['settlements'].get('sites'), list):
        raise missing_block('settlements.sites', 'This world carries no settlement list. '
                            'Cities are placed at stage 9, so generate at least that far.')

    node = body.get('node')
    if type(node) is not int or isinstance(node, bool):
        raise wrong_type('node', node, {'type': 'integer'})
    if node < 0:
        raise out_of_range('node', node, {'type': 'integer', 'min': 0, 'units': 'grid index'})

    kind = body.get('kind', 'city')
    if kind not in KINDS:
        raise invalid_choice('kind', kind, {'type': 'string', 'choices': list(KINDS)})
    if kind != 'city':
        if not isinstance((world.get('humans') or {}).get('hamlets'), list):
            raise missing_block('humans', 'Founding a %s needs a world with a rural layer; '
                                'hamlets and fortresses are raised at stage 9, so generate '
                                'at least that far.' % kind)
        # Both rural blocks key on a parent city by index. A world with none has nothing
        # for the row to answer to, and the two rural planners dereference it directly.
        if not any(s.get('direction') for s in world['settlements']['sites']):
            raise missing_block('settlements.sites', 'A %s answers to a parent city and '
                                'this world has none placed.' % kind)

    role = body.get('role', 'farming')
    if role not in ROLES:
        raise invalid_choice('role', role, {'type': 'string', 'choices': list(ROLES)})

    civilization = body.get('civilization_id')
    if not isinstance(civilization, str):
        raise wrong_type('civilization_id', civilization, {'type': 'string'})

    name = body.get('name')
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise wrong_type('name', name, {'type': 'string'})

    layout = body.get('layout', PLAYER)
    if layout not in (PLAYER, 'generated'):
        raise invalid_choice('layout', layout,
                             {'type': 'string', 'choices': [PLAYER, 'generated']})

    # Default 'none': it leaves every existing join intact. 'humans' gives the new city a
    # hinterland but renumbers the rural layer, which is a trade the caller should make
    # deliberately rather than inherit.
    rebuild = body.get('rebuild', 'none')
    if rebuild not in REBUILD_CHOICES:
        raise invalid_choice('rebuild', rebuild,
                             {'type': 'string', 'choices': list(REBUILD_CHOICES)})

    residents = body.get('population_estimate')
    if residents is not None:
        if type(residents) is not int or isinstance(residents, bool):
            raise wrong_type('population_estimate', residents, {'type': 'integer'})
        if residents < 0:
            raise out_of_range('population_estimate', residents,
                               {'type': 'integer', 'min': 0, 'units': 'residents'})
    return world, node, kind, role, civilization, name, layout, rebuild, residents


def _occupied_nodes(world):
    """Every node a settlement of any kind already stands on, with what stands there.

    A hamlet and a fortress may share a node with nothing, including each other:
    `test_no_two_settlements_share_a_node_in_a_finished_world` pins that across the
    finished world, and a founding that broke it would be found an age later.
    """
    held = {}
    for site in world['settlements']['sites']:
        held[site.get('node')] = site.get('name') or site.get('uid') or 'a city'
    for key, noun in (('hamlets', 'a hamlet'), ('fortresses', 'a fortress')):
        for row in (world.get('humans') or {}).get(key, []) or []:
            held[row.get('node')] = row.get('uid') or row.get('id') or noun
    for ruin in world.get('ruins', []) or []:
        if isinstance(ruin, dict) and ruin.get('node') is not None:
            held.setdefault(ruin['node'], ruin.get('name') or 'a ruin')
    held.pop(None, None)
    return held


def _legality(world, node, kind, civilization):
    """Whether this ground will hold a town of this civilization.

    Every refusal here is `refused_by_world`: the request was well formed and the ground was
    wrong, so the remedy is a different node rather than a different value. A caller that
    cannot tell those apart keeps correcting an argument that was never the problem.
    """
    from .terrain_erosion import sphere_grid
    from .terrain_globe import direction
    from .terrain_profiles import civilization_ids, get_profile

    if civilization not in civilization_ids():
        raise unknown_field(civilization, civilization_ids(), noun='civilization')

    suitability_layer = 'suitability_' + civilization
    if suitability_layer not in world.get('layers', {}):
        present = sorted(k[len('suitability_'):] for k in world['layers']
                         if k.startswith('suitability_'))
        raise refused_by_world(
            'civilization_id', civilization,
            'This world carries no suitability field for %r, so it was generated without '
            'that civilization. Worlds built with an explicit population_profile carry only '
            'that one.' % civilization, alternatives=present)

    config = world['config']
    size = config['size']
    radius = world['effective_config']['globe_radius']
    points, _areas, _ = sphere_grid(size, radius)
    if node >= len(points):
        raise refused_by_world('node', node, 'Node %d is outside this world; it has %d grid '
                               'points.' % (node, len(points)))

    x, z = points[node]
    if _layer(world, 'water_type', x, z, 0):
        raise refused_by_world('node', node, 'A settlement cannot be founded on water; node '
                               '%d is not dry land.' % node)
    if int(_layer(world, 'natural_biome', x, z, 0) or 0) == 17:
        raise refused_by_world('node', node, 'Node %d is persistent land ice, which holds no '
                               'settlement of any civilization.' % node)

    profile = get_profile(civilization)
    slope = _layer(world, 'slope', x, z, 0.) or 0.
    if slope >= profile['site_slope_limit']:
        raise refused_by_world('node', node, 'Node %d has a slope of %.1f degrees and %s will '
                               'not settle at or above %s.'
                               % (node, slope, civilization, profile['site_slope_limit']))

    hazard = _layer(world, 'magic_risk_' + civilization, x, z, None)
    if hazard is None:
        hazard = _layer(world, 'magic_hazard', x, z, 0.) or 0.
    if hazard > profile['mutation_limit']:
        raise refused_by_world('node', node, 'Node %d carries a magical hazard of %.3f and %s '
                               'will not settle above %s.'
                               % (node, hazard, civilization, profile['mutation_limit']))

    held = _occupied_nodes(world)
    if node in held:
        raise refused_by_world('node', node, 'Node %d already holds %s.' % (node, held[node]))

    here = direction(x, z, size)
    if kind == 'city':
        # Cities are spaced by the world's own settlement spacing. Rural kinds are not:
        # a hamlet exists to be near its city, and is held to its own separation below.
        spacing = world['effective_config'].get('settlement_spacing',
                                                config.get('settlement_spacing'))
        if spacing:
            for site in world['settlements']['sites']:
                other = site.get('direction')
                if not other:
                    continue
                dot = max(-1., min(1., sum(a * b for a, b in zip(here, other))))
                metres = radius * math.acos(dot)
                if metres < spacing:
                    raise refused_by_world(
                        'node', node,
                        'Node %d is %.0f m from %s and cities are kept at least %.0f m apart.'
                        % (node, metres, site.get('name') or site.get('uid'), spacing))
    else:
        minimum = RURAL_SPACING_M[kind]
        for other_node, label in sorted(held.items()):
            if other_node >= len(points):
                continue
            ox, oz = points[other_node]
            dot = max(-1., min(1., sum(a * b for a, b in zip(here, direction(ox, oz, size)))))
            metres = radius * math.acos(dot)
            if metres < minimum:
                raise refused_by_world(
                    'node', node,
                    'Node %d is %.0f m from %s and a %s is kept at least %.0f m from '
                    'anything already standing.' % (node, metres, label, kind, minimum))
    return x, z, points, profile


def _authored_layout(civilization, residents):
    """The `city_layout` a player-authored city carries in place of a derived one.

    Shaped like the record `terrain_settlements` builds -- same version, same keys a
    consumer reads -- so a reader does not need a branch. What it says is that the profile
    is the player's, that no district anchors were claimed from the raster, and that no
    assets were drawn. It makes no building-placement claim, because nothing in the
    document does any more: `city_plans` is authoritative for that, and the plan the
    generator writes for this site reports `unbuildable` with the reason.
    """
    from .terrain_settlements import CITY_LAYOUT_VERSION
    return {
        'version': CITY_LAYOUT_VERSION,
        'layout_profile_id': PLAYER, 'layout_profile_name': 'Player-authored layout',
        'population_profile': civilization,
        'population_estimate': residents or 0,
        'river': {'adjacent_river_edges': 0, 'river_distance_m': None,
                  'bridge_recommended': False, 'bridge_threshold': 0},
        'building_pack_id': None,
        'required_assets': [], 'required_asset_count': 0, 'required_node_slots': 0,
        'asset_anchors_missing': False,
        'features': {}, 'constraints': {},
        'authored_by': PLAYER,
    }


def _rural_row(world, node, x, z, kind, role, civilization, name, age):
    """A hamlet or fortress row in the block that already holds them.

    Ordinal `id` in the space the block has always used, because `hamlet_plans` and
    `castle_plans` join on exactly that and the id space is `SDET-SITE-ID-ORDINALS`' to
    change. The node-and-kind `uid` beside it is the handle that survives an age boundary.
    """
    from .terrain_globe import direction
    humans = world.get('humans') or {}
    rows = humans.get('hamlets' if kind == 'hamlet' else 'fortresses', [])
    size = world['config']['size']
    radius = world['effective_config']['globe_radius']

    here = direction(x, z, size)
    core_index, core_distance = None, math.inf
    for index, site in enumerate(world['settlements']['sites']):
        other = site.get('direction')
        if not other:
            continue
        dot = max(-1., min(1., sum(a * b for a, b in zip(here, other))))
        metres = radius * math.acos(dot)
        if metres < core_distance:
            core_index, core_distance = index, metres
    core = world['settlements']['sites'][core_index] if core_index is not None else {}
    culture = next((c['culture_id'] for c in humans.get('cores', [])
                    if c.get('site_id') == core_index), None)

    row = {
        'id': '%s-%d' % (kind, len(rows)),
        'uid': '%s-node-%d' % (kind, node),
        'kind': kind, 'node': node, 'x': x, 'z': z,
        'core_id': core_index,
        'population_profile': civilization,
        'culture_id': culture,
        'height_m': _layer(world, 'height', x, z, 0.),
        # No search stood behind this site, so there is no measured approach path. One
        # node is a path of length one, which the two rural planners read as "no support
        # road" rather than as a route that happens to be short.
        'access_cost': core_distance if math.isfinite(core_distance) else 0.,
        'access_nodes': [node],
        'reason': 'Founded by the player.',
        'name': name or None,
        PLAYER_MARK: PLAYER,
        'founded_age': age,
    }
    if kind == 'hamlet':
        row.update({'role': role, 'irrigation_benefit': 0., 'worked_area_km2': 0.,
                    'delivered_food': 0., 'delivered_materials': 0.})
    else:
        row.update({'defence_score': 0., 'protected_route_node': None})
    return row, core_index


def _site(world, node, x, z, civilization, name, residents, age):
    """The record, built from the layers that already describe this ground.

    Eight of these are exact layer reads -- verified field by field against every site of a
    generated world -- so a player town carries the same numbers a generated one would have
    carried at the same place, rather than plausible invented ones.
    """
    from .terrain_globe import direction
    size = world['config']['size']
    freshwater = _layer(world, 'freshwater_distance', x, z, None)
    urban = round((residents or 0) * .55)
    return {
        'id': len(world['settlements']['sites']),
        'uid': 'surface-city-%d-%d-%s' % (age, node, civilization),
        PLAYER_MARK: PLAYER,
        'node': node, 'x': x, 'z': z, 'direction': direction(x, z, size),
        'kind': 'city', 'layer': 'surface', 'mobility': 'settled', 'outpost': False,
        'population_profile': civilization, 'civilization_id': civilization,
        'parent_race_id': civilization,
        'name': name or 'New Settlement',
        'name_gloss': 'founded by the player',
        'source_culture': '%s-player-%d' % (civilization, node),
        'founded_age': age, 'founding_turn': 0, 'founding_capital': False,
        'founding_year': None, 'migration_source_node': None,
        'source_civilization_id': None, 'migration_distance_m': 0, 'cultural_branch': False,
        'height_m': _layer(world, 'height', x, z, 0.),
        'slope_degrees': _layer(world, 'slope', x, z, 0.),
        'temperature_c': _layer(world, 'temperature', x, z, 0.),
        'moisture': _layer(world, 'moisture', x, z, 0.),
        'flood_risk': _layer(world, 'flood_risk', x, z, 0.),
        'resource_potential': _layer(world, 'resource_potential', x, z, 0.),
        'freshwater_distance_m': freshwater if freshwater is not None and math.isfinite(freshwater) else None,
        'suitability': _layer(world, 'suitability_' + civilization, x, z, 0.),
        'population_estimate': residents or 0,
        'urban_population_estimate': urban,
        'rural_population_estimate': (residents or 0) - urban,
        'reason': 'Founded by the player.',
        'war_history': [],
    }


def found_settlement_request(body):
    """Found a settlement of one of the three kinds and return the transformed world."""
    from .terrain_civilizations import classify_cities
    from .terrain_history import adopt_world

    started = perf_counter()
    world, node, kind, role, civilization, name, layout, rebuild, residents = _validate(body)
    x, z, _points, _profile = _legality(world, node, kind, civilization)

    result = adopt_world(world)
    age = len((result.get('history') or {}).get('ages') or [])

    before_class = {s.get('uid'): s.get('city_class') for s in result['settlements']['sites']}
    before_hamlets = {h.get('id'): h.get('node') for h in (result.get('humans') or {}).get('hamlets', [])}
    before_forts = {f.get('id'): f.get('node') for f in (result.get('humans') or {}).get('fortresses', [])}

    if kind == 'city':
        site = _site(result, node, x, z, civilization, name, residents, age)
        if layout == PLAYER:
            site['city_layout'] = _authored_layout(civilization, residents)
        result['settlements']['sites'].append(site)
        uid = site['uid']
        # Classification is a rank over the whole list, and validate_age_world re-derives
        # it. A caller never sets it; a strong new site can demote an incumbent, and that
        # is reported rather than hidden.
        classify_cities(result['settlements']['sites'])
    else:
        row, core_index = _rural_row(result, node, x, z, kind, role, civilization, name, age)
        result['humans']['hamlets' if kind == 'hamlet' else 'fortresses'].append(row)
        uid = row['uid']
        # The parent city's core row lists what answers to it, and `terrain_wars` counts a
        # city's forts off exactly that list. A row nothing lists is a settlement no block
        # above it knows about.
        for core in result['humans'].get('cores', []):
            if core.get('site_id') == core_index:
                core.setdefault('hamlet_ids' if kind == 'hamlet' else 'fortress_ids', []).append(row['id'])
        site = None

    reclassified = sorted(s['uid'] for s in result['settlements']['sites']
                          if s.get('uid') in before_class
                          and before_class[s['uid']] != s.get('city_class'))

    report = {'version': 2, 'node': node, 'uid': uid, 'kind': kind,
              'city_class': site.get('city_class') if site else None,
              'reclassified_cities': reclassified,
              'layout': layout, 'rebuild': rebuild,
              'nests_rerolled': False,
              'notes': []}
    if kind != 'city':
        report['notes'].append(
            'A %s is keyed on %r, the node-and-kind handle npc_roster mints. Its %r id is '
            'an ordinal that renumbers whenever the rural layer is rebuilt; do not hold it.'
            % (kind, uid, row['id']))
    if reclassified:
        report['notes'].append(
            'Founding this city changed the suitability rank of %d existing city/cities. '
            'city_class is a rank, not a size.' % len(reclassified))

    if rebuild == 'humans':
        from .terrain_humans import add_humans
        from dataclasses import replace as _replace
        from .terrain_lab import Config
        cfg = Config(**result['config'])
        add_humans(result, _replace(cfg, phase=max(cfg.phase, 9)))
        after_hamlets = {h.get('id'): h.get('node') for h in (result.get('humans') or {}).get('hamlets', [])}
        after_forts = {f.get('id'): f.get('node') for f in (result.get('humans') or {}).get('fortresses', [])}
        moved = sorted(k for k in set(before_hamlets) | set(after_hamlets)
                       if before_hamlets.get(k) != after_hamlets.get(k))
        moved_forts = sorted(k for k in set(before_forts) | set(after_forts)
                             if before_forts.get(k) != after_forts.get(k))
        report['rural_ids_reassigned'] = {'hamlets': moved, 'fortresses': moved_forts}
        # Rebuilding humans renumbers hamlet and fortress ordinals, and hamlet_plans and
        # castle_plans key on exactly those ordinals with no uid beside them. Leaving the
        # plan blocks in place would hand a consumer rows naming ground that moved -- a
        # dangling join that resolves to the wrong place rather than to nothing, which is
        # the failure mode this whole API exists to avoid. Absence is representable and
        # honest; a stale row is not.
        dropped = [key for key in ('hamlet_plans', 'castle_plans') if key in result]
        for key in dropped:
            result.pop(key, None)
        report['dropped_blocks'] = dropped
        if moved or moved_forts:
            report['notes'].append(
                'The rural layer was rebuilt, so %d hamlet and %d fortress ordinal ids now '
                'name different ground. Those ids renumber at every age boundary by design; '
                'key on the terrain node instead.' % (len(moved), len(moved_forts)))
        if dropped:
            report['notes'].append(
                'Dropped %s, which key on those ordinals and would otherwise name ground '
                'that moved. Run a phase-16 pass to rebuild them.' % ' and '.join(dropped))
    else:
        report['rural_ids_reassigned'] = {'hamlets': [], 'fortresses': []}
        report['dropped_blocks'] = []
        report['notes'].append(
            'The rural layer was not rebuilt, so this settlement has no hinterland, no '
            'roads and no staffed posts until something rebuilds it. Founding takes a '
            'rebuild argument rather than rebuilding on its own or marking the world '
            'dirty, so the cost is the caller\'s to choose at the call that caused it.')

    report['notes'].append(
        'The beast book was deliberately left alone: the nest pass draws from one sequential '
        'stream keyed on distance to settled ground, so re-running it here would re-roll '
        'nests world-wide. The next age advance will re-roll them regardless.')

    result['settlements']['founded_by_player'] = sorted(
        {s['uid'] for s in result['settlements']['sites'] if s.get(PLAYER_MARK) == PLAYER})
    result['settlement_api_version'] = API_VERSION
    result['settlement_founding'] = report
    # `kind` on an operation row means the operation's kind, which every request function
    # writes; the settlement's kind is a second axis and takes a second name. Two fields
    # spelled alike and meaning different things is how a consumer reads the wrong one.
    result.setdefault('history', {}).setdefault('operations', []).append(
        {'api_version': API_VERSION, 'kind': 'founding', 'settlement_kind': kind,
         'node': node, 'civilization_id': civilization, 'uid': uid, 'layout': layout,
         'rebuild': rebuild, 'name': (site or row).get('name')})
    result['timing_ms']['settlement_founding'] = round((perf_counter() - started) * 1000, 3)
    return result
