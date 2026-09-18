import math
import unittest
from icarus_sim.city_fortifications import (
    program_half_m, build_fortifications, ring_count_for, smooth_closed_ring, path_turn_degrees,
)
from icarus_sim.city_planner import plan_city


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


class FortificationTests(unittest.TestCase):
    def test_program_half_grows_with_demand(self):
        preset={'buildings':[{'plot_m':{'width':20,'depth':30},'count':40,'staffing':{'roles':[{'target':8}]}}]}
        small=program_half_m(preset,'small',240)
        capital=program_half_m(preset,'capital',800)
        self.assertGreaterEqual(capital,400)
        self.assertLessEqual(capital,800)
        self.assertEqual(program_half_m(preset,'capital',300),300)

    def test_ring_policy(self):
        self.assertEqual(ring_count_for('organic_market',{},'medium'),1)
        self.assertEqual(ring_count_for('organic_market',{},'small'),0)
        self.assertEqual(ring_count_for('concentric_enceintes',{'ring_count':3},'capital'),3)

    def test_medium_city_gets_single_ring(self):
        world=fixture()
        world['settlements']['sites'][0]['city_class']='medium'
        world['threat_assessments']={'version':1,'evaluated_after':'age','age':2,
                                     'cities':[{'city_uid':'test-city','regional_threat':0.2}]}
        plan=plan_city(world,world['settlements']['sites'][0])
        self.assertIsNotNone(plan['fortifications'])
        self.assertTrue(plan['fortifications']['defended_perimeter'])
        self.assertEqual(len(plan['fortifications']['rings']),1)
        self.assertGreater(len(plan['fortifications']['segments']),6)
        self.assertTrue(plan['stats']['defended_perimeter'])
        self.assertTrue(any(p['building_id']=='building.gatehouse' for p in plan['plots']))

    def test_high_threat_prefers_concentric_shape_weight(self):
        from icarus_sim.city_shapes import rank_shapes
        site={'buildable_area_m2':80000,'usable_land_fraction':0.5,'local_slope_degrees':5,
              'regional_threat':0.8,'defense_priority':0.8}
        ranked={r['id']:r for r in rank_shapes(site,'capital')}
        self.assertIn('concentric_enceintes',ranked)
        self.assertIn('regional_threat',ranked['concentric_enceintes']['matched_preferences'])
        low={'buildable_area_m2':80000,'usable_land_fraction':0.5,'local_slope_degrees':5,
             'regional_threat':0.1,'defense_priority':0.1}
        low_rank={r['id']:r for r in rank_shapes(low,'capital')}
        self.assertGreater(ranked['concentric_enceintes']['weight'],low_rank['concentric_enceintes']['weight'])

    def test_smooth_closed_ring_removes_a_needle_point(self):
        ring=[(12,0),(8.5,8.5),(0,12),(-8.5,8.5),(-12,0),(-8.5,-8.5),(0,-12),(8.5,-8.5)]
        spiked=list(ring);spiked[2]=(0,80)
        out=smooth_closed_ring(spiked)
        self.assertEqual(len(out),len(spiked))
        self.assertLess(math.hypot(*out[2]),28)
        n=len(out)
        for i in range(n):
            self.assertLessEqual(abs(path_turn_degrees(out[i-1],out[i],out[(i+1)%n])),96)

    def test_closed_ring_geometry(self):
        valid={(i,j) for i in range(5,35) for j in range(5,35)}
        wall={'id':'building.wall','dimensions_m':{'width':3,'depth':10,'height':7}}
        gate={'id':'building.gatehouse'}
        report=build_fortifications(valid=valid,half=80,cell=4,rx=70,rz=70,family='organic',
                                    shape_id='organic_market',parameters={},city_class='medium',
                                    road_connections=[{'status':'connected','gate_local_m':[70,0],'route_index':0}],
                                    wall_structure=wall,gate_structure=gate,tower_budget=2,gate_budget=2)
        self.assertTrue(report['defended_perimeter'])
        self.assertGreater(len(report['gates']),0)
        for seg in report['segments']:
            self.assertLessEqual(abs(seg['length_m']-10),10)
            self.assertTrue(math.isfinite(seg['rotation_degrees']))
