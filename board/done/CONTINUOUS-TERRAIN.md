# Continuous terrain heights

Owner: local. State: running. No delegates.

- A1: Shared seeded spherical height function with rolling/local/ground bands; deterministic position sampling and protected water. Verify synthetic behavioral tests.
- A2: Versioned resolved tile export with metre heights, coordinates and exact shared boundary samples. Verify adjacent tiles and nested resolution.
- A3: City roads, local slopes, foundations and human-scale patch consume shared heights; lab displays exported data. Verify planner tests and live view.
- A4: Version contracts, docs, provenance, full regression suites and repository validator. Preserve unrelated Arctic work. Engine streaming is outside scope.

Next: failing behavioral tests, then implementation.

## Verification checkpoint

- A1 accepted: 6 new terrain-detail tests passed, including deterministic relief, water protection, exact adjacent/nested/seam samples, shared patch heights and city slopes.
- A2 accepted: CLI exported 65 x 65 resolved tile at 0.340239 m equatorial spacing. Height-tile and world-envelope schemas passed. Separate polar samples agree exactly.
- A3 accepted: 28 city tests and 6 legacy patch tests passed. New seed-42 live lab served on 8769 and refreshed; Juniper 3D view inspected, no browser errors. Kestrel local detail adds -3.74 to +3.30 m over a 160 m region. Regional height/climate/biome data exactly match algorithm13 baseline. HTTP smoke passed.
- A4 running: full simulation session41328 and repository session82345. Initial repo command omitted PYTHONPATH and was stopped; corrected run owns detail-repo-corrected.log. Source files frozen during reproducible showcase tests. Required validator blocked by existing Contracts/catalogues/world-assets.json provenance drift (python3 Store alias unavailable; python fallback attempted).
- Live server session26922. Artifacts/continuous-terrain-preview contains world, HTML and example tile. Source change means algorithm14 regeneration is required. No engine integration claimed.

## Closeout

State: complete. A1-A4 accepted, with the pre-existing repository provenance blocker explicitly retained.

- Full simulation suite: 203 tests passed in 601.407s.
- Full repository/export suite: 16 tests passed in 462.264s, including byte-reproducible showcase builds.
- Compileall, schema checks, shared-pole check, HTTP smoke and git diff --check passed. New assets: none. Generated showcase changes are intentional algorithm14/local terrain output changes; source catalogue drift was not repaired.
- Canonical docs: docs/continuous-terrain.md, city-planner.md, terrain-world-layers.md and Contracts/README.md.
- Algorithm14, planner3, terrain-detail1, canonical patch2, height-tile1. Existing worlds require regeneration. The live seed42 lab was regenerated and refreshed. Juniper's detailed 3D layout is open.
- No commits, publishing or engine assets changed. Engine streaming/collision and LOD stitching remain engine responsibilities. Regional drainage/roads remain regional; detailed city roads, slopes and foundations use shared local heights.
- Next action: inspect the regenerated city and human-scale patch, then consume resolved height tiles via the documented JSON boundary in the future engine adapter.
