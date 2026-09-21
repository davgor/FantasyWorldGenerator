# HERITAGE-GEOMETRY — should race traits move where cities go?

> **RETIRED 2026-09-21 — removed from the backlog by owner instruction, not finished and not refused.**
> This card was **awaiting an owner decision, and it still is.** What is known is that the owner had it
> removed from the backlog on 2026-09-21. **That is not an answer to the question it asks** — whether
> race traits should move where cities go — and this banner deliberately does not record one. Nobody
> should read this retirement as “the answer was no”. If trait-driven geometry is ever wanted, ask for
> the decision; do not infer it from the fact that the card left the backlog.
> Nothing here is a blocker. Read it for what it measured, not for what it instructs.

Owner: none. State: awaiting a decision from the user.

## Status

**Not started, and deliberately so.** This card exists so the question is a decision with its
costs visible, not a dropped thread.

**The argument to weigh first.** `human_maritime` already carries `coastal_score_weight` 0.15
and `tidekin` 0.35; their seafaring character is therefore **already expressed in the numeric
profile**. A `craft_focus: seafaring` term would be a second, independently tuned expression of
one idea — the exact two-sources-of-truth failure the heritage layer was built to prevent. The
honest conclusion may be that heritage should never touch geometry: its job is culture,
language and naming, and placement stays numeric. Everything below is the cost of deciding
otherwise.

## Requested behavior

The approved heritage plan scoped a phase that would route key traits into placement: habitat
priority, settlement suitability scoring, founding rotation and war kind. It was scoped
**conditionally** — "if traits touch scoring" — and that condition was never met.

## Why it was not built

**No trait-to-geometry mapping was ever designed.** Nothing anywhere specifies what
`kinship: crew_and_berth` or `memory_mode: carved_record` should do to a suitability score. The
seventeen axes were designed to feed culture and phonology, and they do. Inventing a numeric
mapping from them to placement now would be authoring game balance under the heading of
completing a deferral, which is a different and much larger decision than the one that was
approved.

**It is the only work that is simultaneously geometry-moving, provenance-pinned, and mirrored
in three C++ files.** `terrain_settlements.py:727` is pinned; the native mirrors are
`Core/settlements.cpp`, `Core/founding.cpp` and `Core/humans.cpp`. Everything downstream —
population budgets, roads, hinterlands, ports, wars, ruins, leylines, heroes, story web —
re-bases off city placement.

**The precision hazard is real and is not the one usually cited.** It is tempting to blame
`pow()`, but that is a build-linkage issue the repo has already pinned: `tests/native_cxx.py:51-58`
builds with `/MD` deliberately because the static CRT's `pow()` disagrees with `ucrtbase.dll` by
one ulp and `perlin3` evaluates it three times per sample. Under the linkage the suite actually
uses, they agree.

The live hazard is simpler and unavoidable: **floating-point addition is not associative**, and
`tests/test_native_world.py:186` compares founded cities with **no tolerance at all**. Any new
term added to a scoring sum changes the association order. A one-ulp difference at a single node
flips a tie in `min(pool, key=...)` at `founding.py:65`, and a 40-city diff follows from a cause
that is invisible in the diff. Reproduction is 70–120 s per attempt.

**Anything tuned now would be tuned against the sparse end.** A seed-42 world at size 17 has
**47 land cells** and is raster-bound rather than density-bound; size 33 has 268. A weight that
looks right at 17 is not evidence about 33.

## The questions that need answering before any of this is buildable

1. **Which axes are even supposed to affect placement?** `mobility` and `outsiders` have a
   plausible claim. `dentition` and `carrying_register` clearly do not. Without a stated list,
   the surface is all seventeen.
2. **Against what does a categorical axis become a number?** The existing profile has 37 tuned
   numeric fields. Is a trait a multiplier on one of them, an additive term, or a gate? Each
   answer has a different blast radius.
3. **Is this not already expressed?** `human_maritime` already has `coastal_score_weight` 0.15
   and `fishing_reach_multiplier` 1.0; `tidekin` has 0.35 and 1.5. The *seafaring* character of
   those peoples is already in the numeric profile. A `craft_focus: seafaring` term would be a
   second, independently tuned expression of the same idea — which is precisely the
   two-sources-of-truth failure the heritage layer was built to avoid.
4. **What evidence would show it worked?** City counts and node positions will move by
   construction. What is the intended *shape* of the change, so a reviewer can tell a good diff
   from a regression?

Question 3 is the one I would want answered first. My own reading is that the numeric profile
already encodes what the traits would be asked to encode, and that the honest conclusion may be
that heritage should **not** touch geometry at all — that its job is culture, language and
naming, and placement stays numeric.

## If it is built anyway

Sequence, from the approved plan, one cause per commit and never batched:

1. `terrain_civilizations.py:18-28` habitat priority — widest blast, so first, to keep later
   diffs small.
2. `terrain_settlements.py:727` suitability scoring — pinned, one provenance row.
3. `founding.py:42,58` rotation and participation.
4. `terrain_wars.py:46` war kind — last, and worth asking whether it should happen at all; a war
   outcome change propagates through `ruin_legacy` into leylines and every later age.

Required mitigation for step 2: add the new term as a **separately exported scalar** first,
parity-check it through the fast `catalogues` REPL in `Core/tests/world_driver.cpp`, assert both
implementations equal, and only then multiply it in — as a single new right-hand term appended
to the end of the existing sum, never interleaved. Port the C++ in the same commit. If
`tests/test_native_world.py:186` reddens, revert rather than debug forward.

Evidence on both sides of each step:
`PYTHONPATH=Sim python -m fantasy_world_generator generate --seed 42 --size 17 --output before.json`,
diffing `settlements.sites[*] -> (node, population_profile, founding_turn, founding_year)`,
`population_budget.allowances`, `roads.routes[*].nodes` and `humans.cores[*].food_supply`.
`tools/terrain_metrics.py` is the wrong tool — it reports elevation, relief and tectonics only.

## Sources consulted

`Sim/icarus_sim/terrain_settlements.py:727`, `founding.py:42,58,65`,
`terrain_civilizations.py:18-28`, `terrain_wars.py:46`, `tests/test_native_world.py:186`,
`tests/native_cxx.py:51-58`, `docs/decisions/021-heritage-chain.md`.

## Handoff

Phases A, B and D of the heritage work are complete. This is the only part not done, and it is
not done because it needs a design decision rather than an implementation. Related:
`board/backlog/HERITAGE-NATIVE-MIRRORS.md` lists the C++ mirrors this would additionally
require.
