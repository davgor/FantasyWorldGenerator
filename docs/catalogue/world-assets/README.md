# World asset production list

This is the actual item-by-item production baseline for **Epic 010**: **492 jobs**, each with a stable ID, brief, scale, placement context, dependencies and a shared output/acceptance contract. Nothing in this catalogue has been generated or verified yet. “Not started” means required work, not that an existing reusable asset has been audited and rejected.

The list covers the current generator, not every conceivable future game feature. Exact plant families and dimensions below are proposed art-direction choices, not claims about simulated botany. Approve the representative prototypes first, then work through the remaining IDs without another broad inventory exercise.

## Start here

1. Read [build order](BUILD-ORDER.md) and the contracts below.
2. Open a category list and select an unchecked item whose dependencies are ready.
3. Use its ID as the production ticket suffix (`010.MAT-001`, for example); copy its full brief and contract into the asset task.
4. Generate, reuse or assemble the stated asset, record provenance and evidence, and verify in Unreal.
5. Update the matching JSON status and Markdown checkbox together; only mark done after every contract check passes.

[Machine-readable manifest](manifest.json) is the authoritative structured record; category lists are readable work queues. Each job is one primary source asset, reusable assembly or explicitly named clip/event set. Required import files, LODs, textures and colliders are deliverables within that job. This is not a promise of exactly 492 final mesh files.

## Work queues

- [MAT: Materials](mat.md) — 48 jobs.

- [GEO: Geology](geo.md) — 27 jobs.

- [VEG: Grasses, shrubs and ground cover](veg.md) — 39 jobs.

- [TREE: Tree forms](tree.md) — 78 jobs.

- [FUNG: Giant fungi](fung.md) — 7 jobs.

- [WATER: Water](water.md) — 13 jobs.

- [FX: Weather/magic effects](fx.md) — 12 jobs.

- [BLD: Building components](bld.md) — 48 jobs.

- [ARCH: Building assemblies](arch.md) — 62 jobs.

- [PROP: Infrastructure, farming and props](prop.md) — 57 jobs.

- [PPL: People/appearance assets](ppl.md) — 30 jobs.

- [ROLE: Occupation prefabs](role.md) — 33 jobs.

- [ANIM: Animations](anim.md) — 16 jobs.

- [SND: Audio](snd.md) — 22 jobs.


## Shared production contracts

Working art direction: cohesive grounded stylized fantasy, original silhouettes, restrained weathering/emission, legible at human walking scale. Unreal is the target. Source dimensions are metres; Unreal defaults to centimetres. Convert explicitly at import and validate with a metre-scale reference. Keep editable sources and provenance. Texture resolution 2048 is the initial material target; change it only with a documented prototype/performance decision, not silent per-asset guesses. Triangle/draw-call budgets are not fixed blindly: establish them in the prototype scene before bulk production.

### material

Deliver: Editable source; Seamless 2048px base colour, normal and roughness; linear data maps; Height and occlusion where physically meaningful; emission only when requested; Unreal material/import settings and 1m/4m tiling preview.

Accept only after: No baked directional light or unintended seams; Correct colour spaces and normal orientation; Metre-scale tiling checked beside 1.8m reference; Dry/wet blend tested; licence and source recorded.

### mesh

Deliver: Editable mesh source and FBX or GLB exchange; UVs and linked PBR materials; Unreal asset/actor with appropriate simple collider, LODs and bounds.

Accept only after: Scale/pivot and outward normals verified; No accidental holes, floating parts or self-intersection; Collision and placement footprint verified; LOD transitions and shadows inspected.

### plant

Deliver: Editable plant mesh and material source; FBX/GLB, foliage atlas with alpha clipping; Unreal instanced foliage asset, wind weights, LODs and optional far impostor.

Accept only after: Readable silhouette at walking and overview distance; No giant transparent sheets or harsh atlas fringes; Roots meet terrain and footprint leaves navigation clearance; Wind, shadow and LOD behavior checked.

### character

Deliver: Audited reusable character source or new missing source; Rigged base/attachment and Unreal asset/actor integration; Material, proportion and equipment socket configuration.

Accept only after: Audit existing character/outfit work first; record reuse provenance; Bind pose, locomotion and deformation validated; Clothing, doors and tools fit supported proportions; Does not create extra inhabitants beyond simulation records.

### animation

Deliver: Editable animation source; Loop/action clips with events and root-motion policy; Unreal retarget/import setup.

Accept only after: No foot sliding or visible loop snap; Root/local-up and tool contact verified; Retarget test on human, dwarf and elf rigs; Gameplay event timing remains deterministic.

### vfx

Deliver: Editable texture/particle/shader source; Unreal effect prefab and documented parameters.

Accept only after: Effect bounds and stopping behavior verified; Overdraw/emission checked at player height; No gameplay hazard or water inferred from appearance alone; Low-quality toggle and distance culling verified.

### audio

Deliver: Original/licensed WAV source; Loop or event edits plus Unreal import/mixer settings.

Accept only after: No clipping or audible loop join; 3D attenuation and mix checked in scene; Licence/source recorded; no unlicensed borrowed soundtrack.

## Parameter and state boundaries

[Coverage and selector audit](COVERAGE.md) maps current generator outputs to these concrete IDs. Biome IDs are binding. Placement descriptions are design contracts for epic 009, not executable placement code. Unimplemented weather, geology, land-use and building-layout selectors remain explicit dependencies. Existing generated water/roads/population win over appearance decisions.

No automatic asset selection may spawn extra inhabitants, create ore reserves, add a water source, infer active volcanoes, or declare food available. Culture IDs choose style; they are not real-world ethnic labels. The catalogue separates material/biome variants from people identity.

## Reuse and deliberate exclusions

Character and outfit production is pending in Unreal; all PPL and ANIM entries start with a reuse audit. An approved existing asset can satisfy the job without regeneration, provided its source and verification are recorded. Role entries are assembly/configuration jobs, not unique NPC meshes.

Not in this current baseline: children/aging systems, full combat weapon/armour libraries, mounts/livestock/fauna/monsters, ships and ocean travel, interactive underground halls/caves, glaciers, reefs and floating islands. They require gameplay or generation scope that the current lab does not provide. Mine entrances, livestock pens and water wells are visual structures and must not invent their implied gameplay contents. Ruins/graves/historical sites similarly need a future location/history generator.

Epic 008 is the umbrella environment-library coverage checklist; Epic 009 integrates the math/placement contracts; Epic 010 executes this production list. Do not create competing production copies under 008.

## Evidence

[Catalogue audit](AUDIT.md) records coverage, counts, ID/dependency checks and remaining prototype decisions. All art and Unreal validation evidence is initially empty by design.
