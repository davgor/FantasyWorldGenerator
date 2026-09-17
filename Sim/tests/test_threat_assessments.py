import copy
import json
import unittest
from icarus_sim.terrain_world import generate_request


class ThreatAssessmentTests(unittest.TestCase):
    def test_shared_nest_pressure_matches_fate_weights(self):
        from icarus_sim.terrain_history import city_fate, fantasy_nest_threats, SCHOOLS
        city={'uid':'city','x':1,'z':1,'direction':[1.,0.,0.]}
        layers={'ley_'+s:[[0.]*3 for _ in range(3)] for s in SCHOOLS}
        nest={'id':'threat','name':'Threat','family':'infernal','layer':'surface','real':False,
              'direction':[1.,0.,0.],'spacing_m':300.}
        threats=fantasy_nest_threats(city,[nest],1000.)
        self.assertEqual(len(threats),1)
        self.assertAlmostEqual(threats[0]['weight'],.55)
        fate=city_fate(city,layers,[nest],1000,42,1,roll=0.,magic_enabled=False)
        self.assertEqual(fate['cause'],'monster')
        self.assertAlmostEqual(fate['evidence']['distance_m'],threats[0]['distance_m'])

    def test_assess_city_excludes_self_magic_and_caps(self):
        from icarus_sim.terrain_history import assess_city_threat, SCHOOLS
        city={'uid':'city','name':'Test','x':1,'z':1,'direction':[1.,0.,0.]}
        layers={'ley_'+s:[[0.]*3 for _ in range(3)] for s in SCHOOLS}
        layers['ley_fire'][1][1]=1.
        nest={'id':'n1','name':'Red dragon','family':'draconic','layer':'surface','real':False,
              'direction':[1.,0.,0.],'spacing_m':300.}
        report=assess_city_threat(city,layers,[nest],1000.)
        self.assertGreater(report['regional_threat'],0)
        self.assertLessEqual(report['regional_threat'],1)
        self.assertGreater(report['ley_pressure'],0)
        self.assertGreater(report['nest_pressure'],0)
        self.assertTrue(all(c['kind']!='self_magic' for c in report['contributors']))

    def test_pipeline_after_beasties_and_ages(self):
        from icarus_sim.terrain_history import materialize_stage
        from icarus_sim.terrain_lab import Config, generate
        world=generate_request({'recipe_version':3,'seed':42,'overrides':{'size':17}})
        self.assertIn('threat_assessments',world)
        self.assertEqual(world['threat_assessments']['version'],1)
        self.assertEqual(world['threat_assessments']['evaluated_after'],'age')
        self.assertEqual(world['threat_assessments']['age'],2)
        uids={c['uid'] for c in world['settlements']['sites']}
        self.assertEqual({c['city_uid'] for c in world['threat_assessments']['cities']},uids)
        for city in world['threat_assessments']['cities']:
            self.assertGreaterEqual(city['regional_threat'],0)
            self.assertLessEqual(city['regional_threat'],1)
        early=materialize_stage(world,12)
        self.assertNotIn('threat_assessments',early)
        beasts=materialize_stage(world,13)
        self.assertEqual(beasts['threat_assessments']['evaluated_after'],'beast_nests')
        self.assertIsNone(beasts['threat_assessments']['age'])
        age1=materialize_stage(world,14)
        self.assertEqual(age1['threat_assessments']['evaluated_after'],'age')
        self.assertEqual(age1['threat_assessments']['age'],1)
        age2=materialize_stage(world,15)
        self.assertEqual(age2['threat_assessments']['age'],2)
        again=generate(Config(**world['config']))
        self.assertEqual(world['threat_assessments'],again['threat_assessments'])
        json.dumps(world['threat_assessments'],allow_nan=False)

    def test_advance_age_refreshes_assessment(self):
        from icarus_sim.terrain_history import advance_age_request
        base=generate_request({'recipe_version':3,'seed':12,'overrides':{'size':17}})
        advanced=advance_age_request({'api_version':1,'world':base,'steps':1})
        self.assertEqual(advanced['threat_assessments']['evaluated_after'],'age')
        self.assertEqual(advanced['threat_assessments']['age'],3)
        self.assertEqual(len(advanced['threat_assessments']['cities']),
                         len(advanced['settlements']['sites']))
        again=advance_age_request({'api_version':1,'world':base,'steps':1})
        self.assertEqual(advanced['threat_assessments'],again['threat_assessments'])
