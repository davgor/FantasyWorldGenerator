# PRINCIPAL-GRID-BOUND-PARITY — The grid ceiling was widened at the entry points and carried to no consumer

> **CLOSED 2026-09-21.** The code side was already closed and re-verified by running the tests: all four enforcement points agree on 1025, `Fixtures/unreal-frame-v1.json` carries a genuinely invalid `1026` case, and `tests/test_native_genesis.py` compares parsed integers instead of matching text (`python -m unittest tests.test_native_genesis` → 5 tests, OK). The one item left open was the version marker, which this card had already handed to `PRODUCT-CAPABILITY-RANGE-DIVERGENCE`; that card is closed by the same ruling and its surviving concern is filed as [PRODUCT-PARAMETER-PROVENANCE](../done/PRODUCT-PARAMETER-PROVENANCE.md).


## Requested behavior

One grid ceiling, enforced consistently, with the published capability registry and the native port
agreeing on it. Today they disagree, `Sim/tests` and `tests/` contain one test failing because the
ceiling moved and another passing because it did not, and `validate_repo --stage repo-tests` cannot
terminate.

Raised by the principal-lens red team against `233182e`. Filed rather than held because it describes
a commit that has already landed and that no session in flight will rewrite, and because it blocks
`--stage repo-tests` for every concurrent session.

**The decision this ticket exists to record is not made: is the maximum grid 257 or 1025?** That is
the user's call. Everything below holds either way — the defect is that the answer is currently
different at four places.

## Proposed mechanism

`21df9aa` ("checkpoint", 2026-09-19 22:32) widened the ceiling in `Sim/icarus_sim/terrain_world.py`:

- `bounds['size']` `(3,257)` → `(3,1025)`
- the guard `raw['size']>257` → `raw['size']>1025`, message `Interactive grid maximum is 257` →
  `Grid maximum is 1025`

It touched only that file and `tools/terrain_world.js`. `233182e` did not carry it further.

There are **four independent enforcement points** for the 257 ceiling. The widening reached the two
entry points and none of the consumers:

| Site | Ceiling | State |
|---|---|---|
| `Sim/icarus_sim/terrain_world.py:175,274`, `terrain_lab.py:138` | 1025 | widened |
| `Sim/icarus_sim/terrain_history.py:590` | 257 | deliberate — age advancement documents its own refusal |
| `Sim/icarus_sim/terrain_patch.py:89` | 257 | un-mirrored, and locked in by a **passing** test |
| `Core/genesis.hpp:8`, `Fixtures/unreal-frame-v1.json:21`, `tests/test_native_genesis.py` | 257 | un-mirrored — this is what hangs |

So this is not one constant missed. The value is advertised as the maximum at the entry point and
rejected as invalid by a green test at a consumer.

## Dependencies and unresolved decisions

- **RULED: 1025 is the grid ceiling.** User decision, relayed 2026-09-20. The Python reference path
  already served 3–1025; the native cap and the age-advancement refusal were the sides that had not
  caught up. `TIME-ADVANCE` is unblocked, and the performance session owns the Python widen and the
  `Core/` port as a single change.
- **The interactive lab limit stays 257 deliberately and is not part of this ticket.**
  `tools/terrain_lab.py` keeps its own 257 interactive ceiling, documented in
  `docs/terrain-math-lab.md`. Do not "fix" it to 1025 while mirroring the others — it is a UX budget,
  not a contract bound. Note this is a different file from `Sim/icarus_sim/terrain_lab.py`, which
  does carry the 1025 contract range; the two are easy to conflate by basename.
- **Still required under the ruling:** `Fixtures/unreal-frame-v1.json` must regain an upper-bound
  invalid case that is invalid under 1025. The existing `258` case now tests nothing and is the
  direct cause of the non-termination below; it needs to become `1026`.
- **A version still has to move.** The advertised range changed and it ships inside every world
  document, so this needs a version marker and a `version-bindings.json` entry, not prose.
- Anchors in this card are moving as the fix lands. Line numbers in *Acceptance and evidence* are
  pinned to `233182e` and are historical; treat the prose here as the current statement and re-read
  before editing.
- **Relationship to `board/backlog/PRODUCT-CAPABILITY-RANGE-DIVERGENCE.md`, agreed between the two
  red-team sessions so it does not have to be relitigated.** That card takes no position on the
  ruling and asks the general question this one is an instance of: `recipe.parameters` is a
  single-producer statement published into a two-producer world, and the grid ceiling is simply the
  instance that diverged loudly enough to be noticed. Whichever ruling lands, one card survives, and
  it is the one carrying the general defect rather than the instance:
  - **The ruling was 1025, so that branch applies: close `PRODUCT-CAPABILITY-RANGE-DIVERGENCE` as
    absorbed into this card.** Carry its general statement across rather than dropping it — the
    durable claim is that `recipe.parameters` is a single-producer statement published into a
    two-producer world, and the grid ceiling was only the instance that diverged loudly enough to be
    noticed. The version requirement above is the concrete form of it.
  - (The reciprocal branch, had the ruling been 257, was to close this card into that one.)

## Sources consulted

- `git show 21df9aa -- Sim/icarus_sim/terrain_world.py`
- `AGENTS.md` — "Increment a schema or recipe version when a consumer could otherwise misread changed
  semantics"; "Keep source dimensions in metres and make the metre-to-Unreal-centimetre conversion
  explicit at the adapter boundary"
- `docs/agent-workflow.md` — the shared fixture as the Python half of the native contract

## Files and assets in scope

- `Sim/icarus_sim/terrain_world.py` — `bounds`, `generate_request` guard, `registry`
- `Sim/icarus_sim/terrain_patch.py`, `Sim/tests/test_terrain_patch.py`
- `Sim/icarus_sim/terrain_lab.py`, `tools/terrain_lab.py`
- `Core/genesis.hpp`, `Core/genesis.cpp`
- `Fixtures/unreal-frame-v1.json`
- `tests/test_native_genesis.py`
- `Unreal/FantasyWorldGenerator/Source/FantasyWorldGenerator/Private/FantasyWorldGeneratorSubsystem.cpp`
  (inherits the bound by compiling `Core/`; no edit expected)

## Acceptance and evidence

Done when every site agrees on 1025, the fixture regains a real upper-bound case, a version has
moved, and `tools/validate_repo.py --stage repo-tests` terminates.

### Live status, re-measured 2026-09-20 by the native-parity lane — CODE SIDE CLOSED

Measured against the working tree at `7d94bf5` plus the wave-1 and wave-2 uncommitted changes, by
running the tests rather than reading the constants. **All four enforcement points now agree on
1025, the fixture carries a case that is genuinely invalid under it, and the parity test compares
values instead of matching text.**

- `Sim/icarus_sim/terrain_world.py` — `bounds`/guard/`registry` at `1025` (the original widening)
- `Sim/icarus_sim/terrain_history.py` — age advancement admits `1025`
- `Sim/icarus_sim/terrain_patch.py` — guard and message at `1025`
- `Core/genesis.hpp:8` — `max_grid=1025`
- `Fixtures/unreal-frame-v1.json:21` — the upper-bound case is now `{"size": 1026}`, genuinely
  invalid under 1025, so the `invalid_generate` sweep in
  `test_python_reference_rejects_every_invalid_generate_fixture` raises instead of building a
  258-grid world and hanging
- `tests/test_native_genesis.py:94-97` — the native half now parses `(min_grid|max_grid)=([0-9]+)`
  out of `Core/genesis.hpp` into integers and compares them against the Python `bounds`, so the
  text-match loophole that let a one-sided widening pass is gone. The source comment at :89 records
  why: `'max_grid=257'` is a substring of a hypothetical `max_grid=2570`.
- `Sim/tests/test_terrain_patch.py:61` — the rejection case moved to `1026`

Ran, not read: `python -m unittest -v tests.test_native_genesis` → **Ran 5 tests in 4.487s, OK**,
including both halves of the parity test and the invalid-fixture sweep that used to hang.

**What is still open is not the ceiling.** The version marker the acceptance line asks for has not
moved: `docs/conformance/version-bindings.json` carries no binding for the grid range, and every
generated world still publishes `recipe.parameters.size.max` without a version that says the range
changed. That is the general defect, and by the agreement recorded above it belongs to
`PRODUCT-CAPABILITY-RANGE-DIVERGENCE` rather than here. This card's own scope — one ceiling,
enforced consistently, with the tests terminating — is met.

### Historical: status when this card was last written — HALF LANDED, STILL BLOCKING

Kept because it names the two traps that caught the widening, both now closed. Re-checked at the
time against the working tree at `422f9c3` plus uncommitted changes, because the fix was landing
while this card was open. **The producer side is done; the test and fixture side is not, and
the non-termination survives.**

Landed (uncommitted, by the performance session):

- `Core/genesis.hpp` — `max_grid` is now `1025`
- `Sim/icarus_sim/terrain_patch.py` — guard and message now `1025`
- `Sim/icarus_sim/terrain_history.py` — age advancement now admits up to `1025`

Not landed, and each one still bites:

- `Fixtures/unreal-frame-v1.json` still carries the `258` case under `invalid_generate`. Since
  258 ≤ 1025 it is no longer invalid, so
  `test_python_reference_rejects_every_invalid_generate_fixture` still generates a 258-grid world
  instead of raising. **`--stage repo-tests` still cannot terminate.** Committing the producer side
  alone does not clear this.
- `tests/test_native_genesis.py` still expects `257` in both assertions. Re-run just now:
  `AssertionError: 1025 != 257` at the `registry` assertion, which fails before the
  `Core/genesis.hpp` text assertion is reached.
- That second assertion has now **flipped from passing to failing** — it asserts `max_grid=257`
  against a header that now says `1025`. At `233182e` it was the green test holding the old ceiling
  in place; it is now simply stale. Both halves of that test need moving together, and the
  `registry` half should become a value comparison against the Python reference rather than a text
  match, so a one-sided change cannot pass again.

**A second test has already broken the same way, and it was green an hour ago.**
`Sim/tests/test_terrain_patch.py` — `test_request_rejects_invalid_world_before_sampling` — asserted
that `1025` is rejected. With the guard now admitting 1025 it no longer is. Measured just now, not
predicted: the test **fails** with `AssertionError: ValueError not raised` **after 48.06 seconds**,
because `patch_request` generates a full 1025-grid world before the missing exception is noticed.
The whole file ran in 0.108 s for six tests at `233182e`.

So it does not hang — I expected it to and it does not — but a 0.1 s file now spends 48 s building a
world in order to fail. That case needs to move to a value that is invalid under 1025, for the same
reason the fixture's `258` does.

**The pattern worth naming, because it is the actual lesson of this ticket:** every one of these
breakages is a test that encoded the *old* ceiling as a literal. Widening the guard silently
converts each one from a guard into either a slow failure or, where the value is now merely large
instead of invalid, a very expensive no-op. So they should be found in one sweep rather than
discovered one suite run at a time.

### Sweep of remaining ceiling literals — and a trap in it

**Do not mechanically rewrite every `257`.** Two of the hits below are a *different* 257: the tile
raster limit, which is derived from `span / spacing` and has nothing to do with the world grid. They
happen to share the number. Rewriting them to 1025 would silently widen a published tile contract
that nobody ruled on.

Must move (world grid, verified by reading the surrounding guard):

- `Fixtures/unreal-frame-v1.json` — the `258` invalid case, to `1026`
- `tests/test_native_genesis.py` — both `257` assertions; make the `registry` one a value comparison
- `Sim/tests/test_terrain_patch.py` — the `size` `1025` rejection case

Must **not** move (tile raster, not world grid — confirmed by reading both guards):

- `Contracts/schemas/height-tile.schema.json` — `size` maximum `257` and the `heights_m` array
  bounds. This is a published schema for a resolved terrain tile.
- `Sim/icarus_sim/terrain_patch.py` — the `math.ceil` vertex guard, which rejects more than 256
  steps across a patch whose span is 4–512 m at 0.1–8 m spacing. Independent of the world grid.

Not assessed here, flagged so they are not assumed safe: `Sim/tests/test_terrain_detail.py` and
`Sim/tests/test_terrain_scale.py` each carry a `257` among positional arguments and a size list. Both
read as sample values rather than bounds, but I did not run them, so treat that as unverified.
`Fixtures/coordinates-v1.json` contains `1025` as an expected coordinate component and is unrelated.

**Historical evidence gathered 2026-09-20 against `233182e` (commands run, not read).** Line numbers
below are pinned to that commit and several have since moved:

1. `python -m unittest tests.test_native_genesis.GenerateRequestParityTests.test_python_reference_accepts_the_shared_valid_grid_bounds`
   → **FAIL**, `AssertionError: 1025 != 257` at `tests/test_native_genesis.py:84`.

2. `tests/test_native_genesis.py:87` asserts `'max_grid=257' in Core/genesis.hpp` under the message
   *"native grid maximum must match the Python reference"*. It passes. The parity test pins `Core/`
   to a value the Python reference abandoned — a **text match standing in for a value comparison**,
   which is why a one-sided widening survived review.

3. `generate_request({'recipe_version':3,'seed':1,'overrides':{'size':258}})` — the body
   size-258 body, whose `overrides` entry sits at `Fixtures/unreal-frame-v1.json:21` and which is
   listed under `invalid_generate` at `Fixtures/unreal-frame-v1.json:17` — raises nothing and
   proceeds to build a 258-grid world. Killed at a 60 s cap (`timeout` exit 124). Cost is roughly size² by the code's own
   comment at `terrain_world.py:271-272`, so
   `test_python_reference_rejects_every_invalid_generate_fixture` **hangs rather than fails**. Its
   docstring notes it is the half that runs on machines without a compiler, so this is not confined
   to native-capable machines.

4. `python -m unittest tests.test_terrain_patch -v` → **6 tests, OK**, including
   `test_request_rejects_invalid_world_before_sampling`, whose cases include
   `{'config':{'shape':'globe','size':1025},'patch':{}}`. **A green test asserts that 1025 — the
   value the entry point now advertises as the maximum — is invalid.**

   Point 4 is more dangerous than point 1. A failing test gets fixed. A passing test that encodes
   the abandoned ceiling silently prevents the widening from ever being carried to that consumer,
   and will be cited as proof the consumer is correct.

5. The registry is not only an entry-point constant — it is **published inside every generated
   world**. `Sim/icarus_sim/terrain_world.py:279` writes `'parameters':registry(version)` into the
   recipe block, with a provenance map beside it marking each parameter `override` or `default`.
   Verified by generating a world and reading it back: `recipe.parameters.size` is
   `{'default': 129, 'min': 3, 'max': 1025}`. A consumer therefore does not have to call a
   capability endpoint to be misled — it reads `recipe.parameters.size.max` out of the document it
   was handed.

   Meanwhile `Core/genesis.cpp:92` throws `STATE_CAPACITY` above `max_grid=257`, and
   `Unreal/FantasyWorldGenerator/Source/FantasyWorldGenerator/Private/FantasyWorldGeneratorSubsystem.cpp:237`
   gates on `min_grid`. **Every generated world advertises a grid range that every native consumer
   rejects, with no version move. A UE client that trusts the document it was handed builds a
   request the subsystem refuses.**

   Note that `terrain_world.py:274` enforces 1025 honestly on the Python side, so the reference
   genuinely serves what it advertises; the divergence is entirely at the boundary. Both ceilings
   are 2ⁿ+1 — 2¹⁰+1 against 2⁸+1 — so native is two doublings short: four times fewer cells per
   axis, sixteen times fewer overall at the top of the advertised range.

   (Evidence in this point contributed by the product red-team session, re-verified here by
   generating a world rather than reading the constant.)

**Consequence for the whole tree:** `python tools/validate_repo.py --stage repo-tests` cannot
complete on `233182e`. AGENTS.md requires `validate_repo` before closeout, so "nobody ran
`validate_repo` tonight" and "this defect exists" are one event, not two — the defect is what a run
would have caught, and the absence of a run is why it shipped. (Framing credited to the code red team
session.)

## Documentation impact

`docs/terrain-world-layers.md` and any record claiming `terrain_world.py` state the grid range;
whichever ceiling is chosen, the stated range and the registry must agree. If 1025 stands, the
`registry`/`bounds` change is a consumer-visible contract change and needs a version marker and a
`version-bindings.json` entry, not only prose.

## Adversarial review and limitations

This card is itself a red-team finding, so the adversarial pass is on the finding rather than on an
implementation.

Attacked and held: all five evidence points are executed commands, not readings. The line anchors
were read at `233182e` with a clean working tree.

Attacked and corrected: the same review initially claimed `docs_check.py`'s `docs/*.md` glob was
single-level and that documents could evade the gate by sitting one directory deeper. **That is
false and is withdrawn** — `docs_check.py:73-75` uses `fnmatch.fnmatchcase`, where `*` crosses `/`.
It reached two other sessions and became a coordinator ruling before being refuted empirically. The
rule adopted in response, and applied to every point above: run the checker, do not reason about it.
Two sessions agreeing is not two verifications when both reasoned and neither ran.

Limitations: the correct ceiling is not determined here and is deliberately left to the user. No
engine evidence was gathered — the Unreal consequence in evidence point 5 is derived from
`FantasyWorldGeneratorSubsystem.cpp:237` compiling `Core/`'s constants, not from a packaged build,
and per AGENTS.md a passing Python test does not prove an importer works. The perf and
time-advancement sessions were rewriting other files while this was verified; anchors listed here
were not in their scope but should be re-checked before editing.

## Handoff

Blocking. Not fixed here — the principal red-team session is review-only by agreement with the agent
coordinator and did not edit `Sim/`, `Core/`, `Contracts/` or `tools/`.

Next concrete action: the user rules 257 or 1025; whoever takes it moves all four enforcement points
in one change, replaces the fixture's `258` case with one invalid under the chosen ceiling, converts
`test_native_genesis.py:87` from a text match to a value comparison against the Python reference so
this cannot recur silently, and re-runs `tools/validate_repo.py --stage repo-tests` to confirm it
terminates.
