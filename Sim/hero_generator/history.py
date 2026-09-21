"""Read the finished world's story: ruins, wars, survivors, nests and the peoples.

Every function here is a pure read of the world JSON. Nothing is written back, and only
documented export fields are consulted, so a saved ``world.json`` serves as well as a
live result.
"""
import math

CAUSE_PHRASES = {'dragon': 'a dragon', 'monster': 'a monster', 'self_magic': 'its own magic'}
BEAST_CAUSES = ('dragon', 'monster')
LONG_LIVED_FAMILIES = ('draconic', 'undead', 'aberrant')


def world_seed(world):
    return int(world['config']['seed'])


def ages(world):
    return world.get('history', {}).get('ages', [])


def final_age(world):
    return len(ages(world))


def ruins(world):
    return world.get('ruins', [])


def wars(world):
    return [war for age in ages(world) for war in age.get('wars', [])]


def cities(world):
    return world.get('settlements', {}).get('sites', [])


def nests(world):
    return world.get('beast_nests', {}).get('sites', [])


def civilizations(world):
    return {entity['id']: entity for entity in world.get('civilizations', {}).get('entities', [])}


def cultures(world):
    return world.get('humans', {}).get('cultures', [])


def radius(world):
    return float(world.get('effective_config', {}).get('globe_radius', 1.))


def separation(a, b, globe_radius):
    """Surface metres between two placed records, the same arc the war module measures."""
    dot = sum(x * y for x, y in zip(a['direction'], b['direction']))
    return globe_radius * math.acos(max(-1., min(1., dot)))


def nearest_city(target, candidates, globe_radius):
    """Closest candidate to `target`, ties broken by uid so the answer never depends on order."""
    best = None
    for city in candidates:
        key = (separation(target, city, globe_radius), city['uid'])
        if best is None or key < best[0]:
            best = (key, city)
    return best[1] if best else None


def short_name(name):
    """Cuts a ` City` the live generator never writes; see CONTENT-CITY-SUFFIX-DEAD-READERS.

    `heritage.settlement_name` replaced the round-robin that appended ` City`, so on any
    generated world this is the identity. It still fires on the synthetic worlds in
    `tests/test_hero_generator.py` and on `Fixtures/hero-generator-v1.json`, both of which
    name their cities in the retired convention, so removing the strip renames every
    derived string there. That is why it is still here: the removal is a fixture change,
    not a one-line change, and it is tracked on
    board/backlog/CONTENT-CITY-SUFFIX-DEAD-READERS.md.
    """
    return name.replace(' City', '')


def civilization_name(world, civilization_id):
    entity = civilizations(world).get(civilization_id)
    return entity['name'] if entity else civilization_id


def parent_race(world, record):
    entity = civilizations(world).get(record.get('population_profile'))
    return record.get('parent_race_id') or (entity or {}).get('parent_race_id') or 'human'


def cause_kind(ruin):
    cause = ruin.get('cause', '')
    if cause.startswith('war_'):
        return 'war'
    if cause in BEAST_CAUSES:
        return 'beast'
    if cause == 'self_magic':
        return 'self_magic'
    return 'ley'


def cause_phrase(ruin):
    cause = ruin.get('cause', '')
    if cause.startswith('war_'):
        return f'the {cause[4:]} war'
    article = 'an' if cause[:1] in 'aeiou' else 'a'
    return CAUSE_PHRASES.get(cause, f'{article} {cause} leyline surge')


def species_from_nest_id(nest_id):
    """`nest-abyssal-choir-worms-156` names its species even when the nest itself is gone."""
    parts = nest_id.split('-')
    if len(parts) > 2 and parts[0] == 'nest':
        parts = parts[1:-1]
    return ' '.join(parts).capitalize()
