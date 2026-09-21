import copy
import math
import unittest
from icarus_sim.castle_planner import plan_castle, fill_castles, planner_identity, VERSION


def fixture(water=False, fortresses=1):
    n = 17
    layers = {k: [[v] * n for _ in range(n)] for k, v in
              [('height', 100), ('slope', 2), ('tpi', 0), ('water_type', int(water)), ('river', 0),
               ('flood_risk', 0), ('moisture', .5), ('natural_biome', 3)]}
    city = dict(uid='test-city', id=0, name='Test city', x=8, z=8, city_class='small',
                population_profile='human_heartland', population_estimate=100,
                urban_population_estimate=60, freshwater_distance_m=100, resource_potential=.5)
    forts = []
    for i in range(fortresses):
        forts.append(dict(
            id=f'fortress-{i}', kind='fortress', node=2 + i, x=11 + i, z=8, core_id=0,
            population_profile='human_heartland', culture_id='c0', height_m=110,
            access_cost=200., access_nodes=[2 + i, 1, 0], defence_score=1.2,
            protected_route_node=1, reason='test'))
    return dict(
        config=dict(seed=42, size=n, globe_radius=10000),
        effective_config=dict(globe_radius=10000),
        layers=layers, settlements={'sites': [city]},
        humans={'hamlets': [], 'fortresses': forts},
        water={'nodes': [[8, 8], [10, 8], [11, 8], [12, 8], [13, 8]]},
        roads={'routes': []}, history={'ages': []}, magic={'networks': {}})


class CastlePlannerTests(unittest.TestCase):
    def test_replay_closed_perimeter_and_castle_ids(self):
        world = fixture()
        a = plan_castle(world, world['humans']['fortresses'][0])
        self.assertEqual(a, plan_castle(world, world['humans']['fortresses'][0]))
        self.assertEqual(a['version'], VERSION)
        self.assertEqual([p['id'] for p in a['passes']],
                         ['map', 'kit', 'perimeter', 'courts', 'landmarks', 'services'])
        self.assertEqual(a['bounds_m'][0], -a['bounds_m'][2])
        self.assertIsInstance(a['roads'], list)
        self.assertTrue(a['wall_networks'])
        closed = [n for n in a['wall_networks'] if n['status'] == 'closed']
        self.assertTrue(closed)
        self.assertTrue(all(n['walkway_continuous'] for n in closed))
        self.assertTrue(sum(len(n.get('segments', [])) for n in closed) >= 6)
        self.assertTrue(any(p['building_id'] == 'building.keep_tower' for p in a['plots']))
        self.assertTrue(any(p['building_id'] == 'building.bailey_court' for p in a['plots']))
        self.assertTrue(any(p['kind'] == 'gate' for p in a['plots']))
        self.assertTrue(all(p['building_id'].startswith('building.') for p in a['plots']))
        self.assertFalse(any(p['building_id'].startswith('building.hamlet_') for p in a['plots']))
        self.assertFalse(any(p['building_id'] in ('building.worker_house', 'building.worker_apartment')
                             for p in a['plots']))

    def test_gate_on_approach(self):
        world = fixture()
        plan = plan_castle(world, world['humans']['fortresses'][0])
        outer = plan['wall_networks'][0]
        self.assertEqual(outer['status'], 'closed')
        self.assertGreaterEqual(outer['gate_count'], 1)
        self.assertTrue(plan['road_connections'])
        approach = plan['road_connections'][0]['gate_local_m']
        gate = outer['gates'][0]['position_m']
        self.assertLess(math.dist(gate, approach), 20)

    def test_fill_independent_of_city_plans(self):
        world = fixture()
        original = copy.deepcopy(world)
        fill_castles(world)
        self.assertIn('castle_plans', world)
        self.assertNotIn('city_plans', world)
        self.assertEqual(world['layers'], original['layers'])
        self.assertEqual(world['humans']['fortresses'], original['humans']['fortresses'])
        self.assertEqual(world['castle_plans']['identity'], planner_identity())
        self.assertEqual(len(world['castle_plans']['castles']), 1)

    def test_water_site_reports_failure(self):
        world = fixture(water=True)
        plan = plan_castle(world, world['humans']['fortresses'][0])
        self.assertIn(plan['status'], ('unbuildable', 'partial'))
        if plan['status'] == 'unbuildable':
            self.assertEqual(plan['plots'], [])

    def test_saturated_regional_flood_risk_does_not_disqualify_a_castle(self):
        """Mirrors the city-planner case: a coarse proxy cannot judge one local cell.

        flood_risk is 0 or 1 over a raster cell thousands of metres wide, so every
        sample in a castle footprint reads one value. Honouring it left 34 of 56
        castles unbuildable in a seed-42 size-33 world. A routed river channel and
        its setback still block, because that mask is measured in local metres.
        """
        world = fixture()
        world['layers']['flood_risk'] = [[1] * 17 for _ in range(17)]
        plan = plan_castle(world, world['humans']['fortresses'][0])
        self.assertNotEqual(plan['status'], 'unbuildable')
        self.assertTrue(plan['plots'])

    def test_final_generation_exports_castle_plans_and_assets(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import materialize_stage
        from fantasy_world_generator.asset_list import compile_asset_list
        world = generate_request({'seed': 42, 'overrides': {'size': 17, 'phase': 16, 'fortress_count': 2}})
        self.assertIn('castle_plans', world)
        self.assertNotIn('castle_plans', materialize_stage(world, 15))
        self.assertEqual(world['castle_plans']['version'], VERSION)
        # A castle plan declares no sleeping capacity rather than a zero beside a
        # placed garrison: no structure in the castle registry carries a bed count.
        self.assertIn('beds', world['castle_plans'])
        for plan in world['castle_plans']['castles']:
            self.assertFalse(any('beds' in p for p in plan['plots']))
        self.assertEqual(len(world['castle_plans']['castles']), len(world['humans']['fortresses']))
        ids = {a['id'] for a in compile_asset_list()['assets']}
        for plan in world['castle_plans']['castles']:
            self.assertTrue(all(p['building_id'] in ids for p in plan['plots']))
            for network in plan['wall_networks']:
                for seg in network.get('segments', []):
                    self.assertIn(seg['structure_id'], ids)
        self.assertTrue(any(b.get('settlement_kind') == 'castle' for b in world['world_scene']['buildings'])
                        or all(p['status'] == 'unbuildable' for p in world['castle_plans']['castles']))

    def test_age_advance_rebuilds_castle_plans(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import advance_age_request
        from unittest.mock import patch
        world = generate_request({'seed': 42, 'overrides': {'size': 17, 'phase': 16, 'fortress_count': 1}})
        advanced = advance_age_request({'api_version': 1, 'world': world})
        self.assertEqual({c['fortress_id'] for c in advanced['castle_plans']['castles']},
                         {f['id'] for f in advanced['humans']['fortresses']})
        with patch('icarus_sim.castle_planner.planner_identity', return_value={}):
            with self.assertRaisesRegex(ValueError, 'Castle planner data changed'):
                advance_age_request({'api_version': 1, 'world': world})


if __name__ == '__main__':
    unittest.main()
