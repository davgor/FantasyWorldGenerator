# Build order for Epic 010

The catalogue is prepared now. Production stays in the backlog until started. No dependency requires regenerating an already approved asset.

## First prototype gate

Build the following representative jobs in dependency order. Their acceptance establishes style, scale, density/texel targets and engine performance budgets before bulk production.

Landscaping jobs first require the [source UE-014 biome gate](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/epics/14-landscaping-pipeline.md): reconcile/backport decided definitions into FantasyWorldGenerator and validate the exact revisions consumed by texture/foliage recipes. New or changed biomes cannot enter production on catalogue status alone. The existing list remains a job baseline, not evidence of validated layered-world coverage.

- [ ] `MAT-001` — Fertile loam (include its listed dependencies first).

- [ ] `MAT-011` — Wet marsh mud (include its listed dependencies first).

- [ ] `MAT-017` — Granite-like rock (include its listed dependencies first).

- [ ] `MAT-040` — Weathered timber (include its listed dependencies first).

- [ ] `VEG-001` — Short meadow grass (include its listed dependencies first).

- [ ] `TREE-002` — Spreading oak-like tree - mature A (include its listed dependencies first).

- [ ] `BLD-001` — Human foundation level (include its listed dependencies first).

- [ ] `BLD-003` — Human wall solid (include its listed dependencies first).

- [ ] `BLD-011` — Human door (include its listed dependencies first).

- [ ] `ARCH-001` — Human city dwelling (include its listed dependencies first).

- [ ] `FUNG-001` — Giant umbrella mushroom (include its listed dependencies first).

- [ ] `GEO-023` — Crystal cluster medium (include its listed dependencies first).

- [ ] `WATER-002` — Lake surface (include its listed dependencies first).

## Production batches

[Source UE-015](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/epics/15-landscaping-catalogue-backfill.md) runs the landscaping subset below after UE-014 release: landscaping MAT and dependencies, GEO, VEG, TREE and FUNG. Freeze the exact item scope, reuse verified prototypes and track per-item approval/evidence against these existing catalogue IDs. Other categories remain UE-010 work; a batch retry or fallback cannot mark missing required art complete.

Include biome ambience profiles and their relevant FX dependencies in each landscaping batch. Reuse existing mist, dust, motes or wisps only within reviewed eligibility. Inspect palette, shadows and fog together with the materials/vegetation, including biome transitions, day/night, profile restoration and gameplay readability. General FX outside this profile scope remains UE-010 production.

Before bulk landscaping production, assemble the [source integrated landscaping prototype](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/epics/10-parameter-driven-world-asset-catalogue.md#integrated-landscaping-placement). Include biome-matched grass, light ground cover and trees together with their surface materials; select existing VEG/TREE jobs and dependencies for its meadow, woodland and wet-bank contexts. Individual swatches or isolated tree previews do not satisfy placement acceptance. Use labelled placement inputs until epic 009 integration exists, and retain the distinction between art review and generated-world verification.

1. **MAT** — all material swatches.
2. **GEO, VEG, TREE, FUNG** — geology and vegetation, with their MAT dependencies.
3. **WATER, FX** — water and environmental effects; use labelled integration placeholders until epic 009 hooks exist.
4. **BLD and PROP** — architectural modules, roads, utilities, furnishing and work props.
5. **ARCH** — assemble complete buildings from approved modules and furniture; no duplicate mesh generation.
6. **PPL** — audit/reuse existing bases, rigs and wearable work; produce only missing requirements.
7. **ANIM** — audit/reuse or generate clips, retarget against all approved base rigs.
8. **ROLE** — assemble reusable occupation appearances with their tools and clips.
9. **SND** — environmental and interaction sound sets; can run alongside visual batches once event contracts exist.

## Per-item completion checklist

- [ ] Dependencies reviewed and available.
- [ ] Source/reuse decision and generation brief recorded under the stable job ID.
- [ ] Contract outputs produced, licensed and versioned.
- [ ] Physical size, pivot, material channels and placement footprint verified.
- [ ] Unreal visual/collision/animation/LOD or audio checks relevant to this type passed.
- [ ] Preview and verification evidence linked in the manifest.
- [ ] Matching Markdown checkbox and JSON status updated to done.

No bulk “generate everything” approval is implied. Start each batch with representative review to avoid hundreds of incompatible assets. Dimensions and families are concrete baseline targets; record intentional revisions against the stable ID rather than silently changing scope.
