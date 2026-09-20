"""Divine visitation: the orchestrator summons a god onto the mortal plane. Stateless JSON API v1.

Same input, same output; the caller's world is unchanged; persist the returned world to
call again. A summoned god is highly disruptive: an avatar cluster saturates its school
around the target, the cities within reach roll their fate under divine pressure, rival
nests are driven out, survivors convert, and when the god departs a footprint key point,
the ruins, the mutated biomes and the converted faiths remain. Every distance is a ratio
of settlement spacing, never a metre constant or a raster cell, so world scale and
raster size cannot turn a local visitation into a regional one.
"""
import copy
from .terrain_history import adopt_world
from .terrain_errors import (cross_field, missing_block, over_capacity,
                             refused_by_world, unknown_field, unsupported_api,
                             wrong_type)
import math
import random
from time import perf_counter
from .terrain_tectonics import child_seed
from .terrain_globe import direction
from .terrain_leyline_history import SCHOOLS, KNOWN_SCHOOLS, edit_network
from .terrain_astrology import HEMISPHERES, tide, DAYS_PER_YEAR
from .terrain_ruins import ruin_legacy
from .terrain_religion import gods_by_id, catalogue_identity, add_religion, VERSION as RELIGION_VERSION

API_VERSION = 1
VISITATION_FIELDS = ('api_version', 'world', 'god_id', 'target', 'wrath',
                     'variation', 'depart', 'day')
MAX_VISITATIONS = 8
RING_POINTS = 4
RING_SPACINGS = .5
REACH_SPACINGS = 3.
AVATAR_INTENSITY, RING_INTENSITY, FOOTPRINT_INTENSITY = 4., 3., 3.5
DIVINE_WEIGHT = .6
SUPPRESSION = .5
FAVOR_RELIEF = .2
OPPOSED = {'radiant': 'infernal', 'infernal': 'radiant', 'weave': 'umbral', 'umbral': 'weave', 'fire': 'water', 'water': 'fire'}
ASPECT_FACTOR = {'wild': 2., 'sovereign': .5}
ORDER = ['avatar cluster', 'opposed suppression', 'divine fate lottery', 'ruins and legacies', 'leyline update',
         'biomes', 'civilization', 'nests and purge', 'threat assessment and favour', 'astrology', 'conversion']


def reach_m(world, cfg):
    return REACH_SPACINGS * cfg.settlement_spacing


def _unit(v):
    length = math.sqrt(sum(x * x for x in v))
    return tuple(x / length for x in v)


def _angle(a, b):
    return math.acos(max(-1., min(1., sum(x * y for x, y in zip(a, b)))))


def _offset(up, angle, bearing):
    """A unit vector `angle` radians from `up` along a bearing in its tangent plane."""
    reference = (1., 0., 0.) if abs(up[1]) > .999 else (0., 1., 0.)
    dot = sum(r * u for r, u in zip(reference, up))
    north = _unit(tuple(r - dot * u for r, u in zip(reference, up)))
    east = _unit((north[1] * up[2] - north[2] * up[1], north[2] * up[0] - north[0] * up[2], north[0] * up[1] - north[1] * up[0]))
    tangent = tuple(math.cos(bearing) * e + math.sin(bearing) * n for e, n in zip(east, north))
    return _unit(tuple(math.cos(angle) * u + math.sin(angle) * t for u, t in zip(up, tangent)))


def god_schools(god_id, world, day):
    """The schools a god's avatar saturates; the moon takes the hemisphere leaning that day."""
    affinity = gods_by_id()[god_id]['school_affinity']
    if affinity == ['moon']:
        from .terrain_astrology import moon_state
        leaning = 'still' if moon_state(world['astrology']['moon'], day)['nod_degrees'] >= 0 else 'restless'
        return [s for s in KNOWN_SCHOOLS if s in HEMISPHERES[leaning]]
    return [s for s in KNOWN_SCHOOLS if s in affinity]


def validate_visitation(body):
    """Reject anything the age boundary would, plus every way a summons can be malformed."""
    from .terrain_history import validate_age_world
    if not isinstance(body, dict):
        raise wrong_type('request', body, {'type': 'object'})
    if set(body) - set(VISITATION_FIELDS):
        raise unknown_field(sorted(set(body) - set(VISITATION_FIELDS))[0], VISITATION_FIELDS,
                            noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (API_VERSION,))
    world = body.get('world')
    cfg = validate_age_world(world)
    for key in ('astrology', 'lunar_almanac', 'religion'):
        if not isinstance(world.get(key), dict) or world[key].get('version') != 1:
            raise missing_block(key, 'This world lacks the ' + key + ' contract at version 1. '
                                'It is written during generation, so a world exported before '
                                'that contract has to be regenerated rather than migrated.')
    if world['religion']['catalogue'] != catalogue_identity():
        raise missing_block('religion.catalogue',
                            'This world was built against a different pantheon catalogue. '
                            'The gods it names may not exist here, so it must be regenerated '
                            'or explicitly migrated rather than summoned into.')
    god_id = body.get('god_id')
    god = next((g for g in world['religion']['gods'] if g['id'] == god_id), None)
    if god is None:
        raise unknown_field(god_id, [g['id'] for g in world['religion']['gods']], noun='god')
    depart = body.get('depart', False)
    if type(depart) is not bool:
        raise wrong_type('depart', depart, {'type': 'boolean'})
    if depart:
        if god['status'] != 'walking':
            raise refused_by_world('god_id', god_id, 'Only a walking god can depart; %s is %s.'
                                   % (god_id, god['status']))
        # `status` alone is not the precondition `depart_god` actually needs: it needs an
        # undeparted visitation record. A god revealed by `terrain_corruption._reveal`
        # walks without one, and would otherwise reach depart_god's `next()` and raise a
        # bare StopIteration. `.get`, not subscripts - records in the wild are not all
        # complete, and a validator must not raise KeyError on the input it is judging.
        if not any(v.get('god_id') == god_id and v.get('departed_age') is None
                   for v in (world['religion'].get('visitations', []) or [])):
            raise refused_by_world('god_id', god_id,
                                   'That god does not walk by visitation and cannot depart; '
                                   'a god revealed by corruption is opposed through its '
                                   'corruption, not sent home.')
        if set(body) & {'target', 'wrath'}:
            raise cross_field('A departure takes no target or wrath; those describe a '
                              'summons. Send depart on its own.',
                              sorted(set(body) & {'target', 'wrath'}) + ['depart'])
        return cfg, god, None, 0., 0
    if god['status'] == 'walking':
        raise refused_by_world('god_id', god_id, '%s already walks the world; summon another '
                               'god or send this one home first.' % god_id)
    if god['status'] not in ('manifest', 'sleeping'):
        raise refused_by_world('god_id', god_id, 'An absent god cannot be summoned; %s does '
                               'not exist in this world.' % god_id,
                               alternatives=[g['id'] for g in world['religion']['gods']
                                             if g['status'] in ('manifest', 'sleeping')])
    if len(world['religion'].get('visitations', [])) >= MAX_VISITATIONS:
        raise over_capacity('visitations', len(world['religion'].get('visitations', [])),
                            MAX_VISITATIONS, 'per-world visitation')
    target = body.get('target')
    if not isinstance(target, dict):
        raise wrong_type('target', target, {'type': 'object'})
    if len(target) != 1 or not set(target) <= {'city_uid', 'node'}:
        raise cross_field('target names exactly one place, as {"city_uid": ...} or '
                          '{"node": ...}.', ('city_uid', 'node'))
    points = world['water']['nodes']
    if 'city_uid' in target:
        city = next((s for s in world['settlements']['sites'] if s['uid'] == target['city_uid']), None)
        if city is None:
            raise ValueError('Unknown city')
        node = city['node']
    else:
        node = target['node']
        if type(node) is not int or not 0 <= node < len(points):
            raise ValueError('target node outside the grid')
    x, z = points[node]
    if world['layers']['water_type'][z][x] != 0:
        raise ValueError('A god walks on land; the target is water')
    wrath = body.get('wrath', .5)
    if type(wrath) not in (int, float) or not math.isfinite(wrath) or not 0 <= wrath <= 1:
        raise ValueError('wrath must be 0..1')
    variation = body.get('variation', 0)
    if type(variation) is not int or not 0 <= variation < 2**32:
        raise ValueError('variation must be a uint32')
    day = body.get('day')
    if day is not None and (type(day) is not int or day < 0):
        raise ValueError('day must be an integer day >= 0')
    return cfg, god, node, float(wrath), variation


def _faith_factor(world, city, god_id):
    faith = world['religion']['faiths'].get(city['population_profile'])
    if not faith:
        return 1.
    if god_id in faith['gods']:
        return .25
    patron = faith.get('patron')
    if patron and (god_id in gods_by_id()[patron].get('rivals', []) or patron in gods_by_id()[god_id].get('rivals', [])):
        return 2.
    return 1.


def avatar_cluster(result, cfg, god_id, schools, node, rng, index):
    x, z = result['water']['nodes'][node]
    centre = direction(x, z, cfg.size)
    angle = RING_SPACINGS * cfg.settlement_spacing / result['effective_config']['globe_radius']
    base = rng.uniform(0, 2 * math.pi)
    placements = [(centre, AVATAR_INTENSITY)] + [(_offset(centre, angle, base + k * 2 * math.pi / RING_POINTS), RING_INTENSITY)
                                                 for k in range(RING_POINTS)]
    ids = []
    for school in schools:
        net = result['magic']['networks'][school]
        for k, (point, intensity) in enumerate(placements):
            node_id = f'avatar-{god_id}-{index}-{school}-{k}'
            net = edit_network(net, new_node={'id': node_id, 'direction': list(point), 'intensity': intensity})
            ids.append(node_id)
        result['magic']['networks'][school] = net
    return ids, centre


def suppress_opposed(result, schools, centre, reach, wrath):
    """Weaken rival schools within reach; the record lets departure restore them exactly."""
    radius = result['effective_config']['globe_radius']
    scale = 1 - SUPPRESSION * wrath
    restore = []
    for school in schools:
        opposed = OPPOSED.get(school)
        if not opposed:
            continue
        net = result['magic']['networks'][opposed]
        near = {i for i, n in enumerate(net['nodes']) if radius * _angle(centre, n['direction']) <= reach}
        for i in sorted(near):
            restore.append({'school': opposed, 'node_id': net['nodes'][i]['id'], 'intensity': net['nodes'][i]['intensity']})
            net['nodes'][i]['intensity'] *= scale
        for edge in net['edges']:
            if edge['from'] in near or edge['to'] in near:
                restore.append({'school': opposed, 'line_id': edge['id'], 'intensity': edge['intensity']})
                edge['intensity'] *= scale
    return restore


def divine_lottery(result, cfg, god, schools, centre, reach, wrath, seed, index, variation):
    """Every city within reach rolls the age lottery with one more cause: the god itself."""
    from .terrain_history import ley_threat_pressure, fantasy_nest_threats, LEY_DESTRUCTION, RUIN_KEYS
    radius = result['effective_config']['globe_radius']
    layers = result['layers']
    nests = result.get('beast_nests', {}).get('sites', [])
    record = gods_by_id()[god['id']]
    aspect_factor = ASPECT_FACTOR.get(god['aspect'], 1.)
    cities = copy.deepcopy(result['settlements']['sites'])
    survivors, ruins, favored = [], [], []
    age = len(result['history']['ages'])
    for city in cities:
        distance = radius * _angle(centre, city['direction'])
        if distance > reach:
            survivors.append(city)
            continue
        # Every school, known or not: a god smiting a city sees the ground as it is.
        potencies = {name: layers['ley_' + name][city['z']][city['x']] if 'ley_' + name in layers else 0. for name in SCHOOLS}
        causes = []
        ley_pressure, ley = ley_threat_pressure(city, layers)
        if ley:
            causes.append((ley['school'], ley_pressure, LEY_DESTRUCTION[ley['school']], ley))
        for threat in fantasy_nest_threats(city, nests, radius):
            causes.append((threat['kind'], threat['weight'], threat['reason'],
                           {'nest_id': threat['nest_id'], 'family': threat.get('family'),
                            'distance_m': threat['distance_m'], 'reach_m': threat['reach_m']}))
        faith_factor = _faith_factor(result, city, god['id'])
        weight = DIVINE_WEIGHT * wrath * (1 - distance / reach) * aspect_factor * faith_factor
        causes.append(('divine_' + god['id'], weight, f"{god['aspect_name'] or god['name']}: {record['smite']}.",
                       {'god_id': god['id'], 'distance_m': distance, 'reach_m': reach, 'aspect': god['aspect'],
                        'faith_factor': faith_factor}))
        chance = min(.9, sum(c[1] for c in causes))
        rng = random.Random(child_seed(seed, f"visitation-{index}-{god['id']}-{city['uid']}", variation))
        draw = rng.random()
        if draw >= chance:
            survivors.append(city)
            if faith_factor < 1:
                strength = round(wrath * (1 - distance / reach), 6)
                city.setdefault('favor', []).append({'god_id': god['id'], 'strength': strength, 'visitation': index})
                favored.append({'city_uid': city['uid'], 'strength': strength})
            continue
        selector = (draw / chance) * sum(c[1] for c in causes)
        chosen = causes[-1]
        for cause in causes:
            selector -= cause[1]
            if selector <= 0:
                chosen = cause
                break
        legacy = ruin_legacy(city, chosen[0], potencies, nest_family=chosen[3].get('family'), god_school=schools[0])
        ruin = {k: copy.deepcopy(city[k]) for k in RUIN_KEYS if k in city}
        ruin.update(id='ruin-' + city['uid'], kind='ruins', destroyed_age=age, asset_id='marker.city_ruins',
                    cause=chosen[0], reason=chosen[2], evidence=chosen[3], probability=chance, roll=draw,
                    new_node_school=legacy['school'], legacy=legacy, visitation=index)
        ruins.append(ruin)
    return survivors, ruins, favored


def _rebuild(result, cfg, survivors, label, age):
    """The age transition's tail, shared with it: fields, biomes, civilization, nests, threats, almanac.

    The pantheon is not re-resolved here; a visitation writes its own religion records and
    calls add_religion once they are in place.
    """
    from .terrain_history import rebuild_tail
    rebuild_tail(result, cfg, survivors, label, age, religion=False)


OWN_STATE = ('astrology', 'lunar_almanac', 'religion')


def state_keys():
    """The pipeline's snapshot keys plus this feature's own, until the pipeline lists them."""
    from .terrain_history import STATE_KEYS
    return tuple(STATE_KEYS) + tuple(k for k in OWN_STATE if k not in STATE_KEYS)


def _snapshot(result, previous_layers, previous_state, title, kind):
    STATE_KEYS = state_keys()
    if 'build_stages' not in result:
        return
    stage = len(result['build_stages']) + 1
    result['build_stages'].append({'stage': stage, 'title': title, 'kind': kind,
        'layers': {k: copy.deepcopy(v) for k, v in result['layers'].items() if previous_layers.get(k) != v},
        'removed_layers': sorted(set(previous_layers) - set(result['layers'])),
        'state': {k: copy.deepcopy(result.get(k)) for k in STATE_KEYS if previous_state.get(k) != result.get(k)}})
    result['phases']['titles'] = [s['title'] for s in result['build_stages']]
    result['phases']['completed'] = stage


def summon(result, cfg, god, node, wrath, variation, day=None):
    STATE_KEYS = state_keys()
    previous_layers = copy.deepcopy(result['layers'])
    previous_state = {k: copy.deepcopy(result.get(k)) for k in STATE_KEYS}
    religion = result['religion']
    index = len(religion.get('visitations', []))
    seed = cfg.seed
    age = len(result['history']['ages'])
    if day is None:
        day = int((result['settlements'].get('founding') or {}).get('end_year', 0)) * DAYS_PER_YEAR
    schools = god_schools(god['id'], result, day)
    rng = random.Random(child_seed(seed, f"visitation-{index}-{god['id']}", variation))
    reach = reach_m(result, cfg)
    cluster, centre = avatar_cluster(result, cfg, god['id'], schools, node, rng, index)
    restore = suppress_opposed(result, schools, centre, reach, wrath)
    survivors, ruins, favored = divine_lottery(result, cfg, god, schools, centre, reach, wrath, seed, index, variation)
    result.setdefault('ruins', []).extend(ruins)
    for ruin in ruins:
        net = result['magic']['networks'][ruin['legacy']['school']]
        result['magic']['networks'][ruin['legacy']['school']] = edit_network(
            net, new_node={'id': ruin['id'] + '-key', 'direction': ruin['direction'], 'intensity': ruin['legacy']['intensity']})
    for key in ('city_plans', 'hamlet_plans', 'castle_plans', 'world_scene'):
        result.pop(key, None)
    _rebuild(result, cfg, survivors, 'visitation', age)
    radius = result['effective_config']['globe_radius']
    purge = set(gods_by_id()[god['id']].get('purge_families', []))
    kept, purged = [], []
    for nest in result['beast_nests']['sites']:
        if nest.get('family') in purge and not nest.get('real', True) and radius * _angle(centre, nest['direction']) <= reach:
            purged.append(nest['id'])
        else:
            kept.append(nest)
    result['beast_nests']['sites'] = kept
    favored_uids = {f['city_uid'] for f in favored}
    for report in result.get('threat_assessments', {}).get('cities', []):
        favor = next((f for f in favored if f['city_uid'] == report['city_uid']), None)
        if favor:
            report['divine_favor'] = favor['strength']
            report['regional_threat'] = round(max(0., report['regional_threat'] - FAVOR_RELIEF * favor['strength']), 6)
    converted = []
    for city in result['settlements']['sites']:
        if radius * _angle(centre, city['direction']) <= reach and city['uid'] not in {r['uid'] for r in ruins}:
            faith = religion['faiths'].get(city['population_profile'])
            if faith and faith.get('patron') != god['id'] and city['population_profile'] not in converted:
                converted.append(city['population_profile'])
    # The sky on the arrival day itself, which the orchestrator may have named.
    from .terrain_astrology import day_state
    moon = {'day': day, **day_state(result['astrology']['moon'], day)}
    record = {'index': index, 'god_id': god['id'], 'aspect': god['aspect'], 'node': node, 'direction': list(centre),
              'age': age, 'day': day, 'wrath': wrath, 'variation': variation, 'schools': schools, 'reach_m': reach,
              'cluster': cluster, 'restore': restore, 'ruins': [r['id'] for r in ruins], 'purged_nests': purged,
              'favored': favored, 'converted': converted, 'departed_age': None, 'moon': moon, 'order': ORDER}
    for god_record in religion['gods']:
        if god_record['id'] == god['id']:
            god_record['status'] = 'walking'
            god_record['avatar'] = {'node': node, 'since_age': age, 'day': day, 'visitation': index, 'cluster': cluster}
    for civilization_id in converted:
        religion['faiths'][civilization_id]['conversion'] = {'god_id': god['id'], 'visitation': index}
    religion['sites'].append({'id': f"theophany-{index}-{god['id']}", 'kind': 'theophany', 'god_id': god['id'],
                              'node': node, 'visitation': index})
    religion.setdefault('visitations', []).append(record)
    add_religion(result, cfg)
    result['history'].setdefault('operations', []).append({'api_version': API_VERSION, 'kind': 'visitation',
        'visitation': index, 'god_id': god['id'], 'node': node, 'wrath': wrath, 'variation': variation})
    _finish(result)
    _snapshot(result, previous_layers, previous_state, f"Visitation {index + 1}: {god['name']}", 'visitation')
    return record


def depart_god(result, cfg, god_id, age=None, rebuild=True):
    """The god leaves: cluster collapses to a footprint, rivals recover, the theophany becomes a pilgrimage."""
    religion = result['religion']
    # Defaulted deliberately: a bare `next()` here raised StopIteration with no message out
    # of two validated request APIs, and inside a caller's generator expression that reads
    # as a normal stop rather than as a failure.
    record = next((v for v in reversed(religion.get('visitations', []) or [])
                   if v.get('god_id') == god_id and v.get('departed_age') is None), None)
    if record is None:
        raise ValueError('No undeparted visitation for ' + str(god_id) + '; that god does not '
                         'walk by visitation')
    cluster = set(record['cluster'])
    for school, net in result['magic']['networks'].items():
        if not any(n['id'] in cluster for n in net['nodes']):
            continue
        # Edges index their endpoints by position, so dropping a node renumbers every
        # edge after it. Avatar nodes carry no edges and are appended last, which is why
        # a plain filter was safe; a corrupted network can hold nodes that do have edges,
        # so the endpoints are remapped rather than left pointing at whatever slid down.
        keep = [i for i, n in enumerate(net['nodes']) if n['id'] not in cluster]
        moved = {old: new for new, old in enumerate(keep)}
        net['nodes'] = [net['nodes'][i] for i in keep]
        net['edges'] = [{**e, 'from': moved[e['from']], 'to': moved[e['to']]}
                        for e in net['edges'] if e['from'] in moved and e['to'] in moved]
    school = record['schools'][0]
    result['magic']['networks'][school] = edit_network(result['magic']['networks'][school], new_node={
        'id': f"footprint-{god_id}-{record['index']}", 'direction': list(record['direction']), 'intensity': FOOTPRINT_INTENSITY})
    for item in record['restore']:
        net = result['magic']['networks'][item['school']]
        pool = net['nodes'] if 'node_id' in item else net['edges']
        target = next((v for v in pool if v['id'] == item.get('node_id', item.get('line_id'))), None)
        if target is not None:
            target['intensity'] = item['intensity']
    record['departed_age'] = len(result['history']['ages']) if age is None else age
    for god_record in religion['gods']:
        if god_record['id'] == god_id:
            god_record['status'] = 'manifest'
            god_record.pop('avatar', None)
    for site in religion['sites']:
        if site.get('kind') == 'theophany' and site.get('visitation') == record['index']:
            site['kind'] = 'pilgrimage'
    if rebuild:
        _rebuild(result, cfg, copy.deepcopy(result['settlements']['sites']), 'departure', record['departed_age'])
        add_religion(result, cfg)
    return record


def walking_gods(result):
    return [g['id'] for g in result.get('religion', {}).get('gods', []) if g['status'] == 'walking']


def _finish(result):
    from .city_planner import fill_cities
    from .hamlet_planner import fill_hamlets
    from .castle_planner import fill_castles
    fill_cities(result)
    fill_hamlets(result)
    fill_castles(result)
    from .world_debug import build_debug
    result['debug_stats'] = build_debug(result)


def visitation_request(body):
    """Summon a god (or send a walking one home) and return the transformed world."""
    cfg, god, node, wrath, variation = validate_visitation(body)
    world = body['world']
    started = perf_counter()
    result = adopt_world(world)
    if body.get('depart', False):
        STATE_KEYS = state_keys()
        previous_layers = copy.deepcopy(result['layers'])
        previous_state = {k: copy.deepcopy(result.get(k)) for k in STATE_KEYS}
        for key in ('city_plans', 'hamlet_plans', 'castle_plans', 'world_scene'):
            result.pop(key, None)
        record = depart_god(result, cfg, god['id'])
        result['history'].setdefault('operations', []).append({'api_version': API_VERSION, 'kind': 'departure',
                                                               'visitation': record['index'], 'god_id': god['id']})
        _finish(result)
        _snapshot(result, previous_layers, previous_state, f"Departure {record['index'] + 1}: {god['name']}", 'departure')
    else:
        summon(result, cfg, god, node, wrath, variation, body.get('day'))
    result['visitation_api_version'] = API_VERSION
    result['timing_ms']['visitation_total'] = (perf_counter() - started) * 1000
    return result
