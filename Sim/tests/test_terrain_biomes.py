import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_biomes import classify

class BiomeTests(unittest.TestCase):
    def test_classification_rules(self):
        self.assertEqual(classify(-1,0,30,.1),0)
        self.assertEqual(classify(10,0,25,.1),2)
        self.assertEqual(classify(10,0,20,.65),4)
        self.assertEqual(classify(10,0,25,.9),7)
        self.assertEqual(classify(10,0,-5,.8),6)
        self.assertEqual(classify(10,50,20,.8),5)
        self.assertEqual(classify(10,0,15,.4),3)

    def test_classification_preserves_world_and_wraps(self):
        cfg=Config(shape='globe',tectonics=1,size=33)
        a=generate(cfg); b=generate(replace(cfg,temperature_offset=10,moisture_bias=-.5))
        self.assertEqual(a['layers']['height'],b['layers']['height'])
        self.assertEqual(a['area'],b['area'])
        self.assertNotEqual(a['layers']['biome'],b['layers']['biome'])
        for key in ('biome','landform','temperature','moisture'):
            for row in a['layers'][key]: self.assertEqual(row[0],row[-1])
            self.assertEqual(len(set(a['layers'][key][0])),1)
        self.assertLessEqual(len(a['terrain']['features']),24)
        for f in a['terrain']['features']:
            self.assertGreater(a['layers']['height'][f['z']][f['x']],0)

    def test_invalid_climate_controls(self):
        for args in ({'temperature_offset':float('nan')},{'moisture_bias':2}):
            with self.assertRaises(ValueError): Config(**args)
