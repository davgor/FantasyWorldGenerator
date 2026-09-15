import math
import unittest

from icarus_sim.terrain_erosion import sphere_grid
from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_settlements import (
    _build_city_layout_plan,
    _collect_land_anchor_candidates,
    _dijkstra_distances,
    _load_city_layout_profiles,
)


class CityLayoutTests(unittest.TestCase):
    def test_empty_candidate_set_does_not_bypass_terrain_constraints(self):
        points = [(0, 0), (1, 0), (2, 0)]
        graph = [[(1, 10)], [(0, 10), (2, 10)], [(1, 10)]]
        candidates = _collect_land_anchor_candidates(
            points,
            graph,
            0,
            river_distances=[0, 20, 40],
            water=[0, 0, 0],
            slope=[30, 30, 30],
            max_slope=12,
            min_river_distance=50,
        )
        self.assertEqual(candidates, [])

        profile = _load_city_layout_profiles()['profiles']['standard_city_layout']
        plan = _build_city_layout_plan(7, 0, points, profile, 'human', 200, 0, graph[0], [True, True, False], candidates)
        self.assertIn('fallback', plan)
        self.assertTrue(all(feature['count'] == 0 for feature in plan['features'].values()))
        self.assertTrue(any(feature['target_count'] > 0 for feature in plan['features'].values()))

    def test_generated_layouts_are_deterministic_and_use_safe_land_anchors(self):
        config = Config(shape='globe', tectonics=1, size=33, phase=9)
        first = generate(config)
        second = generate(config)
        self.assertEqual(first['settlements'], second['settlements'])
        self.assertEqual(first['settlements']['version'], 9)
        self.assertTrue(first['settlements']['sites'])

        points, _, graph = sphere_grid(config.size, first['effective_config']['globe_radius'])
        layers = first['layers']
        water = [layers['water_type'][z][x] for x, z in points]
        slope = [layers['slope'][z][x] for x, z in points]
        river = [layers['rain_river'][z][x] for x, z in points]
        river_distances = _dijkstra_distances(graph, [index for index, value in enumerate(river) if value])

        expected_features = {
            'leader_homes', 'barracks', 'noble_homes', 'worker_housing',
            'apartments', 'market_district', 'religious_building'
        }
        for site in first['settlements']['sites']:
            self.assertTrue(site['building_pack_id'])
            layout = site['city_layout']
            self.assertEqual(layout['version'], 1)
            self.assertEqual(set(layout['features']), expected_features)
            constraints = layout['constraints']
            seen = set()
            for feature in layout['features'].values():
                self.assertEqual(feature['count'], len(feature['anchors']))
                for anchor in feature['anchors']:
                    node = anchor['node']
                    self.assertNotIn(node, seen)
                    seen.add(node)
                    self.assertEqual(water[node], 0)
                    self.assertLessEqual(slope[node], constraints['max_anchor_slope_degrees'])
                    if math.isfinite(river_distances[node]):
                        self.assertGreaterEqual(river_distances[node], constraints['min_river_distance_m'])


if __name__ == '__main__':
    unittest.main()
