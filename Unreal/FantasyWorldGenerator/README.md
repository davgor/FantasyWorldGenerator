# FantasyWorldGenerator plugin

Runtime Unreal code plugin owned by FantasyWorldGenerator and consumed by sibling
**UnrealWorldGen** (Unreal 5.8, Win64). See [decision 018](../../docs/decisions/018-unrealworldgen-dev-consumer.md),
[decision 019](../../docs/decisions/019-runtime-surface-not-landscape.md) and
[Unreal integration](../../docs/unreal-integration.md) for the canonical boundary.

## What exists

- `FantasyWorldGenerator.uplugin`: one `Runtime` module, `Win64` allow list,
  `EnabledByDefault` false, `CanContainContent` false. No `/Game` path, content
  directory or game-specific reference in the code.
- `Source/FantasyWorldGenerator/FantasyWorldGeneratorCore/` **in a packaged archive**:
  the engine-independent `Core/` sources, vendored by `tools/package_plugin.py` so
  UnrealBuildTool compiles world genesis, sampling, the coordinate frame and the
  registry loader into the module. The counter kernel is excluded: it is not on the
  generate path and its `check()` helper collides with the Unreal macro.
- `Source/FantasyWorldGenerator/Public/FantasyWorldGeneratorTypes.h`: engine-facing
  value types (status, world summary, surface unwrap, asset binding, surface sample).
  These carry data; they restate no generator rule.
- `Source/FantasyWorldGenerator/Public/FantasyWorldGeneratorSubsystem.h`: the API below.
- `Data/unreal-asset-registry-v1.json`: the catalogue-complete asset-ID to object-path
  table, added as a `RuntimeDependency` so a cooked build carries it.

The frame mirror that used to restate the Core rules in the module is deleted;
`tests/test_plugin_frame.py` fails if a second copy of a Core constant reappears.

## API

`UFantasyWorldGeneratorSubsystem` (engine subsystem, no Python runtime, sidecar
process, embedded interpreter or JSON world file anywhere in the path):

- `GenerateWorld(Seed, RegionalRasterSize, Summary, Diagnostic)` — recipe-3 world in
  process. A rejected request leaves the previous world intact and says why.
- `SampleHeightCentimetres(Lat, Lon)` / `SampleSurface(Lat, Lon)` — the authoritative
  detailed surface in Unreal centimetres, the same function foundations, roads and
  nests must read.
- `BuildSurfaceUnwrap(LatitudeRows, Surface, Diagnostic)` — positions, per-vertex
  biome identities, water types, lab colours and reverse-wound triangles for the
  rectangular tangent unwrap, centred on the origin.
- `ResolveAsset(AssetId)` — the binding table. A missing binding is reported with a
  reason, never replaced by an anonymous mesh.
- `LocalMetresToUnreal` / `LocalUnitAxisToUnreal` — the frame conversion.
- `GetStatus()` — what is actually linked and loaded: Core linked, native generate
  available, registry rows and unbound count, asset-list digest, contract versions.

Frame: X is source east, Y is source north, Z is source radial up. Lengths scale by
100 exactly once, inside the module. Unit axes only permute. Copied triangle winding
reverses for Unreal's left-handed frame.

## What does not exist

Settlement, road, city-plan and nest placement are not in the native envelope yet
([ML-03d](../../board/retired/ML-03d.md)), so this plugin materializes no building,
street or nest. `bUnrealQualified` stays false: an enabled plugin is not a
qualification, and cooked-runtime evidence lives with
[ML-03e](../../board/retired/ML-03e.md).

## Use from UnrealWorldGen

```
python tools/package_plugin.py --install <path to the consumer project>
```

That writes the content-addressed archive to `Artifacts/unreal/` and replaces
`<project>/Plugins/FantasyWorldGenerator` with its contents, vendored Core and registry
table included. Enable `FantasyWorldGenerator` in the `.uproject`, then build the Win64
target. The consumer project must be a C++ project; a Blueprint-only project cannot
compile the module.

`tools/cook_consumer.py` cooks that project for Win64, runs the packaged executable and
records the package digest with the run's own reported numbers.
