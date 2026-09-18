# Terrain math lab

Current lab default: [recipe 2 staged history](terrain-world-layers.md) adds sixteen inspectable stages, deep-time tectonic deformation, eight independent leylines, natural/magical biome catalogues, and two civilization ages. Recipe 0/1 behavior below remains available explicitly.

Current contract: [recipe 3 and explicit biome states](terrain-world-layers.md). Launch `python3 tools/terrain_lab.py --serve`. Recipes 1/2 and legacy biome/save compatibility are retired. The mathematical development notes below are historical evidence; old numeric biome examples, generator versions and seed-calibration figures are not current interchange guidance. Standalone geometry experiments remain available, using the current biome rules.

Unreal port note: the Python/browser lab was originally copied from IcarusAI and is now extended by the layered-world recipe. The
sections below retain the source experiment's chronological history; later
stages supersede earlier scope boundaries. Historical Artifacts paths and review
links refer to the source experiment. Its complete documentation and reviews are
preserved under [the source snapshot](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/reference/icarusai-snapshot/docs/terrain-math-lab.md).
No Unreal terrain renderer, runtime generator integration or save importer is
provided by this standalone port.

Current full globe experiment (derived recipe by default): `python tools/terrain_lab.py --serve --shape globe --tectonics 1 --phase 9`. Stage 9 adds human cities, hamlets, fortresses, irrigation, food exchange and culture IDs. Earlier sections describe preceding increments.

An engine-independent, Python-standard-library experiment. Launch from the
repository root with `python tools/terrain_lab.py --serve`, then open
http://127.0.0.1:8765. Stop the server with Ctrl+C. It binds only to loopback.

Change seed, noise amplitude/scale/octaves, ridge mix, gorge depth/half-width,
meander, physical region extent, resolution, and TPI radius; press Generate.
Use stage buttons and diagnostics, hover for measurements, and click an atlas row for a cross-section.
Export JSON downloads the currently generated result, not unsubmitted form edits.

## Current globe pipeline (generator version 5)

Start with `python tools/terrain_lab.py --serve --shape globe --tectonics 1 --phase 4`.
The four stage buttons retain intermediate results: plate layout, tectonic relief,
surface detail, erosion and sediment. Previous/Next changes inspection only;
Compute through stage limits generation work. Diagnostics are buttons within each
stage. Globe geometry and before/after profiles follow the selected stage. Final
area and slope diagnostics are explicitly associated with the final generated surface.

The display-only relief control and shaped continental foundation from v4 remain.
Collision belts now also have asymmetric cross-belt widths. Continuous compact
plate memberships blend nearby pair contributions, with smooth crust-based
subduction polarity. Categorical ownership can change abruptly without forcing a
terrain jump. Distance diagnostics use the nearest edge of the owning cell,
independently of which pairs are inside the blending support.

For membership `w_i = max(0, 1 - (best_score - score_i)/(2*belt_width))³`, each
pair's interaction is weighted by `w_i*w_j`. Divide the sum by
`max(1, sum(pair_weights))`: multiple junction contributions blend, while isolated
tails fade into the continental foundation. This is a static artistic model;
it does not simulate tectonic history or physical crust strength.

Erosion builds a spherical graph with eight neighbors per interior node, one
unique node per pole, a wrapped seam, geodesic edge lengths and latitude-weighted
areas. Each node routes to its steepest strictly lower neighbor. Descending-height
ordering is acyclic and accumulates upstream catchment area. Submerged nodes and
closed depressions are terminal sinks. There is no rainfall, lake overflow, or
water surface solver yet; catchment is area, not a measured water discharge.

Each pass uses a stream-power proxy for erosion depth:
`d = min(0.15 * downstream_drop, strength * 0.04 * sqrt(catchment_area) * slope)`.
Transport capacity is `2*d*cell_area`. Incoming sediment consumes capacity before
new material is cut; excess deposits locally, capped against the initial maximum
height. Undeposited material at terminal sinks remains in an explicit sediment
reservoir. Thus `eroded volume = deposited volume + stored sediment`, within
floating-point tolerance. The cap and limited cuts keep heights inside their
original range. This is a grid-dependent experiment, not a calibrated erosion rate.

Controls: erosion passes 0–40 and strength 0–1. Zero passes preserves stage 3
exactly. Export includes `continental`, `structure`, `surface`, final `height`,
`erosion`, `deposition`, `erosion_delta` (metres), `catchment` (m²), and a
`sediment_budget` (m³). Physical scaling applies length/area/volume powers
consistently. The generator version is bumped; this standalone lab has no JSON
import or game-save migration path. Reproduce older snapshots with their matching
generator revision rather than assuming seeds match between versions.

A v5 default 129² sample of seeds 0–15 averages 18.92 km² land, range
13.50–23.92 km². The shared scale is unchanged; no individual world is fitted.
See `Artifacts/terrain-lab/stage-four-benchmark.json`. Layout timing currently
includes boundary profile evaluation; interactions timing is array assembly.
A one-repeat benchmark after warm-up measured 0.394 s at 65², 2.022 s at
129² and 8.643 s at 257²; these local observations exclude JSON and browser
rendering and are not a statistical performance guarantee. At 129², layout and
boundary blending took 0.995 s and erosion 0.377 s. Full configuration and
results are in `Artifacts/terrain-stages-benchmark/benchmark.json`.
Stage inspection does not recompute math. Generation does rebuild upstream data;
caching plate-pair frames and spherical neighbor geometry are useful next
optimizations. Erosion sorting is O(passes * N log N), graph storage O(N), and
pair blending has worst-case O(N * plate_count²) work (compact support usually
reduces active pairs). The following sections document earlier model increments;
the v5 description above supersedes their statements about missing blending or erosion.

## Repeatable experiments

```powershell
python tools/terrain_lab.py --seed 42 --depth 900 --width 300 --size 257
python tools/terrain_lab.py --depth 0 --output Artifacts/terrain-flat-carve
python tools/terrain_lab.py --benchmark --repeats 5
```

Each invocation writes `index.html` and `terrain.json` under
`Artifacts/terrain-lab` by default. HTML snapshots support layers and cross-sections;
regeneration requires the local server. Output directories are overwritten per run;
use different `--output` paths to retain experiments. Export includes full-precision
arrays, configuration, spacing, effective neighborhood radius, warnings, and
generator version 1. Timings are intentionally nondeterministic; arrays reproduce
for the same configuration on the tested Python runtime. No game save schema changes.

Grid size is 3–1025 on the CLI and 3–257 interactively. Octaves are 1–10; ridge
mix is 0–1. Distance controls are metres, nonnegative and at most 10,000,000;
extent, wavelength, width and radius must be at least 0.01. Values outside practical
sampling ranges may be accepted with warnings; physical plausibility is not implied.

## Mathematics and tests

- Actual gradient Perlin noise uses quintic interpolation and stable integer
  hashing. Octave wavelength halves and amplitude halves per level. Coordinates
  use metres, not grid indices. A ridge transform `(1 - abs(noise))^3 - 0.5`
  blends with ordinary noise. This is a tunable visual model, not geology.
- The gorge follows a sinusoidal centerline. With horizontal cross-section
  offset `d`, half-width `W`, and depth `D`, subtract
  `D * max(0, 1 - (d/W)^2)^2`. This is not shortest distance to a curved river;
  width is measured in the x direction. The source heightfield remains unchanged.
- Slopes use centered physical derivatives in the interior, one-sided at edges,
  then `degrees(atan(hypot(dx, dz)))`.
- TPI subtracts a square neighborhood mean. A summed-area table makes every
  neighborhood query constant time; the whole measurement stage is O(n²) for
  an n-by-n grid instead of O(n² r²). Boundary windows clip and can bias TPI;
  adjacent-region halos are future work. The requested radius rounds to cells.
- Noise wavelengths smaller than twice cell spacing are omitted. This does not
  fully band-limit the nonlinear ridge transform. Gorge half-width below three
  cells gets a warning. Increase resolution to assess steep terrain accurately.
- Tests independently check a plane's analytical slope, brute-force neighborhood
  means including borders, exact carving depth/support, repeatability, stage
  isolation, finite arrays, invalid inputs, exports and sampling warnings.

## Initial performance evidence

Windows 11, Python 3.12.10, default configuration, one warm-up and three measured
runs per resolution: median totals were 37.73 ms at 65², 149.41 ms at 129², and
594.24 ms at 257². All three resolve five octaves. Noise accounted for about 93%
of total time. Approximately four times the cells cost four times the time here.
The machine-readable benchmark includes configuration, Python/platform metadata,
stage medians and total min/max. These are local measurements, not engine budgets.

Next performance experiments: cache noise gradients or vectorize the noise stage;
cache unchanged base terrain when only carving changes; measure memory and browser
serialization separately; compare resolutions with fixed resolved octave counts.
No hardware-dependent timing threshold is used as a unit test.

## Explicit scope boundary

The gorge is a controlled feature, not a downhill river: its bottom may rise
downstream. There is no erosion, ocean, climate, water balance, settlement, road,
cave, or overhang model. Elevation zero is an arbitrary datum, not sea level.
Next add drainage with outlet/flat handling, conservation checks and longitudinal
profiles; then add climate and suitability layers using the same physical grid.
The lab makes no claim that a dramatic-looking canyon has realistic hydrology.

Validation/review: `docs/reviews/2026-09-09-terrain-math-lab.md`.

## Globe mode and two seed APIs

```powershell
python tools/terrain_lab.py --serve --shape globe --size 129
python tools/terrain_lab.py --shape globe --prompt "A world of mountains and deep gorges"
```

World shape switches between Plane and Globe. Globe replaces plane width with
planet radius; noise scale, heights and gorge widths stay in metres. Drag to
rotate, or use rotation/tilt/zoom controls. View switches to a latitude/longitude
atlas for point inspection and latitude cross-sections. Preview triangles are
limited to 64 segments per axis; exports and diagnostics retain full resolution.
Globe colors indicate the chosen numerical layer, with lighting; they are not
biomes or oceans. Heights displace the surface radially at actual height/radius.

Spherical generation samples 3D gradient noise at Cartesian points on the reference
sphere, then displaces radius by elevation. Longitude endpoint samples match
exactly, and each pole has one height. The export is still a square array with
duplicate longitude endpoints: x spans -180..180 degrees, z spans 90..-90 degrees.
Its cells are NOT equal area; polar samples cannot receive equal weight in future
global climate, resource or population sums. Sphere topology is explicit in JSON.
Globe generator version is 2; the original plane algorithm remains version 1.

Globe gorge carving is a periodic latitude-band profile, not a routed river.
Slopes use finite differences sampled along great circles relative to the reference
sphere. Globe TPI subtracts the average of eight interpolated samples on a
geodesic ring, which differs from the plane's square-area neighborhood mean.
The ring radius clamps to one latitude step through a quarter-circumference;
the effective radius is exported. Future production analysis needs a proper
area-weighted neighborhood and a less distorted mesh such as a cubed sphere.

Choose Manual number or Prompt → number under Seed source, then Generate terrain.
The browser calls these localhost APIs (JSON POST bodies):

- `/seed/manual`: `{"seed":42}` → numeric seed and `manual-u32-v1` method.
- `/seed/prompt`: `{"prompt":"A world of mountains and deep gorges"}` → seed
  `1014459558`, method `sha256-nfc-u32-v1`, and full SHA-256 digest.

Both produce unsigned 32-bit seeds. Prompt conversion normalizes Unicode NFC,
CR/CRLF to LF, and trims surrounding whitespace. It preserves case and internal
whitespace. SHA-256 hashes `icarus-terrain-prompt-v1` plus a NUL separator plus
normalized UTF-8 text; the first four digest bytes are a big-endian seed. Prompt
length is 1..4096 characters before normalization, with blank input rejected.
Hash collisions are possible in a 32-bit seed space. Words do not semantically
set biomes or mountain counts. No external model/API is called.

Copy the returned number into Manual to reproduce the same world with the same
configuration. Browser/CLI prompt exports retain the hash method and digest;
raw prompt text is not included in exports. Direct `/generate` accepts the resolved
numeric seed. Saved reports can rotate/switch layers without a server, but seed
conversion and regeneration need the live server.

Globe timings on the same machine, three measured runs after warm-up: 100.8 ms
at 65² (two resolved octaves), 475.7 ms at 129² (three), and 2218.2 ms at 257²
(four). These are not fixed-work resolution comparisons: more detail becomes
resolvable as spacing decreases. At 129², noise took 218.7 ms and measurements
251.2 ms. Precomputing spherical sampling coordinates/weights is a promising
optimization. Memory/export/browser costs remain separate from these numbers.

## Three tectonic phases (generator version 3)

Start with `python tools/terrain_lab.py --serve --shape globe --tectonics 1 --phase 1`.
Choose **Generate through** and press Generate terrain. Phase-specific controls
appear as they become relevant; regeneration always selects that phase's default
layer. Legacy noise and the earlier controlled gorge remain a separate model.

1. **Layout:** seeded spherical Voronoi plate ownership, unit plate centers,
   dimensionless angular velocities, a separate smooth continental-affinity field,
   nearest-two boundary distance, convergence/divergence/shear potentials. Globe
   colors identify plates and center arrows show local motion. No terrain relief
   or slope calculation runs. Controls: plate count (3–48), layout variation
   (uint32), continental bias (-1..1), radius and resolution. Continental affinity
   uses a coarse seeded noise field to distribute crust; it is separate from
   phase 3's surface-detail noise. Plates can contain both crust types.
2. **Interactions:** baseline crust elevation plus broad collision uplift, rifts,
   spreading ridges, subduction trench profiles and volcanic-arc potential. Relief
   scale is metres; belt width is a fraction of planet radius (.01..0.3). The more
   continental sampled side is treated as overriding: this is a simplified static
   rule, not an age/density/subduction simulation. Shear is diagnostic only; no
   transform displacement. No hotspots or individual volcanic cones yet. The
   cross-section compares crust baseline to tectonic elevation.
3. **Surface noise:** adds independently seeded 3D noise to tectonic elevation.
   Amplitude is modulated from 20% in plate interiors toward 100% near selected
   boundaries. Controls: detail variation (uint32), noise amplitude/scale/octaves,
   ridge mix. Noise height zero reproduces phase 2 exactly. The cross-section
   compares tectonic elevation to final elevation.

The world seed deterministically derives separate SHA-256 child seeds for plate
layout, crust and surface detail. Layout variation affects plates and crust;
detail variation affects only surface noise. Increasing relief does not reshuffle
plate ownership. Full configuration, resolved child seeds, plate vectors, phase
number and generated layers are exported. Phases 2 and 3 retain earlier layers
for inspection. Globe relief budget is conservatively bounded by
`5 * tectonic_relief + 2 * amplitude < 0.9 * globe_radius`, counting only active
phases; inactive future controls do not prevent phase 1 generation.

This is a **static, tunable geological approximation**. Elevation below zero is
a potential ocean basin, not a water simulation. Nearest-two boundaries can
create artifacts near multi-plate junctions and when selected neighbor/polarity
changes. An area-uniform mesh, blended junction treatment and crust-history rules
remain candidates for refinement. Do not interpret cell counts as surface areas.
No conservation, erosion, lake filling or realistic timescale is claimed.

Verification includes analytical relative-motion signs, shared-rotation invariance,
profile direction/falloff, phase isolation, noise-zero equivalence, seam/pole
consistency and preservation of earlier layers when downstream knobs change.

At 129² with default parameters, three local runs after warm-up had median totals
of 372.5 ms through layout, 635.9 ms through interactions, and 881.6 ms through
noise. Phase 2 relief itself cost only about 9 ms; most additional time was curved
surface diagnostics. A full phase 3 run spends about 378 ms rebuilding layout,
229 ms on noise, and 261 ms on diagnostics. Upstream caching and precomputed
geodesic sampling are the next clear efficiency experiments. These measurements
exclude JSON, disk and browser costs; `Artifacts/terrain-lab/phase-benchmark.json`
records this run. Current code deliberately recomputes rather than caching mutable
arrays, so stage timings describe actual work performed.

After experimenting, choose the next stage based on the observed problems:
drainage/basin handling for rivers and lakes, or better tectonic transitions if
mountain belts and junctions still look artificial. Neither is implemented here.

## Continental shape and typical land scale (tectonic generator version 4)

The current default is a small-world preset calibrated for **roughly 20 km² of
total land on average**, not a per-seed target. One shared `world_scale` of
0.17744123532462844 applies to every seed. Different worlds retain different
land areas. Changing terrain/crust/sea-level settings can change that average.

Calibration used default v4 phase 3, 129² samples, seeds 0–31: mean 20.00 km²,
range 14.03–24.83 km². Independent holdout seeds 32–47: mean 18.65 km², range
15.76–20.94 km². These finite samples establish an approximate preset, not a
distribution-wide guarantee. Machine-readable runs are in
`Artifacts/terrain-lab/scale-calibration.json` and `scale-holdout.json`.

Area is computed from spherical latitude-band weights, excluding the duplicate
longitude seam. Each sample represents its latitude/longitude footprint; samples
strictly above sea level count as land. Total weights integrate to `4πR²`, and
polar samples carry less area. The coastline is resolution-dependent. This is
reference-sphere footprint, not sloped surface area, one connected island, or
walkable space. Submerged samples are a sea-level mask, not a hydrology solver.
The **Land / submerged** layer and area readout make the classification visible.

Controls marked **design m** specify the unscaled mathematical model. Physical
world scale multiplies all dimensional parameters, elevations and distances after
generation. It preserves slopes, angular layout, seed differences and land
fraction. `config` retains design inputs for exact regeneration; `effective_config`
contains physical metres, and `topology.radius_m` is the physical radius. The
default physical radius is about 1.774 km. `area` reports the generated land area.
There is no automatic per-seed fit, area lock, or ocean quota.

**Display relief** is a separate browser-only multiplier of radial displacement:
`rendered radius = physical radius + display multiplier × height`. Default 0.25×
makes the small globe easier to inspect; 1× shows actual physical proportions.
Zero makes the silhouette spherical while retaining terrain colors. Controls,
area, slopes, profiles and JSON retain actual physical heights. The slider caps
exaggeration to prevent negative displayed radii. It is not part of world state.

The v4 continental transfer profile replaces the old linear height mapping with
smooth ocean-floor, continental-slope, shelf and interior segments. Interior
height variation is much smaller, while uplift remains a separate contribution.
Mountain structure modulates collision belts in a stable plate-pair frame, using
cross-belt ridges and along-belt peak/pass variation. Setting Mountain structure
to zero restores a smooth collision belt. It does not reshuffle plates.

This increment does not implement erosion, sediment transport, improved junction
blending, water connectivity, climate or a physically calibrated crust model.
`area_scale` timings include physical scaling and land measurement in total time.


## Human-scale patches (patch version 1)

The globe preview now offers 64, 128 (default), or 256 segments per axis, capped
by the actual sampled world grid. This exposes more existing vertices; it does
not invent extra geological detail. The default global equatorial spacing is
about 87 m. A uniformly sub-metre whole-planet grid would be unnecessarily large
for this local inspection experiment.

Below the world controls, Human-scale terrain patch samples a selected latitude
and longitude. Find land location chooses a sampled above-sea-level location,
with a preference for gentler terrain near longitude/latitude zero. Clicking the
world atlas copies coordinates into the patch controls. Generate local vertices
uses the last generated world config, not unsubmitted edits to world controls.

Defaults: 64 m width, 0.5 m reference-sphere vertex spacing, 0.4 m micro-relief
amplitude and 8 m wavelength. Patch span is 4–512 m, spacing 0.1–8 m, and the
maximum grid is 257² vertices. Actual spacing is span / ceil(span / requested
spacing), displayed after sampling. The patch is bounded to half the planet
radius and micro-relief to one percent of radius. The mesh view retains spherical
curvature and physical proportions; the global display exaggeration is ignored.
The 1.8 m human marker is an overlay at the center, not a collision-tested avatar.

A tangent-plane offset of length d maps to the sphere with angle d/R:
`p = center*cos(d/R) + tangent_direction*sin(d/R)`. The final coarse heightfield
is interpolated there. Independently seeded, world-space 3D Perlin adds micro
relief in physical metres. Sampling the same position at nested resolutions
returns the same height. If detail wavelength is below two local samples, it is
omitted and reported. This is one fine noise band; it does not re-evaluate the
large-scale geology or drainage at sub-metre resolution. Small relief can change
local shoreline classification, but the global area mask is deliberately not
recomputed from a single patch.

POST `/patch` accepts `{config: <world config>, patch: <patch controls>}`. It
regenerates the world deterministically, then samples the patch; this avoids
stale server state, at the cost of rebuilding the coarse world on every request.
The shown patch timing excludes coarse regeneration, encoding and rendering.
The observed default patch sampler took about 190 ms locally before browser
rendering. No engine frame-time claim is made.

Export patch mesh JSON contains row-major `local_x`, `local_y`, `local_z` in
metres, radial `height`, added `detail`, and outward-facing `triangle_indices`.
Flatten each coordinate grid in row-major order to reconstruct vertices. Local
axes are east/up/north; origin is the terrain point at the patch center. Config,
world-generator version, patch version and detail seed are included. Exported
triangle winding is tested. Patch export is separate from the coarse globe JSON.

This is a foundation for player-centered terrain chunks, not an implemented
streaming/LOD or character controller. Neighboring chunks still need a shared
sampling lattice and edge stitching before engine assembly. Coarse heightfield
interpolation can expose slope changes at source-cell boundaries. Detail
normals, collision, local erosion and walkability remain later engine/model work.


## Terrain colors and landmarks (classification version 1)

Terrain colors is the default diagnostic on the final generated globe stage.
Categorical colors distinguish submerged terrain (blue), tundra (muted pale),
desert (tan), grassland (light green), forest (medium green), rainforest (deep
green), exposed rock (gray), and snow (white). The legend names every category;
atlas inspection reports the category name. Triangle colors choose a categorical
sample instead of interpolating numeric IDs. Globe shading is deliberately weak
for biomes, preserving the meaning of the shades.

Classification is an artistic climate approximation, not weather simulation.
Temperature is `28 - 45*sin(latitude)^2 - 0.0065*max(0,height_above_sea)` plus
the temperature-offset control. Moisture is a bounded latitude and independently
seeded 3D noise field plus moisture bias. There is no rainfall, evaporation,
prevailing wind, ocean-distance model or rain shadow in this first pass.
Submerged samples take precedence; then temperature <= 0 gives snow, slope >=38
exposed rock, temperature <5 tundra, moisture <0.3 desert, warm (>=20) and very
moist (>=0.78) rainforest, moisture >=0.55 forest, otherwise grassland. Rainforest
and persistent-snow labels express this simplified classification only.

Landform remains a separate layer: submerged, plain/hillside, mountain/ridge
(height above sea >30 m and TPI >12 m), or valley (TPI <-10 m). A forested ridge
keeps its green biome color. Grassland is vegetation, not a guarantee of flatness.
All height thresholds use scaled physical metres. Temperature and moisture
controls change classification, not generated elevation, erosion, or area.

Small drawn mountain, tree, cactus and snowflake symbols identify representative
ridge/forest/dry/snow regions. Selection is deterministic, limited to six per
kind and separated by at least 0.24 radians across all kinds. These are regional
markers, not actual vegetation objects or a claim of geologically unique peaks.
Globe rendering hides back-facing markers and suppresses screen overlaps. The
Terrain landmarks checkbox toggles them on the colored globe and atlas.

Export adds temperature, moisture, biome, landform arrays and a `terrain` object
with classification version, category names/colors, method, and feature locations.
Terrain generator version remains 5 because geometry is unchanged; classification
has its own version. Classification runs after physical scaling and is timed
separately (about 150 ms locally at 129²). Local human-scale patches still inspect
geometry; this classification does not recalculate their fine vegetation cover.


## Stage 5: connected water (water model version 1)

Launch through `--phase 5` (now the default phase). Stage 4 ground elevations and
sediment accounting are unchanged. Water runs afterward in physical units, using
the same unique-pole, wrapped eight-neighbor spherical graph. Components at or
below sea level are measured by spherical area; the largest component is the
chosen ocean. Other disconnected basins may become inland lakes, even if their
floors are below sea level. This is an explicit ocean-selection convention.

A priority flood expands from ocean nodes at sea level. The minimum escape level
for each visited node is `max(ground_height, parent's_escape_level)`. Positive
escape-level minus ground-height is equilibrium water depth. This finds inland
spill elevations rather than forcing lakes to sea level. The model assumes enough
water to fill depressions to overflow; it does not predict lake volume from a
rainfall budget or simulate filling over time. In an oceanless world the global
minimum is a terminal outlet; no ocean is invented, and terminal basin water
supply is not predicted.

Routing chooses the steepest descent on the spill surface where available and
uses flood-parent links on flats. Receivers precede their children in flood order,
so the graph is acyclic. Reverse traversal accumulates reference-sphere catchment
area under uniform unit runoff, conserving total area at terminal outlets. Lake
interiors participate in routing, connecting upstream and downstream catchments.
Dry nodes exceeding River catchment (default 0.15 km²) draw cyan river segments.
Smaller values show more tributaries. These are routes, not river-width geometry
or measured flow rates. Earlier erosion is not rerun with these new routes.

Connected water colors dry ground green, ocean blue and lakes turquoise. Terrain
colors incorporates lake classification; vegetation landmarks avoid flooded cells.
The fifth-stage preview uses the water/ground surface for colored maps, while
Final elevation retains ground geometry. Cross-sections compare ground to the
water/ground surface. Globe river overlays clip back-facing segments; atlas lines
wrap across the longitude seam. The coarse grid still makes routes angular.

Exports add water_type (0 dry, 1 ocean, 2 lake), water_depth and water_surface in
metres, routed_catchment in m², river mask, and a water object with unique node
coordinates, receiver indices (-1 terminal), and river endpoint indices. Lake
capacity is the approximate sum of column depth times nodal footprint, in m³.
Ocean/lake/dry km² form a disjoint partition of the sphere. The earlier area field
still measures height above sea level; it is not redefined or fitted to 20 km².
Dry-ground area excludes lakes but not unmodelled river widths or flooded banks.

Default seed 42 at 129²: ocean 22.52 km², lakes 0.63 km², dry ground 16.41 km²,
about 3.15 million m³ equilibrium lake capacity, and 114 river segments with the
default threshold. Water processing took about 214–228 ms locally, excluding
JSON/browser work. Graph storage is O(N); priority-flood routing is O(N log N).
The classification version and geometry version remain independently exported;
water version 1 identifies this additional model. Lake freezing, rain shadows,
evaporation, water-budget dynamics, and game collision surfaces remain future work.


## Stage 6: wind, rainfall and rain shadows (climate version 1)

Wind toward is a compass bearing: 90 degrees travels east, 270 west, zero north.
This is a fixed direction field, not pressure-driven weather or planetary
circulation. The poles use a deterministic local frame. Each node traces one
reference-sphere equatorial grid step upstream and bilinearly samples humidity.
Upstream interpolation weights are precomputed on the unique spherical nodes.

Humidity starts dry. On every pass, water nodes replenish 45% of the remaining
humidity capacity. A loss fraction `min(0.85, 0.06 + rain_strength*upwind_rise/150)`
becomes relative rainfall; the remaining humidity advects on the next pass.
Upwind rise uses physical metres on the water/ground surface. Thus a ridge rains
out moisture on its windward side, leaving less for its lee. Mountain rain
strength 0 retains background precipitation but removes the uplift term.
Default 48 passes is tunable from 1–128. The final max humidity change is exported
and shown as a residual; fixed passes do not guarantee steady-state convergence.
It is not a simulation of elapsed hours, yearly rainfall, or a conserved global
water/energy budget. All equilibrium lakes can supply moisture, including cold
ones; freezing and temperature-dependent evaporation remain future work.

Biome moisture now uses `rain/(rain+0.025)` plus the moisture bias, clamped to
0–1. Temperature remains the earlier latitude/elevation field. Classification
version 2 distinguishes this from seeded moisture patterns. Raw humidity,
rainfall, uplift and moisture are inspectable. Gold globe arrows show wind.
Stage 5 uniform-runoff routes remain unchanged in its export and view. Stage 6
accumulates `nodal_area * relative_rain / 0.04` on those receivers, conserving
this equivalent input at outlets, and thresholds it for rain-fed river routes.
The field is m²-equivalent runoff, not m³/s. Lake boundaries/capacities and ground
are not recomputed from rain. Erosion does not rerun with the new flows.

## Stage 7: settlement suitability (settlement version 1)

Candidates are dry grid nodes with slope below 35 degrees. Freshwater distance
is a multi-source graph distance from lakes and rain-fed rivers, excluding ocean
traversal. This is potential access, not proof of potability: lake salinity,
seasonal flow and springs are absent. Missing sources export null in a site
record and -1 in the distance grid, keeping JSON finite and explicit.

The score combines 30% freshwater proximity, 25% gentle slope, 20% temperature
comfort, 15% moisture suitability and 10% seeded resource potential, minus up to
25% flood-risk penalty. Water distance decays over 400 m; slope preference is
`exp(-(slope/12)^2)`; temperature preference peaks at 18 C. Flood risk combines
proximity to freshwater and height above the nearest source; it is not a flood
hydraulic or coastal storm-surge model. Resources are seeded hypothetical
potential, not placed mineable deposits.

Seeded jitter adds at most 0.06 to selection rank. Greedy selection preserves a
minimum reference-sphere separation (default 450 physical metres). Count is 0–24.
Stubborn outposts reserves a rounded fraction of the count for resource-oriented
sites with low score, distant water, cold temperature or steep terrain. Water and
the 35-degree exclusion remain hard constraints. If difficult sites are not
available, remaining slots use ordinary sites; if spacing/terrain prevent the
requested count, fewer sites are returned. No per-seed area or population fitting.

Numbered house markers match the proposal cards. Each card reports score, water
access, slope, temperature, flood proxy, resource potential and selection reason.
Clicking a name centers the globe and sets the human-scale patch coordinates.
Names and Town/Village/Outpost labels are deterministic placeholders, not built
settlements, NPCs, an economy or a building-layout simulation.

## Stage 8: terrain-aware road proposals (road version 1)

Shortest paths use spherical grid-edge distances and absolute height change.
An edge is forbidden if either endpoint is water, a diagonal cuts a water corner,
or `abs(height_change)/reference_arc_length` exceeds Max road grade (default
0.35 rise/run). Grade is a coarse horizontal-distance approximation, not an
engine-verified road surface. Allowed edge cost is distance multiplied by
`1 + 12*grade² + 0.5*(endpoint_flood_risks_sum)`, plus the River crossing cost
(default 200 equivalent metres) where either endpoint is on a rain-fed river.

One Dijkstra search per site computes pairwise feasible routes. Kruskal selection
then builds a minimum spanning forest of those terminal-to-terminal routes.
Unreachable sites/islands stay disconnected. Tan lines show roads; cream segments
are river-crossing candidates, not engineered bridges. There are no ocean/lake
bridges, tunnels, ferries or automatic terrain cuts. Roads may share grid edges;
the UI reports the sum of route lengths, not a deduplicated network length.
Receiver/water node indices also index each exported road path. Road records
include endpoint site IDs, path nodes, length, cost and river-crossing edges.

### Verification and performance

Tests compare windward/lee rainfall to a flat fixture, dry-source behavior,
reversed wind, downstream-control isolation, catchment input/outlet sums,
barrier-avoiding paths, site separation, dry placement, route endpoints and grade,
seam/pole consistency, and zero-site behavior. Additional smoke cases: all-water
world gives no sites/roads; dry flat world gives zero rainfall; strict 1% road
grade gives six disconnected proposals with no roads. These are model checks,
not physical-climate validation or navigation-mesh certification.

At 129², default seed 42 proposes six sites (one outpost), with five road routes.
Climate residual is about 0.0031 after 48 passes. A one-repeat benchmark after
warm-up measured 0.77 s at 65², 3.55 s at 129² and 15.16 s at 257², excluding
JSON and browser rendering. At 129², climate took 0.71 s, sites 0.35 s and roads
0.095 s. Results/config are in `Artifacts/terrain-complete-benchmark/benchmark.json`.
These are local observations, not statistical or engine frame-time guarantees.

Climate work scales with passes times vertices. Road searches scale with site
count times graph-search work. Rebuilding the same spherical neighbor geometry
in multiple stages and coarse-world regeneration on every patch request remain
clear caching opportunities. Stage inspection itself reuses generated results.
The UI retains all eight stages, exports versioned model metadata, and makes no
changes to Unity gameplay, game saves, collision or assembled terrain chunks.


## Stage 9: human cities, hinterlands and culture IDs

Run `python tools/terrain_lab.py --serve --shape globe --tectonics 1 --phase 9`.
All primary pins are now **cities**, including those in difficult terrain. The
existing `outpost` boolean remains an origin/placement trait, not a different
settlement class. Settlement metadata is version 2; city coordinates, roads and
all earlier terrain fields are unchanged by stage 9. The new `humans` section is
version 1. These exports are lab snapshots, not game saves.

The stage adds farming/resource hamlets, route-defence fortresses, relative supply
budgets, intercity food exchange and seed-local culture IDs. The six controls are
hamlets per city, total fortress count, supply reach, culture link cost, city food
demand and irrigation capability. Distances are physical cost-metres using the
same road cost function as stage 8. They do not change with display exaggeration.

### Rural supply and adaptation

Multi-source Dijkstra assigns each reachable dry node to one city, following
existing grade/water restrictions. Hamlets must be 100 cost-metres away and within
`support_reach` (default 1,000), on slopes below 20 degrees. They are separated
from all previously placed sites by at least 120 physical metres. Up to three
hamlets per city are requested by default: two farming and one resource-focused.
Selection is deterministic and may yield fewer where suitable sites are absent.

Natural exportable food potential uses:

```
terrain = exp(-(slope/14)^2) * max(0, 1-abs(temperature-18)/24) * (1-0.7*flood)
natural = terrain * max(0, 1-abs(moisture-0.65)/0.65)
water_access = exp(-freshwater_distance/400), or 0 when unavailable
irrigation = capability * water_access * max(0, (0.65-moisture)/0.65)
adapted = natural + 0.75 * terrain * irrigation
```

The irrigation increment includes a maintenance discount. It cannot invent water
in a dry world. It is an opportunity proxy: aquifers, extraction capacity, canal
engineering, water rights and allocation between farms remain unmodelled.
Natural and adapted potential can be inspected separately without changing biomes.

A second multi-source traversal gives each hamlet an exclusive catchment within
250 cost-metres, constrained to its city's hinterland. Nodes contribute only once;
city nodes and slopes at or above 20 degrees do not contribute. Worked area is
latitude-weighted reference-sphere area, not a drawn building footprint.

```
delivered_food = sum(100 * area_km2 * adapted * exp(-city_access_cost/support_reach))
```

Resource hamlets produce one-quarter of that food, while farming hamlets produce
one-quarter of the analogous resource output. These are **relative exportable
surplus units after assumed rural subsistence**, not people, tonnes, historical
yields or a prediction that a full-size city fits in this miniature world.

Cities request 10 food units by default. Cities with deficits can purchase finite
local surpluses along the existing city-road graph. Buyers are processed by
largest initial shortage, then ID; donors are considered by lowest transport cost.
For path cost C, delivery efficiency is `exp(-C/4000)` and material cost per received
unit is `0.2+C/5000`. Donors retain their own demand; exports are deducted only once;
buyers cannot exceed their available material potential. Imports cannot be re-exported
in this single pass. Remaining shortages are explicit. This is a logistics/barter
proxy, not a market-price, road-capacity or currency simulation.

### Fortresses and culture regions

Up to four fortresses are proposed near city-road nodes. Junctions and river
crossings add strategic weight; positive TPI adds an elevated-surroundings bonus.
Local slope and flood risk reduce suitability. Access must obey the road rules,
slopes must be below 20 degrees, and each fortress must be at least 200 metres
from existing sites. Exported reasons, protected road node and access path make
these decisions inspectable. They do not model sight lines, enemies, siegecraft,
or garrison food demand. Metre-scale walls, baileys and keeps are produced later by
the independent [castle planner](castle-planner.md) as `castle_plans`, not by this
placement stage.

Culture formation works backwards from the city graph: join existing road links
whose cost is within `culture_link_cost` (default 1,800). Each connected group gets
`human-<seeded ID>` and `architecture_style_id: null`. The ID uses the world seed
and lowest member city index. It is stable for repeated identical generation,
not guaranteed to persist across changed city layouts or group thresholds.
Single-link grouping permits chains whose endpoints are farther apart than the
threshold. Roads between different cultures remain usable for trade.

The culture overlay colours each city's reachable hinterland by its group. Dark
cells are unassigned wilderness or water. These are provisional interaction regions,
not ethnicity, nationality or political claims. No historical style is hard-coded.
Changing the culture threshold does not move cities, hamlets, terrain or roads.

### Historical design references

The model uses mechanisms from several settings without assigning one culture's
social structure to all humans. The Smithsonian describes Inka roads, storehouses
and terrace farming in [The Great Inka Road](https://www.si.edu/newsdesk/releases/inka-road-remains-monumental-achievement-engineering-after-500-years-continuous-use).
UNESCO describes how [Persian qanats](https://whc.unesco.org/en/list/1506/) supported
agriculture and settlement in arid regions, and water management's role in extensive
settlement at [Petra](https://whc.unesco.org/en/list/326/). These motivate adaptation,
storage and exchange as future levers; no claim is made that our equations reproduce
those societies. Fortresses use general route/crossing considerations also described
in [Medieval Castle](https://www.worldhistory.org/Medieval_Castle/).

Default 129-grid observations: six cities, sixteen hamlets, four fortresses and
three culture groups. Generation was about 3.5–3.8 seconds, with roughly 0.23 seconds
in stage 9, excluding JSON transfer and rendering. These are single-run observations.
The default food demand deliberately exposes shortages instead of changing the land
or forcing enough farms into unsuitable places.


## Leylines, magical ecology and human safety

Fantasy is enabled by default on the tectonic globe from stage 6 onward. Set
`magic_enabled=0` for natural ecology, including ordinary marshes. Magic is
computed after climate and before biome classification: stage 6 exposes its
fields, stage 7 cities respond, stage 8 roads avoid unsafe areas, and stage 9
adds wizard colleges. The existing nine-stage sequence is retained.

The controls are ley node count (3–24, default 10), influence reach (10–2,000
physical metres, default 180), instability (0–1, default 0.85), human mutation
limit (0–1, default 0.45), and college count (0–12, default 2). Preview relief does
not change any of these measurements. Fantasy enablement and safety controls
require regeneration; Show leylines only changes the overlay.

### Network and fields

A separate seed stream places spaced unit vectors on the globe. A minimum-distance
spanning tree and second-nearest-neighbour links form a sparse connected network.
The current network is independent of plates and cities; tectonic attraction is
not implemented. Each link follows a minor great-circle arc with strength,
instability and growth/destructive affinity. Node placement has a bounded retry
count. Exported arc paths are preview samples; influence uses distance to the
actual arc, including endpoint distance when the nearest great-circle point is
outside the segment.

For distance d_i to line i, physical width w and line strength A_i:

```
weight_i = A_i * exp(-(d_i/w)^2)
density = 1 - exp(-sum(weight_i))
growth = sum(weight_i * growth_affinity_i) / sum(weight_i)
hazard = density * weighted_line_instability * magic_instability
```

Fields are in 0–1; zero influence has zero affinity. Growth affinity is currently
0.1 or 0.9 per line, blending spatially where influence overlaps. Independent
instability lets equally dense regions have different danger. The model has no
mana conservation, temporal surges, factions, wards or physical terrain deformation.
Ground, oceans, lakes and rainfall remain unchanged by magic.

Lavender lines indicate growth, rose lines destructive affinity; gold dots are
nodes. Separate density, mutation-hazard and growth-affinity diagnostics reveal
why the biomes and human sites differ. Arc overlays use front-side clipping and
sampled ground elevation, not terrain-ray occlusion.

### Biome rules

Ocean and lake classifications always win. Ordinary marshes are unfrozen land
with moisture >=0.55, slope <6 degrees, within 180 physical metres of mapped water
or river, and 0–4 metres above that nearest source. The proximity traversal uses
sphere-grid distances. This is a wetland opportunity proxy, not water-table, peat,
salinity, seasonality or soil-saturation simulation. Marshes can exist with magic off.

In priority order after water:

- Marsh becomes Haunted marsh when density >0.3 and growth affinity <0.5;
  otherwise it stays Marsh. Haunting itself does not imply unsafe mutation.
- Desolation requires density >0.4, hazard >0.3 and growth affinity <0.5.
- Crystalline desert requires density >0.35, hazard <0.3, moisture <0.4,
  temperature >5 C and non-rock terrain.
- Fungal forest requires density >0.6, growth affinity >0.55, moisture >0.65,
  temperature between 0 and 35 C and non-rock terrain.
- Enchanted forest requires density >0.3, growth affinity >0.55, moisture >0.4,
  temperature between 0 and 35 C and non-rock terrain.
- Otherwise ordinary climate classification remains.

Biome IDs 9–14 are Desolation, Fungal forest, Crystalline desert, Enchanted forest,
Marsh and Haunted marsh. Colours and sparse regional icons appear in globe and
atlas. Thresholds are artistic rules, not scientific predictions. Not every seed
or grid must contain every biome. Desolation retains 5% of ordinary human farming
potential, fungal forest 50%, crystalline desert 15%, and either marsh 35%; all
human crop output is also reduced by `(1-hazard)`. Magical food species are not yet
modelled, and enchanted forest has no invented food-production bonus.

### Colleges and safety

City candidates must have mutation hazard <= the human limit, regardless of their
difficult-site placement trait. Their suitability also receives a `0.2*hazard`
penalty. Roads, hamlet access, fortress access and college access use the same
hazard exclusion, including diagonal corner checks. A hard limit is a lab tuning
choice, not proof of habitability between coarse vertices.

Colleges seek strong magic but must independently satisfy all of:

- Density >=0.35; mutation <= the same human limit.
- Dry ground, slope <15 degrees, temperature strictly between -5 and 38 C.
- Mapped freshwater distance 0–600 metres, flood proxy <0.5, human suitability >=0.55.
- A safe terrain route to a city within the supply reach; 150 metres separation
  from existing cities, rural sites and colleges.

Candidates rank by `density*(1-hazard)+0.25*suitability`. Their output records the
host city/culture, density, hazard, suitability, access path and reason. A haunted
marsh is neither automatically accepted nor automatically rejected; it must pass
all human checks. Colleges get no ward exemption. They are institutions with no
separate staff, food demand or building mesh yet. Counts are maxima, not guarantees.

Metadata: magic v1, terrain classification v4, settlements v3, roads v2 when magic
is active, and human hinterlands v2 when magic is active. Geometry remains v5.
These are lab exports, not changes to game-save schemas.

Default 129-grid verification found all six new biomes and two colleges, with
10 ley nodes and 13 arcs. Full generation was about 4–4.5 seconds in observed runs;
leyline evaluation was roughly 0.5–0.6 seconds and colleges 0.2 seconds. Costs scale
with grid nodes times ley edges; these are observations, not guarantees. Setting
instability and human hazard limit both to zero still yielded two colleges.


## Compact world recipe and population permutations

The CLI and served math lab now default to **derived mode**. The normal form has
only population profile, generation stage, world seed and preview grid size, plus
the existing numeric/prompt seed-source selector. Display controls are independent
of generation. Detailed notes and settings are collapsed. Expert mode is available
inside **Expert overrides and derived settings**; select it and Generate to use
explicit low-level values. The Python `Config` constructor keeps `auto_parameters=0`
for existing low-level experiments/tests. The CLI defaults this switch to 1.

```
python tools/terrain_lab.py --serve --seed 42
python tools/terrain_lab.py --serve --seed 42 --population_profile woodland
python tools/terrain_lab.py --serve --auto_parameters 0 --shape globe --tectonics 1 --ley_nodes 18
```

Derived mode is a globe recipe: it supersedes explicit shape, plate, noise, weather,
magic and settlement knobs. Only seed, profile, grid size and stage are recipe
inputs. Expert mode preserves direct parameter experiments. Existing validation
still rejects malformed/out-of-range input before derivation.

### Where the settings come from

Recipe v1 uses separate child-seed streams for geology, climate and magic. It
selects plate count, crust bias, relief, wind, climate offsets, ley node count and
instability deterministically. Noise amplitude comes from tectonic relief; belt
width and noise wavelength depend on plate count; ley reach depends on physical
radius. Moisture iteration count follows grid resolution. Other fixed numerical
solver constants remain recipe constants, rather than being presented as choices.
The denser leyline preference is retained with 16–20 seeded nodes.

Later settings use actual generated results:

- River threshold: above-sea land area divided by 110, bounded to 0.01–1 km².
- Requested cities: dry land divided by the population land-per-city trait,
  capped at 24. Zero dry land requests no cities; suitability can yield fewer.
- City spacing: square root of dry area per requested city, multiplied by 0.27.
- Supply reach: spacing times 2.2 times population support capability.
- Culture link threshold: supply reach times 1.8.
- Rural sites: two food and one resource proposal per actual city.
- Fortresses: 0.75 times the number of generated road links, rounded up.
- Colleges: roughly one per three actual cities, subject to available safe magic.

The `derivation` section exports recipe version and each resolved value with its
source. The `config` section contains the resolved values and `auto_parameters=1`;
replaying it regenerates the same settings under the same recipe/profile definitions.
The local-patch request accepts this config too. In the compact UI, patch spacing is
0.5 m, micro-relief amplitude derives from physical world amplitude, and wavelength
from world grid spacing. Patch location and width remain inspection choices; expert
mode exposes the patch detail controls.

### Shared physical scale

Recipe geology changes the distribution of land, so its shared scale was calibrated
once across seeds 0–31 at grid 65. At the prior scale 0.17744123532462844, mean
above-sea land was 18.70889994 km². The recipe now uses **0.1834617044641644** for
every seed, giving 20 km² mean for that calibration cohort. No individual world is
fitted to a land target. Other seeds and resolutions vary; this is an approximation,
not a statistical guarantee. The older scale remains available in expert mode.
The calibration data is in `Artifacts/recipe-scale-calibration.json` locally.

### Population templates

Population definitions and all civilization-specific rules are authored in the [civilization master registry](civilizations.md). Each entity is a complete independent record; no human base or inheritance is supported. Presentation stays in that master; construction libraries and measured requirements live in linked buildings.json. Its revision/hash is exported in civilization report version 2 and checked before age advancement.

## Coexisting peoples and inferred capacity (006.10 / 006.11)

The server defaults to `population_profile=mixed`: the six independent human cultures, dwarves, elves, gnomes and Tidekin coexist. Normal generation exposes seed, resolution and phase; profile comparisons and manual controls remain in Expert mode. Python `Config` uses the registry default, currently Heartland humans. Registry roof colours and city cards identify the peoples. Rural sites, culture IDs and colleges inherit their host population; cross-population roads permit trade, while culture groups use qualifying same-population road links.

There are **no required city counts, one-to-two minority rolls, forced minimum city, or enforced human majority ratio**. Broad human habitat generally favours human prevalence, but the environment decides. Dwarves require mineral-rich uplands; elves require moist forest. All share exclusive site spacing and conservative surface-road safety. Missing habitat may result in no cities for a people, including humans.

For each spherical cell i and people p, calculate productive potential F_ip from the existing farming model: temperature, moisture, slope, flood risk, mapped freshwater-supported irrigation, biome food traits and mutation penalties. Unsafe, unworkable or unsuitable habitat contributes zero. This conservative first model requires productive habitat within that people's habitat gates; it does not yet let a dwarven hold import food from unclaimed distant lowlands when calculating its initial capacity.

Cell capacity C_i = cell_area_km2 * 100 * max_p(F_ip). Each people receives C_i * F_ip / sum_p(F_ip), or zero when all potentials are zero. Integrating cell capacity gives the world estimate; integrating each claim gives species allowances. Floors retain whole residents, with fractions unused. A shared cell is counted once, never once per people. The seed influences capacity through the generated environment; there is no separate seeded population-density or percentage roll.

The factor 100 residents per fully productive km2 is an explicit provisional yield/subsistence calibration, **not measured historical agricultural capacity**. Freshwater extraction volume, seasons, soil chemistry, livestock, storage losses, diets and transport bottlenecks are not fully simulated. This is an environmental support estimate; actual reachable hamlet supplies and trade still expose deficits. It is not a promise that every estimated resident is sustainably supplied.

City capacity per people is the smaller of (a) floor of quality-weighted eligible habitat area divided by the profile's land-per-city footprint and (b) floor of resident allowance / 40 regional residents. The 40-person threshold is a provisional minimum viable community size, not a city-count target. Candidate placement must still pass shared spacing and habitat tests. The lab retains a disclosed total computation ceiling of 24 cities, applied in human/dwarf/elf order, so very large experimental worlds can be truncated. No minimum or minority ceiling of two exists.

Actual cities divide their people's allowance. City estimates include about 55% urban and 45% rural dependants; hamlets, forts and colleges are locations inside those figures, not extra residents. Unplaced peoples leave their allowance unused. Hamlet ceilings follow each city's rural residents / 40 (maximum 8), fortress ceilings follow road length/support reach and unique crossing edges (maximum 24), and college ceilings follow safe dense magical area and urban residents / 100 (maximum 12). These remain candidates constrained by usable sites/access, not guaranteed institutions. The numerical thresholds are model calibration and lab limits, not extra normal UI controls.

`settlements` schema 8 and `population_budget` schema 2 expose habitat footprints, per-people allowances, requested capacities, actual counts and calibration. In addition to the city location/viability fields, each city now carries `building_pack_id`, `building_pack_seed`, and `building_pack_version` so engine-side placement can instantiate approved building families deterministically from a data-driven catalogue.
Cities also include `city_layout`, a per-city planning payload generated from the selected city layout profile:
feature targets, anchored feature slots, bridge recommendation context, and river-adapted placement constraints.
`city_layout.buildings` also carries a deterministic building option plan derived from the selected pack, including option-level counts, placements, selected assets, and aggregate required-asset list.
Core option families are now represented in packs as data: civic (leader, courthouse), residential (housing/apartments), defensive (wall/gate/watchtower/barracks), commercial (market/dock), religious (religious_building/temple), and infrastructure (granary/workshop/forge).
River-gated options anchor only on land nodes that touch river-adjacent terrain; walls use city-local perimeter candidates first, then fall back to available land anchors when perimeter extraction is not available.
Full profile definitions/hashes and per-people suitability/productivity layers remain inspectable. The `humans` legacy export key carries all peoples' society records. Outputs are regenerated lab reports, not persisted engine saves; old reports are not migrated in place.

Upstream geology/climate/magic randomness still belongs to seed streams; resolution and physical-model constants remain explicit. Earlier recipe settings that depend on dry area provide provisional spacing and reach before settlement scoring. Final city capacity replaces the preliminary count and records its source. The shared world scale still targets roughly 20 km2 land on average, never fits each seed.

Asset production stays deferred to [source Epic 008](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/epics/08-world-environment-assets.md), tracked in [the source backlog](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/board/backlog/008-world-environment-assets.md). The catalogue covers all 15 biomes and human/dwarven/elven settlement assets irrespective of which biomes or peoples appear on a particular seed.


## Seasonal food and logistics stress test (006.12)

Phase 9 now runs four repeated climatic years from empty food stores, after city, rural, road and college proposals are established. `seasonal_food` schema 1 exports all 48 monthly ledgers, derived city storage/harvest models, monthly route capacities and final-year summaries. City proposals and the earlier environmental capacity integral remain unchanged: this is a diagnostic of whether their reachable food system can support urban demand, not a migration/mortality simulation or an automatic assertion of sustainable world population.

Each hamlet's delivered exportable food becomes the reference annual supply in relative units. Monthly growing temperature follows a cosine whose amplitude depends on latitude and moisture; the two hemispheres are six months apart. Thermal suitability, freezing suppression and a one-month harvest delay produce monthly food, so seasonal conditions can change annual output rather than merely redistribute a guaranteed total. This is a simple growing-season proxy, not twelve simulated crops or a measured calendar. Rainfall remains the earlier mean moisture field; stochastic weather is not introduced here.

City storage capacity derives from its material-to-food potential ratio (up to six demand-months). Monthly spoilage ranges from 0.5% to 4% under the model's temperature/moisture bounds. Material potential also defines a renewable monthly haulage budget. These are provisional infrastructure/economic proxies, not a conserved construction-material inventory or measured warehouse capacity. Model values are exported for inspection; no additional normal lab knobs are added.

For each month: record opening food; apply spoilage; add harvest; trade; consume urban demand; discard storage overflow; retain closing stores. Donors protect current consumption plus up to one month of reserve, limited by available storage. Direct road edges have shared bidirectional throughput, derived from endpoint demand, route cost/reach, crossing count and seasonal endpoint temperature. Carriage also loses food with route cost and consumes the buyer's material budget. No same-month re-export is allowed, so a chain cannot teleport one shipment through the whole world. Route order is deterministic and greedy; this is not an optimal or multi-hop logistics solver. The earlier annual trade diagnostic does not inject additional food into the monthly ledger.

The invariant is opening + production = closing + consumption + spoilage + overflow + transit loss, summed across cities. Per-city ledgers additionally record imports/exports and material spending. Islands without roads cannot import. Roads of effectively zero delivery efficiency cannot transfer food. Food stores start empty; no free winter reserves are invented.

The city cards show year-four coverage, lean months, ending stores, reserve change and twelve monthly bars with hover details. A pass means no final-year shortage and no reserve drawdown that year; four repeated years are not proof of long-term equilibrium. The food-equivalent resident figure concerns urban demand only. Rural subsistence was already removed from upstream exportable surplus and is not independently tested seasonally here. Shortages do not silently delete residents, cities, culture IDs or terrain.

Tests cover conservation, finite throughput and material budgets, disconnected cities, zero initial stores, storage bridging a lean season, hemisphere reversal, zero-efficiency routes, deterministic report generation and phase isolation. Next extensions can model rural household demand, crop diversity, multi-hop shipments with travel time, drought histories, extraction limits and settlement adaptation before feeding a validated sustainable population back into placement.


## Population tolerance calibration (006.13)

The shared profile defaults now allow denser compact communities without forcing counts. Human quality-weighted land footprint is 1.6 km2 per city (previously 2.8); dwarven footprint is 1.0 and elven 1.2. Human temperature comfort tolerance increases from 22 to 26 degrees, slope comfort from 12 to 16 degrees, food temperature tolerance from 24 to 28 and food slope comfort from 14 to 18. Dwarves can use mapped freshwater within a 600 m characteristic reach (previously 400) and their food moisture ideal is 0.55 rather than 0.65. Derived profiles inherit the revised human defaults unless they override them.

These are global fantasy/gameplay calibration values in the profile JSON, not seed-specific tuning or new normal UI controls. Mutation limits, hard site-slope gates, ocean exclusion, exclusive capacity accounting, minimum community support and the seasonal food ledger remain in force. No demographic ratio or minimum minority count is imposed. Narrow dwarven habitat can still have too little productive capacity to form a city; this calibration does not invent subterranean food or lowland imports.

Calibration fixture: seed 42 at grid 129 yields six human and one elven city, 553 allocated residents under environmental support 580. Five additional seeds at grid 65 yielded five-seven human and three-four elven cities. These observations are not universal guarantees. The default still has an unsupported human city and an elven seasonal shortfall; increased density does not bypass viability diagnostics. A regression test checks the requested default-world balance only, alongside the existing tests proving absent habitats and zero requests do not force specialist settlements.


## Dwarven reachable hinterlands (006.14)

Supersedes the earlier restriction that all dwarven productive ground must itself be a mineral upland. Hold candidates still require mineral-rich upland, freshwater access and the existing slope/magic safety gates. Productive capacity may also come from ground reachable from those candidates within the derived support reach, using the same surface-road cost function as society. Water, excessive grade, unsafe magic and blocked diagonal corners cannot be crossed. No candidate means no dwarven support claim.

The shared capacity integral still counts overlapping land only once. `dwarf_support_reach` exposes the eligible support mask; population budget schema 3 identifies the changed semantics. These are potential hinterlands around candidate holds, not proof of supply to the ultimately selected hold. Actual exclusive hamlet catchments and seasonal trade remain the later viability test; claims around unselected candidates can still overestimate a selected city's support. No caves, subterranean farms or new food bonus are fabricated.

Default seed 42 / grid 129 now produces six human cities, one dwarf and one elf. The dwarven terrace has resource potential about 0.66 and a roughly 56 m physical elevation. Its current population estimate exceeds its actual seasonal food system: urban coverage is about 32%. The proposal stays visibly stressed rather than being presented as sustainable. Future capacity reconciliation should use realized catchments and logistics before assigning final inhabitants.


## World-size API presets (006.15)

Derived generation accepts one physical-size input: `world_size=small|medium|large`, default `small`. Small retains the current physical radius (about 1.835 km), medium uses twice that radius (about 3.669 km), large three times (about 5.504 km). Total spherical area is 1x/4x/9x. Dry land, biomes, population and settlement capacity are recalculated; land fraction and city counts are not guaranteed to scale exactly with area.

Examples: `/generate?seed=42&world_size=medium`, `/generate?seed=42&world_size=large`; CLI `python tools/terrain_lab.py --serve --world_size medium`. Seed APIs remain unchanged: they resolve the seed, which can be combined with this generation parameter. Unknown sizes return HTTP 400. Exported config includes the preset and derivation source. Existing callers that omit it keep Small.

The preset changes radius and corresponding noise/leyline horizontal scale, preserving physical relief amplitudes. `size` still means preview grid resolution, not world size. The usual 24-city lab performance ceiling remains and can constrain larger worlds. Explicit legacy Expert mode (`auto_parameters=0`) continues to use its numeric radius; presets apply to the normal derived recipe. No new population knobs are added.
