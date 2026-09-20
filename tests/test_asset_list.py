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
        self.assertEqual(document["summary"]["by_source"]["simulation.creature_profiles"], 680)
        self.assertEqual(document["summary"]["by_source"]["simulation.building_packs"], 84)
        self.assertEqual(document["summary"]["by_source"]["simulation.city_planner"], 96)
        self.assertEqual(document["summary"]["by_source"]["production.world_asset_catalogue"], 492)
        self.assertIn("creature.kraken", assets)
        self.assertIn("terrain.biome.017", assets)
        self.assertIn("building.building_market_stall_generic", assets)
        self.assertTrue(any(item["kind"] == "plant" for item in assets.values()))

    def test_every_key_location_archetype_has_a_marker_identity(self):
        """One marker per archetype, pinned to the catalogue rather than to a number.

        A hardcoded count would break every time a place is added, which trains people to bump
        it without looking. Pinning to the catalogue catches the thing that actually matters -
        markers silently going missing while the catalogue still lists them - and stays quiet
        when the catalogue legitimately grows.
        """
        from key_locations.catalogue import load

        document = load()
        assets = {item["id"]: item for item in compile_asset_list()["assets"]}
        for archetype in document["archetypes"]:
            marker = f"marker.key_location.{archetype['id']}"
            self.assertIn(marker, assets, f"{archetype['id']} is in the catalogue but has no asset identity")
            row = assets[marker]
            self.assertEqual(row["kind"], "marker")
            self.assertEqual(row["source"], "simulation.key_locations")
            self.assertEqual(row["selectors"]["key_location_kind"], archetype["id"])
            self.assertEqual(row["metadata"]["tier"], archetype["tier"])
        self.assertEqual(compile_asset_list()["summary"]["by_source"]["simulation.key_locations"],
                         len(document["archetypes"]),
                         "every archetype gets exactly one marker and nothing else claims that source")

    def test_tombstoned_surfaces_keep_their_identity_and_lose_their_claim(self):
        """User ruling 0.2: 1 tundra and 6 snow stop commissioning art without leaving the list.

        The count is pinned to the catalogue rather than hardcoded, so adding a fourteenth biome
        does not fail this, but tombstoning a third one does - that is a decision, not drift.
        """
        from icarus_sim.terrain_biome_catalogue import (biome_catalogue, reachable_natural_catalogue,
                                                        reachable_biome_catalogue, UNREACHABLE_BIOMES)
        assets = {item["id"]: item for item in compile_asset_list()["assets"]}
        self.assertEqual(UNREACHABLE_BIOMES, frozenset({1, 6}))
        for biome in natural_catalogue():
            expected = "supported" if biome["id"] not in UNREACHABLE_BIOMES else "unreachable"
            self.assertEqual(assets[biome["asset_id"]]["status"], expected, biome["asset_id"])
        for variant in biome_catalogue():
            expected = "supported" if variant["core_biome_id"] not in UNREACHABLE_BIOMES else "unreachable"
            self.assertEqual(assets[variant["asset_id"]]["status"], expected, variant["asset_id"])
        unreachable = [item for item in assets.values() if item["status"] == "unreachable"]
        self.assertEqual(len(unreachable),
                         (len(natural_catalogue()) - len(reachable_natural_catalogue()))
                         + (len(biome_catalogue()) - len(reachable_biome_catalogue())))
        self.assertEqual(len(unreachable), 26)
        # The identity survives: the native registry binds one slot per row and every world
        # document still names all thirteen in terrain['biomes'].
        self.assertIn("terrain.biome.001", assets)
        self.assertIn("terrain.mutation.snow.umbral", assets)

    def test_status_vocabulary_is_closed_and_matches_the_schema(self):
        """The `unreachable` claim was declarative: the schema took any non-empty string.

        Nothing outside the compiler reads `status`, so a typo - `unreachabe`, `Supported` -
        would have shipped through validate_repo, the registry build and the docs mirror without
        a single check noticing. The enum closes that, and this test checks it in both
        directions: a value the compiler emits but the enum omits fails, and a value the enum
        declares but nothing emits fails too, so the vocabulary cannot rot into a list of words
        that used to mean something. The third assertion is the one that matters - it proves the
        enum is enforced rather than decorative, which is exactly what this field was before.
        """
        import sys
        root = Path(__file__).resolve().parents[1]
        if str(root / 'tests') not in sys.path:
            sys.path.insert(0, str(root / 'tests'))
        from schema_subset import errors, validate

        schema = json.loads((root / 'Contracts/schemas/asset-list.schema.json').read_text(encoding='utf-8'))
        declared = schema['properties']['assets']['items']['properties']['status']['enum']
        self.assertEqual(len(declared), len(set(declared)), 'duplicate status in the enum')

        document = compile_asset_list()
        emitted = {item['status'] for item in document['assets']}
        self.assertEqual(emitted, set(declared),
                         'the compiler and the contract disagree about the status vocabulary')
        validate(document, schema)

        # Guard the guard: the enum must actually reject, or this whole test is theatre.
        # The control is the same one-row document with the status left alone, so the only
        # thing separating a clean validate from a reported error is the field under test.
        row = document['assets'][0]
        validate(dict(document, assets=[row]), schema)
        broken = list(errors(dict(document, assets=[dict(row, status='supprted')]), schema))
        self.assertEqual([e for e in broken if 'status' not in e], [],
                         'the control document was already invalid for some other reason')
        self.assertTrue([e for e in broken if 'status' in e],
                        'the schema accepted a status outside its own enum')

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
