"""The current biome contract must not leak retired phenotype IDs."""
import copy
from dataclasses import replace
import json
import unittest

from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_world import default_config, generate_request
from icarus_sim.terrain_history import NATURAL_BIOMES, SCHOOLS, add_biome_variants, materialize_stage, advance_age_request

RETIRED = {9, 10, 11, 12, 14}


class BiomeContractTests(unittest.TestCase):
    def assert_current(self, world):
        terrain = world['terrain']
        self.assertEqual(terrain['version'], 6)
        self.assertEqual({b['id'] for b in terrain['biomes']}, set(NATURAL_BIOMES))
        self.assertEqual(terrain['biomes'], terrain['natural_biomes'])
        self.assertEqual(world['layers']['biome'], world['layers']['natural_biome'])
        self.assertTrue(all(v in NATURAL_BIOMES for row in world['layers']['biome'] for v in row))
        for p in [world['population'], *world.get('peoples', {}).values()]:
            self.assertEqual(p['schema_version'], 4)
            for key in ('biome_preferences', 'food_biome_multipliers'):
                self.assertFalse(set(map(int, p[key])) & RETIRED)

    def test_current_world_stages_replay_and_age(self):
        world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})
        self.assertEqual(world['generator_version'], 16)
        self.assert_current(world)
        self.assertEqual(len(world['terrain']['magical_biomes']), 104)
        for stage in (8, 9, 10, 13, 14, 15, 16):
            view = materialize_stage(world, stage)
            self.assert_current(view)
            partial = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'phase': stage}})
            self.assertEqual(view['layers'], partial['layers'])
        replay = generate(Config(**world['config']))
        for key in ('layers', 'terrain', 'history', 'settlements', 'humans', 'peoples'):
            self.assertEqual(world[key], replay[key])
        advanced = advance_age_request({'api_version': 1, 'world': world})
        self.assert_current(advanced)
        self.assertEqual(len(advanced['history']['ages']), 3)
        json.dumps(advanced, allow_nan=False)
        for changes in ({'terrain_version': 5}, {'biome': 9}, {'variant': 104}, {'variant': True}):
            broken = copy.deepcopy(world)
            if 'terrain_version' in changes:broken['terrain']['version'] = changes['terrain_version']
            if 'biome' in changes:broken['layers']['biome'][0] = [changes['biome']]*17
            if 'variant' in changes:broken['layers']['biome_variant'][0] = [changes['variant']]*17
            with self.assertRaises(ValueError):advance_age_request({'api_version': 1, 'world': broken})

    def test_all_variants_keep_the_natural_core_and_contests_clear_mutation(self):
        cfg = replace(default_config(3), size=17, phase=9)
        world = generate(cfg)
        n = cfg.size
        for core in NATURAL_BIOMES:
            world['layers']['natural_biome'] = [[core]*n for _ in range(n)]
            for school in SCHOOLS:
                for s in SCHOOLS:world['layers']['ley_'+s] = [[float(s == school)]*n for _ in range(n)]
                add_biome_variants(world, cfg)
                self.assertEqual(world['layers']['biome'][0][0], core)
                variant = world['terrain']['magical_biomes'][world['layers']['biome_variant'][0][0]]
                self.assertEqual((variant['core_biome_id'], variant['magic_school']), (core, school))
        world['layers']['ley_fire'] = [[1.]*n for _ in range(n)]
        add_biome_variants(world, cfg)  # Air and Fire now tie.
        self.assertTrue(all(v == -1 for row in world['layers']['biome_variant'] for v in row))

    def test_magic_disabled_has_only_natural_cells(self):
        world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17, 'magic_enabled': 0}})
        self.assert_current(world)
        self.assertTrue(all(v == -1 for row in world['layers']['biome_variant'] for v in row))

    def test_retired_recipes_require_regeneration(self):
        for version in (1, 2):
            with self.assertRaises(ValueError):default_config(version)
            with self.assertRaises(ValueError):generate_request({'recipe_version': version})
            with self.assertRaises(ValueError):Config(world_recipe=version)

    def test_profiles_use_explicit_variant_rules(self):
        from icarus_sim.terrain_profiles import get_profile, biome_food_multiplier
        human, woodland = get_profile('human_heartland'), get_profile('elf')
        self.assertGreater(biome_food_multiplier(woodland, 4, 'forest.earth'),
                           biome_food_multiplier(human, 4, 'forest.earth'))
        self.assertEqual(biome_food_multiplier(human, 4, None), 1)
        self.assertEqual(biome_food_multiplier(human, 4, 'forest.infernal'), .05)

    def test_profiles_reject_retired_ids_and_unknown_variants(self):
        from unittest.mock import patch
        from icarus_sim.terrain_profiles import profiles, get_profile
        for field, key in [('food_biome_multipliers', '10'), ('magic_biome_preferences', 'forest.unknown')]:
            data = profiles()
            data['human_heartland'][field][key] = .5
            with patch('icarus_sim.terrain_profiles.profiles', return_value=data):
                with self.assertRaises(ValueError):get_profile('human_heartland')

    def test_building_selection_matches_natural_or_exact_variant(self):
        from icarus_sim.terrain_settlements import _city_building_packs, _pick_city_building_pack
        catalogue = copy.deepcopy(_city_building_packs())
        pack = catalogue['packs'][0]
        pack.update(biomes={2}, biome_variants={'forest.earth'}, profiles=None, id='explicit-state-pack')
        catalogue['packs'] = [pack]
        args = (42, 'human_heartland', 4, 20., 2., .5, 50., catalogue)
        self.assertEqual(_pick_city_building_pack(*args, variant_id='forest.earth'), 'explicit-state-pack')
        self.assertEqual(_pick_city_building_pack(*args, variant_id='forest.weave'), catalogue['fallback_pack_id'])
        self.assertEqual(_pick_city_building_pack(42,'human_heartland',2,20.,2.,.5,50.,catalogue), 'explicit-state-pack')

    def test_explicit_empty_building_variant_selector_matches_nothing(self):
        from pathlib import Path
        from icarus_sim import terrain_settlements
        from icarus_sim.civilization_registry import building_pack_data
        raw = building_pack_data()
        raw['packs'][1]['criteria'] = {'biome_variants': []}
        catalogue = terrain_settlements._validate_building_packs(raw)
        catalogue['packs'] = [catalogue['packs'][1]]
        actual = terrain_settlements._pick_city_building_pack(42,'human_heartland',4,20.,2.,.5,50.,catalogue,'forest.earth')
        self.assertEqual(actual, catalogue['fallback_pack_id'])
