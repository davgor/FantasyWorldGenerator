# Layered-world recipe 1

Launch from the repository root with `python tools/terrain_lab.py --serve`, then open http://127.0.0.1:8765. Python 3.12 and the standard library are sufficient. This remains a standalone mathlab; it does not mutate Unreal assets.

## Generation and controls

**Random** chooses a fresh uint32 seed and starts from canonical defaults, including a 129² grid. It never inherits prior manual edits. **Parameters** exposes grouped controls and explicit overrides, retaining the displayed world's seed. Reset clears overrides. Changing world size selects its radius unless the radius itself was explicitly overridden. Display and month controls do not regenerate the world.

The registry in `Sim/icarus_sim/terrain_world.py` defines public defaults, types, bounds, groups, descriptions and units. `POST /world/generate` accepts:

```json
{
  "recipe_version": 1,
  "seed": 42,
  "overrides": {
    "size": 65,
    "temperature_offset": -8,
    "archipelago_count": 7,
    "weave_strength": 0.9
  }
}
```

Unknown keys, nonfinite numbers, invalid types and unsupported versions fail with HTTP 400. Overrides equal to defaults still count as explicit choices. Recipe exports contain requested overrides, resolved settings, provenance and parameter definitions. The exported `config` also regenerates through `Config(**config)` and `generate(config)`.

Stronger explicit regional requests can bias prerequisites: draconic requests widen mountain belts, demonic requests strengthen Infernal influence, haunted sands strengthen Umbral influence, steampunk raises metal richness, dead seas raise salinity, starlight raises Weave strength, pirates favor archipelagos, and red sands dry climate. Direct prerequisite overrides take precedence. Exported `biases` explain these choices. Habitat still constrains placement; there is no guarantee every region manifests.

CLI defaults use the new recipe. Extension controls can be passed through the validated `--world_options` JSON object. `--world_recipe 0 --auto_parameters 1` retains the old seed-derived experiment; `--world_recipe 0 --auto_parameters 0` retains explicit legacy settings. The new recipe rejects automatic derivation to avoid silently replacing explicit settings. Prompt hashing remains hashing, not semantic prompt interpretation.

## Geography and independent layers

Mountain abundance widens collision uplift independently of relief height. Oceanic archipelagos uplift eligible oceanic foundations before erosion and water routing. Candidate clusters have occurrence, extent, island size/spacing, and weighted volcanic, atoll, continental-fragment or cold character. Very small features may be under-resolved; the world grid is not a detailed reef or bathymetry solver.

Aquatic fields distinguish reefs, lagoons, estuaries, bays, rocky coasts, kelp shallows, fjords and open ocean. Harbor quality is separate from fishing productivity. Salinity excludes salty lakes from freshwater access. Depth and land barriers constrain sea passages; tides, currents and detailed reef ecology are deferred.

Boreal forest, tundra and persistent land ice use monthly climate suitability. Seasonal snow and water ice overlay underlying terrain. Sea-water freezing thresholds depend on salinity. These are static monthly artistic proxies, not weather or glacier dynamics.

Weave, Umbral, Infernal, Holy and Primordial have independent named seed streams, node geometry, density, width, strength, instability and occurrence. Raw network fields remain unchanged by overlap; aggregate opportunity, opposition and population-specific risk are separate fields. Changing one network never rerolls another or changes upstream terrain/climate.

Regional overlays include demonic and draconic territory, piracy, steampunk, witch-hut opportunity, red sands, dead seas, starlight lakes, haunted sands, enchanted/fungal/crystal ecology and haunted marsh. Normal grassland remains a base biome. Regions export manifestation reasons and sampled area above the diagnostic threshold. Witch huts are isolated low-conventional-suitability sites; necropolises are landmarks. Beast habitat anchors can now select compatible draconic and infernal candidates; these remain placement proposals, not spawned actors.

## Settlements, sky and supply

Mixed populations add gnomes and coastal Tidekin sea elves alongside humans, dwarves and elves. Environmental preferences differ from cultural traits: maritime, islander, industrial and pirate. Islander status requires a small connected landmass; any eligible people may adopt it. Tidekin do not live underwater in this version.

Cities consider coastal support opportunities before placement. Additional coastal hamlets require a safe ground connection and viable landing. After exclusive fishing grounds are allocated, hamlet roles resolve to harbor, fishing, combined harbor/fishing or landing. Each ocean cell supplies at most one hamlet. Vessel reach, distance losses and monthly ice reduce delivered food; prospective fishing habitat is an upper bound, never harvested supply by itself.

Floating clusters have separate disk meshes, local relief, altitude climate, magical support, rainfall capture and food estimates. Surface elevation beneath them is unchanged. Inhabited islands have independent budgets and stable layer-qualified IDs; unsupported islands can remain empty. Their mesh coordinates are local east/radial-altitude/north metres. Island geometry and rain-capture yields are artistic approximations, not a hydraulic simulation.

The `world_economy` result is the authoritative new-recipe supply diagnostic. It combines existing farm export surplus, allocated fishing harvest, and independent sky production in a four-year monthly stress test. Roads, port-to-port sea routes and eligible air terminals have finite capacities, material costs and losses. Frozen sea paths reduce or close throughput. Air routes sample magical access and use clearance above sampled terrain. Imports require surplus and capacity; no same-month re-export occurs. Shortages stay visible and do not silently change population proposals.

The old `seasonal_food`/annual trade results are retained as a labeled ground-only baseline. They are not extra supply. Food units and residents-per-area calibration remain provisional; the experiment is not a demographic equilibrium, optimal logistics solver or moving-vessel simulation.

## Inspection and verification

The layered atlas combines independently toggled fields with per-layer opacity. It shows cities, coastal hamlets, sea/air connections and elevated islands. Select a month for snow, ice, route access and island climate; select an island for its separate mesh. Community cards report authoritative food coverage, shortages and fishing allocations. Regional diagnostics explain absence rather than manufacturing every zone.

Regression coverage includes legacy behavior, recipe reproduction, isolated overrides, independent networks, sphere seams/poles, finite exports, cold-climate distinctions, exclusive fisheries, freshwater rules, navigable routes, monthly conservation/throughput, sky budgets and phase isolation. Local tests run with `PYTHONPATH=Sim python -m unittest discover -s Sim/tests -q` (set the environment variable appropriately for your shell).

A fixed seed 0–7 sweep at 33² through stage 6 produced 0–4 eligible ocean clusters and 4–7 manifested regional influences. Mean sampled mountain/ridge area increased from 1.647 km² at abundance 1.0 to 1.676 km² at the default 1.3. This is a modest coverage increase, not a guaranteed number of discrete mountain peaks; the abundance control remains available for stronger experiments.

An implementation-time seed-42 sample measured roughly 11 seconds at 129² and 42 seconds at 257² before final population refinements, excluding JSON encoding/browser rendering. Full diagnostic JSON was about 30 MB and 116 MB respectively. These are observations, not performance guarantees; 129² remains the default. The richer exports deliberately retain individual fields and monthly diagnostics.

Moving tribes/circuses, the Underdark, underwater settlements and engine integration remain future work. Layer-qualified locations and settled-community metadata provide extension points without generating placeholder worlds.

## Beast nests (anchor schema 1)

From stage 7, `beast_nests` exports static dens, roosts, colonies, lairs and aquatic territories. All 381 catalogue entries have separate structured profiles in `Sim/icarus_sim/terrain_nest_profiles.json`; the candidate catalogue remains unchanged. Profiles are artistic first-pass parameters, not biological validation. Each has a stable species ID, habitat medium, temperature bounds, required fields, weighted preferences, size-based occurrence and spacing. Magical families require their associated ley field; glacier dragons require cold, deep aquatic species require depth, and marine/freshwater/shore anchors cannot substitute for each other. Migratory fish use freshwater spawning anchors; migrations are not simulated. Selected flying species may also anchor on independent sky layers using altitude climate and underlying ley influence.

The Beast nests parameter group exposes the global ceiling (120), per-species ceiling (2), density (1), fantasy occurrence (1), suitability floor (0.3), spacing multiplier (1), settlement clearance (250 m), and independent variation seed (0). Zero density or ceiling disables anchors; zero fantasy occurrence keeps real animals. Random mode resets these with all other defaults. Overrides and resolved values export through the existing recipe contract.

Generation uses at most 2,048 area-weighted draws of unique spherical surface nodes, plus sky candidates. Each species gets an independent occurrence and placement seed. Land/water, temperature and required influence checks precede weighted suitability; accepted anchors avoid settled cities, coastal hamlets and sky settlements on their own layer. Same-species spacing uses great-circle distances, including across the longitude seam. A seeded shared ceiling and one-anchor-per-cell rule resolve proposals; different species can have overlapping territories. Diagnostics distinguish disabled, occurrence lottery, missing sampled habitat/clearance, and shared-budget rejection. Absence is not proof no habitat exists: narrow rivers and tiny refuges may be missed at coarse resolution.

The atlas has a nest toggle, species filter (including absent species), location selector and clickable colored ring markers. Inspection shows profile requirements and actual weighted contributions. Species profiles, reasons, layer-qualified IDs and diagnostics are included in JSON exports. Nests do not change terrain, settlements, fisheries or food budgets. There is no prey accounting, hostility inference, creature count, cave validation, migration, monster asset or Unreal spawning integration. Underground-associated creatures use surface entrance/lair proxies; the Underdark is not generated.
