# CONTENT-NO-ANTAGONIST — two wired systems emit nothing, and neither says so

> **RE-MEASURED 2026-09-21 — the mechanism holds, the title does not.** `heroes.dreads` and
> `magic.colleges` are both still empty and still report no shortfall, so this card's defect is intact.
> But the world is no longer without antagonists: `villains` now carries 10 people, 39 tiers and 10 works,
> because SUPER-VILLAINS S0–S8 landed after this card was written. Scope it as *two wired systems emit
> nothing and neither says so*, not as *the world has no antagonist*. [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

Owner: none. State: **step 1 delivered for both blocks, 2026-09-21. `heroes.diagnostics` and
`magic.diagnostics` both publish a row per role and per institution, placed or not, with a reason.
This card stays in `backlog/` for step 2 — deciding whether the zeros are correct — and for its
third acceptance bullet, the conformance records, which is unmet for both halves.**

## Delivered 2026-09-21 — the `heroes` half, step 1

`heroes.diagnostics` now carries one row per role declared in `policies/wells.json`'s
`precipitation` table, sorted by role, whether it placed anybody or not — the shape
`key_locations` publishes, in the block that owns the roles. Row:
`{role, placed, candidates, sources, source_kind, reason}`.

**Failing test first.** `Sim/tests/test_hero_diagnostics.py`, 7 tests. Before the change every
one of them ended `KeyError: 'diagnostics'`. All seven pass now in 0.09 s, with no world
generated.

**The two zeros are now different facts, which is the whole point.** `candidates: 0` means no
candidate was ever built — the world holds none of the records that well reads — and `reason`
names what was missing. `candidates` above zero with `placed: 0` means every candidate was built,
rolled and lost, and `reason` gives the best chance offered.
`test_zero_candidates_and_zero_precipitated_do_not_read_alike` pins that the two produce
different text, by driving the Dread's chance to zero on a world that *does* have a beast ruin.

### Re-measured on the current tree, and the card's figures were size 17

Run against `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16), which the card
predates:

| role | placed | candidates | sources | reason |
|---|---|---|---|---|
| `dread` | 0 | 0 | 0 | **no ruins a beast destroyed in this world, so nothing rolled** |
| `college_magister` | 0 | 0 | 0 | no living magic colleges in this world, so nothing rolled |
| `magister` | 0 | 0 | 0 | no cities that destroyed themselves in a magical experiment in this world, so nothing rolled |
| `cult` | 0 | 0 | 0 | no cults in this world, so nothing rolled |
| `diaspora` | 0 | **1** | 1 | 1 candidate rolled and it did not precipitate; the best chance offered was 0.7 |
| `council` | 37 | 109 | 109 | 37 of 109 candidates precipitated |
| `champion` | 2 | 2 | **35** | 2 of 2 candidates precipitated |

**The card said "the antagonist role fires zero times". The truer statement is stronger: it never
rolls.** `dread` has no row in `rolls` at all. All 39 ruins in that world fell to war (36), water
(1) or air (1) and none to a beast, and `wells/ruins.py` only builds a Dread for a ruin whose
`cause` is in `history.BEAST_CAUSES`. 957 nests are placed and not one of them ever took a city.
So the diagnostic's answer is not "the roll went badly" but "the input does not exist", and those
are the two readings the card says a consumer cannot currently distinguish.

`diaspora` is the contrasting case and is worth keeping in view: one candidate, chance 0.7, lost
the roll. Under the old block both it and `dread` were invisible in exactly the same way.

`champion`'s `sources` 35 against `candidates` 2 is the third shape: the well walked 35 living
cities and only two stand within a dangerous nest's reach. `sources` exceeding `candidates` is
what says a gate is doing the work rather than the world being empty.

### How it avoids being a second, drifting copy of each well's gate

The risk in a report like this is that it re-derives every well's predicate in a second place and
then disagrees with it. Two things keep that from happening:

- `rolls` already records every candidate that was **evaluated**, so `placed` and `candidates` are
  read off the ledger the wells already write, never recomputed.
- `sources` counts the population each well **iterates**, and `source_kind` says in words what was
  counted rather than restating the gate. Where the count *is* the gate it goes through the name
  the well itself uses: `history.BEAST_CAUSES`, `wells.cities.DIASPORA_ROLES`, and two names
  added to `wells/magic.py` in this change — `key_point_id(ruin)` and `SELF_MAGIC_CAUSE` — with
  the well itself rewritten to call them, so there is one definition and not two.

`test_the_counts_agree_with_the_cast_and_the_ledger` reconciles the table against `people`,
`dreads`, `camps`, `rolls` and `summary` in both directions, so a row that stops adding up fails.

### A finding the card did not have: one role is not a person

`camp` is a key in `precipitation` and it precipitates a **place**. Its `placed` counts rows in
`camps[]`, and a consumer looking for its 12 in `people` finds none. That is asserted explicitly
rather than filtered out of the reconciliation, because dropping it quietly is how it would stop
being visible, and it is stated in the schema and in `docs/hero-generator.md`.

### Version, and why none moved for this

None, and the reason is not that nothing changed. `heroes` **was** bumped 1 → 2 in this same
uncommitted tree by the concurrent quest-contract session — checked with
`git show HEAD:Sim/hero_generator/__init__.py`, which has `VERSION = 1`. Neither 1 nor 2 has
shipped, so version 2 is the unreleased version this additive key lands inside, and one increment
covers the quest contract, the `SDET-SITE-ID-ORDINALS` re-key and this. Under decision 023 an
additive key that carries its own schema and leaves replay identical would not force one in any
case: a world without `diagnostics` reads as "not reported", which is exactly true of it.

`Contracts/schemas/hero-generator.schema.json` gains `diagnostics` and a closed
`$defs.diagnostic`. `Fixtures/sample-world-v1.json` goes stale, as it already had from
`SDET-SITE-ID-ORDINALS` in the same sweep; it was not rebuilt here.

**Conformance:** none touched. No record claims `Sim/hero_generator/**` — the package is in
`coverage.json`'s `uncovered` allowlist under `board/in-progress/CONFORMANCE-DOCS.md` — and no
record describes the `heroes` block. `docs/hero-generator.md` is the canonical document and it
carries the new section.

### Files changed

`Sim/hero_generator/__init__.py` (`_sources`, `role_diagnostics`, the new block key),
`Sim/hero_generator/wells/magic.py` (two shared names, and the well routed through them),
`Sim/tests/test_hero_diagnostics.py` (new),
`Contracts/schemas/hero-generator.schema.json`, `docs/hero-generator.md`.

## Delivered 2026-09-21 — the `magic` half, step 1

`magic.diagnostics` now carries one row per institution, placed or not, in the shape `heroes`
and `key_locations` publish: `{institution, placed, wanted, candidates, sources, source_kind,
reason}`. `wanted` is the seventh key because unlike a hero role a college has an explicit
budget, and this card's whole complaint is `colleges: []` standing against
`effective_config.college_count: 2` with nothing between them. `wanted` is `key_locations`'
own word for that, not a new one.

**Failing test first.** `Sim/tests/test_magic_diagnostics.py`, 10 tests. Before the change the
module would not import, and behaviourally `result['magic']['diagnostics']` raised
`KeyError: 'diagnostics'` — the same message the `heroes` half reported. All ten pass in 0.043 s
with no world generated. `Sim/tests/test_terrain_magic.py`'s 4 tests stay green, including
`test_magic_is_deterministic_and_does_not_change_ground`, which compares two generations' whole
`magic` blocks and so now pins the new key as deterministic too.

### The answer, on real worlds, and it is the same shape as the Dread's

Through the pinned recipe-3 request (`{'recipe_version': 3, 'seed': 42, 'overrides': {'size': N}}`),
phase 16, generator 16 — a hand-built `Config` leaves `globe_radius` at the 10 km design default
and generates a different, tiny world, which is worth knowing before anyone re-measures this:

| size | cities | wanted | placed | candidates | sources | reason |
|---|---|---|---|---|---|---|
| 17 | 12 | 2 | 0 | 0 | 41 | 41 cells within a city's support reach were read and none produced a candidate; **density** refused the most, at 28 |
| 33 | 35 | 2 | 0 | 0 | 232 | 232 cells within a city's support reach were read and none produced a candidate; **density** refused the most, at 150 |

Size 33 is the configuration `Fixtures/sample-world-v1.json` is built at, and the reconstruction
agrees with the committed bytes: that file carries `"colleges":[]` and
`"college_spacing_m":4774.6482927568595`, and this run reproduces both.

**`candidates: 0` with `sources` in the hundreds is the reading this card said a consumer could
not reach.** It is not that colleges rolled and lost, and not that colleges are unimplemented: of
the 232 cells a city can reach at size 33, **150 fail on magic density alone** — `density >= .35`
— before slope, temperature, freshwater, flood or suitability get a turn. That is the Dread's
answer in a different block: the input does not exist. It also localises step 2 for the magic
side to one number, the way the Dread row localised it to `BEAST_CAUSES`.

Note the second fact in the same row: only **232 of 1,024 cells** are within a city's support
reach at size 33 (41 of 256 at size 17). The college pass never looks at the rest, which is why
`sources` counts what it walks rather than the grid.

### How it avoids being a second, drifting copy of the gate

`college_eligible` was an eight-clause `and`. The diagnostic needs to name *which* clause
refused, and writing that out a second time beside the gate is how the report and the gate start
disagreeing. So the predicate was inverted once: `college_refusal` returns the name of the first
of `COLLEGE_LIMITS` that refuses a cell, or `None`, and **`college_eligible` is now
`college_refusal(...) is None`**. There is one definition. The clause order is the original
chain's short-circuit order, so "the limit that refused" means what it always meant, and the
comparisons are unchanged rather than rearranged. `test_the_gate_and_the_diagnostic_have_one_definition`
drives all eight limits and asserts the two agree on every one.

`add_colleges` then counts what it already walks: `sources` off `owner`, `candidates` as cells
that cleared every limit, and the refusals per limit off the same call the gate makes. Nothing
is recomputed.

**One ordering change, and it does not move a college.** The budget check moved from the top of
the loop to below the limits, so a cell the budget never reached still counts as a candidate —
otherwise `candidates` could never exceed `placed` and the report could not distinguish "the
world ran out of ground" from "the budget stopped it". Placement is identical: the checks it
moved past have no side effects, and a `continue` past the placement body leaves `colleges`,
`occupied` and `college_points` exactly as the old `break` did.
`test_placement_is_unchanged_by_the_diagnostic` pins the seated colleges against the gate itself.

### The key is present even when the pass has not run

`generate_networks` writes `colleges: []` and `add_colleges` fills it later, so between the two
an empty list means "not yet", not "none placed" — and in a finished document those read alike
if only one of them says anything. `generate_networks` therefore seeds `diagnostics` with a row
whose reason is *the college pass has not run at this phase, so nothing was evaluated*, and
`add_colleges` replaces it. The seeding is a separate `from .terrain_magic import
pending_college_diagnostics` statement inside the function body **deliberately not added to the
module-level import at `terrain_leyline_history.py:10`**, because that line also carries
`add_magic`, the dead second writer, and nothing should give a later reader a reason to reopen it.

**`add_magic` was not touched, not called and not connected**
([retired card](../retired/MAGIC-ADD-MAGIC-DEAD-WRITER.md)). The `shadow_note` in
`docs/conformance/version-bindings.json` that suppresses the version-1/version-4 disagreement
rests entirely on its being unreachable, and it still is.

### Version, and why none moved

`magic` stays at 4. `diagnostics` is additive, a world without it reads as "not reported" — which
is exactly true of one — and replay is identical because the report is computed from the pass and
never read by it. That is decision 023's compatible-change pattern and the same call the `heroes`
half made for the same reason.

**Recorded because it is a judgement and not a fact:** the conservative alternative was 4 → 5,
on the ground that 023's pattern is written for an additive block carrying its own schema and
`magic.diagnostics` is a key inside an existing block. It was rejected because a bump changes
nothing for any consumer here — no reader of `magic` can be broken by a key it does not read —
and because the two documents that would have to move with it, `docs/terrain-world-layers.md`
and `docs/conformance/version-bindings.json`, are fenced and shared respectively. **That second
reason is a constraint, not an argument**, and it is written down so the owner can weigh it:
if the bump is wanted, it is a one-line change plus those two documents.

**`Fixtures/sample-world-v1.json` is now stale** — the `magic` block gains a key, so the bytes
move. It was already stale from `SDET-SITE-ID-ORDINALS` and the `heroes` half in this same sweep.
Not rebuilt here.

`college_method` gained a sentence pointing at the new row. This card observed that the old
sentence, *"Sites may be fewer than requested"*, "covers one of two and reads differently at
zero"; it now says where the other one is answered.

**Conformance:** none touched, and the reason is not that nothing changed. No record claims
`Sim/icarus_sim/terrain_magic.py` or `Sim/icarus_sim/terrain_leyline_history.py` — both are in
`docs/conformance/coverage.json`'s `uncovered` allowlist under
[CONFORMANCE-DOCS](../in-progress/CONFORMANCE-DOCS.md) — and no record describes the `magic`
block's contents. The document that does, `docs/terrain-world-layers.md`, is fenced to another
session for the duration of this sweep, so **this card's third acceptance bullet, "the
conformance records for `heroes` and `magic` state the gates", is still unmet for both halves**
and is now the cheapest thing left in it.

### Files changed

`Sim/icarus_sim/terrain_magic.py` (`COLLEGE_LIMITS`, `SOURCE_KIND`, `college_refusal`,
`college_eligible` routed through it, `pending_college_diagnostics`, `college_diagnostics`, and
the counting inside `add_colleges`), `Sim/icarus_sim/terrain_leyline_history.py` (the seeded row),
`Sim/tests/test_magic_diagnostics.py` (new).

**`terrain_magic.py` is provenance-pinned**, so this change needs a revision row in
`provenance/extraction-manifest.json`. That file is owned by the sweep orchestrator and was not
touched here.

## What is still open — step 2

**Step 2 — deciding whether the zeros are correct — is still open, and is now cheap.** The
diagnostic makes the measurement trivial, which is what it was for. The specific question the
table raises: `dread` has zero candidates on a world with 957 nests, so "a beast destroys a city"
is either rare by design or gated on something that never fires, and `terrain_history.city_fate`'s
lottery is where that is decided. Re-measure at sizes 17, 33 and 65 before concluding anything.
**The diagnostic reports that no ruin named a beast; it does not establish that a world of that
size and age ought to have produced one**, and a role gated on something unreachable would report
faithfully and look exactly like a world that simply lacks the ground.

**The magic side of step 2 now has a number to argue about.** At size 33, 150 of the 232 cells a
city can reach fail `density >= .35` in `college_eligible`, and the world seats no college at
either size. The same two readings apply and the diagnostic does not choose between them: either
0.35 is the right floor and a 200 km world simply does not concentrate that much magic near
where people live, or it is a floor a world of this size can no longer reach, in which case
colleges are gated on something that effectively never fires.

Two things to check before anyone concludes either, and neither is evidence on its own. **The
field's geometry is already scale-aware**: `generate_networks` multiplies every school's `width_m`
by `globe_radius / REFERENCE_RADIUS_M`, precisely so a Gaussian authored on the 1774 m reference
world still covers the same share of a 200 km one — so "the threshold was never rescaled" is the
obvious story and it is the wrong one to reach for first. **What does not scale is how much there
is to be near**: each school seats a fixed `<school>_nodes` (default 10) however large the world
gets, and `magic_density` saturates a sum over those, so the reachable-by-a-city subset of a
bigger world holds the same number of sources spread over more ground. The measurement that would
settle it is the distribution of `magic_density` across the `sources` cells at 17 / 33 / 65
against the 0.35 cut — which the diagnostic makes obvious to ask and does not itself answer.

Both halves of this card now end in the same place: the report is faithful, and whether the world
it reports is the world that was wanted is a separate question.

---

Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 7).

## Observed behavior

Seed 42, size 17, `generator_version` 16.

**`heroes.dreads: []`.** `heroes.rolls` holds 131 candidates; `heroes.summary` reports
`{"living": 54, "legends": 6, "dreads": 0, "realms": 9, "orgs": 8, "camps": 7, "hooks": 49,
"candidates": 131, "precipitated": 67}`. Sixty people precipitate across ten roles — council
(41 rolls), heir (14), domain holder (14), camp (14), keeper (13), warlord (9), sovereign (9),
reeve (7), harbourmaster (6), castellan (4). **The antagonist role fires zero times.**

`story_web` then weaves 54 of those 60 into 51 reachable tropes, offering `the_court` 8 times,
`the_blight` 7, `the_march` 7, `the_siege` 6, `reclamation` 4, `the_vow` 4, `revenge` 2. A cast
with beliefs, wants, fears, tells and claims, and nobody to oppose.

**`magic.colleges: []` against `effective_config.college_count: 2`.** `magic_enabled` is 1,
twelve schools resolve, 78 ley nodes place, fourteen of them are key points raised by destroyed
cities, and `human_magic_limit` is 0.45. Zero institutions.

**Neither shortfall is reported as a shortfall.** `heroes.summary.dreads` is `0` with no reason
attached. `magic` emits no diagnostic for the colleges it did not place; its `college_method`
says *"Sites may be fewer than requested"*, which covers one of two and reads differently at
zero.

## Why it matters

A world with 60 named heroes, 51 tropes and no antagonist is a story with no second half. `the_siege`
is offered six times and there is nobody besieging. Whatever the quest consumer turns out to be,
`heroes` and `story_web` are the strongest authored content in the document and the half that
would give them stakes is empty.

The missing colleges matter less on their own and more as the second instance of the same
reporting gap: a consumer reading this document cannot distinguish "this world has no colleges
because the world is small" from "colleges are not implemented" from "colleges failed to place".
That distinction is exactly what `PRODUCT-REACHABILITY-REPORT` asks every catalogue to publish,
and `key_locations` already does — every archetype appears in `sites` or in `diagnostics` with a
reason, including `{"archetype": "maelstrom", "placed": 0, "wanted": 0, "candidates": 78,
"reason": "the world is too small to support one"}`.

## Proposed mechanism

Two separable pieces; the second is the cheap one and should not wait for the first.

1. **Report the absence.** Give `heroes` and `magic` the diagnostic shape `key_locations` uses:
   for each role or institution that could exist, whether it placed, how many candidates were
   evaluated, and the reason none did. This is a reporting change, needs no design decision, and
   turns two silent zeros into two answerable questions.
2. **Then decide whether the zeros are correct.** If the dread role is gated on world size or age
   count and this world clears neither, the diagnostic will say so and there is nothing further
   to do here. If it is gated on something that never fires, that is a separate defect and the
   diagnostic is what finds it. The `VILLAIN-*` cards cover the villain system's code; this card
   is about the emitted world containing none of its output.

## Dependencies and unresolved decisions

- Whether `heroes.dreads` and `terrain_villains` are the same population under two names. The
  document mentions `villain` 18 times and emits no `villains` block; the relationship between
  the two is not stated anywhere a consumer can read, and `VILLAINS-NO-SCHEMA` already notes the
  block has no contract.
- Whether either is size-gated. Both should be re-measured at size 33 and 65 before any
  conclusion that they never fire — the diagnostic in step 1 makes that measurement trivial.

## Acceptance and evidence

- A generated world in which a role or institution does not appear carries a reason it did not,
  in the block that owns it.
- A behavioral test asserts that every role in the hero policy appears in `people` or in a
  diagnostic, so a role that stops firing is visible.
- The conformance records for `heroes` and `magic` state the gates.

## Adversarial review and limitations

One seed at one size. Both zeros may be correct behavior for a 200 km world and this card does
not claim otherwise — it claims the document gives a consumer no way to find out. That claim does
not depend on the seed.
