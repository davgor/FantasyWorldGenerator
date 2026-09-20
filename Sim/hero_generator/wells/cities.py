"""The cities well: sovereigns, councils, dynasties, and the leaders a diaspora carries.

A realm's capital may have a sovereign; a founding capital's line is a dynasty. Every
living city seats a council by class (policy `seats`), each seat a candidate. A city
founded by a diaspora carries its leader: a prophet (or heresiarch, while the mother
faith's cities stand) for a schism, an exile for an exile, a founder for an expedition.
"""
from ..history import cities, civilizations, final_age, parent_race, ruins, short_name
from . import chance, roll

SEAT_TITLES = {'magistrate': 'Magistrate', 'commander': 'Commander', 'chaplain': 'Chaplain', 'market_steward': 'Steward',
               'mage': 'Court Mage', 'librarian': 'Archivist'}
DIASPORA_ROLES = {'religious_schism': 'prophet', 'exile': 'exile', 'expedition': 'founder', 'magical_displacement': 'founder'}


def _city_ref(city):
    return {'kind': 'city', 'uid': city['uid'], 'name': city['name']}


def _war_deeds(city):
    return [{'event_kind': 'war', 'event_id': e['war_id'], 'age': e['age'], 'kind': e['kind'],
             'role': 'credited' if e['outcome'] == 'victor' else 'victim', 'opponent_uid': e.get('opponent_uid')}
            for e in city.get('war_history', [])]


def candidates(world, realms, realm_of_city, seed, policy):
    final = final_age(world)
    living = cities(world)
    by_uid = {c['uid']: c for c in living}
    civs = civilizations(world)
    shipments = world.get('humans', {}).get('shipments', [])
    trade = {}
    for s in shipments:
        for key in ('from', 'to'):
            trade[s.get(key)] = trade.get(s.get(key), 0) + 1
    rules = policy['precipitation']
    people, rolls, orgs = [], [], []
    for realm in realms:
        capital = by_uid.get(realm['capital_uid'])
        if capital is None:
            continue
        person = _sovereign(world, capital, realm, by_uid, final)
        if roll(person, 'sovereign', chance(policy, rules['sovereign']['base']), seed, rolls, event_id=capital['uid'], age=final):
            people.append(person)
            realm['sovereign_uid'] = person['uid']
            if capital.get('founding_capital'):
                orgs.append({'uid': 'dynasty-' + capital['uid'], 'kind': 'dynasty', 'name': f"the line of {short_name(capital['name'])}",
                             'home': _city_ref(capital), 'members': [person['uid']], 'charter': {'holds': realm['uid']}})
    for city in living:
        seats = policy['seats'].get(city.get('city_class', 'small'), [])
        members = []
        for seat in seats:
            person = _council(world, city, seat, realm_of_city, by_uid, trade, final)
            value = rules['council']['base'] + (rules['council']['capital_bonus'] if city.get('city_class') == 'capital' else 0.)
            if roll(person, 'council', chance(policy, value), seed, rolls, event_id=city['uid'], age=final):
                people.append(person)
                members.append(person['uid'])
        if members:
            orgs.append({'uid': 'council-' + city['uid'], 'kind': 'council', 'name': f"the council of {short_name(city['name'])}",
                         'home': _city_ref(city), 'members': members, 'charter': {'holds': city['uid']}})
        reason = city.get('diaspora_reason')
        if reason in DIASPORA_ROLES:
            person = _diaspora_leader(world, city, reason, realm_of_city, by_uid, civs, final)
            if roll(person, person['role'], chance(policy, rules['diaspora']['base']), seed, rolls, event_id=person['deeds'][0]['event_id'], age=person['born_age']):
                people.append(person)
    return people, rolls, orgs


def _cold_conflicts(city, by_uid):
    return sum(1 for e in city.get('war_history', []) if e.get('opponent_uid') in by_uid)


def _sovereign(world, capital, realm, by_uid, final):
    members = [by_uid[u] for u in realm['city_uids'] if u in by_uid]
    cold = sum(_cold_conflicts(c, by_uid) for c in members)
    features = {'role:sovereign'}
    if cold:
        features.add('realm:contested')
    if cold >= 2:
        features.add('realm:cold_conflicts_2')
    if capital.get('founding_capital'):
        features.add('dynasty:founding')
    return {'uid': 'hero-sovereign-' + capital['uid'], 'role': 'sovereign', 'well': 'cities',
            'civilization_id': capital['civilization_id'], 'race_id': parent_race(world, capital), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(capital),
            'presence': {'site_kind': 'city', 'uid': capital['uid'], 'situation': 'throne'}, 'realm_uid': realm['uid'],
            'deeds': _war_deeds(capital), 'claim': {'verb': 'hold', 'target_uid': realm['uid'], 'target_name': realm['name']},
            'features': features}


def _council(world, city, seat, realm_of_city, by_uid, trade, final):
    features = {'role:council', 'seat:' + seat}
    if seat == 'market_steward':
        features.add('seat:trade')
        if trade.get(city['id'], 0) >= 2:
            features.add('routes:2')
    realm = realm_of_city.get(city['uid'])
    if _cold_conflicts(city, by_uid):
        features.add('role:schemer')
        if realm and len(realm['city_uids']) >= 2:
            features.add('stakes:2')
    return {'uid': f"hero-council-{city['uid']}-{seat}", 'role': 'council', 'seat': seat, 'well': 'cities',
            'civilization_id': city['civilization_id'], 'race_id': parent_race(world, city), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(city),
            'presence': {'site_kind': 'city', 'uid': city['uid'], 'situation': 'council'},
            'realm_uid': realm['uid'] if realm else None, 'deeds': [],
            'claim': {'verb': 'exploit' if seat == 'market_steward' else 'hold', 'target_uid': city['uid'], 'target_name': city['name']},
            'features': features}


def _diaspora_leader(world, city, reason, realm_of_city, by_uid, civs, final):
    role = DIASPORA_ROLES[reason]
    mother_civ = city.get('source_civilization_id')
    mother_alive = [c for c in by_uid.values() if c['civilization_id'] == mother_civ]
    if role == 'prophet' and mother_alive:
        role = 'heresiarch'
    mother = next((c for c in mother_alive if c.get('city_class') == 'capital'), mother_alive[0] if mother_alive else None)
    born = max(1, city.get('founded_age', 0) or 1)
    features = {'role:' + role}
    realm = realm_of_city.get(city['uid'])
    claim = ({'verb': 'convert', 'target_uid': mother['uid'], 'target_name': mother['name']} if role == 'heresiarch' and mother
             else {'verb': 'protect', 'target_uid': city['uid'], 'target_name': city['name']})
    return {'uid': f"hero-{role}-{city['uid']}", 'role': role, 'well': 'cities', 'diaspora_reason': reason,
            'civilization_id': city['civilization_id'], 'race_id': parent_race(world, city), 'born_age': born,
            'status': 'living' if final - born <= 1 else 'legend', 'home': _city_ref(city) if final - born <= 1 else None,
            'presence': {'site_kind': 'city', 'uid': city['uid'], 'situation': 'pulpit' if role in ('prophet', 'heresiarch') else 'hall'} if final - born <= 1 else None,
            'realm_uid': realm['uid'] if realm and final - born <= 1 else None, 'mother_civilization_id': mother_civ,
            'deeds': [{'event_kind': 'founding', 'event_id': f"founding-{city['node']}", 'age': born, 'role': 'credited', 'reason': reason}],
            'claim': claim, 'features': features}
