import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config,generate
from icarus_sim.terrain_water import route_water

class WaterTests(unittest.TestCase):
    def test_inland_basin_fills_to_sill_not_sea_level(self):
        h=[-2,-1,5,-3,7]; areas=[2,2,1,1,1]
        graph=[[(1,1)],[(0,1),(2,1)],[(1,1),(3,1)],[(2,1),(4,1)],[(3,1)]]
        r=route_water(h,areas,graph,0)
        self.assertEqual(r['ocean'],[True,True,False,False,False])
        self.assertEqual(r['level'][3],5)
        self.assertEqual(r['parent'][3],2)
        self.assertAlmostEqual(sum(r['flow'][i] for i,p in enumerate(r['parent']) if p<0),sum(areas))
        for i in range(len(h)):
            seen=set()
            while i>=0:
                self.assertNotIn(i,seen);seen.add(i);i=r['parent'][i]

    def test_dry_world_has_no_invented_ocean(self):
        r=route_water([3,1,2],[1,1,1],[[(1,1)],[(0,1),(2,1)],[(1,1)]],0)
        self.assertFalse(any(r['ocean']))
        self.assertEqual(r['parent'][1],-1)
        self.assertEqual(r['flow'][1],3)

    def test_stage_isolation_and_sphere_topology(self):
        cfg=Config(shape='globe',tectonics=1,size=33,phase=4)
        a=generate(cfg);b=generate(replace(cfg,phase=5))
        self.assertEqual(a['layers']['height'],b['layers']['height'])
        self.assertEqual(a['area'],b['area'])
        self.assertNotIn('water',a)
        for key in ('water_type','water_depth','water_surface','routed_catchment'):
            for row in b['layers'][key]:self.assertEqual(row[0],row[-1])
            self.assertEqual(len(set(b['layers'][key][0])),1)
        self.assertAlmostEqual(b['water']['ocean_km2']+b['water']['lake_km2']+b['water']['dry_km2'],b['area']['total_km2'])
