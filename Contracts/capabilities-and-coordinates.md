# Producer capabilities and coordinates v1

ML-01b adds an independently versioned capability descriptor and a pure coordinate oracle. It preserves world schema 2, recipe 3, generation algorithm 16, existing export bytes, seed replay and all potential asset identities. These helpers describe the current Python reference producer; they do not implement an importer or alter the generator's validation paths.

## Capability discovery and negotiation

The canonical machine-readable descriptor is [`Sim/fantasy_world_generator/capabilities.json`](../Sim/fantasy_world_generator/capabilities.json), included in the wheel. Export it using:

```sh
PYTHONPATH=Sim python -m fantasy_world_generator capabilities --output capabilities.json
```

`--version` selects the descriptor version and defaults to 1. Unsupported versions fail before creating or overwriting the output. The reference artifact workflow includes this descriptor under `contracts/capabilities.json`.

`fantasy_world_generator.capabilities.capabilities_document(version=1)` returns a fresh descriptor. `require_capabilities(request)` accepts exactly `capability_version` and `requires`, where `requires` maps exact capability IDs to integer versions:

```json
{"capability_version": 1, "requires": {"world_json": 2, "recipe": 3, "generation_algorithm": 16, "coordinates": 1}}
```

Successful negotiation returns a caller-owned descriptor; an empty requirements object is allowed. Unknown IDs, unavailable capabilities, unsupported versions, extra/missing fields and malformed types raise `ValueError`. Booleans, floats and numeric strings are not integer versions. Diagnostic exception messages are not stable machine error codes; [kernel contracts v1](kernel-v1.md) separately defines structured failures for the new kernel.

The supported inventory names the world and asset envelopes, recipe and generation algorithm, terrain taxonomy, coordinates, height tiles, city plans and globe scene. These describe producer support, not guaranteed presence in every world: phase gates still govern optional reports. Negotiation does not validate a supplied world, qualify its contents, or imply cross-language numeric parity. Consumers must also validate the actual document and its nested versions. Package release `0.1.0` is not a substitute for these contracts.

`native_kernel`, `unreal_editor_import`, `unreal_cooked_runtime` and `save_migration` are explicitly unavailable **from this Python producer**, and a request for any of them fails. That stays true now that the native core generates worlds in process inside the Unreal plugin: the plugin is a separate implementation with its own runtime report (`UFantasyWorldGeneratorSubsystem::GetStatus`), and a cooked runtime is a property of a packaged consumer build, evidenced by a recorded package digest, not something this package can hand a caller. Capability descriptor version 1 fixes descriptor structure and negotiation rules; its supported inventory must track the actual producer. Coordinate semantics have their own version 1. Changing those semantics requires a new coordinate version and independent fixtures rather than silently rewriting version 1. [Kernel contracts v1](kernel-v1.md) adds separate integer, random-stream and bounded-counter capabilities; it does not replace coordinate math or legacy world randomness.

## Globe axes, datum and local frame

Globe Cartesian coordinates are metres from the sphere centre. +X is latitude 0 / longitude 0, +Y is the north pole, and +Z is latitude 0 / longitude +90. Arithmetic uses a right-handed Cartesian cross product, X × Y = Z. Latitude and longitude input fields are degrees; convert to radians before trigonometry:

```text
up = (cos(lat)*cos(lon), sin(lat), cos(lat)*sin(lon))
east = (-sin(lon), 0, cos(lon))
north = (-sin(lat)*cos(lon), cos(lat), -sin(lat)*sin(lon))
position_m = (radius_m + height_m) * up
```

Radius comes from `effective_config.globe_radius` when present, otherwise `config.globe_radius`. `height_m` is radial elevation relative to this reference sphere. It is not height above sea level: that separate quantity is `height_m - sea_level_m`. A negative height can be above a more-negative sea level. Never add sea level when reconstructing globe positions. The radius and radius-plus-height must be positive.

The local tangent axis order is X east, Y up, Z north, with east × up = north. A local mesh origin sits at `(radius_m + origin_height_m) * up` at its anchor. To convert a globe position into local mesh coordinates, subtract that origin and dot the displacement with east, up and north. This retains curvature; local Y is generally not the radial height minus origin height away from the anchor.

Latitude lies in [-90, 90] and longitude in [-180, 180]. The coordinate oracle aliases +180 to -180 for identical seam positions. Pole unit positions are exactly `(0, ±1, 0)` regardless of longitude. A pole's tangent orientation still depends on the supplied anchor longitude: there is no single longitude-independent east/north frame at a pole. Existing exports may retain trigonometric rounding at poles/seams; the helper does not rewrite those exports.

## City, patch and tile representations

City-plan X/Z values are east/north gnomonic offsets in metres, not arc lengths or translated globe Cartesian coordinates:

```text
direction = normalize(up + (east*x_m + north*z_m)/radius_m)
globe_position = (radius_m + radial_height_m) * direction
```

`ground_elevation_m`, foundation elevations and city terrain surfaces retain the reference-sphere datum. The schematic city viewer draws radial height vertically without curvature. `world_scene` provides curved globe positions and unit axes instead. Building `rotation_degrees` rotates width from east toward north; depth rotates from north toward minus east. World-scene width/depth axes are orthonormal at the plot, with width × up = depth. An adapter should consume exported axes rather than interpret a plot angle as an engine Euler rotation.

Patch sampling uses the exponential map, with X/Z offsets defining distance and direction along the reference sphere:

```text
distance = hypot(x_m, z_m)
tangent = (east*x_m + north*z_m)/distance
direction = up*cos(distance/radius_m) + tangent*sin(distance/radius_m)
```

At zero distance use `up`. Sample radial height at that direction, reconstruct its globe position, then project the displacement into the anchor frame to obtain exported `local_x`, `local_y`, `local_z`. Patch rows increase south to north, unlike globe/tile raster rows. Patch-2 `height` values are absolute radial elevations; local mesh Y values include origin subtraction and curvature. The same X/Z numbers in a city and a patch need not address the same globe position. The helper implements coordinate math only; generator patch extent, spacing and mesh-size limits still apply at the patch request boundary.

The globe raster has a duplicate longitude seam and rows from north to south. With N samples per side, longitude is `-180 + 360*x/(N-1)` and latitude is `90 - 180*z/(N-1)`; seam endpoints share position and all samples on a pole share position.

At tile level L (1–24), the global lattice has `2^(L+1)` longitude cells and `2^L` latitude cells. Sample direction uses longitude `-180 + 180*x/2^L` and latitude `90 - 180*z/2^L`. The sample resolver accepts boundary indices inclusively, `0 <= x <= 2^(L+1)` and `0 <= z <= 2^L`. This does not permit tile origins at the terminal cell or tiles crossing a seam/pole: `export_height_tile` retains its existing bounds. Tile arrays are row-major, north to south and west to east, and carry `cells+1` samples per axis. Shared and nested global indices identify the same position. East-west metre spacing shrinks toward the poles; equatorial spacing is not uniform surface spacing everywhere.

## Pure coordinate oracle and fixtures

`fantasy_world_generator.coordinates.resolve_coordinate(request)` accepts exactly `coordinate_version`, `operation`, and `values`:

```json
{"coordinate_version": 1, "operation": "globe_position", "values": {"latitude_degrees": 0, "longitude_degrees": 90, "radius_m": 1000, "height_m": 25}}
```

Each operation requires its exact fields, with no defaults, unknown fields or coercions:

- `globe_position`: latitude/longitude in `latitude_degrees`, `longitude_degrees`, plus `radius_m`, `height_m`; returns XYZ metres.
- `tangent_frame`: latitude/longitude; returns unit `east`, `up`, `north` vectors.
- `city_direction` and `patch_direction`: latitude/longitude, `radius_m`, `x_m`, `z_m`; return globe unit direction.
- `local_position`: latitude/longitude, `radius_m`, `origin_height_m`, `position_m` (three-element XYZ array); returns local east/up/north metres.
- `tile_direction`: integer `level`, `x`, `z`; returns globe unit direction.
- `height_above_sea`: `height_m`, `sea_level_m`; returns their difference in metres.
- `metres_to_centimetres`: `value_m`; returns a signed scalar multiplied by 100.

Numeric fields accept finite Python integers/floats representing JSON numbers, excluding booleans and strings. Version and tile-index fields require integers. Out-of-range angles/indices, nonpositive radii or radial distances, nonfinite values and arithmetic overflow raise `ValueError`. Negative dimensions are not validated by a scalar unit conversion; that belongs to the consuming schema. Results and inputs have no shared mutable state and operations do not change simulation state. These helpers do not establish arbitrary-precision or extreme-scale accuracy guarantees.

[`Fixtures/coordinates-v1.json`](../Fixtures/coordinates-v1.json) supplies hand-authored cardinal, frame, projection, datum and unit-conversion vectors. [`Fixtures/capabilities-v1.json`](../Fixtures/capabilities-v1.json) supplies valid and rejected negotiations. Coordinate fixture comparisons use relative tolerance 1e-12 and absolute tolerance 1e-9; this is a scoped fixture criterion, not the future kernel's general numeric contract or a bitwise cross-platform claim. Tests also compare existing city, patch and tile implementations, exact helper seam/pole identities, nested indices, invalid input and finite serialization. Native and engine conformance remain untested.

## Future Unreal boundary

Convert dimensional metres to centimetres exactly once at the adapter boundary: `centimetres = metres * 100`. Apply that to positions relative to the selected origin, heights and dimensions. Do not scale unit directions, normalized axes, angles, IDs or grid indices. The scalar conversion helper is engine-independent arithmetic, not Unreal integration.

The UnrealWorldGen adapter mapping is specified in [Unreal integration](../docs/unreal-integration.md): local `(east, up, north)` metres become Unreal centimetres `(east, north, up)` with Z-up, winding reversed for the right-to-left handed change, and cardinal/elevation fixtures required. That mapping is not implemented by the version-1 oracle; changing it needs a new coordinate version rather than silently rewriting these operations. Scaling alone does not select orientation or prove an imported mesh faces outward. No importer, native world generator or cooked consumer is implemented by ML-01b.
