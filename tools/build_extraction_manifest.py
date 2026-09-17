"""Build the ML-00 extraction manifest from the pinned IcarusUnreal checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PINNED_COMMIT = "d551767cb1c3bd259bb00f56be1e52c2182c5ec3"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mappings(source: Path):
    for directory in ("Sim/icarus_sim", "Sim/tests", "docs/catalogue/world-assets"):
        for path in sorted((source / directory).rglob("*")):
            if path.is_file():
                relative = path.relative_to(source).as_posix()
                yield relative, relative, "Reference implementation, regression fixture, or inherited capability requirement"
    for relative in (
        "Sim/README.md",
        "tools/terrain_lab.py",
        "tools/terrain_lab.html",
        "tools/terrain_world.js",
        "docs/terrain-math-lab.md",
        "docs/terrain-world-layers.md",
        "docs/mathlab-revisions.json",
        "docs/catalogue/creatures.json",
        "docs/decisions/014-mathlab-biome-gate.md",
        "board/done/LAB-005.md",
        "board/done/LAB-006.md",
        "board/done/LAB-017.md",
        "board/done/LAB-018.md",
    ):
        yield relative, relative, "Canonical FantasyWorldGenerator documentation, dependency, or historical evidence"
    for name in ("LAB-005.md", "LAB-006.md", "LAB-017.md", "LAB-018.md"):
        yield f"docs/reviews/{name}", f"provenance/source-reviews/{name}", "Historical source review retained outside the active review namespace"
    yield "docs/catalogue/world-assets/manifest.json", "Contracts/catalogues/world-assets.json", "Pinned semantic asset-requirement input; Unreal assets and bindings remain game-owned"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "provenance/extraction-manifest.json")
    args = parser.parse_args()
    source = args.source.resolve()
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != PINNED_COMMIT:
        raise ValueError(f"source checkout is {commit}; expected pinned commit {PINNED_COMMIT}")
    rows = []
    seen = set()
    for source_name, destination_name, reason in mappings(source):
        if destination_name in seen:
            continue
        seen.add(destination_name)
        source_path = source / source_name
        destination_path = ROOT / destination_name
        if not source_path.is_file() or not destination_path.is_file():
            raise ValueError(f"missing extraction mapping: {source_name} -> {destination_name}")
        source_hash = digest(source_path)
        destination_hash = digest(destination_path)
        exact = source_hash == destination_hash
        row = {
            "source": source_name,
            "source_sha256": source_hash,
            "destination": destination_name,
            "destination_sha256": destination_hash,
            "status": "exact" if exact else "modified",
            "reason": reason,
        }
        if not exact:
            allowed_modifications = {
                "Sim/icarus_sim/terrain_humans.py": "Syntax-only quote change makes the Python 3.12 PEP 701 f-string parse on Python 3.9+; generated values are regression-tested unchanged.",
                "Sim/README.md": "Standalone commands, supported Python baseline, and future-ticket references replace source-monorepo instructions.",
                "docs/terrain-math-lab.md": "Relative game-repository links changed to immutable source-commit URLs for standalone documentation.",
                "docs/decisions/014-mathlab-biome-gate.md": "Relative game-repository links changed to immutable source-commit URLs for standalone documentation.",
                "docs/catalogue/world-assets/BUILD-ORDER.md": "Relative game-repository links changed to immutable source-commit URLs for standalone documentation.",
            }
            if destination_name not in allowed_modifications:
                raise ValueError(f"unreviewed extraction modification: {destination_name}")
            row["modification"] = allowed_modifications[destination_name]
        rows.append(row)
    document = {
        "schema_version": 1,
        "source_repository": "https://github.com/davgor/icarusUnreal.git",
        "source_commit": commit,
        "destination_repository": "https://github.com/davgor/FantasyWorldGenerator.git",
        "license_review": "No standalone source-repository license file was found. Repository ownership permits this private extraction, but public redistribution requires an explicit license decision.",
        "files": sorted(rows, key=lambda row: row["destination"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} extraction records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
