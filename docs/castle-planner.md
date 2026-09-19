# Final-world castle planner

Castle planner version 1 runs after stage 16 (and after the last requested age transition), after the [city planner](city-planner.md) and [hamlet planner](hamlet-planner.md). Earlier simulation snapshots do not contain castle plans. It adds the optional, independently versioned `castle_plans` world-output section so fortification layouts can be retuned without depending on `city_plans` or `hamlet_plans`.

Planner identity hashes [`castles.json`](../Sim/icarus_sim/castles.json) and the `structure_blocks.castle` building subset only. Age advancement rejects mismatched identities. The city planner identity is unaffected by kit/join edits in `castles.json`.

## Independence

- No imports from `city_planner.py`.
- Consumes `humans.fortresses` pins only. How many pins exist is the simulation's
  call, not the planner's: see `humans.fortress_demand` in
  [simulation and world layers](terrain-world-layers.md). One castle is planned per
  pin, so a world whose roads ask for more defence plans more castles.
- Does not write into `city_plans` or change `defended_perimeter` city packing.
- Own module join rules, typology kits, tests and documentation.

## Ordered passes

1. Sample the final map around each fortress pin in local east/north metres.
2. Select a typology kit (`kit.simple_enclosure`, `kit.motte_bailey`, or `kit.concentric`) from the world seed and fortress id.
3. Trace closed perimeter rings, segment curtains, place gate/postern/corner towers/wall stairs, and validate thickness/height/walkway joins.
4. Place bailey courtyard open areas inside closed rings.
5. Place the keep tower landmark (inner ward or motte).
6. Place bailey services (barracks, armory, well, hall, chapel, drawbridge when requested).

Missing joins and failed rings remain in `unplaced`. Curtain segments are never silently dropped to invent a gate.

## Module grain

[`castles.json`](../Sim/icarus_sim/castles.json) defines fortification modules (`curtain_segment`, `corner_join`, `gatehouse`, `postern`, `wall_stair`, …) with end types, thickness/height bands and walkway flags. Join rules reject incompatible ends and dimensional deltas. Measured shells live under `structure_blocks.castle` in [`buildings.json`](../Sim/icarus_sim/buildings.json) ([castle blocks](catalogue/castle-blocks.md)).

Each closed ring exports a `wall_networks[]` entry with stable section IDs, polylines, segments, gates, towers and stairs. Plots reuse the same metre pose fields as city/hamlet plans for viewer compatibility.

## Lab

Click a fortress card under “Inspect hamlets and fortresses”, or a fortress marker on the map/globe, to open the shared layout dialog via `openCastlePlan`. Curtain segments from `wall_networks` render as brown extruded boxes in 3D and filled polygons in 2D (same path as city `fortifications.segments`). 3D boxes follow curtain depth along the wall path. Clipped rings flatten needle vertices. Phase filtering covers perimeter, courts, landmarks and bailey services.

## Verification

`Sim/tests/test_castle_planner.py` and `test_castle_geometry.py` cover replay, join rejection, closed walkways, approach gates, independence from `city_plans`, final-stage visibility, age identity rejection and asset coverage. Run `python3 tools/validate_repo.py` before release.
