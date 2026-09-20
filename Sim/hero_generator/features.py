"""Cross-cutting features: facts about a person that only exist once the whole cast is known.

Wells see one record at a time. Some archetype preconditions are relations between
people or between a person and the ground: a councillor who outranks their sovereign, a
home on tainted ley ground, a legend with a living successor, a heir whose people founded
again. These are computed here, after precipitation and placement, before archetypes.
"""
from .history import cities, final_age, ruins

SEATED = ('sovereign', 'warlord')


def _civilization_of(uid, cities_by_uid, ruins_by_uid):
    site = cities_by_uid.get(uid) or ruins_by_uid.get(uid)
    return site['civilization_id'] if site else None


def apply(world, people, policy):
    final = final_age(world)
    cities_by_uid = {c['uid']: c for c in cities(world)}
    ruins_by_uid = {r['uid']: r for r in ruins(world)}
    layers = world.get('layers') or {}
    threshold = policy['features']['tainted_threshold']
    living = [p for p in people if p['status'] == 'living']
    by_realm = {}
    for p in living:
        by_realm.setdefault(p.get('realm_uid'), []).append(p)
    latest_founding = {}
    for c in cities_by_uid.values():
        civ = c['civilization_id']
        latest_founding[civ] = max(latest_founding.get(civ, 0), c.get('founded_age', 0))
    camp_leaders_by_civ = {p['civilization_id'] for p in living if (p.get('presence') or {}).get('situation') == 'leader'}
    warlord_cities = {p.get('victor_uid') for p in people if p['role'] == 'warlord'}
    for person in people:
        f = person['features']
        home = cities_by_uid.get((person.get('home') or {}).get('uid'))
        if home is not None:
            for school in ('ley_umbral', 'ley_infernal'):
                try:
                    if layers[school][home['z']][home['x']] > threshold:
                        f.add('ley:tainted_home')
                except (KeyError, IndexError, TypeError):
                    pass
        opponents = {_civilization_of(d.get('opponent_uid'), cities_by_uid, ruins_by_uid) for d in person['deeds'] if d.get('opponent_uid')}
        if len(opponents - {None}) >= 2:
            f.add('deeds:two_civilizations')
        if person['role'] == 'pretender' and person['born_age'] < final and latest_founding.get(person['civilization_id'], 0) > person['born_age']:
            f |= {'villain:prior_age', 'stake:regained'}
        if person['role'] in SEATED and person['civilization_id'] in camp_leaders_by_civ:
            f.add('rival:spared')
        if person['role'] == 'champion' and (person.get('home') or {}).get('uid') in warlord_cities:
            f.add('deed:credited_not_actual')
        if person['role'] not in ('sovereign', 'council', 'warlord') and person['status'] == 'living':
            f.add('seat:none')
        if 'legend:predecessor' in f and person['role'] == 'pretender':
            f.add('heir:unclaimed')
    for realm_uid, members in by_realm.items():
        sovereign = next((p for p in members if p['role'] == 'sovereign'), None)
        if sovereign is None:
            continue
        for p in members:
            if p['role'] == 'council' and p['fame'] > sovereign['fame']:
                p['features'].add('council:outranks_sovereign')
                sovereign['features'].add('sovereign:advised')
    for person in living:
        if person['tier'] in ('renowned', 'legendary') and any(
                q['status'] == 'living' and q is not person and q['civilization_id'] == person['civilization_id'] and q['born_age'] > person['born_age']
                for q in people):
            person['features'].add('mentor:successor')
    return people


def tyrant_realms(people):
    """After the seated pass: the realms (by civilization) whose sovereign or warlord is a Tyrant."""
    return {p['civilization_id'] for p in people if p['role'] in SEATED and p.get('archetype') == 'tyrant'}


def mark_rebels(people, tyrants):
    for person in people:
        if person.get('archetype') is None and person['civilization_id'] in tyrants and 'seat:none' in person['features']:
            person['features'].add('realm:tyrant')
