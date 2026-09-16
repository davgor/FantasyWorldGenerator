import math
import unittest
from icarus_sim.city_planner import plan_city
from test_city_planner import fixture


class CityGeometryTests(unittest.TestCase):
    def test_surface_preserves_world_gradient_and_building_levels(self):
        world=fixture()
        world['layers']['height']=[[100+x*40+z*20 for x in range(17)] for z in range(17)]
        plan=plan_city(world,world['settlements']['sites'][0])
        surface=plan['terrain']['surface']
        heights=[h for row in surface['heights_m'] for h in row]
        self.assertGreater(max(heights)-min(heights),1)
        self.assertTrue(all(math.isfinite(h) for h in heights))
        self.assertTrue(plan['plots'])
        for p in plan['plots']:
            self.assertGreaterEqual(p['ground_elevation_m'],min(heights))
            self.assertLessEqual(p['ground_elevation_m'],max(heights))
        self.assertTrue(any(abs(p['rotation_degrees'] % 90)>1 for p in plan['plots']))

    def test_streets_route_around_water_and_remain_connected(self):
        from icarus_sim.city_geometry import grow_roads
        valid={(x,z) for z in range(60) for x in range(60) if not (27<=x<=32 and 10<=z<=48)}
        height=lambda c: 0
        roads,paths=grow_roads(valid,height,60,7,18)
        self.assertEqual((roads,paths),grow_roads(valid,height,60,7,18))
        self.assertTrue(roads<=valid)
        reached={min(roads)};todo=list(reached)
        while todo:
            x,z=todo.pop()
            for c in ((x+1,z),(x-1,z),(x,z+1),(x,z-1)):
                if c in roads and c not in reached:reached.add(c);todo.append(c)
        self.assertEqual(reached,roads)
        self.assertTrue(any(x>32 for x,z in roads))
        self.assertTrue(any(x<27 for x,z in roads))
        self.assertNotEqual(paths,grow_roads(valid,height,60,8,18)[1])

    def test_streets_avoid_unclimbable_cliff(self):
        from icarus_sim.city_geometry import grow_roads
        valid={(x,z) for z in range(40) for x in range(40)}
        roads,paths=grow_roads(valid,lambda c: 1000 if c[0]>23 else 0,40,3,16)
        self.assertTrue(paths)
        self.assertTrue(all(x<=23 for path in paths for x,z in path))

    def test_diagonal_cannot_cross_between_cliff_cells(self):
        from icarus_sim.city_geometry import grow_roads
        valid={(x,z) for z in range(8) for x in range(8)}
        roads,paths=grow_roads(valid,lambda c: 0 if c[0]==c[1] else 1000,8,3,16)
        self.assertEqual(roads,{(4,4)})
        self.assertEqual(paths,[])
