"""The handle rule, the parity fixture that binds a second implementation to it, and the
operation envelope.

The fixture tests are the load-bearing ones. A handle is only a shared name if two
implementations derive it identically, and the only way a Python-side change that breaks
that is visible is if the pinned bytes stop matching here.
"""

import json
from pathlib import Path
import re
import unittest

import schema_subset

from fantasy_world_generator import world_handle as wh
from fantasy_world_generator.cli import world_document
from icarus_sim.terrain_errors import RequestError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Fixtures" / "world-handle-v1.json").read_text(encoding="utf-8"))


class FixtureParityTests(unittest.TestCase):
    """What a native host must reproduce.

    Bytes are asserted before digests on purpose: two implementations that agree on a
    digest while disagreeing on the bytes are agreeing by luck, and the failure that
    matters is the one that says which of the two serialisations is wrong.
    """

    def test_every_case_still_serialises_to_the_pinned_bytes(self):
        for case in FIXTURE["cases"]:
            with self.subTest(case["name"]):
                self.assertEqual(wh.transfer_bytes(case["document"]).decode("utf-8"),
                                 case["transfer_bytes"])

    def test_every_case_still_hashes_to_the_pinned_handle(self):
        for case in FIXTURE["cases"]:
            with self.subTest(case["name"]):
                self.assertEqual(wh.handle(case["document"]), case["handle"])

    def test_the_pinned_handles_are_distinct(self):
        """A rule that collapsed every document to one name would pass the two above."""
        handles = [c["handle"] for c in FIXTURE["cases"]]
        self.assertEqual(len(set(handles)), len(handles))

    def test_nan_and_infinity_are_refused(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(repr(value)):
                with self.assertRaises(ValueError):
                    wh.transfer_bytes({"a": value})

    def test_the_float_case_pins_the_formatting_a_port_must_match(self):
        """Named explicitly, because these are the four decisions a C++ port gets wrong.

        Shortest round-trip digits are the easy half. The trailing '.0', the sign on
        negative zero, the exponent thresholds and the two-digit signed exponent are
        conventions on top of the digits, and nothing else in the fixture would catch a
        port that chose differently.
        """
        rendered = next(c["transfer_bytes"] for c in FIXTURE["cases"] if c["name"] == "floats")
        self.assertIn('"whole":1.0', rendered)
        self.assertIn('"negative zero":-0.0', rendered)
        self.assertIn('"at the high threshold":1e+16', rendered)
        self.assertIn('"below the high threshold":1000000000000000.0', rendered)
        self.assertIn('"at the low threshold":1e-05', rendered)
        self.assertIn('"above the low threshold":0.0001', rendered)


class RuleTests(unittest.TestCase):
    def test_key_order_does_not_change_the_name(self):
        first = {"z": 1, "a": {"y": 2, "b": 3}}
        second = {"a": {"b": 3, "y": 2}, "z": 1}
        self.assertEqual(wh.handle(first), wh.handle(second))

    def test_timing_comes_off_at_every_depth_including_inside_lists(self):
        document = {"a": 1, "timing_ms": {"total": 1.0},
                    "b": {"timing_ms": 2, "c": [{"timing_ms": 3, "d": 4}]}}
        self.assertEqual(wh.transfer_document(document), {"a": 1, "b": {"c": [{"d": 4}]}})

    def test_build_stages_comes_off_only_at_the_top(self):
        """A block that carries the key deeper is content, not lab payload."""
        self.assertEqual(wh.transfer_document({"build_stages": [1], "a": {"build_stages": [2]}}),
                         {"a": {"build_stages": [2]}})

    def test_a_non_document_is_refused_by_type(self):
        for value in ([], "world", 3, None):
            with self.subTest(repr(value)):
                with self.assertRaises(TypeError):
                    wh.transfer_document(value)

    def test_is_handle_accepts_what_handle_produces_and_little_else(self):
        self.assertTrue(wh.is_handle(wh.handle({})))
        for value in ("", "w_", "w_nothex0123456", "w_44136fa355b3678ab", "44136fa355b3678a",
                      "W_44136fa355b3678a", None, 3):
            with self.subTest(repr(value)):
                self.assertFalse(wh.is_handle(value))


class GeneratedWorldTests(unittest.TestCase):
    """The rule against a real document rather than a synthetic one.

    Seed 42 size 17 phase 4 costs about a tenth of a second, which is what lets this run
    in the default suite instead of behind a flag.
    """

    @classmethod
    def setUpClass(cls):
        cls.request = FIXTURE["world"]["request"]
        cls.world = world_document(cls.request)

    def test_the_pinned_world_still_has_its_pinned_handle(self):
        self.assertEqual(wh.handle(self.world), FIXTURE["world"]["handle"])

    def test_profiling_residue_is_invisible_to_the_name(self):
        """The property that makes a handle name a world rather than a run."""
        profiled = world_document(self.request, build_stages=True, timings=True)
        self.assertIn("build_stages", profiled)
        self.assertEqual(wh.handle(profiled), wh.handle(self.world))

    def test_a_changed_world_gets_a_different_name(self):
        touched = json.loads(json.dumps(self.world))
        touched["config"]["seed"] = self.world["config"]["seed"] + 1
        self.assertNotEqual(wh.handle(touched), wh.handle(self.world))


class StalenessTests(unittest.TestCase):
    def test_a_matching_generator_passes(self):
        self.assertIsNone(wh.check_generator({"generator_version": 16}, 16))

    def test_a_stale_world_is_refused_in_the_vocabulary_every_refusal_uses(self):
        with self.assertRaises(RequestError) as caught:
            wh.check_generator({"generator_version": 15}, 16)
        document = caught.exception.document()
        self.assertEqual(document["code"], "UNSUPPORTED_VERSION")
        self.assertEqual(document["field"], "generator_version")
        self.assertEqual(document["received"], 15)
        self.assertFalse(document["retry"], "a stale world is not retryable with a value")

    def test_a_world_with_no_generator_version_is_refused_rather_than_assumed(self):
        with self.assertRaises(RequestError):
            wh.check_generator({}, 16)


class ChangedPathTests(unittest.TestCase):
    def test_identical_worlds_report_nothing(self):
        world = {"a": {"b": 1}}
        self.assertEqual(wh.changed_paths(world, json.loads(json.dumps(world))), [])

    def test_paths_are_dotted_to_two_levels(self):
        before = {"settlements": {"sites": [1], "founding": {"events": []}}, "layers": {"h": 1}}
        after = {"settlements": {"sites": [1, 2], "founding": {"events": []}}, "layers": {"h": 1}}
        self.assertEqual(wh.changed_paths(before, after), ["settlements.sites"])

    def test_an_added_block_and_a_removed_block_both_appear(self):
        self.assertEqual(wh.changed_paths({"a": 1}, {"b": 2}), ["a", "b"])

    def test_a_deeper_change_is_reported_at_the_second_level(self):
        before = {"a": {"b": {"c": 1}}}
        after = {"a": {"b": {"c": 2}}}
        self.assertEqual(wh.changed_paths(before, after), ["a.b"])

    def test_what_the_handle_ignores_is_never_reported_as_changed(self):
        """Caught on a real age advance, which reported `timing_ms` among 190 paths.

        A path that cannot distinguish two versions is not a change. Reporting one would
        have put the single key the handle is defined to ignore into the account of every
        call that carries timings.
        """
        before = {"a": 1, "timing_ms": {"total": 1.0}, "build_stages": [{"state": 1}]}
        after = {"a": 1, "timing_ms": {"total": 9.5}, "build_stages": [{"state": 2}]}
        self.assertEqual(wh.changed_paths(before, after), [])
        self.assertEqual(wh.handle(before), wh.handle(after),
                         "the premise: these are the same version")


class EnvelopeTests(unittest.TestCase):
    def world(self, operations=(), **extra):
        base = {"generator_version": 16, "history": {"operations": list(operations)}}
        base.update(extra)
        return base

    def test_a_version_envelope_carries_the_name_the_parent_and_what_moved(self):
        before = self.world(settlements={"sites": [1]})
        after = self.world([{"kind": "founding", "uid": "c-9"}],
                           settlements={"sites": [1, 2]},
                           settlement_founding={"notes": ["placed"]})
        result = wh.envelope("found-settlement", after, before)
        self.assertEqual(result["schema"], wh.ENVELOPE_SCHEMA)
        self.assertEqual(result["operation"], "found-settlement")
        self.assertEqual(result["handle"], wh.handle(after))
        self.assertEqual(result["parent"], wh.handle(before))
        self.assertEqual(result["generator_version"], 16)
        self.assertIn("settlements.sites", result["changed"])
        self.assertEqual(result["operation_record"], {"kind": "founding", "uid": "c-9"})
        self.assertEqual(result["report"], {"notes": ["placed"]})

    def test_a_verb_with_no_report_block_still_reports_its_operation_record(self):
        """Four of the eight version verbs stamp no report; this is what they have."""
        before = self.world()
        after = self.world([{"kind": "departure", "god_id": "g-1"}])
        result = wh.envelope("depart", after, before)
        self.assertIsNone(result["report"])
        self.assertEqual(result["operation_record"]["kind"], "departure")

    def test_a_root_has_no_parent_and_nothing_to_have_changed(self):
        result = wh.envelope("generate", self.world())
        self.assertIsNone(result["parent"])
        self.assertEqual(result["changed"], [])

    def test_the_envelope_names_blocks_without_quoting_them(self):
        """The whole reason a handle exists: kilobytes out, however large the world.

        `changed` carries the path `layers`, which is why this cannot assert on the word
        itself -- it asserts that the grid under that path did not come with it.
        """
        after = self.world([{"kind": "age"}],
                           layers={"height": [["sentinel-27182818", 2], [3, 4]]})
        result = wh.envelope("advance-age", after, self.world())
        self.assertIn("layers", result["changed"])
        self.assertNotIn("sentinel-27182818", json.dumps(result))

    def test_misuse_is_refused_by_name(self):
        world = self.world()
        for operation, before, because in (
                ("moon", world, "a read produces no version"),
                ("patch", world, "a read produces no version"),
                ("generate", world, "a root has no parent"),
                ("advance-age", None, "a transform needs the world it was given"),
                ("summon-god", world, "not a verb")):
            with self.subTest(because):
                with self.assertRaises(ValueError):
                    wh.envelope(operation, world, before)


class SchemaTests(unittest.TestCase):
    """The envelope against its published schema, both directions."""

    SCHEMA = json.loads(
        (ROOT / "Contracts" / "schemas" / "operation-envelope.schema.json")
        .read_text(encoding="utf-8"))

    def world(self, operations=(), **extra):
        base = {"generator_version": 16, "history": {"operations": list(operations)}}
        base.update(extra)
        return base

    def check(self, value):
        return list(schema_subset.errors(value, self.SCHEMA))

    def test_a_root_envelope_validates(self):
        self.assertEqual(self.check(wh.envelope("generate", self.world())), [])

    def test_a_version_envelope_validates(self):
        before = self.world()
        after = self.world([{"kind": "cleanse"}], cleanse={"acted": True})
        self.assertEqual(self.check(wh.envelope("cleanse", after, before)), [])

    def test_every_version_verb_produces_a_valid_envelope(self):
        for operation in wh.version_operations():
            with self.subTest(operation):
                after = self.world([{"kind": operation}])
                self.assertEqual(self.check(wh.envelope(operation, after, self.world())), [])

    def test_the_schema_rejects_what_it_should(self):
        """A control, because three greens above prove nothing if nothing can be red.

        Each case breaks a different constraint: the handle pattern, the closed property
        set, and the operation vocabulary. A control that fails for one reason would not
        establish that the other two are being checked.
        """
        for label, damage in (
                ("a handle that is not one", {"handle": "not-a-handle"}),
                ("a field the schema does not declare", {"surprise": 1}),
                ("a verb outside the vocabulary", {"operation": "moon"})):
            with self.subTest(label):
                envelope = wh.envelope("generate", self.world())
                envelope.update(damage)
                self.assertTrue(self.check(envelope), "%s was accepted" % label)


class TaxonomyTests(unittest.TestCase):
    """The operation table against the routes that actually exist.

    A verb added to the lab without being classified here would leave a host unable to
    say whether it produces a version, which is the one thing the store needs to know.
    """

    def routes(self):
        text = (ROOT / "tools" / "terrain_lab.py").read_text(encoding="utf-8")
        declaration = re.search(r"if self\.path not in \(([^)]*)\)", text, re.S)
        self.assertIsNotNone(declaration, "the lab's route tuple has moved or changed shape")
        return set(re.findall(r"'(/[a-z/-]+)'", declaration.group(1)))

    def test_every_world_route_is_a_classified_operation(self):
        for route in sorted(self.routes()):
            if not route.startswith("/world/"):
                continue
            with self.subTest(route):
                self.assertIn(route[len("/world/"):], wh.OPERATIONS)

    def test_the_table_classifies_nothing_that_does_not_exist(self):
        """`depart` is the exception and is named here rather than left to be noticed.

        It has no route of its own: it is `/world/summon` with `depart: true`, and it is
        a separate operation because it produces a different version from a summons.
        """
        routed = {r[len("/world/"):] for r in self.routes() if r.startswith("/world/")}
        self.assertEqual(set(wh.OPERATIONS) - routed - {"patch"}, {"depart"})

    def test_reads_produce_no_version(self):
        self.assertEqual({n for n, s in wh.OPERATIONS.items() if s["kind"] == "read"},
                         {"moon", "patch"})

    def test_every_named_report_key_is_one_a_producer_writes(self):
        """Guards against a report key that was guessed rather than read off the code."""
        sources = {p.name: p.read_text(encoding="utf-8")
                   for p in (ROOT / "Sim" / "icarus_sim").glob("terrain_*.py")}
        for name, spec in wh.OPERATIONS.items():
            if not spec["report"]:
                continue
            with self.subTest(name):
                needle = "result['%s']" % spec["report"]
                self.assertTrue(any(needle in text for text in sources.values()),
                                "no producer writes %s" % needle)


if __name__ == "__main__":
    unittest.main()
