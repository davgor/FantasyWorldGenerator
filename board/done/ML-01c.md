# ML-01c — Numeric, PRNG, ordering and serialization contract

## Requested behavior

Define reproducible numeric and random-stream semantics for the portable kernel, with independently authored vectors usable by Python and native implementations.

## Dependencies and scope

Depends on ML-01a; coordinate assumptions must agree with ML-01b. Read the current seed/replay implementation and canonical world contract before selecting kernel semantics. Do not replace existing generation randomness or promise cross-language world parity without evidence.

## Acceptance

- Record seed domain, stream derivation, integer widths/overflow, PRNG algorithm, float conversion and stream names with explicit versions.
- Demonstrate independent named streams and deterministic ordering under reordered inputs with fixed external expected vectors.
- Define finite-value handling, numeric tolerances, time units/rounding and portable limits rather than inheriting host defaults.
- Define canonical serialization and hashing, including key/list order, Unicode, negative zero and invalid number rejection where relevant.
- Keep the existing generator's compatibility boundary distinct from the future kernel's; document intentional differences and any required contract version changes.
- Behavioral tests precede implementation; canonical docs and full repository validation pass.

## Handoff

ML-02 may use these semantics only after the vectors and compatibility decision are recorded. A native implementation must run the same vectors later.

## Completion evidence — 2026-09-16

Implemented `kernel_numeric.py` with versioned indexed SHA-256 streams, safe-integer arithmetic, explicit float conversion, canonical JSON/hashing and strict bounded decoding. `Fixtures/kernel-numeric-v1.json` has independently authored byte frames and canonical strings, with expected digests checked using OpenSSL. Four behavioral tests cover fixed vectors, independent stream order, Unicode/numeric/encoding boundaries and unsupported versions. Tests failed for the missing implementation before it was added.

Canonical contract: `Contracts/kernel-v1.md`. Existing recipe-3 randomness and generator schemas are unchanged. Full repository validation passes with 213 reference and 55 facade/native-driver tests. Native numeric stream conformance remains part of ML-03; no engine qualification is implied.
