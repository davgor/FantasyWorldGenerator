import copy
import math
from icarus_sim.city_geometry import corners
import unittest
from icarus_sim.city_planner import plan_city, fill_cities


def fixture(water=False):
    n=17
    layers={k:[[v]*n for _ in range(n)] for k,v in
            [('height',100),('slope',2),('tpi',0),('water_type',int(water)),('river',0),
             ('flood_risk',0),('moisture',.5),('natural_biome',3)]}
    site=dict(uid='test-city',id=0,name='Test city',x=8,z=8,city_class='small',
              population_profile='human_heartland',population_estimate=100,urban_population_estimate=60,
              freshwater_distance_m=100,resource_potential=.5)
    return dict(config=dict(seed=42,size=n,globe_radius=10000),effective_config=dict(globe_radius=10000),
                layers=layers,settlements={'sites':[site]},history={'ages':[]})


class CityPlannerTests(unittest.TestCase):
    def test_priority_order_housing_and_replay(self):
        world=fixture();a=plan_city(world,world['settlements']['sites'][0])
        self.assertEqual(a,plan_city(world,world['settlements']['sites'][0]))
        self.assertEqual([p['id'] for p in a['passes']],['map','shape','high','high_housing','low','low_housing'])
        self.assertGreater(a['stats']['workers'],0)
        self.assertGreaterEqual(a['stats']['worker_beds'],a['stats']['workers'])
        self.assertTrue(any(p['building_id']=='building.guildhall' for p in a['plots']))
        self.assertTrue(any(p['kind']=='housing' for p in a['plots']))
        for i,p in enumerate(a['plots']):
            self.assertTrue(p['road_access'])
            for q in a['plots'][i+1:]:
                polygons=[corners(b['x_m'],b['z_m'],b['plot_m']['width'],b['plot_m']['depth'],math.radians(b['rotation_degrees'])) for b in (p,q)]
                axes=[(math.cos(math.radians(b['rotation_degrees'])+offset),math.sin(math.radians(b['rotation_degrees'])+offset)) for b in (p,q) for offset in (0,math.pi/2)]
                projections=[[[x*ax+z*az for x,z in poly] for poly in polygons] for ax,az in axes]
                self.assertTrue(any(max(a)<=min(b) or max(b)<=min(a) for a,b in projections))

    def test_apartments_condense_existing_housing_when_land_runs_out(self):
        from unittest.mock import patch
        from icarus_sim.civilization_registry import city_plan as original
        def crowded(*args):
            preset=original(*args)
            for row in preset['buildings']:
                for role in row['staffing']['roles']:role['target']*=10
            return preset
        world=fixture()
        with patch('icarus_sim.city_planner.city_plan',side_effect=crowded):
            plan=plan_city(world,world['settlements']['sites'][0])
        apartments=[p for p in plan['plots'] if p['building_id']=='building.worker_apartment']
        self.assertTrue(apartments)
        self.assertTrue(all(p['beds']==16 for p in apartments))
        self.assertGreaterEqual(plan['stats']['worker_beds'],plan['stats']['workers'])

    def test_water_site_reports_failure_without_forced_buildings(self):
        world=fixture(True);plan=plan_city(world,world['settlements']['sites'][0])
        self.assertEqual(plan['plots'],[])
        self.assertEqual(plan['status'],'unbuildable')

    def test_routed_river_reserves_corridor_instead_of_entire_world_cell(self):
        world=fixture();world['layers']['river']=[[1]*17 for _ in range(17)]
        world['layers']['flood_risk']=[[1]*17 for _ in range(17)]
        world['water']={'nodes':[[8,7],[8,9]],'river_segments':[[0,1]]}
        plan=plan_city(world,world['settlements']['sites'][0])
        self.assertTrue(plan['plots'])
        for p in plan['plots']:
            for x,z in corners(p['x_m'],p['z_m'],p['plot_m']['width'],p['plot_m']['depth'],math.radians(p['rotation_degrees'])):self.assertGreaterEqual(abs(x),28)

    def test_final_generation_only_and_assets_cover_all_plots(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import materialize_stage
        from fantasy_world_generator.asset_list import compile_asset_list
        world=generate_request({'seed':42,'overrides':{'size':17,'phase':16}})
        self.assertIn('city_plans',world)
        self.assertNotIn('city_plans',materialize_stage(world,15))
        self.assertEqual(len(world['city_plans']['cities']),len(world['settlements']['sites']))
        ids={a['id'] for a in compile_asset_list()['assets']}
        for city in world['city_plans']['cities']:
            self.assertTrue(all(p['building_id'] in ids for p in city['plots']))

    def test_fill_does_not_change_population_or_world_layers(self):
        world=fixture();original=copy.deepcopy(world)
        fill_cities(world)
        self.assertEqual(world['layers'],original['layers'])
        self.assertEqual(world['settlements'],original['settlements'])

    def test_invalid_housing_capacity_rejected(self):
        from icarus_sim.civilization_registry import load_registry,validate_registry
        data=load_registry();data['housing_profiles']['worker_house']['worker_beds']=0
        with self.assertRaises(ValueError):validate_registry(data)

    def test_age_advance_rebuilds_plans_and_rejects_changed_shape_identity(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import advance_age_request
        from unittest.mock import patch
        world=generate_request({'seed':42,'overrides':{'size':17,'phase':16}})
        advanced=advance_age_request({'api_version':1,'world':world})
        self.assertEqual({c['city_uid'] for c in advanced['city_plans']['cities']},
                         {s['uid'] for s in advanced['settlements']['sites']})
        with patch('icarus_sim.city_planner.planner_identity',return_value={}):
            with self.assertRaisesRegex(ValueError,'planner data changed'):
                advance_age_request({'api_version':1,'world':world})
