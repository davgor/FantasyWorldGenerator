# Parameter-to-asset coverage

Recipe 3 / terrain schema 6. Numeric IDs select natural cores, including their magical variants. Exact `core.school` IDs select named magical states. Candidate assets remain subject to their water, slope, climate, activity and clearance gates. Omitted biome selectors are unrestricted; empty selectors match nothing. These are potential assets, not assets guaranteed in a sampled world.

## Natural cores

### 0 — Ocean

MAT-014, MAT-015, GEO-001, VEG-035, VEG-036, WATER-001, WATER-006, WATER-012, WATER-013, SND-001

### 1 — Tundra

MAT-002, MAT-008, MAT-017, MAT-030, MAT-034, MAT-035, GEO-002, GEO-003, GEO-004, VEG-004, VEG-013, VEG-014, VEG-022, TREE-007, TREE-008, TREE-009, TREE-010, TREE-011, TREE-012, TREE-013, TREE-014, TREE-015, TREE-016, TREE-017, TREE-018, TREE-019, TREE-020, TREE-021, TREE-022, TREE-023, TREE-024, TREE-025, TREE-026, TREE-027, TREE-028, TREE-029, TREE-030, FX-004, FX-010, SND-007

### 2 — Desert

MAT-004, MAT-005, MAT-013, MAT-014, MAT-018, MAT-020, GEO-002, GEO-005, GEO-009, GEO-010, GEO-016, GEO-018, VEG-003, VEG-021, TREE-055, TREE-056, TREE-057, TREE-058, TREE-059, TREE-060, FX-003, FX-010, SND-006

### 3 — Grassland

MAT-001, MAT-003, MAT-004, MAT-012, GEO-017, VEG-001, VEG-002, VEG-003, VEG-006, VEG-007, VEG-008, VEG-009, VEG-019, VEG-020, FX-001, FX-010, SND-005

### 4 — Forest

MAT-001, MAT-003, MAT-006, MAT-007, MAT-008, MAT-033, MAT-034, MAT-035, VEG-010, VEG-012, VEG-013, VEG-015, VEG-019, VEG-020, VEG-037, VEG-038, TREE-001, TREE-002, TREE-003, TREE-004, TREE-005, TREE-006, TREE-007, TREE-008, TREE-009, TREE-010, TREE-011, TREE-012, TREE-013, TREE-014, TREE-015, TREE-016, TREE-017, TREE-018, TREE-019, TREE-020, TREE-021, TREE-022, TREE-023, TREE-024, TREE-025, TREE-026, TREE-027, TREE-028, TREE-029, TREE-030, FX-001, FX-010, FX-012, SND-004

### 5 — Exposed rock

MAT-002, MAT-008, MAT-016, MAT-017, MAT-018, MAT-019, MAT-020, MAT-035, GEO-002, GEO-003, GEO-004, GEO-005, GEO-006, GEO-007, GEO-008, GEO-009, GEO-010, GEO-011, GEO-012, GEO-013, GEO-014, GEO-015, GEO-016, GEO-017, GEO-018, GEO-020, VEG-005, VEG-014, VEG-023, TREE-019, TREE-020, TREE-021, TREE-022, TREE-023, TREE-024, TREE-025, TREE-026, TREE-027, TREE-028, TREE-029, TREE-030, TREE-061, TREE-062, TREE-063, TREE-064, TREE-065, TREE-066, FX-010

### 6 — Snow

MAT-027, MAT-028, MAT-029, GEO-025, GEO-026, GEO-027, FX-004, FX-010, SND-007

### 7 — Rainforest

MAT-001, MAT-006, MAT-036, VEG-011, VEG-013, VEG-015, VEG-016, VEG-017, VEG-018, VEG-037, VEG-038, TREE-031, TREE-032, TREE-033, TREE-034, TREE-035, TREE-036, TREE-037, TREE-038, TREE-039, TREE-040, TREE-041, TREE-042, FX-001, FX-002, FX-010, SND-008

### 8 — Lake

MAT-010, MAT-012, MAT-014, MAT-015, MAT-029, MAT-031, GEO-001, VEG-025, VEG-026, VEG-028, VEG-029, TREE-043, TREE-044, TREE-045, TREE-046, TREE-047, TREE-048, WATER-002, WATER-003, WATER-004, WATER-005, WATER-006, WATER-007, WATER-008, WATER-009, WATER-012, WATER-013, FX-010, SND-002, SND-003

### 13 — Marsh

MAT-009, MAT-010, MAT-011, MAT-012, MAT-031, MAT-037, VEG-024, VEG-025, VEG-026, VEG-027, VEG-028, VEG-029, VEG-031, TREE-043, TREE-044, TREE-045, TREE-046, TREE-047, TREE-048, TREE-049, TREE-050, TREE-051, TREE-052, TREE-053, TREE-054, WATER-003, WATER-004, WATER-005, WATER-010, WATER-012, FX-001, FX-002, FX-010, SND-009

### 15 — Boreal forest

Terrain surface supported; no additional biome-specific production rows yet.

### 16 — Cold tundra

Terrain surface supported; no additional biome-specific production rows yet.

### 17 — Persistent land ice

Terrain surface supported; no additional biome-specific production rows yet.

## Magical states

Every state below has its own `terrain.mutation.<core>.<school>` surface asset. Core-matching production rows above also remain candidates. Additional exact-state rows:

- **Prismatic seas** (`ocean.weave`): no additional exact-state production rows.
- **Silent seas** (`ocean.umbral`): no additional exact-state production rows.
- **Brimstone seas** (`ocean.infernal`): no additional exact-state production rows.
- **Dawn seas** (`ocean.radiant`): no additional exact-state production rows.
- **Steam seas** (`ocean.fire`): no additional exact-state production rows.
- **Crystal currents** (`ocean.water`): no additional exact-state production rows.
- **Rootreef seas** (`ocean.earth`): no additional exact-state production rows.
- **Storm seas** (`ocean.air`): no additional exact-state production rows.
- **Dream tundra** (`tundra.weave`): no additional exact-state production rows.
- **Grave tundra** (`tundra.umbral`): no additional exact-state production rows.
- **Blighted tundra** (`tundra.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Blessed tundra** (`tundra.radiant`): no additional exact-state production rows.
- **Ember tundra** (`tundra.fire`): no additional exact-state production rows.
- **Rime tundra** (`tundra.water`): no additional exact-state production rows.
- **Mossbound tundra** (`tundra.earth`): no additional exact-state production rows.
- **Gale tundra** (`tundra.air`): no additional exact-state production rows.
- **Glass mirages** (`desert.weave`): MAT-013, MAT-023, MAT-032, GEO-022, GEO-023, GEO-024, VEG-034, FX-007, FX-010, SND-012
- **Haunted tombs** (`desert.umbral`): no additional exact-state production rows.
- **Hellglass wastes** (`desert.infernal`): MAT-005, MAT-013, MAT-016, MAT-019, MAT-021, MAT-022, MAT-023, MAT-032, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, GEO-022, GEO-023, GEO-024, VEG-032, VEG-034, FX-003, FX-005, FX-007, FX-010, FX-011, SND-012, SND-014
- **Golden sanctuaries** (`desert.radiant`): no additional exact-state production rows.
- **Furnace dunes** (`desert.fire`): no additional exact-state production rows.
- **Frostglass dunes** (`desert.water`): MAT-013, MAT-023, MAT-032, GEO-022, GEO-023, GEO-024, VEG-034, FX-007, FX-010, SND-012
- **Blooming dunes** (`desert.earth`): no additional exact-state production rows.
- **Whistling dunes** (`desert.air`): no additional exact-state production rows.
- **Possibility meadows** (`grassland.weave`): no additional exact-state production rows.
- **Ashen meadows** (`grassland.umbral`): no additional exact-state production rows.
- **Cinder blight** (`grassland.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Healing meadows** (`grassland.radiant`): no additional exact-state production rows.
- **Flamegrass plains** (`grassland.fire`): no additional exact-state production rows.
- **Dew meadows** (`grassland.water`): no additional exact-state production rows.
- **Titan meadows** (`grassland.earth`): no additional exact-state production rows.
- **Thundergrass plains** (`grassland.air`): no additional exact-state production rows.
- **Living storywoods** (`forest.weave`): MAT-006, MAT-007, MAT-025, MAT-033, VEG-010, VEG-013, VEG-033, TREE-001, TREE-002, TREE-003, TREE-004, TREE-005, TREE-006, TREE-067, TREE-068, TREE-069, TREE-070, TREE-071, TREE-072, FX-008, FX-010, FX-012, SND-013
- **Mourning woods** (`forest.umbral`): no additional exact-state production rows.
- **Thornhell woods** (`forest.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Sanctuary woods** (`forest.radiant`): no additional exact-state production rows.
- **Phoenix woods** (`forest.fire`): no additional exact-state production rows.
- **Rainveil woods** (`forest.water`): no additional exact-state production rows.
- **Ancient rootwoods** (`forest.earth`): MAT-024, MAT-039, VEG-037, VEG-038, VEG-039, FUNG-001, FUNG-002, FUNG-003, FUNG-004, FUNG-005, FUNG-006, FUNG-007, FX-006, FX-010, SND-011
- **Skyreach woods** (`forest.air`): no additional exact-state production rows.
- **Floating stonefields** (`exposed_rock.weave`): no additional exact-state production rows.
- **Ossuary crags** (`exposed_rock.umbral`): no additional exact-state production rows.
- **Demon spires** (`exposed_rock.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Hallowed heights** (`exposed_rock.radiant`): no additional exact-state production rows.
- **Molten crags** (`exposed_rock.fire`): no additional exact-state production rows.
- **Springstone cliffs** (`exposed_rock.water`): no additional exact-state production rows.
- **Living monoliths** (`exposed_rock.earth`): no additional exact-state production rows.
- **Windcarved spires** (`exposed_rock.air`): no additional exact-state production rows.
- **Chromatic snow** (`snow.weave`): no additional exact-state production rows.
- **Funeral snow** (`snow.umbral`): no additional exact-state production rows.
- **Sootsnow fields** (`snow.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Luminous snow** (`snow.radiant`): no additional exact-state production rows.
- **Smoldering snow** (`snow.fire`): no additional exact-state production rows.
- **Sapphire snow** (`snow.water`): no additional exact-state production rows.
- **Mosswarm snow** (`snow.earth`): no additional exact-state production rows.
- **Dancing snow** (`snow.air`): no additional exact-state production rows.
- **Everchanging canopy** (`rainforest.weave`): MAT-006, MAT-007, MAT-025, MAT-033, VEG-010, VEG-013, VEG-033, TREE-001, TREE-002, TREE-003, TREE-004, TREE-005, TREE-006, TREE-067, TREE-068, TREE-069, TREE-070, TREE-071, TREE-072, FX-008, FX-010, FX-012, SND-013
- **Withering canopy** (`rainforest.umbral`): no additional exact-state production rows.
- **Devouring jungle** (`rainforest.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Mercy gardens** (`rainforest.radiant`): no additional exact-state production rows.
- **Emberbloom jungle** (`rainforest.fire`): no additional exact-state production rows.
- **Deluge jungle** (`rainforest.water`): no additional exact-state production rows.
- **Colossal jungle** (`rainforest.earth`): MAT-024, MAT-039, VEG-037, VEG-038, VEG-039, FUNG-001, FUNG-002, FUNG-003, FUNG-004, FUNG-005, FUNG-006, FUNG-007, FX-006, FX-010, SND-011
- **Stormcrown jungle** (`rainforest.air`): no additional exact-state production rows.
- **Starlight lakes** (`lake.weave`): no additional exact-state production rows.
- **Stillwater tombs** (`lake.umbral`): no additional exact-state production rows.
- **Bloodglass lakes** (`lake.infernal`): no additional exact-state production rows.
- **Lustral lakes** (`lake.radiant`): no additional exact-state production rows.
- **Boiling lakes** (`lake.fire`): no additional exact-state production rows.
- **Winterglass lakes** (`lake.water`): no additional exact-state production rows.
- **Rootcradle lakes** (`lake.earth`): no additional exact-state production rows.
- **Suspended mist lakes** (`lake.air`): no additional exact-state production rows.
- **Spellmist marsh** (`marsh.weave`): no additional exact-state production rows.
- **Haunted marsh** (`marsh.umbral`): MAT-009, MAT-011, MAT-026, MAT-031, MAT-037, MAT-038, VEG-025, VEG-030, VEG-031, TREE-073, TREE-074, TREE-075, TREE-076, TREE-077, TREE-078, WATER-010, WATER-011, FX-002, FX-009, FX-010, SND-010
- **Corruption mire** (`marsh.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Purifying marsh** (`marsh.radiant`): no additional exact-state production rows.
- **Cinder mire** (`marsh.fire`): no additional exact-state production rows.
- **Tidal gardens** (`marsh.water`): no additional exact-state production rows.
- **Deep-root marsh** (`marsh.earth`): no additional exact-state production rows.
- **Cloudveil marsh** (`marsh.air`): no additional exact-state production rows.
- **Aurora woods** (`boreal_forest.weave`): MAT-006, MAT-007, MAT-025, MAT-033, VEG-010, VEG-013, VEG-033, TREE-001, TREE-002, TREE-003, TREE-004, TREE-005, TREE-006, TREE-067, TREE-068, TREE-069, TREE-070, TREE-071, TREE-072, FX-008, FX-010, FX-012, SND-013
- **Ghost pines** (`boreal_forest.umbral`): no additional exact-state production rows.
- **Charred blackwoods** (`boreal_forest.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Dawnlit pines** (`boreal_forest.radiant`): no additional exact-state production rows.
- **Firecone woods** (`boreal_forest.fire`): no additional exact-state production rows.
- **Mistbound pines** (`boreal_forest.water`): no additional exact-state production rows.
- **Ironbark taiga** (`boreal_forest.earth`): MAT-024, MAT-039, VEG-037, VEG-038, VEG-039, FUNG-001, FUNG-002, FUNG-003, FUNG-004, FUNG-005, FUNG-006, FUNG-007, FX-006, FX-010, SND-011
- **Singing pines** (`boreal_forest.air`): no additional exact-state production rows.
- **Shifting frostlands** (`cold_tundra.weave`): no additional exact-state production rows.
- **Deathfrost plains** (`cold_tundra.umbral`): no additional exact-state production rows.
- **Torment barrens** (`cold_tundra.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Peaceful frostlands** (`cold_tundra.radiant`): no additional exact-state production rows.
- **Ashfrost plains** (`cold_tundra.fire`): no additional exact-state production rows.
- **Bluefrost tundra** (`cold_tundra.water`): no additional exact-state production rows.
- **Lichenstone plains** (`cold_tundra.earth`): no additional exact-state production rows.
- **Force-swept tundra** (`cold_tundra.air`): no additional exact-state production rows.
- **Singing glaciers** (`land_ice.weave`): no additional exact-state production rows.
- **Sepulchral ice** (`land_ice.umbral`): no additional exact-state production rows.
- **Infernal glaciers** (`land_ice.infernal`): MAT-005, MAT-016, MAT-019, MAT-021, MAT-022, MAT-038, GEO-002, GEO-006, GEO-011, GEO-014, GEO-019, GEO-020, GEO-021, VEG-032, FX-003, FX-005, FX-010, FX-011, SND-014
- **Cathedral ice** (`land_ice.radiant`): no additional exact-state production rows.
- **Steamcut glaciers** (`land_ice.fire`): no additional exact-state production rows.
- **Everflow glaciers** (`land_ice.water`): no additional exact-state production rows.
- **Rootsplit glaciers** (`land_ice.earth`): no additional exact-state production rows.
- **Howling glaciers** (`land_ice.air`): no additional exact-state production rows.
