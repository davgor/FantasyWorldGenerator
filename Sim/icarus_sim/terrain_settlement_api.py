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
"""

import copy
import math
from time import perf_counter

from .terrain_errors import (cross_field, invalid_choice, missing_block, out_of_range,
                             refused_by_world, unknown_field, unsupported_api, wrong_type)

API_VERSION = 1

FIELDS = {'api_version', 'world', 'node', 'civilization_id', 'name', 'layout',
          'population_estimate', 'rebuild'}

REBUILD_CHOICES = ('humans', 'none')

# Written onto a player site so the founding pass can tell it from one it placed itself.
# `terrain_settlements` carries this key, and `city_layout`, across an age boundary for a
# site that has it -- which is the only reason a player-authored layout survives.
PLAYER_MARK = 'founded_by'
PLAYER = 'player'


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
    return world, node, civilization, name, layout, rebuild, residents


def _legality(world, node, civilization):
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

    for site in world['settlements']['sites']:
        if site.get('node') == node:
            raise refused_by_world('node', node, 'Node %d already holds %s.'
                                   % (node, site.get('name') or site.get('uid') or 'a city'))
    for ruin in world.get('ruins', []) or []:
        if isinstance(ruin, dict) and ruin.get('node') == node:
            raise refused_by_world('node', node, 'Node %d is a ruin, and an active city may '
                                   'not stand on one.' % node)

    spacing = world['effective_config'].get('settlement_spacing', config.get('settlement_spacing'))
    if spacing:
        here = direction(x, z, size)
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
    return x, z, points, profile


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
    """Found a city at a node and return the transformed world."""
    from .terrain_civilizations import classify_cities
    from .terrain_history import adopt_world

    started = perf_counter()
    world, node, civilization, name, layout, rebuild, residents = _validate(body)
    x, z, _points, _profile = _legality(world, node, civilization)

    result = adopt_world(world)
    age = len((result.get('history') or {}).get('ages') or [])

    before_class = {s.get('uid'): s.get('city_class') for s in result['settlements']['sites']}
    before_hamlets = {h.get('id'): h.get('node') for h in (result.get('humans') or {}).get('hamlets', [])}
    before_forts = {f.get('id'): f.get('node') for f in (result.get('humans') or {}).get('fortresses', [])}

    site = _site(result, node, x, z, civilization, name, residents, age)
    result['settlements']['sites'].append(site)

    # Classification is a rank over the whole list, and validate_age_world re-derives it.
    # A caller never sets it; a strong new site can demote an incumbent, and that is
    # reported rather than hidden.
    classify_cities(result['settlements']['sites'])
    reclassified = sorted(s['uid'] for s in result['settlements']['sites']
                          if s.get('uid') in before_class
                          and before_class[s['uid']] != s.get('city_class'))

    report = {'version': 1, 'node': node, 'uid': site['uid'],
              'city_class': site.get('city_class'),
              'reclassified_cities': reclassified,
              'layout': layout, 'rebuild': rebuild,
              'nests_rerolled': False,
              'notes': []}
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
            'The rural layer was not rebuilt, so this city has no hinterland, no roads and '
            'no staffed posts until something rebuilds it.')

    report['notes'].append(
        'The beast book was deliberately left alone: the nest pass draws from one sequential '
        'stream keyed on distance to settled ground, so re-running it here would re-roll '
        'nests world-wide. The next age advance will re-roll them regardless.')

    result['settlements']['founded_by_player'] = sorted(
        {s['uid'] for s in result['settlements']['sites'] if s.get(PLAYER_MARK) == PLAYER})
    result['settlement_api_version'] = API_VERSION
    result['settlement_founding'] = report
    result.setdefault('history', {}).setdefault('operations', []).append(
        {'api_version': API_VERSION, 'kind': 'founding', 'node': node,
         'civilization_id': civilization, 'uid': site['uid'], 'layout': layout,
         'rebuild': rebuild, 'name': site['name']})
    result['timing_ms']['settlement_founding'] = round((perf_counter() - started) * 1000, 3)
    return result
