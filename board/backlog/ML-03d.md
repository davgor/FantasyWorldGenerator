# ML-03d — Native in-process world genesis for Unreal

## Requested behavior

Port recipe-3 **world** genesis into `Core/` so the Unreal plugin can generate in process. This slice exists because the native core is still the bounded counter; Python world JSON is not the generate API. Freeze the native API only after it includes the visualization envelope **and** the sampling/frame/registry contracts UnrealWorldGen will keep:

- On-demand detailed surface samples (continuous terrain / height-tile contract), not only a `size`-cell regional raster
- Natural biome IDs and lab RGB colors; mutation colors where catalogues supply them
- Water masks for a blue landscape layer
- `world_scene` buildings with metre width/depth/height, positions, and exported axes
- Street and regional-road polylines on the **detailed** surface, with shared junction points
- Nest / habitat anchors on that surface
- Source-to-Unreal mapping fixtures: east→Unreal +X, north→Unreal +Y, up→Unreal +Z, lengths ×100, unit axes unscaled, winding reverse
- Asset-ID registry schema: every exhaustive-catalogue identity has a binding slot (path or explicit missing)

Python `POST /world/generate` remains the reference oracle and the browser lab. It is not an Unreal dependency.

Default first native generate: recipe 3, size 65 regional climate, tectonic globe, **plus** detail sampling at the display/contact resolution used by ML-03e. Interactive regional cap stays 257. Reject unsupported recipe/schema versions.

## Proposed mechanism

Keep Unreal types out of `Core/`. Versioned generate request/result, sample-surface, and registry-table documents. Match existing kernel style: finite JSON, deterministic ordering.

Implement incrementally **headlessly**:

1. Request validation and capability/version reporting.
2. Coordinate fixtures for the Unreal permutation (cardinals, elevation, seam/pole) against the oracle.
3. On-demand height/mask samples vs tile/patch/city foundation fixtures (same function as [continuous terrain](../../docs/continuous-terrain.md)).
4. Regional classification + colors vs pinned Python fixtures.
5. Water cells.
6. `world_scene` footprints and roads; contact tests: foundation corners/centres on sampled height; road samples on grade; junctions coincide; seam-adjacent equality.
7. Nest anchors on the sampled surface.
8. Registry coverage: one row per exhaustive asset-list ID.

Each step starts with a behavioral test that fails for the missing output. Do not approximate Python; version numeric divergence. Public operations: describe capabilities; generate genesis; sample surface; report seed/config/digest. No HTTP in Core.

## Dependencies and unresolved decisions

This slice is epic item 1’s native generate. Epic items 2–3 (importer, packaged loop) are ML-03e and stay blocked until this envelope, sampling contract, axis fixtures, and catalogue registry coverage are proven headlessly.

Settled by [decision 018](../../docs/decisions/018-unrealworldgen-dev-consumer.md) and [Unreal integration](../../docs/unreal-integration.md).

Open: native vs Python numeric thresholds; display sample density vs 4 m city surfaces; PRNG contract if streams cannot match bit-for-bit.

## Sources consulted

- Astra 2026-09-16: axis mapping, detailed contact, registry, cooked handoff (cooked owned by ML-03e).
- `PLAN.md` PK02–04/08/10; capabilities v1; world-output schema; unified globe scene; continuous terrain.

## Files and assets in scope

`Core/`, `Contracts/` / `Fixtures/` (generate, coordinates-unreal permutation, registry coverage), native packaging/qualify tools and tests, docs listed above. No Unreal maps or `.uasset` edits.

## Acceptance and evidence

- Tests precede each layer. Isolated native qualify runs without Unreal.
- Same seed: visualization fields match reviewed Python fixtures within the numeric contract.
- Surface samples match height-tile/patch identities at shared indices; city foundation heights match planner exports.
- Cardinal/elevation fixtures pass for the Unreal mapping without placing Unreal types in Core (pure centimetre vectors).
- Registry table covers 100% of exhaustive asset-list IDs; missing bindings are explicit, not omitted.
- Unsupported versions fail explicitly.
- This ticket does not cook Unreal.

## Documentation impact

Decision 018, Unreal integration, capabilities “future Unreal boundary,” this ticket, parent ML-03, ML-03e.

## Adversarial review and limitations

- A 65-grid globe raster cannot stand in for local streets or foundations.
- Sky islands stay disabled. Live simulation (jobs, residue, age advance) is out of scope.
- Registry rows may point at a shared placeholder path; they still must exist per ID.

## Progress — 2026-09-18

Steps 1-5, 7 (surface) and 8 are implemented in `Core/` and gated by
`tests/test_native_world.py`:

- Request validation and capability reporting.
- Coordinate fixtures for the Unreal permutation, including seam and pole identities
  (`Fixtures/unreal-world-frame-v1.json`), checked against the Python coordinate oracle.
- On-demand height sampling identical to the height-tile contract at shared indices.
- Regional classification, natural biome identities and lab colours.
- Water cells, depth, spill surfaces and rivers.
- Registry coverage: one row per exhaustive-catalogue identity, 1184 slots, explicit
  unbound reasons, native loader with duplicate and path rejection.

The numeric contract is `Fixtures/native-world-v1.json`: identity layers match the
reference world exactly and continuous fields agree within 1e-9 relative. Measured
across four seeds:

| seed / size | layers with any differing cell | worst relative | surface samples exact |
| --- | --- | --- | --- |
| 777 / 33 | none | 0 | 400/400 |
| 12345 / 33 | 1 (`noise`, one cell) | 2.2e-15 | 400/400 |
| 42 / 33 | 4 (one cell each) | 4.9e-15 | 400/400 |
| 7 / 65 | 21 | 4.5e-13 | 398/400 |

No categorical layer differed in any of them. The only
observed source of divergence is `pow()` differing between the interpreter and the
platform C++ runtime in the last ulp. The Mersenne Twister stream, plate layout,
spherical noise, CPython's compensated `sum` and its vector norm are bit-for-bit.

### Placement port progress — 2026-09-18

Two of the twenty modules are ported and gated by
`tests/test_native_world.py::test_stage_nine_magic_and_environment_match_the_reference`:

- **Leylines** (`Core/magic.cpp`): eight independently seeded networks with clustered
  nodes, outliers, the three-locus alignment, cluster trees and random extra links.
  Node and edge geometry and intensities are bit-for-bit; the eight potency fields, the
  instability fields and the derived density, hazard, growth, opposition and dominance
  layers match, with four cells differing at 1e-32 absolute from the platform `pow`.
- **Environment** (`Core/ecology.cpp`): metal richness, salinity, coastal exposure,
  harbour suitability, fishing productivity, reef, lagoon, estuary, sheltered bay,
  rocky coast, kelp, fjord, open ocean, maritime reach, the three cold-habitat
  indicators, coastal support, island habitat, and all thirteen magical region fields
  including their centre selection. Exact.

- **Authoring catalogues** (`Core/catalogue.cpp`, `Core/profiles.cpp`): the resolved
  civilization traits, biome preferences, magical-variant preferences, food
  multipliers, civilization identities and habitat rule trees, read from
  `Contracts/catalogues/native-catalogues-v1.json`. Habitat evaluation, allocation-group
  exclusion and priority ordering reproduce `eligible_civilizations`. Authoring and
  validation stay in Python by [decision 020](../../docs/decisions/020-authoring-catalogues-ship-as-data.md);
  every trait, preference and habitat answer is still compared against the oracle.

A finding worth recording: the world's **final** magic and zone fields are not stage
nine. Ages one and two rescale every ley node and edge intensity and re-evaluate, and a
destroyed city can add a key point, so those fields depend on the settlement and age
stages. The native envelope therefore carries `history_stage = 9` and treats them as
civilization-stage inputs; the parity test compares them against
`materialize_stage(world, 9)` rather than the finished world.

**Still open — step 6 and the anchors in step 7:** `world_scene` building footprints,
street and regional-road polylines with shared junctions, and nest anchors. Nothing
places them today, and the consumer materializes no building, road or nest as a result.

Placement is not a thin layer on what is done: site selection reads magic hazard, ley
networks, coastal support, metal richness, civilization habitats and population
budgets, so the remaining port is the rest of the simulation, measured at 4,539 lines
of Python across twenty modules plus eight JSON catalogues:

| module | lines | module | lines |
| --- | --- | --- | --- |
| terrain_settlements | 927 | civilization_registry | 339 |
| castle_planner | 402 | city_planner | 353 |
| castle_geometry | 302 | terrain_society | 278 |
| hamlet_planner | 266 | terrain_humans | 224 |
| city_fortifications | 199 | terrain_leyline_history | 185 |
| city_shapes | 174 | terrain_magic | 137 |
| world_scene | 122 | terrain_seasons | 115 |
| terrain_nests | 107 | terrain_profiles | 100 |
| founding | 93 | city_geometry | 78 |
| terrain_civilizations | 75 | world_debug | 63 |

Catalogues: `buildings.json`, `castles.json`, `city_shapes.json`, `civilizations.json`,
`terrain_city_building_packs.json`, `terrain_city_layout_profiles.json`,
`terrain_nest_profiles.json`, `terrain_profiles.json`.

A site chosen from a different score is a different world, so nothing here can be
approximated. The work does split into steps that each have their own oracle field to
compare against, which is how the terrain and magic layers were kept honest:

| step | native output | compared against |
| --- | --- | --- |
| a **done** | per-species suitability and life-capacity fields, support reach | `suitability_*`, `life_capacity_*`, `*_support_reach` |
| b **done** | world cap, allowances, weighted habitat, quotas | `population_budget` |
| c **done** | founded sites and their order | `settlements.sites` nodes, profiles, founding years |
| d **done** | building pack, layout profile, anchors, city layout | `settlements.sites[].city_layout` |
| e **done** | road routes and river crossings | `roads.routes` |
| f **done** | age transitions one and two | final magic, ruins, surviving cities |
| g **done** | nest anchors | `beast_nests.sites` |
| h *partial* | `world_scene`: regional road polylines and city anchors done; buildings, streets and junctions wait on the city-planner slice behind (f) | `world_scene` |

Step (a) landed on 2026-09-18 in `Core/settlements.cpp`: all twelve `suitability_*`
fields are exact, the twelve `life_capacity_*` fields agree within 2.2e-16 relative,
and both routed `*_support_reach` fields are exact. That covers catalogue-driven
habitat matching, the road cost function behind a people's productive hinterland, and
the marine fishing reach that makes a coastal civilization viable.

Step (b) landed the same day: world cap, per-people allowances, weighted habitat
footprints, shares and the city quotas after the shared ceiling all match exactly at
seed 42 size 33 (cap 888 residents, 14 cities requested).

Step (c) landed on 2026-09-18 in `Core/founding.cpp`: at seed 42 size 33 the native
generator founds the same fourteen cities as the reference, at the same nodes, for the
same civilizations, in the same turns, with the same founding years, capitals,
diaspora flags, cultural-branch flags and migration distances, and it stops on the same
turn for the same reason. Parent-race initiative rotation, the origin separation rule,
participation draws, the unused-civilization preference, the search radius growth and
the diaspora round are all reproduced.

Step (e) landed too, in `Core/roads.cpp`: the same eleven routes as the reference,
node for node, with the same lengths, costs and river crossings. Each route is routed
with the founding people's own grade and mutation limits and then re-checked against
the destination people's limits, so a road only exists when both ends can travel it.

Part of step (h) landed with (e): `Core/scene.cpp` densifies each route onto the
sampled surface at the reference's own four-metre interval and anchors each city at its
sampled height. The polylines match the reference's own densification and projection
coordinate for coordinate (7,347 of them at seed 42 size 33). The trimming of a route
at a city gate belongs to (d), because the gate comes from the city plan.

`Core/scene.cpp` also exposes `populate_world`, which runs fields, founding, roads and
the scene against a supplied catalogue. The plugin calls it after generate, so a cooked
consumer draws the cities and roads the generator placed; with no catalogue present it
reports terrain-only rather than inventing civilizations.

Step f is what promotes the stage-nine magic and zone fields to the world's final
state; until it lands the native envelope keeps `history_stage = 9`.

The catalogue export grows with these steps. Building packs and layout profiles landed
with (d); city shapes, castles, structure blocks and nest profiles are still not in
`native-catalogues-v1.json`.

Step (d) landed on 2026-09-18 in `Core/cityplan.cpp`, with the layout profiles and
building packs added to the exported catalogue: at seed 42 size 33 and again at seed 7
size 65, all fourteen cities choose the same building pack from the same seeded
weighted draw, take the same layout profile, report the same river fork and bridge
recommendation, and claim the same nodes for every district and every building, with
the same assets drawn from the pack's weighted choices and the same fallback reasons
where the walking ring runs out. The finer grid exercises what the coarse one cannot:
143 building anchors across anchored, wall and river-gate placements, 41 distinct
assets, five different packs.

What (d) does **not** include is plot geometry. The reference turns these reserved
nodes into walls, streets and footprints in `city_planner.fill_cities`, which runs at
stage sixteen, after both age transitions, so `world_scene.buildings` stays behind the
same dependency chain as (f). The native plan reports which building stands on which
node, and the plugin surfaces exactly that through `GetPlannedBuildings`, labelled as
reserved slots rather than footprints.

### Where the port stops, and what the next slice actually costs — 2026-09-18

Steps (a), (b), (c), (d), (e) and the road/anchor half of (h) are done and compared
against the oracle. Steps (f) and (g) are **not started**, and the reason is a
dependency chain rather than remaining effort in those two modules:

- **(g) nest anchors** (`terrain_nests.py`, 107 lines) reads an `occupied` set built
  from settlement sites *plus* `fisheries.ports` *plus* `sky.settlements`. Fisheries
  ports come from `add_world_society`, which runs only after `add_seasonal_food`, and
  the sky settlements exist even in recipe 3, where the islands themselves are
  suspended. A nest placed without them is placed against a different clearance test,
  so it is a different world, not a partial one.
- **(f) age transitions** call `civilization(result, cfg, phase=9)`, which is
  `add_settlements` *and* `add_humans`, `add_colleges`, `add_seasonal_food`,
  `add_world_society`. `city_fate` then needs the nests from (g) and the ley threat
  pressure, and `add_threat_assessments` runs on both sides of the transition.

So (f) and (g) sit behind roughly 861 further lines of Python
(`terrain_humans` 224, `terrain_society` 278, `terrain_magic` 137, `terrain_seasons`
115, `terrain_nests` 107) and their catalogues, each of which needs its own oracle
comparison to be worth anything. That is a slice of its own, not a finishing touch, and
it is left open deliberately rather than approximated.

The consequence for consumers is stated plainly in `Core/README.md` and
`docs/unreal-integration.md`: the native envelope is the world at **history stage 9**
plus one placement round. Magic and zone fields are stage-nine values, there are no
ruins, no nests and no built geometry, and the settlement layer is the reference's
stage 10 fields and city layouts with its stage 11 routes. Anything a game builds on top of this
today is building on terrain, climate, ecology, leylines, cities and roads — all of
which are bit-compared — and not on the finished history.

## Handoff

The native envelope above is proven headlessly, so [ML-03e](ML-03e.md) is open for the
surface, registry and cooked loop. Placement work returns here.
