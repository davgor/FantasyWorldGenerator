"""Generate the machine-readable control catalogue from the reference registry.

One table, three readers. `terrain_world.registry(3)` is the source of truth; this writes
it as data so Python, the native core and the packaged plugin stop keeping copies of the
same bounds by hand. Four of the twenty rows the native table shared with the reference
disagreed with it, and one of them -- `support_reach` -- meant the reference producer's own
default world could not be requested through Core's JSON boundary. Those close as a
consequence of generation rather than as four hand edits.

Three things the registry does not carry are derived here, because a caller cannot see any
of them and each changes what its request does:

- `status` separates `open` from `pinned` (`min == max`, so every value is refused) and
  `inert` (accepted and read by nothing on this recipe). A pinned control announces itself
  on the first attempt; an inert one never does.
- `derived_from` / `overrides` state the precedence between the authored world shape and
  the terms computed from it. An agent that sets `circumference_km` and `amplitude` together
  gets silent precedence today with nothing to read it from.
- `producers` says whether the native core honours the control, measured by reading its
  bounds table rather than by asserting a list here.

Every extracted fact is read out of the code that implements it, and the run fails rather
than emitting a catalogue built on a guess.

Standard library only, Python 3.9 compatible. The package declares no dependencies.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

DESTINATION = ROOT / "Contracts" / "catalogues" / "world-controls-v1.json"
MIRROR = ROOT / "Sim" / "fantasy_world_generator" / "world_controls.json"
SOURCE = ROOT / "Sim" / "icarus_sim" / "terrain_world.py"
NATIVE_SOURCE = ROOT / "Core" / "genesis.cpp"
NATIVE_RESOLVER = ROOT / "Core" / "world.cpp"
NATIVE_HEADER = ROOT / "Core" / "controlbounds.inl"

# The authored world shape. Zero keeps the world_size preset, so the derivation below runs
# on the default path too -- the half a caller is most likely to be surprised by.
SHAPE_INPUTS = ("circumference_km", "relief_m")

# Native-only, deliberately. Python carries `extent` in registry()'s `inactive` set, so it
# has no catalogue row to generate from; Core still resolves it on the retired plane path.
NATIVE_ONLY = {"extent": (0.01, 1e7)}

# Accepted, validated, published -- and read by nothing on this recipe. Verified by sweeping
# each Config-derived control for a read site outside tests and the declaration, with
# cfg.magic_enabled as the probe's own control so a broken probe cannot report silence.
INERT = {
    "stubbornness": "Written only by terrain_recipes.seed_config, which runs when "
                    "auto_parameters is set; recipe 3 forbids auto_parameters, so on "
                    "this recipe the value is accepted and never read.",
}


def _string_tuple(node) -> list:
    """Every plain string element of a tuple/list literal, ignoring anything else."""
    if not isinstance(node, (ast.Tuple, ast.List)):
        return []
    found = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            found.append(element.value)
        elif isinstance(element, (ast.Tuple, ast.List)) and element.elts:
            first = element.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.append(first.value)
    return found


def derived_keys() -> list:
    """Controls recomputed from the world's physical width unless individually overridden.

    Read out of the two `for` statements that perform the derivation and the one `if` that
    guards the runoff term, so this cannot fall out of step with the code that does it.
    """
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            for name in _string_tuple(node.iter):
                if name not in keys:
                    keys.append(name)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant):
            value = node.left.value
            if isinstance(value, str) and value.endswith("_km2") and value not in keys:
                keys.append(value)
    return keys


def native_keys() -> list:
    """Controls the native core resolves, read from `Core/world.cpp::resolve_config`.

    Deliberately not read from `override_bounds()`: that table is now generated from this
    list, so extracting the list from it would be circular and would agree with itself no
    matter what drifted. `resolve_config` is the hand-written if/else chain that actually
    consumes a value, which makes it the honest denominator -- and checking the two against
    each other is what found `culture_link_cost` being resolved with no bound at all, so
    the native core accepted any value for it while the reference bounded it 1..100000.
    """
    text = NATIVE_RESOLVER.read_text(encoding="utf-8")
    start = text.find("WorldConfig resolve_config")
    if start < 0:
        raise ValueError(
            "resolve_config not found in Core/world.cpp; the extraction moved. Fix it "
            "rather than emitting a catalogue that guesses what the native core honours.")
    block = text[start:text.index("\n}", start)]
    found = sorted(set(re.findall(r'key=="([A-Za-z_0-9]+)"', block)))
    if not found:
        raise ValueError("resolve_config parsed to nothing; the branch shape changed.")
    return found


def _cxx(value) -> str:
    """A C++ double literal that round-trips the catalogue value."""
    number = float(value)
    if number == int(number) and abs(number) < 1e15:
        return "%d." % int(number)
    return repr(number)


def render_header(rows: dict, native: list) -> str:
    """The native bounds table, generated from the catalogue rather than kept by hand."""
    lines = [
        "// Generated by tools/export_controls.py. Do not edit.",
        "//",
        "// The reference registry's bounds for the controls this core resolves.",
        "// tools/export_controls.py --check fails the gate when this file and",
        "// Contracts/catalogues/world-controls-v1.json disagree, so a divergence becomes a",
        "// failing build rather than a core that refuses what the reference accepts.",
        "",
    ]
    for name in native:
        if name in NATIVE_ONLY:
            low, high = NATIVE_ONLY[name]
            lines.append('{"%s",{%s,%s}}, // native-only: no reference row'
                         % (name, _cxx(low), _cxx(high)))
        elif name in rows:
            lines.append('{"%s",{%s,%s}},'
                         % (name, _cxx(rows[name]["min"]), _cxx(rows[name]["max"])))
        else:
            raise ValueError(
                "Core resolves %r but the reference publishes no such control. Either add "
                "it to registry() or record it in NATIVE_ONLY with a reason." % name)
    return "\n".join(lines) + "\n"


def build_controls() -> dict:
    from icarus_sim.terrain_world import registry

    controls = registry(3)
    native = set(native_keys())
    derived = [key for key in derived_keys() if key in controls]
    if not derived:
        raise ValueError(
            "no derived controls were extracted from terrain_world.py; the derivation "
            "loops moved or changed shape. Fix the extraction rather than shipping a "
            "catalogue that claims every control is independent.")

    rows = {}
    for name in sorted(controls):
        definition = controls[name]
        row = {key: definition[key] for key in
               ("default", "min", "max", "type", "units", "group", "description")
               if key in definition}
        for optional in ("choices", "choice_labels"):
            if optional in definition:
                row[optional] = definition[optional]

        low, high = definition.get("min"), definition.get("max")
        if low is not None and low == high:
            row["status"] = "pinned"
            row["pinned_reason"] = (
                "min == max == %s, so every override of this control is rejected." % low)
        elif name in INERT:
            row["status"] = "inert"
            row["inert_reason"] = INERT[name]
        else:
            row["status"] = "open"

        if name in derived:
            row["derived_from"] = list(SHAPE_INPUTS)
            row["note"] = ("Computed from the world's physical width unless set explicitly; "
                           "an explicit value wins. An absent circumference_km falls back to "
                           "the world_size preset, so this derives on the default path too.")
        if name in SHAPE_INPUTS:
            row["overrides"] = derived
        row["producers"] = ["reference", "native"] if name in native else ["reference"]
        rows[name] = row

    body = {
        "schema": "fantasy-world-generator.world-controls",
        "version": 1,
        "recipe_version": 3,
        "controls": rows,
    }
    body["content_sha256"] = hashlib.sha256(
        json.dumps(rows, indent=1, sort_keys=True).encode("utf-8")).hexdigest()
    return body


def _serialise(body: dict) -> str:
    return json.dumps(body, indent=1, sort_keys=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail when a committed copy is stale")
    arguments = parser.parse_args(argv)

    body = build_controls()
    text = _serialise(body)
    header = render_header(body["controls"], native_keys())

    statuses = {}
    for row in body["controls"].values():
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    summary = "%d controls (%s), %d honoured natively" % (
        len(body["controls"]),
        ", ".join("%d %s" % (count, name) for name, count in sorted(statuses.items())),
        sum(1 for row in body["controls"].values() if "native" in row["producers"]))

    targets = ((DESTINATION, text, "Controls catalogue"),
               (MIRROR, text, "Packaged controls mirror"),
               (NATIVE_HEADER, header, "Native bounds header"))

    if arguments.check:
        for target, expected, label in targets:
            current = target.read_text(encoding="utf-8") if target.is_file() else ""
            if current != expected:
                print("%s is stale; run tools/export_controls.py" % label, file=sys.stderr)
                return 1
        print("Controls catalogue current: %s" % summary)
        return 0

    for target, expected, _ in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="utf-8")
    print("Wrote the catalogue, its packaged mirror and %s: %s"
          % (NATIVE_HEADER.relative_to(ROOT), summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
