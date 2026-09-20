# SDET-VILLAIN-FALL-UNREACHABLE — no legal `villain_hold` can end a reign

Owner: none. State: **defect pinned by failing tests; no fix attempted.**
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
  regions behave, and the confirming run should be at 513 or above, where all five octaves
  resolve.

## Sources consulted

One citation per line, so a stale anchor names the claim it broke rather than its neighbours.

- `Sim/icarus_sim/terrain_villains.py:20-37` — the band and fragment constants.
- `Sim/icarus_sim/terrain_villains.py:223-327` — `advance`, the seat/hold/unseat loop.
- `Sim/icarus_sim/terrain_villains.py:359-386` — `outlook`.
- `Sim/icarus_sim/terrain_villains.py:90-137` — `regions` and `concentration`.
- `Sim/icarus_sim/terrain_world.py:76-78` — the declared option ranges.
- `Sim/icarus_sim/terrain_history.py:318-396` — `age_transition`.
- `Sim/tests/test_super_villains.py:111` — the hysteresis assertion.
- `board/backlog/VILLAIN-FALL-UNRECORDED.md` — the card this one follows.

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
