"""The ruins well: a lost city may leave an heir, a war a remembered victor, a beast kill a Dread.

A person is a named handle on an event the world already recorded. Nothing here invents
an event: the heir points at the ruin, the warlord at the war, the Dread at the nest the
ruin's own evidence names. Whether an event precipitates anyone at all is a seeded roll
against the wells policy, and every roll is returned so the block records what history
*could* have produced and did not. Features are the plain facts an archetype
precondition can test.
"""
from ..history import (BEAST_CAUSES, LONG_LIVED_FAMILIES, cities, final_age, nearest_city, nests, parent_race,
                       radius, ruins, species_from_nest_id, wars)
from . import chance as _chance_of, roll as _roll_once


def _city_ref(city):
    return {'kind': 'city', 'uid': city['uid'], 'name': city['name']}


def _lost_ref(ruin):
    return {'uid': ruin['uid'], 'ruin_id': ruin['id'], 'name': ruin['name'], 'city_class': ruin.get('city_class', 'small'),
            'cause': ruin.get('cause'), 'destroyed_age': ruin['destroyed_age']}


def candidates(world, realm_of_city, seed, policy):
    """People and Dreads from the ruins record, plus the roll ledger, in ruin order for exact replay."""
    final = final_age(world)
    globe = radius(world)
    living = cities(world)
    by_uid = {c['uid']: c for c in living}
    nest_ids = {n['id']: n for n in nests(world)}
    wars_by_defeated = {w['defeated_uid']: w for w in wars(world)}
    lost_per_civilization = {}
    for ruin in ruins(world):
        lost_per_civilization[ruin['civilization_id']] = lost_per_civilization.get(ruin['civilization_id'], 0) + 1
    heirs, warlords, dreads = [], {}, {}
    for ruin in ruins(world):
        age = ruin['destroyed_age']
        heirs.append(_pretender(world, ruin, age, final, globe, living, nest_ids, lost_per_civilization, realm_of_city))
        war = wars_by_defeated.get(ruin['uid'])
        if war is not None:
            _warlord(world, war, ruin, by_uid, warlords, final, lost_per_civilization, realm_of_city)
        if ruin.get('cause') in BEAST_CAUSES:
            _dread(ruin, age, nest_ids, dreads)
    rolls = []
    people = [p for p in heirs if _roll_once(p, 'heir', _heir_chance(policy, p), seed, rolls)]
    if policy['precipitation']['warlord'].get('one_per_city'):
        # A city remembers one warlord: the most recent victor. Earlier victors' wars stay in
        # the city's history and the survivor's deeds; they do not each precipitate a person.
        latest = {}
        for key, person in warlords.items():
            uid = person['victor_uid']
            if uid not in latest or (person['born_age'], key) > (warlords[latest[uid]]['born_age'], latest[uid]):
                latest[uid] = key
        warlords = {k: warlords[k] for k in sorted(latest.values())}
    people += [warlords[k] for k in sorted(warlords) if _roll_once(warlords[k], 'warlord', _warlord_chance(policy, warlords[k]), seed, rolls)]
    kept_dreads = [dreads[k] for k in sorted(dreads) if _roll_once(dreads[k], 'dread', _dread_chance(policy, dreads[k]), seed, rolls)]
    return people, kept_dreads, rolls


def _chance(policy, value):
    return _chance_of(policy, value)


def _heir_chance(policy, person):
    rule = policy['precipitation']['heir']
    return _chance(policy, rule['base'] + rule['per_city_class'].get(person['lost']['city_class'], 0.))


def _warlord_chance(policy, person):
    rule = policy['precipitation']['warlord']
    kinds = [d['kind'] for d in person['deeds']]
    return _chance(policy, rule['base'] + max(rule['per_war_kind'].get(k, 0.) for k in kinds) + rule['per_extra_war'] * (len(kinds) - 1))


def _dread_chance(policy, dread):
    rule = policy['precipitation']['dread']
    return _chance(policy, rule['base'] + rule['per_nest_tier'] * dread['nest_tier'])


def _war_deeds(ruin):
    deeds = []
    for entry in ruin.get('war_history', []):
        deeds.append({'event_kind': 'war', 'event_id': entry['war_id'], 'age': entry['age'],
                      'role': 'credited' if entry['outcome'] == 'victor' else 'victim', 'kind': entry['kind'],
                      'opponent_uid': entry.get('opponent_uid')})
    return deeds


def _pretender(world, ruin, age, final, globe, living, nest_ids, lost_per_civilization, realm_of_city):
    same = [c for c in living if c['population_profile'] == ruin['population_profile']]
    home = nearest_city(ruin, same, globe)
    alive = home is not None and final - age <= 1
    war_deeds = _war_deeds(ruin)
    outcomes = {d['role'] for d in war_deeds}
    features = {'role:pretender', 'home:fell', 'stake:lost', 'heir:' + ruin.get('city_class', 'small')}
    if {'credited', 'victim'} <= outcomes:
        features.add('sides:both')
    if lost_per_civilization.get(ruin['civilization_id'], 0) >= 2:
        features.add('civ:lost_many')
    evidence = ruin.get('evidence') or {}
    if ruin.get('cause') in BEAST_CAUSES and evidence.get('nest_id') in nest_ids:
        features.add('dread:living')
    return {'uid': 'hero-pretender-' + ruin['uid'], 'role': 'pretender', 'well': 'ruins',
            'civilization_id': ruin['civilization_id'], 'race_id': parent_race(world, ruin), 'born_age': age,
            'status': 'living' if alive else 'legend', 'home': _city_ref(home) if alive else None,
            'presence': {'site_kind': 'city', 'uid': home['uid'], 'situation': 'court'} if alive else None,
            'realm_uid': realm_of_city.get(home['uid'], {}).get('uid') if alive else None,
            'lost': _lost_ref(ruin),
            'deeds': [{'event_kind': 'ruin', 'event_id': ruin['id'], 'age': age, 'role': 'heir'}] + war_deeds,
            'claim': {'verb': 'retake', 'target_uid': ruin['uid'], 'target_name': ruin['name']},
            'features': features}


def _warlord(world, war, ruin, by_uid, warlords, final, lost_per_civilization, realm_of_city):
    victor_uid = war['victor_uid']
    key = f"{war['age']}-{victor_uid}"
    home = by_uid.get(victor_uid)
    if key not in warlords:
        alive = home is not None and final - war['age'] <= 1
        features = {'role:warlord', 'war:' + war['kind'] + '_victor'}
        if home is None:
            features.add('home:fell_later')
        if home is not None and _realm_contested(home, by_uid, realm_of_city):
            features.add('realm:contested')
        if lost_per_civilization.get(war['victor_civilization_id'], 0) >= 2:
            features.add('civ:lost_many')
        if home is not None and {'victor', 'defeated'} <= {e['outcome'] for e in home.get('war_history', [])}:
            features.add('sides:both')
        victor_name = home['name'] if home else _ruin_name(world, victor_uid)
        warlords[key] = {'uid': 'hero-warlord-' + key, 'role': 'warlord', 'well': 'ruins',
                         'civilization_id': war['victor_civilization_id'],
                         'race_id': war.get('victor_parent_race_id') or parent_race(world, home or ruin),
                         'born_age': war['age'], 'status': 'living' if alive else 'legend',
                         'home': _city_ref(home) if alive else None,
                         'presence': {'site_kind': 'city', 'uid': home['uid'], 'situation': 'command'} if alive else None,
                         'realm_uid': realm_of_city.get(home['uid'], {}).get('uid') if alive else None,
                         'victor_uid': victor_uid, 'victor_name': victor_name, 'victor_fell': home is None,
                         'deeds': [], 'claim': {'verb': 'hold', 'target_uid': victor_uid, 'target_name': victor_name},
                         'features': features, 'defeated': []}
    person = warlords[key]
    person['deeds'].append({'event_kind': 'war', 'event_id': war['id'], 'age': war['age'], 'role': 'credited',
                            'kind': war['kind'], 'defeated_uid': ruin['uid'], 'defeated_name': ruin['name'],
                            'defeated_class': ruin.get('city_class', 'small')})
    person['defeated'].append({'uid': ruin['uid'], 'name': ruin['name'], 'war_id': war['id'], 'kind': war['kind']})


def _ruin_name(world, uid):
    return next((r['name'] for r in ruins(world) if r['uid'] == uid), uid)


def _realm_contested(home, by_uid, realm_of_city):
    """A realm is contested while any of its cities has a living former opponent."""
    realm = realm_of_city.get(home['uid'])
    members = [by_uid[u] for u in realm['city_uids'] if u in by_uid] if realm else [home]
    return any(entry.get('opponent_uid') in by_uid for city in members for entry in city.get('war_history', []))


def _dread(ruin, age, nest_ids, dreads):
    evidence = ruin.get('evidence') or {}
    nest_id = evidence.get('nest_id')
    if not nest_id:
        return
    nest = nest_ids.get(nest_id)
    dread = dreads.setdefault(nest_id, {
        'uid': 'dread-' + nest_id, 'role': 'dread', 'well': 'ruins', 'nest_id': nest_id,
        'species': nest['name'] if nest else species_from_nest_id(nest_id),
        'family': nest.get('family') if nest else None, 'nest_tier': nest.get('tier', 5) if nest else 5,
        'status': 'living' if nest else 'legend',
        'presence': {'site_kind': 'nest', 'uid': nest_id, 'situation': 'lair'} if nest else None,
        'deeds': [], 'destroyed': [], 'features': {'role:dread'}})
    dread['deeds'].append({'event_kind': 'ruin', 'event_id': ruin['id'], 'age': age, 'role': 'actual',
                           'cause': ruin.get('cause'), 'city_name': ruin['name'], 'city_class': ruin.get('city_class', 'small')})
    dread['destroyed'].append({'uid': ruin['uid'], 'name': ruin['name'], 'age': age})
    if dread['family'] in LONG_LIVED_FAMILIES:
        dread['features'].add('dread:long_lived')
    if len({d['age'] for d in dread['deeds']}) >= 2:
        dread['features'].add('dread:ages_2')
