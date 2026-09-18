import math
import unittest
from icarus_sim.castle_geometry import (
    can_join, turn_degrees, segmentize, corner_indices, approach_gate_index,
    build_wall_network, ellipse_ring,
)
from icarus_sim.castle_planner import load_castles


class CastleGeometryTests(unittest.TestCase):
    def setUp(self):
        self.doc = load_castles()
        self.modules = self.doc['modules']
        self.rules = self.doc['join_rules']

    def test_compatible_curtain_joins(self):
        ok, reason = can_join(self.modules['curtain_segment'], self.modules['corner_join'], self.rules,
                              height_a=8.0, height_b=8.0)
        self.assertTrue(ok, reason)
        ok, reason = can_join(self.modules['curtain_segment'], self.modules['gatehouse'], self.rules,
                              height_a=8.0, height_b=8.0)
        self.assertTrue(ok, reason)

    def test_rejects_thickness_mismatch(self):
        ok, reason = can_join(self.modules['curtain_segment'], self.modules['corner_join'], self.rules,
                              thickness_a=3.0, thickness_b=5.0, height_a=8.0, height_b=14.0)
        self.assertFalse(ok)
        self.assertIn('Thickness', reason)

    def test_rejects_height_mismatch_on_curtain_pair(self):
        ok, reason = can_join(self.modules['curtain_segment'], self.modules['curtain_segment'], self.rules,
                              thickness_a=3.0, thickness_b=3.0, height_a=8.0, height_b=12.0)
        self.assertFalse(ok)
        self.assertIn('Height', reason)

    def test_turn_and_corners_on_square(self):
        square = [(20, 0), (0, 20), (-20, 0), (0, -20)]
        self.assertGreater(abs(turn_degrees(square[0], square[1], square[2])), 80)
        hits = corner_indices(square, 25)
        self.assertEqual(len(hits), 4)

    def test_segmentize_closed_ring(self):
        ring = ellipse_ring(40, 30, 24)
        segments, nodes = segmentize(ring, 10, 'building.curtain_segment', 'ring-0', 3.0, 8.0)
        self.assertGreaterEqual(len(segments), 6)
        self.assertEqual(len(nodes), len(ring))
        self.assertTrue(all(s['walkway'] for s in segments))
        self.assertTrue(all(s['id'].startswith('ring-0-seg-') for s in segments))

    def test_wall_network_closes_with_gate_and_corners(self):
        ring = ellipse_ring(48, 40, 32)
        approach = (48, 0)
        network = build_wall_network(
            ring_id='ring-outer', role='outer', polyline=ring, approach_m=approach,
            ring_spec={'gate': 'gatehouse', 'postern': True, 'stairs': 2, 'tower_budget': 4, 'ditch': False},
            modules=self.modules, rules=self.rules)
        self.assertEqual(network['status'], 'closed')
        self.assertTrue(network['walkway_continuous'])
        self.assertGreaterEqual(network['gate_count'], 1)
        self.assertEqual(network['gates'][0]['structure_id'], 'building.barbican')
        self.assertTrue(any(g.get('kind') == 'postern' or 'postern' in g['id'] for g in network['gates']))
        gate_pos = network['gates'][0]['position_m']
        self.assertLess(math.dist(gate_pos, approach), 12)
        self.assertTrue(network['towers'])
        self.assertTrue(network['stairs'])
        self.assertEqual(approach_gate_index(ring, approach),
                         min(range(len(ring)), key=lambda i: math.dist(ring[i], approach)))


if __name__ == '__main__':
    unittest.main()
