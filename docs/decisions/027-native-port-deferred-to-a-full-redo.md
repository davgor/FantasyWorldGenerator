# 027 — The native port is deferred to a full redo, and no Python change owes it anything

On 2026-09-21 the owner ruled on the native `Core/` port. **It does not happen until the end of
the project, and when it happens it is a full rewrite against all the functionality that exists
by then — not a continuation of the C++ in the tree today.**

This record exists because the opposite assumption had been written into the repository, and it
was quietly taxing every Python change and inflating the board.

## Decision

1. **No Python change owes a native port.** A seed-changing, contract-changing or
   behavior-changing edit to `Sim/` lands on its own. It does not wait for, and is not bundled
   with, a `Core/` port.
2. **The native side is not a parity target.** `Core/` as it stands is a prototype whose value is
   that it proved the kernel shape. It will be rewritten. Its current divergence from Python is
   not a defect, is not tracked, and is not a hold on anything.
3. **No new C++ is written speculatively.** Do not add mirrors, stubs or records for native
   modules ahead of the port. Writing C++ months before anything compiles it produces code nobody
   has run and tests nobody has seen fail.
4. **Python is the reference and the product.** Every capability the board calls complete is
   complete in Python. That is the only layer any current claim refers to.

## What this supersedes

[023 World compatibility policy](023-world-compatibility-policy.md) says of a seed-breaking
change: *"It still needs its native `Core/` port in the same change."* **That clause is
superseded.** The rest of 023 stands unchanged — worlds are disposable, no migration is owed, and
the policy holds until phase 2 of the product roadmap. Only the port obligation is lifted.

`AGENTS.md`'s rule that a passing Python test does not prove an Unreal importer or a packaged game
works is **not** superseded and is, if anything, the reason for this record: the way to avoid
claiming engine integration without engine evidence is to stop writing engine code with no engine
in the loop, not to attach a C++ tax to Python work.

## Why

Three things were true at once and together they were expensive.

**The clause deferred real work.** Cards like `PERF-CITY-COUNT-TRACKS-RASTER` carry measured,
agreed Python changes that sat unowned because the card correctly observed they were seed-changing
and therefore owed a `Core/` port under 023. The port was never going to be done by the session
that found the defect, so the defect kept not being fixed.

**It produced code with no consumer.** Roughly ten thousand lines across `cityplanner`,
`hamletplanner`, `castleplanner`, `castlegeometry`, `cityfortifications`, `citygeometry`,
`cityshapes`, `settlementpresets`, `sceneframe` and `scenebuildings` compile under `-Werror` and
link into the parity binary, and no test reaches any of them — they are callable only through
`plan_settlement_buildings` at `Core/scene.cpp:462`, itself callable only through the `scenebuildings`
operation at `Core/tests/world_driver.cpp:463`, which no test invokes. That was established by
`UNREAL-IMPORT-CONFORMANCE` before this ruling and is the clearest evidence for it.

**It inflated the board.** Nine of fifty-seven backlog cards were native-only or had nothing
outstanding but a native mirror, and two of them said so in their own first paragraph.

## Consequences

`board/retired/` is created by this ruling and holds the seven cards it retires: `ML-03` and its
slices `ML-03d`, `ML-03e`, `ML-03f`, plus `HERITAGE-NATIVE-MIRRORS`, `UNREAL-IMPORT-CONFORMANCE`
and `PRODUCT-RUNTIME-PARITY-LEDGER`. Retired means not done and not to be worked as written; the
folder's README states that a card in it is never a blocker. Three further cards whose Python half
had landed and whose only outstanding item was a native build closed to `board/done/`:
`PRINCIPAL-GRID-BOUND-PARITY`, `PRODUCT-CAPABILITY-RANGE-DIVERGENCE` and `VILLAIN-SCHOOL-DRIFT`.

`SUPER-VILLAINS` loses slice S9, which was the native port and its only unlanded slice.

The 46 `Core/` stems stay in the `uncovered` allowlist of `docs/conformance/coverage.json`. Under
`UNREAL-IMPORT-CONFORMANCE` that was a declared debt with a ticket; it is now a deliberate
permanent exclusion until the port is scoped again, and `docs/conformance/README.md` says so.

The three `VERSION-MIRROR` clauses in `docs/conformance/version-bindings.json` were removed on
2026-09-21 as follow-through on this ruling. They bound `city_planner.py`, `hamlet_planner.py` and
`castle_planner.py`'s `VERSION` to the `planner_version` constexpr in `Core/cityplanner.hpp`,
`Core/hamletplanner.hpp` and `Core/castleplanner.hpp`, and `tools/docs_check.py:606` failed HARD
when the two disagreed. That gate tracked native divergence, treated it as a defect and held Python
changes on it — the three things point 2 says it must not be. It had already had its intended
effect: a session that moved the planner versions in Python mirrored roughly its whole change into
four `Core/*.cpp` files it could not compile, because reverting the headers would have failed the
gate. Each binding keeps its `code` and `claims`, so the Python-constant-to-document binding is
unchanged; only the C++ parity clause is gone. No remaining binding uses the `cxx-constexpr`
resolver.

ML-13 remains in `PLAN.md` as the engine-integration milestone. It is the place the port gets
scoped, from scratch, against whatever the Python reference is at that time.

## What would reverse this

A decision to ship on Unreal earlier than the end, or a player-facing consumer that cannot be
served by Python. Neither exists. If either arrives, this record is superseded rather than
quietly ignored, and the retired cards are re-scoped rather than un-retired — they describe a tree
that will have moved.
