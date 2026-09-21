# NOMAD-IRRUPTION-TRIGGER - swarms that erupt in bad years, not every year

**Delivered 2026-09-21.** The blocker named below had already cleared:
`board/done/TIME-ADVANCE.md`.

## Observed behavior

An irruptive creature is one that is normally sparse and occasionally overwhelming. The
locust pattern: the solitary phase is the normal state, and gregarious swarming is a
response to violent environmental fluctuation, forming in marginal ground and marching when
local resources deplete.

Today every irruptive group is present in every year, because **there are no years**. The
class carries the right route shape - one march out of marginal ground toward the best
forage in reach - but no condition in time deciding whether it happens at all.

## Premise, re-measured before implementing

**Half of it was stale, and it is the half the card was blocked on.** "There are no years"
was true when this was written and is not true now: `TIME-ADVANCE` landed, `world_clock`
carries an authoritative absolute day, and `terrain_time` already runs this very pass on a
monthly cadence keyed on the absolute step index.

The behavioural half reproduces exactly. Seed 42, phase 16:

| world | irruptive groups | marching |
|---|---|---|
| size 17 | 90 | **90 of 90** |
| size 33 | 352 | 339 of 352 (the other 13 had no reachable target) |

Every group that *could* march did, in whatever year the world was standing in, because
nothing read the clock. The same measurement through the new test, with the trigger ablated
back to version-1 behaviour: `AssertionError: 90 not greater than 90 : the same swarms march
in a lean year and a fat one, so the year is not deciding anything`.

## What was built

`Sim/icarus_sim/terrain_beast_movement.py`. Two conditions, and neither on its own is
enough — which is what separates this from a flat probability with a calendar bolted on:

- **The year.** `year_forage_factor(result, year)` scales this year's forage against an
  ordinary one, 0.55 to 1.25. **One draw for the whole world.** A per-group draw would make
  "a bad year" mean nothing: swarms would be independent coin flips that happened to be
  indexed by year.
- **The ground.** The group's own cell against the mean forage of everything a march can
  reach. Marginal ground is ground that falls short of its *neighbourhood* — a swarm forms
  where conditions turn, not where they were always poor — and an absolute forage floor
  would mean a different thing in every biome.

A group that does not clear the bar carries the new `route_status: "solitary"` and keeps one
base camp, so the encounter index still places it: a player can meet the solitary phase,
just not a swarm on the march. `stranded` keeps its old and different meaning — no reachable
ground to march to at all — rather than being made to carry both facts.

### The trap, and why the seed is where it is

`terrain_time` hands every cadence `replace(cfg, seed=child_seed(cfg.seed, 'time-<name>',
index))`, and this pass runs on a **monthly** cadence. A year factor drawn from `cfg.seed`
would therefore be a different number in every month of the same year: twelve weathers
inside one year, and swarms that formed and dissolved with the call rather than with the
world. The factor is keyed on `result['config']['seed']` — the genesis seed, which the
stepping does not touch — and the absolute year. `test_the_year_survives_the_tick_that_asks_about_it`
pins it, and goes red when the factor is made to re-roll per call.

### Calibration, with its measurement

`IRRUPTION_MARGIN = 0.18`, and it is well below one because of the distribution it sits in.
An irruptive species is *already* placed on marginal ground by the nest pass, so
`forage(start) / mean(forage within a march)` runs 0.08 at the tenth percentile to 1.14 at
the maximum, median 0.30, over the 90 irruptive groups of seed 42 at size 17. At 0.18:

| | leanest year of a century | ordinary year | fattest year |
|---|---|---|---|
| size 17 | 59% march | 28% | 20% |
| size 33 | 42% march | 28% | 24% |

So the solitary phase stays the normal state and a bad year roughly doubles the swarms, at
both rasters. The first value tried, 0.85, left nearly every group marching in every year —
the behaviour this card exists to remove.

## Contract

`beast_movements` moves 1 → 2 and `Contracts/schemas/beast-movements.schema.json` with it:
`route_status` gains `solitary`, and the block gains `solitary`, `year` and
`year_forage_factor` as required fields. The version had to move: under v1 a consumer could
read the block as a fixed roster of swarms and cache it against the world's identity, and it
is now a function of the year. `routed + stranded + solitary` accounts for every group.

A new binding `beast-movements` was added to `docs/conformance/version-bindings.json`,
claiming `docs/beast-movement.md`, which carries the marker.

**No conformance record was changed, and the reason is that none claims this module.**
`terrain_beast_movement.py` is on the `uncovered` list in
`docs/conformance/coverage.json` under `board/in-progress/CONFORMANCE-DOCS.md`, and
`docs/conformance/nomads.md` says in as many words that `beast_movements` and `encounters`
are not owned there. Writing a record for it belongs to that ticket, not to this one.

## Proof

New module `Sim/tests/test_beast_movements.py`. Every test was ablated and watched go red;
see the delivery report for the matrix.

## Known imprecision, for the orchestrator

On a tick the year is read from `world_clock` as it stands when the pass runs, and
`advance_time_request` writes the advanced clock *after* its cadence loop. So a span
crossing several years builds this block for the year the span started in — measured at year
5250 against a clock that ended at 5252 on a two-year advance. Generation, the age path and
any span not crossing a year boundary are exact.

It is stated in the module, in `docs/beast-movement.md` and in the block's own `limits`
rather than quietly fixed, because closing it means handing each cadence step its own day —
a change to `Sim/icarus_sim/terrain_time.py`, which is another session's file tonight.

## Not built

`seasonal_environment` supplies twelve climatological months that are identical in every
year, so there is no modelled weather for a year to depart from and the factor stands in for
one. The card proposed reading `terrain_seasons.seasonal_harvest` for the growth curve; that
was not used, because a curve which is the same in every year cannot distinguish one year
from another and reading it would have dressed the draw up as a simulation. Real
inter-annual variation is separate work and would slot in behind `year_forage_factor`
without changing the shape of the trigger.

## Files

`Sim/icarus_sim/terrain_beast_movement.py`, `Contracts/schemas/beast-movements.schema.json`,
`docs/beast-movement.md`, `docs/conformance/version-bindings.json`,
`Sim/tests/test_beast_movements.py` (new), `tests/test_world_schema_conformance.py`.

Changes generated output, so `Fixtures/sample-world-v1.json` is stale and the orchestrator
rebuilds it.
