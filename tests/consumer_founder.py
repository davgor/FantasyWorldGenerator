"""The founder: a player picks a spot and the orchestrator raises a town there.

The assertions that matter are not "it didn't crash" -- they are the three structural
invariants a site has to satisfy, which no field list captures and which an empirically
verified drop-matrix found:

- `site['id']` must equal the site's index in `sites[]`, because it is used as a direct
  list index into `humans.cores`, `seasonal_food.models` and per-site profile lists. A
  wrong id silently joins the wrong rows rather than raising.
- `city_class` must be exactly what `classify_cities` derives, or `validate_age_world`
  refuses the whole world and it can never advance an age again -- a failure that surfaces
  at the next advance rather than at the call that caused it.
- every existing cross-block join must still resolve afterwards.

The persona is declared as data for the same reason the others are: it is a reference
trajectory the MCP evaluation can score a model against.
"""

import math
import unittest

import consumer_support as support
from consumer_support import ok, refused

from icarus_sim.terrain_erosion import sphere_grid
from icarus_sim.terrain_globe import direction
from icarus_sim.terrain_history import advance_age_request, validate_age_world
from icarus_sim.terrain_settlement_api import found_settlement_request

TOOLS = {
    "found_settlement": lambda world, args: found_settlement_request(
        dict(args, world=world, api_version=1)),
}


def a_legal_node(world):
    """A node that satisfies every gate the founding call enforces.

    Computed rather than hardcoded: the legal set depends on the seed, the size and the
    civilization, and a hardcoded node silently stops testing anything the day one moves.
    """
    config = world["config"]
    radius = world["effective_config"]["globe_radius"]
    spacing = world["effective_config"].get("settlement_spacing") or 0
    points, _areas, _ = sphere_grid(config["size"], radius)
    layers = world["layers"]
    civilization = world["settlements"]["sites"][0]["population_profile"]

    taken = {s["node"] for s in world["settlements"]["sites"]}
    taken |= {r["node"] for r in (world.get("ruins") or [])
              if isinstance(r, dict) and "node" in r}

    for node, (x, z) in enumerate(points):
        if node in taken or layers["water_type"][z][x]:
            continue
        if int(layers.get("natural_biome", [[0]])[z][x]) == 17:
            continue
        if layers["suitability_" + civilization][z][x] <= 0:
            continue
        here = direction(x, z, config["size"])
        if any(radius * math.acos(max(-1., min(1., sum(a * b for a, b in zip(here, s["direction"])))))
               < spacing for s in world["settlements"]["sites"] if s.get("direction")):
            continue
        return node, civilization
    raise AssertionError("no legal node in this world; the gates or the world changed")


class FounderRefusalTests(unittest.TestCase):
    """Every way the ground or the request can be wrong, and what the caller is told."""

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.node, cls.civilization = a_legal_node(cls.world)

    def steps(self):
        occupied = self.world["settlements"]["sites"][0]["node"]
        points, _a, _ = sphere_grid(self.world["config"]["size"],
                                    self.world["effective_config"]["globe_radius"])
        layers = self.world["layers"]
        water = next(n for n, (x, z) in enumerate(points) if layers["water_type"][z][x])
        return [
            ("a civilization that does not exist", "found_settlement",
             {"node": self.node, "civilization_id": "dwarfs"},
             refused("INVALID_INPUT", field="dwarfs", suggests="dwarf")),
            ("caller tries to set the class", "found_settlement",
             {"node": self.node, "civilization_id": self.civilization, "city_class": "capital"},
             refused("INVALID_INPUT", field="city_class")),
            ("a node past the edge of the world", "found_settlement",
             {"node": 10 ** 6, "civilization_id": self.civilization},
             refused("INVALID_INPUT", field="node")),
            ("a node in the sea", "found_settlement",
             {"node": water, "civilization_id": self.civilization},
             refused("INVALID_INPUT", field="node")),
            ("a node that already holds a city", "found_settlement",
             {"node": occupied, "civilization_id": self.civilization},
             refused("INVALID_INPUT", field="node")),
            ("a rebuild mode that does not exist", "found_settlement",
             {"node": self.node, "civilization_id": self.civilization, "rebuild": "everything"},
             refused("INVALID_INPUT", field="rebuild")),
        ]

    def test_every_refusal_names_what_to_change(self):
        for case in self.steps():
            support.drive(case, TOOLS, self.world)

    def test_the_ground_refusals_are_world_refusals_not_argument_ones(self):
        """A node in the sea is a different problem from a misspelt civilization.

        The first needs a different node; the second needs a different value. A caller that
        cannot tell them apart keeps correcting an argument that was never wrong.
        """
        points, _a, _ = sphere_grid(self.world["config"]["size"],
                                    self.world["effective_config"]["globe_radius"])
        layers = self.world["layers"]
        water = next(n for n, (x, z) in enumerate(points) if layers["water_type"][z][x])
        try:
            found_settlement_request({"api_version": 1, "world": self.world, "node": water,
                                      "civilization_id": self.civilization})
            self.fail("founding on water was accepted")
        except Exception as exc:
            document = exc.document()
            self.assertEqual(document["expected"], {"refused_by": "world state"})


class FounderTests(unittest.TestCase):
    """Found a town and check the world still holds together around it."""

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.node, cls.civilization = a_legal_node(cls.world)
        cls.founded = found_settlement_request({
            "api_version": 1, "world": cls.world, "node": cls.node,
            "civilization_id": cls.civilization, "name": "Player Town",
            "population_estimate": 400})
        cls.recorder = support.Recorder("founder")

    @classmethod
    def tearDownClass(cls):
        cls.recorder.write()

    def test_the_callers_world_is_untouched(self):
        self.assertEqual(len(self.world["settlements"]["sites"]),
                         len(self.founded["settlements"]["sites"]) - 1)

    def test_the_site_carries_a_node_keyed_uid(self):
        site = self.founded["settlements"]["sites"][-1]
        self.assertEqual(site["uid"], "surface-city-%d-%d-%s"
                         % (len(self.founded["history"]["ages"]), self.node, self.civilization))
        self.recorder.held("player site takes the generated uid rule verbatim", site["uid"])

    def test_id_equals_index_for_every_site(self):
        """Used as a direct list index into three parallel blocks. A wrong id joins the
        wrong rows silently rather than raising, which is why this is asserted and not
        assumed."""
        for index, site in enumerate(self.founded["settlements"]["sites"]):
            self.assertEqual(site["id"], index, "site %r has id %r" % (site["uid"], site["id"]))

    def test_the_class_is_derived_not_supplied(self):
        site = self.founded["settlements"]["sites"][-1]
        self.assertIn(site["city_class"], ("small", "medium", "capital"))

    def test_the_world_still_validates(self):
        """If this fails the world can never advance an age again, and the failure would
        otherwise surface at the next advance rather than here."""
        validate_age_world(self.founded)
        self.recorder.held("a world with a player city still passes validate_age_world")

    def test_every_join_still_resolves(self):
        broken = support.dangling(self.founded)
        self.assertEqual(broken, [], "dangling after founding: %r" % (broken[:5],))
        self.recorder.held("no join dangles after a founding")

    def test_the_terrain_values_are_real_not_invented(self):
        """Eight fields are exact layer reads, so a player town carries the numbers a
        generated one would have carried on the same ground."""
        site = self.founded["settlements"]["sites"][-1]
        layers = self.founded["layers"]
        x, z = site["x"], site["z"]
        for field, layer in (("height_m", "height"), ("slope_degrees", "slope"),
                             ("temperature_c", "temperature"), ("moisture", "moisture"),
                             ("flood_risk", "flood_risk"),
                             ("resource_potential", "resource_potential"),
                             ("suitability", "suitability_" + self.civilization)):
            self.assertEqual(site[field], layers[layer][z][x], field)

    def test_the_call_is_recorded_in_the_operation_log(self):
        operation = self.founded["history"]["operations"][-1]
        self.assertEqual(operation["kind"], "founding")
        self.assertEqual(operation["node"], self.node)

    def test_the_report_discloses_what_it_left_alone(self):
        """The nest book is deliberately not re-rolled, and a caller holding nest ids has
        to be told that the next age advance will re-roll it anyway."""
        report = self.founded["settlement_founding"]
        self.assertFalse(report["nests_rerolled"])
        self.assertTrue(any("nest" in note for note in report["notes"]))

    def test_the_world_still_advances(self):
        """Survival is not asserted. An age advance at this seed ruins ten of twelve cities
        on an untouched world, so a player town dying is ordinary attrition rather than a
        founding defect -- asserting it survived would be asserting the war model is gentle.
        """
        advanced = advance_age_request({"api_version": 1, "world": self.founded, "steps": 1})
        self.assertGreater(len(advanced["history"]["ages"]),
                           len(self.founded["history"]["ages"]))
        self.recorder.recorded("sites after one age",
                               {"before": len(self.founded["settlements"]["sites"]),
                                "after": len(advanced["settlements"]["sites"])})


if __name__ == "__main__":
    unittest.main()
