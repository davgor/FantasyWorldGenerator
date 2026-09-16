# Portable contracts

- `schemas/` contains export-only JSON envelopes for generated genesis data and the exhaustive potential-state asset list.
- `catalogues/world-assets.json` is a pinned semantic requirement input used to enumerate materials, vegetation, structures, effects, people roles, animation, and audio that supported generator states may require.
- `../Sim/icarus_sim/buildings.json` under `structure_blocks.common` is schema-1 design input for future city layouts for all civilizations: 80 non-housing requirements grouped into 11 blocks, with provisional dimensions, plot clearances, access and reuse candidates. It is not yet consumed by generation or the asset compiler. See [the measurement and layout contract](../docs/catalogue/human-civilization-blocks.md).

These files do not contain Unreal object paths or prove that game-owned assets exist. ML-01 will add the stable taxonomy, IDs, units, versions, numeric rules, capability description, and conformance fixtures needed by the native runtime.


The current world envelope is schema **2**, recipe **3**, generation algorithm **16**, phase schema **2**, magic schema **4**, terrain schema **6**, and history schema **1**. Population profiles use schema **4** and building-pack inputs use schema **3**; settlements use schema **14**, civilization reports use schema **2**, and rural reports use schema **6**. Algorithm-8/9/10/11 worlds and retired generic human profile IDs require regeneration. Recipes 1/2 and old age/save contracts are rejected and must be regenerated. Natural IDs are sparse, never list offsets; retired IDs 9/10/11/12/14 are invalid. The 104 magical states use explicit `core.school` identities. See [the canonical behavior contract](../docs/terrain-world-layers.md).

The exhaustive asset-list schema is **2**, scoped to recipe **3**. Production selectors use natural `biome_ids` or exact `biome_variant_ids`; catalogue schema **2** is synchronized across this directory, the packaged JSON and the readable production manifest. No current export includes the retired terrain surfaces.

Civilization identity, rules and appearance live in civilizations.json, which links the shared buildings.json libraries. See the [registry contract](../docs/civilizations.md). The former human-block catalogue path is a redirect notice.

Final-stage world exports may include `city_plans` version 4: local metre-scale rotated plots, canonical detailed elevation surfaces, terrain-routed streets, staffing, houses/apartments, ordered placement passes and explicit failures. See [the city planner contract](../docs/city-planner.md). Schema 2 of the world envelope remains compatible through this optional versioned section.

Arctic registry schema 6/revision 11 requires independent crop temperature, founding minima, and economy winter fishing fractions. Population budget 4 exports a map of founding minima; founding report 4 records the same map. Old worlds require regeneration.

Resolved height tiles use `schemas/height-tile.schema.json` version 1. See [coordinates, shared samples and metre units](../docs/continuous-terrain.md).

Final-world `world_scene` version 1 carries globally located buildings, streets, regional routes and shared junctions. See [the unified globe contract](../docs/unified-world-scene.md).

See [unified globe diagnostics](../docs/unified-world-scene.md) for algorithm-16 sky suspension, college spacing, aridity, ley alignments and lab tables.
