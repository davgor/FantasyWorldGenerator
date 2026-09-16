import copy
import unittest
from icarus_sim.terrain_profiles import profiles, get_profile, profile_options


HUMANS = {'human_maritime', 'human_desert', 'human_cold', 'human_large_island', 'human_rainforest', 'human_heartland'}


class CivilizationTests(unittest.TestCase):
    def test_malformed_entity_rules_are_rejected(self):
        from unittest.mock import patch
        for rule in ({'field':'misspelled','min':0},{'field':'temperature','min':float('nan')},{'all':[]},{'field':'biome','in':[]},{'field':'temperature','min':5,'max':1}):
            registry=profiles();registry['human_maritime']['civilization']['habitat']=rule
            with patch('icarus_sim.terrain_profiles.profiles',return_value=registry):
                with self.assertRaises(ValueError):get_profile('human_maritime')

    def test_independent_extension_and_cultural_region_layer(self):
        from unittest.mock import patch
        from icarus_sim.terrain_profiles import civilization_ids
        from icarus_sim.terrain_civilizations import eligible_civilizations
        from icarus_sim.terrain_world import generate_request
        registry=profiles();original=copy.deepcopy(registry['human_cold'])
        registry['human_maritime']['temperature_ideal']=35
        self.assertEqual(registry['human_cold'],original)
        registry['new_people']=copy.deepcopy(registry['elf'])
        registry['new_people']['name']='New people'
        with patch('icarus_sim.terrain_profiles.profiles',return_value=registry):
            self.assertIn('new_people',civilization_ids())
            self.assertEqual(get_profile('new_people')['name'],'New people')
        env=dict(biome=3,temperature=18,moisture=.6,maritime=0,landmass_area_m2=1e7,landmass_fraction=1,largest_landmass=True)
        self.assertIn('new_people',eligible_civilizations(env,registry))
        world=generate_request({'recipe_version':3,'overrides':{'size':17,'phase':12}})
        index={e['id']:e['region_index'] for e in world['civilizations']['entities']}
        for city in world['settlements']['sites']:
            self.assertEqual(world['layers']['civilization_region'][city['z']][city['x']],index[city['civilization_id']])

    def test_entities_are_complete_and_old_humans_are_retired(self):
        registry = profiles()
        self.assertTrue(HUMANS <= set(registry))
        for retired in ('human', 'highland', 'woodland'):
            self.assertNotIn(retired, registry)
            with self.assertRaises(ValueError):get_profile(retired)
        for key, record in registry.items():
            self.assertNotIn('extends', record)
            self.assertIn('temperature_ideal', record)
            self.assertEqual(get_profile(key)['schema_version'], 4)
        self.assertTrue(HUMANS <= {v['id'] for v in profile_options()})

    def test_environment_partition_and_fallback(self):
        from icarus_sim.terrain_civilizations import eligible_civilizations
        base = dict(biome=3, temperature=18., moisture=.6, maritime=0.,
                    landmass_area_m2=10e6, landmass_fraction=1., largest_landmass=True)
        cases = [({}, 'human_heartland'), ({'maritime':.8}, 'human_maritime'),
                 ({'biome':2}, 'human_desert'), ({'temperature':-4, 'maritime':.8}, 'human_cold'),
                 ({'biome':7,'moisture':.9}, 'human_rainforest'),
                 ({'landmass_area_m2':1.2e6,'landmass_fraction':.1,'largest_landmass':False}, 'human_large_island')]
        for updates, expected in cases:
            with self.subTest(expected=expected):
                env = dict(base, **updates)
                self.assertEqual(HUMANS & set(eligible_civilizations(env)), {expected})
        self.assertEqual(HUMANS & set(eligible_civilizations(dict(base, landmass_area_m2=1e4, landmass_fraction=.01, largest_landmass=False))), {'human_heartland'})

    def test_zero_single_many_and_deterministic_capitals(self):
        from icarus_sim.terrain_civilizations import classify_cities
        sites = [dict(id=3,node=3,population_profile='human_desert',suitability=.9),
                 dict(id=1,node=1,population_profile='human_desert',suitability=.9),
                 dict(id=2,node=2,population_profile='human_desert',suitability=.7),
                 dict(id=4,node=4,population_profile='human_desert',suitability=.4),
                 dict(id=5,node=5,population_profile='elf',suitability=.1)]
        classify_cities(sites)
        self.assertEqual({s['node']:s['city_class'] for s in sites}, {1:'capital',3:'medium',2:'medium',4:'small',5:'capital'})
        reverse = list(reversed(copy.deepcopy(sites)))
        classify_cities(reverse)
        self.assertEqual({s['node']:s['city_class'] for s in sites}, {s['node']:s['city_class'] for s in reverse})
        empty=[];classify_cities(empty);self.assertEqual(empty,[])
        classify_cities(sites[2:4])
        self.assertEqual(sites[2]['city_class'],'capital')

    def test_generated_world_identity_replay_and_versions(self):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import advance_age_request
        request={'recipe_version':3,'seed':42,'overrides':{'size':17}}
        a=generate_request(request);b=generate_request(request)
        self.assertEqual(a['settlements'],b['settlements'])
        self.assertEqual(a['generator_version'],16)
        self.assertEqual(a['settlements']['version'],14)
        self.assertEqual(a['civilizations']['version'],2)
        all_sites=a['settlements']['sites']+a.get('sky',{}).get('settlements',[])
        self.assertTrue(all(s['population_profile'] not in ('human','highland','woodland') for s in all_sites))
        for group in {s['population_profile'] for s in a['settlements']['sites']}:
            members=[s for s in a['settlements']['sites'] if s['population_profile']==group]
            self.assertEqual(sum(s['city_class']=='capital' for s in members),1)
        retired=copy.deepcopy(a);retired['generator_version']=8
        with self.assertRaises(ValueError):advance_age_request({'api_version':1,'world':retired})
        empty=generate_request({'recipe_version':3,'overrides':{'size':17,'settlement_count':0,'magic_enabled':0}})
        self.assertEqual(empty['settlements']['sites'],[])


if __name__ == '__main__':unittest.main()
