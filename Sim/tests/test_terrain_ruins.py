"""Every ruin leaves a leyline key point: source of destruction, then region, then culture.

The age-transition half (nodes actually added, hamlets removed) joins these once
terrain_history.py is free; this file covers the pure resolution rule.
"""
import unittest

from icarus_sim.terrain_ruins import ruin_legacy, culture_schools, NEST_FAMILY_SCHOOL, CLASS_INTENSITY
from icarus_sim.terrain_leyline_history import SCHOOLS
from icarus_sim.terrain_profiles import civilization_ids


def city(profile='human_heartland', city_class='small'):
    return {'uid': 'city', 'population_profile': profile, 'city_class': city_class}


def potencies(**values):
    return {school: values.get(school, 0.) for school in SCHOOLS}


class RuinLegacyTests(unittest.TestCase):
    def test_tables_cover_every_civilization_and_family_with_real_schools(self):
        self.assertEqual(set(culture_schools()), set(civilization_ids()))
        self.assertTrue(all(v in SCHOOLS for v in culture_schools().values()))
        for family, school in NEST_FAMILY_SCHOOL.items():
            self.assertTrue(school is None or school == 'primordial' or school in SCHOOLS, family)
        self.assertEqual(CLASS_INTENSITY, {'small': 1.5, 'medium': 2.5, 'capital': 3.5})

    def test_source_of_destruction_wins(self):
        self.assertEqual(ruin_legacy(city(), 'water', potencies(fire=1.)), {'school': 'water', 'intensity': 1.5, 'basis': 'source'})
        self.assertEqual(ruin_legacy(city(), 'self_magic', potencies())['school'], 'weave')
        self.assertEqual(ruin_legacy(city(), 'monster', potencies(), nest_family='undead')['school'], 'umbral')
        self.assertEqual(ruin_legacy(city(), 'monster', potencies(), nest_family='holy')['school'], 'radiant')
        self.assertEqual(ruin_legacy(city(), 'dragon', potencies(), nest_family='draconic')['school'], 'fire')
        self.assertEqual(ruin_legacy(city(), 'war_civil', potencies(), victor_culture='tidekin')['school'], 'water')
        self.assertEqual(ruin_legacy(city(), 'divine_god_air', potencies(), god_school='air'),
                         {'school': 'air', 'intensity': 4., 'basis': 'source'})

    def test_primordial_nest_takes_the_strongest_element_at_the_ruin(self):
        legacy = ruin_legacy(city(), 'monster', potencies(earth=.4, water=.9, weave=2.), nest_family='primordial')
        self.assertEqual((legacy['school'], legacy['basis']), ('water', 'source'))
        tie = ruin_legacy(city(), 'monster', potencies(), nest_family='primordial')
        self.assertEqual(tie['school'], 'fire', 'a dead tie falls back to school order')

    def test_region_then_culture(self):
        region = ruin_legacy(city('dwarf'), 'monster', potencies(umbral=.8, fire=.1), nest_family='fantastic')
        self.assertEqual((region['school'], region['basis']), ('umbral', 'region'))
        contested = ruin_legacy(city('dwarf'), 'monster', potencies(umbral=.8, fire=.78), nest_family='fantastic')
        self.assertEqual((contested['school'], contested['basis']), ('earth', 'culture'))
        unknown = ruin_legacy(city('elf'), 'monster', potencies(), nest_family=None)
        self.assertEqual((unknown['school'], unknown['basis']), ('weave', 'culture'))
        war = ruin_legacy(city('gnome'), 'war_regional', potencies(), victor_culture=None)
        self.assertEqual((war['school'], war['basis']), ('weave', 'culture'))

    def test_intensity_follows_city_class_with_floors(self):
        for city_class, expected in CLASS_INTENSITY.items():
            self.assertEqual(ruin_legacy(city(city_class=city_class), 'fire', potencies())['intensity'], expected)
        self.assertEqual(ruin_legacy(city(city_class='small'), 'self_magic', potencies())['intensity'], 2.5)
        self.assertEqual(ruin_legacy(city(city_class='capital'), 'self_magic', potencies())['intensity'], 3.5)
        self.assertEqual(ruin_legacy(city(city_class='capital'), 'divine_x', potencies(), god_school='weave')['intensity'], 4.)
        self.assertEqual(ruin_legacy({'uid': 'c', 'population_profile': 'dwarf'}, 'fire', potencies())['intensity'], 1.5)


if __name__ == '__main__':
    unittest.main()
