# ML-03e — UnrealWorldGen plugin, hub, debug map, cooked loop

## Requested behavior

This slice is epic items 2 and 3: the UnrealWorldGen importer (Z-up, centimetres, Landscape, registry, hub) and the packaged Win64 generate → materialize loop. It runs against the **native** generate API from [ML-03d](ML-03d.md) (epic item 1). Sibling **UnrealWorldGen** (Unreal 5.8, local Win64) pulls a plugin from FantasyWorldGenerator `main` and proves the **same** path in PIE and in a **packaged Win64** build, with no Python.

1. Merges to `main` produce a source-inclusive `MathLabRuntime` archive for `Plugins/`.
2. The game uses the plugin generate/capability/sample/registry API.
3. Hub: capsule pawn, use object, loading screen, random uint32 seed, in-process generate, Z-up Landscape unwrap:
   - Heights from on-demand detailed samples (same function as buildings/roads)
   - Lab biome colors; mutation outlines where provided
   - Water as blue landscape
   - Buildings as registry-bound placeholders at reported scale (metres → cm once, remapped axes)
   - Roads as color on the sampled surface
   - Nest markers on that surface
4. Seed shown; same seed replays layout.
5. **Asset-production handoff:** clean packaged Win64 run of the entire loop; record **exact package digest**. CI cook automation may follow this evidence; it must not replace it.
6. **Registry path:** placeholders resolve through the final asset-ID → Unreal object-path table. Prove at least one non-default mesh and one material replacement via the registry (dimensions, pivot, orientation). Missing bindings diagnose; they do not spawn anonymous cubes. Cooked package contains referenced registry assets. Coverage vs exhaustive catalogue is inherited from ML-03d tests plus engine load of that table.

Debug look is allowed. Architecture (frame, sampling, registry, cooked generate) is not optional.

## Proposed mechanism

### Package

`Unreal/MathLabRuntime/`: `.uplugin`, runtime module wrapping `Core/`. Packaging tool + CI source archive. Qualification report for the local cook includes package digest, engine patch, Win64 target, `genesis: native-core`. `unreal_qualified` becomes true for this consumer only after the packaged loop passes.

### Translation

Validate native result → sample detailed heights onto Landscape using [Unreal integration](../../docs/unreal-integration.md) (`U = (east, north, up) * 100`) → color/water layers → registry-bound meshes for buildings → roads/nests on the same XY unwrap and sampled Z. Prefer `world_scene` axes. Reverse winding when copying source indices.

### Hub

Capsule, one interactable, loading widget, present the generated map. Failure text on generate/materialize/registry errors. No character mesh or save migration.

## Dependencies and unresolved decisions

**Blocked on ML-03d** (including sampling, axis fixtures, catalogue registry coverage). Do not implement against JSON files, Python, or hardcoded cubes.

Settled: Z-up mapping, detailed contact, registry, cooked digest ([decision 018](../../docs/decisions/018-unrealworldgen-dev-consumer.md)).

Open: Landscape component size vs display sample density; Shipping vs Development packaged configuration (must still be a cooked Win64 executable, not PIE).

## Sources consulted

- Astra 2026-09-16 P1 cooked, P1 registry, P2 axes, P2 terrain contact.
- Epic Z-up / left-handed world; `PLAN.md` PK03/PK04/PK06.

## Files and assets in scope

**FantasyWorldGenerator:** plugin, registry data, packaging, docs, tests that do not require the editor where possible.

**UnrealWorldGen:** plugin enablement, hub, pawn, interactable, loading UI, placeholder mesh/material assets **registered by ID**, packaged smoke. Do not commit that tree from this repo unless requested.

## Acceptance and evidence

- Plugin loads from the published archive with **no Python**.
- Hub PIE: generate, non-flat Landscape, colors, water, roads, nests; buildings and roads **contact** sampled terrain; seed replay matches; cardinal/elevation checks visible or logged from fixtures.
- Registry: catalogue-complete table loads; representative mesh/material swap; missing-binding diagnostic; no ID-less cubes.
- **Packaged Win64** executable completes generate → materialize without the editor; collision at display resolution; package digest recorded in ML-03e evidence. A green Python suite or PIE-only capture is not this gate.
- Parent ML-03 may still lack hosted CI/immutable channel; that does not waive this cooked consumer proof.

## Documentation impact

This ticket, decision 018, Unreal integration, publishing, parent ML-03.

## Adversarial review and limitations

- Polar stretch on the rectangular unwrap.
- Size 257 can hitch; cap or warn.
- Placeholders are not production art; they must still be the production **binding mechanism**.
- No `.uasset` binary edits in the producer repo.

## Handoff

Starts after ML-03d. Finish line for asset-focused work: cooked digest + registry coverage, not PIE boxes. Immutable hosted release automation can remain a parent ML-03 follow-up.
