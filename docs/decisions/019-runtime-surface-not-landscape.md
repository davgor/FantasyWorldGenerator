# 019 — The materialized surface is a runtime mesh, not an editor Landscape

On 2026-09-18 the native world generate landed in `Core/` and the consumer pass began.
[Decision 018](018-unrealworldgen-dev-consumer.md) and [ML-03e](../../board/retired/ML-03e.md)
call the presented terrain a *Landscape*. `ALandscape` cannot be created at runtime:
its import and heightmap-authoring paths live in editor-only modules, so a cooked game
cannot build one. ML-03e also requires that the **same** path run in PIE and in a
packaged Win64 executable.

## Decision

- The materialized surface is a `UProceduralMeshComponent` built from the plugin's
  on-demand detailed samples, with collision at the display resolution.
- One mesh section per natural biome identity, each painted by the material the
  asset-ID registry binds for `terrain.biome.NNN`. Water and rivers are sections and
  colours on that same surface, not separate floating geometry.
- Every requirement Landscape carried is kept: Z-up centimetres, east to +X and north
  to +Y, heights from the shared sampling function, collision matching the visual, lab
  biome colours, blue water, registry-bound materials.
- The word *Landscape* in ML-03e and decision 018 means this presented terrain
  surface. An editor Landscape actor may still be produced later for editor workflows;
  it is not the runtime path and cannot be the cooked evidence.

## Reason

A cooked build that materialized something different from PIE would make the packaged
digest meaningless, and an editor-only Landscape would force a second materialize path
the moment real art arrived.

## Consequences

- `UnrealWorldGen` depends on the `ProceduralMeshComponent` plugin.
- The hub level is `/Engine/Maps/Entry` and everything else is spawned in code, so no
  `.uasset` or `.umap` is authored in either repository for this slice.
- Placeholder art is engine primitives named by the registry table
  (`/Engine/BasicShapes/...`), so the producer repository still ships no binaries and
  production art replaces paths in `Contracts/catalogues/unreal-asset-bindings.json`.
- Polar stretch remains a property of the rectangular unwrap, as documented in
  [Unreal integration](../unreal-integration.md).
