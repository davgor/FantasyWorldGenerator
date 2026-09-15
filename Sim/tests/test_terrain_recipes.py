import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config,generate
from icarus_sim.terrain_profiles import get_profile


class RecipeTests(unittest.TestCase):
    def test_profiles_are_validated_and_distinct(self):
        human=get_profile('human');highland=get_profile('highland')
        self.assertGreater(highland['site_slope_limit'],human['site_slope_limit'])
        with self.assertRaises(ValueError):get_profile('../unknown')

    def test_recipe_is_reproducible_and_ignores_expert_values(self):
        cfg=Config(shape='globe',tectonics=1,size=33,auto_parameters=1)
        a=generate(cfg);b=generate(replace(cfg,plate_count=25,ley_nodes=3,settlement_count=24))
        self.assertEqual(a['layers'],b['layers'])
        self.assertEqual(a['config'],b['config'])
        self.assertTrue(a['derivation']['settings'])
        self.assertEqual(a['population']['id'],'human')
        self.assertEqual(generate(Config(**a['config']))['layers'],a['layers'])

    def test_population_changes_do_not_reroll_world(self):
        cfg=Config(shape='globe',tectonics=1,size=33,auto_parameters=1)
        a=generate(cfg);b=generate(replace(cfg,population_profile='highland'))
        for key in ('height','water_surface','rainfall','biome','magic_density'):
            self.assertEqual(a['layers'][key],b['layers'][key])
        self.assertNotEqual(a['layers']['suitability'],b['layers']['suitability'])
        self.assertNotEqual(a['layers']['food_potential'],b['layers']['food_potential'])
        self.assertEqual(b['population']['id'],'highland')
        self.assertTrue(all(c['id'].startswith('highland-') for c in b['humans']['cultures']))

    def test_environment_sets_population_budget(self):
        from icarus_sim.terrain_recipes import derive_population
        cfg=Config(shape='globe',tectonics=1,size=17,auto_parameters=1)
        r=generate(cfg)
        r['water']['dry_km2']=0
        resolved=derive_population(r,cfg)
        self.assertEqual(resolved.settlement_count,0)

    def test_invalid_recipe_mode(self):
        for change in ({'auto_parameters':2},{'population_profile':'missing'}):
            with self.assertRaises(ValueError):Config(**change)

    def test_profile_definition_validation_and_woodland_food(self):
        from unittest.mock import patch
        from icarus_sim.terrain_profiles import profiles
        self.assertGreater(get_profile('woodland')['food_biome_multipliers']['10'],get_profile('human')['food_biome_multipliers']['10'])
        data=profiles();data['human']['mutation_limit']=2
        with patch('icarus_sim.terrain_profiles.profiles',return_value=data):
            with self.assertRaises(ValueError):get_profile('human')
        data=profiles();del data['human']['water_weight']
        with patch('icarus_sim.terrain_profiles.profiles',return_value=data):
            with self.assertRaises(ValueError):get_profile('human')
