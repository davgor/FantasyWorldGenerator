"""The request boundary's refusals, as the caller receives them.

The caller is a local model packaged inside the game with nobody to ask. So these tests
assert the thing that makes a refusal actionable rather than merely correct: that it names
the field, echoes the value it was sent, states the bound or the vocabulary it violated,
and where one exists offers a value that would work.

The sweep over every bounded control is deliberate. A spot-check of four controls proves
four controls; the whole point of generating the catalogue is that the refusal path can be
checked against all of them at once. It costs milliseconds because `generate_request`
validates before it constructs a `Config`, so no world is built.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

from icarus_sim import terrain_errors  # noqa: E402
from icarus_sim.terrain_world import generate_request, registry  # noqa: E402

CODES = ("INVALID_INPUT", "UNSUPPORTED_VERSION", "UNKNOWN_ID", "STALE_REVISION",
         "AUTHORITY_MISMATCH", "CONFLICTING_EVENT", "INTERVAL_CONFLICT", "WORK_BUDGET",
         "STATE_CAPACITY", "NUMERIC_OVERFLOW", "INVALID_CANDIDATE")

SUGGESTIONS = ("clamp", "choose", "did_you_mean", "none")


def refuse(body):
    """Return the envelope a request is refused with, or fail if it is not refused."""
    try:
        generate_request(body)
    except terrain_errors.RequestError as exc:
        return exc.document()
    raise AssertionError("request was accepted: %r" % (body,))


def request(**overrides):
    """A cheap request with the swept control applied last, so it wins.

    Writing `dict(overrides, size=17, phase=1)` silently overwrote the swept value whenever
    the control under test was `size` or `phase`, which turned two sweep steps into a legal
    request and read as a pass.
    """
    body = {"size": 17, "phase": 1}
    body.update(overrides)
    return {"recipe_version": 3, "seed": 42, "overrides": body}


class EnvelopeShapeTests(unittest.TestCase):
    def test_a_request_error_is_a_value_error(self):
        """Every existing handler catches ValueError; adopting this must not break them.

        `cli.py`, the lab server and four leaf packages all catch `ValueError`. If this
        stopped being one, they would start letting refusals escape as tracebacks.
        """
        self.assertTrue(issubclass(terrain_errors.RequestError, ValueError))

    def test_the_code_vocabulary_is_not_widened(self):
        """The enum is declared `additionalProperties: false` in the counter-kernel schema
        and is a categorical the evaluation groups failures by. A new code there is a
        contract change, not a convenience.
        """
        for code in (terrain_errors.INVALID_INPUT, terrain_errors.UNSUPPORTED_VERSION,
                     terrain_errors.STATE_CAPACITY):
            self.assertIn(code, CODES)

    def test_the_detail_tier_is_separable(self):
        """The harness has to be able to switch the optional half off to measure it."""
        error = terrain_errors.out_of_range("plate_count", 99, registry(3)["plate_count"])
        core = error.document(detail=False)
        full = error.document(detail=True)
        self.assertEqual(sorted(core), ["code", "field", "message", "schema", "schema_version"])
        self.assertEqual(core["message"], full["message"])
        self.assertEqual(core["code"], full["code"])
        for optional in ("received", "expected", "suggestion", "retry"):
            self.assertIn(optional, full)
            self.assertNotIn(optional, core)

    def test_every_envelope_is_json(self):
        """A caller parses this. A value that will not serialise is not a contract."""
        for document in (refuse(request(plate_cout=12)), refuse(request(plate_count=99)),
                         refuse(request(world_size="huge"))):
            json.loads(json.dumps(document))


class RefusalContentTests(unittest.TestCase):
    def test_every_bounded_control_reports_its_own_violation(self):
        """One step past each declared bound, for every control that has one.

        Pinned controls are excluded only because they are covered by their own test; every
        other bounded control is swept in both directions.
        """
        controls = registry(3)
        swept = 0
        for name, definition in sorted(controls.items()):
            low, high = definition.get("min"), definition.get("max")
            if low is None or high is None or low == high or definition.get("type") == "string":
                continue
            if name == "seed":
                continue  # validated at the request root, not as an override; see its own test
            step = 1 if definition["type"] == "integer" else 0.5
            for value in (low - step, high + step):
                document = refuse(request(**{name: value}))
                self.assertEqual(document["field"], name,
                                 "%s=%r named field %r" % (name, value, document["field"]))
                self.assertEqual(document["received"], value)
                self.assertIn(document["code"], CODES)
                self.assertIn(str(low), document["message"])
                self.assertIn(str(high), document["message"])
                self.assertIn(document["suggestion"]["kind"], SUGGESTIONS)
                swept += 1
        self.assertGreater(swept, 300, "the sweep covered suspiciously few controls")

    def test_a_misspelt_control_names_the_one_that_was_meant(self):
        """One deleted character and one transposition, for every control.

        This is the failure an LLM actually produces, and `Unknown override` -- which named
        no key and suggested nothing -- was the most expensive message in the API.
        """
        controls = sorted(registry(3))
        for name in controls:
            if len(name) < 6:
                continue
            for typo in (name[:3] + name[4:], name[:3] + name[4] + name[3] + name[5:]):
                if typo in controls:
                    continue
                document = refuse(request(**{typo: 1}))
                self.assertEqual(document["field"], typo)
                self.assertIn(name, document["suggestion"].get("candidates", []),
                              "%r did not suggest %r" % (typo, name))

    def test_a_bare_prefix_suggests_the_family_not_the_nearest_string(self):
        """difflib alone answers 'radius' for 'rain', because it is shorter."""
        candidates = refuse(request(rain=4))["suggestion"]["candidates"]
        self.assertIn("rain_passes", candidates)
        self.assertIn("rain_strength", candidates)
        self.assertLess(candidates.index("rain_passes"), candidates.index("radius"))

    def test_a_pinned_control_says_it_is_pinned(self):
        for name in sorted(k for k, v in registry(3).items()
                           if v.get("min") is not None and v["min"] == v["max"]):
            document = refuse(request(**{name: 3}))
            self.assertEqual(document["field"], name)
            self.assertIn("pinned", document["message"])
            self.assertTrue(document["expected"].get("pinned"))

    def test_a_closed_vocabulary_is_listed(self):
        document = refuse(request(world_size="huge"))
        self.assertEqual(document["field"], "world_size")
        for choice in ("small", "medium", "large"):
            self.assertIn(choice, document["message"])
            self.assertIn(choice, document["expected"]["choices"])

    def test_a_retired_version_is_not_retryable(self):
        document = refuse({"recipe_version": 2, "seed": 42})
        self.assertEqual(document["code"], "UNSUPPORTED_VERSION")
        self.assertIs(document["retry"], False)

    def test_a_cross_field_refusal_names_every_field_involved(self):
        document = refuse(request(globe_radius=5000.0, relief_m=900.0))
        self.assertIsNone(document["field"])
        self.assertIn("relief_m", document["expected"]["fields"])
        self.assertIn("circumference_km", document["expected"]["fields"])

    def test_a_misspelt_request_field_is_caught_too(self):
        document = refuse({"recipe_version": 3, "seed": 42, "ovverides": {}})
        self.assertEqual(document["field"], "ovverides")
        self.assertIn("overrides", document["suggestion"]["candidates"])


class ControlTests(unittest.TestCase):
    """Guards that the assertions above can fail, not only pass.

    `SDET-WORLD-SCHEMA-SURFACE` records three tests that passed while asserting nothing,
    with a positive control that shared the bug. `refuse()` raising on an accepted request
    is what keeps that from happening here, so it is asserted directly.
    """

    def test_refuse_fails_when_a_request_is_accepted(self):
        with self.assertRaises(AssertionError):
            refuse(request(plate_count=12))

    def test_the_suggestion_search_can_return_nothing(self):
        self.assertEqual(terrain_errors.nearest("zzzzzzzzzz", ["plate_count", "seed"]), [])


if __name__ == "__main__":
    unittest.main()
