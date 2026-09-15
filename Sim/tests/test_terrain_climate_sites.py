import unittest
import math
from dataclasses import replace
from icarus_sim.terrain_lab import Config,generate
from icarus_sim.terrain_climate import transport_moisture
from icarus_sim.terrain_settlements import shortest_paths

class ClimateSitesTests(unittest.TestCase):
    def test_windward_rain_and_downwind_drying(self):
        upstream=[[(max(0,i-1),1.)] for i in range(7)]
        flat=transport_moisture([0]*7,[True]+[False]*6,upstream,32,1)
        ridge=transport_moisture([0,0,0,100,0,0,0],[True]+[False]*6,upstream,32,1)
        self.assertGreater(ridge['rain'][3],flat['rain'][3])
        self.assertLess(ridge['rain'][5],flat['rain'][5])
        dry=transport_moisture([0]*7,[False]*7,upstream,32,1)
        self.assertEqual(dry['rain'],[0]*7)

    def test_road_routing_avoids_barrier_and_uses_cheaper_detour(self):
        graph=[[(1,1),(2,2)],[(0,1),(3,1)],[(0,2),(3,2)],[(1,1),(2,2)]]
        distance,parent=shortest_paths(graph,0,lambda i,j,d: None if j==1 or i==1 else d)
        self.assertEqual(distance[3],4)
        self.assertEqual(parent[3],2)
        self.assertEqual(parent[2],0)

    def test_new_stages_preserve_ground_and_site_spacing(self):
        cfg=Config(shape='globe',tectonics=1,size=33,phase=5)
        a=generate(cfg); b=generate(replace(cfg,phase=8,settlement_count=4))
        for key in ('height','water_surface','water_type'):
            self.assertEqual(a['layers'][key],b['layers'][key])
        self.assertIn('climate',b);self.assertIn('settlements',b);self.assertIn('roads',b)
        for site in b['settlements']['sites']:
            self.assertEqual(b['layers']['water_type'][site['z']][site['x']],0)
        sites=b['settlements']['sites'];radius=b['effective_config']['globe_radius']
        for i,site in enumerate(sites):
            for other in sites[i+1:]:
                distance=radius*math.acos(max(-1,min(1,sum(x*y for x,y in zip(site['direction'],other['direction'])))))
                self.assertGreaterEqual(distance,cfg.settlement_spacing-1e-6)
        for road in b['roads']['routes']:
            self.assertEqual(road['nodes'][0],sites[road['from']]['node'])
            self.assertEqual(road['nodes'][-1],sites[road['to']]['node'])
            for i in road['nodes']:
                x,z=b['water']['nodes'][i]
                self.assertEqual(b['layers']['water_type'][z][x],0)
            from icarus_sim.terrain_globe import direction
            for i,j in zip(road['nodes'],road['nodes'][1:]):
                x,z=b['water']['nodes'][i];xx,zz=b['water']['nodes'][j]
                u=direction(x,z,cfg.size);v=direction(xx,zz,cfg.size)
                distance=radius*math.acos(max(-1,min(1,sum(a*c for a,c in zip(u,v)))))
                grade=abs(b['layers']['height'][z][x]-b['layers']['height'][zz][xx])/distance
                self.assertLessEqual(grade,cfg.road_max_grade+1e-9)
        for key in ('rainfall','air_moisture','suitability'):
            for row in b['layers'][key]:self.assertEqual(row[0],row[-1])
            self.assertEqual(len(set(b['layers'][key][0])),1)
        self.assertAlmostEqual(b['climate']['runoff_input_m2_equivalent'],b['climate']['runoff_outlets_m2_equivalent'],places=5)

    def test_wind_and_downstream_controls_are_isolated(self):
        cfg=Config(shape='globe',tectonics=1,size=17,phase=8)
        a=generate(cfg);b=generate(replace(cfg,wind_bearing=270));c=generate(replace(cfg,settlement_count=0))
        self.assertNotEqual(a['layers']['rainfall'],b['layers']['rainfall'])
        self.assertEqual(a['layers']['water_surface'],b['layers']['water_surface'])
        self.assertEqual(a['layers']['rainfall'],c['layers']['rainfall'])
        self.assertEqual(c['settlements']['sites'],[])
        self.assertEqual(c['roads']['routes'],[])

    def test_control_validation(self):
        for kwargs in ({'rain_passes':0},{'settlement_count':25},{'stubbornness':2},{'road_max_grade':0}):
            with self.assertRaises(ValueError):Config(**kwargs)
