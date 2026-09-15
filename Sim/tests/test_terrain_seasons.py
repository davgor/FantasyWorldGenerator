import unittest
from icarus_sim.terrain_seasons import simulate_food, seasonal_harvest

class SeasonalFoodTests(unittest.TestCase):
    def test_storage_and_transport_conserve_food(self):
        cities=[{'harvest':[10.]*12,'demand':1.,'storage':30.,'spoilage':.02},
                {'harvest':[0.]*12,'demand':3.,'storage':10.,'spoilage':.02}]
        roads=[{'from':0,'to':1,'capacity':[2.]*12,'efficiency':.8}]
        result=simulate_food(cities,roads,years=2)
        for month in result['months']:
            self.assertAlmostEqual(month['opening']+month['harvest'],month['closing']+month['consumed']+month['spoiled']+month['overflow']+month['transit_loss'])
            self.assertLessEqual(sum(t['sent'] for t in month['shipments']),2.)
            self.assertGreater(month['cities'][1]['shortage'],0)
            self.assertTrue(all(c['closing']>=0 for c in month['cities']))

    def test_no_road_no_imports_and_no_free_initial_reserve(self):
        cities=[{'harvest':[10.]*12,'demand':1.,'storage':30.,'spoilage':0.},
                {'harvest':[0.]*12,'demand':1.,'storage':10.,'spoilage':0.}]
        r=simulate_food(cities,[],years=1)
        self.assertEqual(r['months'][0]['opening'],0)
        self.assertTrue(all(m['cities'][1]['shortage']==1 for m in r['months']))

    def test_reserves_bridge_a_lean_season(self):
        base={'harvest':[12.]+[0.]*11,'demand':1.,'spoilage':0.}
        stored=simulate_food([{**base,'storage':12.}],[],years=1)
        bare=simulate_food([{**base,'storage':0.}],[],years=1)
        self.assertEqual(sum(m['cities'][0]['shortage'] for m in stored['months']),0)
        self.assertGreater(sum(m['cities'][0]['shortage'] for m in bare['months']),0)

    def test_hemispheres_reverse_seasons(self):
        north=seasonal_harvest(20,.5,50,18,24)
        south=seasonal_harvest(20,.5,-50,18,24)
        for i in range(12):self.assertAlmostEqual(north[i],south[(i+6)%12])
        self.assertNotEqual(north[0],north[6])

    def test_integrated_report_is_deterministic_and_preserves_city_proposals(self):
        import json
        from dataclasses import replace
        from icarus_sim.terrain_lab import Config,generate
        cfg=Config(auto_parameters=1,population_profile='mixed',size=33)
        a=generate(cfg);b=generate(cfg);earlier=generate(replace(cfg,phase=8))
        self.assertTrue(a['seasonal_food']['cities'])
        self.assertEqual(a['seasonal_food'],b['seasonal_food'])
        self.assertEqual(a['settlements'],earlier['settlements'])
        self.assertNotIn('seasonal_food',earlier)
        self.assertEqual(len(a['seasonal_food']['months']),48)
        json.dumps(a,allow_nan=False)
        for month in a['seasonal_food']['months']:
            for city in month['cities']:
                self.assertAlmostEqual(city['opening']+city['harvest']+city['imports'],city['closing']+city['consumed']+city['spoiled']+city['overflow']+city['exports'])

    def test_material_budget_and_zero_efficiency_limit_trade(self):
        cities=[{'harvest':[10.]*12,'demand':1.,'storage':30.,'spoilage':0.},
                {'harvest':[0.]*12,'demand':3.,'storage':10.,'spoilage':0.,'transport_budget':.25}]
        roads=[{'from':0,'to':1,'capacity':[10.]*12,'efficiency':.8,'price':2.}]
        r=simulate_food(cities,roads,years=1)
        self.assertTrue(all(m['cities'][1]['material_spent']<=.25+1e-9 for m in r['months']))
        roads[0]['efficiency']=0
        self.assertTrue(all(not m['shipments'] for m in simulate_food(cities,roads,years=1)['months']))

    def test_donor_does_not_reserve_food_it_cannot_store(self):
        cities=[{'harvest':[2.]*12,'demand':1.,'storage':0.,'spoilage':0.},
                {'harvest':[0.]*12,'demand':1.,'storage':0.,'spoilage':0.}]
        roads=[{'from':0,'to':1,'capacity':[2.]*12,'efficiency':1.}]
        self.assertEqual(simulate_food(cities,roads,years=1)['months'][0]['cities'][1]['shortage'],0)
