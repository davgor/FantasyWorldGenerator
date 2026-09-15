"""Recipe 2 magic: independent editable networks and deterministic local competition."""
import copy
import math
import random
from dataclasses import replace
from .terrain_tectonics import child_seed
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_climate import node_grid
from .terrain_magic import add_magic, arc_frame, distance_to_frame

SCHOOLS = {
    'weave': ('Raw magic', 'chaos, creation, creativity', [166, 104, 214]),
    'umbral': ('Raw magic', 'necrotic, entropy, death, order', [72, 49, 35]),
    'infernal': ('Holy / unholy', 'demons, hellscapes, corruption, evil', [154, 43, 49]),
    'radiant': ('Holy / unholy', 'holy, healing, order, peace, righteousness', [225, 209, 133]),
    'fire': ('Primordial', 'fire, heat, renewal, chaos', [207, 86, 37]),
    'water': ('Primordial', 'water, ice, currents, order', [65, 156, 202]),
    'earth': ('Primordial', 'nature, ground, stone, roots, order', [67, 120, 51]),
    'air': ('Primordial', 'wind, storms, chaos, force', [176, 210, 213]),
}


def generate_networks(result, cfg):
    from .terrain_world import options
    o = options(cfg)
    networks = {}
    for name, (group, descriptors, color) in SCHOOLS.items():
        seed = child_seed(cfg.seed, 'history-ley-' + name, o[name + '_variation'])
        temporary = {'climate': True, 'layers': {}, 'effective_config': result['effective_config'],
                     'warnings': [], 'timing_ms': {'total': 0}}
        enabled = cfg.magic_enabled and random.Random(seed).random() < o[name + '_occurrence']
        nodes, edges = [], []
        if enabled:
            add_magic(temporary, replace(cfg, phase=6, seed=seed, ley_nodes=o[name + '_nodes'],
                                        ley_width=o[name + '_width']))
            rng = random.Random(child_seed(seed, 'intensities'))
            nodes = [{'id': f'{name}-node-{i}', 'direction': list(p), 'intensity': rng.uniform(.35, 1.65)}
                     for i, p in enumerate(temporary['magic']['nodes'])]
            edges = [{**e, 'id': f'{name}-line-{i}', 'intensity': rng.uniform(.35, 1.65)}
                     for i, e in enumerate(temporary['magic']['edges'])]
        networks[name] = {'name': name, 'group': group, 'descriptors': descriptors, 'color': color,
                          'seed': seed, 'strength': o[name + '_strength'], 'width_m': o[name + '_width'],
                          'instability': o[name + '_instability'], 'nodes': nodes, 'edges': edges}
    result['magic'] = {'version': 3, 'school_order': list(SCHOOLS), 'groups': list(dict.fromkeys(v[0] for v in SCHOOLS.values())),
                       'networks': networks, 'colleges': [], 'enabled': bool(cfg.magic_enabled),
                       'mutation_threshold': .35, 'dominance_margin': .08,
                       'method': 'Eight independently seeded networks. Node and line intensities are editable; '
                                 'overlapping raw potency is preserved. Mutation requires potency >= 0.35 '
                                 'and an absolute lead >= 0.08 over the next strongest school.'}
    evaluate_networks(result, cfg)


def edit_network(network, *, node_id=None, line_id=None, intensity=None, new_node=None):
    """Validated copy-on-write edit; callers reevaluate fields without rerolling geometry.

    A new key point is a local source until a future caller supplies connecting lines.
    """
    net = copy.deepcopy(network)
    if sum(v is not None for v in (node_id, line_id, new_node)) != 1:
        raise ValueError('Select one node, line, or new key point')
    if new_node is not None:
        if not isinstance(new_node, dict) or set(new_node) != {'id', 'direction', 'intensity'}:
            raise ValueError('New node requires id, direction, intensity')
        p = new_node['direction']
        if not isinstance(new_node['id'], str) or not new_node['id'] or any(n['id'] == new_node['id'] for n in net['nodes']):
            raise ValueError('Node id must be unique and nonempty')
        if not isinstance(p, (list, tuple)) or len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p):
            raise ValueError('Direction must be a finite unit vector')
        if abs(sum(v*v for v in p)-1) > 1e-6:
            raise ValueError('Direction must be a unit vector')
        intensity = new_node['intensity']
        target = copy.deepcopy(new_node)
        net['nodes'].append(target)
    else:
        collection = net['nodes'] if node_id is not None else net['edges']
        target = next((v for v in collection if v['id'] == (node_id if node_id is not None else line_id)), None)
        if target is None:
            raise ValueError('Unknown key point or line')
    if type(intensity) not in (int, float) or not math.isfinite(intensity) or not 0 <= intensity <= 4:
        raise ValueError('Intensity must be finite and between 0 and 4')
    target['intensity'] = intensity
    return net


def dominant_school(potencies, threshold=.35, margin=.08):
    ranked = sorted(potencies, key=lambda n: (-potencies[n], n))
    if not ranked:
        return None
    winner = ranked[0]
    runner = potencies[ranked[1]] if len(ranked) > 1 else 0
    return winner if potencies[winner] >= threshold and potencies[winner] - runner >= margin else None


def evaluate_networks(result, cfg):
    """Rebuild only magic-derived fields, preserving the independent network inputs."""
    l = result['layers']; magic = result['magic']; n = cfg.size
    radius = result['effective_config']['globe_radius']
    points, _, _ = sphere_grid(n, radius)
    vectors = [direction(x, z, n) for x, z in points]
    for name, net in magic['networks'].items():
        frames = [arc_frame(net['nodes'][e['from']]['direction'], net['nodes'][e['to']]['direction']) for e in net['edges']]
        power = []
        for p in vectors:
            total = sum(node['intensity'] * math.exp(-(radius * math.acos(max(-1., min(1., sum(a*b for a,b in zip(p,node['direction']))))) / net['width_m'])**2)
                        for node in net['nodes'])
            total += sum(e['intensity'] * (net['nodes'][e['from']]['intensity'] + net['nodes'][e['to']]['intensity']) / 2 *
                         math.exp(-(radius * distance_to_frame(p, frame) / net['width_m'])**2)
                         for e, frame in zip(net['edges'], frames))
            power.append(net['strength'] * -math.expm1(-total))
        l['ley_' + name] = node_grid(power, points, n)
        l['instability_' + name] = node_grid([min(1., v*net['instability']) for v in power], points, n)
    density, hazard, growth, opposition, winners = [], [], [], [], []
    for x,z in points:
        p = {name: l['ley_' + name][z][x] for name in SCHOOLS}
        total = sum(p.values())
        conflict = min(p['radiant'], p['infernal']) + min(p['weave'], p['umbral']) + min(p['fire'], p['water'])
        density.append(-math.expm1(-total))
        opposition.append(min(1., conflict))
        hazard.append(min(1., sum(l['instability_'+name][z][x] for name in SCHOOLS)*.3 + conflict*.2))
        growth.append((p['earth'] + .6*p['radiant'] + .5*p['weave'] + .4*p['water']) / max(total, 1e-12))
        winner = dominant_school(p)
        winners.append(list(SCHOOLS).index(winner) if winner else -1)
    for key, vals in [('magic_density', density), ('magic_hazard', hazard), ('magic_growth', growth),
                      ('magic_opposition', opposition), ('dominant_magic', winners)]:
        l[key] = node_grid(vals, points, n)
    # Compatibility projections for existing ecological/nest requirements, never extra networks.
    l['ley_holy'] = l['ley_radiant']
    l['ley_primordial'] = node_grid([max(l['ley_'+s][z][x] for s in ('fire','water','earth','air')) for x,z in points], points, n)
    for people in ('human','dwarf','elf','gnome','tidekin'):
        l['magic_risk_'+people] = node_grid(hazard, points, n)
    magic['nodes'], magic['edges'] = [], []
    for name, net in magic['networks'].items():
        offset = len(magic['nodes'])
        magic['nodes'].extend(node['direction'] for node in net['nodes'])
        magic['edges'].extend({**e, 'from': e['from']+offset, 'to': e['to']+offset, 'network': name,
                               'strength': e['intensity']} for e in net['edges'])
    magic['compatibility_fields'] = {'ley_holy': 'radiant', 'ley_primordial': 'maximum of fire, water, earth, air'}
