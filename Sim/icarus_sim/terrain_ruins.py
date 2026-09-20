"""Ruin legacies: every fallen city leaves a leyline key point. Pure resolution, no world I/O.

The school is chosen by the source of destruction first, the region's dominant magic
second, and the ruined culture's own magic last, so a drowned city seeds a water
line and a dwarven hold eaten by something nameless still leaves an earth scar.
The nest-family table is a code constant mirrored in Core/ages.cpp. A culture's own
school is no longer one: it is the `magic_school` key trait, resolved through the
heritage tables, which is the home the earlier note here pointed at.
"""
from functools import lru_cache

from .terrain_leyline_history import SCHOOLS, dominant_school

NEST_FAMILY_SCHOOL = {'infernal': 'infernal', 'undead': 'umbral', 'aberrant': 'weave', 'fey': 'weave',
                      'holy': 'radiant', 'unholy': 'infernal', 'draconic': 'fire', 'primordial': 'primordial',
                      'fantastic': None}


@lru_cache(maxsize=1)
def culture_schools():
    """Each civilization's own magic school, from its heritage key traits.

    This was a hand-written twelve-row dict here and a second, unsynchronised copy in
    Core/legacy.cpp. Reading it from the heritage layer gives both sides one source: the
    native core takes the same values out of the exported catalogue. The resolved values
    are identical to the table this replaces, which tests/test_heritage_registry_binding.py
    asserts, so the migration moves no world.

    Built once and cached: the registry is already cached behind load_registry, and a
    fallen city asks this question for every ruin in every age.
    """
    from heritage import resolve
    from .civilization_registry import load_registry
    return {key: resolve(key, entity['parent_race_id'])['traits']['magic_school']
            for key, entity in load_registry()['entities'].items()}

CLASS_INTENSITY = {'small': 1.5, 'medium': 2.5, 'capital': 3.5}
SELF_MAGIC_FLOOR = 2.5
DIVINE_INTENSITY = 4.
ELEMENTS = ('fire', 'water', 'earth', 'air')


def source_school(cause, potencies, nest_family=None, victor_culture=None, god_school=None, villain_school=None):
    """The school the destroyer itself leaves behind, or None when it has no magic of its own."""
    if cause in SCHOOLS:
        return cause
    if cause == 'self_magic':
        return 'weave'
    if cause.startswith('divine'):
        return god_school
    # A villain scars the ground with whatever it holds. Holding nothing, it falls
    # through to the region and then the culture, exactly as an unmagical cause does.
    if cause.startswith('villain'):
        return villain_school
    if cause.startswith('war_'):
        return culture_schools().get(victor_culture)
    school = NEST_FAMILY_SCHOOL.get(nest_family)
    if school == 'primordial':
        # Strongest element at the ruin; a dead tie keeps school order.
        return min(ELEMENTS, key=lambda s: (-potencies.get(s, 0.), list(SCHOOLS).index(s)))
    return school


def ruin_legacy(city, cause, potencies, nest_family=None, victor_culture=None, god_school=None, villain_school=None):
    school = source_school(cause, potencies, nest_family, victor_culture, god_school, villain_school)
    basis = 'source'
    if school is None:
        school = dominant_school(potencies)
        basis = 'region'
    if school is None:
        school = culture_schools().get(city.get('population_profile'), 'weave')
        basis = 'culture'
    intensity = CLASS_INTENSITY.get(city.get('city_class'), CLASS_INTENSITY['small'])
    if cause == 'self_magic':
        intensity = max(intensity, SELF_MAGIC_FLOOR)
    if cause.startswith('divine'):
        intensity = DIVINE_INTENSITY
    return {'school': school, 'intensity': intensity, 'basis': basis}
