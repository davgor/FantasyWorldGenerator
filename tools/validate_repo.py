"""Run repository checks and verify deterministic publish inputs.

Runs everything by default. `--stage` selects one part so CI can spread the work
across parallel jobs: the two unittest suites together take most of the wall
clock and used to sit in a single job against a 20 minute ceiling.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]

STAGES = ("checks", "sim-tests", "repo-tests", "consumers", "artifacts")


def reap(process) -> None:
    """Stop `process` AND everything it spawned, matching only PIDs descended from it.

    `process.terminate()` reaches exactly the process this parent holds a handle to and
    nothing underneath it. On this tree that is never the process worth killing, for two
    compounding reasons, both measured on 2026-09-21 rather than reasoned:

    * `sys.executable` here is a ~5 MB `Scripts/python.exe` shim that spawns the real
      `Python312/python.exe`. `Popen` hands back the shim's PID; the work runs in a
      different process. Terminating the shim does take its own worker with it -- that
      part was checked twice and holds -- so this is not the leak by itself.
    * `--stage repo-tests` is three deep: this spawns `unittest discover`, inside which
      `tests/test_showcase.py` spawns the showcase exporter. A probe mirroring that chain
      terminated the top handle and found the GRANDCHILD still running, twice. It is
      hard-killed level 2 that never gets to run its own cleanup, so cleanup written at
      every level cannot close this; only walking the tree can.

    Windows walks the tree with `taskkill /T`, and it must run BEFORE the handle dies:
    once the intermediate process is gone its descendants are re-parented and no longer
    reachable from this PID. `terminate()` on Windows is already `TerminateProcess`, so
    leading with the tree kill gives up no graceful shutdown that existed.

    POSIX keeps the single-child `terminate` -> bounded `wait` -> `kill` sequence. There
    is no shim there and the grandchild case is left OPEN rather than fixed: closing it
    means `start_new_session=True` plus `killpg`, which detaches the child from the
    terminal's signal group, and that trade could not be tested on this machine. See
    board/done/PERF-SUITE-RUNNER-ORPHANS-CHILD.md.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        # By PID, never by image name. The process list on this tree is full of other
        # sessions' work and `taskkill /IM python.exe` would destroy a peer's run.
        #
        # Everything here runs in a `finally`, usually while a KeyboardInterrupt is in
        # flight. An exception raised from this block would REPLACE that interrupt, so a
        # missing taskkill or a slow one must not become the error the operator sees --
        # fall through to the direct-child kill instead, which is worse but not silent.
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    except OSError:
        pass


def run(*command: str, env=None) -> None:
    """Run `command` to completion, naming the child's PID, and never outlive it.

    `subprocess.run(..., check=True)` is shorter and it is NOT the leak it looks like:
    CPython's `run` wraps `communicate` in a bare `except:` that calls `process.kill()`,
    so a Ctrl-C or any other exception in this process already reaps the direct child.
    Two things it cannot do, and both matter here.

    It cannot say WHICH child: it returns a `CompletedProcess`, which carries no PID. When
    this process is hard-killed -- which no parent can intercept, and which is how a
    stopped background task actually ends -- the descendants survive holding a world each,
    and on a tree shared by five sessions an anonymous survivor cannot be killed safely.
    Printing the PID is what makes one safe to kill, and printing it requires holding the
    `Popen`.

    And it cannot reach past the direct child, which is where the real leak is. See `reap`.
    """
    process = subprocess.Popen(command, cwd=ROOT, env=env)
    print("+ [pid %d] %s" % (process.pid, " ".join(command)), flush=True)
    try:
        code = process.wait()
    finally:
        reap(process)
    if code:
        raise subprocess.CalledProcessError(code, command)


def environment() -> dict:
    values = dict(os.environ)
    values["PYTHONPATH"] = str(ROOT / "Sim")
    values["PYTHONPYCACHEPREFIX"] = str(ROOT / ".pycache")
    return values


# The sections a completed world always carries. Kept identical to the list in
# `tests/test_world_schema_conformance.py` and `Contracts/schemas/world-output.schema.json`
# so the gate, the suite and the contract fail together instead of disagreeing.
#
# Declared below `run` on purpose: board/done/PERF-SUITE-RUNNER-ORPHANS-CHILD.md cites
# `run` by line number, and tools/docs_check.py's CITE rule checks the cited line, so a
# constant inserted above it silently retargets somebody else's citation.
VERSIONED_SECTIONS = ("terrain", "settlements", "civilizations", "city_plans", "hamlet_plans",
                      "castle_plans", "world_scene", "astrology", "lunar_almanac", "religion")


def option_registry():
    """`terrain_world.registry(3)`, the published domain of every generation option."""
    if str(ROOT / "Sim") not in sys.path:
        sys.path.insert(0, str(ROOT / "Sim"))
    from icarus_sim.terrain_world import registry
    return registry(3)


def out_of_domain(option: dict, value) -> bool:
    """Whether `value` is outside the domain `option` declares.

    Only the two kinds of domain the registry actually publishes are understood: a
    `choices` list and a `min`/`max` pair. An option declaring neither is not something
    this function can decide, and it says so by returning False rather than by guessing.
    """
    if "choices" in option:
        return value not in option["choices"]
    low, high = option.get("min"), option.get("max")
    if low is None or high is None:
        return False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    return not low <= value <= high


def rejection_fixtures() -> None:
    """Every override in an `invalid_*` fixture list must still be outside its bound.

    A rejection case needs an input the product refuses. The obvious value is the smallest
    such input -- one more than the current limit -- which is correct the day it is written
    and wrong, silently, the day the limit moves. Nothing errors when that happens: the
    input has become legal, so instead of being rejected it is EXECUTED, and a rejection
    fixture becomes a world generation. The only symptom is a suite that got slower, which
    is the one symptom nobody investigates.

    This has already fired. Raising the grid ceiling from 257 to 1025 in `4713f9a` turned
    three "one above the limit" sentinels into legal work at once, and `Fixtures/
    unreal-frame-v1.json` still carries the repaired value as a literal -- 1026, which is
    one above the ceiling again.

    JSON cannot compute its own sentinel, so the loader has to. This reads the bound from
    `registry(3)` rather than restating it, which is what makes the check itself immune:
    it cannot be satisfied by moving a number, only by moving the fixture back out of
    range. It fails at the instant a ceiling moves and names the entry, instead of an hour
    later when someone notices `--stage repo-tests` stopped terminating.

    Scope, stated so this is not read as more than it is: only values under `overrides`
    whose key the registry declares a domain for are decidable here. An entry that is
    invalid for a reason the registry does not publish -- a retired `recipe_version`, a
    malformed body -- carries no such override and this check says nothing about it.
    """
    options = option_registry()
    legal = []
    for path in sorted((ROOT / "Fixtures").glob("*.json")):
        text = path.read_text(encoding="utf-8")
        # A rejection fixture declares its cases in "invalid_*" fields, so a file carrying
        # none of them cannot contribute one. Checked as text first because Fixtures/ now
        # also holds the lab's 162 MB sample world, and parsing it here would cost seconds
        # and hundreds of megabytes to reach the same `continue`.
        if '"invalid_' not in text:
            continue
        document = json.loads(text)
        if not isinstance(document, dict):
            continue
        for field, entries in document.items():
            if not field.startswith("invalid_") or not isinstance(entries, list):
                continue
            for index, entry in enumerate(entries):
                overrides = entry.get("overrides") if isinstance(entry, dict) else None
                for name, value in (overrides or {}).items():
                    option = options.get(name)
                    if option is None or out_of_domain(option, value):
                        continue
                    bound = (f"choices {option['choices']}" if "choices" in option
                             else f"{option.get('min')}..{option.get('max')}")
                    legal.append(f"{path.name} {field}[{index}] {name}={value!r} "
                                 f"is inside the declared domain ({bound})")
    if legal:
        raise ValueError(
            "rejection fixtures carry values the product now accepts, so they generate a "
            "world instead of being refused: " + "; ".join(legal) +
            ". Derive the sentinel from the declared bound instead of restating it.")


def compare_worlds(first: Path, second: Path, label: str, require=()) -> dict:
    """Assert two generated worlds are byte-identical, and say WHICH block drifted if not.

    The byte comparison stays the primary gate -- it is the strictest statement available
    and the interchange artifact is shipped as bytes. What it cannot do is either half of
    what an operator needs when it goes red:

    * It names nothing. "world generation is not byte-reproducible" tells whoever is
      holding the pager that determinism broke and nothing about where, so the next step
      is a hand diff of two multi-megabyte documents.
    * It is satisfied by two documents that are byte-identical and structurally empty.
      Equality is necessary and not sufficient: a generator that stopped emitting
      `settlements` would compare equal to itself all day.

    So on failure this parses both and names the first top-level block whose canonical
    digest differs, and on success it checks the blocks in `require` are present and
    non-empty. `require` is per-pair on purpose -- a phase-gated world legitimately has
    fewer blocks than a completed one, and demanding them there would be asserting
    something untrue.
    """
    if first.read_bytes() != second.read_bytes():
        try:
            left = json.loads(first.read_text(encoding="utf-8"))
            right = json.loads(second.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"{label} is not byte-reproducible, and the document does not "
                             f"parse either: {error}") from None
        drifted = []
        for key in sorted(set(left) | set(right)):
            marker = (json.dumps(left.get(key), sort_keys=True, default=str),
                      json.dumps(right.get(key), sort_keys=True, default=str))
            if marker[0] != marker[1]:
                drifted.append(key)
        raise ValueError(f"{label} is not byte-reproducible; these top-level blocks differ "
                         f"between the two runs: {drifted or ['none -- the parsed content is equal, so the difference is in key order or formatting']}")
    document = json.loads(first.read_text(encoding="utf-8"))
    empty = [key for key in require if not document.get(key)]
    if empty:
        raise ValueError(f"{label} is byte-reproducible over a document that is missing or "
                         f"empty in {empty}. Reproducing nothing reproducibly is not the "
                         "guarantee this gate is here to make.")
    return document


def checks(env) -> None:
    required = [
        "README.md",
        "AGENTS.md",
        "pyproject.toml",
        "Contracts/schemas/world-output.schema.json",
        "Contracts/schemas/asset-list.schema.json",
        "Contracts/catalogues/unreal-asset-registry-v1.json",
        "Contracts/catalogues/native-catalogues-v1.json",
        "Fixtures/native-world-v1.json",
        "Sim/icarus_sim/terrain_world.py",
        "Sim/fantasy_world_generator/world_asset_requirements.json",
        "provenance/extraction-manifest.json",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise ValueError("missing required repository files: " + ", ".join(missing))
    for schema in (ROOT / "Contracts/schemas").glob("*.json"):
        json.loads(schema.read_text(encoding="utf-8"))
    rejection_fixtures()
    packaged_catalogue = ROOT / "Sim/fantasy_world_generator/world_asset_requirements.json"
    documented_catalogue = ROOT / "Contracts/catalogues/world-assets.json"
    if packaged_catalogue.read_bytes() != documented_catalogue.read_bytes():
        raise ValueError("packaged and canonical world asset requirements differ")
    # The catalogue exists as three byte-identical copies. Only two of the pairs were
    # compared, so the documentation copy could drift from the contract unnoticed while
    # every check stayed green.
    catalogue_mirror = ROOT / "docs/catalogue/world-assets/manifest.json"
    if catalogue_mirror.read_bytes() != documented_catalogue.read_bytes():
        raise ValueError("documented catalogue mirror and canonical world assets differ")
    # The Unreal asset registry is generated from the exhaustive catalogue, so a
    # new identity must not reach a consumer without a binding slot.
    run(sys.executable, "tools/build_asset_registry.py", "--check", env=env)
    # The native catalogue is generated from the authoring registries; a trait edit that
    # never reaches the generator would otherwise pass unnoticed.
    run(sys.executable, "tools/export_catalogues.py", "--check", env=env)
    # The control catalogue is the one table Python, Core and the plugin all read. It also
    # carries the two facts a caller cannot otherwise see: which controls are pinned shut,
    # and which are derived from the authored world shape.
    run(sys.executable, "tools/export_controls.py", "--check", env=env)
    run(sys.executable, "tools/verify_provenance.py", env=env)
    # Documents describing the product must point at things that exist and state
    # versions the code agrees with. Structural only: it cannot tell whether a record
    # is true, and a green run is not documentation review.
    run(sys.executable, "tools/docs_check.py", env=env)
    run(sys.executable, "-m", "compileall", "-q", "Sim/icarus_sim", "Sim/fantasy_world_generator", "tools", env=env)


def sim_tests(env) -> None:
    run(sys.executable, "-m", "unittest", "discover", "-s", "Sim/tests", "-p", "test_*.py", "-v", env=env)


def consumers(env) -> None:
    """The scripted consumers: the orchestrator's calls, in the order a game makes them.

    Its own stage rather than part of `repo-tests`, which already runs the showcase
    exporter and is near its ceiling. These are discovered by a `consumer_*.py` pattern so
    the two unittest suites cannot pick them up and charge for them twice.
    """
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "consumer_*.py",
        "-v", env=env)


def repo_tests(env) -> None:
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v", env=env)


def artifacts(env) -> None:
    # The lab serves a committed world instead of generating one per page load, so the
    # sample is now a generated file like the catalogues -- and the only gate that can
    # catch a recipe change it no longer matches is a rebuild. That costs a full world
    # (about 80 s at the pinned size), which is why it sits in this stage and not in
    # `checks`. Ahead of smoke_lab, which serves the file this proves is current.
    run(sys.executable, "tools/build_sample_world.py", "--check", env=env)
    run(sys.executable, "tools/smoke_lab.py", env=env)
    with tempfile.TemporaryDirectory() as directory:
        first = Path(directory) / "first.json"
        second = Path(directory) / "second.json"
        run(sys.executable, "-m", "fantasy_world_generator", "asset-list", "--output", str(first), env=env)
        run(sys.executable, "-m", "fantasy_world_generator", "asset-list", "--output", str(second), env=env)
        if first.read_bytes() != second.read_bytes():
            raise ValueError("asset-list compilation is not byte-reproducible")

        # The world document is the Unreal interchange artifact, so it needs the
        # same guarantee the catalogue already had. Embedded wall-clock timings
        # used to break this, and nothing checked it.
        world_first = Path(directory) / "world-first.json"
        world_second = Path(directory) / "world-second.json"
        for target in (world_first, world_second):
            run(sys.executable, "-m", "fantasy_world_generator", "generate",
                "--seed", "42", "--size", "17", "--output", str(target), env=env)
        # The ten sections `tests/test_world_schema_conformance.py` asserts a generated
        # world carries. Pinned here too so a world that quietly stopped carrying one
        # fails the determinism gate and the conformance suite together, rather than the
        # gate passing over an emptier and emptier document while the suite alone objects.
        compare_worlds(world_first, world_second, "world generation", require=VERSIONED_SECTIONS)

        # The size-17 world above resolves NONE of its five noise octaves. Octave
        # admission needs step <= wavelength/2^k, and 17 is far too coarse to admit even
        # the first, so the multi-octave surface accumulation -- the filtered loop, the
        # .5**k falloff, the ridge term -- contributes identically zero and never runs.
        # Sim/tests/test_terrain_metrics.py measures that across the whole 17/33/65 ladder:
        # zero octaves resolve at 17 and the noise layer is identically zero there. So the
        # guarantee above covers a world with no surface relief, which is not a world
        # anyone ships -- the `require` list is what stops it also covering an empty one.
        #
        # 513 is the first size that admits all five octaves, and phase 5 stops before
        # settlements, ages and city planning, so this pair costs about four minutes
        # rather than the hours a full phase-16 world at 513 would take.
        octaves_first = Path(directory) / "world-octaves-first.json"
        octaves_second = Path(directory) / "world-octaves-second.json"
        for target in (octaves_first, octaves_second):
            run(sys.executable, "-m", "fantasy_world_generator", "generate",
                "--seed", "42", "--size", "513", "--phase", "5", "--output", str(target), env=env)
        # `require` is empty here and that is deliberate: this pair stops at phase 5, so it
        # has no settlements, no ages and no plans, and demanding them would assert
        # something the configuration cannot produce.
        document = compare_worlds(octaves_first, octaves_second,
                                  "full-octave world generation", require=())
        # Moving the size fixes today; asserting the octaves resolved keeps it fixed. If a
        # future wavelength or plate-count change stops admitting the fifth octave here,
        # this fails loudly instead of quietly guaranteeing determinism over nothing.
        resolved = document.get("resolved_octaves")
        requested = document.get("effective_config", document.get("config", {})).get("octaves")
        if resolved != requested:
            raise ValueError("size 513 must resolve every noise octave for the determinism "
                             f"guarantee to cover the accumulation path; resolved {resolved} of {requested}")


RUNNERS = {"checks": checks, "sim-tests": sim_tests, "repo-tests": repo_tests,
           "consumers": consumers, "artifacts": artifacts}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate the repository.")
    parser.add_argument("--stage", choices=(*STAGES, "all"), default="all",
                        help="Run one stage instead of all of them (default: all)")
    args = parser.parse_args(argv)
    env = environment()
    selected = STAGES if args.stage == "all" else (args.stage,)
    for name in selected:
        # Every stage begins with the cheap structural checks so a partial CI run
        # still fails fast on a missing file or an unrevised provenance hash.
        if name != "checks" and args.stage != "all":
            checks(env)
        RUNNERS[name](env)
    print(f"Repository validation passed ({args.stage}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
