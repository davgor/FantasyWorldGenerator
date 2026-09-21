---
conformance: 1
record: time-advance
tier: EXERCISED
summary: Advances a live world by an arbitrary span of elapsed time, banded by how long that span is, with a span of an age or longer answered by an age advancement rather than a tick.
modules:
  - Sim/icarus_sim/terrain_time.py
  - Sim/icarus_sim/terrain_time_schedule.py
  - Sim/icarus_sim/terrain_liveness.py
emits:
  - path: world_clock
    schema: none
  - path: quests
    schema: none
  - path: time_advance
    schema: none
versions:
  - id: time-api
    assert: 1
  - id: world-clock
    assert: 1
  - id: quests
    assert: 1
proof:
  - path: Sim/tests/test_time_advance.py
    establishes: chunk independence of the step schedule and of a real advanced world including a cut across a band boundary and a cut across the age boundary, coalescing of wholesale passes and dependency order between them, that the age band ticks its remainder and caps its ages, that a century is a long tick that moves no ground, that the per-year ley bounds compose over one whole age to the age transition's own band, the refusal envelope over a sample of malformed requests and on the reported age gate, that the instant band moves nothing seeded, the liveness predicate over every vocabulary including the block/person status collision, claim decay and its floor, the age band's estimate and its reported gate, that the work ceiling reports a span past it rather than executing it and that commit proceeds anyway, that the counter the ceiling reads answers the same question the step enumerator does, that the ceiling is an absolute count rather than a share of an age, quest opening, expiry and resolution, that an age turn closes every open quest under its own reason and rebuilds the board from the new age's hooks, that the closing-reason vocabulary and its published enum are the same list, and that the caller's world is never mutated
decisions:
  - docs/decisions/024-fallen-claim-decay.md
  - docs/decisions/028-an-age-is-five-thousand-years.md
tickets:
  - board/done/TIME-ADVANCE.md
  - board/done/TIME-LIVENESS.md
  - board/done/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md
  - board/done/TIME-LONG-BAND-HAS-NO-COST-GUARD.md
  - board/done/NOMAD-IRRUPTION-TRIGGER.md
---

# Conformance: time advance

## What it produces

A world advanced to a later moment. The caller names an elapsed span in seconds, days or
years; the span selects a band; the band decides which cadences may run. A tick moves the
living layer — quests, encounters, beast movements, nomad routes and bands, seasonal food,
the ley base field and the lunar surge — over ground that does not move. A span of one age
or longer is not a tick at all: it is answered with a cost estimate and, on request, a
delegated age advancement.

**An age is five thousand years**
([028](../decisions/028-an-age-is-five-thousand-years.md)), so the band that routes to an
age advance begins at 1,800,000 days and everything shorter is a tick however long it is. A
century is a `LONG` tick: one fiftieth of an age, moving the living layer and leaving the
ground, the plans and the cast alone. The bands are `INSTANT` under a day, `DAY` to a
season, `SEASON` to two years, `LONG` from two years to one age, and `AGE` at one age or
more. None of them selects cadences; a band names how big a span is.

**Cost is guarded on work rather than on band membership.** A request that would run more
than `MAX_TICK_STEPS` cadence steps is answered with an estimate and a reason instead of
being executed, at every span length rather than only at the age boundary, and `commit`
proceeds anyway. See *Refusals*.

The world carries a `world_clock` from the first call onward, and it is the authoritative
now that the other runtime mutators previously had to infer.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `advance_time_request(body)` | `terrain_time` | Time API 1. World in, new world out. `POST /world/advance-time`. |
| `clock(world)` | `terrain_time` | This world's `world_clock`, derived from the founding year for a world generated before the clock existed. |
| `cost_estimate(world, ages)` | `terrain_time` | What an age advance would cost, with its basis and whether it was measured. |
| `tick_cost_estimate(world, days, steps)` | `terrain_time` | What a tick would cost. The step count is exact; the seconds and megabytes are projected from a measured basis. |
| `age_gate(world)` | `terrain_time` | Why this world cannot advance an age, or `None`. |
| `schedule.steps(now, days)` | `terrain_time_schedule` | The ordered `(day, cadence, index)` steps inside a span. Pure. |
| `schedule.work(now, days)` | `terrain_time_schedule` | How many steps that span is, counted without building them. Pure. |
| `schedule.by_cadence(now, days)` | `terrain_time_schedule` | The same count, per cadence. Pure. |
| `schedule.longest_span(now, limit)` | `terrain_time_schedule` | The longest span in days whose work is at most `limit`. Pure; a bisection. |
| `schedule.plan(now, days)` | `terrain_time_schedule` | What a span would do, without doing it. |
| `schedule.band(days)` / `elapsed_days(spec)` | `terrain_time_schedule` | Band selection and unit conversion. |
| `liveness(record, block)` | `terrain_liveness` | `present` or `gone` for one person, across four blocks that disagree on the words. |
| `token(block, state)` | `terrain_liveness` | The word `block` writes for that state. The inverse of `liveness`, and the only published translation between the vocabularies. Read-only here; `POST /world/person-state` is its writer. |
| `census(world)` | `terrain_liveness` | Per-block present/gone counts. |

## Inputs it reads

A recipe 3 world through creatures (phase 13) with `terrain` 6, `generator_version` 16,
`recipe` 3 and `astrology` 1. Below the age band it reads `magic.networks`,
`settlements.sites`, `beast_nests.sites`, `heroes` (people, dreads and `quest_hooks`),
`npcs`, `villains` and `history.ages`. It does **not** require the age boundary's own
contract set: `validate_time_world` deliberately omits the age boundary's own requirements,
including its grid ceiling, because a world that cannot turn an age can still move its
encounters and its quests. The age band asks `validate_age_world` itself rather than
restating any of its rules.

## Artifacts it writes

`world_clock` — `{version, day, age, epoch_day, derived_from}`. `day` is a real number of
days since founding year 0 on the moon's calendar (24-hour days, 30-day months, 12-month
years), so a tick and `POST /world/moon` cannot disagree about what time it is.

`quests` — `{version, quests[], log[]}`. One entry per hook in `heroes.quest_hooks`, keyed
on `hook_id`, carrying the contract's `anchor` and `verb` from fields the hook already has,
a `state`, and the day and reason it closed. **Difficulty is not emitted here**; it belongs
to the quest generator, and `heroes` version 2 emits it on the hook — a consumer wanting a
priced offer joins `quests.quests[].quest_id` to `heroes.quest_hooks[].hook_id`.

`verb` is read from the hook's own `verb` field, which `heroes` version 2 added, and falls
back to `actual_effect.action` for a world generated before it. That fallback is the only
way a `verb` on this board can still be null: a ley effect carries a school and a delta and
never an action, so every ley quest of a pre-2 world reads as a verbless offer. No key was
added to a quest record and no version moved.

States this capability writes: `offered`, `expired`, and the three a caller resolves —
`completed`, `failed`, `abandoned`. It also *honours* `taken`, which stops a quest expiring
on its offer window, and **a second capability writes it**: `POST /world/quest` takes an
offer and abandons one, and [actor-scale-writes](actor-scale-writes.md) is the record for
that route. This capability reads `taken` and never sets it, because whether a party
accepted an offer is not something the world can know.

A quest whose hook disappears while the world around it stands is closed with
`closed_reason: 'hook_gone'` rather than left open. The reaper walks the union of hooks and
tracked quests for that reason; walking hooks alone left an immortal offer for every hook
that vanished, and the block grew without bound.

**An age turn closes the whole board under its own reason, `age_turned`.** An age is five
thousand years and `heroes` is regenerated wholesale, so every quest still `offered` or
`taken` closes because the world moved on, the closure is recorded in `quests.log`, the
previous age's rows are retired, and the board is rebuilt from the new age's hooks in the
same call. A `taken` quest is reaped exactly like an offered one: there is no cross-age
anchor and none is wanted
([028](../decisions/028-an-age-is-five-thousand-years.md)). `quest_id` therefore names one
age's offer only — an id seen before and after a turn is two different quests.

`age_turned` and `hook_gone` are **different reasons and a consumer must be able to tell
them apart**: one says this hook left the block, the other says the age did. The reap is
keyed on the age turning and never on an id disappearing, and that distinction is
load-bearing rather than tidy. The regenerated cast re-mints positional uids —
`hero-reeve-hamlet-node-<n>`, `hero-sovereign-<city uid>` — as the same string, so a board reaped
by id disappearance leaves behind every quest whose id was minted twice, pointing at a hook
nobody wrote it for: the old age's `anchor`, `verb` and `stated_purpose`, which are written
once at open time and never refreshed, against the new age's `_target_present` and a
`giver_uid` naming someone who no longer exists. The previous age's rows are retired for
the same reason: a retained row whose id the new cast re-mints could not be told apart from
the offer that id now names.

The seven reasons are a published vocabulary with one home, `terrain_time.CLOSED_REASONS`,
and `closed_reason` in `Contracts/schemas/read-quests.schema.json` is constrained to exactly
them plus `null`: `expired`, `giver_gone`, `target_gone`, `hook_gone`, `age_turned`,
`resolved`, and the `abandoned` that `POST /world/quest` writes.

`time_advance` — the report for the call just made: band, span, step count by cadence,
whether leylines were evaluated, and for the age band the cost estimate and any gate.

`history.operations` gains one entry per call **that advances the world**. The age band's
estimate and its refusals change nothing and record nothing. `history.replay` states that
the returned world is what must be persisted.

`world_clock` and `quests` are registered in `terrain_history.STATE_KEYS` and in the
lab's own `historyStateKeys`. That registration is load-bearing and silent when wrong:
`materialize_stage` builds an earlier stage from every key *not* in that tuple, so an
unregistered block is reported at every stage as though it had always been there,
rather than raising. `docs/conformance/nomads.md` documents the same failure for the
same list.

`magic.networks[].intensity` drifts on a one-year cadence; `surged_strength` and
`lunar_surge` are recomputed on every call including the instant band.

### Binding invariants

- **The RNG domain is keyed by simulated time, never by tick ordinal or call count.** Every
  cadence fires on an absolute index `floor(day / period)` measured from the epoch. A call
  executes exactly the indices in `(now, now + elapsed]`, half-open at the start and closed
  at the end, so a step lands in exactly one of two adjacent spans.
- **A span cut differently produces the same world.** `advance(30y)` equals `advance(15y)`
  twice, and a year equals four seasons. Proven by byte comparison of the serialised world
  with the operation log and wall-clock timings excluded — those honestly differ, because
  two calls are two operations.
- **Steps execute in absolute-time order**, ties broken by the pinned cadence order in
  `CADENCES`. A subsystem-major order is not chunk-independent and would diverge the moment
  a call boundary landed inside it.
- **`CADENCES` is dependency order, producers before consumers.** `add_nomad_routes` reads
  and writes the block `add_nomads` replaced, and `add_encounters` reads both `nomads` and
  `beast_movements`. Reordering them builds an index of bands that no longer exist.
- **A wholesale-replacement pass runs once per call, at its last crossing** (`COALESCED`).
  Thirty years runs one `add_encounters`, not three hundred and sixty. This is the same
  coalescing `advance_age_request` does at `age == start_age + steps`. It is sound only
  because a shorter period divides a longer one — so a consumer's last crossing is never
  earlier than its producer's — and only for passes that never read the block they write.
  A pass that accumulates must never be listed: `quests` carries expiry forward and
  `ley_drift` is a compounding random walk, and neither is.
- **A span runs exactly the cadence crossings inside it, and nothing else.** Three seconds
  normally runs nothing because three seconds normally crosses nothing; a sub-day span that
  does step over a day boundary runs that day's quest sweep, which is correct. The band is
  a label for the report and the route into the age band — it does **not** select cadences.
  It used to, and that was a silent permanent data loss: the window is half-open at the
  start, so a crossing skipped because one call was short was never revisited. A game
  ticking a month at a time never ran ley drift, nomads, seasonal food or the villain
  outlook, and a game ticking by the second advanced nothing but its clock.
- **A span is ticked in full.** The age band advances whole ages and then ticks the
  remainder, so one age plus thirty days equals one age followed by thirty days, and the
  operation log never claims an elapsed the clock did not move. The age turn's own quest
  reap and board rebuild are keyed on the day the age turned, for the same reason every
  other step here is keyed on simulated time.
- **The caller's world is never mutated**, and a failure leaves no half-advanced world:
  every pass runs against a private copy and the request returns it or raises.
- **Absent liveness status reads as present.** A record written before its package recorded
  departure described someone who stood; reading it as gone would turn every world
  generated before the fall pair into a world of ghosts.

### Facts that look incidental and are load-bearing

- A hidden school takes no lunar surge and carries **no** `surged_strength` key at all.
  `_apply_surge` writes only schools present in the tide factors. Widening that to all
  twelve would add a key to four networks in every world and change the bytes.
- `_apply_surge` uses `terrain_astrology.tide` rather than restating the formula. The
  surge is `strength * tide_school(day)` in exactly one place, and a second implementation
  would be free to drift from the almanac the lab and `/world/moon` both read.
- The per-year ley bounds are the per-age bounds raised to `1 / AGE_YEARS`
  (`0.65 ** 0.0002` ≈ 0.99991385, `1.35 ** 0.0002` ≈ 1.00006002). They are not a tuned pair,
  they must not be rounded to friendlier numbers, and **the exponent must never be written
  as a literal**: the point is that a whole age of year-steps composes to the age's own
  band, so the two constants are one contract. The pair that composes correctly over a
  century composes to `0.65 ** 50` — about 2e-10 — over the five thousand years an age now
  lasts, which is the magic layer draining to zero through ordinary ticking with every
  individual step inside its stated bounds and nothing out of range anywhere to notice.
- `liveness` dispatches on the block a record came from and refuses a record carrying
  `people`, `quest_hooks` or `policy_revision`. `hero_generator` and `npc_roster` both
  write a block-level `status` of `ok`/`failed` and a person-level `status` of
  `living`/`legend` under the same key name; matching on the string alone reads a failed
  package as a living person.
- `claim_influence` returns exactly `0.` below the floor rather than a small fraction, so a
  consumer scaling by it stops being nudged rather than being nudged imperceptibly forever.
- **`add_seasonal_food` is not the wholesale replacement the rest of its body is.** It ends
  with `result['warnings'].append(...)`, so every run leaves another copy of the same
  sentence. Invisible when it runs once at generation; on a cadence it turns a list of
  limitations into a tally of how often a pass ran, and it made the same span differ
  between two chunkings purely by call count. `_dedupe_warnings` runs after every coalesced
  pass, preserving order and dropping only exact repeats. This was caught by
  `test_a_year_in_four_seasons_is_a_year`, not by reasoning, and a future pass that appends
  to a shared list will need the same treatment.

### What it is not allowed to touch

Read-only to a tick: the physical layers — height, water, climate, biome and every grid
derived from them. **Not** the ley field grids: when the base intensities move, or a player
edit or a resolved hook changes a node, `evaluate_networks` rewrites the `ley_*` layers,
which is the point of running it. `terrain`, `water`, `climate`, `geological_history`,
`civilizations`,
`settlements`, `roads`, `humans`, `ruins`, `city_plans`, `hamlet_plans`, `castle_plans`,
`key_locations`, `heroes`, `story_web`, `npcs`, and the ley *geometry* — nodes and edges
are never added or removed by a tick, only their intensity drifts, and only a player edit
or a resolved hook adds a node. The villain **cast** is read-only: a villain rises, holds
or falls at an age boundary and nowhere else, because `advance` reads the threat assessment
an age inherited and raising one mid-tick would let a villain be raised by its own damage.
Only `villains.outlook`, a reading of present ground, is refreshed.

Everything in that list may be rebuilt by the age band, because the age band is an age
advance and does not pretend otherwise.

### Refusals

Every refusal at this boundary raises `terrain_errors.RequestError`, which subclasses
`ValueError`, so existing handlers are unaffected and a caller that wants the document gets
one: the field, the value received, the bound or vocabulary violated, and where available a
value that would work. `api_version` carries `retry: false`, because resending is pointless.

Two refusals are **reported rather than raised**, and they are the pair a caller asking
for a long span will actually meet. Both arrive as a document under `time_advance.blocked`
with `committed: false`, so a caller branches on the same `code`, `field`, `received`,
`expected`, `suggestion` and `retry` fields it would get from a raised refusal, and the
world comes back unchanged apart from the clock the refusal was measured against and the
report itself.

**The age gate.** A caller asking for five thousand years deserves the estimate and the
reason together, and an exception throws away the more useful half. Shaped as
`refused_by_world`: the request was well formed and the world is the constraint. A caller
unable to tell that from a malformed argument would shorten a span that was never wrong.

**The work ceiling, `MAX_TICK_STEPS`.** A request that would execute more than 200,000
cadence steps **as a tick** is reported with its cost rather than attempted. Shaped as
`over_capacity` on `elapsed`, because the request is well formed and the constraint is
cost rather than world state. `suggestion` is replaced rather than taken from
`over_capacity`, which would otherwise tell a caller to clamp `elapsed` to a step count:
it carries `{"days": n}`, the longest span from this world's clock that fits, found by
bisecting `schedule.work`.

`commit: true` proceeds anyway, exactly as it does for the age band, so **nothing a caller
could do before this ceiling existed is now impossible** — but a caller that asked for a
long span and used to get a world back now gets a report unless it says `commit`. That is
a contract change and it is stated here rather than only in the code.

The ceiling is **per request**, so chunking is the other way past it and reaches the same
world: a thousand years refused whole is two five-hundred-year calls permitted, and the
determinism contract above is what makes those identical. The ceiling decides whether a
span runs, never *what* runs inside it — a guard that quietly ran less than it was asked
for would re-introduce the band-selects-cadences data loss `terrain_time_schedule`
documents at length.

The ceiling is counted **only over the steps the request will tick**. A span of whole ages
is delegated to `advance_age_request` and is not ticked, so only the remainder after those
ages is priced; pricing the ages as cadence steps would refuse every age advance for work
it never does. It is asked before the age branch runs, so a span of ages plus an
unaffordable remainder is reported whole rather than advancing its ages and then baulking.

It is an **absolute count of steps and never a share of an age**. Writing it as a fraction
of `AGE_DAYS` would re-couple the guard to the band boundary, which is the defect it
exists to fix: how much work a machine can afford does not change when the calendar is
redefined. `MAX_AGES_PER_REQUEST` is kept beside it rather than replaced by it, because
the two bound different things — one prices a tick, the other bounds a loop of whole-world
rebuilds this module does not execute itself.

### Partial failure

There is none. `advance_time_request` deep-copies the world before any pass runs, and the
copy is returned only on success. A raise anywhere — a malformed edit, an unknown
`quest_id`, a pass rejecting the world — leaves the caller holding exactly the world it
passed in. The age band commits through `advance_age_request`, which has the same shape; a
multi-age run that fails midway returns nothing, and the caller's world is untouched.

## Where it runs

Not part of generation. It runs only when a caller asks, through
`POST /world/advance-time` or `terrain_time.advance_time_request`, against a world that
generation has already finished.

It is a **new writer of blocks other capabilities own**: `encounters`, `beast_movements`,
`nomad_routes`, `nomads`, `seasonal_food` and `magic`. Those blocks were written once, at
generation or at an age boundary; after this capability exists they can be rewritten at any
moment a caller chooses. `docs/conformance/nomads.md` states this on the nomads side. The
records for encounters, beast movement and seasonal food do not exist yet and must state it
when they are written.

It is also no longer the **only** writer of `quests`. `POST /world/quest` sets `taken` and
closes an abandoned quest at any moment a session chooses, without a span and without a
clock. That route adds no key to a quest record and moves no version, so a consumer caching
on the block's shape is unaffected; a consumer caching on its *contents* between ticks is
not, because a quest's `state` can now change with no elapsed time in between. See
[actor-scale-writes](actor-scale-writes.md). The same record covers the second writer of
`heroes`, `npcs` and `villains` person records, whose `status` field a tick reads through
`liveness` on every quest sweep.

## Versions asserted

| What | Value |
|---|---|
| Request API | <!-- conformance:version time-api=1 --> |
| `world_clock` block | <!-- conformance:version world-clock=1 --> |
| `quests` block | <!-- conformance:version quests=1 --> |

**The request API stays at 1 across the work ceiling, and that is a judgement rather than
an oversight.** The ceiling is a new refusal on a path that never refused, which is a
contract change; but it arrives inside `time_advance.blocked` with `committed: false`,
which is the envelope the age band has always been able to return from this same call, so
a caller that handles the age gate already handles this. `time_advance` declares no schema
— `Contracts/schemas/operation-envelope.schema.json` carries the producing API's report as
an untyped object precisely so it can grow — no key changes meaning, and `commit: true`
reaches every world the previous version reached. Bumping `TIME_API_VERSION` would instead refuse every caller sending
`api_version: 1` — including the browser lab — to announce a field they can already see.
The alternative, a bump with a deprecation window, was rejected on that ground and is
recorded in the card so it can be reversed.

The `quests` version covers the block's **shape**, and `age_turned` adds no key and no
state: a reaped quest is `expired` like any other closed one, and the `state` vocabulary a
consumer branches on to decide what a row *is* is untouched. What changed is a value inside
`closed_reason`, which is published as an enum and is discoverable there. A consumer caching
on shape is unaffected; a consumer that switched on `closed_reason` exhaustively sees a value
it does not know, which is why the enum carries it and this record names it.

## Proven by

`Sim/tests/test_time_advance.py`, in eight classes. The pure half needs no world: the
schedule, the work counter and its ceiling, the ley composition, the closing-reason
vocabulary, the liveness predicate, claim decay, and the age band's gate and estimate. The
rest advance a generated size-17 seed-42 world. Counts are description, not invariant;
recount rather than trusting this sentence.

The load-bearing ones are `test_same_span_cut_differently_is_the_same_world`,
`test_a_year_in_four_seasons_is_a_year` and — the cut that matters most, because it crosses
a band boundary — `test_a_year_of_monthly_ticks_matches_one_yearly_tick`. Together they are the whole
determinism contract; `test_chunking_does_not_change_the_step_sequence` states the same
claim at the schedule level, where it can be checked without generating anything.
`test_an_age_span_with_a_remainder_keeps_the_remainder` carries it across the one boundary
that is not a tick, comparing one age plus thirty days against one age then thirty days by
the same byte comparison.

`LeyDriftCompositionTests` guards the half of the age length that is silent when it breaks.
It asserts the derivation directly and then runs `_ley_drift` itself for a whole age of year
steps, checking both that every individual step is inside its stated per-year bounds and
that the product of all of them is inside the age's. It is a guard against a future edit
writing the exponent as a literal, not against the current line.

`WorkCeilingTests` carries a sentinel of its own and guards it. Its rejection cases use a
span named in years rather than one derived from `MAX_TICK_STEPS` by arithmetic, because
`board/backlog/SDET-CEILING-SENTINELS.md` records three rejection tests whose sentinel was
"one above the current limit": when the limit moved, each sentinel became legal work and a
0.1 s rejection turned into a 48 s generation, with no signal but a slower suite.
`test_the_sentinel_is_still_outside_the_ceiling` asserts the precondition instead, so
raising the ceiling past a millennium fails there loudly rather than quietly ticking one
inside a rejection test. `test_the_counter_and_the_enumerator_agree` checks `work` against
`steps` itself rather than against a formula, for the same reason the age gate asks
`validate_age_world` rather than restating it.

## Why it works this way

There were seven request-shaped mutators before this one and no clock between them. Each
took a world and returned a new one, and none knew what time it was, so every consequence
of elapsed time had to be smuggled into an age boundary. `NOMAD-IRRUPTION-TRIGGER` and
`docs/beast-movement.md` both say so explicitly: a swarm that should erupt in a bad year
erupts in every year *because there are no years*.

Banding exists so that cost tracks what could actually change rather than what was asked
for. The alternative — one code path that runs everything and returns early — makes "three
seconds" and "thirty years" the same function with different arguments, and the first
time a rounding error lets a three-second call into the fate lottery, a player loses a city
to a frame of animation.

Ages had no duration before this capability. `history.ages` is a list and the age lottery
samples the founding year for its moon day, so nothing said how long an age lasts. A tick
cannot route a long span into an age advance without an answer, so `AGE_YEARS = 5000.` is
new contract rather than a discovered constant, and it is stated here because a reader
otherwise has no way to learn that the length of an age is a decision. It is a module
constant and not a control: nobody has asked for two worlds to run different age lengths,
and `history.ages` stays ordinal in the generated record.

That number is load-bearing in two places outside its own line, which is why it and the ley
bounds move together or not at all. It decides what a tick is — a century is a `LONG` tick
rather than an age advance — and the per-year ley bounds are derived from it, so an age
length changed without them drains the magic layer through ordinary ticking.

## Does not establish

**Any cost above size 33.** An age advance has now been timed directly, which it had not
been when this record was first written, but only at two small grid sizes. Measured
2026-09-21, seed 42, recipe 3, through phase 16, on a development machine shared with five
other sessions — so **wall clock is an upper bound and peak working set a lower one**, and
both are description rather than contract:

| Seed 42 | size 17 | size 33 |
|---|---|---|
| Generation | 62.4 s, 69.0 s, 71.8 s | 182.9 s, 208.8 s |
| World as JSON, with / without `build_stages` | 59.2 MB / 26.0 MB | 174.6 MB / 77.5 MB |
| **One age advance** | 34.3 s, 37.6 s, 39.4 s | 181.8 s |
| Tick, 2 years / 729 steps | 0.92 s | 3.47 s |
| Tick, 50 years / 18,057 steps | 1.15 s | 4.30 s |
| Tick, 200 years / 72,207 steps | 2.05 s | 6.47 s |
| Tick, 1,000 years / 361,007 steps | 6.15 s | 19.26 s |
| **Tick, 4,999 years / 1,804,646 steps** | 26.8 s | 79.9 s |
| Peak working set, generation, then one age advance | 378 MB, then 566 MB | trimmed; discarded |
| Private deep copy of the world | 51 MB resident, about 1 s | — |
| One step tuple in the schedule's list | 132 bytes | 132 bytes |

The tick figures are a straight line — 14.2 µs a step over a one-second copy at size 17 —
which is what `tick_cost_estimate` reports and where `MAX_TICK_STEPS` comes from. The step
cost is **not** world-independent: it is about three times larger at size 33, so both terms
of that estimate scale by cell count, which over-reports size 33 by about a fifth. Erring
that way is deliberate for a figure a caller uses to decide whether to pay.

`cost_estimate` takes size **33** as its seconds basis because an age advance grows faster
than cell count between the two points — 4.7x the time for 3.8x the cells — so the smaller
reference would under-report. Its memory basis is size **17** instead, and the mismatch is
deliberate: the size-33 peak-working-set reading came back smaller *per cell* than the
size-17 one, which is Windows trimming working sets under load from the other sessions
rather than anything about the world, so it was discarded. Nothing is measured above size
33 and everything beyond it is extrapolation.

When a world has advanced before, `cost_estimate` uses that world's own recorded
`age_advance_total` divided by the number of ages that call carried, because the recording
is a whole call's wall time and reading it raw reported a ten-age run as the price of one.
`measured` says whether **this world's own** cost was used, and not whether anything has
ever been timed.

**Whether `MAX_AGES_PER_REQUEST = 50` is the right ceiling.** The span it permits is a
quarter of a million years, and at the one measured size that is over two hours of age
advances. Decision 028 leaves the question open deliberately and this record does not
answer it: the work ceiling added beside it prices ticks, not age rebuilds.

**The quest reap belongs to this capability and not to the age boundary.** `POST
/world/advance-age` turns an age without a clock, so it has no day to close a quest on and
does not reap: a caller that turns ages through that route directly carries its board across
unchanged, including the quests whose `hook_id` the regenerated cast re-mints. Only
`advance-time`'s age band closes a board.

**A resolution cannot be carried across an age turn.** `resolutions` ride the remainder
tick, which runs after the ages, and the board the remainder sees is the new age's. A
caller that sends an age span and a resolution for a quest of the outgoing age is refused
with `unknown_field` naming the quest, which is a worse refusal than the `refused_by_world`
it would get for a quest that merely closed.

`villains` is a block whose bytes move for reasons no `world_options` records. Two module
constants, not controls, so two worlds from one seed and one option set can differ across
either change: the fallen-claim decay of decision 024, and `TIER_KEPT_PER_AGE`, the share
of its tier a region carries from one age to the next. The second is what makes
`villain_hold` reachable at all — while the ledger only ever rose, no legal value of that
option could end a reign — and it moves every world that carries a `villains` block, which
is why the block is at version 2. Both are seed-visible and deliberate.

A tick does not raise or unseat a villain, found a city, destroy one, move a border, or
rebuild any plan. It does not make quests: it moves the lifecycle of hooks the hero
generator already produced, and it does not emit difficulty. It applies a resolved hook's
declared ley effect and records every other kind without acting on it.

**A persisted world ticks, and the guard for that is at the boundary rather than here.**
`cli.py` strips `timing_ms` recursively to keep an exported world byte-reproducible, and
32 producers across 18 modules write into it by subscript, so the key has to exist before
any of them runs. `terrain_history.adopt_world` guarantees it for the six request APIs
that take a caller's world through it; this module makes its own private copy and so keeps
its own `_timing` for the same reason. Neither is a mitigation for an unfixed defect: the
contract `cli.py` asserts is that a persisted world carries no timing, and the guard
belongs where such a world re-enters. Verified 2026-09-21 by driving every `POST /world/*`
route in `tools/terrain_lab.py` against CLI-persisted seed-42 size-17 worlds at phase 13
and phase 16 — see `board/done/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md`. The producers are
deliberately **not** guarded one by one; a `setdefault` at each of the 32 would scatter
the contract across 18 modules and arm the next producer written.

No native `Core/` port exists. A world advanced in Python and one advanced natively are not
claimed to agree, because the native side has no time advance at all.
