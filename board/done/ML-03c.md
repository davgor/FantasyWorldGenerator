# ML-03c — Reproducible native source proof and isolated consumer

## Scope

Package the bounded native proof so another checkout-independent consumer can
compile and test it using C++17 and a Python orchestration script, without the
Python simulation, Unreal, game assets or downloaded libraries. This is local
source evidence, not an engine-qualified or publicly published runtime release.

## Acceptance

- Identical inputs produce byte-identical source ZIPs with fixed metadata and a
  full SHA-256 filename, license, contract versions, sources and fixtures.
- A clean extracted consumer verifies its complete allowlisted source hashes,
  compiles and executes the native fixture driver, and records actual toolchain
  and source identities in a qualification report.
- Source tampering and unsupported/malformed manifests fail; a rejected run does
  not leave an earlier passing report as the current result.
- Tests precede packaging behavior and full repository validation passes.

## Current evidence — 2026-09-16

`tools/package_native.py` and the included `tools/qualify_native.py` implement the
source proof. The packaging test initially failed for the missing tool. It now
compares two complete archives, builds from an extracted temporary directory
outside the checkout, runs shared fixtures and rejects altered source/metadata.
A malformed-manifest test caught a stale success report; the failure handling and
strict metadata validation were corrected. The native binary has no Python
runtime dependency; Python only orchestrates compilation/tests.

A retained local archive is
`Artifacts/native/fantasy-world-generator-native-source-6c35250735d341fe83a77ad05bf0c75cd6c670e55d9f40d4b82c4ca98bdde54a.zip`.
Its isolated Apple clang 17 / arm64 qualification passes 31 fixture checks in
`Artifacts/native-evidence-6c35250735d3/qualification.json`. The report has
`unreal_qualified: false`; the source manifest has `unqualified-source-only`.
Hashes are integrity identifiers, not signatures or an immutable hosting channel.
The private license and actual engine/platform/package gates remain in force.
No source archive was uploaded or published. Full repository validation passes (213 reference +63 facade/native-driver tests).

## Completion — 2026-09-16

`python3 tools/validate_repo.py` passed: 276 tests total, provenance verification,
byte-identical repeated showcase exports, lab server smoke and reproducible asset
exports. All nine native tests also pass under UBSan. The exhaustive asset export
retains SHA-256 `128c7b20bb9c3fc427cabfb5070d7e4113b48585826a8ff8ddad8a0f935d8007`.
The showcase manifest now includes hashes for the new tooling; generator source,
seeds, world schemas and potential asset states are unchanged. No commit, push or
publication occurred. Next: the actual Unreal adapter/consumer and cooked proof,
with an installed 5.8.2 engine and an explicitly selected shipping platform.
