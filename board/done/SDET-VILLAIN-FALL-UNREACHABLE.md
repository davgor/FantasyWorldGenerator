# SDET-VILLAIN-FALL-UNREACHABLE — no legal `villain_hold` can end a reign

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** **0 fallen against 10 seated villains**, consistent with the fall branch being dead in every buildable configuration.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: villains session. State: **closed 2026-09-21 — fixed, all six tests pass unmodified.**
The card declined to choose between two shapes; it was decided, and the rejected one is
recorded in "Resolution" at the foot along with the first fall this repository has produced.
Originally: **defect pinned by failing tests; no fix attempted.**
Evidence: `Sim/tests/test_villain_fall_reachability.py` — 6 tests, 1 control passes, 5 fail,
0.003 s, no world generated.

This is not a reopening of `VILLAIN-FALL-UNRECORDED.md`. That card was given a defect — the
fall was written onto a record that was then discarded — and its Resolution fixed exactly
that. It made the fall **recordable**. Nobody asked whether the fall could **occur**.

## Requested behavior

`OPTIONS['villain_hold']` is described as "Tier a seated villain falls below to lose the
world". Some value inside its declared range must be able to end a reign in a region that
has gone quiet. Today none can.

## The defect

Three facts, each verified against the code rather than reasoned about:

1. Seating requires `tier >= SUPER_TIER`, and `SUPER_TIER` is `1.` (`terrain_villains.py:20`).
2. The tier ledger has exactly three writers, all inside `advance()` — `terrain_villains.py:264`
   (`tiers[rid] = tier`), `:289` (the post-fall fragment) and `:312` (the rounded write-back).
   The accumulating one is `tier = tiers.get(rid, 0.) + rise * pressed`, with `rise >= 0` and
   `pressed >= 0` by construction. **A seated villain's tier is monotonically non-decreasing.**
3. The fall test is `if tier < hold`, and `villain_hold` is declared `min 0., max 1.`
   (`terrain_world.py:77`).

So the fall requires `hold > 1.0`. Bisected against a villain seated at exactly `SUPER_TIER`
— the weakest the model can produce — **a reign ends only at `villain_hold` above
1.0000000000000009.** The reachable set is empty by one epsilon.

Swept the declared range (`0.0`, `0.35`, `0.7`, `0.999`, `1.0`) crossed with `villain_rise`
(`0.0`, `0.01`, `0.5`, `1.0` = max), 25 ages each with the region collapsed to zero turmoil:
**twenty runs, zero falls, tier monotone in all twenty.**

Everything downstream of the fall is therefore dead code in any world that can be built:
`status: 'fallen'`, `fell_age`, `villains.fallen`, `claims[].holder_status`,
`claims[].holder_fell_age`, `claims[].influence`, `FALLEN_CLAIM_INFLUENCE`, `fallen_mark()`,
`marks_left()` and the seven consumer filters added when the fall was made recordable.

### Why the suite did not catch it

`test_super_villains.FallTests` forces every one of its eight tests with `hold=99.` — **99x
the declared maximum**. It establishes what a fall does and never that one can happen.

And `test_super_villains.py:111`, `test_the_band_to_stay_sits_below_the_band_to_rise`,
asserts `OPTIONS['villain_hold']['default'] < SUPER_TIER` and names it hysteresis. That
passing assertion **is** the defect: hysteresis needs a measure that can come back down, and
`tier` is cumulative turmoil-ever rather than current grip. A region at zero turmoil for 25
ages holds its villain at exactly its seating tier.

## Second defect: a villain whose region stops being produced is never looked at again

Independent of the above and surviving any fix to it. `VILLAIN-FALL-UNRECORDED.md` raised
this under "Adversarial review" as a suspicion needing a multi-age run; it is confirmed, by a
different route than that card guessed.

Not the `regions()` dedupe — that is safe, the winner keeps the anchor so the loop still
visits it. The real route is a **seat city dying**. `regions()` is rebuilt each age from
`humans.cultures`, a culture whose cities died is not produced, and `advance()` only visits
anchors produced this age. A villain at a vanished anchor is never the subject of the loop,
so its tier is never touched and the fall check never runs. It is written straight back into
`people` as standing, holding a frozen tier and reach over a region the world no longer has,
and `advance()` returns it in the standing cast that feeds `resolve_wars._villain_pressure`,
which reads `reach_m` with no status test. It presses cities together forever on behalf of a
region that does not exist.

Isolated from the first defect deliberately: the test fires at `hold=99.`, the band that
unseats any villain the loop reaches. It still does not fall.

**Consumer-visible face, needing no villain knowledge to call wrong:** `outlook()` counts
`standing` from `people` but builds `regions` from anchors produced this age. With one
stranded villain it returns `standing: 1` alongside zero regions reporting `seated: true` —
one document, two answers, no way for a reader to tell which is right.

## Proposed mechanism

**Not proposed.** Two shapes are defensible and this card does not choose between them:
decay the ledger toward current concentration so the hold band is crossable from above, or
test the fall against current concentration and leave `tier` as the accumulator it is. The
tests assert only that the reachable set is non-empty, so either passes them unchanged. The
stranded-villain defect needs its own answer regardless — a villain whose anchor is not
produced must either fall or remain reachable by the loop.

## Dependencies and unresolved decisions

- Whoever fixes the band must decide what a fallen villain's `claims[].influence` decays to.
  `FALLEN_CLAIM_INFLUENCE` is `1.0` and `VILLAIN-FALL-UNRECORDED.md` explicitly left the
  value open. It has never mattered because no villain has ever fallen; it starts mattering
  the moment this lands.
- `test_the_outlook_says_where_it_is_coming_from` asserts
  `outlook['standing'] == len(people)`. `standing` counts only the standing; `people` now
  holds the fallen. **The day a fall becomes reachable that test fails for a reason
  unrelated to the change that made it reachable.** Fix it in the same commit.
- Open and not addressed here: determinism outside seed 42 / size 17. The byte-compare runs
  only there, and the villain paths never execute in it, so nothing in this area has ever
  been replay-checked against real data. Needs generated worlds at `villain_rise > 0`.

  **Unblocking.** The reason nobody could widen the run was the age-advance size gate; the
  ceiling is being raised to 1025, owned by the performance session as a single change
  across the Python gate and its `Core/` mirror. That makes the empirical half of this card
  runnable for the first time: the static argument above says the fall branch is dead in
  every buildable configuration, and a multi-age run at `villain_rise > 0` on a grid where
  the villain paths actually execute would confirm it against real data rather than by
  reasoning. Do not run it before that change lands or it measures the old ceiling.

  Size matters here for a reason beyond speed. At the recipe-3 defaults the seed-42 size-17
  world resolves **zero of five** surface-noise octaves — see the table in
  `SDET-WORLD-SCHEMA-SURFACE.md` — so the terrain the villain regions are drawn over is
  flat. Concentration is computed from threat assessments rather than from relief, so this
  does not invalidate the static result; it does mean a size-17 run is not evidence that
  regions behave.

  **The run, specified, so whoever resumes does not re-derive it.** It was attempted on
  2026-09-20 and never got a quiet machine — see `SDET-PRODUCER-CALL-GRAPH.md` for the
  negative result. It is cheap and does **not** need a 513 world:

  1. **Size is not the constraint — `villain_rise` is.** A seed-42 size-17 phase-16 run at
     `villain_rise 1.0` already seats a villain (1 standing, 12 tier anchors, `max_tier`
     1.198, `works` built). The villain paths execute at 17. Earlier framing that this
     needed 513 confused *determinism* with *terrain fidelity*; they are separate questions
     and only the second needs the octaves.
  2. **Ladder the cost first**: phase 16 at 33, 65, 129, one process per size, stopping at
     the first size that is expensive. Nobody knows how phase-16 cost scales with the raster
     and guessing it is what the ladder is for.
  3. **Then the comparison**: the same seed twice at the largest affordable size (must be
     byte-identical), the same seed at two sizes and two seeds at one size (must differ).
     Compare canonical digests per block, not whole documents, so a disagreement names the
     block that drifted. Exclude `timing_ms` and `debug_stats`: both are clock readings and
     differ between identical runs.
  4. **Take it on a verified-quiet machine.** Poll the process table directly rather than
     relying on a report that it is clear; wall clock and peak memory are corrupted by
     contention, and this is a first-ever measurement that will be quoted.

  A harness that does all of this exists at
  `scratchpad/run_world.py` from the 2026-09-20 session — digests per block, peak RSS, wall
  clock, villain summary — but scratchpads are session-scoped, so assume it is gone and
  rebuild it; it is about seventy lines.

## Sources consulted

One citation per line, so a stale anchor names the claim it broke rather than its neighbours.

Re-anchored to the post-fix tree on 2026-09-21; the line numbers the defect was found at are
recorded in the section above and are not these.

- `Sim/icarus_sim/terrain_villains.py:28-60` — the band, fragment and ledger-decay constants.
- `Sim/icarus_sim/terrain_villains.py:295-429` — `advance`, the seat/hold/unseat loop.
- `Sim/icarus_sim/terrain_villains.py:461-506` — `outlook`.
- `Sim/icarus_sim/terrain_villains.py:148-196` — `regions` and `concentration`.
- `Sim/icarus_sim/terrain_world.py:82-84` — the declared option ranges.
- `Sim/icarus_sim/terrain_history.py:321-407` — `age_transition`.
- `Sim/tests/test_super_villains.py:176` — the hysteresis assertion.
- `board/done/VILLAIN-FALL-UNRECORDED.md` — the card this one follows.

## Files and assets in scope

`Sim/icarus_sim/terrain_villains.py`, `Sim/tests/test_super_villains.py` (the two tests named
above), `docs/super-villains.md`. No schema exists to change — see `VILLAINS-NO-SCHEMA.md`.

## Acceptance and evidence

`Sim/tests/test_villain_fall_reachability.py` passes without modification. That means:

1. some legal `villain_hold` ends a reign in a region at zero turmoil within 25 ages;
2. the band that ends a reign is inside the declared option range;
3. a region at zero turmoil does not hold its villain at peak tier indefinitely;
4. a villain whose region anchor is no longer produced is still subject to the fall check;
5. `outlook()` does not report a standing count that no region accounts for.

Test (0), the positive control, must keep passing throughout: it proves the fixture can
observe a fall at all. Five of the six tests report an **absence**, and absence is what a
broken fixture produces, so the control is load-bearing rather than decorative.

## Documentation impact

`docs/super-villains.md` describes the fall and the successor squabble as things that happen.
They do not. Either the document gains a sentence saying the band is currently unreachable,
or it is left alone until the fix lands and the sentence is never needed. Do not write a
timestamp-only edit.

## Adversarial review and limitations

- The monotonicity argument depends on `rise` and `pressed` both being non-negative.
  `villain_rise` is declared `0. .. 1.` and `concentration()` returns a mean of `turmoil()`
  values, which is clamped to `0..1`. If either ever admits a negative, re-derive this.
- **Not established:** that a stranded villain occurs in a generated world. The mechanism is
  proven at the unit level; whether a real multi-age run produces a culture whose anchor
  stops being produced needs the run. Stated as reachable-in-principle, not observed.
- **Not established:** that fixing the band is safe for replay. It changes world output by
  construction, so it is a seed-compatibility event and needs the version discipline in
  AGENTS.md. Nothing here has been run beyond the 6 new tests plus
  `test_super_villains.FallTests` and `.BandTests` (12 tests, still green, unmodified).
- `docs_check` and the checks stage are green with this file added; test modules need no
  conformance claim.

## Handoff

Found by the red-team SDET session while taking the coordinator's "villain fall through a
real age transition" assignment. The assignment assumed the fall was rare; it is impossible.
The second defect was a suspicion `VILLAIN-FALL-UNRECORDED.md` recorded and could not
confirm, and it is confirmed here by a route that card did not consider.

## A third stranding route, found and fixed 2026-09-20: a villain's own well

The card considers two ways a villain can be stranded. There is a third, it is
deterministic, and it fired for every villain bound to a school god.

`sink_well` appends a ley node at the villain's own seat direction. `_held_node` picks the
nearest ley node to that seat. So the moment a villain sinks its well, the well becomes the
nearest node and `regions()` re-anchors the region onto it. `advance` then looks the villain
up by the old anchor and misses, the accumulated tier is orphaned under a key no region
reports, and the reign ends on the age it began without ever passing through the fall branch.

The symptom was visible in the output and had been read past: a `villain_rise: 1.0` world
seated one villain and published `outlook.standing: 1` with **zero** regions marked `seated`.
The roster and the outlook were describing different worlds.

Fixed by excluding `well-` prefixed nodes from anchor selection, on the principle that a
region must be anchored to ground the world laid down rather than ground the villain did.
After the fix a default world reports standing 4 against 4 regions seated, and
`Sim/tests/test_super_villains.py` asserts the two agree and that no region anchor is a well.

**What this does not establish:** whether the fall branch is reachable now. That is still the
card's own question. Promotion seats at exactly `SUPER_TIER` and `villain_hold` defaults to
0.7, so a fall still needs a region to lose three tenths of its concentration, which no
generated world has been observed to do.

## Resolution — villains session, 2026-09-21

**Premise re-tested by running it. It reproduces exactly as written.**
`Sim/tests/test_villain_fall_reachability.py`: 6 tests, 1 control passes, 5 fail, 0.003 s.
The headline message before the change:

```
AssertionError: False is not true : no legal villain_hold in [0.0, 1.0] ends a reign over 25
quiet ages: {0.0: None, 0.35: None, 0.7: None, 0.999: None, 1.0: None}. The fall branch is
unreachable in every configuration a world can be built with, so everything it writes is dead
code in production.
```

and the bisection located the boundary at exactly the value the card claims:
`AssertionError: 1.0000000000000009 not less than or equal to 1.0`. The two stranded-villain
tests failed as described, the second with `outlook reports standing=1 but 0 of 1 regions are
seated`. **All six now pass, unmodified.**

### The choice this card refused to make, made — and the alternative rejected

The card offered two shapes and declined to choose: decay the ledger, or test the fall
against current concentration and leave `tier` the accumulator it is. **It also asserted that
either would pass the tests unchanged, and that is not true.**
`test_a_region_that_goes_quiet_does_not_hold_its_villain_at_peak_tier` asserts
`record['tier'] < seated_tier` after twenty-five quiet ages. Testing the fall against current
concentration leaves the stored tier exactly where it was, so that test fails under the
second shape. The tests pin the first shape and only the first.

**Taken: decay the ledger.** `TIER_KEPT_PER_AGE = .9` — a region keeps nine tenths of its
tier from one age to the next and adds `rise × concentration`, so the ledger measures turmoil
*sustained* rather than turmoil *ever*. From the bottom of the band a quiet region crosses
the default `villain_hold` of `.7` on the fourth quiet age — `.9`, `.81`, `.729`, `.656` —
which is what "a reign is long once established" has to mean once it can end at all. A
steady concentration `p` now settles at `rise × p / .1` instead of climbing with the world's
age, so reach measures how bad a region is rather than how old the world is.

**Rejected: testing the fall against current concentration.** Besides failing the test above,
it silently re-types `villain_hold`: the option is declared as a *tier* — "Tier a seated
villain falls below to lose the world" — and comparing it to a concentration in 0..1 makes
one number mean two things, which is the collision class this repository keeps finding.

**`.9` is a module constant, not a new option.** `terrain_world.py` is provenance-pinned, and
a new control there needs a manifest revision row the orchestrator serialises. The constant is
seed-visible and is recorded as such in `docs/conformance/time-advance.md` beside the
fallen-claim decay of decision 024, which is the same class.

### The second defect, fixed and not by an immediate fall

A villain whose anchor is not produced this age is now visited by the loop, after the
produced regions, with the concentration a region nobody produced presses — none. So it
decays and falls in the same band as any other quiet region.

**Deliberately not "a stranded villain falls at once."** The card frames stranding through a
dead seat city, where an instant fall is defensible. There is a second route it does not
name: `_held_node` picks the nearest non-well ley node, so a node appended nearer the seat
moves the anchor while the region itself carries on. Unseating that villain the moment a
nomad cult or a player edit adds a node would be a rule about ley geometry wearing the
clothes of a rule about power. Visiting it after the produced regions is also load-bearing:
a stranded reign ending must not free a seat in the same age it ends, or the fix would move
which regions seat a villain.

**The consumer-visible face is fixed by reporting, not by hiding.** `outlook()` appends a row
for an anchor that holds a standing villain but that no region was produced for, with
`culture: null` and `cities: 0`. `standing` therefore always equals the number of rows marked
`seated`. The alternative — counting `standing` off the rows — would have made the document
self-consistent by concealing the villain, which is worse than the contradiction.

### The dependency this card named, discharged

`test_the_outlook_says_where_it_is_coming_from` asserted `outlook['standing'] ==
len(people)`. `people` holds the fallen; `standing` counts the standing. Changed to
`len(villains.standing(people))` in the same change, as the card instructed.

### `claims[].influence` after a fall

The card says whoever fixes the band must decide what a fallen claim's influence decays to,
and records `FALLEN_CLAIM_INFLUENCE` as `1.0` with the value left open. **That is stale: it
was decided on 2026-09-20 and is in the tree.** `docs/decisions/024-fallen-claim-decay.md`:
`.6` at the fall, `.6` of that each further age, exactly zero below `.05`. Nothing was
changed here and nothing needed to be — the value that "starts mattering the moment this
lands" was already settled before it landed. The multi-age run below is the first time it has
ever been exercised by a real fall: the fallen villain's claim reports `influence 0.6`.

### Evidence

- `Sim/tests/test_villain_fall_reachability.py` — 6/6, unmodified, 0.003 s.
- `Sim/tests/test_super_villains.py` — 26 tests including `FallTests` (8) and the two new
  `ClaimTests`; see the run recorded in the session report.
- **The empirical half the card specified, and it did not need a 513 world or a quiet
  machine.** Seed 42, size 17, recipe 3, `villain_rise 1.0`, generated then advanced two ages
  at a time through `advance_age_request` — the real `terrain_history` path, not a synthetic
  harness. Generation 107 s, each two-age advance 78-84 s, 268 s in total.

  | age | standing | fallen records | marks | max tier | outlook standing vs seated rows |
  |---|---|---|---|---|---|
  | 2 | 3 | 0 | 0 | 1.0165 | 3 = 3 |
  | 4 | 3 | 0 | 0 | 1.5264 | 3 = 3 |
  | 6 | 2 | **1** | **1** | 1.2364 | 2 = 2 |

  `villain-2-115` rose at age 2 and fell at age 6 holding tier 0.667, and left
  `fallen-villain-2-115` with `reigned_ages: 4`, one ruin (`ruin-surface-city-0-147-elf`),
  one claim and one well. **This is the first fall this repository has ever produced**, and
  it took a `hold` of `.7` — the declared default — rather than the 99 the unit tests force.

### Limitations, stated

- **Not re-run for byte determinism.** The card's open item on replay outside seed 42 size 17
  is untouched: this change moves world output by construction, so nothing that was
  byte-compared before is comparable now. The `villains` block is at version 2 for exactly
  that reason.
- **`Fixtures/sample-world-v1.json` is invalidated** by this change and has not been rebuilt —
  it belongs to another session and the orchestrator rebuilds once at the end.
- **The stranded villain is still not observed in a generated world.** The mechanism is
  proven at the unit level and the fix is proven at the unit level; the six-age run above did
  not happen to produce a culture whose anchor stopped being produced. Reachable in
  principle, still not observed in practice, exactly as the card said.

### Ablation — each fix checked against its own deletion

Re-run against a copy of the tree with each piece of the fix removed in turn:

| Ablation | Tests that went red |
|---|---|
| `TIER_KEPT_PER_AGE` back to `1.` (the accumulator) | all three `ReachableFallTests`, plus both `VillainsContractTests` — with no decay no fall occurs, so the contract's fallen half has nothing to validate |
| the stranded-anchor visit removed from `advance`'s loop | `test_the_fall_check_runs_for_a_villain_whose_region_is_no_longer_produced` |
| the held-but-unproduced rows removed from `outlook` | `test_the_outlook_does_not_contradict_itself_about_who_stands` |

**One prediction was wrong and the result is worth recording.** Removing the loop fix was
expected to redden the outlook test too; it did not. The two stranded-villain tests turn out
to guard two genuinely separate mechanisms — whether the villain can ever fall, and whether
the document contradicts itself while it still stands — and each reddens for exactly one. A
single fix covering both would have been the weaker outcome.

### Suites run, and the two failures that are not this work's

| Module | Result |
|---|---|
| `Sim/tests/test_super_villains.py` + `test_villain_fall_reachability.py` | **32 tests, OK**, 191 s |
| `Sim/tests/test_corruption.py` + `test_terrain_nomads.py` | 69 tests, **1 failure** |
| `tests/test_world_schema_conformance.py` (villains tests) + `Sim/tests/test_key_locations.py` | villains tests **OK**; 2 pre-existing failures elsewhere in the conformance module |
| `python tools/docs_check.py` | green apart from `board/README.md` link targets other lanes own |

Every failure was **isolated rather than assumed**, by re-running it in a copy of the tree
with `terrain_villains.py` reverted to `HEAD` and nothing else changed:

- `test_terrain_nomads.NomadRouteTests.test_no_caravan_leg_exceeds_a_day_march` —
  `40980.25 not less than or equal to 36750.0`. **Reproduces identically with this work
  reverted.** `terrain_nomads.py` and its test are both modified in the working tree; it
  belongs to the nomads lane.
- `test_world_schema_conformance` carries two failures that also reproduce reverted:
  a `fortress-node-190` / `fortress-3` id mismatch in the heroes join
  (`SDET-SITE-ID-ORDINALS`, in flight) and a beast-movements divergence.

`test_corruption` is fully green, which matters here because it generates at
`villain_rise: 1.0` — the configuration this change moves most.
