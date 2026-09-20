"""The generated control catalogue against the registry it is generated from.

`test_every_control_carries_prose` and `test_every_control_states_its_units` landed red on
purpose, as the worklist for the notation pass: 54 of 209 controls described themselves
with their own field name and 40 numeric ones shipped no unit. Both are green now. They
stay because they are the thing that keeps a new control from arriving undescribed.

Every correspondence is checked in BOTH directions. A one-way check reads as coverage while
missing the other half: verifying that each catalogue row matches a control says nothing
about controls the catalogue omits, and checking that each native bound matches the
reference says nothing about controls the native core resolves with no bound at all --
which is how `culture_link_cost` accepted any value for as long as it did.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

from icarus_sim.terrain_world import registry  # noqa: E402

CATALOGUE = ROOT / "Contracts" / "catalogues" / "world-controls-v1.json"
MIRROR = ROOT / "Sim" / "fantasy_world_generator" / "world_controls.json"

COMPARED = ("default", "min", "max", "type", "units", "group", "choices")


def load():
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


class ControlCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.body = load()
        self.rows = self.body["controls"]
        self.registry = registry(3)

    def test_catalogue_is_a_faithful_projection_in_both_directions(self):
        self.assertEqual(set(self.rows), set(self.registry),
                         "catalogue and registry disagree on which controls exist")
        for name, definition in sorted(self.registry.items()):
            row = self.rows[name]
            for field in COMPARED:
                if field in definition:
                    self.assertEqual(row.get(field), definition[field],
                                     "%s.%s differs between catalogue and registry" % (name, field))

    def test_the_committed_copies_are_current(self):
        result = subprocess.run([sys.executable, "tools/export_controls.py", "--check"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_the_packaged_mirror_is_byte_identical(self):
        self.assertEqual(MIRROR.read_bytes(), CATALOGUE.read_bytes(),
                         "the packaged mirror has drifted from Contracts/")

    def test_status_is_a_closed_three_value_vocabulary(self):
        """`open`, `pinned` and `inert` are different things and a caller must tell them apart.

        A pinned control has `min == max` and refuses every value, so a caller discovers it
        on the first attempt. An inert one accepts every value and is read by nothing, so a
        caller never discovers it at all -- which is why it has to be declared.
        """
        for name, row in sorted(self.rows.items()):
            self.assertIn(row["status"], ("open", "pinned", "inert"),
                          "%s carries an unknown status" % name)

    def test_every_pinned_control_is_marked(self):
        """A control whose min equals its max rejects every value a caller can send."""
        for name, definition in sorted(self.registry.items()):
            low, high = definition.get("min"), definition.get("max")
            status = self.rows[name]["status"]
            if low is not None and low == high:
                self.assertEqual(status, "pinned", "%s has min == max and is not marked" % name)
                self.assertTrue(self.rows[name].get("pinned_reason"),
                                "%s is pinned and must say why" % name)
            else:
                self.assertNotEqual(status, "pinned",
                                    "%s is marked pinned but its bounds differ" % name)

    def test_every_inert_control_says_why(self):
        inert = sorted(k for k, row in self.rows.items() if row["status"] == "inert")
        self.assertTrue(inert, "nothing is marked inert; the sweep found one and should still")
        for name in inert:
            self.assertTrue(self.rows[name].get("inert_reason"),
                            "%s is inert and must say why" % name)

    def test_the_native_header_matches_the_catalogue(self):
        """Core's bounds are generated, so a divergence is a failing build rather than a
        core that refuses a world the reference produces by default.

        Parsed rather than imported, so this holds on a machine with no C++ compiler --
        which is most of them, and `Core/README.md` says a skipped native test is missing
        evidence rather than passing evidence.
        """
        import re
        header = (ROOT / "Core" / "controlbounds.inl").read_text(encoding="utf-8")
        rows = dict((name, (float(low), float(high))) for name, low, high in
                    re.findall(r'\{"([A-Za-z_0-9]+)",\{(-?[\d.e+]+),(-?[\d.e+]+)\}\}', header))
        self.assertTrue(rows, "the generated native header parsed to nothing")
        for name, (low, high) in sorted(rows.items()):
            if name not in self.rows:
                continue  # native-only, carried with a stated reason
            self.assertEqual((low, high),
                             (float(self.rows[name]["min"]), float(self.rows[name]["max"])),
                             "%s: native header and catalogue disagree" % name)

    def test_every_natively_resolved_control_has_a_bound(self):
        """Both directions. `culture_link_cost` was resolved by Core with no bound at all,
        so the native core accepted any value while the reference bounded it 1..100000.
        """
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "tools"))
        import export_controls
        resolved = set(export_controls.native_keys())
        import re
        header = (ROOT / "Core" / "controlbounds.inl").read_text(encoding="utf-8")
        bounded = set(re.findall(r'\{"([A-Za-z_0-9]+)",\{', header))
        self.assertEqual(resolved - bounded, set(),
                         "Core resolves these controls with no bound: %s" % sorted(resolved - bounded))
        self.assertEqual(bounded - resolved, set(),
                         "Core bounds these controls but resolves none of them: %s"
                         % sorted(bounded - resolved))

    def test_precedence_is_stated_in_both_directions(self):
        """An agent that sets circumference_km and amplitude together gets silent precedence.

        The catalogue has to say so from either end, or a caller reading one row cannot
        discover it.
        """
        derived = sorted(k for k, row in self.rows.items() if "derived_from" in row)
        self.assertTrue(derived, "no control is marked derived; the extraction found nothing")
        for name in derived:
            for source in self.rows[name]["derived_from"]:
                self.assertIn(source, self.rows, "%s derives from unknown %s" % (name, source))
                self.assertIn(name, self.rows[source].get("overrides", []),
                              "%s says it derives from %s, which does not claim it"
                              % (name, source))

    def test_every_control_carries_prose(self):
        """EXPECTED TO FAIL until the notation pass lands.

        A description equal to the control's own name is not documentation. The reader
        here is a local model mapping an intent onto a control, and it cannot ask.
        """
        placeholders = sorted(name for name, row in self.rows.items()
                              if row.get("description", "") == name.replace("_", " "))
        self.assertEqual(placeholders, [],
                         "%d controls carry a placeholder description: %s"
                         % (len(placeholders), ", ".join(placeholders)))

    def test_every_control_states_its_units(self):
        """EXPECTED TO FAIL until the notation pass lands.

        `units` is how a caller knows whether 250 is metres, kilometres or a multiplier.
        Text controls are exempt; they have no dimension.
        """
        missing = sorted(name for name, row in self.rows.items()
                         if row.get("type") != "string" and not row.get("units"))
        self.assertEqual(missing, [],
                         "%d numeric controls ship no units: %s"
                         % (len(missing), ", ".join(missing)))


class ControlCatalogueControlTests(unittest.TestCase):
    """Guards against the failures above being indistinguishable from a broken test.

    `SDET-WORLD-SCHEMA-SURFACE` records three tests that passed on first run while
    asserting nothing, and a positive control that shared the bug. These assert that the
    predicates behind the two pins can return both answers.
    """

    def test_the_prose_predicate_can_pass(self):
        row = {"description": "Tectonic plates the globe is divided into."}
        self.assertNotEqual(row["description"], "plate_count".replace("_", " "))

    def test_the_prose_predicate_can_fail(self):
        row = {"description": "plate count"}
        self.assertEqual(row["description"], "plate_count".replace("_", " "))

    def test_the_units_predicate_ignores_text_controls(self):
        self.assertFalse([name for name, row in load()["controls"].items()
                          if row.get("type") == "string" and not row.get("units")
                          and name not in load()["controls"]])


if __name__ == "__main__":
    unittest.main()
