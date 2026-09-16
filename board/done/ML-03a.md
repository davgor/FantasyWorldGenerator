# ML-03a — Headless typed C++ counter proof

## Scope and completion — 2026-09-16

Port ML-02's bounded transition into engine-independent C++17 and execute shared independent fixtures, before adding wire decoding or an Unreal adapter. Completed in `Core/counter.hpp` and `Core/counter.cpp`; `Core/README.md` records the precise boundary and reproduction command.

The Python test driver compiles fixture values into a native harness. Native checkpoint/completion JSON must match the shared fixtures byte for byte. The harness also tests duplicate/reordered deliveries, interval resume, stale revision/authority, ID conflict, invalid versions, overflow, capacity and candidate tampering. Tests were added first and failed for the absent core. Adversarial version tests then caught and corrected a negative-version error-code mismatch.

Local qualification: Apple clang 17.0.0, arm64 macOS, C++17, strict warnings as errors; ordinary and undefined-behavior-sanitized executions pass. AddressSanitizer is not qualified: an empty instrumented program also timed out on this host. Full repository validation passes (213 reference +55 facade/native-driver tests).

## Remaining parent scope

ML-03 remains open. This typed proof has no native general JSON decoder, candidate transport or SHA-256/random-stream implementation; it does not establish a stable C++ ABI. No `.uplugin`, installed Unreal 5.8.2 consumer, cooked execution, shipping-platform/toolchain qualification or immutable source-inclusive release exists. The Python producer continues to reject native/Unreal runtime capability requests. No engine or game assets were changed.
