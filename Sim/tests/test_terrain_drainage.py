import math
import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_erosion import erode, sphere_grid
from icarus_sim.terrain_tectonics import layout_point, make_plates, unit


class DrainageTests(unittest.TestCase):
    def test_spherical_area_and_conservative_transport(self):
        n=17; radius=1000
        h=[[100*math.cos(math.pi*z/(n-1))]*n for z in range(n)]
        points,areas,neighbors=sphere_grid(n,radius)
        self.assertAlmostEqual(sum(areas),4*math.pi*radius**2,places=6)
        result,budget=erode(h,radius,-200,4,.5)
        before=sum(h[z][x]*a for (x,z),a in zip(points,areas))
        after=sum(result['height'][z][x]*a for (x,z),a in zip(points,areas))
        self.assertAlmostEqual((after-before+budget['stored_sediment_m3'])/sum(abs(h[z][x])*a for (x,z),a in zip(points,areas)),0,places=7)
        self.assertGreater(budget['eroded_m3'],0)
        self.assertGreater(budget['deposited_m3'],0)
        for layer in result.values():
            for row in layer:
                self.assertEqual(row[0],row[-1])
            self.assertEqual(len(set(layer[0])),1)
            self.assertEqual(len(set(layer[-1])),1)

    def test_phase_four_zero_passes_and_stage_isolation(self):
        cfg=Config(shape='globe',tectonics=1,size=17,phase=3)
        a=generate(cfg)
        b=generate(replace(cfg,phase=4,erosion_passes=0))
        c=generate(replace(cfg,phase=4,erosion_passes=3))
        self.assertEqual(a['layers']['height'],b['layers']['height'])
        for key in ('plates','crust','structure','noise','surface'):
            self.assertEqual(b['layers'][key],c['layers'][key])
        self.assertEqual(a['layers']['height'],c['layers']['surface'])

    def test_junction_continuity_and_plate_order(self):
        cfg=Config(shape='globe',tectonics=1,size=17)
        plates=make_plates(17,3)
        a,b,c=[p['center'] for p in plates]
        from icarus_sim.terrain_tectonics import cross
        p=unit(cross(tuple(x-y for x,y in zip(a,b)),tuple(x-y for x,y in zip(a,c))))
        heights=[]
        for offset in (-1e-7,0,1e-7):
            q=unit((p[0]+offset,p[1],p[2]))
            heights.append(layout_point(q,plates,42,cfg)[-3])
        self.assertLess(max(heights)-min(heights),.1)
        self.assertAlmostEqual(layout_point(p,plates,42,cfg)[-3],layout_point(p,list(reversed(plates)),42,cfg)[-3])

    def test_erosion_controls_reject_invalid_values(self):
        for args in ({'erosion_passes':-1},{'erosion_passes':1.5},{'erosion_strength':float('nan')},{'erosion_strength':2}):
            with self.assertRaises(ValueError):
                Config(**args)

    def test_downhill_catchment_reaches_sink_and_zero_strength_is_noop(self):
        n=9; radius=1000
        h=[[100-25*z]*n for z in range(n)]
        layers,budget=erode(h,radius,-200,1,0)
        self.assertEqual(layers['height'],h)
        self.assertEqual(budget['eroded_m3'],0)
        self.assertAlmostEqual(layers['catchment'][-1][0],4*math.pi*radius**2,places=6)
        self.assertGreater(layers['catchment'][-1][0],layers['catchment'][0][0])
        flat,_=erode([[10.]*n for _ in range(n)],radius,0,5,1)
        self.assertEqual(flat['height'],[[10.]*n for _ in range(n)])

    def test_physical_units_scale_area_and_sediment_volume(self):
        cfg=Config(shape='globe',tectonics=1,size=17,phase=4,world_scale=1)
        a=generate(cfg); b=generate(replace(cfg,world_scale=.5))
        for key in ('eroded_m3','deposited_m3','stored_sediment_m3'):
            self.assertAlmostEqual(b['sediment_budget'][key],a['sediment_budget'][key]/8)
        for ra,rb in zip(a['layers']['catchment'],b['layers']['catchment']):
            self.assertEqual([v/4 for v in ra],rb)
