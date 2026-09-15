import math
import unittest
from icarus_sim.terrain_area import land_area


class AreaTests(unittest.TestCase):
    def test_full_sphere_area_and_duplicate_seam(self):
        for n in (5,17):
            info=land_area([[1.]*n for _ in range(n)],1000,0)
            self.assertAlmostEqual(info['land_km2'],4*math.pi)
            self.assertAlmostEqual(info['land_fraction'],1)

    def test_hemisphere_area(self):
        n=18
        h=[[math.cos(math.pi*z/(n-1))]*n for z in range(n)]
        info=land_area(h,1000,0)
        self.assertAlmostEqual(info['land_fraction'],.5)

    def test_polar_cells_have_less_area_than_equator(self):
        n=17
        polar=[[-1.]*n for _ in range(n)]; equator=[[-1.]*n for _ in range(n)]
        polar[0]=[1.]*n; equator[8]=[1.]*n
        self.assertLess(land_area(polar,1000,0)['land_km2'],land_area(equator,1000,0)['land_km2'])

    def test_shared_scale_preserves_slopes_and_natural_area_variation(self):
        from dataclasses import replace
        from icarus_sim.terrain_lab import Config,generate
        cfg=Config(shape='globe',tectonics=1,size=33,phase=3,world_scale=1)
        raw=generate(cfg); fitted=generate(replace(cfg,world_scale=.2))
        self.assertAlmostEqual(fitted['area']['land_km2'],raw['area']['land_km2']*.04)
        self.assertEqual(raw['layers']['slope'],fitted['layers']['slope'])
        self.assertEqual(raw['layers']['plates'],fitted['layers']['plates'])
        self.assertEqual(fitted['config']['globe_radius'],cfg.globe_radius)
        factor=fitted['physical_scale']['factor']
        self.assertAlmostEqual(fitted['layers']['height'][8][8],raw['layers']['height'][8][8]*factor)
        other=generate(replace(cfg,world_scale=.2,seed=43))
        self.assertNotEqual(other['area']['land_km2'],fitted['area']['land_km2'])
