# UNREAL-IMPORT-CONFORMANCE — Native conformance records, written against the redone port

## Requested behavior

Every `Core/` module stem gains a conformance record, written when the native port is
redone for the Unreal import rather than against the current tree. Until then all 46
stems sit in the `uncovered` allowlist of `docs/conformance/coverage.json`, so the
parking is a declared debt with a ticket rather than a silent omission.

## Proposed mechanism

The Python conformance records are the acceptance spec. A native record is written only
once the module it describes has a test that reaches it, and it states its evidence tier
rather than inheriting the Python record's.

## Dependencies and unresolved decisions

Blocked on the port being redone. The owner has said the native side will be rebuilt for
the Unreal import and validated against `docs/conformance/`, so this ticket starts when
that work does.

## Sources consulted

`Core/README.md`, `Core/tests/world_driver.cpp`, `tests/test_native_world.py`,
`docs/decisions/018-unrealworldgen-dev-consumer.md`,
`docs/decisions/019-runtime-surface-not-landscape.md`, `board/backlog/ML-03d.md`,
`board/in-progress/ML-03.md`.

## Files and assets in scope

`docs/conformance/` native records; the `uncovered` entries naming `Core/` stems.

## Acceptance and evidence

Each `Core/` stem is either claimed by a record or removed from the tree. No stem
remains in `uncovered`. Every record above tier `DECLARED` cites a test that exists and
that reaches the module.

## Documentation impact

This ticket exists to produce documentation; the impact is the native half of
`docs/conformance/`.

## Adversarial review and limitations

The trap this ticket exists to avoid: `Core/castleplanner.hpp` and its siblings read as
finished, confident, carefully reasoned contracts. Transcribing that prose would produce
records asserting parity that nothing has ever checked. As of 2026-09-19, roughly ten
thousand lines across `cityplanner`, `hamletplanner`, `castleplanner`, `castlegeometry`,
`cityfortifications`, `citygeometry`, `cityshapes`, `settlementpresets`, `sceneframe` and
`scenebuildings` compile under `-Werror` and link into the parity binary, and no test
reaches any of them: they are callable only through `plan_settlement_buildings` in
`scene.cpp`, itself callable only through the `scenebuildings` operation at
`Core/tests/world_driver.cpp:452`, which no test invokes. `cityplan` is the exception,
exercised by the tested `cityplans` operation.

Writing a record must never promote an evidence tier. A tier moves when a test lands.

## Handoff

Parked. `docs/conformance/README.md` carries the tier definitions and the rule that a
record claims a module in its `modules:` front matter.
