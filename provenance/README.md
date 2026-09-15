# Extraction provenance

`extraction-manifest.json` records the pinned source commit, source and destination paths, SHA-256 hashes, reasons, and any reviewed extraction-time modification. Run the following only against the pinned source checkout when intentionally rebuilding the manifest:

```bash
python3 tools/build_extraction_manifest.py --source ../icarusUnreal
```

Ordinary validation uses `tools/verify_provenance.py` and does not require the source repository. Any intentional edit to an extracted file needs its own reviewed revision record; do not regenerate the manifest merely to hide drift.

The source repository contains no standalone license file. This extraction is maintained by the same repository owner, but public redistribution remains blocked until an explicit license is selected. Game-owned Unreal assets and object-path bindings are not included here.


## Initial checkout checksum correction

The initial manifest measured working-tree line endings before `* text=auto` stored LF blobs in Git.
The publishing change verifies 22 original destination hashes against retained original bytes or an
exact LF-to-CRLF conversion and records the committed LF destination hashes. The initial standalone
MathLab document checksum is also reconciled to its committed document, retaining the existing
source-link rewrite explanation. Each correction has an explicit modification record; original
source hashes remain unchanged. No simulator bytes or algorithms are changed by this correction.

`.gitattributes` now pins LF on checkout as well as in Git, keeping these byte hashes stable on Windows.
