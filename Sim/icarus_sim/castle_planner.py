"""Deterministic final-world castle layouts from fortress pins, independent of city_plans."""
import hashlib
import json
import math
import random
from functools import lru_cache
from pathlib import Path

from .castle_geometry import (
    VERSION as GEOMETRY_VERSION, ellipse_ring, clip_ring_to_valid, build_wall_network,
)
from .terrain_detail import HeightField
from .civilization_registry import section

VERSION = 3
CELL = 4
CASTLES_PATH = Path(__file__).with_name('castles.json')
PHASE_ORDER = ['map', 'kit', 'perimeter', 'courts', 'landmarks', 'services']


@lru_cache(maxsize=1)
def load_castles():
    data = json.loads(CASTLES_PATH.read_text())
    if data.get('schema') != 'fantasy-world-generator.castle-registry' or data.get('schema_version') != 1:
        raise ValueError('Unsupported castle registry schema')
    if type(data.get('revision')) is not int or data['revision'] < 1:
        raise ValueError('Invalid castle registry revision')
    return data


def castle_structures():
    library = section('structure_blocks')['castle']
    return {s['id']: s for block in library['blocks'] for s in block['structures']}


def planner_identity():
    doc = load_castles()
    structures = castle_structures()
    castles_hash = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    buildings_hash = hashlib.sha256(
        json.dumps(structures, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'version': VERSION, 'geometry_version': GEOMETRY_VERSION,
            'castles_sha256': castles_hash, 'castle_buildings_sha256': buildings_hash}


def _sampler(world, site, half):
    """Local east/north metre sampler; duplicated to avoid importing city_planner."""
    field = HeightField(world)
    n = world['config']['size']
    radius = world.get('effective_config', world['config'])['globe_radius']
    lat = math.pi / 2 - math.pi * site['z'] / (n - 1)
    lon = -math.pi + 2 * math.pi * site['x'] / (n - 1)
    up = (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))
    east = (-math.sin(lon), 0, math.cos(lon))
    north = (-math.sin(lat) * math.cos(lon), math.cos(lat), -math.sin(lat) * math.sin(lon))

    def local(node):
        x, z = node
        la = math.pi / 2 - math.pi * z / (n - 1)
        lo = -math.pi + 2 * math.pi * x / (n - 1)
        p = (math.cos(la) * math.cos(lo), math.sin(la), math.cos(la) * math.sin(lo))
        den = sum(a * b for a, b in zip(p, up))
        if den <= .1:
            return None
        return (radius * sum(a * b for a, b in zip(p, east)) / den,
                radius * sum(a * b for a, b in zip(p, north)) / den)

    nodes = world.get('water', {}).get('nodes', [])
    lines = []
    for i, j in world.get('climate', world.get('water', {})).get('river_segments', []):
        a = local(nodes[i])
        b = local(nodes[j])
        if a and b and all(min(a[k], b[k]) <= half + 40 and max(a[k], b[k]) >= -half - 40 for k in (0, 1)):
            lines.append((a, b))

    def river_distance(x, z):
        best = 1e30
        for a, b in lines:
            dx = b[0] - a[0]
            dz = b[1] - a[1]
            t = max(0, min(1, ((x - a[0]) * dx + (z - a[1]) * dz) / (dx * dx + dz * dz or 1)))
            best = min(best, math.hypot(x - a[0] - t * dx, z - a[1] - t * dz))
        return best

    def direction_at(x, z):
        p = [up[i] + (east[i] * x + north[i] * z) / radius for i in range(3)]
        length = math.sqrt(sum(v * v for v in p))
        return [v / length for v in p]

    def sample(x, z, with_slope=True):
        p = [up[i] + (east[i] * x + north[i] * z) / radius for i in range(3)]
        length = math.sqrt(sum(v * v for v in p))
        p = [v / length for v in p]
        gx = round((math.atan2(p[2], p[0]) + math.pi) / (2 * math.pi) * (n - 1)) % (n - 1)
        gz = max(0, min(n - 1, round((math.pi / 2 - math.asin(p[1])) / math.pi * (n - 1))))

        def get(key, default=0):
            layer = world['layers'].get(key)
            return default if layer is None else layer[gz][gx]

        distance = river_distance(x, z)
        slope = get('slope')
        if field.definition and with_slope:
            dx = (field.height(direction_at(x + 1, z)) - field.height(direction_at(x - 1, z))) / 2
            dz = (field.height(direction_at(x, z + 1)) - field.height(direction_at(x, z - 1))) / 2
            slope = math.degrees(math.atan(math.hypot(dx, dz)))
        # `channel` is the local reserved river channel and setback; `flood_risk` is the
        # coarse regional proxy, constant across a footprint and therefore unable to say
        # anything about one cell within it. Mirrors city_planner.
        return {'water': get('water_type') != 0 or distance < 12, 'slope': slope,
                'channel': int(distance < 28) if lines and get('river') > .5 else 0,
                'flood_risk': get('flood_risk'),
                'height': field.height(p), 'moisture': get('moisture', .5),
                'biome': get('natural_biome', 3), 'variant': get('biome_variant', -1)}

    return sample


def support_approach(world, fortress, half):
    """Project the fortress access path and take the window-boundary crossing as approach."""
    from .world_scene import frame, local_direction
    from .terrain_globe import direction
    nodes = world.get('water', {}).get('nodes', [])
    path = list(fortress.get('access_nodes') or [])
    if len(path) < 2 or not nodes:
        return None, []
    f = frame(world, fortress)
    r, up, east, north = f
    prev = (0., 0.)
    entries = []
    approach = None
    for index in path[1:]:
        if index < 0 or index >= len(nodes):
            break
        x, z = nodes[index]
        p = direction(x, z, world['config']['size'])
        den = sum(a * b for a, b in zip(p, up))
        if den <= 0:
            break
        q = (r * sum(a * b for a, b in zip(p, east)) / den,
             r * sum(a * b for a, b in zip(p, north)) / den)
        if max(abs(v) for v in q) > half:
            ts = [((half if q[j] > 0 else -half) - prev[j]) / (q[j] - prev[j])
                  for j in (0, 1) if abs(q[j]) > half]
            t = min(ts)
            approach = [prev[j] + t * (q[j] - prev[j]) for j in (0, 1)]
            entries.append({
                'route_id': f"support:{fortress['id']}", 'route_index': -1, 'end': 'to',
                'outside_index': 0, 'junction_id': f"junction:{fortress['id']}:support",
                'gate_local_m': list(approach), 'direction': local_direction(f, *approach),
                'status': 'unreachable',
                'reason': 'No terrain-safe street connection to parent-city approach',
            })
            break
        prev = q
    return approach, entries


def select_kit(seed, fortress_id, kits):
    rng = random.Random(hashlib.sha256(f'{seed}:castle-kit:{fortress_id}'.encode()).hexdigest())
    weights = [max(1, int(k.get('weight', 1))) for k in kits]
    return rng.choices(kits, weights=weights, k=1)[0]


def _ground(sample, x, z, w, d, degrees):
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    corners = []
    for u, v in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        corners.append(sample(x + u * c - v * s, z + u * s + v * c)['height'])
    return corners


def plan_castle(world, fortress):
    doc = load_castles()
    structures = castle_structures()
    modules = doc['modules']
    rules = doc['join_rules']
    kit = select_kit(world['config']['seed'], fortress['id'], doc['kits'])
    n = world['config']['size']
    radius = world.get('effective_config', world['config'])['globe_radius']
    half = kit['half_m']
    # Bound by parent city and neighbouring fortresses without moving anchors.
    sites = list(world['settlements']['sites'])
    for other in world.get('humans', {}).get('fortresses', []):
        if other is fortress or other.get('id') == fortress.get('id'):
            continue
        sites.append(other)
    for other in sites:
        lat1 = math.pi / 2 - math.pi * fortress['z'] / (n - 1)
        lat2 = math.pi / 2 - math.pi * other['z'] / (n - 1)
        dl = 2 * math.pi * (other['x'] - fortress['x']) / (n - 1)
        distance = radius * math.acos(max(-1, min(1, math.sin(lat1) * math.sin(lat2)
                                                  + math.cos(lat1) * math.cos(lat2) * math.cos(dl))))
        half = min(half, distance * .28)
    half = max(CELL, int(half / CELL) * CELL)
    size = 2 * half // CELL
    sample = _sampler(world, fortress, half)
    terrain = []
    biomes = []
    mutations = []
    valid = set()
    heights = {}
    slopes = {}
    for j in range(size):
        row = []
        biome_row = []
        mutation_row = []
        for i in range(size):
            v = sample(-half + (i + .5) * CELL, -half + (j + .5) * CELL)
            heights[(i, j)] = v['height']
            slopes[(i, j)] = v['slope']
            # See city_planner: the regional flood proxy cannot block a cell it cannot
            # resolve. 34 of 56 castles were unbuildable on this rule.
            code = 1 if v['water'] else 2 if v['slope'] > 25 or v['channel'] else 0
            row.append(code)
            biome_row.append(v['biome'])
            mutation_row.append(v['variant'])
            if code == 0:
                valid.add((i, j))
        terrain.append(row)
        biomes.append(biome_row)
        mutations.append(mutation_row)
    surface_size = size + 1
    surface = {
        'size': surface_size,
        'step_m': 2 * half / (surface_size - 1),
        'heights_m': [[round(sample(-half + i * 2 * half / (surface_size - 1),
                                    -half + j * 2 * half / (surface_size - 1), False)['height'], 4)
                       for i in range(surface_size)] for j in range(surface_size)],
    }
    result = {
        'version': VERSION, 'kind': 'castle', 'fortress_id': fortress['id'],
        'core_id': fortress.get('core_id'), 'x': fortress['x'], 'z': fortress['z'],
        'kit_id': kit['id'], 'kit_name': kit['name'],
        'bounds_m': [-half, -half, half, half],
        'passes': [{'id': p, 'placed': 0} for p in PHASE_ORDER],
        'plots': [], 'roads': [], 'wall_networks': [], 'unplaced': [], 'road_connections': [],
        'warnings': [
            'Schematic fortification modules; structural engineering and garrison beds are not resolved.',
            'Curtain segments are metre-scale wall runs; production ARCH meshes remain unassigned.',
        ],
        'stats': {}, 'debug': {}, 'status': 'unbuildable',
        'source_resolution_m': round(math.pi * radius / (n - 1), 4),
        'terrain': {
            'cell_m': CELL, 'size': size, 'codes': terrain, 'surface': surface,
            'natural_biome': biomes, 'biome_variant': mutations,
            'biome_catalogue': world.get('terrain', {}).get('biomes', []),
            'magical_catalogue': world.get('terrain', {}).get('magical_biomes', []),
            'magic_colors': {k: v['color'] for k, v in world.get('magic', {}).get('networks', {}).items()},
        },
    }
    result['passes'][0]['placed'] = 1
    if len(valid) < 24:
        result['unplaced'].append({'building_id': 'building.curtain_segment', 'count': 1,
                                   'reason': 'Insufficient buildable land for a fortress precinct'})
        return result
    result['passes'][1]['placed'] = 1
    approach, entries = support_approach(world, fortress, half)
    result['road_connections'] = entries
    rx = half * 0.72
    rz = half * 0.62
    networks = []
    for ring_i, ring_spec in enumerate(kit['rings']):
        scale = ring_spec['scale']
        ring_id = f"ring-{ring_spec['role']}"
        raw = ellipse_ring(rx * scale, rz * scale, 32)
        polyline = clip_ring_to_valid(raw, valid, half, CELL, 25,
                                      lambda i, j: heights[(i, j)],
                                      lambda i, j: slopes[(i, j)])
        if len(polyline) < 8:
            # Fall back to unclipped ellipse when terrain clipping collapses the ring.
            polyline = raw
        network = build_wall_network(
            ring_id=ring_id, role=ring_spec['role'], polyline=polyline,
            approach_m=approach if ring_i == 0 else None,
            ring_spec=ring_spec, modules=modules, rules=rules,
            ditch=ring_spec.get('ditch'))
        networks.append(network)
        if network['status'] != 'closed':
            result['unplaced'].extend(
                {'building_id': u.get('building_id', 'building.curtain_segment'),
                 'count': u.get('count', 1), 'reason': u.get('reason', 'Wall network failure')}
                for u in network.get('unplaced', []))
    result['wall_networks'] = networks
    result['passes'][2]['placed'] = sum(1 for n in networks if n['status'] == 'closed')
    if not any(n['status'] == 'closed' for n in networks):
        result['status'] = 'partial'
        result['stats'] = {'wall_rings_closed': 0, 'segments': 0, 'plots': 0, 'workers': 0}
        return result

    def install(structure_id, x, z, degrees, phase, kind='service'):
        row = structures[structure_id]
        ground = _ground(sample, x, z, row['plot_m']['width'], row['plot_m']['depth'], degrees)
        plot = {
            'id': f"plot-{len(result['plots'])}", 'building_id': structure_id, 'name': row['name'],
            'kind': kind, 'phase': phase, 'x_m': round(x, 2), 'z_m': round(z, 2),
            'rotation_degrees': round(degrees, 4),
            'ground_elevation_m': round(max(ground), 4),
            'foundation_bottom_m': round(min(ground), 4),
            'plot_m': row['plot_m'], 'dimensions_m': row['dimensions_m'],
            'road_access': [round(x, 2), round(z, 2)],
            # No `beds`. No structure in the castle registry carries a bed count, so a
            # number here would be invented rather than measured. The field used to be a
            # literal 0 on every plot beside 35-53 placed `workers`, which reads as a
            # garrison sleeping nowhere and divides into a runtime error for anything
            # computing occupancy. Absence is representable; a zero that was never
            # measured is not. See castle_plans['beds'] in fill_castles.
            'workers': sum(r['target'] for r in row.get('staffing', {}).get('roles', [])),
        }
        result['plots'].append(plot)
        result['passes'][next(i for i, p in enumerate(result['passes']) if p['id'] == phase)]['placed'] += 1
        return plot

    ring_polylines = {n['role']: n['polyline_m'] for n in networks if n['status'] == 'closed'}
    for court in kit.get('courts', []):
        ring = ring_polylines.get(court['ring_role'])
        if not ring:
            result['unplaced'].append({'building_id': court['structure_id'], 'count': 1,
                                       'reason': f"No closed ring {court['ring_role']} for court"})
            continue
        cx = sum(p[0] for p in ring) / len(ring)
        cz = sum(p[1] for p in ring) / len(ring)
        install(court['structure_id'], cx, cz, 0, 'courts', kind='court')

    for landmark in kit.get('landmarks', []):
        ring = ring_polylines.get(landmark['ring_role'])
        if not ring:
            result['unplaced'].append({'building_id': landmark['structure_id'], 'count': 1,
                                       'reason': f"No closed ring {landmark['ring_role']} for keep"})
            continue
        cx = sum(p[0] for p in ring) / len(ring)
        cz = sum(p[1] for p in ring) / len(ring)
        install(landmark['structure_id'], cx, cz, 0, 'landmarks', kind='landmark')

    # Place services around the primary bailey centre, offset from the keep.
    primary = networks[0]
    if primary['status'] == 'closed':
        poly = primary['polyline_m']
        cx = sum(p[0] for p in poly) / len(poly)
        cz = sum(p[1] for p in poly) / len(poly)
        angle0 = 0.0
        if approach:
            angle0 = math.atan2(approach[1] - cz, approach[0] - cx)
        service_i = 0
        for service in kit.get('services', []):
            sid = service['structure_id']
            if sid not in structures:
                result['unplaced'].append({'building_id': sid, 'count': 1, 'reason': 'Unknown castle structure'})
                continue
            if sid == 'building.drawbridge':
                if not primary.get('ditch') or not primary.get('gates'):
                    result['unplaced'].append({'building_id': sid, 'count': 1,
                                               'reason': 'Drawbridge requires outer ditch and gate'})
                    continue
                gate = primary['gates'][0]
                gx, gz = gate['position_m']
                install(sid, gx + math.cos(angle0) * 10, gz + math.sin(angle0) * 10,
                        math.degrees(angle0), 'services')
                continue
            if sid == 'building.barbican' and any(g['structure_id'] == 'building.barbican' for g in primary.get('gates', [])):
                # Already represented as the gate node.
                continue
            for _ in range(service.get('count', 1)):
                ang = angle0 + math.pi * 0.5 + service_i * (math.pi * 0.35)
                dist = half * 0.22
                install(sid, cx + math.cos(ang) * dist, cz + math.sin(ang) * dist,
                        math.degrees(ang + math.pi / 2), 'services')
                service_i += 1

    # Emit gate/tower/stair plots for consumers that only read plots[].
    for network in networks:
        if network['status'] != 'closed':
            continue
        for gate in network.get('gates', []):
            if any(p['building_id'] == gate['structure_id']
                   and math.dist((p['x_m'], p['z_m']), gate['position_m']) < 1 for p in result['plots']):
                continue
            install(gate['structure_id'], gate['position_m'][0], gate['position_m'][1],
                    0, 'perimeter', kind='gate')
        for tower in network.get('towers', []):
            install(tower['structure_id'], tower['position_m'][0], tower['position_m'][1],
                    0, 'perimeter', kind='tower')
        for stair in network.get('stairs', []):
            install(stair['structure_id'], stair['position_m'][0], stair['position_m'][1],
                    0, 'perimeter', kind='stair')

    workers = sum(p['workers'] for p in result['plots'])
    closed = sum(1 for n in networks if n['status'] == 'closed')
    segments = sum(len(n.get('segments', [])) for n in networks)
    result['stats'] = {
        'wall_rings_closed': closed, 'segments': segments, 'plots': len(result['plots']),
        'workers': workers, 'kit_id': kit['id'],
        'walkway_continuous': all(n.get('walkway_continuous') for n in networks if n['status'] == 'closed'),
        'unplaced_total': len(result['unplaced']),
    }
    result['status'] = 'complete' if closed == len(kit['rings']) and not result['unplaced'] else 'partial'
    result['debug'] = {'valid_cells': len(valid), 'approach_m': approach, 'geometry_version': GEOMETRY_VERSION}
    return result


def fill_castles(world):
    castles = []
    for fortress in sorted(world.get('humans', {}).get('fortresses', []), key=lambda f: str(f['id'])):
        castles.append(plan_castle(world, fortress))
    world['castle_plans'] = {
        'version': VERSION, 'identity': planner_identity(), 'castles': castles,
        'phase_order': list(PHASE_ORDER),
        'limits': 'Schematic fortification modules and bailey plots; not structural engineering or production art.',
        'beds': 'A castle plan declares no sleeping capacity. No structure in the castle '
                'registry carries a bed count, so castle plots carry no beds key at all '
                'rather than a zero that was never measured. The garrison a plan staffs is '
                'stats.workers, which npc_roster opens one post per.',
    }
    from .world_scene import build_scene
    build_scene(world)
    return world['castle_plans']
