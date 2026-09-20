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

STAGES = ("checks", "sim-tests", "repo-tests", "artifacts")


def run(*command: str, env=None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def environment() -> dict:
    values = dict(os.environ)
    values["PYTHONPATH"] = str(ROOT / "Sim")
    values["PYTHONPYCACHEPREFIX"] = str(ROOT / ".pycache")
    return values


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
    run(sys.executable, "tools/verify_provenance.py", env=env)
    # Documents describing the product must point at things that exist and state
    # versions the code agrees with. Structural only: it cannot tell whether a record
    # is true, and a green run is not documentation review.
    run(sys.executable, "tools/docs_check.py", env=env)
    run(sys.executable, "-m", "compileall", "-q", "Sim/icarus_sim", "Sim/fantasy_world_generator", "tools", env=env)


def sim_tests(env) -> None:
    run(sys.executable, "-m", "unittest", "discover", "-s", "Sim/tests", "-p", "test_*.py", "-v", env=env)


def repo_tests(env) -> None:
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v", env=env)


def artifacts(env) -> None:
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
        if world_first.read_bytes() != world_second.read_bytes():
            raise ValueError("world generation is not byte-reproducible")

        # The size-17 world above resolves NONE of its five noise octaves. Octave
        # admission needs step <= wavelength/2^k, and 17 is far too coarse to admit even
        # the first, so the multi-octave surface accumulation -- the filtered loop, the
        # .5**k falloff, the ridge term -- contributes identically zero and never runs.
        # Sim/tests/test_terrain_metrics.py already asserts the noise layer is zero at
        # exactly this configuration. So the guarantee above covers a world with no
        # surface relief, which is not a world anyone ships.
        #
        # 513 is the first size that admits all five octaves, and phase 5 stops before
        # settlements, ages and city planning, so this pair costs about four minutes
        # rather than the hours a full phase-16 world at 513 would take.
        octaves_first = Path(directory) / "world-octaves-first.json"
        octaves_second = Path(directory) / "world-octaves-second.json"
        for target in (octaves_first, octaves_second):
            run(sys.executable, "-m", "fantasy_world_generator", "generate",
                "--seed", "42", "--size", "513", "--phase", "5", "--output", str(target), env=env)
        if octaves_first.read_bytes() != octaves_second.read_bytes():
            raise ValueError("full-octave world generation is not byte-reproducible")
        # Moving the size fixes today; asserting the octaves resolved keeps it fixed. If a
        # future wavelength or plate-count change stops admitting the fifth octave here,
        # this fails loudly instead of quietly guaranteeing determinism over nothing.
        document = json.loads(octaves_first.read_text(encoding="utf-8"))
        resolved = document.get("resolved_octaves")
        requested = document.get("effective_config", document.get("config", {})).get("octaves")
        if resolved != requested:
            raise ValueError("size 513 must resolve every noise octave for the determinism "
                             f"guarantee to cover the accumulation path; resolved {resolved} of {requested}")


RUNNERS = {"checks": checks, "sim-tests": sim_tests, "repo-tests": repo_tests, "artifacts": artifacts}


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
