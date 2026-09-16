# Final-world city planner

The [portable coordinate contract](../Contracts/capabilities-and-coordinates.md) defines city gnomonic coordinates, radial elevation, building-axis orientation and their distinction from curved patch mesh coordinates. No planner or export version changes are introduced by that additive contract helper.

City planner version 4 runs after stage 16 and after the last requested age transition. Earlier simulation snapshots do not contain future city plans. It adds the optional, independently versioned `city_plans` world-output section; recipe 3 now uses generation algorithm 16 for parent-race founding. Planner identity includes both civilization/building registries and the city-shape catalogue hash. Age advancement rejects mismatched identities.

## Six ordered passes

1. Sample the final map around each city anchor in local east/north metres.
2. Select a compatible historical shape using the world seed and stable city UID.
3. Place the civilization size preset's core buildings.
4. Fill available plots with worker houses for their target staffing.
5. Place eligible optional and specialist buildings, only after core worker housing fits.
6. Add housing for their additional staff, using spare beds first.

All civilizations use this same path. Guild halls come from their core presets. Missing prerequisites and failed placements remain explicit in `unplaced`; no building is shrunk to force a fit. A partial plan reports missing core facilities and housing shortfalls. A site with no compatible shape is unbuildable. The planner does not relocate the simulation's city anchors.

## Geometry and constraints

Plots retain their authored footprint and clearance dimensions. A conservative 4-metre occupancy grid prevents plot overlap and reserves access corridors to one connected street component. The provisional city window is 480/640/800 metres across for small/medium/capital cities, capped by neighbouring anchor distance. Shape families control the schematic boundary. Within it, streets grow along a seeded least-cost terrain tree connecting the centre to dispersed gates and districts. Routes avoid water, blocked land and grades above 35%; gentler grades cost less. A smooth seeded travel-cost field varies routes across otherwise similar ground. Block spacing controls district density, not a street grid. Roads remain a provisional 4-metre raster with widened verges; diagonal routes cannot cut blocked corners. Buildings follow averaged street tangents with up to five degrees of seeded deviation. Rotated plots reserve every intersecting occupancy cell, including their street access. The planner preserves authored dimensions rather than shrinking buildings. More complete historical growth, road loops and surveyed engineering remain future work.

The terrain mask excludes water, slopes over 25 degrees and coarse flood risk over 0.65. Where routed river lines exist within a river sample, they replace the coarse river flood flag with a provisional 24-metre channel and a 28-metre setback measured from its centreline. These are design assumptions, not simulated flood extents. No bridges are invented. Disconnected street fragments are excluded.

World rasters can be much coarser than a city: land categories use nearest-neighbour samples, while elevations use the final world height field plus canonical local relief. A shared seeded local-relief field adds real elevation detail; see [continuous terrain](continuous-terrain.md). A 4-metre vertex surface in metres is exported under `terrain.surface`; plots export `rotation_degrees`, `ground_elevation_m` (level floor) and `foundation_bottom_m`. Floors sit above sampled plot corner elevations, with schematic plinths rather than simulated earthworks. Version-1/2 city plans require regeneration before age advancement; the underlying world generation algorithm is now 13. Groundwater, navigability, bridge feasibility, wall continuity and structural engineering are unresolved. Buildings requiring unverified prerequisites remain unplaced. Selection currently derives usable area, slope, aridity and woodland; specialized shoreline/ridge/island shapes await verified topology inputs. Repetition weights count previously planned cities in stable UID order across the world.

## Staffing and housing

`buildings.json` schema 2 / revision 3 defines `housing_profiles.worker_house`: an 8 x 10 x 6 metre building on a 12 x 16 metre plot with four worker beds. Civilization schema 6 / revision 11 links building schema 2. This is a provisional shared dwelling for every civilization; cultural art is separate.

Housing serves distinct target workers in successfully placed facilities. It does not add dependents, commuters, simulated NPC objects or general population housing. Existing simulation population is reported separately and never overwritten. Lack of housing space remains a visible shortfall.

## Lab and exports

Click a city on the map, atlas, globe, or city-name list to open its separate layout dialog. The default WebGL 3D view shows the terrain surface and rotated cuboids at authored width, depth and height, with no vertical exaggeration. Drag to orbit, scroll to zoom, reset the camera, toggle labels, or use the building selector. A 2D plan remains available and is the fallback when WebGL is unavailable. Both views retain phase filtering (including pre-upgrade houses), selection and statistics. Core services are gold, lower-priority services purple, and housing blue. Phase selection reveals the ordered fill; zoom and building selection expose dimensions, staffing and beds. Stats and unplaced reasons remain visible. Generate through the final stage to obtain plans.

The exhaustive asset compiler includes all 80 supported measured structure IDs plus `building.worker_house` and `building.worker_apartment`, marked schematic. They are potential final states, not a claim that production art or an Unreal importer exists. World coordinates and dimensions remain metres.

## Verification

`Sim/tests/test_city_planner.py` and `test_city_geometry.py` cover terrain-routing obstacles/grade, elevation export, rotated non-overlap, deterministic replay, pass ordering, staffing beds, guild halls, plot non-overlap, blocked water, routed river setbacks, final-stage visibility, age identity rejection, asset coverage and housing validation. `tests/test_city_view.py` checks metre-scale cuboid geometry and terrain interpolation in Node. Run the complete simulation and repository suites plus `tools/validate_repo.py` before release.

### Apartment densification

When houses exhaust available plots, the housing pass upgrades existing houses to four-storey apartments: 10 x 12 x 12 metres, 16 worker beds, on the same 12 x 16 metre reserved plot. It stops once staffing demand is housed. Apartments use a separate building ID in the shared JSON and exhaustive asset list. The exported upgrade phase preserves earlier-pass views. Apartments increase capacity without changing the reserved land or access; they cannot rescue a site with no space for any housing plot.


## Globe integration

Planner 4 connects streets to actual regional-road crossings before placing buildings. The world exports global building transforms, street/road paths and shared junctions in `world_scene` version 1. Natural biome fills and magic outlines come from the same globe samples. See [the unified scene contract](unified-world-scene.md).

See [unified globe diagnostics](unified-world-scene.md) for algorithm-16 sky suspension, college spacing, aridity, ley alignments and lab tables.

The opt-in [hero guild planning API](hero-guild.md) reports additional resident hero/staff beds separately from visitor lodging. It is not automatically applied to these layout passes; the existing hall cook and bartender remain counted once by current staffing.
