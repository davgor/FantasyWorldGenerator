import json
from pathlib import Path
import tempfile
import unittest
from fantasy_world_generator.asset_list import compile_asset_list
from fantasy_world_generator.cli import main
from icarus_sim.terrain_history import NATURAL_BIOMES, biome_catalogue


class CurrentBiomeAssetsTests(unittest.TestCase):
    def test_current_assets_have_only_natural_and_named_variant_selectors(self):
        document = compile_asset_list()
        self.assertEqual(document['schema_version'], 2)
        self.assertEqual(document['recipe_version'], 3)
        assets = {a['id']: a for a in document['assets']}
        variants = {b['id'] for b in biome_catalogue()}
        for old in (9, 10, 11, 12, 14):self.assertNotIn(f'terrain.biome.{old:03d}', assets)
        for biome in NATURAL_BIOMES:self.assertIn(f'terrain.biome.{biome:03d}', assets)
        for biome in biome_catalogue():self.assertIn(biome['asset_id'], assets)
        for asset in assets.values():
            self.assertTrue(set(asset['selectors'].get('biome_ids', [])) <= set(NATURAL_BIOMES), asset['id'])
            self.assertTrue(set(asset['selectors'].get('biome_variant_ids', [])) <= variants, asset['id'])
        self.assertEqual(assets['production.mat-026']['selectors']['biome_variant_ids'], ['marsh.umbral'])

    def test_cli_defaults_to_clean_world(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'world.json'
            self.assertEqual(main(['generate', '--seed', '42', '--size', '17', '--phase', '10', '--output', str(path)]), 0)
            world = json.loads(path.read_text())
            self.assertEqual(world['recipe']['version'], 3)
            self.assertEqual(world['terrain']['version'], 6)

    def test_catalogue_copies_and_schema_taxonomy_do_not_drift(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'Contracts/catalogues/world-assets.json').read_bytes()
        for relative in ('Sim/fantasy_world_generator/world_asset_requirements.json', 'docs/catalogue/world-assets/manifest.json'):
            self.assertEqual(source, (root/relative).read_bytes())
        schema = json.loads((root/'Contracts/schemas/world-output.schema.json').read_text())
        self.assertEqual(set(schema['$defs']['naturalBiome']['properties']['id']['enum']), set(NATURAL_BIOMES))
        self.assertEqual(set(schema['$defs']['magicalBiome']['properties']['id']['enum']), {b['id'] for b in biome_catalogue()})

    def test_compiler_rejects_retired_or_unknown_production_selectors(self):
        from unittest.mock import patch
        from fantasy_world_generator.asset_list import _production_assets
        root = Path(__file__).resolve().parents[1]
        for field, value in [('biome_ids', [9]), ('biome_variant_ids', ['forest.unknown'])]:
            data = json.loads((root/'Contracts/catalogues/world-assets.json').read_text())
            data['assets'][0][field] = value
            with patch('fantasy_world_generator.asset_list._load', return_value=data):
                with self.assertRaises(ValueError):_production_assets()
