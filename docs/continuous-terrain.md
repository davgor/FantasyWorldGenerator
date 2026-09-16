# Continuous terrain data

The [portable coordinate contract](../Contracts/capabilities-and-coordinates.md) specifies radial datum, globe and local axes, city-versus-patch projections, tile indexing and strict conformance helpers. Its version 1 documents these existing exports; it does not change their bytes or generation semantics.

Algorithm 14 adds `terrain_detail` version 1 from stage 8 onward. The regional raster remains the climate, hydrology and regional settlement input. The authoritative local surface is that raster plus deterministic position-addressed relief; it is used by city planner 3, canonical patch exports and height tiles. Regenerate algorithm-13 worlds. Age replay checks detail identity as well as planner identity.

## Height function

Every unit sphere direction evaluates the same seeded 3D Perlin field. Three provisional bands have scale/amplitude pairs of 120/12, 28/2.5 and 6/0.3 metres. Amplitudes are noise coefficients, not guaranteed peak-to-peak heights. Plains receive gentler relief than exposed rock. Biome strengths interpolate continuously. Noise does not restart at city or tile boundaries, and sample density never changes the height function.

Water, river and flood masks suppress detail; near sea level a smooth 20-metre elevation ramp protects coastlines. This is intentionally conservative around coarse water samples. Regional hydrology is not rerun at metre scale; local depressions are not simulated ponds, and fine streams are not invented. Regional roads and founding still use regional geography; city streets use detailed elevations and local grades. No new asset identity is introduced.

## Resolved tile export

`python tools/export_height_tile.py WORLD.json TILE.json --level 14 --x 16000 --z 8000 --cells 64`

The JSON conforms to `Contracts/schemas/height-tile.schema.json`. At level L the globe has 2^(L+1) longitude cells and 2^L latitude cells. Indices are global, starting at longitude -180 and latitude +90. A tile contains cells+1 samples on each axis, including shared edges. Tile requests may not cross the longitude seam or a pole; request the adjacent wrapped tile separately. Seam and pole directions are canonicalized. Coarser tiles share identical heights at matching indices of finer tiles.

Rows run north to south, columns west to east. Heights are radial metres above the same reference sphere used by `layers.height`, not above sea level or a tile-local datum. Sea level may be nonzero. The export gives radius, angular spacing and equatorial metre spacing (east-west spacing decreases toward the poles). Convert latitude/longitude to unit direction `(cos(lat)*cos(lon), sin(lat), cos(lat)*sin(lon))`, then multiply by radius + height. A source SHA-256 identifies the regional height/mask data and detail parameters. Persist it with tiles to avoid mixing generations.

The engine receives resolved numbers and need not implement noise. All globe locations can be exported on demand; the world JSON stores the compact source definition rather than eagerly allocating a planet-wide sub-metre array. Engine streaming, collision construction and LOD transition stitching are adapter responsibilities. Identical samples do not by themselves solve T-junctions between differently tessellated meshes. Metres must be explicitly converted to Unreal centimetres at that boundary.

## City and lab views

City surfaces export heights at 4-metre spacing. Streets use those heights and the existing 35% grade cap. Buildability evaluates detailed local slopes; foundations inspect plot corners and covered occupancy-cell centres. This is schematic ground clearance, not structural engineering. City exports include the reference radius, centre latitude/longitude and gnomonic projection formula. Their local schematic viewer displays radial elevations vertically without globe curvature, while global tile coordinates reconstruct the sphere.

The human-scale patch uses canonical heights for algorithm-14 worlds; its old amplitude/wavelength controls are hidden and ignored for these worlds. Patch version 2 exports detailed absolute heights plus local tangent-frame mesh coordinates. Nested patches sample the same surface. Old worlds retain the legacy patch-1 behavior. Coarse meshes approximate unresolved features; choose finer sampling for walking/collision data. Preview meshes do not exaggerate height.

Tests cover seeded replay, actual local relief, protected water, exact adjacent/nested/seam tile samples, invalid bounds, shared patch heights, and city surface/slope integration. These are generator checks, not evidence of engine streaming performance.
