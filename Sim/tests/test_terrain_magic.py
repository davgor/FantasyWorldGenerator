import unittest
from dataclasses import replace
from icarus_sim.terrain_lab import Config,generate
from icarus_sim.terrain_magic import arc_distance,magic_biome,college_eligible
from icarus_sim.terrain_biomes import marsh_suitable


class MagicTests(unittest.TestCase):
    def test_arc_distance_and_fantasy_rules(self):
        import math
        a=(1,0,0);b=(0,1,0)
        self.assertAlmostEqual(arc_distance((2**-.5,2**-.5,0),a,b),0,places=7)
        self.assertAlmostEqual(arc_distance((0,0,1),a,b),math.pi/2)
        self.assertEqual(magic_biome(4,.9,.9,.1,.8,20),9)
        self.assertEqual(magic_biome(4,.9,.1,.9,.8,20),10)
        self.assertEqual(magic_biome(8,1,1,1,1,20),8)
        self.assertEqual(magic_biome(0,1,1,1,1,20),0)
        self.assertEqual(magic_biome(2,.7,.1,.1,.15,25),11)
        self.assertEqual(magic_biome(4,.5,.1,.9,.6,20),12)
        self.assertEqual(magic_biome(13,.7,.05,.1,.8,20),14)
        self.assertEqual(magic_biome(13,.1,.05,.1,.8,20),13)
        self.assertTrue(marsh_suitable(.8,20,2,70,1))
        for args in ((.1,20,2,70,1),(.8,-5,2,70,1),(.8,20,30,70,1),(.8,20,2,800,1),(.8,20,2,70,50)):
            self.assertFalse(marsh_suitable(*args))

    def test_college_density_cannot_override_human_safety(self):
        args=dict(density=.8,hazard=.1,limit=.4,slope=4,temp=20,fresh=100,flood=.1,suitability=.8,water=0)
        self.assertTrue(college_eligible(**args))
        for change in ({'hazard':.5},{'water':2},{'slope':25},{'fresh':-1},{'suitability':.2},{'density':.1}):
            self.assertFalse(college_eligible(**dict(args,**change)))

    def test_magic_is_deterministic_and_does_not_change_ground(self):
        cfg=Config(shape='globe',tectonics=1,size=33)
        a=generate(cfg);b=generate(replace(cfg,magic_enabled=0));c=generate(cfg)
        for key in ('height','water_surface','rainfall'):
            self.assertEqual(a['layers'][key],b['layers'][key])
        self.assertEqual(a['magic'],c['magic'])
        self.assertTrue(a['magic']['edges'])
        self.assertTrue(a['magic']['colleges'])
        self.assertNotIn('magic',b)
        for key in ('magic_density','magic_hazard','magic_growth'):
            for row in a['layers'][key]:
                self.assertEqual(row[0],row[-1]);self.assertTrue(all(0<=v<=1 for v in row))
            self.assertEqual(len(set(a['layers'][key][0])),1)
        for site in a['settlements']['sites']+a['humans']['hamlets']+a['humans']['fortresses']+a['magic']['colleges']:
            self.assertLessEqual(a['layers']['magic_hazard'][site['z']][site['x']],cfg.human_magic_limit)
        paths=[road['nodes'] for road in a['roads']['routes']]+[s['access_nodes'] for s in a['humans']['hamlets']+a['humans']['fortresses']+a['magic']['colleges']]
        for path in paths:
            for node in path:
                x,z=a['water']['nodes'][node]
                self.assertLessEqual(a['layers']['magic_hazard'][z][x],cfg.human_magic_limit)
        for c in a['magic']['colleges']:
            x,z=c['x'],c['z'];l=a['layers']
            self.assertTrue(college_eligible(l['magic_density'][z][x],l['magic_hazard'][z][x],cfg.human_magic_limit,
                l['slope'][z][x],l['temperature'][z][x],l['freshwater_distance'][z][x],l['flood_risk'][z][x],l['suitability'][z][x],l['water_type'][z][x]))
            self.assertEqual(c['access_nodes'][-1],a['settlements']['sites'][c['core_id']]['node'])
        stable=generate(replace(cfg,magic_instability=0))
        self.assertEqual(stable['layers']['magic_density'],a['layers']['magic_density'])
        self.assertTrue(all(v==0 for row in stable['layers']['magic_hazard'] for v in row))

    def test_controls_validate(self):
        for change in ({'magic_enabled':2},{'ley_nodes':2},{'ley_width':0},{'human_magic_limit':2},{'college_count':20}):
            with self.assertRaises(ValueError):Config(**change)
