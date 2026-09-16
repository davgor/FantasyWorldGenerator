# Unreal integration contract

FantasyWorldGenerator is the authoritative world-planning producer. Unreal is a downstream consumer. The long-term runtime boundary is the native kernel and thin Unreal plugin specified by `PLAN.md`; the current Python/JSON facade is only an export/reference baseline.

## Current boundary

The generator publishes UTF-8 JSON with finite numeric values. A complete world contains the generator/recipe configuration, deterministic seed provenance, terrain and environmental grids, settlements, routes, sky surfaces, regional influences, and potential creature anchors according to the selected phase.

`Contracts/schemas/world-output.schema.json` identifies the stable export envelope. Nested simulation fields remain governed by their embedded version fields and the canonical world-layer documentation. Consumers must reject unsupported recipe/schema versions rather than guessing.

Coordinates and physical distances are in metres unless a field explicitly states another unit. An Unreal importer must convert metres to centimetres once at its boundary, retain stable IDs, map asset IDs through an Unreal-side registry, and report missing assets without inventing simulation state.

[Capabilities and coordinates v1](../Contracts/capabilities-and-coordinates.md) provides an exported producer descriptor and coordinate fixtures. Consumers can require exact supported contract versions; requests for native, editor import or cooked runtime capabilities are explicitly rejected. The future adapter must also specify axis/handedness mapping, origin and winding, scale dimensional values by 100 exactly once, and leave unit directions and angles unscaled. The included scalar conversion helper does not implement or qualify an Unreal adapter.

## Import sequence for a future Unreal plugin

1. Validate the JSON envelope and supported recipe version.
2. Create landscape/water and non-destructive visual overlays from authoritative grids.
3. Resolve asset IDs against the published exhaustive asset list and an Unreal object-path registry.
4. Materialize settlements, structures, foliage, landmarks, and creature habitat anchors without adding unsupported inhabitants or resources.
5. Store generator version, seed, resolved configuration, source digest, and importer version with the created world.

A bounded headless C++ counter core with strict JSON transport and numeric streams is available in `Core/`; it is not a native world generator. There is currently no `.uplugin`, C++/Blueprint importer, cooked-runtime generator, save migration, or Unreal validation in this repository. JSON export is not the intended live packaged-game runtime. Those capabilities require ML-01–03 contracts, native conformance, and a separately tested minimal consumer.

The [counter contract](../Contracts/kernel-v1.md) supplies a bounded accepted-event protocol and independent fixtures shared by the Python reference and [native core](../Core/README.md). Shared JSON/numeric fixtures and isolated source-bundle checks now run headlessly. It does not implement the world generator in a runtime plugin. The user-selected qualification target is Unreal 5.8.2; that engine is not installed on this machine, so editor/cooked qualification remains pending.
