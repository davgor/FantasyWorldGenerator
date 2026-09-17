# Historical city shapes and location selection

[city_shapes.json](../Sim/icarus_sim/city_shapes.json) is the canonical shape catalogue (schema 1, revision 2). It contains researched morphology patterns, their historical sources, location requirements, weighted preferences, layout guidance and variation ranges. `city_shapes.py` validates it and provides standalone deterministic selection. Both ship with the package.

The selector supplies the [final-world city planner](city-planner.md), which generates schematic streets and measured building plots after simulation. The catalogue alone remains a selection API, not a geometric solver.

## Historical evidence and game adaptation

The catalogue distinguishes a city's boundary, street network and arrangement of centers. Real cities combine periods, districts and topography; none of these examples establishes a universal formula. Every record separates source evidence from the proposed game adaptation. Numeric gates, probabilities and dimensions of generated blocks are provisional design choices, not measurements of the historical examples.

The available patterns are:

- Irregular market town and courtyard/shaded-lane town, adapted from [Tunis's compact fabric, courts, market routes and winding lanes](https://whc.unesco.org/en/activities/1176/).
- Planned market grid, informed by [Cornell's Monpazier collection](https://digital.library.cornell.edu/catalog/ss%3A3852783).
- Ridge fishbone, informed by [Edinburgh's Old Town spine and branching closes](https://whc.unesco.org/en/list/728).
- Hilltop contour rings and oasis clusters, informed by [M'Zab's concentric settlements and relationship to palm groves](https://whc.unesco.org/en/list/188).
- River-meander town and paired bridgehead quarters, informed by [Cesky Krumlov](https://whc.unesco.org/en/list/617) and its [ICOMOS evaluation distinguishing opposite-bank areas](https://whc.unesco.org/document/153890).
- Island town with parallel spines, informed by [Lubeck](https://whc.unesco.org/en/list/272).
- Waterfront comb, extrapolated from the district-scale trading rows and passages of [Bryggen](https://whc.unesco.org/en/list/59). The whole-town interpretation is explicitly a game adaptation.
- Peninsula enclosure, informed by [Nessebar's constrained setting](https://whc.unesco.org/en/list/217).
- Connected lagoon islands, informed by [Venice's island/canal urban system](https://whc.unesco.org/en/list/394).
- Citadel and lower town, informed by [Rhodes's upper and lower quarters](https://whc.unesco.org/en/list/493).
- Ceremonial/residential clusters, informed by [Tikal's distinct functional ensembles](https://whc.unesco.org/en/list/64). This is a pre-Columbian reference, not a claim that Maya cities were European medieval towns.
- Linked enclosed compounds, informed by [Chan Chan](https://whc.unesco.org/en/list/366).
- An older core with a planned extension, informed by [Ferrara](https://whc.unesco.org/en/list/733). This Renaissance reference is disabled by default; request `include_later=True` to include it.
- Concentric defensive enceintes for capitals, informed by [Carcassonne's fortification lines](https://whc.unesco.org/en/list/345). High `regional_threat` strongly prefers this pattern so multi-ring walls can appear; it is an explicit game adaptation, not a claim about any fictional setting.

All civilizations can use compatible shapes. A historical reference does not lock an invented race to that culture. Site features determine feasibility; optional trade, planning and defense scores influence preference, not eligibility.

## Location input contract

Always supply `buildable_area_m2`, `usable_land_fraction`, and `local_slope_degrees`. Area means usable dry land after flood, water, cliff and protected-land exclusions; fraction is that area divided by the candidate footprint area. Slope is a representative footprint slope, not approval of every local road grade. Current provisional gates require at least 12,000 square metres, at least 0.15 usable fraction and at most 35 degrees representative slope; individual patterns impose tighter limits. Insufficient information or space is not permission to force a layout.

Optional explicit booleans describe coast access, navigable water, a river, a river bend, feasible bridges, island/peninsula/lagoon setting, ridge, hill and oasis. Do not infer navigability from the mere presence of water. Bridge feasibility must reflect viable crossings, not just a desired bridge. Missing booleans fail dependent hard requirements.

Optional 0-to-1 scores describe corridor constraint, aridity, wooded fraction, defensive priority, planned foundation and trade intensity. Missing preference data supplies no bonus. The JSON `site_features` dictionary specifies names, types, bounds and units. Unknown fields, nonfinite values and integers in place of booleans are rejected. These are a new planner-facing contract; the existing coarse world grids do not yet automatically produce all these facts.

## Selection and variety

`rank_shapes(site, city_class='medium', nearby_counts=None, include_later=False)` returns eligible candidates in stable ID order with weights and explanations. It is not a sorted best-to-worst ranking. City class accepts small, medium or capital; the current patterns allow all three and must scale to actual land and building requirements, not automatically become huge when labeled capital.

The weight is `(base_weight + matching_preference_bonuses) / (1 + 0.75 * nearby_same_shape_count)`. The penalty comes from JSON. It softly discourages local repetition without fabricating a shoreline or forcing a different unsuitable pattern. Callers must build `nearby_counts` in stable city order for repeatable regional planning. Different suitable shapes can still repeat; there is no uniqueness guarantee.

`select_shape(site, seed, city_id, ...)` samples those weights using SHA-256 over the seed, stable city ID, catalogue identity and a separate label for each draw. Variation covers footprint aspect ratio, street curvature, block spacing, plaza offset and district count. Thus repeated shape families can still produce different parameters. Geographic orientation must follow actual banks/ridges/approaches rather than arbitrary rotation.

No match returns `shape_id: null` with a reason. No fallback bypasses terrain gates. The result is version 1, includes catalogue revision and hash, and declares `runtime_geometry_generated: false`. Replay requires identical inputs, nearby counts, selector version and catalogue. The final-world planner includes this catalogue hash in its replay identity and rejects changed identities before age advancement.

## Placement handoff

The selected form must be clipped to the actual buildable mask. Reserve the civilization's required services and guild hall using the linked building `plot_m` and access widths; reserve streets, public spaces, drainage and hazard separation. Housing fills the remaining feasible plots. Do not shrink buildings or discard core services to meet an outline or density target. Resolve conditional facilities before staffing and housing calculations.

Bridge spans, cargo access, continuous circulation, evacuation/service access, road grades and terrain retention still need geometric checks. `block_spacing_m` and aspect ratio are suggestions for that solver, not finished coordinates. If the measured program cannot fit, report the capacity conflict or choose another approved site/program. No meshes, roads, housing or NPCs are created by the selector.

## Authoring and verification

Add a stable shape ID, sources, evidence/adaptation notes, valid feature rules, layout instructions and bounded variations in JSON. Increment its revision for content changes and schema version for incompatible structure changes. Run `PYTHONPATH=Sim python -m unittest Sim.tests.test_city_shapes` and the repository validator. Tests cover historical reference integrity, inland/water gates, steep terrain, no-match handling, determinism, multiple outcomes, repetition penalties and malformed inputs.
