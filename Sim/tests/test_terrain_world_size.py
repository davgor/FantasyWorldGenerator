import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config,generate

class WorldSizeTests(unittest.TestCase):
    def test_radius_presets_and_default(self):
        cfg=Config(auto_parameters=1,size=17,phase=2)
        small=generate(cfg)
        for name,factor in (('small',1),('medium',2),('large',3)):
            world=generate(replace(cfg,world_size=name))
            self.assertAlmostEqual(world['effective_config']['globe_radius'],small['effective_config']['globe_radius']*factor)
            self.assertEqual(world['config']['world_size'],name)
            self.assertEqual(generate(Config(**world['config']))['layers'],world['layers'])
    def test_unknown_size_rejected(self):
        for value in ('huge','',2,None):
            with self.assertRaises(ValueError):Config(world_size=value)
