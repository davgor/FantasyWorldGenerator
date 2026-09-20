# PERF-ADD-NESTS-DOMINATES — the largest producer in the generator, reported as 9%

Owner: none. State: backlog, unowned. Raised by the generation-performance pass, 2026-09-20.

`add_nests` is **49.2%** of a generation. Every breakdown ever taken of this generator,
including the first three from this pass, reported it as 9.0% — because it runs ten times
from four call sites and the instrument counted one.

## Measured

Seed 42, size 17, phase 16, tree at `651ab00`, Windows 11, CPython 3.12, machine contended —
shares are reliable, absolute times inflated. 41 of 41 producers instrumented, none skipped,
exclusive time charged with a stack so children are subtracted from parents.

| producer | executions | exclusive | share |
|---|---|---|---|
| `add_nests` | 10 | 34,968 ms | **49.2%** |
| `fill_cities` | 1 | 31,712 ms | 44.6% |
| `fill_hamlets` | 1 | 1,690 ms | 2.4% |
| `add_settlements` | 10 | 503 ms | 0.7% |
| `age_transition` | 2 | 26 ms | 0.0% |
| `city_fate` | 13 | 1.4 ms | 0.0% |

`add_nests` + `fill_cities` = **93.9%** of the run. Everything else together is 6%.

## Why nobody saw it

Four call sites, ten executions, and the executions are not where the sites suggest:

```
add_nests <- generate_base > apply_world_scale    5   terrain_area.py:84
add_nests <- (top, stage 13)                      1   terrain_history.py:533
add_nests <- age_transition                       2   terrain_history.py:322
add_nests <- age_transition > rebuild_tail        2   terrain_history.py:307
```

Three separate sessions counted these by reading and got three, three and then ten; the
ten came from wrapping the function and running a generation, which took seventy seconds.
**Counting call sites in one file answers a different question than counting executions in
a run**, and no grep of `terrain_history.py` could ever have found the five in
`terrain_area.py` — a function named `apply_world_scale`, for rescaling coordinates, which
in fact raises humans, colleges, seasonal food, world society and nests.

`age_transition` compounded it. It is not a producer, it is a scheduler: ten producers run
inside its two frames, and an instrument that suppressed nested calls charged all of them
to it. Its true exclusive cost is **26 ms** against the 29,414 ms it was credited with.

## Where the cost actually is

The five executions reached through `apply_world_scale` are no-ops at phases 1–5 and cost
**~25 ms combined** (bounded independently: `generate_base` exclusive is 82 ms and the old
instrument measured 107.6 ms inclusive of them).

So **five expensive executions carry the whole 49.2%, at roughly 7 seconds each**: one at
stage 13, and four inside `age_transition`.

## The lead, which is a lead and not a finding

Within a single `age_transition`, `add_nests` runs **twice** — directly at
`terrain_history.py:322`, and again through `rebuild_tail` at `:307` (called from `:379`).
Two full nest-population rebuilds per age, four across the two ages a generation runs.

The world does change between them: cities are ruined, wars resolve, and `:323` sets
`beast_nests['evaluated_age'] = age-1` immediately after the first, which suggests the first
exists so city fates can be evaluated against a current nest population. **So the second is
plausibly necessary and this card does not claim redundancy.**

But four of the five expensive executions are in that frame. If one rebuild per age turns
out to be sufficient, that is roughly **14 seconds of a 71-second run**. Deciding it
requires someone who owns the nest contract and can say what each rebuild is for. A
performance pass cannot answer it from a profile.

## Does not establish

- That the shares hold at other sizes. This is one size, one seed, on a contended machine.
  The size-33 shares from this pass were taken with the defective instrument and are
  withdrawn rather than corrected.
- That either rebuild is removable. See above — that is the whole open question.
- Anything about *why* one execution costs seven seconds. The interior of `add_nests` has
  not been profiled; only its total. It may be the same raster-bound placement problem
  recorded in [PERF-CITY-COUNT-TRACKS-RASTER](PERF-CITY-COUNT-TRACKS-RASTER.md) —
  `beast_nests` grew 369 to 1,023 between size 17 and 33 — or it may be per-nest work.
  Nobody has looked.

## Method note, because it is the reason this number exists

The first instrument charged exclusive time by **suppressing** any wrapped call nested
inside another wrapped call. That is exactly correct for a producer that runs once, and
every producer it had been checked against ran once. A defective predicate inside an
analysis gives one wrong answer; a defective predicate inside the *instrument* gives wrong
answers to every question anyone asks it, silently, indefinitely.

Two habits caught it and both are cheap. The instrument now **reports what it failed to
wrap** rather than skipping silently, so full coverage is a claim it makes rather than one
inferred from the absence of a warning. And a control was carried across the instrument
change: `fill_cities` has one call site and nothing instrumented nested inside it, so its
share must not move for instrument reasons. It moved 8.0% — explained by `422f9c3` landing
between the two runs, and corroborated by `fill_hamlets` moving 7.8% on the same patch and
`fill_castles` 3.1% on an untouched sampler. **A control cannot be a null control across a
code change**; every figure here names the tree it came from for that reason.
