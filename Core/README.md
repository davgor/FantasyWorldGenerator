# Headless native counter core

`counter.hpp/cpp` implements the bounded ML-02 transition in standard C++17.
`json.hpp/cpp`, `numeric.hpp/cpp` and `wire.hpp/cpp` add strict canonical JSON,
SHA-256 indexed streams, snapshot/command loading and candidate transport.
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

The lower-level `*_value` conversion helpers accept a `json::Value`. Untrusted
wire input must go through `json::parse` (or the `parse_*` wrappers) first, so the
shared byte/node/depth limits apply before semantic conversion.

The counter still has at most 64 command events/effects and 256 retained receipts.
No function writes state, authenticates actors, delivers external effects or
performs an atomic transaction. A host must durably compare/store the resulting
snapshot and effect IDs before publishing completion. Exceptions are standard
C++ `mathlab::Error`; a future Unreal module must explicitly configure or adapt
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

The build drivers require `clang++` or `g++` with C++17 support; an MSVC-only
installation is not handled by these scripts. Unit tests report a skip when neither driver exists;
release qualification must treat that as missing evidence. The isolated consumer
script fails instead of skipping. On macOS the drivers explicitly select SDK
libc++ headers where available because this host's Command Line Tools default
include directory lacks them. `MATHLAB_CXXFLAGS` adds compiler flags, such as
`-fsanitize=undefined -fno-omit-frame-pointer`. Subprocess timeouts are bounded.

Local evidence is Apple clang 17.0.0 / arm64 macOS, C++17, strict warnings as errors,
including UBSan. AddressSanitizer remains unavailable on this host: an instrumented
empty `main` also timed out in ML-03a, so that attempt is not counted as a pass.

## Reproducible source proof bundle

```sh
python3 tools/package_native.py --output-dir Artifacts/native
```

This creates `mathlab-native-source-<full SHA-256>.zip` with fixed ZIP metadata,
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
executes shared fixtures in the standalone native binary, and writes
`qualification.json` with the tested manifest digest, compiler/flags, platform,
architecture, checks and binary digest. It needs no Python simulation package.
A failed attempt replaces any previous success report with a failure report;
source tampering is tested. This is a local toolchain result, not a claim of
identical binaries across compilers or universal platform support.

ML-03b covers wire/numeric conformance; ML-03c covers this source proof bundle and
isolated headless consumer. ML-03 remains open for the generic `.uplugin`, an
installed Unreal 5.8.2 consumer, editor/cooked execution, shipping-platform and
engine-CI qualification, and an immutable runtime artifact channel. The Python
producer's qualified native/Unreal capability requests remain unsupported.
