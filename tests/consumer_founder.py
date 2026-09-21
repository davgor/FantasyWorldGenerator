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
        dict(args, world=world, api_version=2)),
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

    # Every kind counts, not only cities: no two settlements of any kind may share a node,
    # which `test_no_two_settlements_share_a_node_in_a_finished_world` pins across a
    # finished world and the call now refuses at the founding rather than an age later.
    humans = world.get("humans") or {}
    taken = {s["node"] for s in world["settlements"]["sites"]}
    taken |= {h["node"] for h in humans.get("hamlets", [])}
    taken |= {f["node"] for f in humans.get("fortresses", [])}
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


def a_legal_rural_node(world):
    """Dry land no settlement of any kind already stands on.

    Rural kinds are not held to the city spacing -- a hamlet exists to be close to one --
    so the gates are the ground itself plus the node not being taken.
    """
    config = world["config"]
    radius = world["effective_config"]["globe_radius"]
    points, _areas, _ = sphere_grid(config["size"], radius)
    layers = world["layers"]
    civilization = world["settlements"]["sites"][0]["population_profile"]

    humans = world.get("humans") or {}
    taken = {s["node"] for s in world["settlements"]["sites"]}
    taken |= {h["node"] for h in humans.get("hamlets", [])}
    taken |= {f["node"] for f in humans.get("fortresses", [])}
    taken |= {r["node"] for r in (world.get("ruins") or [])
              if isinstance(r, dict) and "node" in r}

    for node, (x, z) in enumerate(points):
        if node in taken or layers["water_type"][z][x]:
            continue
        if int(layers.get("natural_biome", [[0]])[z][x]) == 17:
            continue
        if layers["suitability_" + civilization][z][x] <= 0:
            continue
        return node, civilization
    raise AssertionError("no legal rural node in this world; the gates or the world changed")


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
            found_settlement_request({"api_version": 2, "world": self.world, "node": water,
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
            "api_version": 2, "world": cls.world, "node": cls.node,
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


class FounderKindTests(unittest.TestCase):
    """A hamlet and a fortress the player raised, in the blocks that already hold them.

    The requirement is that they are indistinguishable in kind from generated ones, so the
    assertions are about where the row lands and what names it -- not about the call
    returning. `humans.hamlets[].id` and `humans.fortresses[].id` are ordinals that
    renumber at every age boundary, so a player keep would change name under its owner if
    it were keyed that way. The node-and-kind key `npc_roster` already mints is the handle.
    """

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.node, cls.civilization = a_legal_rural_node(cls.world)
        cls.founded = found_settlement_request({
            "api_version": 2, "world": cls.world, "node": cls.node, "kind": "hamlet",
            "civilization_id": cls.civilization, "name": "Player Farmstead"})

    def test_a_player_hamlet_lands_in_the_block_that_already_holds_hamlets(self):
        """Not a parallel block. A consumer asking "is there a town here" reads one place."""
        self.assertNotIn("player_settlements", self.founded)
        rows = [h for h in self.founded["humans"]["hamlets"] if h["node"] == self.node]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "hamlet")
        self.assertEqual(rows[0]["founded_by"], "player")

    def test_a_rural_site_is_keyed_on_its_node_and_kind(self):
        row = next(h for h in self.founded["humans"]["hamlets"] if h["node"] == self.node)
        self.assertEqual(row["uid"], "hamlet-node-%d" % self.node)
        self.assertEqual(self.founded["settlement_founding"]["uid"], row["uid"])
        self.assertTrue(row["id"].startswith("hamlet-"),
                        "the ordinal id keeps the space it always had")

    def test_the_caller_is_told_which_kind_was_founded(self):
        report = self.founded["settlement_founding"]
        self.assertEqual(report["kind"], "hamlet")
        operation = self.founded["history"]["operations"][-1]
        self.assertEqual(operation["kind"], "founding")
        self.assertEqual(operation["settlement_kind"], "hamlet")

    def test_village_is_refused_by_name(self):
        """It is not a settlement kind anywhere in the tree, and a caller asking for one
        should be told the vocabulary rather than handed a city."""
        try:
            found_settlement_request({
                "api_version": 2, "world": self.world, "node": self.node,
                "kind": "village", "civilization_id": self.civilization})
            self.fail("village was accepted as a settlement kind")
        except Exception as exc:
            document = exc.document()
            self.assertEqual(document["field"], "kind")

    def test_a_rural_node_that_is_already_taken_is_refused(self):
        taken = self.world["settlements"]["sites"][0]["node"]
        try:
            found_settlement_request({
                "api_version": 2, "world": self.world, "node": taken, "kind": "fortress",
                "civilization_id": self.civilization})
            self.fail("a node that already holds a city accepted a fortress")
        except Exception as exc:
            self.assertEqual(exc.document()["expected"], {"refused_by": "world state"})


class FounderRuralRebuildTests(unittest.TestCase):
    """`add_humans` re-derives the rural layer from scratch. A player keep must survive it."""

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.node, cls.civilization = a_legal_rural_node(cls.world)
        cls.founded = found_settlement_request({
            "api_version": 2, "world": cls.world, "node": cls.node, "kind": "fortress",
            "civilization_id": cls.civilization, "name": "Player Keep",
            "rebuild": "humans"})

    def test_the_players_fortress_survives_the_rural_rebuild(self):
        rows = [f for f in self.founded["humans"]["fortresses"] if f["node"] == self.node]
        self.assertEqual(len(rows), 1, "the rebuild dropped the player's fortress")
        self.assertEqual(rows[0]["uid"], "fortress-node-%d" % self.node)
        self.assertEqual(rows[0]["founded_by"], "player")

    def test_no_generated_rural_site_was_placed_on_top_of_it(self):
        nodes = [h["node"] for h in self.founded["humans"]["hamlets"]]
        nodes += [f["node"] for f in self.founded["humans"]["fortresses"]]
        self.assertEqual(len(nodes), len(set(nodes)),
                         "two rural sites share a node after the rebuild")

    def test_the_world_still_validates_with_a_player_fortress_in_it(self):
        validate_age_world(self.founded)


class FounderLayoutTests(unittest.TestCase):
    """`layout: "player"` means the generator does not pack this city."""

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.node, cls.civilization = a_legal_node(cls.world)
        cls.founded = found_settlement_request({
            "api_version": 2, "world": cls.world, "node": cls.node,
            "civilization_id": cls.civilization, "name": "Authored Town",
            "layout": "player", "population_estimate": 400})

    def test_the_site_carries_an_authored_layout_rather_than_a_planned_one(self):
        site = self.founded["settlements"]["sites"][-1]
        self.assertEqual(site["founded_by"], "player")
        self.assertEqual(site["city_layout"]["layout_profile_id"], "player")
        self.assertEqual(site["city_layout"]["population_estimate"], 400)
        self.assertNotIn("buildings", site["city_layout"])

    def test_the_plan_the_generator_writes_for_it_says_unbuildable_with_a_reason(self):
        from icarus_sim.city_planner import plan_city
        site = self.founded["settlements"]["sites"][-1]
        plan = plan_city(self.founded, site)
        self.assertEqual(plan["status"], "unbuildable")
        self.assertEqual(plan["plots"], [])
        self.assertEqual(plan["authored_by"], "player")
        self.assertTrue(any("player" in row["reason"] for row in plan["unplaced"]))


if __name__ == "__main__":
    unittest.main()
