# ML-03b — Native JSON and numeric conformance

## Scope

Port the existing version-1 JSON/numeric contract and counter transport to C++17,
without changing Python/world semantics or claiming Unreal support. Depends on
ML-03a's typed counter transition.

## Acceptance

- Strict UTF-8/scalar Unicode, exact safe integers, duplicate-key rejection and
  shared depth/node/text/byte limits; canonical bytes match independent fixtures.
- SHA-256 digests and indexed stream words match the reviewed external vectors.
- Snapshot/command/candidate JSON transfers between native and Python processes;
  complete-state commit checks and retained-receipt semantics remain intact.
- Failure codes match the reference for invalid envelopes and unknown versions.
- Native tests precede implementation; full repository validation passes.

## Current evidence — 2026-09-16

Implemented in `Core/json.*`, `Core/numeric.*`, `Core/wire.*`. Seven wire tests
cover independent fixtures, block/padding hash boundaries up to one million
bytes, 80 deterministic valid JSON examples and 200 byte-mutated examples,
Unicode/limit rejection, fresh-process candidate exchange, multiple intervals,
budget partitions and all 256 retained receipts. Tests initially failed because
the files were absent; envelope tests caught an identity-validation ordering
mismatch, corrected before conformance passed. Normal and UBSan runs pass on
Apple clang 17 / arm64 macOS. No compiler was available in the inspected local
Linux container; no Linux qualification is claimed.

`Contracts/kernel-v1.md`, `Core/README.md` and the Unreal boundary document are
updated. No new assets or generator states are introduced. Full repository validation passes (213 reference +63 facade/native-driver tests); parent ML-03 still requires the actual Unreal adapter,
consumer and release qualification.

## Completion — 2026-09-16

`python3 tools/validate_repo.py` passed: 276 tests total, provenance verification,
byte-identical repeated showcase exports, lab server smoke and reproducible asset
exports. All nine native tests also pass under UBSan. The exhaustive asset export
retains SHA-256 `128c7b20bb9c3fc427cabfb5070d7e4113b48585826a8ff8ddad8a0f935d8007`.
The showcase manifest now includes hashes for the new tooling; generator source,
seeds, world schemas and potential asset states are unchanged. No commit, push or
publication occurred. Next: the actual Unreal adapter/consumer and cooked proof,
with an installed 5.8.2 engine and an explicitly selected shipping platform.
