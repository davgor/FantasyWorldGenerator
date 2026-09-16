import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def write_linked_fixture(path, data):
    from icarus_sim.civilization_registry import BUILDING_SECTIONS
    raw=copy.deepcopy(data)
    buildings=raw.pop('building_catalogue_metadata')
    for key in BUILDING_SECTIONS:buildings[key]=raw.pop(key)
    path.with_name('buildings.json').write_text(json.dumps(buildings))
    entities=raw.pop('entities')
    raw['civilization_order']=list(entities)
    for parent in raw['parent_races'].values():parent['civilizations']={}
    for key,entity in entities.items():
        race=entity.pop('parent_race_id')
        raw['parent_races'][race]['civilizations'][key]=entity
    path.write_text(json.dumps(raw))


class MasterRegistryTests(unittest.TestCase):
    def test_parent_races_are_explicit_validated_and_exported(self):
        from icarus_sim.civilization_registry import load_registry,validate_registry
        from icarus_sim.terrain_civilizations import civilization_report
        from icarus_sim.civilization_registry import REGISTRY_PATH
        raw=json.loads(REGISTRY_PATH.read_text())
        self.assertNotIn('entities',raw)
        self.assertIn('gnome',raw['parent_races']['dwarf']['civilizations'])
        self.assertIn('human_maritime',raw['parent_races']['human']['civilizations'])
        data=load_registry()
        self.assertEqual(set(data['parent_races']),{'human','elf','dwarf'})
        expected={key:('human' if key.startswith('human_') else 'dwarf' if key in ('dwarf','gnome','hill_dwarf','frosthold_dwarf') else 'elf') for key in data['entities']}
        self.assertEqual({k:v['parent_race_id'] for k,v in data['entities'].items()},expected)
        report=civilization_report([])
        self.assertEqual({e['id']:e['parent_race_id'] for e in report['entities']},expected)
        for invalid in (None,'unknown'):
            bad=copy.deepcopy(data);bad['entities']['gnome']['parent_race_id']=invalid
            with self.assertRaises(ValueError):validate_registry(bad)
        bad=copy.deepcopy(data);del bad['entities']['gnome']['parent_race_id']
        with self.assertRaises(ValueError):validate_registry(bad)

    def test_nested_registry_rejects_duplicates_and_bad_order(self):
        from icarus_sim import civilization_registry as registry
        original=json.loads(registry.REGISTRY_PATH.read_text())
        self.assertEqual(list(registry.load_registry()['entities']),original['civilization_order'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'civilizations.json'
            path.with_name('buildings.json').write_bytes(registry.REGISTRY_PATH.with_name('buildings.json').read_bytes())
            for mode in ('duplicate','order'):
                raw=copy.deepcopy(original)
                if mode=='duplicate':raw['parent_races']['elf']['civilizations']['gnome']=copy.deepcopy(raw['parent_races']['dwarf']['civilizations']['gnome'])
                else:raw['civilization_order'].pop()
                path.write_text(json.dumps(raw))
                with patch.object(registry,'REGISTRY_PATH',path):
                    with self.assertRaises(ValueError):registry.load_registry()

    def test_empty_feature_bindings_disable_feature(self):
        from icarus_sim.terrain_settlements import _coerce_feature_count, _profile_fits_feature
        feature = _coerce_feature_count({'base': 1, 'profiles': []}, 'test')
        self.assertFalse(_profile_fits_feature(feature, 'gnome'))

    def test_master_owns_entities_buildings_and_measurements(self):
        from icarus_sim.civilization_registry import load_registry
        data=load_registry()
        self.assertEqual(data['schema_version'],6)
        self.assertEqual(len(data['entities']),12)
        self.assertIn('human_maritime',data['entities'])
        self.assertEqual(data['city_classification']['medium_suitability_min'],.65)
        self.assertEqual(sum(len(b['structures']) for b in data['structure_blocks']['common']['blocks']),80)
        for entity in data['entities'].values():
            self.assertIn('population',entity)
            self.assertIn('settlement',entity)
            self.assertIn('economy',entity)
            self.assertIn('sky',entity)
            self.assertIn('presentation',entity)
            self.assertNotIn('extends',entity['population'])

    def test_json_only_entity_drives_profiles_rules_and_building_assets(self):
        from icarus_sim import civilization_registry as registry
        from icarus_sim.terrain_profiles import civilization_ids,get_profile
        from icarus_sim.terrain_civilizations import eligible_civilizations
        from fantasy_world_generator.asset_list import compile_asset_list
        data=registry.load_registry()
        entity=copy.deepcopy(data['entities']['gnome'])
        entity['population']['name']='Copper folk'
        entity['population']['land_per_city_km2']=.05
        entity['population']['civilization']['habitat']={}
        entity['settlement']['world_habitat']={}
        data['entities']['copper_folk']=entity
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'civilizations.json';write_linked_fixture(path, data)
            with patch.object(registry,'REGISTRY_PATH',path):
                self.assertIn('copper_folk',civilization_ids())
                self.assertEqual(get_profile('copper_folk')['name'],'Copper folk')
                self.assertIn('copper_folk',eligible_civilizations(dict(biome=3,temperature=18,moisture=.6,maritime=0,landmass_area_m2=1e7,landmass_fraction=1,largest_landmass=True)))
                self.assertEqual(registry.entity_rules('copper_folk')['economy']['fishing_reach_multiplier'],entity['economy']['fishing_reach_multiplier'])
                refs=[r for a in compile_asset_list()['assets'] if a['source']=='simulation.building_packs' for r in a['metadata']['references']]
                self.assertTrue(any('copper_folk' in r['civilization_ids'] for r in refs))
                from icarus_sim.terrain_world import generate_request
                world=generate_request({'recipe_version':3,'seed':42,'overrides':{'size':17,'phase':12,'population_profile':'copper_folk'}})
                self.assertTrue(world['settlements']['sites'])
                self.assertEqual({s['population_profile'] for s in world['settlements']['sites']},{'copper_folk'})

    def test_registry_change_rejects_old_age_state(self):
        from icarus_sim import civilization_registry as registry
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_history import advance_age_request
        world=generate_request({'recipe_version':3,'overrides':{'size':17}})
        data=registry.load_registry();data['revision']+=1
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'civilizations.json';write_linked_fixture(path, data)
            with patch.object(registry,'REGISTRY_PATH',path):
                with self.assertRaisesRegex(ValueError,'registry changed'):
                    advance_age_request({'api_version':1,'world':world})

    def test_invalid_registry_and_cross_references_fail_early(self):
        from icarus_sim.civilization_registry import load_registry,validate_registry
        original=load_registry()
        for field,value in [('schema_version',999),('revision',0)]:
            data=copy.deepcopy(original);data[field]=value
            with self.assertRaises(ValueError):validate_registry(data)
        data=copy.deepcopy(original);data['entities']['gnome']['buildings']['packs']['unknown-pack']=[]
        with self.assertRaises(ValueError):validate_registry(data)
        data=copy.deepcopy(original);data['entities']['gnome']['economy']['fishing_reach_multiplier']=float('nan')
        with self.assertRaises(ValueError):validate_registry(data)
        data=copy.deepcopy(original);data['city_classification']['medium_suitability_min']=2
        with self.assertRaises(ValueError):validate_registry(data)

    def test_classification_threshold_is_data_driven(self):
        from icarus_sim import civilization_registry as registry
        from icarus_sim.terrain_civilizations import classify_cities
        data=registry.load_registry();data['city_classification']['medium_suitability_min']=.8
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'civilizations.json';write_linked_fixture(path, data)
            with patch.object(registry,'REGISTRY_PATH',path):
                sites=[dict(node=0,population_profile='gnome',suitability=.9),dict(node=1,population_profile='gnome',suitability=.7)]
                classify_cities(sites)
                self.assertEqual([s['city_class'] for s in sites],['capital','small'])


if __name__=='__main__':unittest.main()
