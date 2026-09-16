"""Independent identity examples and exhaustive consumer asset traceability."""
import json
from pathlib import Path
import unittest

from fantasy_world_generator.taxonomy import resolve_terrain_identity, taxonomy_document
from fantasy_world_generator.asset_list import compile_asset_list
from icarus_sim.terrain_biome_catalogue import natural_catalogue, biome_catalogue


ROOT = Path(__file__).resolve().parents[1]


class PortableTaxonomyTests(unittest.TestCase):
    def test_independently_authored_conformance_cases(self):
        cases = json.loads((ROOT / 'Fixtures/taxonomy-v1.json').read_text())
        for case in cases['valid']:
            with self.subTest(case=case):
                self.assertEqual(resolve_terrain_identity(case['request']), case['expected'])
        for request in cases['invalid']:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    resolve_terrain_identity(request)

    def test_sparse_ids_and_every_potential_state_match_generator_and_assets(self):
        catalogue = taxonomy_document()
        self.assertEqual(catalogue['schools'],
                         ['weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air'])
        self.assertEqual([r['id'] for r in catalogue['natural_biomes']],
                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 15, 16, 17])
        assets = {row['id'] for row in compile_asset_list()['assets']}
        resolved = set()
        for row in natural_catalogue() + biome_catalogue():
            request = dict(taxonomy_version=1, recipe_version=3,
                           natural_biome_id=row.get('core_biome_id', row['id']),
                           magic_school=row.get('magic_school'))
            result = resolve_terrain_identity(request)
            self.assertEqual(result['core'], row['core'])
            self.assertEqual(result['asset_id'], row['asset_id'])
            self.assertIn(result['asset_id'], assets)
            resolved.add(result['asset_id'])
        self.assertEqual(len(resolved), 117)

    def test_rejects_noninteger_ids_versions_and_implicit_aliases(self):
        base = dict(taxonomy_version=1, recipe_version=3, natural_biome_id=13, magic_school=None)
        for key in ('taxonomy_version', 'recipe_version', 'natural_biome_id'):
            for value in (True, False, 1.0, None, '1', [], {}):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    resolve_terrain_identity(dict(base, **{key: value}))
        for school in ('holy', 'primordial', 'necrotic', 'nature', 'arcane', 'storm', 'Radiant', ' fire', '', 0, [], {}):
            with self.subTest(school=school), self.assertRaises(ValueError):
                resolve_terrain_identity(dict(base, magic_school=school))
        for retired in (9, 10, 11, 12, 14):
            with self.subTest(retired=retired), self.assertRaises(ValueError):
                resolve_terrain_identity(dict(base, natural_biome_id=retired))

    def test_requires_exact_request_fields_and_does_not_mutate_input(self):
        request = dict(taxonomy_version=1, recipe_version=3, natural_biome_id=13, magic_school='water')
        original = dict(request)
        resolve_terrain_identity(request)
        self.assertEqual(request, original)
        invalid = [None, [], 'marsh.water', dict(request, extra=1)]
        invalid.extend({k: v for k, v in request.items() if k != missing} for missing in request)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_terrain_identity(value)

    def test_caller_cannot_mutate_shared_taxonomy(self):
        first = taxonomy_document()
        first['schools'].clear()
        first['natural_biomes'][0]['core'] = 'changed'
        second = taxonomy_document()
        self.assertEqual(second['schools'][0], 'weave')
        self.assertEqual(second['natural_biomes'][0]['core'], 'ocean')
