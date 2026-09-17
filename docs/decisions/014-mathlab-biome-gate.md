# 014 - FantasyWorldGenerator validation precedes landscaping production

Status: accepted product direction from the user's landscaping-pipeline request. Owner/evidence: [source UE-014](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/board/backlog/UE-014.md).

## Context and decision

The asset catalogue began with fifteen biome IDs while the live layered FantasyWorldGenerator recipe describes additional habitats and overlays. The user requires backporting decided biomes into FantasyWorldGenerator and validating new biomes there before the texture/foliage pipeline consumes them. The source contracts are [content catalogue](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/content-catalogue.md) and [worlds and persistence](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/worlds-and-persistence.md); [source Epic 014](https://github.com/davgor/icarusUnreal/blob/d551767cb1c3bd259bb00f56be1e52c2182c5ec3/docs/epics/14-landscaping-pipeline.md) owns staged delivery.

## Reason and alternatives

Producing biome-specific art before validating its environmental definition risks incompatible recipes and assets for habitats the generator cannot reproduce. Validating only in Unreal, or relying on a catalogue entry or attractive preview, does not satisfy the requested FantasyWorldGenerator-first ordering.

## Consequences

Reconcile existing definitions and backport missing decisions using explicit protected-file revisions. Version validation evidence and invalidate dependent recipes when consumed definitions change. Preserve independent layers and IDs; do not promote every regional overlay into a base biome. FantasyWorldGenerator acceptance and human art approval remain separate. This selects a workflow gate, not a final biome inventory, renderer, material-authoring provider or PCG implementation. No backport is performed in this planning task.
