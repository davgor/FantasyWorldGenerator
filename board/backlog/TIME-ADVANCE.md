# TIME-ADVANCE - the clock the runtime APIs already assume

Owner: unassigned. State: scoped, not started. Planned 2026-09-19 with the agent
coordinator and the conformance session; no code written.

## Requested behavior

Once a world is live, advance the simulation by an arbitrary elapsed time supplied by the
caller - three seconds, thirty years, or five thousand - and return the advanced world. It
advances quests, recomputes leylines, and drives the living layer after the game begins.
A request long enough to be an epoch is answered with an age advancement rather than a
tick.

## Why this is infrastructure and not a feature

There are seven request-shaped mutators today and no clock between them:
`advance_age_request` (`terrain_history.py:714`), `corruption_request` and
`cleanse_request` (`terrain_corruption.py`), `visitation_request`
(`terrain_visitation.py:395`), `nomad_request` (`terrain_nomad_api.py:57`),
`lunar_request` (`terrain_astrology.py:200`) and `patch_request`. Each takes a world
document and returns a new one; none of them knows what time it is. Two places in the
repository already say the gap out loud: `NOMAD-IRRUPTION-TRIGGER.md` names this work as
its dependency, and `docs/beast-movement.md:89` says a swarm that should erupt in a bad
year erupts every year "because there are no years yet".

## Proposed mechanism

`POST /world/advance-time` -> `terrain_time.advance_time_request(body)`, time API 1,
stateless in the same shape as the other seven: world in, new world out, caller persists,
`history.operations` records the call.

A new `world_clock` block `{day, age, epoch_day, version}` is the authoritative mutable
now. The world has no such thing today - time is implicit in `founding.end_year` plus the
length of `history.ages` - which is precisely why nothing can tick. Time already has a
canonical form to adopt: real days since founding year 0, 360-day years
(`docs/astrology.md:18`).

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
- `evaluate_networks` (`terrain_leyline_history.py:261`) is the expensive globe pass. Run
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

- **The size gate is the headline feature's blocker.** `terrain_history.py:586` refuses age
  advancement above grid 257, and the user wants 513 and age-able. The Age band routes
  straight through it. Recorded costs: 11 s / 30 MB at 129, 42 s / 116 MB at 257,
  extrapolating to roughly 167 s / 462 MB at 513 - for *generation*. Age advance at 513 has
  never been measured and that measurement is the open ask on the performance session.
  Lifting the gate is a public-contract change and is not in this card's scope.
- **Therefore: bounded "advance N ages", returning a cost estimate before committing.**
  This is a design position, not a contingency. A caller asking for five thousand years has
  no idea whether that is a second or an hour, and telling them turns the gate from a wall
  into information whichever way the size question is ruled.
- **`FALLEN_CLAIM_INFLUENCE` is this card's to settle.** `terrain_villains.py:37` is set to
  `1.` and its comment says so explicitly: the value is unargued, it exists so that
  retention was the only change in the fall pair, and the decay is owned by whoever settles
  the tick cadence. Over long spans an undecayed claim means the world places by who *ever*
  held power rather than who holds it. Decide whether decay is one step at the fall or
  continues per age; the latter is a tick question.
- **Retention is "keep everything, revisit later".** That survives a long span: a live game
  world carries no `build_stages` (`generate_history:566` builds them, `cli.py:44` drops
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

## Handoff

Nothing is implemented. First three actions, in order: write the `1 x 30y` versus `2 x 15y`
byte-equality test; define the cadence table in `terrain_time_schedule.py` against it; then
build the Instant and Day bands, which need no rebuild machinery at all.

Verification is centralised on the agent coordinator - request runs rather than running
suites directly. Hand board index lines to the coordinator rather than editing
`board/README.md`.
