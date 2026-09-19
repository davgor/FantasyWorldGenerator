import copy
import json
import unittest
from icarus_sim.terrain_world import generate_request


class HistoryTests(unittest.TestCase):
    def test_versioned_pipeline_and_replay(self):
        from icarus_sim.terrain_history import STAGES, materialize_stage
        from icarus_sim.terrain_lab import Config, generate
        world = generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})
        self.assertEqual(len(STAGES), 16)
        self.assertEqual(world['phases']['completed'], 16)
        self.assertEqual(len(world['history']['ages']), 2)
        for stage in (5, 6, 7, 8, 9, 10, 13, 14, 15):
            view = materialize_stage(world, stage)
            if stage < 10:
                self.assertNotIn('settlements', view)
            if stage < 13:
                self.assertNotIn('beast_nests', view)
            if stage == 9:
                self.assertIn('magic', view)
                self.assertNotIn('biome_variant', view['layers'])
        self.assertNotEqual(materialize_stage(world, 5)['layers']['height'], materialize_stage(world, 6)['layers']['height'])
        again = generate(Config(**world['config']))
        for key in ('layers', 'history', 'ruins', 'settlements'):
            self.assertEqual(world[key], again[key])
        json.dumps(world, allow_nan=False)
        for grid in world['layers'].values():
            for row in grid:
                self.assertEqual(row[0], row[-1])
            for row in (grid[0], grid[-1]):
                self.assertEqual(len(set(row)), 1)

    def test_every_natural_biome_has_every_school(self):
        from icarus_sim.terrain_history import biome_catalogue, SCHOOLS, NATURAL_BIOMES
        entries = biome_catalogue()
        self.assertEqual(len(entries), len(NATURAL_BIOMES) * len(SCHOOLS))
        self.assertEqual(len({e['id'] for e in entries}), len(entries))
        tomb = next(e for e in entries if e['name'] == 'Haunted tombs')
        self.assertEqual((tomb['core'], tomb['magic_school'], tomb['color']), ('desert', 'umbral', [72, 49, 35]))

    def test_event_reasons_and_self_destruction(self):
        from icarus_sim.terrain_history import city_fate
        city = {'uid': 'city-test', 'direction': [1, 0, 0], 'x': 1, 'z': 1}
        layers = {'ley_' + n: [[0.]*3 for _ in range(3)] for n in ('weave','umbral','infernal','radiant','fire','water','earth','air')}
        layers['ley_fire'][1][1] = 1
        fate = city_fate(city, layers, [], 1000, 42, 1, roll=0.)
        self.assertEqual(fate['cause'], 'fire')
        self.assertIn('flames', fate['reason'])
        layers['ley_fire'][1][1] = 0
        fate = city_fate(city, layers, [], 1000, 42, 1, roll=0.)
        self.assertEqual(fate['cause'], 'self_magic')
        self.assertEqual(fate['new_node_school'], 'weave')

    def test_nearby_infernal_and_aberrant_threats(self):
        from icarus_sim.terrain_history import city_fate, SCHOOLS
        city={'uid':'city','x':1,'z':1,'direction':[1,0,0]}
        layers={'ley_'+s:[[0.]*3 for _ in range(3)] for s in SCHOOLS}
        for family in ('infernal','aberrant','undead'):
            nest={'id':'threat','name':'Threat','family':family,'layer':'surface','real':False,'direction':[1,0,0],'spacing_m':300.}
            fate=city_fate(city,layers,[nest],1000,42,1,roll=0.,magic_enabled=False)
            self.assertIsNotNone(fate,family)
            self.assertEqual(fate['cause'],'monster')
            nest['direction']=[-1,0,0]
            self.assertIsNone(city_fate(city,layers,[nest],1000,42,1,roll=0.,magic_enabled=False))

    def test_abandoned_waterways(self):
        from icarus_sim.terrain_history import abandoned_waterways
        old = {'river': [[1,0,0]], 'water_type': [[0,2,0]], 'water_depth': [[0,20,0]]}
        new = {'river': [[0,0,1]], 'water_type': [[0,0,0]]}
        gorges, valleys = abandoned_waterways(old, new)
        self.assertEqual(gorges, [[1,0,0]])
        self.assertEqual(valleys, [[0,1,0]])

class LeylineTests(unittest.TestCase):
    def test_competing_strength_and_edits(self):
        from icarus_sim.terrain_leyline_history import dominant_school, edit_network
        self.assertIsNone(dominant_school({'fire':.2,'water':.01}))
        self.assertIsNone(dominant_school({'fire':.8,'water':.78}))
        self.assertEqual(dominant_school({'fire':.8,'water':.6}), 'fire')
        network={'nodes':[{'id':'n','direction':[1,0,0],'intensity':1.}], 'edges':[]}
        changed=edit_network(network,node_id='n',intensity=0.)
        self.assertEqual(network['nodes'][0]['intensity'],1.)
        self.assertEqual(changed['nodes'][0]['intensity'],0.)
        changed=edit_network(changed,new_node={'id':'new','direction':[0,1,0],'intensity':2.})
        self.assertEqual(len(changed['nodes']),2)
        for intensity in (float('nan'),-1,5,True):
            with self.assertRaises(ValueError):edit_network(network,node_id='n',intensity=intensity)
        with self.assertRaises(ValueError):edit_network(network,new_node={'id':'n','direction':[1,0,0],'intensity':1.})

    def test_independent_eight_networks_and_partial_stages(self):
        from icarus_sim.terrain_history import materialize_stage
        from icarus_sim.terrain_leyline_history import SCHOOLS, evaluate_networks, edit_network
        from icarus_sim.terrain_lab import Config
        body={'recipe_version':3,'seed':42,'overrides':{'size':17,'phase':9}}
        a=generate_request(body)
        b=generate_request({**body,'overrides':{**body['overrides'],'fire_strength':0.}})
        self.assertEqual(set(a['magic']['networks']),set(SCHOOLS))
        self.assertEqual(a['magic']['school_order'],list(SCHOOLS))
        self.assertEqual(len(a['magic']['groups']),3)
        for school in SCHOOLS:
            if school!='fire':self.assertEqual(a['layers']['ley_'+school],b['layers']['ley_'+school])
        for key in ('height','rainfall','natural_biome'):self.assertEqual(a['layers'][key],b['layers'][key])
        net=a['magic']['networks']['fire']
        self.assertGreater(len({node['intensity'] for node in net['nodes']}),1)
        a['magic']['networks']['fire']=edit_network(net,new_node={'id':'player-point','direction':[1,0,0],'intensity':4.})
        before=copy.deepcopy(a['layers']['ley_water'])
        evaluate_networks(a,Config(**a['config']))
        self.assertEqual(before,a['layers']['ley_water'])
        for stage in (5,6,7,8):
            partial=generate_request({**body,'overrides':{'size':17,'phase':stage}})
            self.assertEqual(partial['layers'],materialize_stage(b,stage)['layers'])

    def test_ruins_remove_hamlets_and_create_nodes(self):
        from unittest.mock import patch
        from icarus_sim.terrain_history import age_transition
        from icarus_sim.terrain_lab import Config
        w=generate_request({'recipe_version':3,'seed':42,'overrides':{'size':33,'phase':13}})
        self.assertTrue(w['settlements']['sites'], 'Fixture must contain cities')
        old=copy.deepcopy(w['settlements']['sites'])
        node_count=len(w['magic']['networks']['weave']['nodes'])
        fate={'cause':'self_magic','reason':'Test magical catastrophe','evidence':{},'probability':1.,'roll':0.,'new_node_school':'weave'}
        # Wars are silenced so this stays a test of the fate path: a city lost to a
        # neighbour takes the war's own key-point rule instead of the patched fate, and
        # would leave the school its ground already held rather than a Weave node.
        with patch('icarus_sim.terrain_wars.resolve_wars',return_value=([],{})), \
             patch('icarus_sim.terrain_history.city_fate',return_value=fate):
            age_transition(w,Config(**w['config']),1)
        self.assertEqual(len(w['ruins']),len(old))
        self.assertEqual(len(w['magic']['networks']['weave']['nodes']),node_count+len(old))
        self.assertEqual({r['source_culture'] for r in w['ruins']},{s['source_culture'] for s in old})
        self.assertFalse({s['node'] for s in w['settlements']['sites']} & {s['node'] for s in old})
        active={s['id'] for s in w['settlements']['sites']}
        for h in w['humans']['hamlets']:self.assertIn(h['core_id'],active)
        for port in w['fisheries']['ports']:self.assertIn(port['core_id'],active)
        for ruin in w['ruins']:self.assertEqual(ruin['kind'],'ruins')
        json.dumps(w,allow_nan=False)

class AgeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world=generate_request({'recipe_version':3,'seed':12,'overrides':{'size':17}})

    def test_advance_existing_world_and_recalculate_nests(self):
        from icarus_sim.terrain_history import advance_age_request
        before=copy.deepcopy(self.world)
        a=advance_age_request({'api_version':1,'world':self.world,'steps':2})
        b=advance_age_request({'api_version':1,'world':self.world,'steps':2})
        self.assertEqual(self.world,before)
        self.assertEqual([age['age'] for age in a['history']['ages']],[1,2,3,4])
        for key in ('history','magic','beast_nests','settlements','ruins','layers'):
            self.assertEqual(a[key],b[key])
        self.assertEqual(a['layers']['height'],before['layers']['height'])
        self.assertEqual(a['history']['ages'][-1]['order'][0],'nests before fates')
        self.assertEqual(a['history']['ages'][-1]['order'][-1],'threat assessment')
        self.assertEqual(a['beast_nests']['evaluated_age'],4)
        from icarus_sim.terrain_history import materialize_stage
        view=materialize_stage(a,len(a['build_stages']))
        self.assertEqual(view['layers'],a['layers'])
        self.assertEqual(view['history'],a['history'])
        json.dumps(a,allow_nan=False)

    def test_survivors_do_not_create_extra_new_city_capacity(self):
        from unittest.mock import patch
        from collections import Counter
        from icarus_sim.terrain_history import advance_age_request
        initial=Counter(c['population_profile'] for c in self.world['settlements']['sites'])
        with patch('icarus_sim.terrain_history.city_fate',return_value=None):
            after=advance_age_request({'api_version':1,'world':self.world,'steps':5})
        placed=Counter(c['population_profile'] for c in after['settlements']['sites'])
        for people,count in placed.items():
            self.assertLessEqual(count,max(initial[people],after['population_budget']['requested_cities'][people]))

    def test_api_player_key_point_and_invalid_requests(self):
        from icarus_sim.terrain_history import advance_age_request
        request={'api_version':1,'world':self.world,'leyline_edits':[{'school':'fire','new_node':{'id':'player-volcano','direction':[1,0,0],'intensity':4.}}]}
        advanced=advance_age_request(request)
        self.assertIn('player-volcano',{n['id'] for n in advanced['magic']['networks']['fire']['nodes']})
        self.assertEqual(advanced['history']['operations'][-1]['leyline_edits'],request['leyline_edits'])
        for bad in ({}, {'api_version':2,'world':self.world}, {'api_version':1,'world':self.world,'steps':True}, {'api_version':1,'world':self.world,'steps':0}):
            with self.assertRaises(ValueError):advance_age_request(bad)
        bad=copy.deepcopy(self.world);bad['layers']['height'][0][0]=float('nan')
        with self.assertRaises(ValueError):advance_age_request({'api_version':1,'world':bad})
