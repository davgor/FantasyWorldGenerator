import copy
import json
import unittest
from icarus_sim.terrain_world import generate_request


class HistoryTests(unittest.TestCase):
    def test_versioned_pipeline_and_replay(self):
        from icarus_sim.terrain_history import STAGES, materialize_stage
        from icarus_sim.terrain_lab import Config, generate
        world = generate_request({'recipe_version': 2, 'seed': 42, 'overrides': {'size': 17}})
        self.assertEqual(len(STAGES), 16)
        self.assertEqual(world['phases']['completed'], 16)
        self.assertEqual(len(world['history']['ages']), 2)
        for stage in (5, 6, 7, 8, 9, 10, 13, 14, 15):
            view = materialize_stage(world, stage)
            if stage < 10:
                self.assertNotIn('settlements', view)
            if stage < 13:
                self.assertNotIn('beast_nests', view)
            if stage == 9:
                self.assertIn('magic', view)
                self.assertNotIn('biome_variant', view['layers'])
        self.assertNotEqual(materialize_stage(world, 5)['layers']['height'], materialize_stage(world, 6)['layers']['height'])
        again = generate(Config(**world['config']))
        for key in ('layers', 'history', 'ruins', 'settlements'):
            self.assertEqual(world[key], again[key])
        json.dumps(world, allow_nan=False)
        for grid in world['layers'].values():
            for row in grid:
                self.assertEqual(row[0], row[-1])
            for row in (grid[0], grid[-1]):
                self.assertEqual(len(set(row)), 1)

    def test_every_natural_biome_has_every_school(self):
        from icarus_sim.terrain_history import biome_catalogue, SCHOOLS, NATURAL_BIOMES
        entries = biome_catalogue()
        self.assertEqual(len(entries), len(NATURAL_BIOMES) * len(SCHOOLS))
        self.assertEqual(len({e['id'] for e in entries}), len(entries))
        tomb = next(e for e in entries if e['name'] == 'Haunted tombs')
        self.assertEqual((tomb['core'], tomb['magic_school'], tomb['color']), ('desert', 'necrotic', [72, 49, 35]))

    def test_event_reasons_and_self_destruction(self):
        from icarus_sim.terrain_history import city_fate
        city = {'uid': 'city-test', 'direction': [1, 0, 0], 'x': 1, 'z': 1}
        layers = {'ley_' + n: [[0.]*3 for _ in range(3)] for n in ('weave','umbral','infernal','holy','primordial')}
        layers['ley_infernal'][1][1] = 1
        fate = city_fate(city, layers, [], 1000, 42, 1, roll=0.)
        self.assertEqual(fate['cause'], 'fire')
        self.assertIn('flames', fate['reason'])
        layers['ley_infernal'][1][1] = 0
        fate = city_fate(city, layers, [], 1000, 42, 1, roll=0.)
        self.assertEqual(fate['cause'], 'self_magic')
        self.assertEqual(fate['new_node_school'], 'weave')

    def test_abandoned_waterways(self):
        from icarus_sim.terrain_history import abandoned_waterways
        old = {'river': [[1,0,0]], 'water_type': [[0,2,0]], 'water_depth': [[0,20,0]]}
        new = {'river': [[0,0,1]], 'water_type': [[0,0,0]]}
        gorges, valleys = abandoned_waterways(old, new)
        self.assertEqual(gorges, [[1,0,0]])
        self.assertEqual(valleys, [[0,1,0]])
