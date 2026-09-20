"""The guilds well: every guild hall is an Order, and an Order under threat has a Champion.

A living city within reach of a dangerous nest holds its line: the Order's charter is
against that nest's family and its Champion is credited with the holding. A city a beast
destroyed had a Champion too, one who failed; the Order survives as a Remnant, and the
Champion is dispossessed. Both are rolled like everything else.
"""
from ..history import BEAST_CAUSES, LONG_LIVED_FAMILIES, cities, final_age, nests, parent_race, ruins, separation, short_name
from . import chance, roll

DARK_FAMILIES = ('infernal', 'undead', 'aberrant')


def _city_ref(city):
    return {'kind': 'city', 'uid': city['uid'], 'name': city['name']}


def _dangerous(nest):
    return 'dragon' in nest.get('name', '').lower() or nest.get('family') in DARK_FAMILIES or nest.get('family') == 'draconic'


def _nearest_threat(site, dangerous, globe):
    """The closest dangerous nest in surface metres, ties by id."""
    best = None
    for nest in dangerous:
        key = (separation(site, nest, globe), nest['id'])
        if best is None or key < best[0]:
            best = (key, nest)
    return (best[1], best[0][0]) if best else (None, None)


def candidates(world, realm_of_city, seed, policy, globe):
    final = final_age(world)
    dangerous = [n for n in nests(world) if _dangerous(n)]
    rules = policy['precipitation']['champion']
    people, rolls, orgs = [], [], []
    for city in cities(world):
        nest, distance = _nearest_threat(city, dangerous, globe)
        if nest is None or distance > rules['reach_factor'] * nest.get('range_m', 1000.):
            continue
        person = _champion(world, city, nest, realm_of_city, final)
        orgs.append(_order(city, nest, 'order'))
        if roll(person, 'champion', chance(policy, rules['base'] + rules['per_nest_tier'] * nest.get('tier', 1)), seed, rolls,
                event_id=nest['id'], age=final):
            people.append(person)
            orgs[-1]['members'].append(person['uid'])
    nest_ids = {n['id']: n for n in nests(world)}
    for ruin in ruins(world):
        if ruin.get('cause') not in BEAST_CAUSES:
            continue
        evidence = ruin.get('evidence') or {}
        nest = nest_ids.get(evidence.get('nest_id'))
        person = _fallen_champion(world, ruin, nest, evidence.get('nest_id'), final)
        orgs.append(_order(ruin, nest or {'family': 'beast', 'name': 'the beast'}, 'remnant'))
        if roll(person, 'champion', chance(policy, rules['base'] + rules['per_nest_tier'] * (nest.get('tier', 5) if nest else 5)), seed, rolls):
            people.append(person)
            orgs[-1]['members'].append(person['uid'])
    return people, rolls, orgs


def _order(site, nest, kind):
    family = nest.get('family') or 'beast'
    return {'uid': f"{kind}-{site['uid']}", 'kind': kind, 'name': f"the Order of {short_name(site['name'])}",
            'home': {'kind': 'city' if kind == 'order' else 'ruin', 'uid': site['uid'], 'name': site['name']},
            'members': [], 'charter': {'against': family, 'nest_id': nest.get('id')}}


def _champion(world, city, nest, realm_of_city, final):
    dark = nest.get('family') in DARK_FAMILIES
    features = {'role:champion', 'order:member', 'warden:post'}
    if dark:
        features |= {'order:against_dark', 'deed:dark_nest'}
    realm = realm_of_city.get(city['uid'])
    return {'uid': 'hero-champion-' + city['uid'], 'role': 'champion', 'well': 'guilds',
            'civilization_id': city['civilization_id'], 'race_id': parent_race(world, city), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(city),
            'presence': {'site_kind': 'city', 'uid': city['uid'], 'situation': 'guildhall'},
            'realm_uid': realm['uid'] if realm else None, 'nest_id': nest['id'], 'nest_name': nest['name'],
            'deeds': [{'event_kind': 'nest', 'event_id': nest['id'], 'age': max(1, final), 'role': 'credited', 'tier': nest.get('tier', 1)}],
            'claim': {'verb': 'kill', 'target_uid': nest['id'], 'target_name': f"the {nest['name'].lower()} near {short_name(city['name'])}"},
            'features': features}


def _fallen_champion(world, ruin, nest, nest_id, final):
    age = ruin['destroyed_age']
    features = {'role:champion', 'order:member', 'order:remnant', 'defence:failed', 'stake:lost'}
    if nest is not None:
        features.add('dread:failed_against')
    if nest is not None and nest.get('family') in DARK_FAMILIES:
        features |= {'order:against_dark', 'deed:dark_nest'}
    name = nest['name'] if nest else 'the beast'
    return {'uid': 'hero-champion-' + ruin['uid'], 'role': 'champion', 'well': 'guilds',
            'civilization_id': ruin['civilization_id'], 'race_id': parent_race(world, ruin), 'born_age': age,
            'status': 'living' if final - age <= 1 else 'legend', 'home': None, 'presence': None, 'realm_uid': None,
            'dispossessed': True, 'lost': {'uid': ruin['uid'], 'ruin_id': ruin['id'], 'name': ruin['name'],
                                           'city_class': ruin.get('city_class', 'small'), 'cause': ruin.get('cause'), 'destroyed_age': age},
            'nest_id': nest_id, 'nest_name': name,
            'deeds': [{'event_kind': 'ruin', 'event_id': ruin['id'], 'age': age, 'role': 'credited', 'tier': nest.get('tier', 5) if nest else 5}],
            'claim': {'verb': 'kill', 'target_uid': nest_id or ruin['uid'], 'target_name': f"{name.lower()}, the doom of {short_name(ruin['name'])}"},
            'features': features}
