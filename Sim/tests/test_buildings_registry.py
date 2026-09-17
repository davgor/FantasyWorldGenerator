import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_sim import civilization_registry as registry


class BuildingsRegistryTests(unittest.TestCase):
    def test_buildings_live_in_linked_file_with_neutral_ids(self):
        raw = json.loads(registry.REGISTRY_PATH.read_text(encoding='utf-8'))
        self.assertEqual(raw['building_catalogue']['path'], 'buildings.json')
        self.assertNotIn('structure_blocks', raw)
        self.assertNotIn('building_packs', raw)
        self.assertNotIn('layout_profiles', raw)
        buildings = json.loads(registry.REGISTRY_PATH.with_name('buildings.json').read_text(encoding='utf-8'))
        rows = [s for b in buildings['structure_blocks']['common']['blocks'] for s in b['structures']]
        self.assertEqual(len(rows), 80)
        rural = [s for b in buildings['structure_blocks']['rural']['blocks'] for s in b['structures']]
        self.assertEqual(len(rural), 13)
        self.assertTrue(all(s['id'].startswith('building.hamlet_') for s in rural))
        self.assertEqual(buildings['housing_profiles']['hamlet_house']['id'], 'building.hamlet_house')
        for key in raw['civilization_order']:
            for tier in registry.CITY_BLOCKS:
                halls = [r for r in registry.city_plan(key, tier)['buildings'] if r['structure_id']=='building.guildhall']
                self.assertEqual(len(halls), 1)
                self.assertEqual(halls[0]['staffing_totals']['workers']['target'], 2)
            hamlet = registry.hamlet_plan(key)
            self.assertEqual(hamlet['settlement_block'], 'hamlet')
            self.assertTrue(any(r['structure_id']=='building.hamlet_well' for r in hamlet['buildings']))

    def test_linked_edit_reloads_and_changes_replay_identity(self):
        raw = json.loads(registry.REGISTRY_PATH.read_text(encoding='utf-8'))
        source = registry.REGISTRY_PATH.with_name('buildings.json')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'civilizations.json'
            path.write_text(json.dumps(raw))
            linked = Path(folder)/'buildings.json'
            linked.write_bytes(source.read_bytes())
            with patch.object(registry, 'REGISTRY_PATH', path):
                before = registry.registry_identity()
                buildings = json.loads(linked.read_text(encoding='utf-8'))
                buildings['revision'] += 1
                well = buildings['structure_blocks']['common']['blocks'][0]['structures'][0]
                well['staffing']['roles'][0].update(minimum=7, target=7, maximum=7)
                linked.write_text(json.dumps(buildings))
                self.assertNotEqual(before, registry.registry_identity())
                plan = registry.city_plan('dwarf', 'small_city')
                self.assertEqual(next(r for r in plan['buildings'] if r['structure_id']=='building.well')['staffing_totals']['workers']['target'], 7)
                buildings['schema_version'] = 999
                linked.write_text(json.dumps(buildings))
                with self.assertRaises(ValueError): registry.load_registry()
                linked.unlink()
                with self.assertRaises(ValueError): registry.load_registry()

    def test_link_cannot_escape_sibling_file_or_embed_competing_definitions(self):
        original = json.loads(registry.REGISTRY_PATH.read_text(encoding='utf-8'))
        source = registry.REGISTRY_PATH.with_name('buildings.json').read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'civilizations.json'
            path.with_name('buildings.json').write_bytes(source)
            for value in ('../buildings.json', 'https://example.com/buildings.json'):
                raw = json.loads(json.dumps(original))
                raw['building_catalogue']['path'] = value
                path.write_text(json.dumps(raw))
                with patch.object(registry, 'REGISTRY_PATH', path):
                    with self.assertRaises(ValueError): registry.load_registry()
            original['structure_blocks'] = {}
            path.write_text(json.dumps(original))
            with patch.object(registry, 'REGISTRY_PATH', path):
                with self.assertRaises(ValueError): registry.load_registry()
