# Extraction provenance

`extraction-manifest.json` records the pinned source commit, source and destination paths, SHA-256 hashes, reasons, and any reviewed extraction-time modification. Run the following only against the pinned source checkout when intentionally rebuilding the manifest:

```bash
python3 tools/build_extraction_manifest.py --source ../icarusUnreal
```

Ordinary validation uses `tools/verify_provenance.py` and does not require the source repository. Any intentional edit to an extracted file needs its own reviewed revision record; do not regenerate the manifest merely to hide drift.

For a reviewed destination update, retain the original source hash and previous revisions, append the previous/new destination hashes with the date, reason and canonical document, then update the current destination hash. Hash corrections must identify the committed behavior reviewed and its regression coverage. The 2026-09-16 ML-00 follow-up repairs stale final-edit hashes for `terrain_climate.py` and `terrain_patch.py` from commit `4ea7169`; it changes no source or simulation behavior.

The pinned source repository contains no standalone license file. This extraction is maintained by the same repository owner. The destination now uses the [private distribution policy](../LICENSE) recorded in [decision 017](../docs/decisions/017-private-package-distribution.md); it does not clear third-party provenance or authorize public redistribution. Game-owned Unreal assets and object-path bindings are not included here.


`.gitattributes` disables text normalization for **every** manifest destination, not only the inherited files whose recorded bytes contain CRLF or mixed line endings. Their original bytes are stored in Git so clean checkouts pass the same provenance checks as the development workspace. This changes neither Python behavior nor source hashes.

That list used to be maintained by hand and fell behind the manifest. Because `verify_provenance.py` hashes working-tree bytes, a `text=auto` destination checked out on Windows as CRLF failed against a hash recorded from the LF original — 35 files at once, so the check could not pass on a Windows workspace even when nothing had actually drifted. `tests/test_provenance_bytes.py` now fails when a manifest destination, or a byte-identical mirror of one such as `Sim/fantasy_world_generator/world_asset_requirements.json`, is missing its `-text` entry.

The 2026-09-18 war revisions cover `terrain_humans.py`, `terrain_settlements.py`, `test_terrain_city_layout.py` and the canonical document: contested neighbours now fight during an age transition, the loser becomes a ruin naming the war, both sides keep a `war_history` that survivors carry across the rebuild, and a veteran city raises its own defences. Settlement schema moves to 15, history to 2, rural report to 8 and threat assessment to 2, so every existing world must be regenerated; `Core/wars.cpp` mirrors the rules for the native parity gate.

The 2026-09-18 fortress revisions cover `terrain_humans.py`, `terrain_lab.py`, `terrain_world.py`, `test_terrain_humans.py` and the two canonical documents together: how many route-defence fortresses a world holds now follows its own road length, support reach, distinct river crossings and city count, and `fortress_count` became a caller's ceiling whose default no longer binds. This changes generated worlds for every existing seed, so the rural report moved to 7 and age advancement refuses an older one; `Core/humans.cpp` mirrors the same demand for the native parity gate.

The 2026-09-17 revisions cover the lab ruin icon in commit `0e2fd68`: `terrain_world.js`, `terrain_lab.html` and the `terrain-world-layers.md` description changed together, and `Sim/tests/test_terrain_lab.py` moved from `exact` to `modified` because it gained an assertion for the new renderer helper. Presentation only; no generated-world contract changed.
