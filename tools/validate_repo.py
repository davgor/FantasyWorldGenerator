"""Run repository checks and verify deterministic publish inputs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(*command: str, env=None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    required = [
        "README.md",
        "AGENTS.md",
        "pyproject.toml",
        "Contracts/schemas/world-output.schema.json",
        "Contracts/schemas/asset-list.schema.json",
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

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "Sim")
    environment["PYTHONPYCACHEPREFIX"] = str(ROOT / ".pycache")
    run(sys.executable, "tools/verify_provenance.py", env=environment)
    run(sys.executable, "-m", "compileall", "-q", "Sim/icarus_sim", "Sim/fantasy_world_generator", "tools", env=environment)
    run(sys.executable, "-m", "unittest", "discover", "-s", "Sim/tests", "-p", "test_*.py", "-v", env=environment)
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v", env=environment)
    run(sys.executable, "tools/smoke_lab.py", env=environment)

    with tempfile.TemporaryDirectory() as directory:
        first = Path(directory) / "first.json"
        second = Path(directory) / "second.json"
        run(sys.executable, "-m", "fantasy_world_generator", "asset-list", "--output", str(first), env=environment)
        run(sys.executable, "-m", "fantasy_world_generator", "asset-list", "--output", str(second), env=environment)
        if first.read_bytes() != second.read_bytes():
            raise ValueError("asset-list compilation is not byte-reproducible")
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
