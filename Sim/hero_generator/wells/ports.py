"""The ports well: every harbour may have a harbourmaster.

A port is where the shipments the economy diagnostics already count actually land; the
harbourmaster holds a trade seat by construction (`seat:trade`), and a terminal that two
or more sea routes touch gives them `routes:2`. Rolled like everything else.
"""
from ..history import cities, final_age, parent_race, short_name
from . import chance, roll


def _city_ref(city):
    return {'kind': 'city', 'uid': city['uid'], 'name': city['name']}


def port_name(port, city):
    return f"the harbour of {short_name(city['name'])}"


def _route_touches(route, port):
    ends = {route.get('from'), route.get('to'), route.get('from_id'), route.get('to_id'), route.get('from_node'), route.get('to_node')}
    return port.get('id') in ends or port.get('node') in ends or port.get('sea_node') in ends


def candidates(world, realm_of_city, seed, policy):
    final = final_age(world)
    by_id = {c['id']: c for c in cities(world) if 'id' in c}
    routes = [r for r in ((world.get('transport') or {}).get('routes') or []) if isinstance(r, dict) and r.get('mode') == 'sea']
    rules = policy['precipitation']['harbourmaster']
    people, rolls = [], []
    for port in ((world.get('fisheries') or {}).get('ports') or []):
        city = by_id.get(port.get('core_id'))
        if city is None or 'id' not in port:
            continue
        touching = sum(1 for r in routes if _route_touches(r, port))
        person = _harbourmaster(world, port, city, realm_of_city, final, touching)
        value = rules['base'] + rules['per_route'] * touching + (rules['terminal_bonus'] if port.get('trade_terminal') else 0.)
        if roll(person, 'harbourmaster', chance(policy, value), seed, rolls):
            people.append(person)
    return people, rolls


def _harbourmaster(world, port, city, realm_of_city, final, touching):
    name = port_name(port, city)
    features = {'role:harbourmaster', 'seat:trade'}
    if touching >= 2 or (port.get('trade_terminal') and touching >= 1):
        features.add('routes:2')
    if port.get('trade_terminal'):
        features.add('port:terminal')
    return {'uid': 'hero-harbourmaster-' + port['id'], 'role': 'harbourmaster', 'well': 'ports',
            'civilization_id': city['civilization_id'], 'race_id': parent_race(world, city), 'born_age': max(1, final),
            'status': 'living', 'home': _city_ref(city), 'site_name': name, 'routes': touching,
            'presence': {'site_kind': 'port', 'uid': port['id'], 'situation': 'quay'},
            'realm_uid': (realm_of_city.get(city['uid']) or {}).get('uid'),
            'deeds': [{'event_kind': 'port', 'event_id': port['id'], 'age': max(1, final), 'role': 'keeper'}],
            'claim': {'verb': 'exploit', 'target_uid': port['id'], 'target_name': name},
            'features': features}
