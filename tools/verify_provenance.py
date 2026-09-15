"""Verify extracted destination bytes against the checked-in extraction manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest = json.loads((ROOT / "provenance/extraction-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not manifest.get("source_commit") or not manifest.get("files"):
        raise ValueError("invalid extraction manifest")
    destinations = set()
    for row in manifest["files"]:
        destination = row["destination"]
        if destination in destinations:
            raise ValueError(f"duplicate provenance destination: {destination}")
        destinations.add(destination)
        path = (ROOT / destination).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"missing or unsafe extracted file: {destination}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["destination_sha256"]:
            raise ValueError(f"extracted file changed without a provenance revision: {destination}")
        if row["status"] == "exact" and digest != row["source_sha256"]:
            raise ValueError(f"exact extraction hash differs from source: {destination}")
    print(f"Provenance validation passed for {len(destinations)} extracted files from {manifest['source_commit']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

