"""Raise a band on a world that already exists. Stateless JSON API v1.

Same input, same output; the caller's world is unchanged; persist the returned world to
call again. This is the seam that lets a villain put cultists on the map without either
feature importing the other: the villain pass calls in with its own uid as the origin, and
gets back a world with a band in it. Nothing here knows what a villain is beyond an id.

Deliberately **not** copying `visitation.MAX_VISITATIONS`. A summoning cap is right for a
god walking the mortal plane and wrong for a spawner: bands are raised across ages as a
matter of course, and a cap would silently stop working partway through a long history.

The band is classified by the ground it is placed on, exactly as a world-generated one is.
A caller can ask for a classification, but it only gets one whose gate the ground actually
passes -- so a request for cultists on ground with nothing sacred is refused rather than
quietly honoured. The land decides who walks it; that does not stop being true because
something else asked.
"""
import copy
from time import perf_counter
from .terrain_lab import Config
from .terrain_nomads import CLASSIFICATIONS, GATES, ORIGIN_CAMP_KIND, ground, policy, seasonal_swing
from .terrain_nomad_routes import add_nomad_routes
from .terrain_encounters import add_encounters
from .terrain_nomad_effects import apply_nomad_effects

API_VERSION = 1
FIELDS = {'api_version', 'world', 'node', 'origin', 'classification', 'variation'}


def validate_nomad_request(body):
    if not isinstance(body, dict) or set(body) - FIELDS:
        raise ValueError('Expected api_version, world, node, origin, optional classification and variation')
    if type(body.get('api_version')) is not int or body['api_version'] != API_VERSION:
        raise ValueError('Unsupported nomad API version')
    world = body.get('world')
    if not isinstance(world, dict) or 'nomads' not in world:
        raise ValueError('World must already carry a nomads block')
    node = body.get('node')
    if type(node) is not int or node < 0:
        raise ValueError('node must be a non-negative grid index')
    origin = body.get('origin')
    if not isinstance(origin, dict) or set(origin) - {'kind', 'id', 'age'}:
        raise ValueError('origin takes kind, id and age')
    if origin.get('kind') not in ('world', 'god', 'villain'):
        raise ValueError('origin kind must be world, god or villain')
    if type(origin.get('age')) is not int or origin['age'] < 0:
        raise ValueError('origin age must be a non-negative integer')
    wanted = body.get('classification')
    if wanted is not None and wanted not in CLASSIFICATIONS:
        raise ValueError('Unknown classification')
    variation = body.get('variation', 0)
    if type(variation) is not int or not 0 <= variation <= 4294967295:
        raise ValueError('variation must be a uint32')
    return Config(**world['config']), node, origin, wanted, variation


def nomad_request(body):
    """Raise one band at a node and return the transformed world."""
    import random
    from .terrain_tectonics import child_seed
    from .terrain_erosion import sphere_grid
    from .terrain_nests import habitat_cells
    cfg, node, origin, wanted, variation = validate_nomad_request(body)
    world = body['world']
    started = perf_counter()
    result = copy.deepcopy({k: v for k, v in world.items() if k != 'build_stages'})
    if 'build_stages' in world:
        result['build_stages'] = list(world['build_stages'])
    result.setdefault('timing_ms', {'total': 0.})
    result['timing_ms'].setdefault('total', 0.)

    radius = result['effective_config']['globe_radius']
    points, areas, _ = sphere_grid(cfg.size, radius)
    if node >= len(points):
        raise ValueError('node is outside this world')
    cells = habitat_cells(result, cfg, points, areas)
    cell = cells[node]
    if cell['fields'].get('medium') != 'land':
        raise ValueError('A band cannot be raised on water')
    cell['swing'] = seasonal_swing(result, cell['x'], cell['z'])
    g = ground(result, cfg, radius, points)
    pol = policy()

    shares, evidence = [], {}
    for name in CLASSIFICATIONS:
        verdict = GATES[name](cell, g, pol['classifications'][name]['gate'], result)
        if verdict is None:
            continue
        score, why = verdict
        shares.append((name, score * pol['classifications'][name]['weight']))
        evidence[name] = why
    if not shares:
        raise ValueError('This ground raises nobody: no classification gate holds at that node')
    if wanted is not None:
        if wanted not in evidence:
            raise ValueError('The ground at that node does not support %s' % wanted)
        chosen = wanted
    else:
        total = 0.
        for _, share in shares:
            total += share
        rng = random.Random(child_seed(cfg.seed, 'nomad-request-%d' % node, variation))
        draw = rng.random() * total
        cursor = 0.
        chosen = shares[-1][0]
        for name, share in shares:
            cursor += share
            if draw <= cursor:
                chosen = name
                break

    rule = pol['classifications'][chosen]
    rng = random.Random(child_seed(cfg.seed, 'nomad-request-size-%d' % node, variation))
    low, high = rule['size']
    size = rng.randint(low, high)
    uid = 'nomad-%d-%d' % (origin['age'], node)
    existing = {b['uid'] for b in result['nomads']['groups']}
    suffix = 0
    while uid in existing:
        suffix += 1
        uid = 'nomad-%d-%d-%d' % (origin['age'], node, suffix)

    band = {
        'uid': uid, 'classification': chosen, 'parent_uid': None,
        'origin': {'kind': origin['kind'], 'id': origin.get('id'), 'age': origin['age']},
        'god_id': evidence[chosen].get('god_id'), 'school': evidence[chosen].get('school'),
        'node': node, 'x': cell['x'], 'z': cell['z'],
        'direction': list(cell['direction']), 'biome': cell['biome'],
        'size': size, 'speed_m_per_day': float(rule['speed_m_per_day']),
        'column_length_m': round(size * rule['column_length_per_head_m'], 6),
        'disposition': rule['disposition'], 'seeks': list(rule['seeks']),
        'carries': list(rule['carries']),
        'camps': [{'id': uid + '-camp-0', 'node': node, 'direction': list(cell['direction']),
                   'kind': ORIGIN_CAMP_KIND[chosen], 'arrive_day': None, 'depart_day': None}],
        'legs': [], 'basis': evidence[chosen], 'route_status': 'stranded',
    }
    result['nomads']['groups'].append(band)
    result['nomads']['groups'].sort(key=lambda b: b['uid'])
    result['nomads']['counts'][chosen] = result['nomads']['counts'].get(chosen, 0) + 1

    # Routes, the encounter index and the write-backs are all functions of the band set, so
    # they are rebuilt rather than patched. Cheap: the route pass is single-digit
    # milliseconds and rebuilding is the only way the index cannot drift from the bands.
    add_nomad_routes(result, cfg)
    add_encounters(result, cfg)
    apply_nomad_effects(result, cfg)

    operations = result.setdefault('history', {}).setdefault('operations', [])
    operations.append({
        'kind': 'nomad_request', 'api_version': API_VERSION, 'uid': uid,
        'classification': chosen, 'node': node, 'origin': band['origin'],
        'requested_classification': wanted, 'variation': variation,
    })
    elapsed = (perf_counter() - started) * 1000
    result['timing_ms']['nomad_request'] = elapsed
    result['timing_ms']['total'] += elapsed
    return result
