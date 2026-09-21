# ML-03e — UnrealWorldGen plugin, hub, debug map, cooked loop

> **RETIRED 2026-09-21 by owner ruling. Not done, and not to be worked as written.**
> The native `Core/` port is deferred wholesale to the end of the project and will be a full
> rewrite against functionality that does not exist yet, so this card describes porting,
> mirroring or measuring a tree that is not the tree that will be ported. It is kept for its
> scoping notes and measurements only. **It is not a hold on anything** and must not be cited
> as a blocker or as evidence that a capability is incomplete.
> See [027 The native port is deferred to a full redo](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md).
>
> Scope was the UnrealWorldGen plugin pass: hub, registry placeholders, terrain contact, packaged Win64 digest. It was blocked on ML-03d; both are retired together.


## Requested behavior

This slice is epic items 2 and 3: the UnrealWorldGen importer (Z-up, centimetres, Landscape, registry, hub) and the packaged Win64 generate → materialize loop. It runs against the **native** generate API from [ML-03d](ML-03d.md) (epic item 1). Sibling **UnrealWorldGen** (Unreal 5.8, local Win64) pulls a plugin from FantasyWorldGenerator `main` and proves the **same** path in PIE and in a **packaged Win64** build, with no Python.

1. Merges to `main` produce a source-inclusive `FantasyWorldGenerator` archive for `Plugins/`.
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

`Unreal/FantasyWorldGenerator/`: `.uplugin`, runtime module wrapping `Core/`. Packaging tool + CI source archive. Qualification report for the local cook includes package digest, engine patch, Win64 target, `genesis: native-core`. `unreal_qualified` becomes true for this consumer only after the packaged loop passes.

The 2026-09-17 skeleton still **mirrors** Core frame/validation in `FantasyWorldGeneratorFrame.h` with compile-time asserts against `genesis.hpp`. ML-03e must compile Core `.cpp` (except tests) into the module, delete that mirror, and stop shipping a second copy of the rules (PK10). A numeric Core entry point is required for Landscape samples; JSON decimal strings per vertex are not that API.

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

## Progress — 2026-09-18

- The archive is source-inclusive: it vendors `Core/` into the module, so
  UnrealBuildTool compiles world genesis into `FantasyWorldGenerator` and the frame
  mirror is deleted (PK10). `Data/unreal-asset-registry-v1.json` is a runtime
  dependency, so a cooked build carries the binding table.
- The consumer is now a C++ project. Its Win64 **game** target compiles the plugin and
  the hub: capsule pawn, one interactable station, loading line, HUD report, lighting
  spawned in code on `/Engine/Maps/Entry`, and no authored `.uasset` in either tree.
- Materialize builds the rectangular tangent unwrap from the plugin's detailed samples
  as a runtime procedural mesh with collision, one section per natural biome, painted
  by registry-bound materials, with rivers coloured on the same surface. The
  Landscape-actor wording is settled by
  [decision 019](../../docs/decisions/019-runtime-surface-not-landscape.md).
- The materializer reports its own contact error: the largest disagreement between a
  drawn vertex and a fresh height sample, shown on the HUD and logged.
- Registry proof: `building.guildhall` and `terrain.biome.004` are bound to object
  paths that differ from their kind placeholders, so a mesh swap and a material swap
  are exercised; unresolved identities are logged and skipped, never replaced by an
  anonymous cube.
- **The cook:** `Build.bat` refuses to build any target while Live Coding is active, so
  the Unreal Editor must be closed. `tools/cook_consumer.py` then cooks Win64, runs the
  packaged executable with `-FWGSeed`, records the package digest and writes
  `Artifacts/unreal/packaged-run.json`.
- **In the packaged world as of 2026-09-18:** cities, regional roads, planned building
  slots, and both habitat passes — animal hunting grounds and monster territory, each
  carrying its danger tier and range. The registry probe placeholders remain labelled as
  a registry demonstration, not generated settlement content.

## Packaged evidence — 2026-09-18

Cooked with `tools/cook_consumer.py --replay`: UnrealBuildTool + UAT `BuildCookRun`,
Win64, Development, engine 5.8, no editor in the loop and no Python in the game. This
run replaces the 2026-09-18 eleven-kilometre evidence it supersedes: that one was cooked
from a copy of the project, and this one is the canonical checkout.

- **Package digest** `fa8888706d567542d4af910a573c258638b90081824857fba898e698a1c9decb`
  over 50 staged files and 1,070,670,793 bytes, excluding what the run itself writes
  under `Saved/`.
- **Executable** `UnrealWorldGen.exe`, exit code 0, 27.0 s of wall clock for three runs.
- **Generate to materialize**, seed 20260918, sixty kilometre map, regional raster 193,
  unwrap 513 latitude rows: 525,825 vertices in 14 biome sections (318,319 of them
  water), heights -51012..47868 cm, generate 15,457 ms and materialize 2,862 ms.
  Generate is the whole native world: terrain, climate, ecology, leylines, settlement
  fields, founded cities, roads and both habitat passes.
- **Civilizations**: 481 cities and 468 regional roads, 230,142 ribbon vertices, and
  2,568 planned building slots with none unbound. The city count is the ground's own
  packing ceiling rather than the old constant 24.
- **Habitat**, the two passes the game reports for itself:
  - 6,791 animal hunting grounds, tiers one to five **5078 / 1290 / 352 / 71 / 0**.
    Successive ratios 3.94, 3.66 and 4.96 against the authored falloff of 4, so the
    trophic pyramid survives placement rather than only existing in the constant.
  - 527 monster territories, tiers **289 / 86 / 90 / 41 / 21**. Twenty-one campaign
    threats on a sixty kilometre world, and tier three slightly exceeding tier two is
    habitat and draw noise at these counts, not an inverted pyramid.
  - Widest hunting ground 375 m, widest monster territory 1,750 m.
  - **1,424 hunting grounds fall inside a monster territory.** The two passes never
    read each other, so this overlap is the design being observed, not a collision:
    the monsters hunt the same game.
- **Frame checks from the shipped plugin**: east is +X, north is +Y, radial up is +Z,
  metres scale by 100 exactly once, unit axes permute without scaling — all pass.
- **Contact**: drawn vertex against a fresh height sample, 0.000000 cm. Collision
  against the drawn surface, 0.066970 cm over 253 line traces at stride 1, so what the
  player stands on is what the generator reported. Between vertices the flat triangle
  differs from the true sampled height by up to 1246.3 cm at this display resolution;
  that is the honest cost of 513 rows over sixty kilometres, and it is why a foundation
  must read the sampling function rather than the drawn mesh.
- **Registry**: 494 identities resolved, 0 missing, 1 resolved to a concrete bound
  object rather than its kind placeholder, and the deliberate unbound identity reported
  itself instead of spawning anything. Of 8,986 world markers, 7,351 carry a registry
  identity and none are unbound. The staged table is the catalogue-complete 1,184-row
  file.
- **Replay**: the same seed twice produces an identical reported world. Seed 20260919
  differs throughout — 384.58 km2 of land against 510.64, 412 cities against 481, 6,747
  animals against 6,791 and 365 monster territories against 527, with its own tier
  spreads of 5106/1233/325/83/0 and 179/67/66/36/17. A player generating many worlds
  gets different ecologies, and the same seed always returns the same one.
- **Capture**: `Saved/Screenshots/Windows/FWGPackagedRun.png` and `FWGPackagedRegion.png`
  inside the package. Habitat anchors draw as instanced boxes scaled by danger tier,
  animals green and monsters red; at map scale the emissive debug material washes them
  to white points, so the legend is legible close up and the counts above are the
  evidence at altitude.

**The Unreal Editor must be closed, and `UnrealMCP` must be disabled.** That plugin uses
`ANY_PACKAGE`, removed in UE 5.5, so it cannot compile against 5.8 and its failure stops
the editor build that cooking requires. It is an editor-side bridge the packaged game
never loads. The cook does not disable it for you: turn it off in `UnrealWorldGen.uproject`
for the cook and turn it back on afterwards.

## Handoff

Finish line for asset-focused work: cooked digest + registry coverage, not PIE boxes.
Immutable hosted release automation can remain a parent ML-03 follow-up.
