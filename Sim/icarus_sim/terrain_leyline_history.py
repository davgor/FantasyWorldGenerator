"""Recipe 2 magic: independent editable networks and deterministic local competition."""
import copy
import heapq
import math
import random
from dataclasses import replace
from .terrain_tectonics import child_seed
from .terrain_erosion import sphere_grid
from .terrain_globe import direction
from .terrain_climate import node_grid
from .terrain_magic import add_magic, arc_frame, distance_to_frame

# Physical radius of the reference world: design radius 10000 at the recipe world_scale.
REFERENCE_RADIUS_M = 1774.4123532462844

# The world's own taxonomy. Everything this world can name, measure, chart against its
# moon or raise a god for is one of these eight, and the places that must stay eight
# forever say KNOWN_SCHOOLS rather than SCHOOLS.
KNOWN_SCHOOLS = {
    'weave': ('Raw magic', 'chaos, creation, creativity', [166, 104, 214]),
    'umbral': ('Raw magic', 'necrotic, entropy, death, order', [72, 49, 35]),
    'infernal': ('Holy / unholy', 'demons, hellscapes, corruption, evil', [154, 43, 49]),
    'radiant': ('Holy / unholy', 'holy, healing, order, peace, righteousness', [225, 209, 133]),
    'fire': ('Primordial', 'fire, heat, renewal, chaos', [207, 86, 37]),
    'water': ('Primordial', 'water, ice, currents, order', [65, 156, 202]),
    'earth': ('Primordial', 'nature, ground, stone, roots, order', [67, 120, 51]),
    'air': ('Primordial', 'wind, storms, chaos, force', [176, 210, 213]),
}
# Schools outside that taxonomy. Appended, never inserted: dominant_magic exports an
# index into SCHOOLS and biome_variant an index into a catalogue built in this order, so
# the known eight keep positions 0-7 and every world ever generated keeps its meaning.
#
# Generation can never raise one. Their occurrence is locked to zero in the option
# registry, so generate_networks always leaves them empty, and only the corruption API
# puts a node in one. They are declared here, and nowhere else, because a school that
# does not exist in the taxonomy cannot be edited into a world by a caller who guesses
# its name.
HIDDEN_SCHOOLS = {
    'blood': ('Outside', 'sacrifice, lineage, vitality, hunger', [140, 26, 38]),
    'void': ('Outside', 'absence, entropy, unmaking, silence', [26, 22, 40]),
    'rot': ('Outside', 'disease, undeath, decay, rebirth', [124, 130, 62]),
    'eldritch': ('Outside', 'madness, wrong geometry, dominion of minds', [62, 96, 92]),
}
SCHOOLS = {**KNOWN_SCHOOLS, **HIDDEN_SCHOOLS}


def network_geometry(seed, count):
    """Uneven seeded clusters, scattered outliers and independently variable links."""
    rng=random.Random(child_seed(seed,'clustered-ley-v1'))
    def unit():
        y=rng.uniform(-1,1);a=rng.uniform(-math.pi,math.pi);r=math.sqrt(1-y*y)
        return (r*math.cos(a),y,r*math.sin(a))
    clusters=rng.randint(1,min(4,count));centres=[unit() for _ in range(clusters)]
    spread=rng.uniform(.12,.8);outlier=rng.uniform(.05,.4);nodes=[];groups=[]
    for _ in range(count):
        group=rng.randrange(clusters)
        for attempt in range(1000):
            if rng.random()<outlier:p=unit()
            else:
                q=[v+rng.gauss(0,spread) for v in centres[group]];length=math.sqrt(sum(v*v for v in q))
                p=tuple(v/length for v in q)
            if all(abs(sum(a*b for a,b in zip(p,q)))<.9999 for q in nodes):break
        else:raise ValueError('Could not separate ley points')
        nodes.append(p);groups.append(group)
    # Three sacred loci share a straight spherical alignment; other loci remain scattered.
    # This is a fantasy interpretation of Watkins' alignments, not a physical law.
    if count>=3:
        arc=arc_frame(nodes[0],nodes[1]);t=rng.uniform(.3,.7)*arc[3]
        nodes[2]=tuple(x*math.cos(t)+v*math.sin(t) for x,v in zip(arc[0],arc[2]))
        groups[1]=groups[2]=groups[0]
    pairs={(0,2),(1,2)} if count>=3 else set()
    # Sparse trees within clusters; some schools have disconnected concentrations.
    for group in range(clusters):
        members=[i for i,g in enumerate(groups) if g==group]
        if not members:continue
        joined={members[0]}
        while len(joined)<len(members):
            _,a,b=min((1-sum(x*y for x,y in zip(nodes[a],nodes[b])),a,b) for a in sorted(joined) for b in members if b not in joined)
            pairs.add(tuple(sorted((a,b))));joined.add(b)
    link_chance=rng.uniform(.08,.45)
    for a in range(count):
        if rng.random()<link_chance:
            choices=[b for b in range(count) if b!=a]
            b=rng.choice(choices);pairs.add(tuple(sorted((a,b))))
    edges=[]
    for a,b in sorted(pairs):
        frame=arc_frame(nodes[a],nodes[b])
        edges.append({'from':a,'to':b,'path':[[x*math.cos(frame[3]*k/32)+t*math.sin(frame[3]*k/32)
                       for x,t in zip(frame[0],frame[2])] for k in range(33)]})
    return nodes,edges,{'version':2,'model':'landscape_alignments','aligned_nodes':[0,2,1] if count>=3 else [],'clusters':clusters,'spread':spread,'outlier_fraction':outlier,'extra_link_probability':link_chance}


def generate_networks(result, cfg):
    from .terrain_world import options
    o = options(cfg)
    # Authored school widths are a reach on the reference world (design radius 10000 at
    # the recipe scale, 1774.4 m physical). Magic has to cover the same share of the
    # world at every circumference: left as absolute metres, a 110 m Gaussian on a
    # 200 km world falls entirely between raster cells, and every ley field, magic
    # density, biome variant, college and magic-gated habitat collapses to zero.
    width_scale = result['effective_config']['globe_radius']/REFERENCE_RADIUS_M
    networks = {}
    for name, (group, descriptors, color) in SCHOOLS.items():
        seed = child_seed(cfg.seed, 'history-ley-' + name, o[name + '_variation'])
        temporary = {'climate': True, 'layers': {}, 'effective_config': result['effective_config'],
                     'warnings': [], 'timing_ms': {'total': 0}}
        enabled = cfg.magic_enabled and random.Random(seed).random() < o[name + '_occurrence']
        nodes, edges = [], []
        if enabled:
            positions, links, distribution = network_geometry(seed,o[name + '_nodes'])
            rng = random.Random(child_seed(seed, 'intensities'))
            nodes = [{'id': f'{name}-node-{i}', 'direction': list(p), 'intensity': rng.uniform(.35, 1.65)}
                     for i, p in enumerate(positions)]
            edges = [{**e, 'id': f'{name}-line-{i}', 'intensity': rng.uniform(.35, 1.65)}
                     for i, e in enumerate(links)]
        networks[name] = {'name': name, 'group': group, 'descriptors': descriptors, 'color': color,
                          'seed': seed, 'strength': o[name + '_strength'], 'width_m': o[name + '_width']*width_scale,
                          'instability': o[name + '_instability'], 'nodes': nodes, 'edges': edges,
                          'distribution':distribution if enabled else None}
    result['magic'] = {'version': 4, 'school_order': list(SCHOOLS), 'groups': list(dict.fromkeys(v[0] for v in SCHOOLS.values())),
                       'networks': networks, 'colleges': [], 'enabled': bool(cfg.magic_enabled),
                       'mutation_threshold': .35, 'dominance_margin': .08,
                       'method': 'Eight known schools as independently seeded sacred alignments with uneven clusters, scattered outliers and variable connectivity, plus four hidden schools that generation never raises: their occurrence is locked at zero and only the corruption API places a node in one. Node and line intensities are editable; '
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
    # Only the top two of twelve are ever read, so a partial selection replaces a full
    # sort: this runs once per cell. (-potency, name) tuples compare exactly as the old
    # sort key did, and no float is added or reordered -- these are comparisons only.
    ranked = heapq.nsmallest(2, ((-v, k) for k, v in potencies.items()))
    if not ranked:
        return None
    winner = ranked[0][1]
    runner = -ranked[1][0] if len(ranked) > 1 else 0
    return winner if potencies[winner] >= threshold and potencies[winner] - runner >= margin else None


# Each hidden school draws on something the known eight do not. These only ever run for a
# network that already has a node, so a generated world, whose hidden networks are always
# empty, takes none of these paths and its fields are untouched.
BLOOD_FEED_GAIN = 2.5     # dense living multiplies what blood can draw
ELDRITCH_FEED_GAIN = 2.5  # aberrant nests and ruins are what eldritch reads
ROT_REACH_WIDTHS = 6.     # how far rot creeps, measured in its own network widths
ROT_DECAY_WIDTHS = 2.     # e-folding length of that creep, likewise
ROT_MAX_STEPS = 64
VOID_BITE = .8            # share of void potency taken out of every other school


def _saturating_field(sources, vectors, radius, width_m):
    """A 0..1 field of how close each point is to a weighted set of sources."""
    field = []
    for p in vectors:
        total = 0.
        for point, weight in sources:
            angle = math.acos(max(-1., min(1., sum(a*b for a,b in zip(p, point)))))
            total += weight * math.exp(-(radius * angle / width_m)**2)
        field.append(-math.expm1(-total))
    return field


def hidden_feeds(result, magic, vectors, radius):
    """What blood and eldritch find to feed on, as a multiplier per point.

    Blood reads the living: many people, close together. Eldritch reads what the world
    already fears, its aberrant and undead nests and its ruins. Both read the world as it
    stood before this rebuild, because evaluate_networks runs ahead of civilization() and
    add_nests, so a corruption is always one rebuild behind the cities it is eating. Both
    read defensively: at stage nine there are no settlements, nests or ruins at all.
    """
    feeds = {}
    networks = magic.get('networks', {})
    blood = networks.get('blood')
    if blood and blood['nodes']:
        cities = [c for c in result.get('settlements', {}).get('sites', []) if c.get('direction')]
        largest = max((c.get('population_estimate') or 0.) for c in cities) if cities else 0.
        sources = [(c['direction'], (c.get('population_estimate') or 0.) / largest) for c in cities] if largest else []
        field = _saturating_field(sources, vectors, radius, blood['width_m'])
        feeds['blood'] = [1. + BLOOD_FEED_GAIN * v for v in field]
    eldritch = networks.get('eldritch')
    if eldritch and eldritch['nodes']:
        sources = [(nest['direction'], 1.) for nest in result.get('beast_nests', {}).get('sites', [])
                   if nest.get('direction') and nest.get('family') in ('aberrant', 'undead')]
        sources += [(ruin['direction'], 1.) for ruin in result.get('ruins', []) if ruin.get('direction')]
        field = _saturating_field(sources, vectors, radius, eldritch['width_m'])
        feeds['eldritch'] = [1. + ELDRITCH_FEED_GAIN * v for v in field]
    return feeds


def rot_spread(power, net, graph, radius):
    """Rot creeps cell to cell instead of falling off from a node.

    The creep is measured in metres, never in cells: each step carries a neighbour's
    value across that edge's own arc length, decaying over a length derived from the
    network's width. A 33-grid world and a 257-grid world therefore rot at the same
    physical rate, which a fixed iteration count over cells would not give.
    """
    decay_m = ROT_DECAY_WIDTHS * net['width_m']
    arcs = [d for edges in graph for _, d in edges]
    mean_arc = sum(arcs) / len(arcs) if arcs else 0.
    if not mean_arc or not decay_m:
        return power
    steps = min(ROT_MAX_STEPS, max(1, round(ROT_REACH_WIDTHS * net['width_m'] / mean_arc)))
    for _ in range(steps):
        carried = [max([value] + [power[j] * math.exp(-distance / decay_m) for j, distance in graph[i]])
                   for i, value in enumerate(power)]
        if carried == power:
            break
        power = carried
    return power


def void_bite(powers, names):
    """Void does not add potency, it takes it: every other school loses ground to it.

    The subtraction is skipped where void is absent rather than applied as a zero, because
    `max(0., x - 0.)` would turn the negative zero an unmanifested network writes into a
    positive one and move every magic-disabled world's bytes.
    """
    void = powers.get('void')
    if void is None:
        return
    for i, bite in enumerate(v * VOID_BITE for v in void):
        if not bite:
            continue
        for name in names:
            if name != 'void':
                powers[name][i] = max(0., powers[name][i] - bite)


def evaluate_networks(result, cfg):
    """Rebuild only magic-derived fields, preserving the independent network inputs."""
    l = result['layers']; magic = result['magic']; n = cfg.size
    radius = result['effective_config']['globe_radius']
    points, _, graph = sphere_grid(n, radius)
    vectors = [direction(x, z, n) for x, z in points]
    feeds = hidden_feeds(result, magic, vectors, radius)
    powers = {}
    exp, acos = math.exp, math.acos
    for name, net in magic['networks'].items():
        nodes, edges = net['nodes'], net['edges']
        width, strength = net['width_m'], net['strength']
        feed = feeds.get(name)
        # A school with no nodes and no lines sums to integer zero for every point, so
        # every point gets the identical value -- and that value is NEGATIVE zero, since
        # -math.expm1(-0) is -0.0 and the sign survives the multiply. It is written as
        # the same expression rather than a literal so it cannot drift from the loop. The
        # four hidden schools take this path in every generated world: their occurrence is
        # locked at zero, so generation never raises one.
        if not nodes and not edges and feed is None:
            powers[name] = [strength * -math.expm1(-0)] * len(vectors)
            continue
        # Per-point invariants hoisted out of a loop that runs once per cell per school:
        # at size 513 that is 263k iterations x twelve schools. Values and their order of
        # accumulation are untouched -- k is the same ((intensity*(a+b))/2) the inline
        # expression built, and both sums still run over the same sequence.
        node_terms = [(node['intensity'], node['direction']) for node in nodes]
        edge_terms = [(e['intensity'] * (nodes[e['from']]['intensity'] + nodes[e['to']]['intensity']) / 2,
                       arc_frame(nodes[e['from']]['direction'], nodes[e['to']]['direction'])) for e in edges]
        power = []
        for i, p in enumerate(vectors):
            total = sum(intensity * exp(-(radius * acos(max(-1., min(1., sum(a*b for a,b in zip(p,point))))) / width)**2)
                        for intensity, point in node_terms)
            total += sum(k * exp(-(radius * distance_to_frame(p, frame) / width)**2)
                         for k, frame in edge_terms)
            # Applied before saturation, so a well-fed field still tops out at strength.
            if feed is not None:
                total *= feed[i]
            power.append(strength * -math.expm1(-total))
        powers[name] = power
    rot = magic['networks'].get('rot')
    if rot is not None and rot['nodes']:
        powers['rot'] = rot_spread(powers['rot'], rot, graph, radius)
    if magic['networks'].get('void', {}).get('nodes'):
        void_bite(powers, list(magic['networks']))
    for name, net in magic['networks'].items():
        power = powers[name]
        l['ley_' + name] = node_grid(power, points, n)
        l['instability_' + name] = node_grid([min(1., v*net['instability']) for v in power], points, n)
    density, hazard, growth, opposition, winners = [], [], [], [], []
    # The grids, their names and the index of each school are fixed for the whole sweep.
    # Rebuilt per point they were twelve string concatenations, twelve dict lookups and a
    # fresh list(SCHOOLS) whose .index() then scanned it -- per cell, 263k times at 513.
    school_names = list(SCHOOLS)
    school_index = {name: i for i, name in enumerate(school_names)}
    ley_grids = [l['ley_' + name] for name in school_names]
    instability_grids = [l['instability_' + name] for name in school_names]
    for x,z in points:
        p = {name: grid[z][x] for name, grid in zip(school_names, ley_grids)}
        total = sum(p.values())
        conflict = min(p['radiant'], p['infernal']) + min(p['weave'], p['umbral']) + min(p['fire'], p['water'])
        density.append(-math.expm1(-total))
        opposition.append(min(1., conflict))
        hazard.append(min(1., sum(grid[z][x] for grid in instability_grids)*.3 + conflict*.2))
        growth.append((p['earth'] + .6*p['radiant'] + .5*p['weave'] + .4*p['water']) / max(total, 1e-12))
        winner = dominant_school(p)
        winners.append(school_index[winner] if winner else -1)
    for key, vals in [('magic_density', density), ('magic_hazard', hazard), ('magic_growth', growth),
                      ('magic_opposition', opposition), ('dominant_magic', winners)]:
        l[key] = node_grid(vals, points, n)
    # Compatibility projections for existing ecological/nest requirements, never extra networks.
    l['ley_holy'] = l['ley_radiant']
    l['ley_primordial'] = node_grid([max(l['ley_'+s][z][x] for s in ('fire','water','earth','air')) for x,z in points], points, n)
    from .terrain_profiles import civilization_ids
    for people in civilization_ids():
        l['magic_risk_'+people] = node_grid(hazard, points, n)
    magic['nodes'], magic['edges'] = [], []
    for name, net in magic['networks'].items():
        offset = len(magic['nodes'])
        magic['nodes'].extend(node['direction'] for node in net['nodes'])
        magic['edges'].extend({**e, 'from': e['from']+offset, 'to': e['to']+offset, 'network': name,
                               'strength': e['intensity']} for e in net['edges'])
    magic['compatibility_fields'] = {'ley_holy': 'radiant', 'ley_primordial': 'maximum of fire, water, earth, air'}
