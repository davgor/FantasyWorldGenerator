import json
import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_humans import culture_groups, allocate_access, exchange_food, farming_potential


class HumanHinterlandTests(unittest.TestCase):
    def test_adaptation_needs_water_and_trade_needs_routes(self):
        natural,adapted=farming_potential(2,28,.1,.05,50,1)
        self.assertGreater(adapted,natural)
        self.assertEqual(farming_potential(2,28,.1,.05,-1,1)[0],farming_potential(2,28,.1,.05,-1,1)[1])
        cores=[{'site_id':0,'food_supply':30.,'food_demand':10.,'material_supply':30.},
               {'site_id':1,'food_supply':0.,'food_demand':10.,'material_supply':30.},
               {'site_id':2,'food_supply':0.,'food_demand':10.,'material_supply':30.}]
        shipments=exchange_food(cores,[{'from':0,'to':1,'cost':1000}])
        self.assertEqual(len(shipments),1)
        self.assertAlmostEqual(cores[1]['food_deficit'],0)
        self.assertEqual(cores[2]['food_deficit'],10)
        self.assertGreater(shipments[0]['sent'],shipments[0]['delivered'])
        self.assertLessEqual(cores[0]['food_exports'],20)
        self.assertAlmostEqual(shipments[0]['sent'],shipments[0]['delivered']+shipments[0]['lost'])
        self.assertLessEqual(cores[1]['trade_material_cost'],cores[1]['material_supply'])
    def test_cultures_follow_links_not_numbering(self):
        links=[{'from':0,'to':2,'cost':40}, {'from':2,'to':1,'cost':200}]
        self.assertEqual(culture_groups(4,links,100),[0,1,0,3])
        self.assertEqual(culture_groups(4,links,300),[0,0,0,3])

    def test_access_respects_barriers_and_single_ownership(self):
        graph=[[(1,1)],[(0,1),(2,1)],[(1,1)],[]]
        distance,owner,parent=allocate_access(graph,[(0,4),(2,7)],lambda i,j,d:d)
        self.assertEqual(owner,[4,4,7,-1])
        self.assertEqual(parent[1],0)
        self.assertEqual(distance[1],1)

    def test_hinterland_invariants_and_stage_isolation(self):
        cfg=Config(shape='globe',tectonics=1,size=33,phase=9)
        result=generate(cfg); previous=generate(replace(cfg,phase=8))
        for key in previous['layers']:
            self.assertEqual(result['layers'][key],previous['layers'][key])
        self.assertEqual(result['settlements'],previous['settlements'])
        self.assertEqual(result['roads'],previous['roads'])
        human=result['humans'];self.assertTrue(human['cores']);self.assertTrue(human['hamlets'])
        self.assertTrue(all(s['kind']=='city' and s['name'].endswith(' City') for s in result['settlements']['sites']))
        all_sites=human['hamlets']+human['fortresses']
        nodes=[s['node'] for s in all_sites]+[s['node'] for s in result['settlements']['sites']]
        self.assertEqual(len(nodes),len(set(nodes)))
        core_ids={s['site_id'] for s in human['cores']}
        for site in all_sites:
            self.assertIn(site['core_id'],core_ids)
            self.assertEqual(site['access_nodes'][0],site['node'])
            self.assertEqual(site['access_nodes'][-1],result['settlements']['sites'][site['core_id']]['node'])
            for node in site['access_nodes']:
                x,z=result['water']['nodes'][node]
                self.assertEqual(result['layers']['water_type'][z][x],0)
            from icarus_sim.terrain_erosion import sphere_grid
            from icarus_sim.terrain_settlements import road_cost_function
            points,_,graph=sphere_grid(cfg.size,result['effective_config']['globe_radius'])
            def vals(key):return [result['layers'][key][z][x] for x,z in points]
            cost=road_cost_function(points,vals('water_type'),vals('height'),vals('flood_risk'),vals('rain_river'),cfg)
            for i,j in zip(site['access_nodes'],site['access_nodes'][1:]):
                d=next(d for k,d in graph[i] if k==j)
                self.assertIsNotNone(cost(i,j,d))
        self.assertLessEqual(sum(h['worked_area_km2'] for h in human['hamlets']),result['water']['dry_km2']+1e-6)
        for core in human['cores']:
            expected=sum(h['delivered_food'] for h in human['hamlets'] if h['core_id']==core['site_id'])
            self.assertAlmostEqual(core['food_supply'],expected)
            self.assertAlmostEqual(core['food_deficit'],max(0,core['food_demand']-expected-core['food_imports']+core['food_exports']))
        self.assertTrue(all(c['architecture_style_id'] is None for c in human['cultures']))
        for key in ('culture_region','food_potential','hamlet_catchment'):
            for row in result['layers'][key]:self.assertEqual(row[0],row[-1])
            self.assertEqual(len(set(result['layers'][key][0])),1)
        again=generate(cfg)
        self.assertEqual(human,again['humans'])
        json.dumps(result,allow_nan=False)

    def test_culture_control_changes_groups_without_moving_sites(self):
        cfg=Config(shape='globe',tectonics=1,size=33,phase=9)
        a=generate(cfg);b=generate(replace(cfg,culture_link_cost=1))
        self.assertEqual(a['settlements'],b['settlements'])
        self.assertEqual(a['roads'],b['roads'])
        self.assertEqual([h['node'] for h in a['humans']['hamlets']],[h['node'] for h in b['humans']['hamlets']])
        self.assertEqual(len(b['humans']['cultures']),len(b['humans']['cores']))

    def test_empty_and_disabled_rural_generation(self):
        cfg=Config(shape='globe',tectonics=1,size=17,phase=9,settlement_count=0)
        human=generate(cfg)['humans']
        for key in ('cores','cultures','hamlets','fortresses'):self.assertEqual(human[key],[])
        human=generate(replace(cfg,settlement_count=3,hamlets_per_core=0,fortress_count=0))['humans']
        self.assertEqual(human['hamlets'],[]);self.assertEqual(human['fortresses'],[])
        self.assertTrue(all(c['food_supply']==0 for c in human['cores']))

    def test_validation(self):
        for kwargs in ({'hamlets_per_core':9},{'fortress_count':-1},{'support_reach':0},
                       {'culture_link_cost':float('nan')},{'urban_food_demand':-1}):
            with self.assertRaises(ValueError):Config(**kwargs)
