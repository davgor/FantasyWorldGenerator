# CITY-WALLS — City fortifications and regional threat

## Requested behavior

Automatic city walls/gates for medium and capital cities, expandable urban crops, capital multi-ring shape selection from regional threat, and threat assessments after beasties and each age.

## Proposed mechanism

- `threat_assessments` schema 1 after stage 13 and each age (shared nest weights with `city_fate`).
- City planner v5: program-sized crop, fortification pass, `fortifications` export.
- Shape catalogue revision 2: `regional_threat` feature and `concentric_enceintes` capital shape.
- City-only wall generator (`city_fortifications.py`); castle walls remain separate.

## Dependencies and unresolved decisions

Castle bailey generator stays independent. Structural engineering, ditches for small towns, and Paris-style ruined inner walls deferred.

## Sources consulted

Carcassonne UNESCO listing for multi-wall adaptation; existing city planner / nest fate rules.

## Files and assets in scope

`terrain_history.py`, `city_fortifications.py`, `city_planner.py`, `city_shapes.json`, city view, docs, tests.

## Acceptance and evidence

Threat, fortification, shape and city-planner unit tests; `validate_repo.py` at closeout.

## Documentation impact

`terrain-world-layers.md`, `city-planner.md`, `city-shapes.md`, `Contracts/README.md`.

## Adversarial review and limitations

Schematic enceintes only; no structural continuity proof. Threat score is artistic, not creature AI.

## Handoff

Implementing in this session; move to done when validation passes.
