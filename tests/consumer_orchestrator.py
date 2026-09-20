"""Scripted consumers: the orchestrator's calls, in the order a game would make them.

Every other suite in this repository tests a producer. These test the *caller* -- what an
orchestrator receives, whether it can act on it, and whether a refusal tells it enough to
try again. They are the only scripts here shaped like a session rather than a unit.

Each persona is a list of steps declared as data. The test method iterates; it holds no
sequence of its own. That makes the correct call order for a task a readable artefact
instead of Python control flow, which is what lets the MCP evaluation score a model's
trajectory against these rather than against its own guess at them.

Cost: one generation is shared by every persona in the process. The mutating personas each
add roughly one generation's work, because an age transition and a visitation both run
`rebuild_tail`, and `add_nests` plus `fill_cities` are most of a run between them.
"""

import unittest

import consumer_support as support
from consumer_support import ok, refused, unchanged

from icarus_sim.terrain_astrology import lunar_request
from icarus_sim.terrain_corruption import cleanse_request, corruption_request
from icarus_sim.terrain_history import advance_age_request
from icarus_sim.terrain_nomad_api import nomad_request
from icarus_sim.terrain_visitation import visitation_request
from icarus_sim.terrain_world import generate_request


# --- the tool surface, as an orchestrator reaches it ----------------------------------

TOOLS = {
    "generate_world": lambda world, args: generate_request(args),
    "advance_age": lambda world, args: advance_age_request(dict(args, world=world, api_version=1)),
    "summon_god": lambda world, args: visitation_request(dict(args, world=world, api_version=1)),
    "depart_god": lambda world, args: visitation_request(dict(args, world=world, api_version=1, depart=True)),
    "corrupt": lambda world, args: corruption_request(dict(args, world=world, api_version=1)),
    "cleanse": lambda world, args: cleanse_request(dict(args, world=world, api_version=1)),
    "raise_band": lambda world, args: nomad_request(dict(args, world=world, api_version=1)),
    "read_moon": lambda world, args: lunar_request(dict(args, world=world, api_version=1)),
}


def summonable(world):
    return [g["id"] for g in world["religion"]["gods"]
            if g.get("status") in ("manifest", "sleeping")]


def land_node(world):
    return world["settlements"]["sites"][0]["node"]


class FumblingControllerTests(unittest.TestCase):
    """The mistakes a small model actually makes, and whether it can recover from them.

    Costs nothing: every step is refused before a world is built.
    """

    def steps(self):
        return [
            ("misspelt control", "generate_world",
             {"recipe_version": 3, "seed": 42, "overrides": {"plate_cout": 12, "size": 17, "phase": 1}},
             refused("INVALID_INPUT", field="plate_cout", suggests="plate_count")),
            ("half-remembered family", "generate_world",
             {"recipe_version": 3, "seed": 42, "overrides": {"rain": 4, "size": 17, "phase": 1}},
             refused("INVALID_INPUT", field="rain", suggests="rain_passes")),
            ("out of range", "generate_world",
             {"recipe_version": 3, "seed": 42, "overrides": {"plate_count": 99, "size": 17, "phase": 1}},
             refused("INVALID_INPUT", field="plate_count")),
            ("a control pinned shut", "generate_world",
             {"recipe_version": 3, "seed": 42, "overrides": {"sky_clusters": 3, "size": 17, "phase": 1}},
             refused("INVALID_INPUT", field="sky_clusters")),
            ("value outside a vocabulary", "generate_world",
             {"recipe_version": 3, "seed": 42, "overrides": {"world_size": "huge", "size": 17, "phase": 1}},
             refused("INVALID_INPUT", field="world_size")),
            ("retired version", "generate_world",
             {"recipe_version": 2, "seed": 42},
             refused("UNSUPPORTED_VERSION", field="recipe_version")),
            ("seed in the wrong place", "generate_world",
             {"recipe_version": 3, "seed": 42, "overrides": {"seed": 7, "size": 17, "phase": 1}},
             refused("INVALID_INPUT", field="seed")),
        ]

    def test_every_fumble_is_recoverable_from_the_refusal_alone(self):
        recorder = support.Recorder("fumbling_controller")
        for case in self.steps():
            support.drive(case, TOOLS, None)
            recorder.held("refusal names its field and offers a next value", case[0])
        recorder.write()


class CartographerTests(unittest.TestCase):
    """Found a world and read out everywhere a player can go."""

    @classmethod
    def setUpClass(cls):
        cls.world = support.base_world()
        cls.recorder = support.Recorder("cartographer")

    @classmethod
    def tearDownClass(cls):
        cls.recorder.write()

    def test_the_document_is_what_a_game_receives(self):
        """No profiling residue, no lab-only payload."""
        self.assertNotIn("build_stages", self.world)
        self.assertNotIn("timing_ms", self.world)
        self.recorder.held("exported document carries no timings and no stage snapshots")

    def test_every_declared_join_resolves(self):
        broken = support.dangling(self.world)
        self.assertEqual(broken, [], "dangling references: %r" % (broken[:5],))
        self.recorder.held("every join edge resolves", len(support.JOIN_TABLE))

    def test_the_join_keys_are_the_ones_declared(self):
        """Pins the key name per block, because no two blocks agree on one.

        A consumer joining a creature to a key location on `tier` gets a plausible number
        and a wrong world. The same hazard applies to every id field here, so a rename has
        to break a test rather than a consumer.
        """
        for label, source, key, target, target_key in support.JOIN_TABLE:
            rows = support.rows(self.world, source)
            self.assertTrue(rows, "%s: %s is empty" % (label, source))
            self.assertIn(key, rows[0], "%s: %s no longer carries %r" % (label, source, key))
            self.assertIn(target_key, support.rows(self.world, target)[0],
                          "%s: %s no longer carries %r" % (label, target, target_key))

    def test_node_keyed_blocks_still_carry_their_node(self):
        """The key that survives an age boundary, unlike the ordinal ids beside it."""
        for path in support.NODE_KEYED:
            rows = support.rows(self.world, path)
            if not rows:
                continue
            self.assertIn("node", rows[0], "%s no longer carries a terrain node" % path)

    def test_no_single_liveness_predicate_exists(self):
        """Asserted as present, not as fixed.

        `heroes` says living/legend, `npcs` says alive/dead. A consumer cannot write one
        `status == x` across them, and the harness records that rather than papering over
        it: if the vocabularies are ever unified this test fails and the record is updated
        deliberately.
        """
        heroes = {p.get("status") for p in support.rows(self.world, "heroes.people")}
        npcs = {p.get("status") for p in support.rows(self.world, "npcs.people")}
        self.assertTrue(heroes.isdisjoint(npcs),
                        "hero and npc status vocabularies now overlap: %r / %r" % (heroes, npcs))
        self.recorder.recorded("liveness vocabularies", {"heroes": sorted(map(str, heroes)),
                                                        "npcs": sorted(map(str, npcs))})

    def test_the_hazards_a_consumer_must_know_are_still_there(self):
        """Recorded so a downstream reader is not surprised by them."""
        roads = support.rows(self.world, "roads.routes")
        if roads:
            self.assertNotIn("id", roads[0], "roads.routes gained an id; update the consumer notes")
        nodes = (self.world.get("magic") or {}).get("nodes")
        if isinstance(nodes, list) and nodes:
            self.assertNotIsInstance(nodes[0], dict,
                                     "magic.nodes gained structure; it used to be bare vectors")
        self.recorder.held("roads have no id and magic.nodes are bare vectors")


class PersistBoundaryTests(unittest.TestCase):
    """Generate, write it out, read it back, act on it.

    This is the workflow `terrain_history` instructs a caller to use and the one nothing
    covered: every other test acts on an in-memory world that still carries `timing_ms`,
    which `cli.py` strips. Five of the six mutating APIs raised KeyError on a persisted
    world until `adopt_world` put the guard at the boundary instead of at whichever
    producer ran first.
    """

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.recorder = support.Recorder("persist_boundary")

    @classmethod
    def tearDownClass(cls):
        cls.recorder.write()

    def test_the_persisted_world_really_lacks_timings(self):
        """Without this the rest of the class proves nothing."""
        self.assertNotIn("timing_ms", self.world)

    def test_a_pure_read_crosses_the_boundary(self):
        support.drive(("persisted moon read", "read_moon", {"day": 10}, unchanged()),
                      TOOLS, self.world)
        self.recorder.held("lunar_request accepts a persisted world")

    def test_an_age_advance_crosses_the_boundary(self):
        support.drive(("persisted advance", "advance_age", {"steps": 1},
                       ok("history.ages", "settlements.sites")), TOOLS, self.world)
        self.recorder.held("advance_age_request accepts a persisted world")

    def test_raising_a_band_crosses_the_boundary(self):
        support.drive(("persisted band", "raise_band",
                       {"node": land_node(self.world), "origin": {"kind": "world", "age": 0}},
                       ok("nomads.groups")), TOOLS, self.world)
        self.recorder.held("nomad_request accepts a persisted world")


class TheurgeTests(unittest.TestCase):
    """Summon a god, deal with the aftermath, and hit the declared limit."""

    @classmethod
    def setUpClass(cls):
        cls.world = support.persisted(support.base_world())
        cls.recorder = support.Recorder("theurge")

    @classmethod
    def tearDownClass(cls):
        cls.recorder.write()

    def test_a_summons_and_its_departure(self):
        god = summonable(self.world)[0]
        city = self.world["settlements"]["sites"][0]["uid"]
        walked = support.drive(
            ("summon", "summon_god", {"god_id": god, "target": {"city_uid": city}},
             ok("religion.visitations")), TOOLS, self.world)
        support.drive(("depart", "depart_god", {"god_id": god}, ok("religion.visitations")),
                      TOOLS, walked)
        self.recorder.held("a god summoned to a city can be sent home")

    def test_an_unknown_god_is_refused_by_name(self):
        support.drive(("unknown god", "summon_god",
                       {"god_id": "god-that-does-not-exist",
                        "target": {"city_uid": self.world["settlements"]["sites"][0]["uid"]}},
                       refused("INVALID_INPUT")), TOOLS, self.world)

    def test_the_caller_world_is_never_mutated(self):
        """Stateless means stateless. A consumer caching a world must be able to trust it."""
        god = summonable(self.world)[0]
        city = self.world["settlements"]["sites"][0]["uid"]
        support.drive(("summon leaves the caller alone", "summon_god",
                       {"god_id": god, "target": {"city_uid": city}},
                       unchanged()), TOOLS, self.world)


if __name__ == "__main__":
    unittest.main()
