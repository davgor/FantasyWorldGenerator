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

    def test_compiler_rejects_a_brief_whose_only_ground_is_tombstoned(self):
        """A tombstoned id stays a legal selector; a brief with nothing else is the error.

        The first two cases are what the tombstone forbids - art commissioned for a surface no
        world renders. The third is the guard: 1 and 6 alongside reachable ground still compile,
        so this check cannot be satisfied by banning the id outright.
        """
        from unittest.mock import patch
        from fantasy_world_generator.asset_list import _production_assets
        root = Path(__file__).resolve().parents[1]
        source = (root/'Contracts/catalogues/world-assets.json').read_text()
        for override in ({'biome_ids': [6], 'biome_variant_ids': []},
                         {'biome_ids': [], 'biome_variant_ids': ['tundra.weave']}):
            data = json.loads(source)
            data['assets'][0].update(override)
            with patch('fantasy_world_generator.asset_list._load', return_value=data):
                with self.assertRaises(ValueError, msg=override):_production_assets()
        data = json.loads(source)
        data['assets'][0].update({'biome_ids': [1, 4, 6], 'biome_variant_ids': []})
        with patch('fantasy_world_generator.asset_list._load', return_value=data):
            self.assertEqual(_production_assets()[0]['selectors']['biome_ids'], [1, 4, 6])

    def test_no_production_brief_is_commissioned_for_tombstoned_ground(self):
        """The shipped catalogue names 1 and 6 nowhere, and the cold ids that exist carry art.

        Before user ruling 0.2 this was the other way round: biome 1 carried 40 selectors and
        biome 6 nine, while 15, 16 and 17 - the three that actually occur - had none between
        them. The second half of this test is the part that would silently rot.
        """
        from icarus_sim.terrain_biome_catalogue import UNREACHABLE_BIOMES
        root = Path(__file__).resolve().parents[1]
        catalogue = json.loads((root/'Contracts/catalogues/world-assets.json').read_text())
        counts = {}
        for row in catalogue['assets']:
            for biome in row.get('biome_ids') or ():
                counts[biome] = counts.get(biome, 0) + 1
        self.assertEqual(sorted(UNREACHABLE_BIOMES), [1, 6])
        for tombstoned in sorted(UNREACHABLE_BIOMES):
            self.assertNotIn(tombstoned, counts, f'biome {tombstoned} is tombstoned but still commissions art')
        for cold in (15, 16, 17):
            self.assertGreater(counts.get(cold, 0), 0, f'biome {cold} occurs in worlds and must carry art')

    def test_no_production_brief_is_commissioned_for_tombstoned_variant_ground(self):
        """The same ruling, applied to the other selector field, which the first pass missed.

        `biome_ids` was cleaned and `biome_variant_ids` was not, so nineteen shipped rows went on
        naming `tundra.infernal` and `snow.infernal` - 38 selectors against two of the 24 variant
        identities the compiler marks `unreachable`. Every one of those rows already named
        `cold_tundra.infernal` and `land_ice.infernal`, so the substitution wave 1 applied to the
        core ids collapsed here to a strip: the reachable cold ground the brief depicts was
        already in the list.

        Both halves are load-bearing. The first fails if a dead variant returns. The second fails
        if someone "cleans up" by deleting the cold selectors instead of the dead ones, which
        would satisfy the first half while removing the only infernal art cold ground has.
        """
        from icarus_sim.terrain_biome_catalogue import biome_catalogue, reachable_biome_catalogue
        root = Path(__file__).resolve().parents[1]
        catalogue = json.loads((root/'Contracts/catalogues/world-assets.json').read_text(encoding='utf-8'))
        dead = {v['id'] for v in biome_catalogue()} - {v['id'] for v in reachable_biome_catalogue()}
        self.assertEqual(len(dead), 24)
        self.assertEqual({v.split('.')[0] for v in dead}, {'tundra', 'snow'})

        counts = {}
        for row in catalogue['assets']:
            for variant in row.get('biome_variant_ids') or ():
                self.assertIn(variant, {v['id'] for v in biome_catalogue()}, row['id'])
                counts[variant] = counts.get(variant, 0) + 1
        named = sorted(dead & set(counts))
        self.assertEqual(named, [], f'tombstoned variants still commission art: {named}')
        for cold in ('cold_tundra.infernal', 'land_ice.infernal', 'boreal_forest.infernal'):
            self.assertEqual(counts.get(cold, 0), 19,
                             f'{cold} is the reachable ground those 19 briefs depict')
