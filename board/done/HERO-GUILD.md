# HERO-GUILD — Calculate city hero-guild needs

Status: complete. Owner: repository maintainers.

## Requested behavior

Design and implement calculations for the hero guild associated with each city's core guild hall. Determine hero membership/activity and the resulting service and accommodation demand without counting visiting heroes as permanent residents by default.

## Proposed mechanism

Define explicit, configurable rules using civilization identity, city population/size and relevant local demand. Separate resident heroes, visiting heroes, active parties and the hall's service staff. Document the selected formulas and rounding rules before implementing deterministic calculations; do not invent fixed hero ratios as part of the building-data change.

## Dependencies and unresolved decisions

- Every city preset already includes one hall with one cook and one bartender. These two workers are already included in city worker-bed estimates.
- Decide what drives hero numbers, resident versus visitor status, party sizes, activity/capacity limits and any additional staff.
- Coordinate with future household/housing and city-site planning so accommodation is counted once. A sole-city capital must not imply a large hero population solely from its title.

## Files and assets in scope

Civilization master JSON, engine-independent calculation module, behavioral tests, and versioned output/documentation if exported. Existing guild-hall geometry is the planning input; no Unreal assets or new art are required to design these calculations.

## Acceptance and evidence

- Reviewed formulas, inputs, units and bounds are documented and data-driven where appropriate.
- Deterministic tests cover zero heroes, small cities, a sole-city capital, visitors versus residents, and unchanged results for repeated inputs.
- Service staff are not double-counted; resident housing demand and temporary lodging demand are distinct.
- Any new export or generator asset state receives explicit versioning, compiler coverage and regression tests.

## Documentation impact and handoff

Update `docs/civilizations.md` and relevant world-layer contracts when implemented. This ticket schedules calculation work only; the current hall supplies two service jobs and no hero population estimate.

## Completion evidence — 2026-09-16

Implemented the opt-in `hero_guild.calculate` planning API and a version-1 packaged policy registry with explicit entries for all twelve civilizations. Rates default to zero automatic resident heroes; capacities and rates are caller-configurable. Integer formulas and rounding were documented in `docs/hero-guild.md` before implementation. Six behavioral tests preceded the code and cover zero heroes, small cities, sole-city capitals, visitors, service/party caps, strict inputs, repeatability and all 36 civilization/tier presets. Existing cook/bartender beds are excluded from incremental demand.

Full repository validation passes (213 reference +55 facade/native-driver tests), including unchanged generated assets and reproducible showcase outputs. The installed wheel includes and executes the planner and policies. No new assets are referenced. The calculation is deliberately opt-in: it does not spawn NPCs, change city population, place housing or assign existing residents to jobs. Automatic city/world integration and demographic calibration are future work. Existing civilization/building JSON and replay identities are preserved; historical deferred-work notes there now refer to automatic integration, clarified in `docs/civilizations.md`.
