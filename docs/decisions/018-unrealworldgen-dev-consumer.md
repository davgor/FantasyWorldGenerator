# 018 — UnrealWorldGen consumes in-process native genesis

On 2026-09-16 the owner selected sibling project `UnrealWorldGen` as the first Unreal consumer (Unreal Engine 5.8, local Win64). The same day, a Python lab sidecar / subprocess generate path was rejected: Unreal work is expensive, so the consumer must hit the real runtime boundary on the first engine pass. Astra review the same evening required cooked Win64 evidence, a catalogue-complete asset registry, an explicit Z-up Unreal mapping, and detailed-terrain contact before an asset-production handoff.

## Decision

- FantasyWorldGenerator owns `Unreal/MathLabRuntime/`. UnrealWorldGen consumes that plugin and does not fork generator rules.
- **In this epic (ML-03), all required:** (1) `.uplugin` plus in-process native **world** generate — Core is counter-only today; (2) UnrealWorldGen importer — Z-up, ×100, Landscape, registry; (3) packaged Win64 generate → materialize with package digest. Python world JSON does not close any of these.
- **Forbidden:** HTTP to `terrain_lab.py`, spawning `python -m fantasy_world_generator`, Unreal Editor Python, or an embedded interpreter. The browser lab remains inspection-only.
- Native API freeze includes on-demand detailed surface sampling and the [source-to-Unreal frame](../unreal-integration.md) (east→X, north→Y, up→Z, ×100 on lengths, winding reverse). Regional raster size is not the placement surface.
- Placeholder presentation uses the **final asset-ID → Unreal object-path registry**, covering the exhaustive catalogue. Hardcoded cubes that bypass the registry are not acceptance.
- ML-03e is not done without a **clean packaged Win64 run** of generate → materialize, recorded by exact package digest. GitHub Actions cooking can wait; local cooked evidence cannot. That digest is the asset-production handoff gate.
- Debug look (biome tints, blue water landscape, colored roads, registry placeholders at reported scale, nest markers) is allowed. Hub (capsule, interactable, loading) lives in UnrealWorldGen.

## Reason

A sidecar, an editor-only Landscape, a Y-up copy of source axes, a coarse-grid heightfield with floating boxes, or cubes that are not registry bindings would each force another Unreal architecture pass when real assets arrive.

## Consequences

- [ML-03d](../../board/backlog/ML-03d.md) owns native **world** generate (not counter-only), sampling, axis fixtures, and registry schema/coverage tests.
- [ML-03e](../../board/backlog/ML-03e.md) owns the `.uplugin`, UnrealWorldGen importer/hub, representative registry swaps, and cooked Win64 generate → materialize digest.
- `unreal_cooked_runtime` stays unavailable until the packaged digest exists. Closing ML-03e is that consumer proof; an immutable hosted channel / CI cook remains parent ML-03 if not yet automated.
- Decision 002 still applies to `fantasy-world-generator-reference`.
