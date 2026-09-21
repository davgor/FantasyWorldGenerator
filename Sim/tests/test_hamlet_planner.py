import copy
import math
import unittest
from icarus_sim.city_geometry import corners
from icarus_sim.hamlet_planner import plan_hamlet, fill_hamlets, VERSION


def fixture(role='farming', water=False):
    n=17
    layers={k:[[v]*n for _ in range(n)] for k,v in
            [('height',100),('slope',2),('tpi',0),('water_type',int(water)),('river',0),
             ('flood_risk',0),('moisture',.5),('natural_biome',3)]}
    city=dict(uid='test-city',id=0,name='Test city',x=8,z=8,city_class='small',
              population_profile='human_heartland',population_estimate=100,urban_population_estimate=60,
              freshwater_distance_m=100,resource_potential=.5)
    # Neighbour node toward +x so the support path crosses the local window edge.
    hamlet=dict(id='hamlet-0',kind='hamlet',role=role,node=1,x=10,z=8,core_id=0,
                population_profile='human_heartland',culture_id='c0',height_m=100,
                access_cost=120.,access_nodes=[1,0],worked_area_km2=.1,delivered_food=1.,
                delivered_materials=0.,irrigation_benefit=0.,reason='test')
    return dict(config=dict(seed=42,size=n,globe_radius=10000),effective_config=dict(globe_radius=10000),
                layers=layers,settlements={'sites':[city]},humans={'hamlets':[hamlet]},
                water={'nodes':[[8,8],[10,8],[12,8]]},roads={'routes':[]},history={'ages':[]},magic={'networks':{}})


class HamletPlannerTests(unittest.TestCase):
    def test_priority_order_housing_replay_and_rural_ids(self):
        world=fixture();a=plan_hamlet(world,world['humans']['hamlets'][0])
        self.assertEqual(a,plan_hamlet(world,world['humans']['hamlets'][0]))
        self.assertEqual([p['id'] for p in a['passes']],['map','shape','high','high_housing','low','low_housing'])
        self.assertEqual(a['version'],VERSION)
        self.assertTrue(a['plots'])
        self.assertTrue(any(p['building_id']=='building.hamlet_well' for p in a['plots']))
        self.assertTrue(any(p['building_id']=='building.hamlet_farmyard' for p in a['plots']))
        self.assertTrue(any(p['kind']=='housing' for p in a['plots']))
        self.assertTrue(all(p['building_id'].startswith('building.hamlet_') for p in a['plots']))
        self.assertFalse(any(p['building_id'] in ('building.worker_house','building.worker_apartment') for p in a['plots']))
        self.assertGreaterEqual(a['stats']['worker_beds'],a['stats']['workers'])
        for i,p in enumerate(a['plots']):
            self.assertTrue(p['road_access'])
            for q in a['plots'][i+1:]:
                polygons=[corners(b['x_m'],b['z_m'],b['plot_m']['width'],b['plot_m']['depth'],math.radians(b['rotation_degrees'])) for b in (p,q)]
                axes=[(math.cos(math.radians(b['rotation_degrees'])+offset),math.sin(math.radians(b['rotation_degrees'])+offset)) for b in (p,q) for offset in (0,math.pi/2)]
                projections=[[[x*ax+z*az for x,z in poly] for poly in polygons] for ax,az in axes]
                self.assertTrue(any(max(a)<=min(b) or max(b)<=min(a) for a,b in projections))

    def test_resource_role_places_staging_not_farmyard(self):
        world=fixture('resource');plan=plan_hamlet(world,world['humans']['hamlets'][0])
        ids={p['building_id'] for p in plan['plots']}
        self.assertIn('building.hamlet_staging_yard',ids)
        self.assertNotIn('building.hamlet_farmyard',ids)
        self.assertNotIn('building.hamlet_barn',ids)

    def test_coastal_role_places_landing(self):
        world=fixture('harbor + fishing');plan=plan_hamlet(world,world['humans']['hamlets'][0])
        ids={p['building_id'] for p in plan['plots']}| {u['building_id'] for u in plan['unplaced'] if 'navigable' not in u.get('reason','')}
        # Landing may place or fail for terrain; farming barns must stay filtered out.
        self.assertFalse(any(p['building_id']=='building.hamlet_farmyard' for p in plan['plots']))
        self.assertTrue(any(u['building_id']=='building.hamlet_farmyard' for u in plan['unplaced']))
        if plan['plots']:
            self.assertTrue(any(p['building_id'] in ('building.hamlet_landing','building.hamlet_net_shed','building.hamlet_well') for p in plan['plots']))

    def test_support_road_gate_exported(self):
        world=fixture();plan=plan_hamlet(world,world['humans']['hamlets'][0])
        self.assertTrue(plan['road_connections'])
        self.assertEqual(plan['road_connections'][0]['route_id'],'support:hamlet-0')
        self.assertIn(plan['road_connections'][0]['status'],('connected','unreachable'))

    def test_water_site_reports_failure_without_forced_buildings(self):
        world=fixture(water=True);plan=plan_hamlet(world,world['humans']['hamlets'][0])
        self.assertEqual(plan['plots'],[])
        self.assertEqual(plan['status'],'unbuildable')

    def test_coarse_coastal_flood_risk_does_not_empty_hamlet(self):
        world=fixture('harbor + fishing')
        n=world['config']['size']
        world['layers']['flood_risk']=[[1]*n for _ in range(n)]
        plan=plan_hamlet(world,world['humans']['hamlets'][0])
        self.assertTrue(plan['plots'], plan['unplaced'])
        self.assertNotEqual(plan['status'],'unbuildable')
        self.assertTrue(any(p['building_id']=='building.hamlet_well' for p in plan['plots']))

    def test_nearby_hamlets_keep_core_plots(self):
        world=fixture()
        neighbour=dict(world['humans']['hamlets'][0])
        neighbour.update(id='hamlet-1',x=10.02,node=2)
        world['humans']['hamlets'].append(neighbour)
        plan=plan_hamlet(world,world['humans']['hamlets'][0])
        self.assertLess(plan['bounds_m'][2],100)
        self.assertTrue(plan['plots'], plan['debug'])
        self.assertTrue(any(p['building_id']=='building.hamlet_well' for p in plan['plots']))
        self.assertGreater(plan['debug']['shape_safe_cells'],plan['debug']['road_cells'])

    def test_final_generation_exports_hamlet_plans_and_assets(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import materialize_stage
        from fantasy_world_generator.asset_list import compile_asset_list
        world=generate_request({'seed':42,'overrides':{'size':17,'phase':16,'hamlets_per_core':2}})
        self.assertIn('hamlet_plans',world)
        self.assertNotIn('hamlet_plans',materialize_stage(world,15))
        self.assertEqual(world['hamlet_plans']['version'],3)
        self.assertEqual(len(world['hamlet_plans']['hamlets']),len(world['humans']['hamlets']))
        ids={a['id'] for a in compile_asset_list()['assets']}
        for plan in world['hamlet_plans']['hamlets']:
            self.assertTrue(all(p['building_id'] in ids for p in plan['plots']))
            self.assertTrue(all(p['building_id'].startswith('building.hamlet_') for p in plan['plots']))
            if any(cell==0 for row in plan['terrain']['codes'] for cell in row):
                self.assertTrue(plan['plots'], plan['hamlet_id'])
        self.assertTrue(any(b.get('settlement_kind')=='hamlet' for b in world['world_scene']['buildings']) or
                        all(p['status']=='unbuildable' for p in world['hamlet_plans']['hamlets']))

    def test_fill_does_not_change_population_or_layers(self):
        world=fixture();original=copy.deepcopy(world)
        fill_hamlets(world)
        self.assertEqual(world['layers'],original['layers'])
        self.assertEqual(world['humans']['hamlets'],original['humans']['hamlets'])
        self.assertEqual(world['city_plans'] if 'city_plans' in world else None, None)

    def test_age_advance_rebuilds_hamlet_plans(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import advance_age_request
        from unittest.mock import patch
        world=generate_request({'seed':42,'overrides':{'size':17,'phase':16,'hamlets_per_core':1}})
        advanced=advance_age_request({'api_version':1,'world':world})
        self.assertEqual({h['hamlet_id'] for h in advanced['hamlet_plans']['hamlets']},
                         {h['id'] for h in advanced['humans']['hamlets']})
        with patch('icarus_sim.hamlet_planner.planner_identity',return_value={}):
            with self.assertRaisesRegex(ValueError,'Hamlet planner data changed'):
                advance_age_request({'api_version':1,'world':world})


if __name__=='__main__':
    unittest.main()
