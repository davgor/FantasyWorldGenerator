---
conformance: 1
record: settlement-records
tier: EXERCISED
summary: Places settlements on the finished raster and packs each one in local metres, with exactly one block authoritative for the buildings a settlement has and every figure it reports about people named for the axis it measures.
modules:
  - Sim/icarus_sim/terrain_settlements.py
  - Sim/icarus_sim/city_planner.py
  - Sim/icarus_sim/hamlet_planner.py
  - Sim/icarus_sim/castle_planner.py
emits:
  - path: settlements
    schema: Contracts/schemas/world-output.schema.json
  - path: roads
    schema: Contracts/schemas/world-output.schema.json
  - path: population_budget
    schema: Contracts/schemas/world-output.schema.json
  - path: city_plans
    schema: Contracts/schemas/world-output.schema.json
  - path: hamlet_plans
    schema: Contracts/schemas/world-output.schema.json
  - path: castle_plans
    schema: Contracts/schemas/world-output.schema.json
versions:
  - id: settlements
    assert: 16
  - id: population-budget
    assert: 4
  - id: city-layout
    assert: 2
  - id: city-planner
    assert: 8
  - id: hamlet-planner
    assert: 3
  - id: castle-planner
    assert: 3
proof:
  - path: Sim/tests/test_settlement_records.py
    establishes: that no settlement record makes a building-placement claim beside the plan that placed them, that the asset requirement survives that removal, that every emitted magnitude with population in its name equals the site field it copies and names its own axis, that the roster opens exactly one post per staffed worker and a plan builds a bed for each, and that a castle plot declares no bed count rather than a zero beside a placed garrison
  - path: Sim/tests/test_terrain_city_layout.py
    establishes: that a layout is deterministic, that its anchors stand on non-water land inside the profile's slope and river constraints, and that an empty candidate set produces a stated fallback rather than bypassing the constraints
  - path: Sim/tests/test_city_planner.py
    establishes: placement priority and replay, non-overlapping plots with road access, apartment densification when land runs out, that a saturated regional flood proxy does not disqualify a city while a routed river still reserves its channel and setback, that filling changes no population or layer, and that an age advance rebuilds the plans and refuses a changed planner identity
  - path: Sim/tests/test_hamlet_planner.py
    establishes: rural packing priority and replay, role-specific buildings, the support-road gate, that a coarse coastal flood proxy does not empty a hamlet, and that neighbouring hamlets keep their core plots
  - path: Sim/tests/test_castle_planner.py
    establishes: closed perimeters and walkway continuity, the gate on the approach, that castle filling is independent of city_plans, that a saturated regional flood proxy does not disqualify a castle, and that an age advance rebuilds the plans
decisions:
  - docs/decisions/023-world-compatibility-policy.md
  - docs/decisions/027-native-port-deferred-to-a-full-redo.md
tickets:
  - board/done/CONTENT-CITY-LAYOUT-DEAD-BLOCK.md
  - board/done/CONTENT-POPULATION-THREE-NUMBERS.md
---

# Conformance: settlement records

## What it produces

Where settlements stand, what each one is, and what each one is built of. `settlements`
holds one record per city, chosen by suitability over the finished raster and carrying the
ground it stands on. `roads` connects them. `population_budget` accounts for the carrying
capacity the sites are sized against. Then three independent planners pack each settlement
in local metres from that same raster: `city_plans` for cities, `hamlet_plans` for their
hinterland hamlets, `castle_plans` for route-defence fortresses.

Two questions a consumer asks of these blocks have one answer each, and both answers are
here rather than inferable: which block says what a settlement is built of, and what each
number about people counts.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `add_settlements(result, cfg)` | `terrain_settlements` | `settlements`, `roads`, `population_budget` and the per-site `city_layout` |
| `fill_cities(world)` | `city_planner` | `city_plans`, one entry per site, then the unified scene |
| `fill_hamlets(world)` | `hamlet_planner` | `hamlet_plans`, one entry per `humans.hamlets` row |
| `fill_castles(world)` | `castle_planner` | `castle_plans`, one entry per `humans.fortresses` row |
| `plan_city` / `plan_hamlet` / `plan_castle` | the three planners | one settlement's plan, for a caller holding a single site |

## Inputs it reads

The finished layer stack (`height`, `slope`, `water_type`, `river`, `rain_river`,
`flood_risk`, `moisture`, `natural_biome`, `biome_variant`, `temperature`,
`metal_richness`, the per-civilization `suitability_*` and `magic_risk_*` grids), the
civilization registry through `civilization_registry` and `terrain_profiles`, the shape
catalogue, the castle registry, `water.nodes` and the routed river segments, and
`humans.hamlets` / `humans.fortresses` for the two rural planners.

## Artifacts it writes

`settlements.sites[]`, `roads.routes[]`, `population_budget`, `city_plans`,
`hamlet_plans`, `castle_plans`, and the `world_scene` each planner rebuilds after it runs.

**`city_plans` is the only block that says which buildings a settlement has.** A city's
`settlements.sites[].city_layout` is a node-scale record: which layout profile and building
pack the city draws from, how far it stands from a routed river, which terrain nodes its
districts claim, and the assets that claim requires. It states no building placement of any
kind, and it carries no key that could be read as one. Everything a consumer needs about
placed buildings — the plot, its metre position and rotation, its footprint, its road
access, the workers it staffs and the beds it builds — is in the matching `city_plans`
entry, joined by `city_uid`.

The two are not reconcilable by arithmetic and were never meant to be. They draw from two
different catalogues (`buildings.json` building packs against the per-civilization city
preset in `civilizations.json`), at two different scales (world-raster terrain nodes against
local metres), at two different stages (9 against 16). A `placed_count` beside a plot count
is two answers to one question, and only one of them was ever the product.

**Four figures measure people, on four axes, and each names its own.**

| field | axis |
|---|---|
| `settlements.sites[].population_estimate` | the demographic estimate for a settlement's whole catchment |
| `settlements.sites[].urban_population_estimate` | the urban share of it |
| `settlements.sites[].rural_population_estimate` | the remainder; the two shares sum to the whole |
| `settlements.sites[].city_layout.population_estimate` | the same catchment estimate, copied verbatim, and it drives the district counts |
| `city_plans.cities[].stats.population_estimate` / `.urban_population_estimate` | the same two, copied verbatim onto the plan |
| `city_plans` / `hamlet_plans` `stats.worker_beds` | built capacity: beds the plan actually placed |
| `npcs.sites[].posts` | instantiated people: one post per worker the plan staffs |
| `settlements.sites[].absorbed_refugees` | people who walked in: survivor bands this city took in at an age boundary, already included in `population_estimate` |

`population_estimate` is the capacity split -- the species' allowance divided over its
cities -- **plus** `absorbed_refugees`, and it is derived afresh on every rebuild, so the
refugee term is what is carried rather than the total. On a generated world the term is
absent: refugee absorption happens at an age boundary, and the candidates it reads are
written at stage 16, after both generation-internal age transitions. See the
[nomads](nomads.md) record for what absorbs them and why nothing is founded.

The urban share is `round(population_estimate * .55)`, and the ratio between the catchment
estimate and the built capacity is **two orders of magnitude**: on seed 42 at size 17 the
largest city estimates 29,428 residents against 244 beds and 241 staffed posts. That is a
ratio, not a rounding, and it is not a defect of either number — a demographic estimate for
a catchment and the beds in a schematic city centre are different quantities. A consumer
choosing which to hold should hold the built capacity, because it is the one a runtime can
instantiate.

**A castle plan declares no sleeping capacity.** No structure in the castle registry carries
a bed count, so a castle plot carries no `beds` key: absence rather than a zero that was
never measured. `castle_plans.beds` says so in the block, and the garrison is reported as
`workers`, which `npcs` matches exactly. A consumer computing occupancy from a castle plan
has to notice the field is missing, which is the intent; a zero beside 42 placed people
reads as a shortfall and divides into a runtime error.

## Where it runs

`add_settlements` at stage 9 of a generation, and again inside every age transition.
The three planners run only at the final stage of a phase-16 generation and at the end of
an age advance. `fill_cities` does not write into `settlements`: the plan reads the site and
never the other way round, which is what keeps stage 9 reproducible without stage 16.

## Versions asserted

| what | version |
|---|---|
| `settlements` block | <!-- conformance:version settlements=16 --> |
| `settlements.sites[].city_layout` record | <!-- conformance:version city-layout=2 --> |
| `population_budget` | <!-- conformance:version population-budget=4 --> |
| `city_plans` and the city planner | <!-- conformance:version city-planner=8 --> |
| `hamlet_plans` and the hamlet planner | <!-- conformance:version hamlet-planner=3 --> |
| `castle_plans` and the castle planner | <!-- conformance:version castle-planner=3 --> |

## Proven by

`Sim/tests/test_settlement_records.py` generates one seed-42 size-17 phase-16 world and
asks it the four questions above. The three planner suites cover packing, replay and the
terrain gates; `Sim/tests/test_terrain_city_layout.py` covers the node-scale layout and its
anchor constraints.

## Why it works this way

**One authority per question.** Two blocks describing the same city's buildings disagreed,
and a reader had no way to tell which was load-bearing without reading both and guessing.
The failure was worse than a mismatch: because the node-scale record reported a shortfall in
every city, a real shortfall in one would have been invisible. Removing the claim rather
than reconciling it is what makes the guarantee checkable — there is nothing left to drift.

**Absence over a zero that was never measured.** The castle case and the `city_layout` case
are the same discipline the river split took: a consumer that reads a removed field gets a
`KeyError` at the line that made the wrong assumption, rather than a plausible number and a
wrong world.

## Does not establish

- **That the node-scale district plan finds anchors.** It does not, at any size this
  repository generates. `_collect_land_anchor_candidates` walks a band of
  `max(180, 4 * river_buffer_m + 180)` **metres**, and the raster it walks has cells
  kilometres across, so the search never leaves the city's own node: on seed 42 at size 17
  every city reports 0 or 1 district anchors against a target of 24 to 43, and
  `required_asset_count` is 0 for all twelve. That is a member of the
  [SCALE-METRE-CONSTANTS-COLLAPSE](../../board/backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md)
  class — a constant in absolute metres authored for an 11 km world — and it is that card's
  to fix, not this record's to describe as working.
- **That the catchment estimate and the built capacity should converge.** They do not, and
  nothing here argues they should. A plan that housed 29,428 people would be a different
  product.
- **That `settlement_candidates[].population_estimate` shares this vocabulary.** It is a
  nomad band's headcount — 227 people, not a catchment estimate — under the same field name,
  and it belongs to the [nomads](nomads.md) record rather than this one.
- **That `key_location_plans` shares it either.** Its plots carry the same `beds: 0` a
  castle plot used to, written at `Sim/key_locations/core/exterior.py:178`.
- **Nothing about the native port.** `Core/` is frozen at planner 6/1/2 against Python's
  8/3/3 under [027](../decisions/027-native-port-deferred-to-a-full-redo.md), which rules
  that divergence is not a defect and is not tracked.
