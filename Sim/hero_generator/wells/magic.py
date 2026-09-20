"""The magic well: key points keep wardens, dead colleges leave masters, living colleges have heads.

Every ruin seeds a leyline key point (`<ruin id>-key` in the school the legacy chose). A
person may take it up: the Domain-holder. A city that destroyed itself in a magical
experiment leaves a surviving master of its college: a Magister with no college. A living
college has a head. Which of these precipitate is a seeded roll like every other well.
"""
from ..history import cities, final_age, parent_race, ruins, short_name
from . import chance, roll

DEED_KEEPER = 'keeper'


def candidates(world, realm_of_city, seed, policy):
    final = final_age(world)
    magic = world.get('magic') or {}
    networks = magic.get('networks') or {}
    nodes = {n['id']: (school, n) for school, net in networks.items() for n in net.get('nodes', [])}
    dark = set(policy['magic']['dark_schools'])
    rules = policy['precipitation']
    people, rolls = [], []
    for ruin in ruins(world):
        key_id = ruin['id'] + '-key'
        if key_id in nodes:
            school, node = nodes[key_id]
            person = _domain_holder(world, ruin, school, node, final, dark)
            if roll(person, 'domain_holder', chance(policy, rules['domain_holder']['base'] + rules['domain_holder']['per_intensity'] * node.get('intensity', 0.)), seed, rolls):
                people.append(person)
        if ruin.get('cause') == 'self_magic':
            person = _ruin_magister(world, ruin, ruin.get('new_node_school') or 'weave', key_id if key_id in nodes else None, final, dark)
            if roll(person, 'magister', chance(policy, rules['magister']['base']), seed, rolls):
                people.append(person)
    by_id = {c['id']: c for c in cities(world)}
    for college in magic.get('colleges') or []:
        home = by_id.get(college.get('core_id'))
        if home is None:
            continue
        person = _college_magister(world, college, home, _dominant_school(world, college), final, dark, realm_of_city)
        if roll(person, 'college_magister', chance(policy, rules['college_magister']['base']), seed, rolls, event_id=college['id'], age=final):
            people.append(person)
    return people, rolls


def _dominant_school(world, college):
    layers = world.get('layers') or {}
    best, best_value = 'weave', -1.
    for key in sorted(layers):
        if key.startswith('ley_') and key not in ('ley_holy', 'ley_primordial'):
            try:
                value = layers[key][college['z']][college['x']]
            except (IndexError, KeyError, TypeError):
                continue
            if value > best_value:
                best, best_value = key[4:], value
    return best


def _lost(ruin):
    return {'uid': ruin['uid'], 'ruin_id': ruin['id'], 'name': ruin['name'], 'city_class': ruin.get('city_class', 'small'),
            'cause': ruin.get('cause'), 'destroyed_age': ruin['destroyed_age']}


def _domain_holder(world, ruin, school, node, final, dark):
    age = ruin['destroyed_age']
    alive = final - age <= 1
    features = {'role:domain_holder', 'keypoint:ruin_born', 'seat:none'}
    if school in dark:
        features.add('school:dark')
    return {'uid': 'hero-domain-' + ruin['uid'], 'role': 'domain_holder', 'well': 'magic',
            'civilization_id': ruin['civilization_id'], 'race_id': parent_race(world, ruin), 'born_age': age,
            'status': 'living' if alive else 'legend', 'home': None,
            'presence': {'site_kind': 'ruin', 'uid': ruin['uid'], 'situation': 'warding'} if alive else None,
            'realm_uid': None, 'lost': _lost(ruin), 'school': school, 'node_id': node['id'],
            'deeds': [{'event_kind': 'ruin', 'event_id': ruin['id'], 'age': age, 'role': DEED_KEEPER}],
            'claim': {'verb': 'hold', 'target_uid': node['id'], 'target_name': f"the {school} key point at {short_name(ruin['name'])}"},
            'features': features}


def _ruin_magister(world, ruin, school, key_id, final, dark):
    age = ruin['destroyed_age']
    features = {'role:magister', 'college:destroyed', 'stake:lost'}
    if school in dark:
        features.add('school:dark')
    return {'uid': 'hero-magister-' + ruin['uid'], 'role': 'magister', 'well': 'magic',
            'civilization_id': ruin['civilization_id'], 'race_id': parent_race(world, ruin), 'born_age': age,
            'status': 'living' if final - age <= 1 else 'legend', 'home': None, 'presence': None, 'realm_uid': None,
            'dispossessed': True, 'lost': _lost(ruin), 'school': school, 'node_id': key_id,
            'deeds': [{'event_kind': 'ruin', 'event_id': ruin['id'], 'age': age, 'role': 'actual'}],
            'claim': {'verb': 'exploit', 'target_uid': key_id or ruin['uid'],
                      'target_name': f"the {school} key point at {short_name(ruin['name'])}" if key_id else ruin['name']},
            'features': features}


def _college_magister(world, college, home, school, final, dark, realm_of_city):
    features = {'role:magister', 'seat:college'}
    if school in dark:
        features.add('school:dark')
    return {'uid': 'hero-magister-' + college['id'], 'role': 'magister', 'well': 'magic',
            'civilization_id': home['civilization_id'], 'race_id': parent_race(world, home), 'born_age': max(1, final),
            'status': 'living', 'home': {'kind': 'city', 'uid': home['uid'], 'name': home['name']},
            'presence': {'site_kind': 'college', 'uid': college['id'], 'situation': 'teaching'},
            'realm_uid': realm_of_city.get(home['uid'], {}).get('uid'), 'school': school, 'node_id': None,
            'college': {'id': college['id'], 'node': college['node'], 'x': college['x'], 'z': college['z']},
            'deeds': [],
            'claim': {'verb': 'hold', 'target_uid': college['id'], 'target_name': f"the college near {short_name(home['name'])}"},
            'features': features}
