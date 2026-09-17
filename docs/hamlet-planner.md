# Final-world hamlet planner

Hamlet planner version 1 runs after stage 16 (and after the last requested age transition), immediately after the [city planner](city-planner.md). Earlier simulation snapshots do not contain hamlet plans. It adds the optional, independently versioned `hamlet_plans` world-output section so Unreal and lab consumers can tinker with rural layouts without depending on `city_plans`.

Planner identity includes the linked civilization/building registry hash. Age advancement rejects mismatched identities.

## Six ordered passes

1. Sample the final map around each support hamlet anchor in local east/north metres.
2. Clip to a seeded compact elliptical boundary (hamlet-owned; not the city shape catalogue).
3. Place the civilization `hamlet` preset's core buildings that pass role filters.
4. Fill worker cottages (`building.hamlet_house`) for their target staffing.
5. Place eligible conditional buildings only after core housing fits.
6. Add cottages for their additional staff.

Missing prerequisites and failed placements remain in `unplaced`. No building is shrunk to force a fit. Apartment densification is **not** used for hamlets in v1.

## Role filters

Simulation roles drive placement conditions:

- `farming` → `farming_support` (barn, farmyard)
- `resource` → `resource_support` (staging yard)
- coastal (`harbor`, `fishing`, `landing`, `harbor + fishing`) → `navigable_shore` (landing, net shed)

## Geometry and roads

The provisional window is about 200 metres across (100 m half-extent), capped by neighbouring anchors. Streets grow with the same 4-metre least-cost tree as cities. Required gates come from the hamlet's `access_nodes` path toward its parent city (window-boundary crossing). Regional MST edges are not invented here. See [unified globe scene](unified-world-scene.md) for tagged `settlement_kind: hamlet` globe exports.

## Catalogue

Measured rural IDs live in `structure_blocks.rural` and `housing_profiles.hamlet_house` ([hamlet blocks](catalogue/hamlet-blocks.md)). City worker housing IDs are never placed.

## Lab

Click a hamlet card under “Inspect hamlets and fortresses”, or a nearby map/globe hamlet marker, to open the shared layout dialog via `openHamletPlan`. Phase filtering, 2D and 3D cuboid views match the city inspector.

## Verification

`Sim/tests/test_hamlet_planner.py` covers replay, pass order, role filters, rural ID exclusivity, support-road gates, final-stage visibility, age identity rejection and asset coverage. Run `python3 tools/validate_repo.py` before release.
