import unittest
import json
from dataclasses import replace
from icarus_sim.terrain_lab import Config,generate


class PeoplesTests(unittest.TestCase):
    def test_seeded_coexistence_and_budget(self):
        cfg=Config(auto_parameters=1,population_profile='mixed',size=65)
        a=generate(cfg);b=generate(cfg)
        self.assertEqual(a['settlements'],b['settlements'])
        sites=a['settlements']['sites'];counts={p:sum(s['population_profile']==p for s in sites) for p in ('human','dwarf','elf')}
        self.assertEqual(sum(counts.values()),len(sites))
        self.assertLessEqual(sum(s['population_estimate'] for s in sites),a['population_budget']['world_cap'])
        self.assertEqual(len({s['node'] for s in sites}),len(sites))
        for s in sites:
            self.assertEqual(s['population_estimate'],s['urban_population_estimate']+s['rural_population_estimate'])
            if s['population_profile']=='elf':self.assertIn(a['layers']['biome'][s['z']][s['x']],(4,7,15))
            if s['population_profile']=='dwarf':self.assertGreaterEqual(s['resource_potential'],.5)
        for core in a['humans']['cores']:
            self.assertEqual(core['population_profile'],sites[core['site_id']]['population_profile'])
        for culture in a['humans']['cultures']:
            self.assertEqual({sites[i]['population_profile'] for i in culture['city_ids']},{culture['population_profile']})
        for college in a['magic']['colleges']:
            self.assertEqual(college['population_profile'],sites[college['core_id']]['population_profile'])
        json.dumps(a,allow_nan=False)
        for rural in a['humans']['hamlets']+a['humans']['fortresses']:
            self.assertEqual(rural['population_profile'],sites[rural['core_id']]['population_profile'])

    def test_mixed_does_not_change_physical_world(self):
        a=generate(Config(auto_parameters=1,population_profile='human',size=17))
        b=generate(Config(auto_parameters=1,population_profile='mixed',size=17))
        for key in ('height','biome','rainfall','magic_density'):self.assertEqual(a['layers'][key],b['layers'][key])

    def test_missing_habitats_leave_allowance_unused(self):
        from icarus_sim.terrain_settlements import add_settlements
        result=generate(Config(auto_parameters=1,population_profile='mixed',size=17,phase=6))
        for key,value in (('biome',2),('slope',0),('tpi',0)):
            result['layers'][key]=[[value]*17 for _ in range(17)]
        cfg=replace(Config(**result['config']),phase=7)
        add_settlements(result,cfg)
        self.assertTrue(result['settlements']['sites'])
        self.assertEqual({s['population_profile'] for s in result['settlements']['sites']},{'human'})
        self.assertEqual(result['population_budget']['shares']['dwarf'],0)
        self.assertEqual(result['population_budget']['shares']['elf'],0)

    def test_zero_city_request_does_not_invent_specialists(self):
        result=generate(Config(shape='globe',tectonics=1,population_profile='mixed',size=17,settlement_count=0))
        self.assertEqual(result['settlements']['sites'],[])
        self.assertEqual(result['population_budget']['allocated'],0)
        self.assertEqual(result['humans']['cores'],[])

    def test_capacity_scales_with_area_and_suitability_without_minimum(self):
        from icarus_sim.terrain_settlements import habitat_capacity
        self.assertEqual(habitat_capacity([1e6]*12,[1.]*12,list(range(12)),2),6)
        self.assertEqual(habitat_capacity([1e6]*12,[.5]*12,list(range(12)),2),3)
        self.assertEqual(habitat_capacity([1e6]*12,[1.]*12,[],2),0)
        self.assertEqual(habitat_capacity([1e5],[1.],[0],2),0)

    def test_life_capacity_needs_productive_land_and_does_not_double_count(self):
        from icarus_sim.terrain_settlements import life_capacity
        cap,allowances=life_capacity([1e6],{'human':[1.]})
        both,split=life_capacity([1e6],{'human':[1.],'elf':[1.]})
        self.assertEqual(cap,both)
        self.assertEqual(sum(split.values()),both)
        self.assertEqual(life_capacity([1e6],{'human':[0.]})[0],0)
        self.assertGreater(cap,life_capacity([1e6],{'human':[.2]})[0])
        self.assertEqual(life_capacity([2e6],{'human':[1.]})[0],cap*2)

    def test_default_world_population_balance_regression(self):
        # Calibration fixture, not a requirement imposed on arbitrary worlds.
        r=generate(Config(auto_parameters=1,population_profile='mixed',size=129,seed=42))
        counts=r['population_budget']['placed_cities']
        self.assertGreaterEqual(counts['human'],4)
        self.assertGreaterEqual(counts['dwarf']+counts['elf'],1)
        self.assertLessEqual(r['population_budget']['allocated'],r['population_budget']['world_cap'])

    def test_default_mountain_can_support_a_dwarven_hold(self):
        r=generate(Config(auto_parameters=1,population_profile='mixed',size=129,seed=42))
        dwarves=[s for s in r['settlements']['sites'] if s['population_profile']=='dwarf']
        self.assertTrue(dwarves)
        for site in dwarves:
            self.assertGreaterEqual(site['resource_potential'],.5)
        self.assertLessEqual(r['population_budget']['allocated'],r['population_budget']['world_cap'])

    def test_support_cannot_cross_an_impassable_edge(self):
        from icarus_sim.terrain_settlements import reachable_support
        graph=[[(1,1)],[(0,1),(2,1)],[(1,1)]]
        self.assertEqual(reachable_support(graph,[0],lambda i,j,d:None if {i,j}=={1,2} else d,10),[True,True,False])
        self.assertEqual(reachable_support(graph,[],lambda i,j,d:d,10),[False]*3)
