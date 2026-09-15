# Portable contracts

- `schemas/` contains export-only JSON envelopes for generated genesis data and the exhaustive potential-state asset list.
- `catalogues/world-assets.json` is a pinned semantic requirement input used to enumerate materials, vegetation, structures, effects, people roles, animation, and audio that supported generator states may require.

These files do not contain Unreal object paths or prove that game-owned assets exist. ML-01 will add the stable taxonomy, IDs, units, versions, numeric rules, capability description, and conformance fixtures needed by the native runtime.


The current world envelope is schema **2**, recipe **3**, generation algorithm **8**, phase schema **2**, magic schema **3**, terrain schema **6**, and history schema **1**. Population profiles and building-pack inputs use schema **2**; settlements use schema **9** and rural-human reports use schema **5**. Recipes 1/2 and old age/save contracts are rejected and must be regenerated. Natural IDs are sparse, never list offsets; retired IDs 9/10/11/12/14 are invalid. The 104 magical states use explicit `core.school` identities. See [the canonical behavior contract](../docs/terrain-world-layers.md).

The exhaustive asset-list schema is **2**, scoped to recipe **3**. Production selectors use natural `biome_ids` or exact `biome_variant_ids`; catalogue schema **2** is synchronized across this directory, the packaged JSON and the readable production manifest. No current export includes the retired terrain surfaces.
