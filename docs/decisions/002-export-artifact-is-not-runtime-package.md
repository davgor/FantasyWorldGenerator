# Decision 002 — Label current publication export-only

## Decision

The current CI artifact is named `fantasy-world-generator-reference` and contains Python distributions, contracts, provenance, and the exhaustive semantic asset list. It is not the versioned Unreal runtime package required by ML-03.

## Reason

The repository has no portable native kernel, `.uplugin`, minimal Unreal consumer, cooked test, or immutable package channel. Calling the existing artifact runtime-ready would violate the package gates in `PLAN.md`.

## Consequences

Reference artifacts can support inspection and offline genesis experiments. Runtime publication begins only after ML-03 selects and validates its engine/toolchain/channel contract. Game-owned Unreal assets and bindings remain outside this artifact.

