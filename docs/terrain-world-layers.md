# Layered world and history recipes

## Recipe 3: staged construction and two ages

The lab now defaults to recipe **3**, generation algorithm **16**, with sixteen stages. Launch with `python3 tools/terrain_lab.py --serve`. `--phase` stops computation at a stage; Previous/Next inspects saved states without regeneration:

1. Plate layout
2. Tectonic relief
3. Surface detail
4. Erosion and sediment
5. Connected water
6. Second tectonic relief
7. Valleys and gorges
8. Wind and rain
9. Leylines, over natural biomes
10. Founding, parent-race settlement rounds after magical biome classification
11. Roads
12. Populated regions, supporting hamlets and supply
13. Beasties and animals (then regional threat assessment)
14. Age transition 1 (ends with refreshed threat assessment)
15. Age transition 2 (ends with refreshed threat assessment)
16. Simulation complete

`POST /world/generate` accepts recipe **3** only, e.g. `{"recipe_version":3,"seed":42,"overrides":{"size":33,"phase":16}}`. Omitted recipe versions, the publishing CLI and the lab all default to 3. Recipes 1 and 2 are retired and rejected: existing worlds must be regenerated. Seed compatibility with those recipes is intentionally broken by the clean-start biome migration. Recipe 3 replays deterministically from its exported `Config`, including `world_options`. The standalone `world_recipe=0` geometry experiment remains a development tool, uses the current biome rules, and does not promise historical seed/save compatibility.

`build_stages` contains ordered content deltas: `layers` replaces named arrays, `removed_layers` deletes obsolete arrays, and `state` replaces named report sections (`null` deletes a section). Begin from empty layers and no stage-dependent sections. Apply deltas through the chosen stage. `materialize_stage` provides the Python counterpart of the browser reconstruction. Snapshots contain no timing values and never expose future cities, nests, magic, or ruins. Export downloads the complete generated history regardless of the stage being viewed. Content deltas avoid repeating every grid at every step; later society/economy reports still make full-history exports larger than recipe 1.

### Deep-time geography

The second tectonic pass represents a **50-million-year artistic epoch**. It rotates the original plate centers using their original angular velocity axes, backtraces each destination cell's crust, blends transported relief with the existing terrain, and applies uplift/subsidence from the shifted boundaries. Original plate identities and geometry remain inspectable alongside moved plates and elevation deltas. All resulting heights, slopes, land area, and hydrology use physical metres. The duration is narrative calibration; angular velocities are dimensionless, not Earth-calibrated rates.

Water is rerouted after this deformation. Previously active river cells that become dry and lose their river are gorge candidates. Former water footprints that become dry are valley candidates. The generator incises these beds and shoulders, then reroutes water again. `gorge` and `dry_valley` mark surviving dry abandoned features; `relic_gorge`, `relic_valley`, and `relic_incision` preserve provenance even if a cut refills. This is grid-scale geomorphology, not a water-volume/evaporation simulation or a sediment-conserving second erosion pass. Rainfall and rain-fed drainage are calculated afterward.

### Twelve leylines: eight known in three groups, four hidden (magic schema 3)

- **Raw magic:** Weave — chaos, creation, creativity; Umbral — necrotic, entropy, death, order.
- **Holy / unholy:** Infernal — demons, hellscapes, corruption, evil; Radiant — holy, healing, order, peace, righteousness.
- **Primordial:** Fire — fire, heat, renewal, chaos; Water — water, ice, currents, order; Earth — nature, ground, stone, roots, order; Air — wind, storms, chaos, force.
- **Outside:** Blood — sacrifice, lineage, vitality, hunger; Void — absence, entropy, unmaking, silence; Rot — disease, undeath, decay, rebirth; Eldritch — madness, wrong geometry, dominion of minds.

The four Outside schools are **hidden**: they are declared in the taxonomy, appended after the known eight so no existing index moves, and their occurrence is locked at `min == max == 0`, so no request can raise one during generation. A generated world always carries four empty networks and four all-zero fields for them. Only the corruption API places a node in one. They are also outside the world's own instruments: the moon charts no tide for them, no god of the known pantheon claims them, and player leyline edits at an age boundary are restricted to the known eight.

Every school has an independent seed/variation, occurrence, node count, width, strength and instability. Every key point and line also has an independent seeded intensity in 0.35–1.65. Network records retain stable node/line IDs, positions, connectivity, descriptor/group metadata and these intensities. Key-point Gaussian influence and line Gaussian influence contribute to local potency; endpoint intensity weights each line, and network strength scales its field. Overlapping raw school fields are preserved. Aggregate density, instability and opposing influences remain separate diagnostics.

A magical biome requires strongest local potency **at least 0.35**, and a lead of **at least 0.08** over the next strongest school, including schools from other groups. Ties, close contests, and weak magic retain the natural biome. Overlap itself does not force a mutation. `dominant_magic` indexes the exported school order, with −1 for weak/contested cells. The initial Leylines stage shows the unmodified natural biome; classification first appears at Cities.

`terrain_leyline_history.edit_network` validates copy-on-write changes to a node or line intensity (0–4), or adds a uniquely identified unit-vector key point. `evaluate_networks` rebuilds fields without rerolling any network geometry. Zero weakens a source to nothing. A new standalone point has local influence without fabricated connecting lines. This provides the simulation boundary for future player actions; no player editing UI or persistence/save importer is supplied. Callers must reclassify biomes and rebuild affected society after edits. Generated age changes and their nodes are already part of deterministic replay.

The `ley_holy` and `ley_primordial` grids are compatibility projections for existing habitat profiles: Radiant, and the maximum of the four elemental fields, respectively. They are not additional networks and are hidden from the normal leyline menus. Future profile revisions can specialize elemental creature requirements without changing the network contract.

### The moon and lunar surges (astrology schema 1)

One moon, not tidally locked, whose Still hemisphere carries radiant, water, earth and umbral and whose Restless hemisphere carries weave, fire, air and infernal, one school per quarter. Three seeded integer-day cycles (phase, spin, nod) with a coprime preference give each school a **tide** multiplier in 0.5–1.8 that surges when its quarter both faces the world and is lit. `astrology` exports the parameters, a 24-hour, 30-day, 12-month calendar and closed-form formulas (phase, rise hour after sunrise, illumination, leaning) so a game can tie day and night to the moon; `lunar_almanac` exports the reported year's month heads, events (full and new moons, surges, hollow nights, ascendant hemispheres) and the next grand alignment; `magic.networks[<school>].surged_strength` and `magic.lunar_surge` publish the strengths in force on the reported day; the `lunar_sensitivity` layer says how far each cell sways. The exported `ley_*` grids are the base field: a consumer applies `ley_s(t) = ley_s × (1 + lunar_sensitivity × (tide_s(t) − 1))`. Full contract in [the moon](astrology.md).

### Natural and magical biomes (terrain schema 6)

`natural_biome` carries the existing climate/hydrology classification, including the 13 supported natural surface categories: ocean, tundra, desert, grassland, forest, exposed rock, snow, rainforest, lake, marsh, boreal forest, cold tundra and persistent land ice. These are game-scale Earth-like categories, not an exhaustive scientific biome taxonomy.

`terrain.natural_biomes` and `terrain.magical_biomes` are separate catalogues. Every natural category has a named mutation for **all twelve schools: 156 potential variants**, of which the first 104 are the known eight and the last 52 belong to the hidden four. Each variant exports its natural `core`, `core_biome_id`, `magic_school`, group, descriptors, display color and asset ID. For example, **Haunted tombs** has `core: desert`, `magic_school: umbral`, necrotic descriptors and dark-brown RGB `[72,49,35]`. Examples elsewhere include Rootreef seas, Phoenix woods, Singing glaciers and Hallowed heights.

`biome_variant` is the magical catalogue index or −1. `biome` and `natural_biome` both carry natural IDs only. Natural IDs are stable and sparse: 0–8, 13, 15–17. **An ID is not an array offset.** `terrain.biomes` and `terrain.natural_biomes` contain the same 13 records; look them up by `id`. Each record includes its `terrain.biome.<three-digit-id>` asset ID. `terrain.magical_biomes` contains all 156 variants, with stable `core.school` IDs and `terrain.mutation.<core>.<school>` asset IDs. Catalogue positions 0–103 are the known eight and never move; the hidden four occupy 104–155, so a `biome_variant` index recorded before the hidden schools existed still means what it meant. The atlas and globe show natural color for cells without a winning mutation.

The old standalone categories—Desolation (9), Fungal forest (10), Crystalline desert (11), Enchanted forest (12), and Haunted marsh (14)—are removed from generation, profiles, building criteria and production selectors. These numeric IDs are reserved and invalid, never recycled. Haunted marsh still exists as the explicitly defined `marsh.umbral` variant. There is no compatibility phenotype or automatic conversion of old saved worlds.

Population profile schema **3** stores complete independent civilization records without inheritance. It has natural-only `biome_preferences` and `food_biome_multipliers`, plus `magic_biome_preferences` and `food_magic_biome_multipliers` keyed by exact `core.school` IDs. A matching variant overrides the natural value; otherwise the natural value applies (default preference 0, food factor 1). Population capacity and rural food use the same lookup, then apply the existing local magic-risk reduction. Contested/weak magic gets natural rules. Elven habitat uses forest, rainforest and boreal forest cores. Mineral-rich dwarven habitat may also use Glass mirages, Hellglass wastes and Frostglass dunes; existing relief, water and safety gates still apply.

The initial explicit food calibration carries harsh terrain penalties onto land Infernal variants, woodland food adaptation onto Earth woodland variants, dry crystal penalties onto the three named glass deserts, and haunted-wetland penalties onto `marsh.umbral`. This is provisional game balance, not a biological claim. Exact values are in `civilizations.json`; adding a new state never inherits a retired numeric category.

Building-pack schema **3** and production catalogue schema **2** match natural IDs or exact variant IDs. Core eligibility includes mutated versions of that core. Either selector list may match; all other criteria still apply. An omitted biome selector is unrestricted; an explicit empty selector matches nothing. Fungal art is eligible in Earth-altered woodland, enchanted woodland art in Weave woodland, glass/crystal desert art in the three glass deserts, scorched/desolate art in land Infernal variants, and haunted wetland art in `marsh.umbral`. These are candidate visual assets, never extra water, resources or population. The exhaustive asset compiler emits the full potential-state list, including states absent from a sampled seed.

Regional influence overlays remain independently inspectable opportunity fields, not biome categories. The geometry, climate, magic and food remain artistic approximations.

### Civilization ages (history schema 1)

Each age evaluates all existing **surface cities** against the same pre-age world. A seeded city/age lottery combines dominant local leyline potency, nearby eligible fantasy threats, and a small chance of magical self-destruction. Threats currently include named dragons and demonic, undead or aberrant families; their proximity influence decays over a bounded local reach. Species occurrence is not a guarantee of a city attack. A magic-disabled world has no magical self-destruction. This is an explicit artistic threat rule, not a general biological hostility inference.

Ruins retain a stable city UID, founding age, destruction age, source culture, population profile, location, reason, cause, lottery probability/draw and local evidence (school/potency or nest/distance/reach). Source culture records the city's founding society; later road/culture regrouping cannot erase it. The lab renders a broken-keep ruin icon on the globe and atlas, plus reason cards. Existing survivors retain their identity/name/location. Ruined city cells cannot immediately be chosen as new cities.

Wars are settled before any other fate. Two cities are in contention when they stand nearer than 1.5x the founding `settlement_spacing`, or when a road joins them and either one's own hinterland cannot feed it; both pressures come from quantities the world already reports, and a pair with neither is never at war. Contested pairs fight on a seeded draw that rises with pressure, strongest contention first. A war is named for the relationship between its participants, never its cause: `civil` inside one civilization, `regional` inside one parent race, `international` across parent races. The weaker side — residents plus the fortresses already watching its roads — is destroyed, and a tie goes to the lower uid. A city can be drawn into several wars in one age but is only lost once.

A war ruin carries `cause` `war_civil`, `war_regional` or `war_international`, and leaves a leyline key point where `dominant_school` says a school already held its ground, the same test the leyline threat uses. Both participants record the war in `war_history` with the outcome and the opponent's identity; survivors carry that history across the age rebuild, and a ruin keeps whatever its city had fought. `history.ages[].wars` lists every war of an age. Because a city lost to a neighbour cannot also be lost to a dragon, wars reduce how often the leyline, nest and self-magic causes fire.

Having fought raises a city's defences twice over: each veteran adds up to three to both the world's fortress demand and its ceiling, its ground outranks equally defensible ground when fortresses are placed, and its `regional_threat` gains up to 0.4, which the city planner reads as `defense_priority` for heavier walls. Rural report 8 carries `veteran_demand` and `veteran_cities` in `fortress_demand`; threat assessment 2 carries `war_pressure` and `wars_fought`. **Threat assessment 3 (2026-09-19)** adds the forward war outlook beside that backward pressure, from `terrain_wars.war_outlook`: `wars_recent` (wars fought in the assessed age), `enemy_living` (a former opponent still stands), `war_risk` with `war_risk_kind` and `war_risk_opponent_uid`, the strongest contention pressure a living neighbour exerts on the city, and `war_hunger` with `war_hunger_target_uid`, the pressure the city exerts on a road neighbour because it cannot feed itself (a supply-pressed pair has a direction: the hungrier city carries the hunger, the other the risk; a proximity-pressed pair gives both the risk). Each is exactly the pair pressure the next age's lottery draws against. `regional_threat` is unchanged, so fortification does not move; the outlook exists so a story layer can tell "they are coming" from "we once fought". World option `war_survival` (default 0, so every existing seed replays byte for byte) is the chance a defeated city survives a war as its victor's vassal instead of a ruin: such a war carries `outcome: vassalage`, `survival_chance` and `survival_roll`, leaves no fate, and the loser carries `vassal_of`. The native core mirrors the option but does not draw it yet; only zero is reproduced natively.

After all fates are decided, line and key-point intensities evolve independently by seeded factors 0.65–1.35, bounded at 4. Magical self-destruction leaves an intensity-2.5 Weave key point at the ruin. Then natural/environmental reports and magical variants are recalculated, civilization placement runs again against updated habitat, and roads, supporting hamlets, forts, colleges, fisheries and food budgets are rebuilt using active cities only. New eligible cities may appear within each people's remaining habitat capacity after survivors are counted; none are forced. Existing survivors persist, while current population/support estimates are recalculated. This is not a conserved population migration model.

The age lottery rolls under the moon. The age day is the founding report's end year × 360 before the transition; every potency a fate reads is scaled by `1 + lunar_influence × lunar_sensitivity × (tide − 1)` (world option `lunar_influence`, default 0.5), so a surge at the wrong moment is what kills a city while the fields themselves are untouched. `history.ages[].moon` records the day, phase, leaning and per-school tide. Every ruin now seeds a key point, `<ruin id>-key`, whose school follows the source of destruction (a school cause, Weave for self-destruction, the nest family's school, the war victor's culture), else the region's dominant school, else the ruined culture's school; intensity follows city class (small 1.5, medium 2.5, capital 3.5; self-destruction at least 2.5). Ruins export `legacy {school, intensity, basis}`. A god still walking the world departs when the age turns, leaving a footprint key point (see [pantheon](pantheon.md)); the pantheon is re-resolved at the end of every age.

Nests are reevaluated before city fates and after each age so all ages see current habitat and settlement clearance. Independent sky settlements are refreshed through the existing support model; surface-city ruin history does not yet simulate sky-city mortality or displaced populations. `history.ages` records losses, survivor UIDs and new city UIDs. Simulation complete freezes the second age's state.

### Regional threat assessments (schema 1)

After beast nests (stage 13) and again after each age transition (including `advance-age`), the world exports `threat_assessments`. Each active city receives a `regional_threat` in [0, 1] from eligible fantasy nest pressure (dragons and infernal/undead/aberrant families within the same reach rules as age-fate weights) plus dominant local leyline potency. Nest pressure is graded by danger tier at `0.11 x tier` falling off with distance, so a tier five lair at the gates keeps the flat `0.55` the single fixed weight used to give every monster alike, and a tier one nuisance contributes a fifth of it. Magical self-destruction is excluded from the standing score. Assessments are deterministic, versioned, and stage-isolated: earlier snapshots never expose later ages' scores. City fortification and capital multi-ring shape preference consume the latest assessment at plan time. Real-animal nests do not contribute; the score is not a creature count or hostility AI.

### Verification and boundaries

Behavioral coverage checks partial-stage equivalence, replay, finite JSON, seams/poles, all known network streams, that a generated world never raises a hidden one, competition thresholds, intensity edit validation, abandoned waterway classification, ruin culture retention, new key points, and active-city ownership of rebuilt hamlets/fishing ports. The exhaustive asset compiler includes all 156 variants and the city-ruins marker, regardless of which a seed realizes. Asset definitions do not imply built Unreal content. Review stage snapshots in the lab before downstream integration; metre-to-Unreal-centimetre conversion remains the future adapter's responsibility.

## Surface systems

The sections below describe the surface systems used by recipe 3. The separate nine-stage world recipe is retired. Launch `python3 tools/terrain_lab.py --serve` and open the reported loopback URL.

## Generation and controls

**Random** chooses a fresh uint32 seed and starts from canonical defaults, including a 129² grid. It never inherits prior manual edits. **Parameters** exposes grouped controls and explicit overrides, retaining the displayed world's seed. Reset clears overrides. Changing world size selects its radius unless the radius itself was explicitly overridden. Display and month controls do not regenerate the world.

The registry in `Sim/icarus_sim/terrain_world.py` defines public defaults, types, bounds, groups, descriptions and units. `POST /world/generate` accepts:

```json
{
  "recipe_version": 3,
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

CLI defaults use recipe 3. Extension controls can be passed through the validated `--world_options` JSON object. The world recipe rejects automatic parameter derivation; use explicit defaults and overrides. Prompt hashing remains hashing, not semantic prompt interpretation.

## Geography and independent layers

Mountain abundance widens collision uplift independently of relief height. Oceanic archipelagos uplift eligible oceanic foundations before erosion and water routing. Candidate clusters have occurrence, extent, island size/spacing, and weighted volcanic, atoll, continental-fragment or cold character. Very small features may be under-resolved; the world grid is not a detailed reef or bathymetry solver.

Aquatic fields distinguish reefs, lagoons, estuaries, bays, rocky coasts, kelp shallows, fjords and open ocean. Harbor quality is separate from fishing productivity. Salinity excludes salty lakes from freshwater access. Depth and land barriers constrain sea passages; tides, currents and detailed reef ecology are deferred.

Boreal forest, tundra and persistent land ice use monthly climate suitability. Seasonal snow and water ice overlay underlying terrain. Sea-water freezing thresholds depend on salinity. These are static monthly artistic proxies, not weather or glacier dynamics.

Weave, Umbral, Infernal, Radiant, Fire, Water, Earth and Air have independent named seed streams, node geometry, density, width, strength, instability and occurrence. Raw network fields remain unchanged by overlap; aggregate opportunity, opposition and population-specific risk are separate fields. Changing one network never rerolls another or changes upstream terrain/climate.

Regional overlays include demonic and draconic territory, piracy, steampunk, witch-hut opportunity, red sands, dead seas, starlight lakes, haunted sands, enchanted/fungal/crystal ecology and haunted marsh. Normal grassland remains a base biome. Regions export manifestation reasons and sampled area above the diagnostic threshold. Witch huts are isolated low-conventional-suitability sites; necropolises are landmarks. Beast habitat anchors can now select compatible draconic and infernal candidates; these remain placement proposals, not spawned actors.

## Settlements, sky and supply

Algorithm-8 worlds require regeneration. Settlement schema 10 and civilization report 1 expose entity identity and city class; rural report 8 carries architecture style keys, `civilization_region` and the route-defence demand independently of seed-local interaction groups.

Mixed populations select independent Maritime humans, Desert humans, Cold peoples, Large islanders, Deep rainforest humans and Heartland humans alongside dwarves, elves, gnomes and coastal Tidekin. The generic human/highland/woodland profile IDs are retired. Each nonempty civilization has exactly one suitability-ranked capital; other cities are medium at suitability >= 0.65 and small otherwise. Zero-city civilizations are valid. See [standalone civilizations](decisions/016-standalone-civilizations.md) for habitat priority, independent entity definitions, cultural region layers and compatibility. Environmental preferences differ from cultural traits: maritime, islander, industrial and pirate. Islander status requires a small connected landmass; any eligible people may adopt it. Tidekin do not live underwater in this version.

Cities consider coastal support opportunities before placement. Additional coastal hamlets require a safe ground connection and viable landing. After exclusive fishing grounds are allocated, hamlet roles resolve to harbor, fishing, combined harbor/fishing or landing. Each ocean cell supplies at most one hamlet. Vessel reach, distance losses and monthly ice reduce delivered food; prospective fishing habitat is an upper bound, never harvested supply by itself.

How much route defence a world asks for is read from the world, not from a constant. `humans.fortress_demand` reports it: the generated road network proposes one fortress per support reach of road length plus one per distinct river crossing, and a civilization cannot raise more than it has cities. `fortress_count` is a caller's ceiling over that proposal and never raises it; its default sits at the parameter bound so that it does not bind, and a request that lowers it still gets no guarantee. Defensible ground and the 200 m spacing decide how many of the requested forts exist, so a world with short roads and no crossings can legitimately hold none. Worlds generated before rural report 8 pinned every size to four fortresses and must be regenerated to gain the derived count.

Floating clusters have separate disk meshes, local relief, altitude climate, magical support, rainfall capture and food estimates. Surface elevation beneath them is unchanged. Inhabited islands have independent budgets and stable layer-qualified IDs; unsupported islands can remain empty. Their mesh coordinates are local east/radial-altitude/north metres. Island geometry and rain-capture yields are artistic approximations, not a hydraulic simulation.

The `world_economy` result is the authoritative new-recipe supply diagnostic. It combines existing farm export surplus, allocated fishing harvest, and independent sky production in a four-year monthly stress test. Roads, port-to-port sea routes and eligible air terminals have finite capacities, material costs and losses. Frozen sea paths reduce or close throughput. Air routes sample magical access and use clearance above sampled terrain. Imports require surplus and capacity; no same-month re-export occurs. Shortages stay visible and do not silently change population proposals.

The old `seasonal_food`/annual trade results are retained as a labeled ground-only baseline. They are not extra supply. Food units and residents-per-area calibration remain provisional; the experiment is not a demographic equilibrium, optimal logistics solver or moving-vessel simulation.

## Inspection and verification

The layered atlas combines independently toggled fields with per-layer opacity. It shows cities, coastal hamlets, sea/air connections and elevated islands. Select a month for snow, ice, route access and island climate; select an island for its separate mesh. Community cards report authoritative food coverage, shortages and fishing allocations. Regional diagnostics explain absence rather than manufacturing every zone.

Regression coverage includes retired-contract rejection, explicit variant food/asset rules, recipe reproduction, isolated overrides, independent networks, sphere seams/poles, finite exports, cold-climate distinctions, exclusive fisheries, freshwater rules, navigable routes, monthly conservation/throughput, sky budgets and phase isolation. Local tests run with `PYTHONPATH=Sim python -m unittest discover -s Sim/tests -q` (set the environment variable appropriately for your shell).

A fixed seed 0–7 sweep at 33² through stage 6 produced 0–4 eligible ocean clusters and 4–7 manifested regional influences. Mean sampled mountain/ridge area increased from 1.647 km² at abundance 1.0 to 1.676 km² at the default 1.3. This is a modest coverage increase, not a guaranteed number of discrete mountain peaks; the abundance control remains available for stronger experiments.

An implementation-time seed-42 sample measured roughly 11 seconds at 129² and 42 seconds at 257² before final population refinements, excluding JSON encoding/browser rendering. Full diagnostic JSON was about 30 MB and 116 MB respectively. These are observations, not performance guarantees; 129² remains the default. The richer exports deliberately retain individual fields and monthly diagnostics.

Moving tribes/circuses, the Underdark, underwater settlements and engine integration remain future work. Layer-qualified locations and settled-community metadata provide extension points without generating placeholder worlds.

## Habitat: animals and monsters (anchor schema 2)

From stage 13 the world exports two independent habitat passes: `wildlife` holds animal hunting grounds and `beast_nests` holds monster territory. All 638 catalogue entries (305 animals, 333 monsters) have structured profiles in `Sim/icarus_sim/terrain_nest_profiles.json`, each carrying a stable species ID, a `class` of `animal` or `monster`, a danger `tier`, habitat medium, temperature bounds, required fields, weighted preferences, occurrence and spacing. Animals additionally carry a feeding `role`; the 21 roles are described once in the same file and supply the biome table every animal of that role uses. Profiles are artistic first-pass parameters, not biological validation.

**Tier is danger to a player, 1 to 5** — 1 harmless, 2 can hurt you, 3 kills the careless, 4 kills the prepared, 5 a campaign threat. It carries the ecology: density falls geometrically with it, territory and settlement clearance grow with it, and it grades the monster pressure that decides whether a city survives an age. It replaces `size` in that duty. `size` had been doing it by accident, in lock-step with `spacing_m` and `occurrence` across the original 381 rows, which is why a gray wolf and a European rabbit shared an identical placement rule.

**The book is a pyramid too (profile document version 2, 2026-09-18).** A tier is a share of the world divided among its members, so the catalogue's own shape decides how often a player meets the rare thing: forty campaign threats authored against twenty nuisances gives each dragon a bigger slice than each grave mite. The first tier pass derived tier from size with a per-family offset, which left the monster book top-heavy — 21 / 24 / 56 / 46 / 45 across tiers one to five, sixteen of twenty-one draconic rows at tier five, and three families (holy, fey, fantastic) with no campaign threat at all. Version 2 re-tiers 32 rows against the definitions above (drakes are not dragons; skeletons and zombies can hurt you rather than kill you; liches, the great sea monsters, the judgment titan and a walking fey court are campaign threats; shrine-carrying tortoises and grazing giants are not) and adds 141 monsters and 116 animals weighted to the harmless end: vermin, sprites, hounds, drakes and the like for every family, and on the animal side the everyday creatures the first roster lacked (rats, mice, cats, feral and wild dogs, possums, skunks, weasels, mongooses, monkeys and apes, pandas and other bears, deer, goats, camels and kangaroos) alongside amphibians, venomous snakes, scavengers, shore animals and megafauna (elephants, rhinoceroses, hippopotamus, water buffalo, gaur). The monster book now runs **72 / 81 / 81 / 56 / 43** and the animal book **174 / 62 / 50 / 19 / 0**; every monster family spans all five tiers, and `test_the_book_is_a_pyramid_too` holds both shapes. Draconic keeps the most campaign threats by design. Budgets are per medium, so the water tiers are authored across families as well, and with several fantastic (non-ley) species at each low tier: every other family's water monster requires ley potency, which is low at sea and rarely clears the 0.3 suitability floor there, so in practice the sea belongs to the fantastic family and a lone fantastic species at a tier inherits that tier's whole sea. That ley gating at sea is inherited authoring, not a rule, and is the next thing to revisit if magical sea monsters are wanted in numbers. Because the tier budget is divided among whoever qualifies, **any catalogue change moves every seed's placement**: worlds generated against version 1 do not replay against version 2, and the ML-03e packaged habitat counts predate it.

**Biome tables are range maps.** Keys are decimal strings of natural biome ids, matching the `biome_preferences` convention; an absent biome is ground the species does not use, and a species table overrides its role's.

Placement is a thinned point process over the ground rather than a fixed anchor budget. For species `s` in cell `c` the intensity is `occurrence x suitability x biome_weight x area`, normalised so that **danger tier `t` receives `density x falloff^(1-t)` groups per square kilometre**. That budget is set per medium — once over the world's land, once over its water — because land and sea are separate ecosystems and a world's land should not be emptied by how much ocean it has. Each cell then places `floor(lambda) + [u < frac(lambda)]` groups and picks the species in proportion to its share, which is an exact discretisation built from one uniform draw and a cumulative weighted pick. Settlement clearance is folded into the intensity rather than rejecting a draw after the fact. Counts therefore scale with habitable area: doubling the land doubles the creatures, with no cap anywhere.

The two passes differ only in what refuses a candidate. **An animal competes with its own species only** — a wolf range over a deer range is the point of the map, not a collision. **A monster is refused only by an equal or greater monster**, so lesser lairs nest inside a greater territory and hunting grounds overlap by construction. Each anchor exports a centre and a `range_m` (half the authored spacing); `den` marks the ones that are a findable place to raid rather than only a range where the creature is met.

The Beast nests parameter group exposes animal density (2.8 groups/km2), monster density (0.14 lairs/km2), the two tier falloffs (4 for animals, 2.2 for monsters), overall density (1), fantasy occurrence (1), suitability floor (0.3), spacing multiplier (1), settlement clearance (250 m at tier 3), a per-pass hard cap (0 = systemic) and per-species cap (0 = systemic), and an independent variation seed (0). Zero overall density empties both passes; zero fantasy occurrence keeps animals and removes monsters. When the hard cap has to bite it keeps the highest tiers. Overrides and resolved values export through the existing recipe contract.

The atlas has a nest toggle, species filter (including absent species), location selector and clickable colored ring markers. Inspection shows profile requirements and actual weighted contributions. Species profiles, reasons, layer-qualified IDs and diagnostics are included in JSON exports. Habitat does not change terrain, settlements, fisheries or food budgets. These remain static habitat proposals: there is no prey carrying capacity, herd size, population, hostility inference, migration, patrol or runtime spawning, and a range is where a creature may be met, not a simulated animal. Absence is not proof no habitat exists: narrow rivers and tiny refuges may be missed at coarse resolution. Underground-associated creatures use surface entrance/lair proxies; the Underdark is not generated.

## Advancing a live world through the age API

`POST /world/advance-age` accepts age API **1** and returns the updated world. The same engine-independent entry point is `terrain_history.advance_age_request(body)`. The lab also has an **Advance age** button once creature generation is complete.

The age boundary also requires `astrology` and `lunar_almanac` version 1 with a structurally valid moon, and `religion` version 1 with the current pantheon catalogue identity; worlds exported before those contracts must be regenerated. `POST /world/summon` (`terrain_visitation.visitation_request(body)`, visitation API **1**) lets the orchestrator summon a manifest or sleeping god to a land target or send a walking one home; it is stateless like the age API and appends a `visitation` or `departure` stage. The gods otherwise change nothing: see [pantheon](pantheon.md). The moon is controllable from the API: generation overrides `moon_variation`, `moon_synodic_days`, `moon_spin_days`, `moon_nod_days`, `moon_tilt_degrees` and `lunar_influence`; `POST /world/moon` answers the sky and the surge at any day or hour; `advance-age` takes an optional `moon_day` and `summon` an optional `day` (see [the moon](astrology.md)).

```json
{
  "api_version": 1,
  "world": "replace this string with the existing exported world object",
  "steps": 1,
  "leyline_edits": [
    {"school":"fire","new_node":{"id":"player-volcano","direction":[1,0,0],"intensity":2.5}},
    {"school":"weave","node_id":"weave-node-0","intensity":0.2}
  ]
}
```

`world` must be the actual object, not a filename or the placeholder string shown above. Both `steps` and `leyline_edits` are optional. Steps are bounded to 1–10 per call; age numbering continues beyond the two genesis ages. Pass the returned world to the next call. Retries against the same original input reproduce the same output; this stateless endpoint does not persist or advance a server-owned world. The caller's Python object is not mutated.

The API validates recipe 3 / algorithm 12 through stage 13 or later, settlement/civilization identity and classification, supported magic/history versions, grid dimensions, finite numbers, spherical seams/poles, natural biome IDs, city/node locations, physical scale, and network IDs/endpoints/intensities. Invalid requests return HTTP 400. At most 128 leyline edits are accepted per request. Nodes are bounded to 1,024 and lines to 4,096 per school. The endpoint's body ceiling is 256 MiB (other lab JSON requests retain 64 KiB). Very large worlds can omit `build_stages` when only the current state is needed; the core age operation does not depend on visual history.

Player leyline edits are applied before environmental/biome refresh. **Both habitat passes are recalculated before each age's city-fate decisions and again after the age's biome/civilization rebuild**, and `beast_nests` exports `evaluated_age`. **Regional threat assessments refresh after those post-age nests** (and once after the initial beasties stage). Thus time skips and significant player changes do not reuse an obsolete creature distribution or fortification threat score. The surface geography is preserved through these civilization ages. Terrain-changing player systems must supply coherent rebuilt hydrology/climate before using this boundary.

`history.operations` records API steps and leyline edits. `history.ages` records each outcome. When supplied, saved build history gains an inspectable step for each additional age. Genesis `config.phase` remains within its 1–16 recipe range; `phases.completed` can exceed 16 in an advanced world. Config-only replay reconstructs genesis; persist the returned runtime state and operation record to preserve player actions. There is no database, authentication service, multiplayer arbitration, or Unreal save importer in this loopback lab.

### Civilization data boundary

The [master registry](civilizations.md) owns entity traits, placement/economy/sky rules, colors and links to shared construction libraries in buildings.json. Civilization report version 2 exports its revision/hash and presentation data. Age advancement requires the same registry identity; report-1 saves require regeneration. Parent-race founding changes city placement under algorithm 10; regenerate algorithm-9 worlds.

Registry schema 2 / revision 3 requires independent small_city, medium_city and capital_city planning blocks for every entity. These measured presets do not yet change runtime layouts. The changed registry identity requires regeneration of revision-1 worlds before age advancement; see the [city preset contract](civilizations.md#preconfigured-city-size-blocks-registry-schema-2-revision-2).

Registry schema 3 / revision 3 adds staffing rosters and worker-bed estimates to measured city plans. This planning data does not modify simulated population, generated layouts or NPC state. The changed registry identity requires regeneration before age advancement; see the staffing contract in civilizations.md.

### City shape planning catalogue

The independent [historical city shapes catalogue](city-shapes.md) supplies sourced morphology patterns and deterministic location selection for future city planning. It does not yet alter generated layouts, roads, population or assets. A future footprint adapter must provide the documented site facts, and runtime integration must add the catalogue identity to seed/save compatibility checks.

## Final-world city plans

The [city planner](city-planner.md) adds versioned measured plots and worker housing after simulation. The [hamlet planner](hamlet-planner.md) then packs support hamlets into a separate `hamlet_plans` section using dedicated rural building IDs. The [castle planner](castle-planner.md) assembles fortification modules from fortress pins into `castle_plans`. The exhaustive asset list includes schematic potential identities for city, hamlet and castle structures plus housing profiles; these are not production art. Terrain recipe and algorithm remain unchanged.

### Founding and preview resolution

Algorithm 10 replaces simultaneous city selection with [parent-race founding rounds](civilizations.md#founding-rounds-revision-8). Exported settlement report 11 records attempts and turn numbers. Terrain algorithms are unchanged, but city results and dependent society/history results differ from algorithm 9; regenerate old saves.

The live preview offers 16, 32, 64 and 128 cells per side (17, 33, 65 and 129 samples including boundary vertices). The prominent resolution selector affects random and parameter generation. Regenerate this seed preserves the current seed and explicit overrides while recomputing at the selected resolution; higher fidelity can change resolved geography and founding sites. Static exported previews cannot regenerate. The globe mesh-density control only changes display sampling, not simulation resolution.

The current migration revision uses algorithm 11, settlement report 12 and founding report 2. See [migration and cultural divergence](civilizations.md#migration-and-cultural-divergence-revision-9) for parent origin separation, Hill Dwarves, participation rates, lineage and 250-year rounds. Old algorithm-10 worlds must be regenerated.

Current founding includes [diaspora rounds](civilizations.md#diaspora-rounds-revision-10), using algorithm12, settlement report13 and founding report3. Periodic unused-civilization settlement can exceed ordinary quotas by one supported city per parent, within the global city ceiling. Regenerate algorithm11 saves.


Current Arctic specialization uses algorithm 13 and settlement report 14. See [Arctic settlements and Frostholds](civilizations.md#arctic-settlements-and-frostholds-revision-11) for independent crop temperature, per-civilization founding minima and bounded winter fisheries. Regenerate algorithm-12 worlds. Physical terrain generation is unchanged; civilization selection and downstream history/economy differ.


Algorithm 14 adds [continuous local terrain](continuous-terrain.md), terrain detail 1 and city planner 3. Region-scale geography remains unchanged; local city geometry now follows the shared detailed surface. Regenerate algorithm-13 worlds.


Algorithm 16 adds [varied clustered leyline networks and a unified globe scene](unified-world-scene.md), with magic report 4 and city planner 4. Natural biome colors are preserved beneath school-colored mutation outlines. Regenerate algorithm-14 worlds.

See [unified globe diagnostics](unified-world-scene.md) for algorithm-16 sky suspension, college spacing, aridity, ley alignments and lab tables.
