# Unreal integration contract

FantasyWorldGenerator is the authoritative world-planning producer. Unreal is a downstream consumer. The long-term runtime boundary is the native kernel and thin Unreal plugin specified by `PLAN.md`; the current Python/JSON facade is only an export/reference baseline.

## Current boundary

Native in-process generate is the Unreal path; the JSON export below remains the reference and lab baseline. The generator publishes UTF-8 JSON with finite numeric values. A complete world contains the generator/recipe configuration, deterministic seed provenance, terrain and environmental grids, settlements, routes, sky surfaces, regional influences, and potential creature anchors according to the selected phase.

`Contracts/schemas/world-output.schema.json` identifies the stable export envelope. Nested simulation fields remain governed by their embedded version fields and the canonical world-layer documentation. Consumers must reject unsupported recipe/schema versions rather than guessing.

Coordinates and physical distances are in metres unless a field explicitly states another unit. An Unreal importer must convert metres to centimetres once at its boundary, retain stable IDs, map asset IDs through an Unreal object-path registry, and report missing assets without inventing simulation state.

[Capabilities and coordinates v1](../Contracts/capabilities-and-coordinates.md) provides an exported producer descriptor and coordinate fixtures. Consumers can require exact supported contract versions; requests for native, editor import or cooked runtime capabilities are explicitly rejected until those gates pass. The scalar conversion helper does not implement or qualify an Unreal adapter.

## Source-to-Unreal frame (required adapter mapping)

Unreal Engine uses a **left-handed, Z-up** world: +X forward in pawn terms, +Y right, +Z up. Source simulation does **not**. Do not copy source `(X, Y, Z)` into an Unreal `FVector`.

Source frames (metres, right-handed), from capabilities v1:

- Globe Cartesian: origin at sphere centre; +X latitude 0 / longitude 0; +Y north pole; +Z latitude 0 / longitude +90; `X × Y = Z`.
- Local tangent: **+east, +up, +north** with `east × up = north`. Local mesh `Y` is up, not Unreal Z.
- City-plan `x_m`/`z_m` are gnomonic east/north offsets. Building width × up = depth in `world_scene`.

**UnrealWorldGen world centimetres** after choosing a tangent origin `(lat0, lon0, origin_height_m)`:

```text
(east_m, up_m, north_m) = local_position(globe_point, origin)
U.X = east_m * 100
U.Y = north_m * 100
U.Z = up_m * 100
```

| Source | Unreal |
| --- | --- |
| +east | +X |
| +north | +Y |
| +up (radial) | +Z |
| length, height, width, depth | × 100 once |
| unit east/up/north axes | permute to (east, north, up); **do not** × 100 |
| angles | unscaled; prefer remapped `world_scene` axes over Euler-from-`rotation_degrees` |

`(east, north, up)` is right-handed (`east × north = up`). Unreal is left-handed, so **copied source triangle winding is reversed** when building Unreal index buffers. Landscape: +X follows +east, +Y follows +north, height is +Z.

**Cardinal/elevation fixtures** (engine and native) must prove: a point east of origin has `U.X > 0`; north has `U.Y > 0`; greater radial height has `U.Z` greater; a width axis that is source-east aligns with Unreal +X. Seam (`lon = ±180`) and pole samples use the coordinate oracle identities. A new coordinate version is required if this mapping changes.

Rectangular presentation is this tangent unwrap, not a claim that the generator `shape` is planar. Recipe 3 remains a tectonic globe. Polar stretch is a presentation artifact of the unwrap.

## Shared sampling and terrain contact

The regional climate raster (`size`, including 65) is **not** the placement surface. Authoritative local height is [continuous terrain](continuous-terrain.md): regional field plus `terrain_detail`, the same function used by city planner foundations, streets, patches, and height tiles.

Before freezing the native generate API, Core must expose **on-demand surface samples** (globe direction or lat/lon → radial height and masks) identical in contract to tile/patch exports. Landscape display vertices, building foundations, road polylines, and nest anchors must all:

1. Sample that function (not bilinear-only from the coarse raster).
2. Convert through the **same** origin and east/north/up unwrap as the Landscape.
3. Meet the surface at the supported display resolution: foundation corners and occupancy centres within the planner’s ground-clearance rule; street/regional-road samples on the detailed grade; junctions share one Unreal point; seam-adjacent samples do not tear; collision uses the same heights as visuals.

A non-flat coarse Landscape with floating boxes fails this contract.

## Asset ID registry

Every identity in the exhaustive asset list has an Unreal registry row: object path, or an explicit missing/non-ready binding. Placeholder debug meshes are **bindings in that registry**, not hardcoded `Cube` spawns outside it. ML-03e must prove: swap a representative mesh and material through the registry; preserve metre dimensions, pivot, and remapped orientation; diagnose missing bindings without inventing assets; cooked package includes referenced registry objects. Coverage is tested against the **full catalogue**, not one generated seed. Later art replaces paths in the registry; it must not require a second adapter.

## Push to Unreal (this epic: ML-03)

Python can already write world JSON. That is not Unreal setup. ML-03 must close all three:

1. `.uplugin` (`FantasyWorldGenerator`) and an in-process native generate API. `Core/` today is the counter only; world genesis is in scope ([ML-03d](../board/backlog/ML-03d.md)).
2. UnrealWorldGen importer: Z-up / centimetre mapping in this document, Landscape, asset-ID registry ([ML-03e](../board/backlog/ML-03e.md)).
3. Packaged Win64 generate → materialize loop with an exact package digest (ML-03e). Editor PIE does not close the epic.

See [decision 018](decisions/018-unrealworldgen-dev-consumer.md) and parent [ML-03](../board/in-progress/ML-03.md).

The first engine host is sibling project **UnrealWorldGen** (Unreal 5.8, local Win64). The plugin is owned here at `Unreal/FantasyWorldGenerator/`. See [decision 018](decisions/018-unrealworldgen-dev-consumer.md), [ML-03d](../board/backlog/ML-03d.md), and [ML-03e](../board/backlog/ML-03e.md).

- Genesis is in-process native `Core/` code. No Python lab, spawned Python, or embedded interpreter.
- ML-03d proves native generate, on-demand sampling, axis fixtures, and catalogue-complete registry schema **headlessly** before UnrealWorldGen maps.
- ML-03e is the single engine pass: hub, materialize, registry placeholders, and a **packaged Win64 generate → materialize run** with an exact package digest. CI automation of that cook may follow; local cooked evidence is required before an asset-production handoff. `unreal_cooked_runtime` stays unavailable in the Python capability descriptor until that digest exists and is recorded.
- Unreal supplies a random uint32 seed, calls the plugin, and stores seed, contract versions, and plugin/package digests on the world.
- Debug presentation: lab biome colors, blue water landscape, colored roads, nest markers, registry-bound placeholder boxes at reported scale.

Hub gameplay lives in UnrealWorldGen.

### Plugin tree status (2026-09-18)

`Unreal/FantasyWorldGenerator/` is a Win64 `Runtime` module that **wraps compiled Core sources**. The packaged archive vendors `Core/` into `Source/FantasyWorldGenerator/FantasyWorldGeneratorCore/`, so UnrealBuildTool compiles world genesis, sampling, the coordinate frame and the registry loader into the module; the earlier private mirror of the frame and validation rules is deleted, and `tests/test_plugin_frame.py` now fails if a second copy of a Core rule reappears. `Core/` stays free of UObject types, and the counter kernel is excluded from the vendored set: it is not on the generate path and its `check()` helper collides with the Unreal macro.

`UFantasyWorldGeneratorSubsystem` exposes the numeric entry points an adapter needs, with no JSON per vertex:

- `GenerateWorld(seed, regional raster)` — recipe-3 world in process; a rejected request leaves the previous world intact.
- `SampleHeightCentimetres(lat, lon)` and `SampleSurface(lat, lon)` — the shared detailed surface function.
- `BuildSurfaceUnwrap(rows)` — the whole rectangular tangent unwrap as positions in Unreal centimetres, per-vertex biome identities, water types, colours and reverse-wound triangles.
- `ResolveAsset(id)` — the registry table shipped in `Data/unreal-asset-registry-v1.json` and staged into cooked builds; a missing binding is a diagnostic, never an anonymous mesh.
- `GetPlaceMarkers(rows)` — every point that is not a city, a road or a building: hamlets, fortresses, coastal landings, witch huts, ruins and habitat anchors, each tagged with its category. A ruin carries `marker.city_ruins` and a creature carries `creature.<species id>`; a hamlet, landing or landmark has no identity in the generator, so a consumer draws those as its own markers and must not count them as registry bindings. Habitat arrives as two categories from two independent passes — `animal` for hunting grounds and `nest` for monster territory — and they overlap on purpose, because the monsters hunt the same game; a consumer must not treat one as excluding the other. Both carry `Tier` (danger to a player, 1 to 5), `RangeMetres` (the ground the claim covers) and `bIsDen` (a place to raid rather than only a range where the creature is met). Every other category reports tier zero and no range.
- `GenerateWorldOfSize(seed, size, kilometres)` — the same generate, sized in kilometres of map width. The seed's terrain is unchanged; it covers more ground. Distances stated in metres, such as settlement spacing, do not scale, so a larger world holds proportionally more content.
- `GetPlannedBuildings(rows)` — the building slots the city plans reserved, each with the registry identity it carries (`building.<catalogue id>`) and a position on the unwrap. These are reserved nodes, not footprints: a consumer that draws them should present them as markers, which is what UnrealWorldGen does.
- `GetCities(rows)` / `GetRoads(rows)` — the civilizations the generator founded and the regional routes between them, already placed on the presented unwrap at their sampled heights. Both need `Data/native-catalogues-v1.json`, the authoring traits and rules from [decision 020](decisions/020-authoring-catalogues-ship-as-data.md); without it a world has terrain and says so rather than inventing civilizations.
- `GetStatus()` — reports `bCoreGenesisLinked`, `bNativeGenerateAvailable`, registry row and unbound counts, and the asset-list digest. `bUnrealQualified` stays false until a packaged Win64 digest is recorded.

Request offsets still transport as exact whole metres or bounded decimal strings in the JSON validation path; sampled heights cross the boundary as doubles.

The module compiles under UnrealBuildTool for the Win64 game target in the sibling UnrealWorldGen project. Editor-target compile and the cooked run are the open items ([ML-03e](../board/backlog/ML-03e.md)).

## Presented surface

`ALandscape` cannot be created at runtime, and the packaged loop must run the path PIE runs, so the presented terrain is a runtime procedural mesh built from the detailed samples: one section per natural biome, registry-bound materials, collision at display resolution. See [decision 019](decisions/019-runtime-surface-not-landscape.md). Every frame, sampling, colour and registry requirement above still applies to it.

## Native parity with the Python reference

`Core/` reproduces the recipe-3 reference world for the same seed: plate layout, spherical noise, erosion, the second tectonic epoch and its relic incision, connected water, wind and rain, biome and landform labels, cold habitats, salinity, flood risk and the continuous-terrain sampling. Identity layers (plate, land, water type, river, biome, natural biome, landform) match the Python oracle exactly; continuous fields match within the contract in `Fixtures/native-world-v1.json`, whose only observed divergence is the platform `pow()` differing from the interpreter's in the last ulp. `tests/test_native_world.py` is that gate. Per-people suitability and capacity, the population budget, founded cities, the regional road network and the scene polylines those produce are also native and compared against the reference. City layout plans are native too: which pack each city builds from, which layout profile it takes, and which node every district and planned building claims. So are the hinterlands (hamlets, fortresses, cultures), the coastal landings, the specialist landmarks, the creature habitat anchors and both age transitions, so the envelope a consumer receives is the reference's finished world, ruins included, and it carries `history_stage = 15`. Plot geometry (footprints, walls and streets) comes from the reference's city-planner stage and is **not** ported, so a planned building is a reserved node rather than a footprint.

## Import sequence

1. Validate the native/JSON envelope and supported recipe version.
2. Sample detailed heights; create Landscape/water overlays through the Unreal frame above.
3. Resolve every emitted asset ID through the Unreal object-path registry (placeholders allowed; silent cube-without-ID is not).
4. Materialize settlements, structures, roads, and nest anchors on the sampled surface without adding unsupported inhabitants or resources.
5. Store generator version, seed, resolved configuration, source digest, importer version, and cooked package digest with the created world.

A bounded headless C++ counter core is available in `Core/` and the `.uplugin` tree exists but is uncompiled; native world generate, the importer, and the cooked loop are the open ML-03 push-to-Unreal items, not out-of-epic work.
