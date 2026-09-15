# Extraction provenance

`extraction-manifest.json` records the pinned source commit, source and destination paths, SHA-256 hashes, reasons, and any reviewed extraction-time modification. Run the following only against the pinned source checkout when intentionally rebuilding the manifest:

```bash
python3 tools/build_extraction_manifest.py --source ../icarusUnreal
```

Ordinary validation uses `tools/verify_provenance.py` and does not require the source repository. Any intentional edit to an extracted file needs its own reviewed revision record; do not regenerate the manifest merely to hide drift.

The source repository contains no standalone license file. This extraction is maintained by the same repository owner, but public redistribution remains blocked until an explicit license is selected. Game-owned Unreal assets and object-path bindings are not included here.


`.gitattributes` disables text normalization for inherited files whose recorded bytes contain CRLF or mixed line endings. Their original bytes are stored in Git so clean checkouts pass the same provenance checks as the development workspace. This changes neither Python behavior nor source hashes.
