"""Shared machinery for the scripted consumers.

These files are named `consumer_*.py` rather than `test_*.py` on purpose: the two unittest
suites discover `test_*.py`, and `repo-tests` already carries the showcase exporter. A
consumer run belongs in its own stage with its own budget, not bolted onto a job that is
near its ceiling.

**Personas are data, not control flow.** Each is a list of `(tool, args, expectation)`
steps that a thin test method iterates. Writing them as straight-line bodies would make the
correct call sequence for a task implicit in Python; as a list it is a declared artefact
another tool can read. The MCP evaluation scores a model's trajectory against a reference
trajectory, and a scripted deterministic persona *is* a reference trajectory -- so the
definition of correct lives here once rather than being re-derived there and getting
subtly different.
"""

import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

from fantasy_world_generator.cli import world_document  # noqa: E402
from icarus_sim import terrain_errors  # noqa: E402
import schema_subset  # noqa: E402

SIZE = int(os.environ.get("FANTASY_WORLD_CONSUMER_SIZE", "17"))
SEED = int(os.environ.get("FANTASY_WORLD_CONSUMER_SEED", "42"))
AGES = int(os.environ.get("FANTASY_WORLD_CONSUMER_AGES", "1"))
CACHE = os.environ.get("FANTASY_WORLD_CONSUMER_BASE")

_BASE = {}


def errors(value, schema, root=None):
    """`schema_subset.errors` materialised.

    It is a generator, so `assertTrue(errors(...))` is true whether or not it would yield
    anything. Three tests in `test_world_schema_surface` passed that way on first run, and
    so did the control that was meant to catch it.
    """
    return list(schema_subset.errors(value, schema, root))


def base_world():
    """One world, generated once per process, shared by every persona.

    At size 17 phase 16 a generation is the single largest cost in the suite, and every
    persona needs the same starting world. `FANTASY_WORLD_CONSUMER_BASE` points at a
    pre-generated file so a developer iterating on a persona does not pay for it again.
    """
    key = (SEED, SIZE)
    if key in _BASE:
        return _BASE[key]
    if CACHE and Path(CACHE).is_file():
        _BASE[key] = json.loads(Path(CACHE).read_text(encoding="utf-8"))
        return _BASE[key]
    started = time.perf_counter()
    document = world_document({"recipe_version": 3, "seed": SEED,
                               "overrides": {"size": SIZE, "phase": 16}})
    document["_generation_seconds"] = round(time.perf_counter() - started, 1)
    _BASE[key] = document
    return document


def persisted(world):
    """A world as a game actually holds it: through the export path and back off disk.

    `cli.world_document` strips `timing_ms` to keep an exported world byte-reproducible.
    Every existing test advances an in-memory world that still carries it, so the one
    workflow a real consumer uses was the one nothing exercised.
    """
    return json.loads(json.dumps(world))


# --- the join table -------------------------------------------------------------------
#
# Read off a real seed-42 size-17 world rather than guessed: no two blocks name their key
# the same way, and a consumer joining on the wrong one gets a plausible answer and a wrong
# world. Each row is (label, source path, source key, target path, target key).

JOIN_TABLE = (
    ("city plan to settlement", "city_plans.cities", "city_uid", "settlements.sites", "uid"),
    ("hamlet plan to hamlet", "hamlet_plans.hamlets", "hamlet_id", "humans.hamlets", "id"),
    ("castle plan to fortress", "castle_plans.castles", "fortress_id", "humans.fortresses", "id"),
    ("key location plan to site", "key_location_plans.plans", "location_id", "key_locations.sites", "id"),
    ("npc to staffed site", "npcs.people", "site_uid", "npcs.sites", "uid"),
    ("quest hook to its giver", "heroes.quest_hooks", "giver_uid", "heroes.people", "uid"),
)

# Blocks whose rows carry a terrain node, which is the key that survives an age boundary.
NODE_KEYED = ("settlements.sites", "humans.hamlets", "humans.fortresses", "key_locations.sites",
              "nomads.groups", "beast_nests.sites", "npcs.sites", "villains.people")


def rows(world, path):
    node = world
    for part in path.split("."):
        if not isinstance(node, dict):
            return []
        node = node.get(part)
    return node if isinstance(node, list) else []


def dangling(world):
    """Every join edge that does not resolve, as (label, source key, missing value)."""
    broken = []
    for label, source, key, target, target_key in JOIN_TABLE:
        known = {row.get(target_key) for row in rows(world, target)}
        for row in rows(world, source):
            value = row.get(key)
            if value is not None and value not in known:
                broken.append((label, key, value))
    return broken


# --- trajectories ---------------------------------------------------------------------

class Expect:
    """What a step asserts. Declared beside the call so a persona reads as a script."""

    def __init__(self, kind, **detail):
        self.kind = kind
        self.detail = detail

    def __repr__(self):
        return "Expect(%s, %r)" % (self.kind, self.detail)


def ok(*paths):
    """The call succeeds and every named path is present and non-empty."""
    return Expect("ok", paths=paths)


def refused(code, field=None, suggests=None):
    """The call is refused with this code, and optionally names this field."""
    return Expect("refused", code=code, field=field, suggests=suggests)


def unchanged(*paths):
    """The call succeeds and leaves the caller's world untouched at these paths."""
    return Expect("unchanged", paths=paths)


def value_at(world, path):
    node = world
    for part in path.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
                continue
            except (ValueError, IndexError):
                return None
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def drive(case, tools, world):
    """Run one persona step and check its expectation. Returns the step's result.

    Raises AssertionError naming the persona and the step, so a failure says which call in
    which sequence went wrong rather than only which assertion.
    """
    label, tool, args, expectation = case
    before = copy.deepcopy(world) if expectation.kind == "unchanged" else None
    try:
        result = tools[tool](world, args)
    except terrain_errors.RequestError as exc:
        document = exc.document()
        if expectation.kind != "refused":
            raise AssertionError("%s: %s was refused unexpectedly: %s"
                                 % (label, tool, document["message"]))
        assert document["code"] == expectation.detail["code"], (
            "%s: %s refused with %s, expected %s"
            % (label, tool, document["code"], expectation.detail["code"]))
        if expectation.detail.get("field") is not None:
            assert document["field"] == expectation.detail["field"], (
                "%s: %s named field %r, expected %r"
                % (label, tool, document["field"], expectation.detail["field"]))
        if expectation.detail.get("suggests") is not None:
            candidates = (document.get("suggestion") or {}).get("candidates", [])
            assert expectation.detail["suggests"] in candidates, (
                "%s: %s suggested %r, expected %r among them"
                % (label, tool, candidates, expectation.detail["suggests"]))
        return None

    assert expectation.kind != "refused", (
        "%s: %s was accepted but should have been refused with %s"
        % (label, tool, expectation.detail["code"]))
    for path in expectation.detail.get("paths", ()):
        found = value_at(result, path)
        assert found not in (None, [], {}), "%s: %s left %s empty" % (label, tool, path)
    if expectation.kind == "unchanged":
        assert world == before, "%s: %s mutated the caller's world" % (label, tool)
    return result


class Recorder:
    """The evidence a conformance record can cite, rather than a transcript that ends."""

    def __init__(self, name):
        self.name = name
        self.claims = []

    def held(self, claim, detail=None):
        self.claims.append({"claim": claim, "status": "held", "detail": detail})

    def recorded(self, claim, value):
        self.claims.append({"claim": claim, "status": "recorded", "value": value})

    def write(self):
        target = os.environ.get("FANTASY_WORLD_CONSUMER_EVIDENCE")
        if not target:
            return
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
            "schema": "fantasy-world-generator.consumer-evidence", "version": 1,
            "seed": SEED, "size": SIZE, "personas": {}}
        existing["personas"][self.name] = self.claims
        path.write_text(json.dumps(existing, indent=1, sort_keys=True) + "\n", encoding="utf-8")
