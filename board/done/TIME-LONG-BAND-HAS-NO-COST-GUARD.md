# TIME-LONG-BAND-HAS-NO-COST-GUARD — the guard is on the band that cannot be reached cheaply, and not on the one that can

Owner: none. State: **DELIVERED 2026-09-21.** Created by
[decision 028](../../docs/decisions/028-an-age-is-five-thousand-years.md) and found by the
session that implemented it.

> **Premise re-tested before implementing, and it reproduces exactly as written.**
> `band(4999 years) -> 'long'`, `ages_for -> 0`, `steps(0, 4999 years) -> 1,804,646`,
> `band(100 years) -> 'long'`, `band(5000 years) -> 'age'`. Every figure in *Observed
> behavior* below is current.
>
> What the card could not know is how much that span actually costs, because nothing had
> been timed. It is **26.8 seconds** at size 17 and **79.9 seconds** at size 33, measured —
> expensive, and an order of magnitude less alarming than 1.8 million steps sounds. The
> guard is still right; the reason is "a caller should be told before paying", not "this
> would hang".

## Observed behavior

Measured 2026-09-21 against the tree as it stands, with `AGE_YEARS = 5000`:

```
band(4999 years)     -> 'long'
ages_for(4999 years) -> 0
steps(0, 4999 years) -> 1,804,646
band(100 years)      -> 'long'        (was 'age')
band(5000 years)     -> 'age'
```

`advance_time_request({'elapsed': {'years': 4999}})` is therefore **one tick of 1,804,646
steps** — 1,799,640 daily quest sweeps plus 4,999 ley drifts and the rest — with no cost
estimate, no `age_gate`, and no refusal path.

The guards exist and are in the other branch. `cost_estimate`, `age_gate` and the
`over_capacity('elapsed', ages, MAX_AGES_PER_REQUEST, 'ages per request')` refusal are all
reached only when `schedule.band(days) == AGE`. Below that boundary a span is executed, however
long it is.

## Why it matters

This is not a number that needs retuning. It is a guard on the wrong axis, and decision 028
moved a fifty-fold cost increase to the unguarded side of it.

Before the ruling the boundary sat at 100 years, so the largest unguarded span was a century and
the AGE band caught everything above. After it the boundary sits at 5,000 years, so a caller can
ask for 4,999 years — 49.99 ages' worth of ticking — and reach none of the machinery built to
say *this will be expensive, here is the estimate, here is why the world refuses*. The band that
kept its guard is the one that was already the most careful, because an age advance was always
understood to be costly. The band that lost its ceiling is the one a game actually drives.

`MAX_AGES_PER_REQUEST = 50` now means 250,000 years rather than 5,000. Whether 50 is the right
integer is a much less interesting question than the fact that it caps the cheap-to-refuse path
while the expensive-to-execute path has no cap at all. Argue the shape first; the integer is
downstream of it.

## Proposed mechanism

A cost guard keyed on **work**, not on band membership. The step count is already computable
without doing any of it: `schedule.steps(now, days)` is pure and `schedule.plan(now, days)`
exists precisely to say what a span would do without doing it. So the estimate a caller deserves
is available before the first pass runs, at every span length, which the AGE band's own estimate
is not — it extrapolates from generation cost and reports `measured: false`.

Follow the age band's established shape rather than inventing a second one: **report, do not
raise.** A caller asking for something too large deserves the estimate and the reason together,
in the `refused_by_world` envelope under `time_advance.blocked`, with `commit` to proceed
anyway. That path is already built, already tested and already documented; this card extends its
reach downward rather than adding a parallel mechanism.

Open sub-questions the implementer must answer rather than assume:

- **What the ceiling is measured in.** Steps is the honest unit, because a step is what costs;
  years is what a caller asks in. Reporting both and refusing on steps is probably right.
- **Where it sits.** One ceiling across all bands, or a per-band one. A single work ceiling is
  simpler and does not re-introduce the band-selects-behaviour bug the module's own comment at
  `terrain_time_schedule.py:106` warns about at length.
- **Whether `MAX_AGES_PER_REQUEST` survives.** If a work ceiling covers every band, an
  ages-per-request cap may be redundant. Do not delete it in the same change that introduces
  the replacement.

## Dependencies and unresolved decisions

- **Nothing blocks this.** The pure planner exists, the refusal envelope exists, the report path
  exists.
- **An age advance has still never been timed directly, at any size.** `cost_estimate`
  extrapolates from generation cost and says so. A work ceiling chosen from an unmeasured cost is
  a guess with better packaging; measure at least one age advance and one long tick on a quiet
  box before picking a number, and state seed, size and machine with it.
- **Do not re-arm the ceiling-sentinel trap.** [SDET-CEILING-SENTINELS](../done/SDET-CEILING-SENTINELS.md)
  records three rejection tests that used "one above the current limit" as their sentinel, so
  raising a ceiling turned all three into legal work — a 0.1 s rejection became a 48 s
  generation. A test for this guard must not pick its sentinel by arithmetic on the constant.
- **Nothing native is owed**, under [027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md).

## Files and assets in scope

`Sim/icarus_sim/terrain_time.py` (the guard and its report), possibly
`Sim/icarus_sim/terrain_time_schedule.py` (if the work estimate wants a home beside `plan`),
`Sim/tests/test_time_advance.py`, and `docs/conformance/time-advance.md`, whose *Refusals* and
*Does not establish* sections both make claims this changes.

## Acceptance and evidence

- A span that would execute more than the ceiling is reported, not executed, carrying the
  estimate and the reason in the existing envelope.
- `commit` proceeds anyway, matching the age band.
- The guard is proven at a span that is **not** derived from the constant by arithmetic.
- Chunk independence is unaffected: a refused span changes nothing, and a permitted span cut
  differently still produces the same world byte-for-byte.
- A measured cost for at least one long tick and one age advance, with seed, size and machine.

## Documentation impact

`docs/conformance/time-advance.md` — the *Refusals* section currently describes the age gate as
the one refusal reported rather than raised; it gains a sibling. Its *Does not establish* entry
about age advances never having been timed is the thing this card should retire, if it measures.

## Adversarial review and limitations

- **A work ceiling is a new refusal on a path that never refused.** Any caller today that asks
  for a long span and gets a world back would start getting a report instead. That is the point,
  but it is a contract change and belongs in the record, not only in the code.
- **Steps are a proxy for cost, not cost.** `add_encounters` coalesces to one run per call while
  a daily quest sweep runs every day, so two spans with equal step counts can differ by orders of
  magnitude. A ceiling on raw steps will be wrong in both directions until something is measured;
  say so rather than presenting it as precise.
- **Do not let the guard select behaviour.** The band label deliberately does not choose which
  cadences run — `terrain_time_schedule.py:106` explains that it used to, and that it was silent
  permanent data loss rather than a conservative cut. A guard that skips work instead of refusing
  it re-introduces exactly that.
- Determinism, draw and iteration order and byte reproducibility are invariants and bind this
  work.

## What was delivered, 2026-09-21

### The measurement the card asked for first

Nothing was chosen before something was timed. Seed 42, recipe 3, through phase 16, on the
development machine with five other sessions sharing it — so **wall clock is an upper
bound**, and counts are exact because counts do not care how busy a box is:

| | size 17 | size 33 |
|---|---|---|
| Generation | 62.4 s, 69.0 s, 71.8 s | 182.9 s, 208.8 s |
| World as JSON, with / without `build_stages` | 59.2 MB / 26.0 MB | 174.6 MB / 77.5 MB |
| **One age advance** | 34.3 s, 37.6 s, 39.4 s | 181.8 s |
| Tick, 2 y / 729 steps | 0.92 s | 3.47 s |
| Tick, 50 y / 18,057 steps | 1.15 s | 4.30 s |
| Tick, 200 y / 72,207 steps | 2.05 s | 6.47 s |
| Tick, 1,000 y / 361,007 steps | 6.15 s | 19.26 s |
| **Tick, 4,999 y / 1,804,646 steps** | 26.8 s | 79.9 s |
| Peak working set, generation, then one age advance | 378 MB, then 566 MB | trimmed under load; discarded |
| Private deep copy of the world | 51 MB, about 1 s | — |
| One step tuple in `steps()`'s list | 132 bytes | 132 bytes |

Three things fall out of it, and two of them contradict the card's own framing:

1. **A tick is linear in steps**: 14.2 µs a step over a one-second copy at size 17. So the
   4,999-year span is 27 s, not the runaway the step count suggests.
2. **At the reference size the whole LONG band is cheaper than one age advance.** A ceiling
   set by "as expensive as an age advance" would therefore never fire, which is why the
   number below is argued from what a game asks for instead.
3. **Per-step cost is not world-independent.** It is 3x larger at size 33 than at 17, so
   both terms of the estimate scale with cell count. A fixed step ceiling is consequently
   generous on a small world and tight on none — stated as a limitation below rather than
   papered over.

This retires the *Does not establish* entry the card hoped it would, and replaces the
`cost_estimate` basis constants — which were recorded **generation** cost at size 129,
used to price a different pass. At size 17 they answered **0.19 s and 0.5 MB**; the same
call now answers **48.2 s and 566 MB**, against a measured 34.3-39.4 s and a 566 MB peak.
The old memory figure was wrong by nearly three orders of magnitude, in the direction that
tells a caller an expensive call is free. This is `board/README.md`'s "still uncorrected
and needing its own card: `terrain_time.py:60`'s `COST_BASIS_MB`", corrected here.

### The sub-questions, answered rather than assumed

- **Unit: steps, reporting both.** The refusal is on `schedule.work(...)`; the report
  carries `steps`, `elapsed_days` and `elapsed_years`, and the suggestion is in days
  because days are what the caller sends.
- **Where: one work ceiling, not per band.** `MAX_TICK_STEPS` applies to the steps any
  request will tick, at every band. It is asked **before** the age branch, so a span of
  ages plus an unaffordable remainder is reported whole rather than advancing its ages and
  then baulking — failure at this boundary is all-or-nothing.
- **`MAX_AGES_PER_REQUEST` survives**, unchanged and un-deleted, exactly as the card asked.
  The two bound different things: one prices a tick, the other bounds a loop of whole-world
  rebuilds this module delegates rather than executes.

### The number, and why it is that number

`MAX_TICK_STEPS = 200000` — about **554 years** from day zero, which
`schedule.longest_span` computes rather than a comment asserting it.

It is an **absolute count and never a share of an age**. Writing it as a fraction of
`AGE_DAYS` would re-couple the guard to the band boundary, which is the defect itself: how
much work a machine can afford does not change when the calendar is redefined.
`test_the_ceiling_is_an_absolute_count_and_not_a_share_of_an_age` tokenises the module and
asserts the assignment mentions neither `AGE_DAYS`, `AGE_YEARS` nor `schedule`.

554 years is an order of magnitude above any span a game drives — a century is 36,107
steps — and an order of magnitude below the band's own maximum. At size 17 it is 3.8 s;
the span it refuses at the top of the band is 26.8 s and 230 MB of transient step tuples.

### The shape

Reported, not raised, with `commit: true` to proceed — the age band's own shape, extended
down the bands it never reached. `time_advance.blocked` carries an `over_capacity`
document on `elapsed` plus `cost_estimate`. `over_capacity`'s own suggestion is
**replaced**: it clamps the field to the limit, which here would tell a caller to send
`elapsed` as a step count, a unit this API does not accept. The replacement is
`{"kind": "clamp", "value": {"days": n}}`, the longest span that fits, found by bisecting
`schedule.work`.

### Files

- `Sim/icarus_sim/terrain_time_schedule.py` — `by_cadence`, `work` and `longest_span`, all
  pure and allocating nothing. `plan` now counts crossings instead of materialising them,
  producing a byte-identical document; that second 1.8-million-tuple list was being built
  on every long tick purely to be counted.
- `Sim/icarus_sim/terrain_time.py` — `MAX_TICK_STEPS`, the guard, `tick_cost_estimate`, and
  the measured basis constants replacing the stale generation-cost ones.
- `Sim/tests/test_time_advance.py` — `WorkCeilingTests` plus three world-level tests.
- `docs/conformance/time-advance.md` — *Refusals* gains the sibling the card predicted;
  *Does not establish* gains the measurement table and loses the untimed-age-advance claim;
  *Versions asserted* records why the API version does not move.
- `docs/time-advance.md` — the narrative doc gains a section on the ceiling and loses the
  same stale claim about age advances never having been timed.

### Decisions taken on the owner's behalf — reversible, and flagged

1. **`TIME_API_VERSION` stays at 1.** This is a new refusal on a path that never refused,
   which is a contract change. It was not bumped because the refusal arrives inside
   `time_advance.blocked` with `committed: false` — the envelope this same call has always
   been able to return from the age band, so a caller that handles the age gate handles
   this — `time_advance` declares no schema, no key changes meaning, and `commit: true`
   still reaches every world the previous version reached. Bumping would instead refuse
   every caller sending `api_version: 1`, including the browser lab, to announce a field
   they can already see. **Rejected alternative:** bump to 2 with a deprecation window.
2. **The ceiling does not scale with world size.** A ceiling computed from
   `tick_cost_estimate` would move every time somebody re-measured — the same request
   refused on Monday and run on Tuesday with no constant edited — and the model rests on
   two points. **Rejected alternative:** a seconds budget read through the cost model.

### Before and after, on the card's own span

The guard's only effect is one comparison, so lifting `MAX_TICK_STEPS` out of reach
reproduces the behaviour that existed before it. Same world (seed 42, size 17, phase 16),
same request, `advance_time_request({'elapsed': {'years': 4999}})` with no `commit`:

```
BEFORE (ceiling unreachable): {"band": "long", "committed": true, "blocked": false,
                               "steps": 1804646, "clock_moved": true,
                               "operations_appended": 1}
AFTER  (ceiling 200000):      {"band": "long", "committed": false,
                               "blocked_code": "STATE_CAPACITY", "field": "elapsed",
                               "received": 1804646, "expected": {"max": 200000},
                               "suggestion": {"kind": "clamp", "value": {"days": 199439.0}},
                               "steps": 1804646, "estimate_seconds": 26.626,
                               "estimate_peak_mb": 278.2, "clock_moved": false,
                               "operations_appended": 0}
message: elapsed 1804646 is above the cadence steps per request maximum of 200000.
note:    Estimate only. Send commit: true to run it anyway, or ask for at most 199439 day(s).
```

Before, the span ran: the clock moved and an operation was recorded. After, nothing ran and
the caller is told what it would have cost — **26.6 s estimated against 26.8 s measured**,
which is the first time this boundary has been able to answer that question at all.

### Acceptance, against the card's own list

- A span past the ceiling is reported, not executed, carrying the estimate and the reason
  in the existing envelope — `test_a_tick_past_the_work_ceiling_is_reported_rather_than_executed`.
- `commit` proceeds anyway — `test_commit_ticks_a_span_past_the_ceiling_anyway`.
- The guard is proven at a span **not** derived from the constant by arithmetic: the
  sentinel is 1,000 years, a literal, and `test_the_sentinel_is_still_outside_the_ceiling`
  asserts the ceiling is below it so raising the ceiling fails there loudly instead of
  turning a rejection test into a six-second tick. The card's own 4,999-year figure is
  exercised separately by `test_the_longest_span_the_long_band_can_hold_is_refused`.
- Chunk independence unaffected: the guard runs before anything is copied and a refused
  span returns the caller's world unchanged, asserted by comparing the whole document; the
  existing byte-equality tests over cut spans are untouched and still pass.
- A measured cost for a long tick and an age advance, with seed, size and machine — the
  table above.

### Limitations, stated rather than discovered later

- **Steps remain a proxy for cost.** A coalesced pass runs once per call however many
  crossings it had while the daily quest sweep runs every day, so two spans with equal
  counts can differ. `tick_cost_estimate` carries a `precision` field saying so.
- **Nothing is measured above size 33**, and both estimates extrapolate by cell count from
  there. `cost_estimate` deliberately takes size 33 as its basis rather than 17, because an
  age advance grows faster than cell count between the two points and a cost guard should
  err toward warning.
- **A large world is expensive at any span.** The fixed ceiling does not express that; the
  estimate does.
