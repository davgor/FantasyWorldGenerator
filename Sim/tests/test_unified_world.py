import math
import unittest
from icarus_sim.terrain_leyline_history import network_geometry
from icarus_sim.world_scene import road_entries, build_scene
from icarus_sim.city_planner import plan_city
from test_city_planner import fixture


class UnifiedTests(unittest.TestCase):
    def test_network_variation_and_replay(self):
        results=[network_geometry(s,12) for s in range(12)]
        self.assertEqual(results[0],network_geometry(0,12))
        self.assertGreater(len({len(r[1]) for r in results}),2)
        self.assertGreater(len({r[2]['clusters'] for r in results}),1)
        for nodes,edges,meta in results:
            self.assertEqual(len(nodes),12)
            self.assertTrue(all(abs(sum(v*v for v in p)-1)<1e-9 for p in nodes))
            self.assertTrue(all(e['from']!=e['to'] for e in edges))

    def road_world(self):
        w=fixture();w['roads']={'routes':[{'from':0,'to':1,'nodes':[0,1,2]}]}
        w['water']={'nodes':[[8,8],[9,8],[10,8]]}
        return w

    def test_city_connects_to_world_road_and_exports_same_junction(self):
        w=self.road_world();site=w['settlements']['sites'][0]
        p=plan_city(w,site)
        self.assertTrue(p['road_connections'])
        c=p['road_connections'][0];self.assertEqual(c['status'],'connected')
        self.assertEqual(c['local_path_m'][-1],c['gate_local_m'])
        w['city_plans']={'cities':[p]};build_scene(w)
        scene=w['world_scene'];junction=next(j for j in scene['junctions'] if j['id']==c['junction_id'])
        region=scene['regional_roads'][0]
        self.assertEqual(region['positions_m'][0],junction['position_m'])
        street=next(s for s in scene['streets'] if s.get('junction_id')==c['junction_id'])
        self.assertEqual(street['positions_m'][-1],junction['position_m'])
        self.assertTrue(scene['buildings'])
        building=scene['buildings'][0];corners=building['footprint_positions_m']
        self.assertAlmostEqual(math.dist(corners[0],corners[1]),building['dimensions_m']['width'])
        self.assertAlmostEqual(math.dist(corners[1],corners[2]),building['dimensions_m']['depth'])

    def test_blocked_gate_is_explicit(self):
        w=self.road_world();w['layers']['water_type']=[[1]*17 for _ in range(17)]
        p=plan_city(w,w['settlements']['sites'][0])
        self.assertTrue(p['road_connections'])
        self.assertTrue(all(c['status']=='unreachable' for c in p['road_connections']))
