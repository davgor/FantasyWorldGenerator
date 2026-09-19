"""Compile the Unreal asset-ID registry: one binding slot per exhaustive-catalogue identity.

Every identity in the exhaustive asset list gets a row. A row either binds a concrete
Unreal object path or records an explicit unbound status; the importer diagnoses the
latter instead of spawning an anonymous cube. Later art replaces paths here, never in
an adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

from fantasy_world_generator.asset_list import compile_asset_list  # noqa: E402

SCHEMA = "fantasy-world-generator.unreal-asset-registry"
VERSION = 1
DESTINATION = ROOT / "Contracts" / "catalogues" / "unreal-asset-registry-v1.json"
OVERRIDES = ROOT / "Contracts" / "catalogues" / "unreal-asset-bindings.json"

# Debug placeholders are engine primitives, so the producer repository stays free of
# binary assets and a consumer cooks what the table names. They are registry bindings,
# not hardcoded spawns: art replaces these paths without touching an adapter.
PLACEHOLDERS = {
    "building": "/Engine/BasicShapes/Cube.Cube",
    "mesh": "/Engine/BasicShapes/Cube.Cube",
    "plant": "/Engine/BasicShapes/Cone.Cone",
    "creature": "/Engine/BasicShapes/Sphere.Sphere",
    "character": "/Engine/BasicShapes/Sphere.Sphere",
    "marker": "/Engine/BasicShapes/Cone.Cone",
    # Unlit with a Color parameter: a debug surface has to read as its lab colour
    # whatever the lighting is doing, and a real material replaces this path.
    "terrain_surface": "/Engine/EngineMaterials/EmissiveMeshMaterial.EmissiveMeshMaterial",
    "material": "/Engine/EngineMaterials/EmissiveMeshMaterial.EmissiveMeshMaterial",
}
# Kinds with no debug presentation in this slice stay explicitly unbound.
UNBOUND_KINDS = {"animation": "no_runtime_binding", "audio": "no_runtime_binding", "vfx": "no_runtime_binding"}


def _rows(assets: list[dict], overrides: dict[str, dict]) -> list[dict]:
    rows = []
    for asset in assets:
        identity = asset["id"]
        kind = asset["kind"]
        override = overrides.get(identity)
        if override is not None:
            row = {"id": identity, "kind": kind, "status": "bound", "path": override["path"]}
        elif kind in PLACEHOLDERS:
            row = {"id": identity, "kind": kind, "status": "placeholder", "path": PLACEHOLDERS[kind]}
        else:
            row = {"id": identity, "kind": kind, "status": "unbound", "reason": UNBOUND_KINDS.get(kind, "not_ready")}
        rows.append(row)
    rows.sort(key=lambda row: row["id"])
    return rows


def build_registry() -> dict:
    catalogue = compile_asset_list()
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))["bindings"] if OVERRIDES.is_file() else {}
    unknown = sorted(set(overrides) - {asset["id"] for asset in catalogue["assets"]})
    if unknown:
        raise ValueError("binding overrides name identities outside the catalogue: " + ", ".join(unknown))
    rows = _rows(catalogue["assets"], overrides)
    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "recipe_version": catalogue["recipe_version"],
        "asset_list_sha256": catalogue["content_sha256"],
        "scope": "One binding slot per exhaustive-catalogue identity; placeholder rows are bindings, not anonymous spawns.",
        "rows": rows,
    }
    body["content_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the committed table is stale")
    arguments = parser.parse_args()
    body = build_registry()
    text = json.dumps(body, indent=1, sort_keys=True) + "\n"
    if arguments.check:
        current = DESTINATION.read_text(encoding="utf-8") if DESTINATION.is_file() else ""
        if current != text:
            print("Unreal asset registry is stale; run tools/build_asset_registry.py", file=sys.stderr)
            return 1
        print(f"Unreal asset registry current: {len(body['rows'])} bindings")
        return 0
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(text, encoding="utf-8")
    print(f"Wrote {DESTINATION.relative_to(ROOT)} with {len(body['rows'])} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
