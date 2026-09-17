# Headless native counter core

`counter.hpp/cpp` implements the bounded ML-02 transition in standard C++17.
`json.hpp/cpp`, `numeric.hpp/cpp` and `wire.hpp/cpp` add strict canonical JSON,
SHA-256 indexed streams, snapshot/command loading and candidate transport.
`genesis.hpp/cpp` adds the Unreal centimetre frame and generate-request
validation only; it does not generate a world.
There are no Unreal, Python-runtime, third-party JSON/crypto library or game-asset
dependencies. Original project source follows the root private distribution policy.
The public semantic boundary is [`Contracts/kernel-v1.md`](../Contracts/kernel-v1.md).
Native structs are not a stable binary ABI or a persistence format.

## API boundary

- `json::parse` / `json::canonical` implement the bounded kernel JSON domain:
  exact safe integers, scalar Unicode, duplicate-key rejection, canonical ASCII
  escapes, scalar-ordered keys, depth/node/string/byte limits. Booleans are never
  integer values. `json::Value` is an owning tree with distinct variant types.
- `random_word` / `unit_float` implement numeric version 1. `digest` hashes canonical
  JSON. The internal-use `sha256` byte helper also limits inputs to 1 MiB.
- `parse_snapshot` / `parse_command` decode strict versioned envelopes.
  `evaluate` returns immutable candidate values; `commit` validates them against
  the complete current state. `candidate_json` / `parse_candidate` preserve the
  Python transport envelope, including normalized commands and retained effects.
- `snapshot_json` emits validated canonical snapshot bytes. `failure_json` emits
  the same versioned failure envelope and stable codes as the Python contract;
  diagnostic message wording is not a cross-language promise.
- `unreal_point` converts a source offset in metres to whole Unreal centimetres
  `[X, Y, Z] = [east*100, north*100, up*100]`, the mapping in
  [`docs/unreal-integration.md`](../docs/unreal-integration.md). Unreal is
  left-handed and Z-up, so source up is Z and never Y. Kernel JSON excludes
  floats, so each offset is a JSON integer or an exact decimal string
  (`"-0.01"`); an offset finer than one centimetre is rejected instead of
  rounded, and no float arithmetic enters the conversion. Winding reversal and
  metre-to-centimetre scaling of meshes stay with a future adapter.
- `generate_request` validates a request only: recipe version exactly 3, a seed
  in `0..2^32-1`, and an optional `overrides` object limited to `size` (1..257)
  and `shape` (`globe`, because recipe 3 is a tectonic globe). Unknown override
  keys are rejected. `generate_request_json` returns
  `{"ok": true, "recipe_version": 3, "seed": <seed>}`; accepting a request is not
  generating, sampling, exporting or importing anything.

The lower-level `*_value` conversion helpers accept a `json::Value`. Untrusted
wire input must go through `json::parse` (or the `parse_*` wrappers) first, so the
shared byte/node/depth limits apply before semantic conversion.

**Native world generation is still missing.** `genesis` is a request boundary, so
there is no native tectonic globe, elevation, climate, on-demand surface sample,
tile/patch export, catalogue state or Landscape/asset path, and nothing here
replaces the Python producer. The native seed/size domain is also not yet the full
producer contract: the Python recipe additionally requires `size` of at least 3
and validates the remaining recipe fields, which `generate_request` does not see.
A caller must still treat a successful validation as accepted input, not evidence
that a world can be built natively.

The counter still has at most 64 command events/effects and 256 retained receipts.
No function writes state, authenticates actors, delivers external effects or
performs an atomic transaction. A host must durably compare/store the resulting
snapshot and effect IDs before publishing completion. Exceptions are standard
C++ `fantasy_world_generator::Error`; a future Unreal module must explicitly configure or adapt
exception handling and validate that boundary. The optional float conversion
requires an IEEE-754 binary64 `double`, checked at compile time.

The SHA-256 implementation follows the functions, constants and recurrence in
[NIST FIPS 180-4](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf), sections
4.1.2, 4.2.2, 5.3.3 and 6.2. It exists for deterministic contract hashes/streams;
this project does not claim cryptographic-module certification or authentication.

## Conformance

From the repository root:

```sh
PYTHONPATH=Sim python3 -m unittest discover -s tests -p 'test_native_*.py' -v
```

The typed harness still checks shared independently authored counter fixtures.
The wire driver additionally exchanges candidate/snapshot JSON with Python in
fresh native processes, checks full receipt capacity and budget partitions,
compares canonical Unicode/numeric encodings, and rejects malformed/oversized
JSON. Independent SHA/stream fixtures, hash padding boundaries, a deterministic
valid/malformed JSON corpus, schema failures and unknown versions are covered.
The driver is a test consumer, not a production persistent service or CLI.

The genesis driver checks the hand-authored `Fixtures/unreal-frame-v1.json`
oracle in a fresh native process without Python: each cardinal and elevation
offset reaches the expected Unreal axis in centimetres (including source up as Z),
a valid recipe-3 request is accepted, and the retired recipe, out-of-range seeds,
an oversized grid and a non-globe shape are refused with the failure envelope.

```sh
python3 -m unittest tests.test_native_genesis -v
```

`tests/native_cxx.py` selects `clang++`, `g++` or MSVC `cl.exe` (through
`vcvars64.bat`) for the unit tests, so the fixture oracle is the shared authority
rather than one toolchain. `tools/qualify_native.py` still requires `clang++` or
`g++` with C++17 support; an MSVC-only installation is not handled by that script.
Unit tests report a skip when no driver exists;
release qualification must treat that as missing evidence. The isolated consumer
script fails instead of skipping. On macOS the drivers explicitly select SDK
libc++ headers where available because this host's Command Line Tools default
include directory lacks them. `FANTASY_WORLD_GENERATOR_CXXFLAGS` adds compiler flags, such as
`-fsanitize=undefined -fno-omit-frame-pointer`. Subprocess timeouts are bounded.

Local evidence is Apple clang 17.0.0 / arm64 macOS, C++17, strict warnings as errors,
including UBSan. AddressSanitizer remains unavailable on this host: an instrumented
empty `main` also timed out in ML-03a, so that attempt is not counted as a pass.
Genesis evidence is separate: MSVC v14.44.35207 x64 on Windows with
`/std:c++17 /EHsc /W3 /WX`, no sanitizer, and no clang/g++ build of `genesis` yet.
`tools/qualify_native.py` was therefore never executed by its own supported
compilers on that host, so the bundled genesis sources have no isolated
qualification report from this machine.

## Reproducible source proof bundle

```sh
python3 tools/package_native.py --output-dir Artifacts/native
```

This creates `fantasy-world-generator-native-source-<full SHA-256>.zip` with fixed ZIP metadata,
source/fixture hashes, versioned contract metadata, private license and the test
consumer. Identical source bytes yield identical archive bytes. A conflicting
existing content-addressed filename is rejected. The archive is explicitly
`unqualified-source-only`; a content hash is an integrity identifier, not a
signature, public release or immutable hosting channel.

Extract into an empty directory outside this checkout, then run its included
script with Python 3.9+ and a C++17-capable `clang++` or `g++`:

```sh
python3 tools/qualify_native.py --output-dir build/qualification
```

The script verifies every allowed source hash before and after compiling/running,
executes shared fixtures in two standalone native binaries (the counter wire
driver and the genesis driver), and writes `qualification.json` with the tested
manifest digest, compiler/flags, platform, architecture, checks and both binary
digests. Because `Fixtures/unreal-frame-v1.json` declares no stable codes for its
invalid request bodies, those are qualified as refusals with the failure envelope
rather than by code. It needs no Python simulation package.
A failed attempt replaces any previous success report with a failure report;
source tampering is tested. This is a local toolchain result, not a claim of
identical binaries across compilers or universal platform support.

ML-03b covers wire/numeric conformance; ML-03c covers this source proof bundle and
isolated headless consumer. ML-03 remains open for the generic `.uplugin`, an
installed Unreal 5.8.2 consumer, editor/cooked execution, shipping-platform and
engine-CI qualification, and an immutable runtime artifact channel. The native
world generate API is likewise only started: request validation and the Unreal
centimetre frame exist, and generation, surface sampling and Landscape do not. The
Python producer's qualified native/Unreal capability requests remain unsupported.
