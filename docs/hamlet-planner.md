# Final-world hamlet planner

Hamlet planner version 3 runs after stage 16 (and after the last requested age transition), immediately after the [city planner](city-planner.md). Earlier simulation snapshots do not contain hamlet plans. It adds the optional, independently versioned `hamlet_plans` world-output section so Unreal and lab consumers can tinker with rural layouts without depending on `city_plans`.

Planner identity includes the linked civilization/building registry hash. Age advancement rejects mismatched identities.

## Six ordered passes

1. Sample the final map around each support hamlet anchor in local east/north metres.
2. Clip to a seeded compact elliptical boundary (hamlet-owned; not the city shape catalogue).
3. Place the civilization `hamlet` preset's core buildings that pass role filters.
4. Fill worker cottages (`building.hamlet_house`) for their target staffing.
5. Place eligible conditional buildings only after core housing fits.
6. Add cottages for their additional staff.

Missing prerequisites and failed placements remain in `unplaced`. No building is shrunk to force a fit. Apartment densification is **not** used for hamlets.

## Role filters

Simulation roles drive placement conditions:

- `farming` → `farming_support` (barn, farmyard)
- `resource` → `resource_support` (staging yard)
- coastal (`harbor`, `fishing`, `landing`, `harbor + fishing`) → `navigable_shore` (landing, net shed)

## Geometry and roads

The provisional window is about 200 metres across (100 m half-extent). Neighbouring cities and hamlets clip windows to half the metre distance minus an 8 m gap, so packed footprints do not overlap. Version 1 used the city 0.28 distance crop, which left clustered rural sites too small for cottages.

Streets grow as a 4-metre least-cost tree **inside the ellipse**, with a rural branch floor of 2 instead of the city 12-district floor. Required gates come from the hamlet's `access_nodes` path toward its parent city when that crossing lies in the ellipse. Regional MST edges are not invented here. See [unified globe scene](unified-world-scene.md) for tagged `settlement_kind: hamlet` globe exports.

Standing water and local slopes above 25 degrees still block cells. Coarse regional `flood_risk` does **not** empty a hamlet: coastal support pins often sit on flood_risk=1 cells that are otherwise dry at schematic scale. River channels remain reserved through the water sampler's 12 m setback.

Version 3 applies that rule to the road-access gate as well. The cell mask had excluded the regional proxy since version 1, but the gate deciding whether a plot reaches a street still required `flood <= 0.65` from a sampler field that meant the regional layer whenever no river was near, so on a flood_risk=1 cell the mask admitted the ground and the gate then refused every plot on it. The shared sampler now returns `channel` and `flood_risk` as separate fields and both tests read `channel`. See [city planner](city-planner.md) 7, which carries the measurements.

## Catalogue

Measured rural IDs live in `structure_blocks.rural` and `housing_profiles.hamlet_house` ([hamlet blocks](catalogue/hamlet-blocks.md)). City worker housing IDs are never placed.

## Lab

Click a hamlet card under “Inspect hamlets and fortresses”, or a nearby map/globe hamlet marker, to open the shared layout dialog via `openHamletPlan`. Phase filtering, 2D and 3D cuboid views match the city inspector. Fortress cards open `openCastlePlan` for independent `castle_plans` (wall segments included).

## Verification

`Sim/tests/test_hamlet_planner.py` covers replay, pass order, role filters, rural ID exclusivity, support-road gates, nearby-window packing, coastal flood_risk, final-stage visibility, age identity rejection and asset coverage. Run `python tools/validate_repo.py` before release.
