"""Cook the consumer project for Win64, run the packaged generate-to-materialize loop and record the evidence.

This is the ML-03e asset-production gate: a clean cooked Win64 executable that
generates a world in process and materializes it, with the exact package digest and
the run's own reported numbers written to Artifacts/unreal/. A green Python suite or a
PIE capture is not this gate.

The Unreal Editor must be closed: Live Coding holds the build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE = Path(r"C:\Program Files\Epic Games\UE_5.8")
DEFAULT_PROJECT = ROOT.parent / "UnrealWorldGen"
RESULT_PATTERN = re.compile(r"FWG_RESULT ([^\r\n]+)")
FRAME_PATTERN = re.compile(r"FWG_FRAME ([^\r\n]+)")


def run(command: list[str], timeout: int) -> subprocess.CompletedProcess:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, text=True, timeout=timeout, capture_output=True)


def digest_tree(root: Path) -> tuple[str, int, int]:
    """Content digest of the staged package: every file path and its bytes, in order."""
    accumulator = hashlib.sha256()
    files = 0
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        # The game writes logs, screenshots and config under Saved/ when it runs. The
        # digest identifies the build, so what the build produced afterwards is out.
        if "Saved/" in relative or relative.startswith("Saved"):
            continue
        data = path.read_bytes()
        accumulator.update(relative.encode("utf-8"))
        accumulator.update(b"\0")
        accumulator.update(hashlib.sha256(data).digest())
        files += 1
        total += len(data)
    return accumulator.hexdigest(), files, total


def parse_result(text: str, pattern: re.Pattern = RESULT_PATTERN) -> dict:
    match = None
    for match in pattern.finditer(text):
        pass
    if match is None:
        return {}
    values = {}
    for pair in match.group(1).split():
        key, _, value = pair.partition("=")
        try:
            values[key] = int(value) if value.lstrip("-").isdigit() else float(value)
        except ValueError:
            values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--configuration", default="Development", choices=("Development", "Shipping"))
    parser.add_argument("--seed", type=int, default=20260918)
    # The consumer's own default: a vertex every 19.5 metres on a twenty kilometre
    # world, which is the resolution the biome boundaries are presented at.
    parser.add_argument("--rows", type=int, default=513)
    parser.add_argument("--stage-dir", type=Path, default=None, help="where the cook stages the build")
    parser.add_argument("--skip-cook", action="store_true", help="run an existing package instead of cooking")
    parser.add_argument("--evidence", type=Path, default=ROOT / "Artifacts/unreal/packaged-run.json")
    parser.add_argument("--replay", action="store_true",
                        help="run the packaged build three times: the seed twice and a second seed once, "
                             "so replay equality and seed sensitivity are both recorded")
    parser.add_argument("--ubt-args", default=None,
                        help="passed to UnrealBuildTool, e.g. -NoHotReloadFromIDE when another editor is open "
                             "on an unrelated project")
    arguments = parser.parse_args()

    project = arguments.project.resolve()
    uproject = next(iter(project.glob("*.uproject")), None)
    if uproject is None:
        print(f"no .uproject in {project}", file=sys.stderr)
        return 2
    stage = (arguments.stage_dir or project / "Saved" / "PackagedWin64").resolve()
    uat = arguments.engine / "Engine/Build/BatchFiles/RunUAT.bat"
    if not uat.is_file():
        print(f"RunUAT not found: {uat}", file=sys.stderr)
        return 2

    if not arguments.skip_cook:
        cook = run([str(uat), "BuildCookRun",
                    f"-project={uproject}",
                    "-noP4", "-platform=Win64", f"-clientconfig={arguments.configuration}",
                    "-cook", "-build", "-stage", "-pak", "-archive",
                    f"-archivedirectory={stage}",
                    "-utf8output"]
                   + ([f"-ubtargs={arguments.ubt_args}"] if arguments.ubt_args else []),
                   timeout=7200)
        (ROOT / "Artifacts/unreal").mkdir(parents=True, exist_ok=True)
        (ROOT / "Artifacts/unreal/cook.log").write_text(cook.stdout + cook.stderr, encoding="utf-8", errors="replace")
        if cook.returncode:
            print(cook.stdout[-6000:])
            print(cook.stderr[-4000:], file=sys.stderr)
            print("cook failed; see Artifacts/unreal/cook.log", file=sys.stderr)
            return cook.returncode

    executables = sorted(stage.rglob("*.exe"))
    executable = next((path for path in executables if path.stem.lower() == uproject.stem.lower()
                       and "Binaries" in path.parts), None)
    if executable is None:
        print(f"no packaged executable under {stage}", file=sys.stderr)
        return 2
    # The digest covers the whole staged package, not one directory inside it.
    package_root = executable.parents[2]
    platform_root = package_root.parent
    digest, files, total = digest_tree(platform_root)

    log = package_root / "Saved" / "Logs" / (uproject.stem + ".log")
    if log.is_file():
        log.unlink()
    def play(seed: int, capture: bool) -> tuple[dict, str, int]:
        command = [str(executable), f"-FWGSeed={seed}", f"-FWGRows={arguments.rows}",
                   "-FWGExitAfterGenerate", "-windowed", "-resx=1600", "-resy=900",
                   "-unattended", "-nosplash", "-stdout", "-fullstdoutlogoutput"]
        if capture:
            command.insert(3, "-FWGScreenshot")
        outcome = run(command, timeout=1800)
        body = outcome.stdout + outcome.stderr
        if log.is_file():
            body += log.read_text(encoding="utf-8", errors="replace")
            log.unlink()
        return parse_result(body), body, outcome.returncode

    started = time.time()
    result, text, exit_code = play(arguments.seed, True)
    elapsed = time.time() - started
    (ROOT / "Artifacts/unreal/packaged-run.log").write_text(text, encoding="utf-8", errors="replace")
    replay = {}
    if arguments.replay:
        # Same seed twice: the packaged build has to reproduce its own world. A second
        # seed proves the first comparison is not measuring a constant.
        again, _, _ = play(arguments.seed, False)
        other, _, _ = play(arguments.seed + 1, False)
        comparable = [key for key in result if key not in ("generate_ms", "materialize_ms")]
        replay = {
            "same_seed_identical": all(result.get(key) == again.get(key) for key in comparable),
            "other_seed_differs": any(result.get(key) != other.get(key) for key in comparable),
            "second_run": again,
            "other_seed": other,
        }
    screenshots = sorted((package_root / "Saved" / "Screenshots").rglob("*.png"))

    evidence = {
        "schema": "fantasy-world-generator.packaged-run",
        "version": 1,
        "engine": {"root": str(arguments.engine), "configuration": arguments.configuration, "platform": "Win64"},
        "project": str(project),
        "executable": str(executable),
        "package_root": str(platform_root),
        "package_digest_sha256": digest,
        "package_files": files,
        "package_bytes": total,
        "exit_code": exit_code,
        "wall_clock_seconds": round(elapsed, 2),
        "requested": {"seed": arguments.seed, "latitude_rows": arguments.rows},
        "reported": result,
        "frame_checks": parse_result(text, FRAME_PATTERN),
        "replay": replay,
        "screenshots": [str(path) for path in screenshots],
        "note": "Cooked Win64 executable, no editor and no Python runtime in the loop. "
                "The reported block is the game's own FWG_RESULT line.",
    }
    arguments.evidence.parent.mkdir(parents=True, exist_ok=True)
    arguments.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    if not result:
        print("packaged run did not report FWG_RESULT; see Artifacts/unreal/packaged-run.log", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
