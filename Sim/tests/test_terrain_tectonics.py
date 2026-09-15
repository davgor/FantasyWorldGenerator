import math
import unittest
from dataclasses import replace

from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_tectonics import relative_motion, make_plates, relief_at, continental_profile, mountain_modulation


class TectonicTests(unittest.TestCase):
    def config(self, **kwargs):
        return Config(**dict({'shape':'globe','tectonics':1,'size':17}, **kwargs))

    def test_boundary_motion_sign_and_shared_rotation(self):
        p, normal = (1,0,0), (0,1,0)
        # omega cross p: +z rotation travels +y.
        close = relative_motion(p,normal,(0,0,1),(0,0,-1))
        apart = relative_motion(p,normal,(0,0,-1),(0,0,1))
        self.assertEqual(close, (1,0,0))
        self.assertEqual(apart, (0,1,0))
        self.assertEqual(relative_motion(p,normal,(1,2,3),(1,2,3)), (0,0,0))

    def test_seeded_layout_and_unique_centers(self):
        a=make_plates(42,12)
        self.assertEqual(a,make_plates(42,12))
        self.assertNotEqual(a,make_plates(43,12))
        self.assertEqual(len({tuple(p['center']) for p in a}),12)
        for plate in a:
            self.assertAlmostEqual(sum(v*v for v in plate['center']),1)

    def test_phase_isolation_and_zero_noise(self):
        a=generate(self.config(phase=1))
        b=generate(self.config(phase=2))
        c=generate(self.config(phase=3,amplitude=0))
        for k in ('plates','crust','boundary_distance'):
            self.assertEqual(a['layers'][k],b['layers'][k])
            self.assertEqual(b['layers'][k],c['layers'][k])
        self.assertEqual(b['layers']['height'],c['layers']['height'])
        self.assertGreater(max(v for row in b['layers']['height'] for v in row)-min(v for row in b['layers']['height'] for v in row),100)
        self.assertNotIn('slope',a['layers'])
        self.assertNotIn('noise',b['layers'])

    def test_detail_changes_cannot_move_plates_or_relief(self):
        cfg=self.config(phase=3,wavelength=20000)
        a=generate(cfg); b=generate(replace(cfg,detail_variation=1))
        for k in ('plates','crust','structure'):
            self.assertEqual(a['layers'][k],b['layers'][k])
        self.assertNotEqual(a['layers']['noise'],b['layers']['noise'])

    def test_all_layers_wrap_and_poles_agree(self):
        a=generate(self.config(phase=3))
        for key,layer in a['layers'].items():
            for row in layer:
                self.assertEqual(row[0],row[-1],key)
                self.assertTrue(all(math.isfinite(v) for v in row))
            self.assertEqual(len(set(layer[0])),1,key)
            self.assertEqual(len(set(layer[-1])),1,key)
        self.assertTrue(all(0<=v<12 for row in a['layers']['plates'] for v in row))

    def test_invalid_phase_controls(self):
        for args in ({'phase':0},{'plate_count':1},{'tectonics':2}, {'belt_width':0}, {'crust_bias':2}):
            with self.assertRaises(ValueError):
                self.config(**args)

    def test_boundary_profiles_have_intended_effects(self):
        cfg=self.config()
        # Compare to the same crust without motion: collision uplifts continents;
        # divergence depresses continents but raises ocean spreading ridges.
        continental=relief_at(1,0,0,0,1,1,cfg)[0]
        ocean=relief_at(0,0,0,0,0,0,cfg)[0]
        self.assertGreater(relief_at(1,0,1,0,1,1,cfg)[0],continental)
        self.assertLess(relief_at(1,0,0,1,1,1,cfg)[0],continental)
        self.assertGreater(relief_at(0,0,0,1,0,0,cfg)[0],ocean)
        far=relief_at(1,10*cfg.belt_width*cfg.globe_radius,1,0,1,1,cfg)[0]
        self.assertAlmostEqual(far,continental)

    def test_phase_two_controls_preserve_layout(self):
        cfg=self.config(phase=2)
        a=generate(cfg); b=generate(replace(cfg,tectonic_relief=400))
        self.assertEqual(a['layers']['plates'],b['layers']['plates'])
        self.assertEqual(a['layers']['crust'],b['layers']['crust'])
        self.assertNotEqual(a['layers']['height'],b['layers']['height'])

    def test_continental_profile_flattens_interiors(self):
        values=[continental_profile(i/100) for i in range(101)]
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertLess(continental_profile(.95)-continental_profile(.75),.2)
        self.assertLess(continental_profile(.25)-continental_profile(.05),.2)
        self.assertGreater(continental_profile(.5)-continental_profile(.3),1)

    def test_mountain_modulation_is_bounded_and_varies_along_belt(self):
        values=[mountain_modulation(i*.2,.1,1) for i in range(30)]
        self.assertGreater(max(values)-min(values),.1)
        self.assertTrue(all(.3<=v<=1 for v in values))
        self.assertEqual(mountain_modulation(1,2,0),1)


if __name__=='__main__':
    unittest.main()
