# 016 — Standalone civilizations and city classes

2026-09-15. The user requested six independent replacements for generic humans, rejected profile inheritance, and confirmed one capital per human culture.

## Independent entities

Every population profile contains a complete trait record. There is no `extends` field or hidden human base. `mixed` is an aggregate configuration, not an ancestor or generated entity. New human and nonhuman entities use the same record format and are discovered from `civilization.kind`; specialized existing nonhuman habitat rules still apply.

Retire `human`, `highland` and `woodland`; reject these IDs rather than silently translating old cities.

- `human_maritime`: Maritime humans; Mediterranean inspiration.
- `human_desert`: Desert humans; Persian inspiration.
- `human_cold`: Cold peoples; Nordic inspiration.
- `human_large_island`: Large islanders; Eastern inspiration, at the breadth requested.
- `human_rainforest`: Deep rainforest humans; Aztec inspiration.
- `human_heartland`: Heartland humans; European inspiration and remaining human habitat.

These are game design directions, not historical demographic claims. Each entity owns all numerical traits, habitat rules and cultural metadata. `structure_blocks: human` refers only to the shared non-housing structure library; it is not profile inheritance. Shared geometry does not merge entity identity.

## Habitat priorities

The six human entities share an exclusive geography-allocation group. Lower priority wins; ID breaks ties. This allocation group is not a political union or capital group.

1. Cold: natural tundra, snow, boreal forest or cold tundra, or mean temperature <= 5 C.
2. Desert: natural desert core.
3. Deep rainforest: natural rainforest core with moisture >= 0.7.
4. Large islands: connected dry land >= 1 km², <= 15% of total dry land, excluding the largest-area landmass (including ties). This is a provisional game-scale island definition.
5. Maritime: maritime suitability >= 0.3.
6. Heartland: remaining human habitat.

Cold ports remain Cold peoples; rainforest coasts remain rainforest cultures. Natural biome cores preserve cultural geography under magical mutations. Actual cities still require suitable slopes, safety, capacity, spacing and support. No civilization is forced to appear. Overlapping populations share capacity once. All entity capacities are considered before applying the bounded shared city ceiling.

Survivors preserve their civilization, founding culture, UID and name when conditions change; new cities use current habitat. Ruins retain civilization and class at destruction. Reclassification does not alter ownership or create buildings.

## City classifications

Each nonempty civilization has exactly one **capital**: its highest-suitability active surface city, then lowest surface node for deterministic ties. A sole city is a capital regardless of score. Other cities are **medium** at suitability >= 0.65 and **small** below 0.65. Zero cities yields no capital. The medium threshold is provisional game balance.

`capital` is the canonical spelling; a capitol building is a separate structure. Classification is a label for subsequent layout budgets, not a population increase or free buildings, food or defenses. Sky settlements remain independent communities, not additional cities/capitals. Unsupported sky settlement choices leave their island geometry intact.

## Exports and compatibility

Recipe 3 now uses generation algorithm **9**, settlements **10**, population profiles **3**, building packs **3**, rural reports **6**, and civilization report **1**. The outer world envelope remains schema 2 and pins algorithm 9. The age API rejects algorithm-8 state. Older population/settlement seed results are intentionally incompatible and worlds require regeneration. Current configurations replay current results; civilization selection does not reroll terrain or raw magic.

`civilizations.entities` lists every entity, habitat metadata, regional index, city count and nullable capital node. `civilization_region` maps reachable support areas to these indices; -1 means unassigned wilderness. Existing `culture_region` and seed-local road-interaction groups remain separate. Neither layer declares political borders.

Cities export `civilization_id`, `city_class` and a classification reason. Building asset references enumerate eligible civilization IDs. The same 84 building asset identities remain shared candidates; this does not establish culture-specific art. The 492-job production catalogue stays unchanged pending its later rebuild. No new generator asset state is introduced solely by cultural identity.

## Verification and limitations

Tests cover independent records, retired IDs, habitat overlap and island bounds, dynamic extension, invalid rules, zero/one/many cities, ties and capital reassignment, replay, region ownership, upstream isolation and old-state rejection. Full simulation and asset/export regressions remain required. City dimensions and housing are unaffected. No Unreal importer, cultural art or packaged-game validation is claimed.

Decision 017 subsequently moves all definitions and specialized rules into the master registry and advances the civilization report to version 2; see [current authoring guide](../civilizations.md).
