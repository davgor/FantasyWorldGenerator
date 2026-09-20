"""Corruption: a hidden god seats a super villain as its instrument. Stateless JSON API v1.

Same input, same output; the caller's world is unchanged; persist the returned world to
call again. This is the only path by which a hidden school ever gets a node: generation
locks their occurrence at zero and player leyline edits are restricted to the known
eight, so nothing else in the codebase can reach them.

The gate is the game's ledger. It reports how many villains the player has met across
playthroughs as `encounters`, and below a god's noticing point the chance is exactly
zero — the gods are not watching yet. Above it, it climbs. Which god takes an interest is
never rolled: it is read from the world, so the corruption fits the place it happens.

The corrupted node, not the villain, is the thing that persists. Killing a holder unseats
them and leaves the nodes; an unheld node is a spawner.
"""
import copy
import math
from time import perf_counter

from .terrain_globe import direction
from .terrain_leyline_history import HIDDEN_SCHOOLS, edit_network
from .terrain_religion import (add_religion, catalogue_identity, gods_by_id, hidden_catalogue,
                               hidden_gods_by_id, VERSION as RELIGION_VERSION)
from .terrain_tectonics import child_seed
# One snapshot body, several callers: a third copy of this is exactly the duplication
# that had age_transition and _rebuild silently disagreeing before they were unified.
from .terrain_visitation import state_keys, _snapshot

API_VERSION = 1
RING_POINTS = 3
RING_SPACINGS = .4
REACH_SPACINGS = 2.5
SEAT_INTENSITY, RING_INTENSITY = 4., 2.5
NODE_BUDGET = 96          # corrupted nodes a world may carry; cleansing frees them
FARM_SHARE = .45          # of a city's people, at the seat, when blood takes it
TAKEN_KEY = 'taken_by'
ORDER = ['gate', 'god', 'host', 'corrupted cluster', 'leyline update', 'biomes',
         'civilization', 'nests', 'threat assessment', 'failure mode', 'pantheon reaction']


def _angle(a, b):
    return math.acos(max(-1., min(1., sum(x * y for x, y in zip(a, b)))))


def _unit(v):
    length = math.sqrt(sum(x * x for x in v))
    return tuple(x / length for x in v)


def _offset(up, angle, bearing):
    reference = (1., 0., 0.) if abs(up[1]) > .999 else (0., 1., 0.)
    dot = sum(r * u for r, u in zip(reference, up))
    north = _unit(tuple(r - dot * u for r, u in zip(reference, up)))
    east = _unit((north[1] * up[2] - north[2] * up[1], north[2] * up[0] - north[0] * up[2],
                  north[0] * up[1] - north[1] * up[0]))
    tangent = tuple(math.cos(bearing) * e + math.sin(bearing) * n for e, n in zip(east, north))
    return _unit(tuple(math.cos(angle) * u + math.sin(angle) * t for u, t in zip(up, tangent)))


# --- what each god reads in the world -------------------------------------------------

def interest(kind, world):
    """How much a god wants this world, in 0..1. Read, never rolled."""
    cities = world.get('settlements', {}).get('sites', [])
    if kind == 'living':
        people = sum((c.get('population_estimate') or 0.) for c in cities)
        return min(1., people / 200000.) if people else 0.
    if kind == 'decay':
        ruins = len(world.get('ruins', []))
        return min(1., ruins / max(1, len(cities) + ruins))
    if kind == 'aberrant':
        nests = world.get('beast_nests', {}).get('sites', [])
        wrong = sum(1 for n in nests if n.get('family') in ('aberrant', 'undead'))
        return min(1., wrong / 24.) if wrong else 0.
    if kind == 'dead_magic':
        networks = world.get('magic', {}).get('networks', {})
        live = sum(1 for name, net in networks.items() if name not in HIDDEN_SCHOOLS and net.get('nodes'))
        return max(0., 1. - live / 8.)
    raise ValueError('Unknown interest kind ' + kind)


def chance(god, encounters):
    """Exactly zero below the noticing point, then a climb toward certain.

    Zero and not merely small: a guaranteed-clean early playthrough is what makes the
    first corruption read as something the player caused.
    """
    noticing, climb = god['noticing'], god['climb']
    if encounters < noticing:
        return 0.
    if climb <= noticing:
        return 1.
    return max(0., min(1., (encounters - noticing) / float(climb - noticing)))


def watching(world, encounters):
    """Every hidden god whose noticing point is passed and whose rule holds, ranked."""
    from .terrain_religion import rule_holds
    facts = world.get('religion', {}).get('facts')
    if not facts:
        return []
    manifest = frozenset(g['id'] for g in world['religion']['gods'] if g.get('status') in ('manifest', 'walking'))
    rows = []
    for god in hidden_catalogue()['gods']:
        if chance(god, encounters) <= 0. or not rule_holds(god['exists'], facts, manifest):
            continue
        rows.append((interest(god['interest'], world), god['id'], god))
    # Most interested first, ties by id: a draw between two gods is decided by the world
    # and then by name, never by a roll.
    return [god for _, _, god in sorted(rows, key=lambda r: (-r[0], r[1]))]


# --- validation -----------------------------------------------------------------------

def validate_corruption(body):
    from .terrain_history import validate_age_world
    allowed = {'api_version', 'world', 'encounters', 'variation', 'villain_uid'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError('Expected api_version, world, encounters, optional variation and villain_uid')
    if type(body.get('api_version')) is not int or body['api_version'] != API_VERSION:
        raise ValueError('Unsupported corruption API version')
    world = body.get('world')
    cfg = validate_age_world(world)
    religion = world.get('religion')
    if not isinstance(religion, dict) or religion.get('version') != RELIGION_VERSION:
        raise ValueError('World lacks the religion contract; regenerate')
    if religion.get('catalogue') != catalogue_identity():
        raise ValueError('Pantheon catalogue changed; regenerate or explicitly migrate this world')
    encounters = body.get('encounters', 0)
    if type(encounters) is not int or not 0 <= encounters < 2**32:
        raise ValueError('encounters must be a uint32')
    variation = body.get('variation', 0)
    if type(variation) is not int or not 0 <= variation < 2**32:
        raise ValueError('variation must be a uint32')
    villain_uid = body.get('villain_uid')
    if villain_uid is not None and not isinstance(villain_uid, str):
        raise ValueError('villain_uid must be a string')
    # Standing only: a god reaches for someone who holds ground, and `people` now keeps
    # the fallen too. A world whose only villain has fallen has none to corrupt.
    from .terrain_villains import standing
    people = standing(world.get('villains', {}).get('people', []))
    if not people:
        raise ValueError('Corruption needs a super villain to seat; this world has none')
    if villain_uid is not None and not any(p['uid'] == villain_uid for p in people):
        raise ValueError('Unknown villain_uid')
    held = sum(len(c['nodes']) for c in religion.get('corruptions', []) if not c.get('cleansed_age'))
    if held >= NODE_BUDGET:
        raise ValueError(f'At most {NODE_BUDGET} corrupted nodes per world; cleanse before corrupting further')
    return cfg, encounters, variation, villain_uid


# --- the act --------------------------------------------------------------------------

def _host(world, villain_uid):
    """The villain a god reaches for: the named one, else the one with the most reach.

    Already taken by a hidden god is the only disqualification. Being sworn to an old one
    is not: a villain bound to a school god is precisely who a hidden god reaches for, and
    excluding them made every seated villain ineligible the moment they started sinking
    wells, because sinking a well binds them to their school's god.
    """
    from .terrain_villains import standing
    candidates = standing(world['villains']['people'])
    people = [p for p in candidates if not p.get('corrupted')]
    if villain_uid is not None:
        return next((p for p in candidates if p['uid'] == villain_uid), None)
    return max(people, key=lambda p: (p['tier'], p['uid'])) if people else None


def _cluster(result, cfg, god, host, rng, index):
    """The corrupted nodes themselves, which are what actually persists."""
    centre = tuple(host['direction'])
    angle = RING_SPACINGS * cfg.settlement_spacing / result['effective_config']['globe_radius']
    base = rng.uniform(0, 2 * math.pi)
    placements = [(centre, SEAT_INTENSITY)] + [
        (_offset(centre, angle, base + k * 2 * math.pi / RING_POINTS), RING_INTENSITY)
        for k in range(RING_POINTS)]
    school = god['school']
    net = result['magic']['networks'][school]
    ids = []
    for k, (point, strength) in enumerate(placements):
        node_id = f'corrupt-{god["id"]}-{index}-{k}'
        net = edit_network(net, new_node={'id': node_id, 'direction': list(point), 'intensity': strength})
        ids.append(node_id)
    result['magic']['networks'][school] = net
    return ids


def _failure_mode(result, god, host, reach, age):
    """What the four do to a city, which is the whole reason they play differently."""
    school = god['school']
    radius = result['effective_config']['globe_radius']
    touched, ruined = [], []
    survivors = []
    for city in result['settlements']['sites']:
        distance = radius * _angle(city['direction'], host['direction'])
        if distance > reach:
            survivors.append(city)
            continue
        share = 1. - distance / reach
        if school == 'blood':
            # Farmed: the city stands and its people do not.
            before = city.get('population_estimate') or 0.
            city['population_estimate'] = round(before * (1. - FARM_SHARE * share), 6)
            touched.append({'uid': city['uid'], 'effect': 'farmed', 'people_lost': round(before - city['population_estimate'], 6)})
            survivors.append(city)
        elif school == 'eldritch':
            # Taken, not destroyed. Nothing visibly changes, which is the horror.
            city[TAKEN_KEY] = god['id']
            touched.append({'uid': city['uid'], 'effect': 'taken'})
            survivors.append(city)
        else:
            # Rot and Void both end the city; what they leave behind differs.
            cause = 'rot_plague' if school == 'rot' else 'void_unmade'
            ruined.append((city, cause, share))
    return survivors, touched, ruined


def corruption_legacy(city, cause, potencies, school):
    """The key point a city unmade by a walking god leaves behind.

    `cause` is `rot_plague` or `void_unmade`, and no `source_school` branch names either,
    so `ruin_legacy` is asked only for the class intensity: the god is the source and the
    school and basis are stated here rather than resolved.

    This used to pass the god's school to `ruin_legacy` as `villain_school` and then
    overwrite `school` on the way out. Only a `villain`-prefixed cause ever reads that
    parameter, so the argument did nothing and the returned `basis` stayed `region` - the
    ruin claimed the region's dominant magic had chosen a hidden school, which the region
    can never hold: hidden schools are locked to zero occurrence and this API is the only
    thing that ever puts a node in one.
    """
    from .terrain_ruins import ruin_legacy
    legacy = ruin_legacy(city, cause, potencies)
    legacy['school'] = school
    legacy['basis'] = 'source'
    return legacy


def corrupt(result, cfg, god, host, encounters, variation, index, age):
    from .terrain_history import RUIN_KEYS, rebuild_tail, city_potencies
    import random
    rng = random.Random(child_seed(cfg.seed, f'corruption-{index}-{god["id"]}', variation))
    nodes = _cluster(result, cfg, god, host, rng, index)
    # A corrupted villain reaches as far as it already did. The floor matters because a
    # villain whose own seat city has since fallen still sits where its node is, and the
    # nearest survivor can be further away than a fixed constant would ever carry.
    reach = max(float(host.get('reach_m') or 0.), REACH_SPACINGS * cfg.settlement_spacing)
    survivors, touched, ruined = _failure_mode(result, god, host, reach, age)

    ruins = result.setdefault('ruins', [])
    made = []
    for city, cause, share in ruined:
        potencies = city_potencies(city, result['layers'])
        legacy = corruption_legacy(city, cause, potencies, god['school'])
        record = {k: copy.deepcopy(city[k]) for k in RUIN_KEYS if k in city}
        record.update(id='ruin-' + city['uid'], kind='ruins', destroyed_age=age,
                      asset_id='marker.city_ruins', cause=cause,
                      reason=f"{god['name']}: {god['smite']}.",
                      evidence={'god_id': god['id'], 'school': god['school'], 'share': round(share, 6),
                                'corruption': index},
                      probability=1., roll=0., new_node_school=god['school'], legacy=legacy,
                      corruption=index)
        ruins.append(record)
        made.append(record['id'])

    for key in ('city_plans', 'hamlet_plans', 'castle_plans', 'world_scene'):
        result.pop(key, None)
    rebuild_tail(result, cfg, survivors, 'corruption', age, religion=False)

    host['god'] = god['id']
    host['school'] = god['school']
    host['corrupted'] = True
    host['held_nodes'] = sorted(set(host.get('held_nodes', [])) | set(nodes))
    host.setdefault('log', []).append({'age': age, 'event': 'corrupted', 'god': god['id'],
                                       'encounters': encounters})
    for person in result['villains']['people']:
        if person['uid'] == host['uid']:
            person.update(host)

    record = {'index': index, 'god_id': god['id'], 'school': god['school'], 'villain_uid': host['uid'],
              'age': age, 'encounters': encounters, 'variation': variation, 'nodes': nodes,
              'reach_m': reach, 'touched': touched, 'ruins': made, 'cleansed_age': None, 'order': list(ORDER)}
    religion = result['religion']
    religion.setdefault('corruptions', []).append(record)
    add_religion(result, cfg)
    _reveal(result, god, host, age)
    result['history'].setdefault('operations', []).append(
        {'api_version': API_VERSION, 'kind': 'corruption', 'corruption': index, 'god_id': god['id'],
         'villain_uid': host['uid'], 'encounters': encounters, 'variation': variation})
    return record


def _reveal(result, god, host, age):
    """The known gods stop not speaking of it.

    Before a return there is no trace of the hidden four anywhere; afterwards the known
    pantheon gains it as a rival and its aspects are pushed Wild, which is what makes the
    cure able to become worse than the disease: a Wild god destroys four times as much.
    """
    religion = result['religion']
    rivals = set(hidden_gods_by_id()[god['id']].get('rivals', []))
    for record in religion['gods']:
        if record['id'] == god['id']:
            record['status'] = 'walking'
            record['aspect'] = 'wild'
            record['aspect_name'] = hidden_gods_by_id()[god['id']]['aspects']['wild']
            record['evidence'] = {'villain_uid': host['uid'], 'since_age': age}
        elif record['id'] in rivals and record.get('status') in ('manifest', 'sleeping', 'walking'):
            known = gods_by_id().get(record['id'])
            if known and known.get('aspects', {}).get('wild'):
                record['aspect'] = 'wild'
                record['aspect_name'] = known['aspects']['wild']
            record.setdefault('roused_by', []).append(god['id'])


def corruption_request(body):
    """Stateless: same body, same world out, and the caller's world is never touched."""
    start = perf_counter()
    cfg, encounters, variation, villain_uid = validate_corruption(body)
    world = body['world']
    result = copy.deepcopy({k: v for k, v in world.items() if k != 'build_stages'})
    if 'build_stages' in world:
        result['build_stages'] = list(world['build_stages'])
    STATE_KEYS = state_keys()
    previous_layers = copy.deepcopy(result['layers'])
    previous_state = {k: copy.deepcopy(result.get(k)) for k in STATE_KEYS}

    age = len(result.get('history', {}).get('ages', []))
    index = len(result['religion'].get('corruptions', []))
    candidates = watching(result, encounters)
    host = _host(result, villain_uid)
    acted = None
    if candidates and host is not None:
        god = candidates[0]
        import random
        roll = random.Random(child_seed(cfg.seed, f'corruption-{index}-{god["id"]}-escalation', encounters)).random()
        if roll < chance(god, encounters):
            acted = corrupt(result, cfg, god, host, encounters, variation, index, age)
            _snapshot(result, previous_layers, previous_state, f'Corruption {index + 1}: {god["name"]}', 'corruption')
    result['corruption_api_version'] = API_VERSION
    result.setdefault('timing_ms', {})['corruption_total'] = round((perf_counter() - start) * 1000, 3)
    if acted is None:
        # Nothing is watching, or nothing bit. The world comes back untouched and says so.
        result['corruption'] = {'acted': False, 'encounters': encounters,
                                'watching': [g['id'] for g in candidates],
                                'reason': 'no hidden god is watching yet' if not candidates else
                                          'a watching god did not act this time'}
    else:
        result['corruption'] = {'acted': True, 'encounters': encounters, 'god_id': acted['god_id'],
                                'villain_uid': acted['villain_uid'], 'corruption': acted['index']}
    return result


# --- cleansing, which is also how a god is opposed ------------------------------------

CLEANSE_MAX_DRAIN = 4.    # a node's full intensity, so power 1.0 ends one in a single tick


def validate_cleanse(body):
    from .terrain_history import validate_age_world
    allowed = {'api_version', 'world', 'target', 'power'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError('Expected api_version, world, target and optional power')
    if type(body.get('api_version')) is not int or body['api_version'] != API_VERSION:
        raise ValueError('Unsupported corruption API version')
    world = body.get('world')
    cfg = validate_age_world(world)
    target = body.get('target')
    if not isinstance(target, dict) or len(target) != 1 or not set(target) <= {'corruption', 'god_id'}:
        raise ValueError('target must be {"corruption": <index>} or {"god_id": ...}')
    power = body.get('power', .25)
    if type(power) not in (int, float) or not math.isfinite(power) or not 0 < power <= 1:
        raise ValueError('power must be greater than 0 and at most 1')
    if 'corruption' in target:
        records = world.get('religion', {}).get('corruptions', [])
        index = target['corruption']
        if type(index) is not int or not 0 <= index < len(records):
            raise ValueError('Unknown corruption')
        if records[index].get('cleansed_age') is not None:
            raise ValueError('That corruption is already cleansed')
    else:
        god = next((g for g in world.get('religion', {}).get('gods', []) if g['id'] == target['god_id']), None)
        if god is None:
            raise ValueError('Unknown god')
        if god.get('status') != 'walking':
            raise ValueError('Only a god that walks the world can be opposed')
    return cfg, target, float(power)


def cleanse_request(body):
    """Drive a corrupted node down, or drive a walking god off the plane.

    One mechanic with two names. An avatar is a ley cluster and not a creature, so
    opposing a god is cleansing its nodes; the difference is only that a god has somewhere
    to go back to.

    The structure drains as it ramps rather than merely out-competing, because
    out-competing cannot work: potency saturates at a network's strength, so a corrupted
    node at full intensity sits above what any counter-node of equal strength can reach,
    and the boundary would creep inward in a ring and never take the node's own cell.
    """
    start = perf_counter()
    cfg, target, power = validate_cleanse(body)
    world = body['world']
    result = copy.deepcopy({k: v for k, v in world.items() if k != 'build_stages'})
    if 'build_stages' in world:
        result['build_stages'] = list(world['build_stages'])
    STATE_KEYS = state_keys()
    previous_layers = copy.deepcopy(result['layers'])
    previous_state = {k: copy.deepcopy(result.get(k)) for k in STATE_KEYS}
    age = len(result.get('history', {}).get('ages', []))

    if 'god_id' in target:
        from .terrain_visitation import depart_god
        depart_god(result, cfg, target['god_id'], age, rebuild=True)
        report = {'kind': 'god', 'god_id': target['god_id'], 'departed': True}
        title = 'Opposed: ' + target['god_id']
    else:
        report, title = _drain(result, cfg, target['corruption'], power, age)

    result['history'].setdefault('operations', []).append(
        {'api_version': API_VERSION, 'kind': 'cleanse', 'target': dict(target), 'power': power, **report})
    _snapshot(result, previous_layers, previous_state, title, 'cleanse')
    result['corruption_api_version'] = API_VERSION
    result.setdefault('timing_ms', {})['cleanse_total'] = round((perf_counter() - start) * 1000, 3)
    result['cleanse'] = report
    return result


def _drain(result, cfg, index, power, age):
    from .terrain_history import rebuild_tail
    record = result['religion']['corruptions'][index]
    school = record['school']
    net = result['magic']['networks'][school]
    drain = power * CLEANSE_MAX_DRAIN
    targets = set(record['nodes'])
    # Corrupted clusters are nodes only. If that ever stops being true, removing one by
    # filter would leave every edge endpoint index in this network pointing at the wrong
    # node, which is the same latent trap depart_god carries.
    if any(e['from'] in targets or e['to'] in targets for e in net['edges'] if isinstance(e.get('from'), str)):
        raise ValueError('A corrupted node carries an edge; removal would misindex this network')
    remaining, removed = [], []
    for node in net['nodes']:
        if node['id'] not in targets:
            remaining.append(node)
            continue
        left = round(max(0., node['intensity'] - drain), 9)
        if left <= 0.:
            removed.append(node['id'])
        else:
            remaining.append({**node, 'intensity': left})
    net = copy.deepcopy(net)
    net['nodes'] = remaining
    result['magic']['networks'][school] = net
    record['nodes'] = [n for n in record['nodes'] if n not in removed]

    survivors = list(result['settlements']['sites'])
    for key in ('city_plans', 'hamlet_plans', 'castle_plans', 'world_scene'):
        result.pop(key, None)
    rebuild_tail(result, cfg, survivors, 'cleanse', age, religion=False)

    cleansed = not record['nodes']
    if cleansed:
        record['cleansed_age'] = age
        # The holder is unseated with its last node. Killing the villain would have left
        # the nodes standing and a successor free to take them; this is the other order.
        for person in result.get('villains', {}).get('people', []):
            if person['uid'] == record['villain_uid']:
                person.pop('god', None)
                person['corrupted'] = False
                person['held_nodes'] = [n for n in person.get('held_nodes', []) if n not in removed]
                person.setdefault('log', []).append({'age': age, 'event': 'cleansed', 'god': record['god_id']})
        for god in result['religion']['gods']:
            if god['id'] == record['god_id'] and god.get('status') == 'walking':
                god['status'] = 'sleeping'
                god['evidence'] = {'last_seen': {'cleansed_age': age}}
    return ({'kind': 'corruption', 'corruption': index, 'god_id': record['god_id'],
             'removed': removed, 'remaining': len(record['nodes']), 'cleansed': cleansed},
            f"Cleanse {index + 1}: {record['god_id']}")
