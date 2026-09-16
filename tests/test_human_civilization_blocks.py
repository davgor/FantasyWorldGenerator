"""Contract checks for the reusable design catalogue, not runtime placement."""
import json
import math
from pathlib import Path
import unittest

from fantasy_world_generator.asset_list import compile_asset_list
from icarus_sim.civilization_registry import section


ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "Contracts/catalogues/human-civilization-blocks.json"


class HumanCivilizationBlockTests(unittest.TestCase):
    def test_measurements_reserve_structure_and_access_space(self):
        data = section("structure_blocks")["common"]
        self.assertEqual(data["unit"], "metres")
        self.assertEqual(data["measurement_status"], "provisional_design_defaults")
        by_id = {s["id"]: s for b in data["blocks"] for s in b["structures"]}
        for row in by_id.values():
            size = row["dimensions_m"]
            clearance = row["clearance_m"]
            plot = row["plot_m"]
            self.assertGreater(size["width"], 0)
            self.assertGreater(size["depth"], 0)
            self.assertGreaterEqual(size["height"], 0)
            for value in [*size.values(), *clearance.values(), *plot.values()]:
                self.assertIsInstance(value, (int, float))
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0)
            self.assertEqual(plot["width"], size["width"] + clearance["left"] + clearance["right"])
            self.assertEqual(plot["depth"], size["depth"] + clearance["front"] + clearance["rear"])
            self.assertIn(row["geometry_type"], {"building", "compound", "open_area", "linear_segment"})
            self.assertIn(row["access"]["mode"], {"pedestrian", "cart", "service"})
            self.assertGreater(row["access"]["minimum_clear_width_m"], 0)
        self.assertEqual(by_id["building.street"]["geometry_type"], "linear_segment")
        self.assertEqual(by_id["building.bridge"]["geometry_type"], "linear_segment")
        self.assertEqual(by_id["building.wall"]["geometry_type"], "linear_segment")
        self.assertEqual(by_id["building.market_square"]["geometry_type"], "open_area")
        self.assertEqual(by_id["building.market_square"]["dimensions_m"]["height"], 0)

    def test_city_functions_are_retrievable_without_housing(self):
        data = section("structure_blocks")["common"]
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["library_id"], "common")
        self.assertEqual(data["status"], "design_only")
        self.assertEqual(data["deferred_blocks"], ["housing"])
        blocks = {b["id"]: b for b in data["blocks"]}
        self.assertEqual(set(blocks), {
            "water_sanitation", "food", "trade", "crafts", "civic",
            "health", "faith", "defense", "streets_transport",
            "knowledge_magic", "hinterland",
        })
        rows = [s for b in data["blocks"] for s in b["structures"]]
        ids = [s["id"] for s in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith("building.") for i in ids))
        self.assertTrue(all(s["status"] == "planned" for s in rows))
        self.assertTrue(all(s["priority"] in {"core", "conditional", "specialist"} for s in rows))
        self.assertTrue(all(s["purpose"] and s["placement"] and s["requirements"] and s["module_family"] for s in rows))
        self.assertFalse(any(s["module_family"] == "housing" for s in rows))
        self.assertTrue(all(s["requirements"] for s in rows if s["priority"] == "conditional"))
        by_id = {s["id"]: s for s in rows}
        for key in ("well", "granary", "market_square", "smithy", "civic_hall", "infirmary", "temple", "gatehouse", "bridge", "library", "farmstead"):
            self.assertIn("building." + key, by_id)
        self.assertEqual(by_id["building.watermill"]["priority"], "conditional")
        self.assertEqual(by_id["building.dock"]["priority"], "conditional")

    def test_reuse_links_resolve_and_planned_ids_do_not_change_exports(self):
        data = section("structure_blocks")["common"]
        exported = {a["id"] for a in compile_asset_list()["assets"]}
        for block in data["blocks"]:
            for row in block["structures"]:
                self.assertIn(row["id"], exported)
                for reference in row["reuse_candidates"]:
                    self.assertIn(reference, exported, row["id"])
        self.assertFalse(data["runtime_placement_enabled"])


if __name__ == "__main__":
    unittest.main()
