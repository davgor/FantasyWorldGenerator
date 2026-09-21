# PERF-ADD-NESTS-DOMINATES — the largest producer in the generator, reported as 9%

Owner: none. State: **done — the open question is ruled and the interior is profiled.**
Raised by the generation-performance pass, 2026-09-20; closed by the backlog sweep, 2026-09-21.

> **What the sweep added, in one paragraph.** The card's lead — is the second `add_nests` inside
> `age_transition` redundant, worth ~14 s of a 71 s run — is **closed: it is not redundant**, and
> not on a judgement call. The two calls are a producer/consumer pair with `city_fate` reading
> between them, they see different settled worlds, and their output fields were diffed: **over
> half the monster lairs move between the two calls.** The card's other open item, the interior of
> `add_nests` that "nobody has looked" at, is now profiled: **86% of it is one pairwise predicate**
> doing 730 million generator steps at size 17. That hot spot was independently restructured by
> the session holding the file while this profile was being taken. Nothing in this card's scope
> was edited — `terrain_nests.py` and `terrain_history.py` are both fenced.

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
add_nests <- (top, stage 13)                      1   terrain_history.py:545
add_nests <- age_transition                       2   terrain_history.py:325
add_nests <- age_transition > rebuild_tail        2   terrain_history.py:310
```

The three `terrain_history` line numbers above were re-resolved on 2026-09-21; they had drifted
from `:533`, `:322` and `:307` as that file moved under concurrent edits. The structure did not
change — four call sites, one of them in `terrain_area` — and all four still do
`from .terrain_nests import add_nests` inside a function body, which is what makes the wrapping
method in [SDET-PRODUCER-CALL-GRAPH](../backlog/SDET-PRODUCER-CALL-GRAPH.md) intercept every execution.

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
`terrain_history.py:325`, and again through `rebuild_tail` at `:310`.
Two full nest-population rebuilds per age, four across the two ages a generation runs.

The world does change between them: cities are ruined, wars resolve, and the line after the
first sets `beast_nests['evaluated_age'] = age-1`, which suggests the first exists so city
fates can be evaluated against a current nest population. **So the second is
plausibly necessary and this card does not claim redundancy.**

But four of the five expensive executions are in that frame. If one rebuild per age turns
out to be sufficient, that is roughly **14 seconds of a 71-second run**. Deciding it
requires someone who owns the nest contract and can say what each rebuild is for. A
performance pass cannot answer it from a profile.

## RULED 2026-09-21: both rebuilds stay, and not merely out of caution

**Decision: the second `add_nests` is load-bearing. Do not remove it. This closes the lead.**

The card is right that a profile cannot answer this, and right that it needs someone who can
say what each rebuild is *for*. It is wrong that nobody can: the two calls are decidable from
their **input**, without owning the nest contract and without a timing.

Nest placement reads the settled world fresh on every call. `terrain_nests.py:301`
(`add_animals`, and `add_monsters` likewise) calls `settled_directions(result, cfg)`, which reads
`result['settlements']['sites']`, `result['fisheries']['ports']` and
`result['humans']['hamlets']`; `_place` then uses the distance to the nearest of them —
`nearest`, at `terrain_nests.py:209` — both as an outright clearance refusal and as the
continuous danger ramp. **Where people are is an input to where nests go.**

The decisive fact is that the first rebuild's output is **read before the second one exists**:

| | `terrain_history.py` | what happens |
|---|---|---|
| 1 | `:325` | `add_nests`, directly in `age_transition`, against the settlements as they stand before the age turns |
| | `:362` | **`city_fate(city, result['layers'], result['beast_nests']['sites'], ...)`** — every surviving city's fate is decided against exactly that nest population. Thirteen calls at seed 42. |
| | `:308` | inside `rebuild_tail`: `civilization()` rebuilds hamlets and institutions from the surviving cities, after the ruined ones are gone |
| 2 | `:310` | `add_nests` again, now against the post-collapse settlement set |

So this is a producer/consumer pair, not a repetition. Delete the **first** and `city_fate` reads
a nest population from the wrong age, or none. Delete the **second** and the world ships nests
placed against cities that no longer exist and blind to hamlets `civilization()` had just
created — holding clear of ruins and crowding new villages. Either way it is a correctness change
dressed as an optimisation, and the ~14 seconds buys the second snapshot rather than being wasted
on it.

**The rejected alternative, recorded as the sweep rules require:** collapse the two into a single
rebuild after `civilization()`, saving roughly 14 s of a 71 s run. Rejected because of `:362` —
the consumer sits *between* the two calls, so there is no single point at which one rebuild
serves both readers.

**A loose end found while ruling, and it is not what the card assumed.** The card reads
`beast_nests['evaluated_age'] = age-1` as the evidence that the first rebuild is for city fates.
It is suggestive but it is not load-bearing: **nothing in `Sim/` reads `evaluated_age`.** The only
reader anywhere is an assertion in `Sim/tests/test_terrain_history.py:158`. The two writes at
`:311` and `:326` are a marker for humans and a test, so the real argument is `:362`, not the
marker. Worth knowing before anyone treats the marker as a contract.

**Reverse this ruling** if someone shows `city_fate` does not in fact depend on the nest
population. It does: `city_fate` passes its `nests` argument to `fantasy_nest_threats(city, nests,
radius)` at `terrain_history.py:235` and each returned threat appends a weight to `causes`, whose
sum is the probability the city is destroyed. The nest population is a direct input to whether a
city survives the age.

### Measured, so the ruling is not an argument from reading

Seed 42, size 17, phase 16, `villain_rise 1.0`, recipe 3, `AGE_YEARS = 5000`, tree `4778a3e`.
Every `add_nests` execution was wrapped and asked what the world looked like when it ran. Counts
only — no timing, immune to contention, and the machine was saturated.

| # | called from | settlements | hamlets | ruins |
|---|---|---|---|---|
| 1-5 | `apply_world_scale` | 0 | 0 | 0 |
| 6 | (top, stage 13) | 13 | 15 | 0 |
| 7 | `age_transition` | 13 | 15 | 0 |
| 8 | `age_transition > rebuild_tail` | **10** | **9** | **6** |
| 9 | `age_transition` | 10 | 9 | 6 |
| 10 | `age_transition > rebuild_tail` | **11** | **12** | **11** |

**Every rebuild pair sees a different world.** Age one: 13 settlements and 15 hamlets before the
age turns, 10 and 9 after six cities fell. Age two: 10 and 9 before, 11 and 12 after, and a
fishery port appears. The input to nest placement is different at the second call every time.

### And the OUTPUT differs too, which is the measurement this card turns on

An input difference only shows the second call *could* do different work. The question is whether
it *does*. So both calls' nest fields were captured and diffed — count, the set of sites that are
the same site in the same place, and a SHA-256 over the canonical field so "identical" means
identical. Seed 42, size 17, phase 15, `terrain_nests.py` at sha256 `17419508cd50dce8`.

| pair | block | sites | byte-identical? | of the first field, unchanged in place |
|---|---|---|---|---|
| age 1: `age_transition` → `rebuild_tail` | `wildlife` | 3562 → 4281 | **no** | 3094 of 3562 (86.9%) |
| | `beast_nests` | 411 → 441 | **no** | 184 of 411 (**44.8%**) |
| age 2: `age_transition` → `rebuild_tail` | `wildlife` | 4281 → 3979 | **no** | 3426 of 4281 (80.0%) |
| | `beast_nests` | 441 → 449 | **no** | 187 of 441 (**42.4%**) |

**Over half the monster lairs are somewhere else after the second call** — 55% in the first age,
58% in the second — and the animal field moves by 13-20%. Not a handful of sites at the margin:
the second rebuild substantially re-lays the monster population against the post-collapse world.
**The lead is closed. The second call is not redundant, and the cost is the price of the
correctness, not waste.**

Phase 15 rather than 16 because every `add_nests` execution happens at or below stage 15, so the
fields are the ones a phase-16 run produces; a phase-16 attempt died at stage 16 in `add_nomads`
on a half-applied edit by another session, after collecting every snapshot. The execution/nesting
pattern was cross-checked against a phase-16 run that did complete.

**A provenance warning on the two tables above.** They come from runs eleven minutes apart, and
`terrain_nests.py` was restructured between them — the settled-set table predates that change and
the field diff follows it. The settled-set columns are settlement counts and are unaffected. The
nest counts are not: the same executions produced 256/283/272 `beast_nests` before the change and
411/441/449 after, because the restructure also corrected the monster territorial rule (it "used
to read `a['tier']>=p['tier']`, which says the opposite in one direction"). **Do not read those
two number series as a before/after of anything this card did**; they are two different
generators. The ruling rests on the second table, whose subject file is pinned by digest.

The table also settles the card's other claim about the cheap five. Executions 1-5, reached
through `apply_world_scale`, run against a world with **zero** settlements, zero hamlets and zero
ruins and produce **zero** nests — they are no-ops, as the card says, and now for a stated reason
rather than from a bounded time. All the work is in executions 6-10.

**None of this ruling rests on a timing, and that is deliberate.** A cost figure says what
something costs and never whether it is needed. The evidence above is a consumer sitting between
two producers, two settled sets that differ, and two nest fields that differ — all counts and
structure, none of it a clock.

### The cost, relayed from another session and not re-measured here

Seed 42, **size 128**, 24-core Windows box at 21% background load, phase-16 run, **profiled**.
Five real executions: one at stage 13 (103.8 s), two across stage 14 (206.2 s), two across
stage 15 (195.5 s), in a 1244 s run. Relayed, not reproduced: this sweep's machine was saturated
all night and re-taking them would have produced upper bounds, not comparable figures.

Two health warnings, both from the session that took them. These are **profiled-run** timings and
nobody measured the wrapper overhead, so they are an order of magnitude and must not be quoted to
three significant figures. And the box was at 21% background load, which this one has not been at
any point tonight.

**A third warning, from reading them.** The summary given alongside these figures says "roughly
200 s of a 1244 s run", and the components sum to 505.5 s, not 200. The two readings that
reconcile it are *each age pair* costing ~200 s (206.2 and 195.5, which fits well) or the total
being ~505 s (~41% of the run). **Whoever owns these numbers should say which**; this card quotes
the components, which are unambiguous, and does not repeat the summary figure.

**Flagged:** this is a decision taken on the owner's behalf under the sweep's standing
"pick the conservative option and record it" rule. It is also the only option available to this
sweep — `terrain_nests.py` and `terrain_history.py` are both fenced to other live sessions, so
removing a rebuild could not have been implemented here even if it had been right.

## Does not establish

- That the shares hold at other sizes. This is one size, one seed, on a contended machine.
  The size-33 shares from this pass were taken with the defective instrument and are
  withdrawn rather than corrected.
- That either rebuild is removable. See above — that is the whole open question.
- Anything about *why* one execution costs seven seconds. The interior of `add_nests` has
  not been profiled; only its total. It may be the same raster-bound placement problem
  recorded in [PERF-CITY-COUNT-TRACKS-RASTER](../backlog/PERF-CITY-COUNT-TRACKS-RASTER.md) —
  `beast_nests` grew 369 to 1,023 between size 17 and 33 — or it may be per-nest work.
  Nobody has looked.

> **Looked, 2026-09-21. It is neither.** See [The interior](#the-interior-profiled-at-last)
> below: it is **pairwise**, a linear scan of everything already placed for every candidate.
> Not raster-bound and not per-nest — per *pair*.

## The interior, profiled at last

Seed 42, size 17, phase 16, recipe 3, tree `4778a3e`, Windows 11, CPython 3.12.10, machine
**saturated**. `add_nests` wrapped in a `cProfile` enabled for the duration of the call and
disabled after, accumulating across all ten executions, so this charges the **interior only**.

**Call counts are exact and immune to contention; they are the result. The seconds are upper
bounds inflated by both the contention and the profiler, and must not be quoted as costs.**

```
916,663,155 function calls inside add_nests, at size 17
                                       ncalls   tottime   cumtime
  add_nests                                10     0.005   145.363
    _place                                 10     0.921   145.279
      add_animals                          10     0.006   126.909
        dominance                      380,459     0.316   124.987
          <genexpr>                729,795,104    64.993    83.812
            distance                16,994,449    11.821    30.613
      add_monsters                         10     0.004    18.449
        dominance                       65,360     0.057    17.339
```

**86% of `add_nests` is one predicate, and the shape is quadratic.** `dominance` was called
380,459 times and each call ran `any(a['species_id']==p['id'] and distance(...) for a in placed)`
— **a linear scan of every site already placed, for every candidate**. 380,459 calls expanded
into **729,795,104** generator steps: an average of ~1,900 already-placed sites examined per
candidate, in a world that ends up holding a few hundred. The species-id test is first and cheap,
so only 17.0 M of those 730 M reached `distance`; the other 713 M were pure filtering.

That answers the card's open question. It is **not** the raster-bound problem of
PERF-CITY-COUNT-TRACKS-RASTER and it is **not** per-nest work. It is per *pair*, and it grows
with the square of the placed population, which is why it is the whole cost while the grid at
size 17 is trivially small. **`add_animals` is 127 s of the 145 s and `add_monsters` 18 s** —
animals dominate because there are far more of them to scan against.

### That hot spot was restructured while this profile was being taken

The profile above describes `terrain_nests.py` as it stood before **02:14:24 on 2026-09-21**.
At that moment the session that holds that file replaced the `dominance(p, reach, cell, placed,
radius)` callback with a `bucket(p)` callback and `company = held.setdefault(bucket(p), [])`, so
the `any(...)` now scans **only the sites in the same bucket** — the same species for animals,
the same tier for monsters — instead of everything placed so far.

**That is precisely the change this profile argues for**, arrived at independently.

### The win, measured

Re-profiled against the restructured file, same seed, size, phase and method. The subject is
pinned by digest in both runs so there is no doubt which code each describes.

| | before (pre-02:14:24) | after (sha `17419508cd50dce8`) | |
|---|---|---|---|
| function calls inside `add_nests` | 916,663,155 | **149,268,096** | **6.1x fewer** |
| the territorial scan's generator steps | 729,795,104 | **13,084,026** | **55.8x fewer** |
| `distance` calls | 16,994,449 | 12,695,317 | 1.3x fewer |
| per expensive execution | 25.0-33.3 s | 6.6-7.1 s | |
| `add_nests` total, of the generation | 145.4 s of 215.3 s | 34.1 s of 102.8 s | |

**The call counts are the result: exact, and immune to contention.** The scan is down 56-fold,
which is the restructure doing exactly what bucketing by species should do — the 713 M steps that
were only ever comparing a species id against a non-match are gone, and what remains is close to
the 17 M that previously reached `distance`.

**The seconds in that table are NOT a speedup measurement and must not be quoted as one.** Both
runs were taken on a saturated machine, minutes apart, under different and unmeasured background
load, and both are inflated by the profiler. They corroborate the direction and nothing more.
A clean figure needs a quiet machine, which this sweep never had.

What the interior looks like now: no single predicate dominates. `distance` is the largest entry
at 8.7 s of 34.1 s tottime, and the remaining cost is spread across `sum`, the distance generator
and `max` — the shape of ordinary per-candidate arithmetic rather than a quadratic scan. **The
pairwise blow-up this card's open question was really about is gone.**

`terrain_nests.py` is fenced, so nothing in it was edited by this sweep — the convergence is
independent, not coordinated, and the measurement above is offered to whoever holds that file as
the before/after nobody had.

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
