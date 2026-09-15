import unittest
from icarus_sim.terrain_nests import profiles, suitability

class NestRulesTests(unittest.TestCase):
    def test_catalogue_coverage(self):
        import json
        from pathlib import Path
        catalogue=json.loads((Path(__file__).resolve().parents[2]/'docs/catalogue/creatures.json').read_text(encoding='utf-8'))['creatures']
        self.assertEqual({p['name'] for p in profiles()}, {p['name'] for p in catalogue})

    def test_water_and_magic_are_requirements(self):
        p=next(p for p in profiles() if p['name']=='Kraken')
        self.assertEqual(suitability(p, {'medium':'land','temperature':12})[0],0)
        p=next(p for p in profiles() if p['name']=='Glacier dragons')
        self.assertEqual(suitability(p, {'medium':'land','temperature':30})[0],0)
        self.assertEqual(suitability(p, {'medium':'land','temperature':-10})[0],0)

class NestWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_world import generate_request
        cls.world=generate_request({'seed':42,'overrides':{'size':33}})

    def test_replay_and_isolation(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_lab import generate,Config
        a=self.world
        self.assertEqual(a['beast_nests'],generate(Config(**a['config']))['beast_nests'])
        b=generate_request({'seed':42,'overrides':{'size':33,'nest_variation':8}})
        self.assertNotEqual(a['beast_nests']['sites'],b['beast_nests']['sites'])
        for k in ['layers','sky','settlements','world_economy']:self.assertEqual(a[k],b[k])

    def test_constraints_and_finite(self):
        import json
        from icarus_sim.terrain_nests import distance
        w=self.world;nests=w['beast_nests']['sites'];self.assertTrue(nests)
        self.assertLessEqual(len(nests),120)
        self.assertEqual(len({(s['layer'],s['node']) for s in nests}),len(nests))
        pp={p['id']:p for p in profiles()};r=w['effective_config']['globe_radius']
        json.dumps(w['beast_nests'],allow_nan=False)
        for s in nests:
            self.assertGreaterEqual(s['suitability'],.3)
            if s['layer']=='surface':
                wt=w['layers']['water_type'][s['z']][s['x']]
                self.assertEqual(wt==1,pp[s['species_id']]['medium']=='marine')
                if pp[s['species_id']]['medium'] in ['land','shore']:self.assertEqual(wt,0)
            for t in nests:
                if s['id']!=t['id'] and s['species_id']==t['species_id'] and s['layer']==t['layer']:
                    self.assertGreaterEqual(distance(s['direction'],t['direction'],r)+1e-5,s['spacing_m'])
            for t in w['settlements']['sites']:
                if s['layer']=='surface':self.assertGreaterEqual(distance(s['direction'],t['direction'],r)+1e-5,250)
        self.assertEqual(sum(d['placed'] for d in w['beast_nests']['diagnostics']),len(nests))

    def test_disabled_and_real_only(self):
        from icarus_sim.terrain_world import generate_request
        for override in [{'nest_limit':0},{'nest_density':0}]:
            w=generate_request({'seed':42,'overrides':{'size':33,**override}})
            self.assertEqual(w['beast_nests']['sites'],[])
        w=generate_request({'seed':42,'overrides':{'size':33,'nest_fantasy':0}})
        self.assertTrue(w['beast_nests']['sites'])
        self.assertTrue(all(s['real'] for s in w['beast_nests']['sites']))

    def test_phase_gate(self):
        from icarus_sim.terrain_world import generate_request
        w=generate_request({'seed':42,'overrides':{'size':33,'phase':6}})
        self.assertNotIn('beast_nests',w)
