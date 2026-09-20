# TIME-ADVANCE - the clock the runtime APIs already assume

Owner: local. State: **delivered** 2026-09-20. Scoped 2026-09-19 with the agent
coordinator and the conformance session; built, tested and documented the following day.
See `docs/conformance/time-advance.md` for what it now does and
`docs/time-advance.md` for the behaviour contract.

## Requested behavior

Once a world is live, advance the simulation by an arbitrary elapsed time supplied by the
caller - three seconds, thirty years, or five thousand - and return the advanced world. It
advances quests, recomputes leylines, and drives the living layer after the game begins.
A request long enough to be an epoch is answered with an age advancement rather than a
tick.

## Why this is infrastructure and not a feature

There are seven request-shaped mutators today and no clock between them:
`advance_age_request` (`terrain_history.py`), `corruption_request` and
`cleanse_request` (`terrain_corruption.py`), `visitation_request`
(`terrain_visitation.py`), `nomad_request` (`terrain_nomad_api.py`),
`lunar_request` (`terrain_astrology.py`) and `patch_request`. Each takes a world
document and returns a new one; none of them knows what time it is. Two places in the
repository already say the gap out loud: `NOMAD-IRRUPTION-TRIGGER.md` names this work as
its dependency, and `docs/beast-movement.md` says a swarm that should erupt in a bad
year erupts every year "because there are no years yet".

## Proposed mechanism

`POST /world/advance-time` -> `terrain_time.advance_time_request(body)`, time API 1,
stateless in the same shape as the other seven: world in, new world out, caller persists,
`history.operations` records the call.

A new `world_clock` block `{day, age, epoch_day, version}` is the authoritative mutable
now. The world has no such thing today - time is implicit in `founding.end_year` plus the
length of `history.ages` - which is precisely why nothing can tick. Time already has a
canonical form to adopt: real days since founding year 0, 360-day years
(`docs/astrology.md`).

### Bands

Elapsed time selects a band, so cost tracks what could actually change. Three seconds must
be structurally incapable of killing a city; the band table is how that is guaranteed
rather than hoped.

| Band | Span | What runs | Target |
|---|---|---|---|
| Instant | < 1 day | clock plus closed-form lunar and surge recompute; nothing seeded moves | < 5 ms |
| Day | 1 day to a season | quest clocks, encounters, beast movement, nomad route positions, lunar events that pass | < 50 ms |
| Season | season to ~2 years | the above plus seasonal food, population, nomad reclassification, villain outlook, fractional ley drift | < 1 s |
| Long | years to less than one age | repeated year steps with the expensive rebuilds deferred and coalesced to the end of the call | seconds |
| Age | one age length or more | delegates to `advance_age_request`; see the size gate below | blocked |

The coalescing in the Long band is the trick `advance_age_request` already uses at
`age == start_age + steps`, where the planners, heroes, story web, NPCs and key locations
run once rather than per step.

### The binding invariant

**The RNG domain is keyed by simulated time, never by tick ordinal or call count.**

Every stochastic sub-step has a cadence and draws from
`child_seed(cfg.seed, '<subsystem>', absolute_step_index)`. A call for elapsed E executes
exactly the step indices falling in `(now, now + E]`, in a pinned subsystem order. No draw
is ever made per call. Chunking is therefore structurally irrelevant rather than
tested-and-hoped: `2 x 15y` and `1 x 30y` produce identical bytes.

Write that test first, before the feature. It is the whole contract in one assertion, and
the failure mode it guards against - a seed derived from tick ordinal - is invisible until
someone chunks differently. Float addition is not associative and city identity is
compared at zero tolerance downstream, so a quantity summed in two chunks differing in the
last ulp propagates into a different city set.

The Long band's deferred rebuilds are the one place chunk-independence could still die.
They are safe only if the deferred passes are pure functions of the state they read; that
needs its own test rather than an assumption.

### Leylines are three things

Conflating them is the trap:

- `surged_strength` is a closed form of the day. Free. Runs in every band including
  Instant.
- Base `intensity` drift is today a per-age `uniform(.65, 1.35)` random walk
  (`terrain_history.py`, the age-ley step). It needs a per-year fractional form that
  composes to the same distribution over an age, keyed on absolute year index.
- `evaluate_networks` (`terrain_leyline_history.py`) is the expensive globe pass. Run
  it at most once per request, and only when base intensities actually moved.

The performance session has pre-registered `evaluate_networks` as an optimisation target.
This work is its consumer, not its competitor.

Player `leyline_edits` already exist on the age API through `edit_network`. Advance-time
takes them in the same shape, applied before the step.

### Quests

The tick owns quest *lifecycle* - offered, taken, expired, resolved - and the world-side
consequences of resolution. The game reports what the player did through a `resolutions`
input; the world never decides a player outcome. It consumes whatever the quest contract
lands (anchor, verb, difficulty 1-5, with the game pricing rewards) rather than inventing
a second model. `heroes.quest_hooks[]` and the NPC verb earmark are the substrate.

### Failure is all-or-nothing

The request returns a new world or raises. It never returns a half-advanced one. The
existing stateless world-in/world-out shape makes that guarantee nearly free, and it is
expensive to retrofit once anything mutates in place.

## Dependencies and unresolved decisions

- **The size gate is the headline feature's blocker.** `terrain_history.py` refuses age
  advancement above grid 257, and the user wants 513 and age-able. The Age band routes
  straight through it. Recorded costs: 11 s / 30 MB at 129, 42 s / 116 MB at 257,
  extrapolating to roughly 167 s / 462 MB at 513 - for *generation*. Age advance at 513 has
  never been measured and that measurement is the open ask on the performance session.
  Lifting the gate is a public-contract change and is not in this card's scope.
- **Therefore: bounded "advance N ages", returning a cost estimate before committing.**
  This is a design position, not a contingency. A caller asking for five thousand years has
  no idea whether that is a second or an hour, and telling them turns the gate from a wall
  into information whichever way the size question is ruled.
- **`FALLEN_CLAIM_INFLUENCE` is this card's to settle.** `terrain_villains.py` is set to
  `1.` and its comment says so explicitly: the value is unargued, it exists so that
  retention was the only change in the fall pair, and the decay is owned by whoever settles
  the tick cadence. Over long spans an undecayed claim means the world places by who *ever*
  held power rather than who holds it. Decide whether decay is one step at the fall or
  continues per age; the latter is a tick question.
- **Retention is "keep everything, revisit later".** That survives a long span: a live game
  world carries no `build_stages` (`generate_history` builds them, `cli.py` drops
  them unless asked, and the age API only appends when they are already present), so growth
  is per-destroyed-city and per-person records, not per-cell snapshots. Note in passing that
  a destroyed city is stored twice, in `ruins` and again as a deep copy in
  `history.ages[].events`; fine at today's volumes, worth watching if retention widens.
- **`TIME-LIVENESS`** supplies the single "is this still here" predicate a long span needs.
- **ML-03** matters only for native parity: seed-changing Python needs a `Core/` port in the
  same change.

## Files and assets in scope

New modules only. `terrain_history.py` is not edited - the Age band reaches
`advance_age_request` by calling it.

- `Sim/icarus_sim/terrain_time_schedule.py` - pure: given now, elapsed and the cadence
  table, return the ordered list of steps to run. No world access.
- `Sim/icarus_sim/terrain_time.py` - glue: validation, request handling, snapshotting,
  operation record.
- `tools/terrain_lab.py` - a `/world/advance-time` route beside the existing five.
- `docs/time-advance.md` - canonical behavior contract.
- `docs/conformance/time-advance.md` - its own record, claiming only the new modules.
- `docs/decisions/` - one decision doc for the chunk-independence invariant. Not
  `Contracts/kernel-v1.md`; that is the bounded counter kernel's boundary and must not be
  widened.

## Documentation impact

The record claims the new modules and nothing else, so there is no claim contest.

**The tick also edits the records that own every block it re-rolls**, in the same change,
under `docs/conformance/README.md:88` ("Widening a record you do not own"). Adding a new
writer to someone else's block is a capability change from that record's side even though
no version moves and none of its modules change: `## Where it runs` is a claim about when a
block is *stable*, and a consumer reads it as licence to cache. `encounters` is written in
two places today, both at generation; after the tick it can be re-rolled at any later
moment, and nothing in the old record would warn them. Version markers stay untouched.

Add a version binding for `world_clock` and the time API integer. Do not add a second
binding for a version merely moved - one authoritative site per integer, and a
`VERSION-AMBIGUOUS` report is resolved by naming the authoritative site rather than
suppressed.

The record needs two sections a producing record does not: which blocks are read-only to
the tick, and what a partial failure leaves behind.

## Adversarial review and limitations

- Record the `-0.0` incidental as a named load-bearing fact, not only a code comment. A
  school with no nodes and no edges sums to integer zero and `strength * -math.expm1(-0)`
  yields negative zero, which serialises with its sign. The Instant band recomputes surged
  strength on every call, so this path is hit far more often by a tick than by generation,
  which touches it once per world.
- Cost figures in any record are description, not invariant, and must state seed, world
  size and machine.
- Determinism, replay identity, draw and iteration order, byte reproducibility and id
  stability across ages are invariants and bind other sessions' work.
- Ids renumber across age boundaries. A tick crossing an age boundary must not hand a
  caller an id minted before it; anything the tick returns that outlives a boundary keys on
  the terrain node and spells the anchor out.

## Delivered

- `terrain_time_schedule.py` (pure: bands, cadences, absolute step indices, coalescing) and
  `terrain_time.py` (glue: validation, quests, ley drift, the age route, the operation
  record). `terrain_history.py` is unedited; the age band calls `advance_age_request`.
- All five bands. The instant band returns in **0.5 ms** on a size-33 world because it
  copies four keys rather than deep-copying the world; a full copy cost 1917 ms and grows
  with the square of the grid, which would have made the band's whole premise a fiction.
- The age band reports rather than raises: a cost estimate with its basis and a `measured`
  flag, plus `commit` to actually advance in chunks of ten. Above size 257 it returns the
  estimate and a `blocked` reason. The gate itself is untouched.
- `world_clock`, `quests` (lifecycle only, no difficulty), `time_advance`, and a
  `history.operations` row per call. `POST /world/advance-time` in the lab, with a
  provenance revision row.
- `terrain_liveness.py` per `TIME-LIVENESS.md`.
- `FALLEN_CLAIM_INFLUENCE` settled at .6 with per-age decay to a .05 floor; decision 024.
  Seed-visible.

**Two defects found in my own work by the tests, not by reasoning.** `add_seasonal_food`
appends to the shared `warnings` list, so it is not the wholesale replacement the rest of
its body is and a span differed by how many calls it was cut into; `_dedupe_warnings` now
runs after each coalesced pass. And the first implementation ran every crossing, so thirty
years rebuilt the encounter index 360 times - `COALESCED` reduced 12,090 steps to 10,836,
of which all but 36 are the cheap daily quest sweep.

## Audit, and what it found

A six-lens adversarial audit was run over the delivered work after it was first called
complete, each finding put to an independent refuter. **Thirty-seven findings survived
refutation, three of them blocking.** They are recorded here because a card that says only
what was built is a worse record than one that says what was wrong with it.

**Two blocking findings shared one root and falsified the central invariant.** `steps()`
chose which cadences may run from `BAND_CADENCES[band(days)]` -- the band of *this call*.
Because the window is half-open at the start, a crossing skipped because one call was short
was never revisited by any later call. A game ticking a month at a time never ran ley
drift, nomad reclassification, seasonal food or the villain outlook once; a game ticking by
the second advanced nothing but its clock. The band no longer filters: a span runs the
cadence boundaries inside it and nothing else. Every chunk test had stayed inside one band,
so all thirty-eight passed while the invariant was false.

**Third blocking:** the age band floored the span to whole ages, dropped the remainder, and
still reported the requested elapsed -- so `advance(150y)` differed from `advance(100y)`
then `advance(50y)`, and the operation log described a move the clock never made. The
remainder is now ticked, and `leyline_edits` and `resolutions` ride it rather than being
validated and discarded.

**The size gate was built on a stale premise from this card.** The dependency section below
still says 257 because that is what it said when the work was scoped. The ceiling had
already been raised to **1025** in commit `4713f9a`, and `validate_age_world` contains no
`257` at all. `age_gate` hard-coded one anyway, attributed it to that function, and refused
every world from 258 to 1025 a span it would have advanced -- with `retry: false`, pointing
at a gate containing no such rule. Two tests asserted the wrong behaviour as correct.
`age_gate` now calls the real predicate instead of restating it, and a test fails if any
grid ceiling is written into this module's executable code again.

Others fixed: the tick re-rolled `nomads` but never re-applied `apply_nomad_effects`,
deleting `nomads.effects` and stranding the previous population's write-backs; the quest
reaper walked hooks rather than quests, so every hook an age transition destroyed left an
immortal offer and the block grew without bound; a resolution moving a ley node never set
`ley_touched`, leaving every derived magic field stale; `ley_touched` was set even when a
magicless world drifted nothing, which then died in `evaluate_networks` on a bare KeyError;
`cost_estimate` reported a whole multi-age wall time as the per-age price; no ceiling on
requested ages; the instant band appended an operation per call for a span in which nothing
happened; a nest quest's anchor was always null; `world_clock` and `quests` were missing
from `STATE_KEYS` and the lab's list, so a ticked world showed its final quest state at
every earlier stage; and decision 024 claimed a `key_locations` placement change that
cannot happen, `influence` having exactly one consumer.

## Acceptance and evidence

- `Sim/tests/test_time_advance.py`: **45 tests**, all passing, ~263 s. Twenty need no world.
- The contract tests are `test_same_span_cut_differently_is_the_same_world`,
  `test_a_year_in_four_seasons_is_a_year`, and -- the cut that matters most, because it
  crosses a band boundary and is the one the blocking defect hid behind --
  `test_a_year_of_monthly_ticks_matches_one_yearly_tick`.
- `test_super_villains` 24 passed; `test_terrain_nomads`, `test_cult_leyline_writes` and
  `test_terrain_history` 52 passed together after the nomad-effects and STATE_KEYS changes.
- `python tools/validate_repo.py --stage checks` passes end to end.
- `python tools/docs_check.py`: 202 documents, 128 modules claimed.
- `python tools/verify_provenance.py`: 79 files.
- Measured at size 33, seed 42: instant **0.5 ms** (a four-key copy, not a full deep copy --
  a full copy cost 1917 ms and grows with the square of the grid), 30 days 2.6 s, 1 year
  2.7 s, 30 years 3.0 s, 5000 years 4.1 s as an uncommitted estimate.

## Still open

- An age advance has never been timed directly at any size, so an estimate for a world that
  has not advanced before extrapolates from *generation* cost.
- There is no request field meaning "the player accepted this quest". The `taken` state is
  honoured if a caller writes it into the document it persists, but nothing sets it.
- No native `Core/` port; a natively advanced world is not claimed to agree.
- The day band and above still pay a full deep copy of the world. The instant band shows
  the shape of the fix if that cost ever matters.
- `SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE.md` records the seven passes that append to
  `warnings`; four are reached by `advance_age_request` on every call, which is pre-existing
  and unrelated to this work.

## Handoff

Delivered, audited, and repaired; see the three sections above. The dependency section
above is left as written at scoping time, including its stale 257 premise, because it is
the record of what was believed then and the audit section says what that cost.

Next concrete action for whoever picks this up: `NOMAD-IRRUPTION-TRIGGER.md` is now
unblocked -- the year boundary it waited for is `world_clock.day` and the absolute year
index. Before building on the age band, note that nobody has timed an age advance, and the
1025 ceiling means a size-513 world is now advanceable where this card assumed it was not.

Verification is centralised on the agent coordinator - request runs rather than running
suites directly. Hand board index lines to the coordinator rather than editing
`board/README.md`.
