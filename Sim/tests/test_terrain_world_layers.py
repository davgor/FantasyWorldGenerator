import json
import math
import unittest
from dataclasses import replace
from icarus_sim.terrain_world import generate_request, default_config, OPTIONS
from icarus_sim.terrain_lab import generate, Config
from icarus_sim.terrain_ecology import monthly_temperatures, cold_habitat
from icarus_sim.terrain_society import water_cost
from icarus_sim.terrain_erosion import sphere_grid


class LayeredWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world=generate_request({'seed':42,'overrides':{'size':33,'phase':13}})

    def test_reproduction_and_partial_override(self):
        a=self.world;b=generate(Config(**a['config']))
        for key in ('layers','sky','fisheries','world_economy'):self.assertEqual(a[key],b[key])
        changed=generate_request({'seed':42,'overrides':{'size':33,'phase':13,'temperature_offset':-8}})
        self.assertEqual(changed['config']['temperature_offset'],-8)
        self.assertEqual(changed['layers']['height'],a['layers']['height'])
        self.assertNotEqual(changed['layers']['temperature'],a['layers']['temperature'])
        self.assertEqual(changed['recipe']['provenance']['temperature_offset'],'override')

    def test_network_independence_and_overlap(self):
        a=self.world;b=generate_request({'seed':42,'overrides':{'size':33,'phase':13,'infernal_strength':0.}})
        for key in ('height','rainfall','ley_weave','ley_umbral','ley_holy','ley_primordial'):
            self.assertEqual(a['layers'][key],b['layers'][key])
        self.assertTrue(all(v==0 for row in b['layers']['ley_infernal'] for v in row))
        self.assertTrue(any(min(u,h)>0 for ur,hr in zip(a['layers']['ley_umbral'],a['layers']['ley_holy']) for u,h in zip(ur,hr)))

    def test_finite_and_sphere_topology(self):
        json.dumps(self.world,allow_nan=False)
        for key,grid in self.world['layers'].items():
            for row in grid:self.assertEqual(row[0],row[-1],key)
            for row in (grid[0],grid[-1]):self.assertTrue(all(v==row[0] for v in row),key)
        for month in self.world['seasonal_environment']['months']:
            for grid in month.values():
                for row in grid:self.assertEqual(row[0],row[-1])

    def test_cold_regions_and_season_reversal(self):
        north=monthly_temperatures(5,60,.5);south=monthly_temperatures(5,-60,.5)
        for m in range(12):self.assertAlmostEqual(north[m],south[(m+6)%12])
        self.assertEqual(cold_habitat([-12]*12,.5,.5),'ice_cap')
        self.assertEqual(cold_habitat([-10]*6+[6]*6,.4,.5),'tundra')
        self.assertEqual(cold_habitat([-5]*6+[15]*6,.6,.5),'boreal')
        self.assertIsNone(cold_habitat([20]*12,.7,.5))

    def test_fishing_ownership_and_delivery(self):
        w=self.world;claimed=[]
        for port in w['fisheries']['ports']:
            claimed.extend(port['fishing_nodes'])
            self.assertGreater(port['harbor_quality'],.1)
            self.assertTrue(port['access_nodes'])
            self.assertAlmostEqual(port['delivered_food'],sum(port['monthly_fish']))
        self.assertEqual(len(claimed),len(set(claimed)))
        self.assertLessEqual(w['fisheries']['delivered_annual_food'],w['fisheries']['potential_annual_food']+1e-9)

    def test_monthly_food_conservation_and_route_caps(self):
        w=self.world
        for month in w['world_economy']['months']:
            self.assertAlmostEqual(month['opening']+month['harvest'],month['closing']+month['consumed']+month['spoiled']+month['overflow']+month['transit_loss'],places=8)
            self.assertTrue(all(c['closing']>=0 and c['shortage']>=0 for c in month['cities']))
            used={}
            for shipment in month['shipments']:used[shipment['route_index']]=used.get(shipment['route_index'],0)+shipment['sent']
            for index,amount in used.items():self.assertLessEqual(amount,w['transport']['routes'][index]['capacity'][month['month']-1]+1e-9)
        for route in w['transport']['routes']:
            self.assertEqual(len(route['capacity']),12)
            self.assertTrue(all(v>=0 for v in route['capacity']))
            self.assertTrue(0<route['efficiency']<=1)

    def test_sea_routes_stay_on_navigable_water(self):
        w=self.world;points,_,_=sphere_grid(33,w['effective_config']['globe_radius'])
        for route in w['transport']['routes']:
            if route['mode']!='sea':continue
            for node in route['nodes']:
                x,z=points[node]
                self.assertEqual(w['layers']['water_type'][z][x],1)
                self.assertGreaterEqual(w['layers']['water_depth'][z][x],OPTIONS['sea_draft']['default'])
            for m,capacity in enumerate(route['capacity']):
                if any(w['seasonal_environment']['months'][m]['water_ice'][points[i][1]][points[i][0]]==1 for i in route['nodes']):self.assertEqual(capacity,0)

    def test_water_paths_reject_land_shallows_and_diagonal_corners(self):
        points=[(0,1),(1,1),(0,2),(1,2),(0,3)]
        cost=water_cost(points,[1,0,1,1,1],[5]*5,[0]*5,.5,1.)
        self.assertIsNone(cost(0,3,10))
        self.assertIsNone(cost(0,1,10))
        cost=water_cost(points,[1]*5,[5,.5,5,5,5],[0]*5,.5,1.)
        self.assertIsNone(cost(0,1,10))

    def test_sky_has_independent_surfaces_and_budgets(self):
        w=self.world;self.assertTrue(w['sky']['islands'])
        ids={i['id'] for i in w['sky']['islands']}
        self.assertEqual(len(ids),len(w['sky']['islands']))
        for island in w['sky']['islands']:
            self.assertGreater(island['altitude_m'],w['layers']['height'][island['z']][island['x']])
            self.assertAlmostEqual(island['area_km2'],math.pi*island['radius_m']**2/1e6)
            self.assertTrue(island['mesh']['triangles'])
        for site in w['sky']['settlements']:
            self.assertIn(site['layer'],ids)
            self.assertLessEqual(site['population_estimate'],site['freshwater_capacity'])

    def test_population_does_not_reroll_sky_geometry(self):
        human=generate_request({'seed':42,'overrides':{'size':17,'phase':12,'population_profile':'human_heartland'}})
        mixed=generate_request({'seed':42,'overrides':{'size':17,'phase':12}})
        self.assertEqual(human['sky']['islands'],mixed['sky']['islands'])
        self.assertEqual(human['layers']['height'],mixed['layers']['height'])

    def test_archipelago_relief_is_an_explicit_addition(self):
        w=self.world
        for a,b,c,d in zip(w['layers']['structure'],w['layers']['continental'],w['layers']['interaction'],w['layers']['archipelago_relief']):
            for structure,continental,interaction,island in zip(a,b,c,d):self.assertAlmostEqual(structure,continental+interaction+island,places=8)

    def test_no_magic_no_sky_and_empty_population(self):
        w=generate_request({'seed':2,'overrides':{'size':17,'magic_enabled':0,'settlement_count':0}})
        self.assertEqual(w['sky']['islands'],[])
        self.assertEqual(w['settlements']['sites'],[])
        self.assertEqual(w['fisheries']['ports'],[])

    def test_early_phases_and_zero_archipelagos(self):
        for phase in (1,2,5,6,7,8):
            w=generate_request({'seed':3,'overrides':{'size':17,'phase':phase,'archipelago_count':0}})
            self.assertEqual(w['ocean_archipelagos'],[])
            self.assertNotIn('world_economy',w)
            json.dumps(w,allow_nan=False)

    def test_invalid_requests(self):
        for body in ({'recipe_version':2},{'seed':True},{'overrides':{'made_up':1}},
                     {'overrides':{'infernal_strength':float('nan')}},{'overrides':{'size':True}},
                     {'overrides':{'sky_clusters':2.5}},{'overrides':{'population_profile':'unknown'}},
                     {'overrides':{'temperature_offset':'cold'}}):
            with self.assertRaises(ValueError):generate_request(body)

    def test_defaults_dont_inherit_previous_overrides(self):
        a=generate_request({'seed':7,'overrides':{'size':17,'weave_strength':0.}})
        b=generate_request({'seed':7,'overrides':{'size':17}})
        self.assertEqual(b['recipe']['resolved']['weave_strength'],OPTIONS['weave_strength']['default'])
        self.assertNotEqual(a['layers']['ley_weave'],b['layers']['ley_weave'])

    def test_region_bias_respects_direct_prerequisite_override(self):
        a=generate_request({'seed':42,'overrides':{'size':17,'phase':6,'demonic_occurrence':1.}})
        b=generate_request({'seed':42,'overrides':{'size':17,'phase':6,'demonic_occurrence':1.,'infernal_strength':0.}})
        self.assertGreater(a['recipe']['resolved']['infernal_strength'],OPTIONS['infernal_strength']['default'])
        self.assertEqual(b['recipe']['resolved']['infernal_strength'],0.)
        self.assertNotIn('infernal_strength',b['recipe']['biases'])

    def test_city_ceiling_and_zero_fisheries(self):
        w=generate_request({'seed':42,'overrides':{'size':17,'settlement_count':2,'fish_productivity':0.}})
        self.assertLessEqual(len(w['settlements']['sites']),2)
        self.assertEqual(w['fisheries']['delivered_annual_food'],0.)
        self.assertTrue(all('fishing' not in p['role'] for p in w['fisheries']['ports']))

    def test_cold_seas_and_isolated_sky(self):
        w=generate_request({'seed':42,'overrides':{'size':17,'temperature_offset':-30,'air_reach':100.}})
        self.assertTrue(any(v>.9 for month in w['seasonal_environment']['months'] for row in month['water_ice'] for v in row))
        for route in w['transport']['routes']:
            if route['mode']=='air':self.assertLessEqual(route['length_m'],100.)

    def test_witch_huts_are_isolated_and_unsuitable_for_cities(self):
        for landmark in self.world['regions']['landmarks']:
            if landmark['kind']=='witch_hut':self.assertLess(landmark['conventional_suitability'],.55)


if __name__=='__main__':unittest.main()
