# Extraction provenance

`extraction-manifest.json` records the pinned source commit, source and destination paths, SHA-256 hashes, reasons, and any reviewed extraction-time modification. Run the following only against the pinned source checkout when intentionally rebuilding the manifest:

```bash
python3 tools/build_extraction_manifest.py --source ../icarusUnreal
```

Ordinary validation uses `tools/verify_provenance.py` and does not require the source repository. Any intentional edit to an extracted file needs its own reviewed revision record; do not regenerate the manifest merely to hide drift.

For a reviewed destination update, retain the original source hash and previous revisions, append the previous/new destination hashes with the date, reason and canonical document, then update the current destination hash. Hash corrections must identify the committed behavior reviewed and its regression coverage. The 2026-09-16 ML-00 follow-up repairs stale final-edit hashes for `terrain_climate.py` and `terrain_patch.py` from commit `4ea7169`; it changes no source or simulation behavior.

The pinned source repository contains no standalone license file. This extraction is maintained by the same repository owner. The destination now uses the [private distribution policy](../LICENSE) recorded in [decision 017](../docs/decisions/017-private-package-distribution.md); it does not clear third-party provenance or authorize public redistribution. Game-owned Unreal assets and object-path bindings are not included here.


`.gitattributes` disables text normalization for inherited files whose recorded bytes contain CRLF or mixed line endings. Their original bytes are stored in Git so clean checkouts pass the same provenance checks as the development workspace. This changes neither Python behavior nor source hashes.
