"""The shrines well: a shrine keeps a keeper, a cult in a ruin keeps a heresiarch.

Religion sites are born of ruins: a shrine to the god whose field the city fell to, or a
cult that took root where a city died under a surge. The keeper tends the shrine and
holds it; the heresiarch preaches the cult's god at the nearest living city. Both are
named handles on a site the religion pass already recorded, and both roll like everything
else. A keeper without a living city of the ruin's people nearby stands at the shrine
with no home; that is a fact for the orchestrator, not a reason to invent one.
"""
from ..history import cities, final_age, nearest_city, parent_race, radius, ruins, short_name
from . import chance, roll

SITE_ROLES = {'shrine': 'keeper', 'cult': 'heresiarch'}


def _city_ref(city):
    return {'kind': 'city', 'uid': city['uid'], 'name': city['name']}


def shrine_name(site, god, ruin):
    god_name = (god or {}).get('name') or site.get('god_id', 'a nameless god').replace('god_', '').replace('_', ' ')
    where = short_name(ruin['name']) if ruin else site.get('id')
    return f"the {'cult' if site.get('kind') == 'cult' else 'shrine'} of {god_name} at {where}"


def candidates(world, realm_of_city, seed, policy):
    final = final_age(world)
    religion = world.get('religion') or {}
    gods = {g.get('id'): g for g in religion.get('gods') or []}
    ruins_by_id = {r['id']: r for r in ruins(world)}
    living = cities(world)
    globe = radius(world)
    rules = policy['precipitation']
    people, rolls = [], []
    for site in religion.get('sites') or []:
        role = SITE_ROLES.get(site.get('kind'))
        if role is None or 'id' not in site:
            continue
        ruin = ruins_by_id.get(site.get('ruin_id'))
        if ruin is None:
            continue
        same = [c for c in living if c.get('population_profile') == ruin.get('population_profile')]
        home = nearest_city(ruin, same, globe) if same and 'direction' in ruin else None
        person = _keeper(world, site, role, ruin, gods.get(site.get('god_id')), home, realm_of_city, final, living, globe)
        value = rules[role if role == 'keeper' else 'cult']['base']
        if roll(person, role if role == 'keeper' else 'cult', chance(policy, value), seed, rolls):
            people.append(person)
    return people, rolls


def _keeper(world, site, role, ruin, god, home, realm_of_city, final, living, globe):
    name = shrine_name(site, god, ruin)
    features = {'role:' + role, 'shrine:' + ('cult' if role == 'heresiarch' else 'ruin')}
    if site.get('born_under_surge'):
        features.add('school:dark')
    target = nearest_city(ruin, living, globe) if role == 'heresiarch' and living and 'direction' in ruin else None
    claim = ({'verb': 'convert', 'target_uid': target['uid'], 'target_name': target['name']} if target
             else {'verb': 'hold', 'target_uid': site['id'], 'target_name': name})
    return {'uid': f"hero-{role}-{site['id']}", 'role': role, 'well': 'shrines',
            'civilization_id': ruin['civilization_id'], 'race_id': parent_race(world, ruin), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(home) if home else None, 'site_name': name, 'god_id': site.get('god_id'),
            'presence': {'site_kind': 'shrine', 'uid': site['id'], 'situation': 'cult' if role == 'heresiarch' else 'altar'},
            'realm_uid': (realm_of_city.get(home['uid']) or {}).get('uid') if home else None,
            'deeds': [{'event_kind': 'shrine', 'event_id': site['id'], 'age': max(1, final), 'role': 'keeper', 'reason': site.get('kind')}],
            'claim': claim, 'features': features}
