# Decision 001 — Preserve the reference package behind a new facade

## Decision

Keep the extracted Python oracle at `Sim/icarus_sim` with its legacy prompt-seed namespace and public generation behavior. Put repository-level CLI, versioned export envelopes, and asset-list compilation in the separate `fantasy_world_generator` package.

## Reason

ML-00 requires a reviewable baseline before path cleanup, and existing seeds/imports are compatibility contracts. A facade gives the repository its settled name without pretending a renamed Python package is the future Unreal runtime.

## Consequences

The initial wheel contains both packages. `icarus_sim` is the reference API; `fantasy_world_generator` is the convenience/export API. A later migration may deprecate the legacy import only with versioned compatibility evidence. The original `icarus-terrain-prompt-v1` hash domain remains unchanged.

