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
    establishes: chunk independence of the step schedule and of a real advanced world including a cut across a band boundary, coalescing of wholesale passes and dependency order between them, that the age band ticks its remainder and caps its ages, the refusal envelope over a sample of malformed requests and on the reported age gate, that the instant band moves nothing seeded, the liveness predicate over every vocabulary including the block/person status collision, claim decay and its floor, the age band's estimate and its reported gate, quest opening, expiry and resolution, and that the caller's world is never mutated
decisions:
  - docs/decisions/024-fallen-claim-decay.md
tickets:
  - board/backlog/TIME-ADVANCE.md
  - board/backlog/TIME-LIVENESS.md
  - board/backlog/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md
  - board/backlog/NOMAD-IRRUPTION-TRIGGER.md
---

# Conformance: time advance

## What it produces

A world advanced to a later moment. The caller names an elapsed span in seconds, days or
years; the span selects a band; the band decides which cadences may run. A tick moves the
living layer — quests, encounters, beast movements, nomad routes and bands, seasonal food,
the ley base field and the lunar surge — over ground that does not move. A span of one age
or longer is not a tick at all: it is answered with a cost estimate and, on request, a
delegated age advancement.

The world carries a `world_clock` from the first call onward, and it is the authoritative
now that the other runtime mutators previously had to infer.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `advance_time_request(body)` | `terrain_time` | Time API 1. World in, new world out. `POST /world/advance-time`. |
| `clock(world)` | `terrain_time` | This world's `world_clock`, derived from the founding year for a world generated before the clock existed. |
| `cost_estimate(world, ages)` | `terrain_time` | What an age advance would cost, with its basis and whether it was measured. |
| `age_gate(world)` | `terrain_time` | Why this world cannot advance an age, or `None`. |
| `schedule.steps(now, days)` | `terrain_time_schedule` | The ordered `(day, cadence, index)` steps inside a span. Pure. |
| `schedule.plan(now, days)` | `terrain_time_schedule` | What a span would do, without doing it. |
| `schedule.band(days)` / `elapsed_days(spec)` | `terrain_time_schedule` | Band selection and unit conversion. |
| `liveness(record, block)` | `terrain_liveness` | `present` or `gone` for one person, across four blocks that disagree on the words. |
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
to the quest generator.

States this capability writes: `offered`, `expired`, and the three a caller resolves —
`completed`, `failed`, `abandoned`. It also *honours* `taken`, which stops a quest expiring
on its offer window, but **no request field sets it**: a game that has accepted a quest for
its player writes that state into the document it persists. The absence of an accept channel
is a gap, not a design; see the behaviour contract's limitations.

A quest whose hook disappears — which an age transition causes wholesale, because `heroes`
is regenerated — is closed with `closed_reason: 'hook_gone'` rather than left open. The
reaper walks the union of hooks and tracked quests for that reason; walking hooks alone left
an immortal offer for every hook that vanished, and the block grew without bound.

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
  remainder, so `advance(150y)` equals `advance(100y)` then `advance(50y)`, and the
  operation log never claims an elapsed the clock did not move.
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
  (`0.65 ** 0.01`, `1.35 ** 0.01`). They are not a tuned pair and must not be rounded to
  friendlier numbers: the point is that a hundred year-steps compose to the age's own band.
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

The age gate is the one refusal that is **reported rather than raised**. A caller asking
for five thousand years deserves the estimate and the reason together, and an exception
throws away the more useful half. It carries the same envelope as a document under
`time_advance.blocked`, shaped as `refused_by_world`: the request was well formed and the
world is the constraint. A caller unable to tell that from a malformed argument would
shorten a span that was never wrong.

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

## Versions asserted

| What | Value |
|---|---|
| Request API | <!-- conformance:version time-api=1 --> |
| `world_clock` block | <!-- conformance:version world-clock=1 --> |
| `quests` block | <!-- conformance:version quests=1 --> |

## Proven by

`Sim/tests/test_time_advance.py`, 44 test methods in five classes. Twenty are pure and
need no world: the schedule, the liveness predicate, claim decay, and the age band's gate
and estimate. Twenty-four advance a generated size-17 seed-42 world. Counts are description,
not invariant; recount rather than trusting this sentence.

The load-bearing ones are `test_same_span_cut_differently_is_the_same_world`,
`test_a_year_in_four_seasons_is_a_year` and — the cut that matters most, because it crosses
a band boundary — `test_a_year_of_monthly_ticks_matches_one_yearly_tick`. Together they are the whole
determinism contract; `test_chunking_does_not_change_the_step_sequence` states the same
claim at the schedule level, where it can be checked without generating anything.

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
cannot route a long span into an age advance without an answer, so `AGE_YEARS = 100` is new
contract rather than a discovered constant, and it is stated here because a reader
otherwise has no way to learn that a century is a decision.

## Does not establish

An age advance has never been timed directly, at any size. When a world has not advanced
before, `cost_estimate` extrapolates from *generation* cost at sizes 129 and 257 and reports
`measured: false`; when it has, it divides that world's recorded `age_advance_total` by the
number of ages that call carried, because the recording is a whole call's wall time and
reading it raw reported a ten-age run as the price of one.

`villains` is now a block whose bytes move for a reason no `world_options` records: the
fallen-claim decay of decision 024 is a module constant, not a control, so two worlds from
one seed and one option set can differ across that change. It is seed-visible and
deliberate; see the decision.

A tick does not raise or unseat a villain, found a city, destroy one, move a border, or
rebuild any plan. It does not make quests: it moves the lifecycle of hooks the hero
generator already produced, and it does not emit difficulty. It applies a resolved hook's
declared ley effect and records every other kind without acting on it.

`timing_ms` is repaired locally — `_timing` makes the key present so a CLI-persisted world
can tick at all — and that is a mitigation, not the fix. Other writers into `timing_ms`
remain unguarded and `board/backlog/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md` still owns the
contract question.

No native `Core/` port exists. A world advanced in Python and one advanced natively are not
claimed to agree, because the native side has no time advance at all.
