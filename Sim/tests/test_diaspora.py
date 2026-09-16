import unittest
from icarus_sim.founding import found_cities
class DiasporaTests(unittest.TestCase):
    def run_case(self,food=40):
        return found_cities(42,{'human':{'founding_participation_percent':0}},{'a':'human','b':'human','c':'human'}, {'a':1,'b':0,'c':0},{'a':[0],'b':[1],'c':[2]}, {k:[1,1,1] for k in ('a','b','c')},lambda a,b:abs(a-b)*900,50,2000,
                           diaspora_interval_years=1000,diaspora_bonus_per_parent=1,food_allowances={'a':40,'b':food,'c':food})
    def test_diaspora_waits_bypasses_participation_and_limits_bonus(self):
        sites,report=self.run_case()
        self.assertEqual((sites,report),self.run_case())
        self.assertEqual(len(sites),2)
        migrant=sites[-1]
        self.assertEqual(migrant['founding_year'],1000)
        self.assertTrue(migrant['diaspora'])
        self.assertIn(migrant['diaspora_reason'],('exile','religious_schism','expedition','magical_displacement'))
        self.assertEqual(migrant['migration_source_node'],0)
        self.assertEqual(report['diaspora_bonus_used'],['human'])
    def test_food_is_not_invented(self):
        sites,_=self.run_case(39)
        self.assertEqual(len(sites),1)

    def test_bonus_cannot_raise_target_above_city_ceiling(self):
        sites,report=found_cities(42,{'human':{'founding_participation_percent':0}},{'a':'human','b':'human'}, {'a':2,'b':0},{'a':[0,2],'b':[1]},{'a':[1,1,1],'b':[1,1,1]},lambda a,b:abs(a-b)*100,50,1000,food_allowances={'a':80,'b':40},city_limit=2)
        self.assertLessEqual(report['target_cities'],2)
    def test_survivor_bonus_and_used_cultures_are_not_reset(self):
        survivors=[dict(node=0,population_profile='a',parent_race_id='human',founding_year=1000)]
        sites,report=found_cities(42,{'human':{'founding_participation_percent':0}},{'a':'human','b':'human'}, {'a':1,'b':0},{'a':[0],'b':[1]},{'a':[1,1],'b':[1,1]},lambda a,b:100,50,1000,survivors=survivors,food_allowances={'a':40,'b':40},diaspora_bonus_used=['human'],used_civilizations=['a'])
        self.assertEqual(sites,survivors)
