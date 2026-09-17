# Unified globe scene and varied leylines

See [capabilities and coordinates v1](../Contracts/capabilities-and-coordinates.md) for the exact globe/tangent axes, building rotation convention, datum, projection differences and consumer negotiation. The coordinate oracle is an independent reference, not an engine adapter.

Algorithm 16 uses magic report 4 and city planner 5. Regenerate worlds from earlier algorithms. Existing authored school node counts, occurrence, strength, width, variation and intensity controls remain supported. No new potential asset IDs are introduced.

## Magical geography

Each school independently draws 1–4 concentration centres, a spread and an outlier fraction. Seeded points cluster unevenly, with scattered outliers. Local groups form sparse trees and random additional links; groups can remain disconnected. Counts remain the authored node counts rather than silently changing a user override. Geometry, links and distribution parameters replay exactly from the school seed. Changing one school's variation does not reroll other schools or terrain. The legacy standalone geometry experiment retains its old magic model.

World and city views retain natural-biome fills. Dominant magical mutations use the corresponding school color as an outline. Diagnostic scalar fields and explicitly selected overlays remain available. City natural-biome IDs and mutation IDs are sampled at the city's actual globe position and exported with the catalogues. World biome classification remains at regional resolution; no extra categorical detail is invented. Height detail remains continuous as described in continuous-terrain.md.

## Connected streets

For each regional road ending at a city, the planner projects its polyline into the city's globe-referenced crop and computes the actual boundary crossing. Those crossings become required destinations in the same terrain-cost street tree used for local streets. The tree may extend beyond the selected urban shape to reach the crop boundary; building plots remain inside the shape. Streets and approaches are reserved before building placement. A final short segment joins the street-cell centre to the exact crossing, subject to water, flood, slope and grade checks.

Every connection records its regional route ID, stable junction ID, local gate coordinates, globe direction and status. Impassable crossings remain `unreachable` with a reason; no bridge, tunnel or steep connector is invented. Cities without regional roads remain isolated. Existing regional transport connectivity is not forcibly expanded.

## World JSON

Final generation and subsequent completed age transitions include `world_scene` version 1 alongside `city_plans`. It contains globally positioned building footprints and transforms, street polylines, regional-road polylines and junctions. XYZ is globe-centred in metres: Y points north, X passes through latitude 0/longitude 0, Z through latitude 0/longitude 90. Surface positions use `(radius_m + canonical_height_m) * direction`.

Buildings have globe positions, unit up/width/depth axes and measured dimensions. Footprint corners preserve authored widths/depths. City previews use the corresponding local projection, with radial heights drawn vertically; the globe scene supplies the actual orientation and curvature. These are two coordinate representations of the same generated records, not separate settlements.

Regional roads are trimmed at city gates. City approaches and regional endpoints reuse exactly the same resolved globe position. Regional polylines are sampled at at most 4 m angular spacing against canonical terrain. That densifies their existing alignment; it does not engineer bridges or reroute the regional network for every newly resolved grade. Bridge candidates and connection failures remain explicit. The original `roads` report remains the regional transport/economy proposal; `world_scene` is the detailed placement boundary.

The lab globe includes global street/road polylines and building footprints. The city inspector shows the same local street connections (orange approach ends), natural biome colors and magic outlines. Engine streaming, collision and asset realization remain adapter responsibilities. Convert metres to Unreal centimetres only at that boundary.

Tests cover replay and distribution/topology variety across seeds, actual city/world junction equality, blocked crossings, building dimensions, biome fills surviving magic outlines, and full world export regression. World-scene arrays are generated only at completed simulation states; earlier history snapshots do not expose future placement.

## Debugging and the compact lab (algorithm 16)

The page orders the stage selector, biome filter buttons, globe, atlas, then graphs and tables. City rows open the layout inspector. Stage tables report selected-state cities, colleges, ruins, food and landmarks. Final-state graphs are explicitly labeled: urban population by civilization, parent-race totals, city counts through history, founding outcomes and diaspora survival, nearest-city distances, worker housing constraints, leyline distribution and area-weighted natural-biome coverage. `debug_stats` version 1 accompanies JSON exports and age advances. Duplicate founding events in snapshots are collapsed; diaspora fate matches node/civilization to current sites and ruins. Recolonization of the same node by the same civilization cannot be distinguished as a separate lineage by this summary. Raw diagnostic JSON remains inspectable.

City `debug` records safe and shape-eligible cells, occupied/access/road cells, vacant shape cells and house frontage candidates. Housing passes record houses placed, upgrades, plot exhaustion and bed shortfall. Housing is houses-first: existing houses upgrade to apartments only when no valid street-accessible house plot remains. Vacant area is not a count of valid contiguous plots. Worker beds do not represent the city's full population.

Recipe 3 suspends sky islands, sky cities and their food production. Sky reports retain empty arrays and `enabled:false`; occurrence and cluster controls are fixed to zero and hidden. The archived surface generator remains for potential future work. No new asset identities are added.

Colleges keep a 150 m exclusion from settlements and gain independent pairwise separation of max(1500 m, 0.15 times globe radius). Suitable reachable sites can yield fewer colleges than requested. Warm terrain now increases the rainfall-to-moisture denominator from .025 by a factor of 1 + max(0, temperature proxy - 10)/15; rainfall, water accounting and runoff are not changed. This provides an evaporation proxy for dry warm landscapes without enforcing a desert quota. Compare area-weighted biome coverage across seeds; this is not calibrated climatology.

## Leyline inspiration

Watkins proposed straight alignments between landscape marks and ancient sites, rather than a measured energy field. His [original ley-hunting criteria](https://www.megalithia.com/alternative/leydef.html) and a [historical study of his work](https://www.mdpi.com/2076-0787/4/4/637) distinguish that origin from later esoteric earth-energy interpretations. There is no established scientific calculation for such energies. Our fantasy translation is explicit: each school has three seeded sacred loci on one great-circle alignment (straight on a sphere), with independently distributed additional loci, uneven clusters and sparse extra links. The loci are generated magical geography, not claims that real archaeological sites obey this rule. Distribution metadata version 2 records the alignment indices. Schools keep separate seeds and editable node/line intensities; later age events can add loci and disturb the initial alignment.
