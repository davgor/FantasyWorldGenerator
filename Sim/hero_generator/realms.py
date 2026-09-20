"""Realms: each road-linked culture group of one civilization, ruled from its capital.

The generator already groups cities into cultures; a realm is that group given a name and
a seat. Sovereigns arrive with the cities well; until then `sovereign_uid` is null.
"""
from .history import cities, civilizations, cultures, short_name


def realm_name(culture, capital):
    """The realm's name in its own tongue, falling back to the English form.

    A realm is its seat plus a realm morpheme, so this reads correctly only once capitals
    carry names from the same language; until then the English form in `english_name` is
    the one to show. Both ship, because a map label and a chronicle line want different
    things from the same realm.
    """
    import heritage
    resolved = heritage.resolve(culture['civilization_id'],
                                capital.get('parent_race_id') or 'human')
    return heritage.realm_name(resolved, short_name(capital['name'])) or         f"Realm of {short_name(capital['name'])}"


def build_realms(world):
    by_id = {city['id']: city for city in cities(world)}
    civs = civilizations(world)
    realms = []
    for culture in cultures(world):
        members = [by_id[i] for i in culture['city_ids'] if i in by_id]
        if not members:
            continue
        capital = next((c for c in members if c.get('city_class') == 'capital'), None)
        if capital is None:
            capital = max(members, key=lambda c: (c.get('suitability', 0.), -c['node']))
        civilization = civs.get(culture['civilization_id'], {})
        realms.append({'uid': 'realm-' + culture['id'], 'name': realm_name(culture, capital),
                       'english_name': f"Realm of {short_name(capital['name'])}",
                       'civilization_id': culture['civilization_id'],
                       'civilization_name': civilization.get('name', culture['civilization_id']),
                       'parent_race_id': capital.get('parent_race_id') or civilization.get('parent_race_id'),
                       'capital_uid': capital['uid'], 'city_uids': [c['uid'] for c in members],
                       'culture_id': culture['id'], 'sovereign_uid': None})
    return realms


def realm_by_city(realms):
    return {uid: realm for realm in realms for uid in realm['city_uids']}
