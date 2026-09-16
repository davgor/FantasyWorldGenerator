import copy
import unittest
from icarus_sim.terrain_profiles import get_profile
from icarus_sim.terrain_humans import farming_potential
from icarus_sim.civilization_registry import entity_rules,city_plan,load_registry,validate_registry


class ArcticCivilizationTests(unittest.TestCase):
    def test_comfort_does_not_change_crops(self):
        a=get_profile('human_cold');b=copy.deepcopy(a);b['temperature_ideal']=-15
        self.assertEqual(farming_potential(5,-5,.5,0,50,.5,a),farming_potential(5,-5,.5,0,50,.5,b))

    def test_small_cold_quotas_preserve_food_limit(self):
        from icarus_sim.terrain_settlements import city_capacity
        p=get_profile('human_cold')
        self.assertEqual(p['land_per_city_km2'],.9)
        self.assertEqual(p['minimum_founding_residents'],30)
        self.assertEqual(city_capacity(2.192,94,p),2)
        self.assertEqual(city_capacity(100,29,p),0)
        self.assertEqual(city_capacity(100,60,p),2)

    def test_diaspora_uses_entity_minimum(self):
        from icarus_sim.founding import found_cities
        def run(food):
            return found_cities(1,{'human':{'founding_participation_percent':100}}, {'cold':'human'},
                {'cold':0},{'cold':[0]},{'cold':[1]},lambda a,b:0,1,100,
                food_allowances={'cold':food},minimum_residents={'cold':30})[0]
        self.assertEqual(len(run(30)),1)
        self.assertEqual(run(29),[])
        sites,_=found_cities(1,{'human':{'founding_participation_percent':100}}, {'cold':'human'},
            {'cold':10},{'cold':list(range(10))},{'cold':[1]*10},lambda a,b:abs(a-b)*100,1,1000,
            food_allowances={'cold':59},minimum_residents={'cold':30})
        self.assertEqual(len(sites),1)

    def test_frosthold_habitat_and_all_presets(self):
        from icarus_sim.terrain_civilizations import matches
        rules=entity_rules('frosthold_dwarf')
        self.assertEqual(rules['parent_race_id'],'dwarf')
        env=dict(abs_latitude=65,temperature=-8,resource=.7,biome=5,tpi=10,slope=15,height=50,maritime=.5)
        self.assertTrue(matches(rules['settlement']['world_habitat'],env))
        self.assertFalse(matches(rules['settlement']['world_habitat'],dict(env,abs_latitude=20)))
        self.assertFalse(matches(rules['settlement']['world_habitat'],dict(env,resource=.1)))
        for tier in ('small','medium','capital'):
            ids={r['structure_id'] for r in city_plan('frosthold_dwarf',tier+'_city')['buildings']}
            self.assertTrue({'building.guildhall','building.fuel_depot'}<=ids)
        from fantasy_world_generator.asset_list import compile_asset_list
        assets=compile_asset_list()['assets'];ids={a['id'] for a in assets}
        for tier in ('small','medium','capital'):
            self.assertTrue(all(r['structure_id'] in ids for r in city_plan('frosthold_dwarf',tier+'_city')['buildings']))
        refs=[r for a in assets if a['source']=='simulation.building_packs' for r in a['metadata']['references']]
        self.assertTrue(any('frosthold_dwarf' in r['civilization_ids'] for r in refs))

    def test_winter_fisheries_are_bounded_and_exclusive(self):
        from icarus_sim.terrain_society import fishing_access_factor
        self.assertEqual(fishing_access_factor(1,0),0)
        self.assertEqual(fishing_access_factor(1,.25),.25)
        self.assertEqual(fishing_access_factor(0,.25),1)
        for ice in (0,.3,.7,1):self.assertTrue(0<=fishing_access_factor(ice,.25)<=1)
        from icarus_sim.terrain_settlements import life_capacity
        total,shares=life_capacity([1e6],{'cold':[.4],'frosthold':[.4]})
        self.assertEqual(total,40);self.assertEqual(sum(shares.values()),40)

    def test_new_fields_validated(self):
        d=load_registry();d['entities']['human_cold']['population']['minimum_founding_residents']=0
        with self.assertRaises(ValueError):validate_registry(d)

        d=load_registry();d['entities']['human_cold']['economy']['winter_fishing_fraction']=1.1
        with self.assertRaises(ValueError):validate_registry(d)

    def test_actual_winter_harvest_and_seasonal_crop_independence(self):
        from unittest.mock import patch
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_society import add_world_society
        from icarus_sim.terrain_seasons import add_seasonal_food
        from icarus_sim.terrain_lab import Config
        request={'seed':42,'overrides':{'size':33,'phase':12,'population_profile':'human_cold'}}
        world=generate_request(request);cfg=Config(**world['config'])
        a=copy.deepcopy(world);b=copy.deepcopy(world)
        original=get_profile
        def colder(key):
            p=original(key);p['temperature_ideal']-=20;return p
        add_seasonal_food(a,cfg)
        with patch('icarus_sim.terrain_profiles.get_profile',side_effect=colder):add_seasonal_food(b,cfg)
        self.assertEqual(a['seasonal_food']['models'],b['seasonal_food']['models'])
        for month in world['seasonal_environment']['months']:month['water_ice']=[[1]*33 for _ in range(33)]
        a=copy.deepcopy(world);b=copy.deepcopy(world)
        add_world_society(a,cfg)
        def ordinary(key):
            r=entity_rules(key);r['economy']['winter_fishing_fraction']=0;return r
        with patch('icarus_sim.terrain_society.entity_rules',side_effect=ordinary):add_world_society(b,cfg)
        self.assertGreater(a['fisheries']['delivered_annual_food'],0)
        self.assertEqual(b['fisheries']['delivered_annual_food'],0)
        self.assertLessEqual(a['fisheries']['delivered_annual_food'],a['fisheries']['potential_annual_food']*.25+1e-9)
