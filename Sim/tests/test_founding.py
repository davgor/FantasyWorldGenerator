import unittest
from icarus_sim.founding import found_cities

class FoundingTests(unittest.TestCase):
    def run_founding(self,percent=100):
        parents={'human':{'founding_participation_percent':percent},'dwarf':{'founding_participation_percent':percent}}
        owners={'a':'human','b':'human','c':'dwarf'}
        candidates={'a':[0,1,2,3],'b':[4,5],'c':[6,7,8]}
        scores={k:[1-i*.01 for i in range(9)] for k in owners}
        return found_cities(42,parents,owners,{'a':3,'b':1,'c':2},candidates,scores,lambda a,b:abs(a-b)*100,50,1000)
    def test_rounds_unused_cultures_and_replay(self):
        sites,report=self.run_founding()
        self.assertEqual((sites,report),self.run_founding())
        first=[s for s in sites if s['founding_turn']==1]
        self.assertEqual(len(first),2)
        self.assertEqual({s['parent_race_id'] for s in first},{'human','dwarf'})
        humans=[s for s in sites if s['parent_race_id']=='human']
        self.assertEqual(humans[1]['population_profile'],'b')
        self.assertGreater(humans[1]['founding_turn'],1)
        self.assertEqual(len(sites),6)
        self.assertEqual(report['stop_reason'],'capacity_target_reached')
    def test_zero_participation_keeps_initial_capitals_only(self):
        sites,report=self.run_founding(0)
        self.assertEqual(len(sites),2)
        self.assertEqual(report['stop_reason'],'no_eligible_expansion')

    def test_survivors_do_not_bypass_zero_participation(self):
        survivors=[dict(node=0,population_profile='a',parent_race_id='human',founding_turn=1,founding_capital=True)]
        sites,report=found_cities(1,{'human':{'founding_participation_percent':0}},{'a':'human'},{'a':2},{'a':[0,1]},{'a':[1,1]},lambda a,b:100,50,1000,survivors)
        self.assertEqual(sites,survivors)
        self.assertEqual(report['stop_reason'],'no_eligible_expansion')

    def test_participation_bounds_are_validated(self):
        from icarus_sim.civilization_registry import load_registry,validate_registry
        for value in (-1,101,float('nan')):
            data=load_registry();data['parent_races']['human']['founding_participation_percent']=value
            with self.assertRaises(ValueError):validate_registry(data)

    def test_survivors_already_at_global_target_do_not_expand(self):
        survivors=[dict(node=0,population_profile='a',parent_race_id='human')]
        sites,_=found_cities(1,{'human':{'founding_participation_percent':100}},{'a':'human','b':'human'},{'a':0,'b':1},{'a':[],'b':[1]},{'a':[1,1],'b':[1,1]},lambda a,b:100,50,1000,survivors)
        self.assertEqual(sites,survivors)

    def test_parent_origins_are_in_opposing_hemispheres(self):
        owners={'a':'human','b':'elf','c':'dwarf'}
        parents={r:{'founding_participation_percent':100} for r in owners.values()}
        distances={(0,1):10,(0,2):120,(0,3):120,(2,3):120}
        distance=lambda a,b:0 if a==b else distances.get(tuple(sorted((a,b))),100)
        sites,report=found_cities(42,parents,owners,{k:1 for k in owners},{'a':[0],'b':[1,2],'c':[3]},{k:[1,.99,.8,.8] for k in owners},distance,1,180)
        self.assertEqual([s['node'] for s in sites],[0,2,3])
        for i,a in enumerate(sites):
            for b in sites[i+1:]:self.assertGreaterEqual(distance(a['node'],b['node']),90)
    def test_migration_records_ancestry_and_centuries(self):
        sites,report=self.run_founding()
        branch=next(s for s in sites if s['population_profile']=='b')
        self.assertEqual(branch['source_civilization_id'],'a')
        self.assertEqual(branch['migration_source_node'],0)
        self.assertTrue(branch['cultural_branch'])
        self.assertEqual(branch['founding_year'],(branch['founding_turn']-1)*250)

    def test_no_origin_separation_is_reported_without_relaxing_rule(self):
        sites,report=found_cities(1,{'human':{'founding_participation_percent':100},'elf':{'founding_participation_percent':100}},{'a':'human','b':'elf'},{'a':1,'b':1},{'a':[0],'b':[1]},{'a':[1,1],'b':[1,1]},lambda a,b:10,1,180)
        self.assertEqual(len(sites),1)
        self.assertTrue(any(e['status']=='no_separated_origin' for e in report['events']))
    def test_calendar_continues_without_survivors(self):
        sites,report=found_cities(1,{'human':{'founding_participation_percent':100}},{'a':'human'},{'a':1},{'a':[0]},{'a':[1]},lambda a,b:0,1,180,start_year=5000)
        self.assertEqual(sites[0]['founding_year'],5000)
        self.assertEqual(report['end_year'],5000)
