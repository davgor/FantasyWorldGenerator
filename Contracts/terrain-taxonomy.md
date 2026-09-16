# Portable terrain taxonomy v1

ML-01a freezes terrain identities already supported by recipe 3. The canonical machine-readable registry is [`terrain_taxonomy.json`](../Sim/fantasy_world_generator/terrain_taxonomy.json), shipped inside the Python package. It is independent of the generator's implementation constants; conformance tests detect disagreements with the generator and exhaustive asset compiler.

## Identity and compatibility

The eight school IDs, in exported school order, are `weave`, `umbral`, `infernal`, `radiant`, `fire`, `water`, `earth`, `air`. Natural IDs are 0–8, 13 and 15–17, ordered numerically in the registry. IDs 9, 10, 11, 12 and 14 are retired and cannot be reused. Natural IDs are never array offsets. Stable variant IDs are `<natural core>.<school>`; their display labels are not identity.

There are no aliases, case folding, whitespace trimming or implicit semantic conversions. In particular, `holy` and `primordial` are not school IDs. Existing `ley_holy` and `ley_primordial` grids remain habitat compatibility projections (Radiant and the maximum elemental field), not new networks. The proposed Necrotic, Nature, Arcane and Storm vocabulary is not mapped to Umbral, Earth, Weave or Air. Adding such a mapping requires an explicit future contract decision.

This taxonomy has its own version 1 and supports recipe 3 only. It does not change world schema 2, recipe 3, any generator revision or seed replay. Changing ID meaning, accepted vocabulary, ordering or resolver behavior requires a new taxonomy version with independent fixtures; retired IDs stay reserved. This document supersedes the historical five-network vocabulary in the planning snapshot for this slice only.

## Python oracle

`fantasy_world_generator.taxonomy.taxonomy_document()` returns a fresh caller-owned registry. `resolve_terrain_identity(request)` accepts exactly these four fields:

```json
{"taxonomy_version": 1, "recipe_version": 3, "natural_biome_id": 13, "magic_school": "water"}
```

The response is:

```json
{"natural_biome_id": 13, "core": "marsh", "magic_school": "water", "variant_id": "marsh.water", "asset_id": "terrain.mutation.marsh.water"}
```

Use explicit `magic_school: null` for a natural surface; `variant_id` is then null and the asset identity uses `terrain.biome.<three-digit-natural-id>`. All fields are required and extra fields are rejected. Versions and natural IDs must be integer values, excluding booleans, floats and strings; adapters must reject or preserve that distinction when decoding requests. Unsupported versions, unknown/retired IDs and malformed inputs raise `ValueError`. Exception message text is diagnostic, not a stable machine error code. The function does not mutate input, generate a world or modify authoritative state.

## Asset ownership and evidence

All 13 natural identities and 104 variants already belong to the exhaustive potential-state asset catalogue. The resolver references those semantic requirements; consumers still own actual art and bindings. No new potential state or asset is introduced, so the asset compiler and existing artifact bytes remain unchanged. Tests resolve every generator catalogue entry and require matching compiled asset membership.

[`Fixtures/taxonomy-v1.json`](../Fixtures/taxonomy-v1.json) contains hand-authored expected examples and invalid requests for a future native implementation. Python tests additionally cover sparse IDs, all retired IDs, strict types, alias rejection, nonmutation and all 117 potential terrain states. Neither these fixtures nor Python tests establish native or Unreal conformance.

ML-01b adds [capabilities and coordinates](capabilities-and-coordinates.md); ML-01c/d adds the scoped [kernel identity, numeric and failure contract](kernel-v1.md). This terrain resolver remains an additive contract helper; existing world import/export validation does not call it yet.
