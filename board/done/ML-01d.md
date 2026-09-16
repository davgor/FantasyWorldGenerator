# ML-01d — Persistent identities, negotiation and failures

## Requested behavior

Finish ML-01's persistent-kernel boundary with stable entity/action identities, schema negotiation and machine-readable failure semantics before implementing state transitions.

## Dependencies and scope

Depends on ML-01a/b/c. Read ML-02 and the embedded package contract in `PLAN.md`. Terrain identity alone does not define entity identity or accepted-event receipts. Storage, network transport and game-owned assets remain outside this package.

## Acceptance

- Define identity scope, lifetime and collision/reuse handling independently of display names, array positions and presentation detail.
- Define supported schema negotiation, unknown version/ID behavior and explicit migration/rejection rules.
- Specify failure categories for malformed input, stale revision, conflicting duplicate payload and exceeded work budgets without silently accepting unsupported operations.
- Independently authored fixtures cover valid envelopes and invalid input, with behavioral tests added before validation behavior changes.
- Review contract coverage against ML-02 retry, checkpoint/resume, no-time-advance-over-pending-work and replay requirements.
- Record remaining limitations and evidence; complete ML-01 only after all slices and full repository validation pass.

## Handoff

Then activate ML-02's single bounded transition. Do not claim durable persistence, native conformance or engine integration from contract fixtures.

## Completion evidence — 2026-09-16

Implemented typed world/actor/event/target identities, explicit schema/rule/numeric versions, strict event and command envelopes, and eleven stable failure codes. `Fixtures/kernel-contract-v1.json` supplies independent valid and invalid cases. Two behavioral tests preceded the implementation; subsequent ML-02 tests exercise the contract through actual transitions.

`Contracts/kernel-v1.md` records scope, identity retention and failure policy. `Contracts/schemas/counter-kernel.schema.json` defines structural envelopes; a Draft 2020-12 validator accepted the schema and six reviewed state/command/candidate examples. Semantic/lexical validation is explicitly stricter than JSON Schema. Full repository validation passes (213 reference +55 facade/native-driver tests). Durable storage, authentication and migration remain outside this proof.
