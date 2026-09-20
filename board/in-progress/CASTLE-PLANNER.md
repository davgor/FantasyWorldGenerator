# CASTLE-PLANNER — Independent modular castle layouts

## Requested behavior

Turn route-defence fortress pins into metre-scale modular castles with fine wall-path segments, joins, gates, baileys and keep towers, exported as independent `castle_plans` version 1.

## Proposed mechanism

- `castles.json` owns kits and join rules; `structure_blocks.castle` owns measured shells.
- `castle_geometry.py` closes rings, segmentizes curtains and validates joins.
- `castle_planner.py` plans each fortress and writes `castle_plans` beside city/hamlet plans.
- Stage 16 and age completion call `fill_castles` after hamlets; identity is checked separately.

## Dependencies and unresolved decisions

- Garrison beds and siege economy remain deferred.
- Dedicated lab castle inspector deferred (JSON + globe tags first).
- Structural engineering and production ARCH assembly remain out of scope.

## Sources consulted

- `PLAN.md` fortification / settlement construction sections
- Existing city fortification helper and hamlet planner independence pattern
- Human civilization defense block measurements

## Files and assets in scope

- `Sim/icarus_sim/castles.json`, `castle_geometry.py`, `castle_planner.py`
- `Sim/icarus_sim/buildings.json` (`structure_blocks.castle`, revision 5)
- `Sim/icarus_sim/terrain_history.py`, `world_scene.py`
- `Sim/fantasy_world_generator/asset_list.py`
- `Contracts/schemas/world-output.schema.json`
- `docs/castle-planner.md`, `docs/catalogue/castle-blocks.md`
- `Sim/tests/test_castle_planner.py`, `test_castle_geometry.py`

## Acceptance and evidence

Behavioral tests for replay, joins, approach gates, independence, stage export, age identity and asset coverage. `python tools/validate_repo.py`.

## Documentation impact

Canonical castle planner doc and catalogue; README map; terrain-math-lab fortress note; contracts README; unified scene settlement_kind.

## Adversarial review and limitations

Schematic polylines/cuboids only. Kit selection is seeded weights, not historical survey. City `defended_perimeter` packing unchanged.

## Handoff

Next: optional ditch/palisade visualisation polish; garrison beds remain deferred.
