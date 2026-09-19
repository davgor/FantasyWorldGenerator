import json
from pathlib import Path
import tempfile
import unittest

from fantasy_world_generator.asset_list import compile_asset_list
from fantasy_world_generator.cli import main, world_document
from icarus_sim.terrain_biome_catalogue import natural_catalogue


class AssetListTests(unittest.TestCase):
    def test_building_references_name_standalone_civilizations(self):
        from icarus_sim.terrain_profiles import civilization_ids
        known=set(civilization_ids());seen=set()
        for asset in compile_asset_list()['assets']:
            if asset['source']!='simulation.building_packs':continue
            for reference in asset['metadata']['references']:
                self.assertTrue(set(reference['civilization_ids']) <= known)
                seen.update(reference['civilization_ids'])
        self.assertEqual(seen,known)
        self.assertNotIn('human',seen)

    def test_all_potential_state_sources_are_included(self):
        document = compile_asset_list()
        assets = {item["id"]: item for item in document["assets"]}
        self.assertEqual(document["summary"]["by_source"]["simulation.biomes"], len(natural_catalogue()))
        self.assertEqual(document["summary"]["by_source"]["simulation.creature_profiles"], 638)
        self.assertEqual(document["summary"]["by_source"]["simulation.building_packs"], 84)
        self.assertEqual(document["summary"]["by_source"]["simulation.city_planner"], 96)
        self.assertEqual(document["summary"]["by_source"]["production.world_asset_catalogue"], 492)
        self.assertIn("creature.kraken", assets)
        self.assertIn("terrain.biome.017", assets)
        self.assertIn("building.building_market_stall_generic", assets)
        self.assertTrue(any(item["kind"] == "plant" for item in assets.values()))

    def test_history_potential_states_are_exhaustive(self):
        from icarus_sim.terrain_history import biome_catalogue
        assets={a['id']:a for a in compile_asset_list()['assets']}
        for biome in biome_catalogue():
            self.assertIn(biome['asset_id'],assets)
            self.assertEqual(assets[biome['asset_id']]['selectors']['magic_school'],biome['magic_school'])
        self.assertIn('marker.city_ruins',assets)

    def test_output_is_deterministic_and_ids_are_unique(self):
        first = compile_asset_list()
        second = compile_asset_list()
        self.assertEqual(first, second)
        ids = [item["id"] for item in first["assets"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        json.dumps(first, allow_nan=False)

    def test_cli_writes_asset_list(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "assets.json"
            self.assertEqual(main(["asset-list", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), compile_asset_list())

    def test_world_document_has_versioned_envelope(self):
        world = world_document({"seed": 42, "overrides": {"size": 17, "phase": 1}})
        self.assertEqual(world["schema"], "fantasy-world-generator.world")
        self.assertEqual(world["schema_version"], 2)
        self.assertEqual(world["recipe"]["version"], 3)
        json.dumps(world, allow_nan=False)

    def test_published_biomes_match_a_generated_layered_world(self):
        world = world_document({"seed": 42, "overrides": {"size": 17, "phase": 10}})
        expected = {
            (item["selectors"]["biome_ids"][0], item["name"], tuple(item["metadata"]["display_color_rgb"]))
            for item in compile_asset_list()["assets"]
            if item["source"] == "simulation.biomes"
        }
        actual = {(item["id"], item["name"], tuple(item["color"])) for item in world["terrain"]["biomes"]}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
