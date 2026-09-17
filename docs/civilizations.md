# Civilization master registry

Civilization definitions and city selections live in [civilizations.json](../Sim/icarus_sim/civilizations.json). Shared building data lives in [buildings.json](../Sim/icarus_sim/buildings.json). Both ship with the Python package. The former population, building-pack, layout-profile and human-block JSON files are redirect notices, not independent datasets.

## Contents

- `parent_races`: human, elf and dwarf blocks, each containing a name and a `civilizations` map of complete independent definitions. Human contains all six human cultures; elf contains elf and tidekin; dwarf contains dwarf and gnome. These are organizational parents, with no runtime inheritance.
- `civilization_order`: explicit stable generation order across nested blocks, preserving seed ordering when parent blocks are rearranged. Every civilization must appear exactly once.
- Each entity owns `population` (identity, traits and adaptation), `settlement` (habitat and placement rules), `economy`, `sky`, `presentation` (map/building colors), and `buildings` (explicit library bindings).
- `configurations`: aggregate generation settings, currently `mixed`. These are not civilizations or ancestors.
- `defaults`: selected profile, aggregate configuration and common display/reason defaults.
- `city_classification`: one capital per nonempty entity, retaining a surviving parent founding capital, otherwise choosing highest suitability then lowest node; medium cities start at suitability 0.65. Remaining cities are small. No city is forced for an absent civilization. Sky settlements remain separate.
- In `buildings.json`, `building_packs` and `layout_profiles`: shared reusable construction libraries. Entity bindings control allowed packs, options and layout features; an empty feature selector disables that feature.
- In `buildings.json`, `structure_blocks.common`: measured planning requirements. The shared library contains 80 non-housing structures in 11 blocks. Its dimensions are provisional design inputs in metres; the final-world city planner places eligible measured requirements and worker housing. See [measurement rules](catalogue/human-civilization-blocks.md).
- In `buildings.json`, `structure_blocks.rural`: dedicated hamlet structures (13 rows including track) plus `housing_profiles.hamlet_house`. Every entity binds the `rural` library and owns a `hamlet` preset. See [hamlet blocks](catalogue/hamlet-blocks.md) and the [hamlet planner](hamlet-planner.md).

## Add or edit a civilization

1. Add a stable lowercase ID inside the chosen `parent_races.<race>.civilizations` block, with all six definition sections, the three city-size blocks and the `hamlet` block. Copying an existing full entry is an authoring convenience only: the resulting entry is independent.
2. Set its name, identity and population traits. Configure habitat expressions and settlement/economy/sky parameters using the existing keys. Empty habitat expressions match everywhere.
3. Set its colors and explicit building-pack option, layout-feature and structure-library bindings. Include the fallback pack binding. New assets also need valid library records and exhaustive asset compilation coverage.
4. Increment the registry `revision` for a content change. Preserve existing IDs and order when compatibility matters. Run `python -m unittest discover -s Sim/tests` with `PYTHONPATH=Sim`, and the repository validator.

Habitat rules support `all`, `any`, and supported field comparisons (`in`, `min`, `max`, `gt`, `equals`); consult the existing entries and `validate_habitat` in `terrain_profiles.py` for the accepted grammar. Existing rule capabilities allow JSON-only additions. A genuinely new mechanic still requires engine code, behavioral tests and documentation.

The loader rejects duplicate JSON keys, nonfinite numbers, unsupported schemas, incomplete profiles, invalid bounds and missing library references. It reloads after the file modification time or size changes. Edits affect subsequently generated worlds, not a world already displayed.

## Replay and compatibility

Registry schema version 6 (revision 12) describes this document; `revision` identifies authored updates. Civilization report version 2 exports the registry revision and SHA-256 identity plus presentation data. The hash ignores whitespace but retains object order because order can affect generation. Age advancement rejects a saved world from a different registry; regenerate or explicitly migrate it before advancing.

This migration preserves recipe 3 / algorithm 9 placement and asset output for the unchanged shipped definitions. Report-1 saves must be regenerated. A seed alone is insufficient after authored rules change: retain the matching registry and generator version for replay. There is no Unreal integration implied by these data or tests.

## Preconfigured city size blocks (registry schema 2, revision 2)

Every entity directly owns `small_city`, `medium_city`, and `capital_city`. Each is a complete list, with no inheritance between cultures or tiers. Edit the desired entity/tier directly. Settlement class `small` selects `small_city`, `medium` selects `medium_city`, and `capital` selects `capital_city` in a future placement caller.

Each block has `buildings` entries with `structure_id`, culturally appropriate `name`, positive integer `count`, and `placement_conditions`. References resolve to the measured `structure_blocks` library, retaining purpose, dimensions, clearances, plot reservation, access and prerequisites. These are functional building/compound/open-space requirements, not guaranteed unique art assets.

- Small: 29–31 instances before site-condition filtering, essential water, sanitation, food, repair, market, civic, care, faith and watch services.
- Medium: 57–62 instances, repeated neighborhood services plus guilds, school, treasury, garrison and trade facilities.
- Capital: 82–87 instances, further service capacity plus library, great temple, command keep and isolation facility. These are provisional budgets for the class; a sole city still gets the capital preset, even when its population is small. Population-driven reductions are not implemented.

Maritime, islander and Tidekin lists include shore-dependent docks and later boatyards. Desert lists favor cisterns and caravan services; cold lists include food preservation and fuel; rainforest lists favor cisterns, remedies and ceremonial spaces. Dwarves add smelting and secure stores, elves remedies and learning, gnomes laboratories and fabrication. All entities remain independently editable. All entities explicitly reference shared `building.*` definitions in buildings.json. There is no human ownership or inherited human building dataset.

`infrastructure` separately lists streets, drainage, boundary walls, conditional bridges, defenses and (where relevant) terraces/ramps. Its `quantity_mode: fit_route_or_perimeter` requires the future planner to calculate segment counts and orientation. Building quantities do not include these segments. Walls and gates require a defended perimeter; docks require a navigable shore; wells require usable groundwater. Other condition names are validated against `PLACEMENT_CONDITIONS` in the loader. An empty conditions list does not waive the referenced structure's textual safety/access/supply requirements.

`civilization_registry.city_plan(entity_id, city_block)` returns an independent copy with all referenced measurements expanded, in metres. It preserves condition tags and requirements for the future site resolver. It does not evaluate conditions, reserve coordinates, claim ground feasibility, or create meshes. The result declares `runtime_placement_enabled: false`. The expanded preset itself does not place coordinates. The final-world planner consumes it to place schematic plots and worker housing; final cultural art remains deferred.

Schema 1 master files are rejected because the three blocks are now required. Revision 2 changes the registry hash, so worlds generated under revision 1 must be regenerated before age advancement. Recipe 3 / algorithm 9 and the civilization report version 2 are unchanged.

## Staffing and worker housing (registry schema 3, revision 3)

All 80 measured structures define `staffing`: `basis: distinct_people_all_shifts`, `housing_location` (city or hinterland), `roles`, and `notes`. Each role has integer `minimum`, `target`, and `maximum` counts per building instance. These are provisional game-design budgets, not researched historical employment figures. Minimum means lean operation, target ordinary operation, maximum fuller staffing; these are not population limits or confidence intervals.

Counts include working owners, staff, apprentices and rostered guards where listed. They already count different people across all shifts: do not multiply by shift count again. Customers, visitors, patients, students and dependents are excluded. Each post assumes a different NPC. Sharing workers between jobs or combining service buildings requires a future explicit assignment to avoid double counting.

For example, a smithy has 1/1/2 smiths and 0/1/2 apprentices: minimum 1, target 2, maximum 4 workers. Two smithies contribute 2/4/8 workers. City workers each need a sleeping place under the current assumption; hinterland workers need accommodation outside the city. Commuting, institutional beds and household composition are not modeled. Barracks count soldiers but do not silently supply beds while housing is deferred.

`city_plan(...)` expands each roster and supplies per-building `staffing_totals` multiplied by `count`. The `staffing_summary` separates `unconditional`, `conditional`, and `all_configured`. Each contains minimum/target/maximum `workers`, `city_worker_beds`, and `hinterland_worker_beds`. Conditional entries have placement-condition tags; exclude their workers when those facilities are not placed. Unconditional entries still require textual site/supply checks. These are planning scenarios before site validation, not confirmed resident counts.

An entity's size-block building entry may provide a complete `staffing` override. It replaces the shared library roster for that entry alone. Validation checks role IDs, duplicates, integral bounded counts, range ordering and housing location.

Linear infrastructure has no staff per segment. Maintenance and patrol crews are budgeted at service buildings such as mason yards, waste yards and guardhouses. Shared notice spaces, shrines, training yards and secondary squares have no dedicated roster: civic, temple or garrison staff serve them. Market management and permanent stall merchants are separate; itinerant sellers are excluded.

`total_residents` and `houses_required` remain null. Worker beds are the employment-driven housing input; dependents, nonworking residents, households and beds per home must be added before calculating total population or house counts. Temporary construction and seasonal supply-chain labor are outside these operating rosters.

Current Heartland target worker beds are 86 small / 188 medium / 285 capital if every listed facility is placed; before conditional additions they are 85 / 161 / 235. Staffing exposes the cost of the existing generous lists without validating or reducing their scale. The generator's population estimate remains separate until land, services, employment and housing are reconciled.

Schema 3 requires staffing on every measured structure and rejects schema-2 registry files. Revision 3 changes the registry hash, requiring regeneration of revision-2 worlds before age advancement. Recipe 3 / algorithm 9, report version 2, building selections, runtime layouts and asset output are unchanged. No NPCs or housing are created by these planning calculations.

## Core guild hall (registry revision 4)

Every civilization and every city-size preset includes exactly one unconditional guild hall. The existing `building.guildhall` measured requirement is now core; its 12 x 18 x 10 m footprint and 16 x 27 m plot are retained. It supplies a communal guild gathering space, kitchen and bar. The prior trade-guild prerequisite and officer/clerk roster are removed.

The minimal roster is one cook (kitchen staff) and one bartender: minimum, target and maximum are all two distinct workers, requiring two city sleeping places. This is a modest service roster, not a promise of round-the-clock opening. Heroes, membership, guild officers and hero accommodation are not included. The opt-in [hero guild planner](hero-guild.md) now calculates separate membership/activity/service/accommodation scenarios. It does not change this existing roster or generated city state.

Schema remains 3; authored revision advances to 4, changing the registry hash and requiring regeneration of revision-3 worlds before age advancement. This updates planning presets, not runtime coordinate placement or asset identities.

## Linked building registry (civilization schema 4 / revision 5)

The top-level `building_catalogue` link is `{"path":"buildings.json","schema_version":2}`. It resolves only to the sibling file, not to a network URL or arbitrary path. The building registry has its own schema (`fantasy-world-generator.building-registry`), schema version 2 and revision 4. Increment the edited file's revision when authored content changes.

`buildings.json` owns measured definitions (dimensions, clearances, staffing, requirements and reuse candidates), runtime building packs and layout libraries. `civilizations.json` owns civilization rules, pack/feature bindings, complete small/medium/capital selection lists, counts, display-name overrides and optional staffing overrides. The measured library ID is `common`, and references such as `building.guildhall` are neutral across races. Old `human.*` measured IDs are retired; existing runtime asset/pack IDs remain stable.

The loader joins both files into a validated in-memory view. `load_registry()` and `section()` return resolved copies for engine callers; do not serialize those expanded views over the source civilization file. Embedded duplicate libraries are rejected. Missing files, duplicate/unknown measured IDs, unsupported versions and invalid links fail instead of silently falling back. Changes to either file invalidate the cache. Replay identity hashes the combined content and both version/revision records, so a building-only edit also invalidates saved age state.

The split preserves city quantities, staffing and dimensions. Civilization profile metadata now references `common`, so its definition hash changes; geography and placement rules do not. Regenerate worlds from the preceding registry revision before age advancement. Algorithm 9, recipe 3, civilization report 2 and asset identities stay unchanged. The subsequent city planner update adds measured coordinate placement and worker housing.

## Final-world placement (civilization revision 6)

The building link now requires schema 2 / revision 3 and includes the validated worker-house profile. The [city planner](city-planner.md) consumes the presets after simulation, adds worker housing in two passes and exports schematic asset IDs. Earlier revision sections above describe their historical changes; current runtime placement follows the planner contract. Preset aggregate `houses_required` remains null because only successful placements determine actual housing demand.

## Parent race blocks

Schema 5 replaces the flat authoring `entities` map with nested parent blocks. Add a new parent by defining its name and civilizations map; add each civilization ID to `civilization_order`. The runtime loader exposes a flattened `entities` view with a derived `parent_race_id`, and parent names as metadata. Never serialize this runtime view back over the nested source file. Duplicate civilization IDs, missing/duplicate order entries and redundant child parent identifiers are rejected. Exported civilization reports include parent metadata and each derived parent ID as additive report-2 fields. Capitals and city presets remain per civilization. Registry identity changes, requiring regeneration before age advancement; no asset IDs or terrain rules change.

## Founding rounds (revision 8)

Each parent block owns `founding_participation_percent` (0-100). Initial values: human 80, dwarf 60, elf 45. Eligible parents each choose one highest-suitability site in round 1, subject to habitat capacity, water/slope exclusions, ruins and global spacing. This is their founding capital and remains capital while it survives. Other civilizations still receive their own capital when first introduced. Parents with no viable capacity remain absent.

Later rounds draw deterministic participation, prefer unused civilizations within remaining capacity, and search outward from existing parent cities. The radius starts at the larger of twice city spacing or one thirty-second of maximum globe distance, then grows 1.6 times per round to globe-wide. If an unused civilization has viable distant habitat, the parent waits for sufficient reach before repeating a used civilization. Parent initiative rotates each round.

Sufficient population means the existing habitat/food-derived per-civilization city quotas, under the 24-city lab ceiling. Rounds end at that target, when no permitted expansion remains, or at the explicit 128-round safety limit. Percentages control participation, not a guarantee of settlement. Reports include each attempt, radius, founding turn and termination reason. Age rebuilding retains survivors and runs the same expansion policy for remaining capacity. Generator algorithm 10 and settlements report 11 replace 9/10; old worlds must be regenerated. Recipe remains 3. No new potential asset identity is introduced.

## Migration and cultural divergence (revision 9)

Parent participation is now human 95%, dwarf 60%, elf 25%. The existing `elf` stable ID is displayed as **High Elf**; the parent ID remains `elf`. New independent `hill_dwarf` belongs to dwarf, has all three city presets and shared guild/housing support. Hill Dwarves are pastoral, hobbit-like smallfolk preferring grassland plains and gentle slopes (at most 18 degrees), with a farming bonus and reduced mineral emphasis. Existing shared production assets are candidates; distinct burrow art is not supplied.

`founding_rules` stores `years_per_round: 250` and `origin_min_separation_degrees: 90`. Parent founding sites must be at least 90 degrees of great-circle separation from the other parent origins. Three parents cannot all be antipodal; this rule places origins outside each other's centered hemispheres. The first parent chooses its best suitable site, then others choose their best qualifying distant site. This deterministic greedy rule does not prove a globally optimal three-origin arrangement. If a parent has no qualifying location, it remains absent with `no_separated_origin`; spacing is never silently relaxed.

Each expansion records its nearest existing same-parent source city, source civilization, migration distance, founding year and whether the culture changes. Target habitat and unused-civilization preference select authored cultural branches. This models settlement branching over centuries, not dynamic invention of languages, customs or biology. A 250-year round is a game calibration, not an anthropological measurement. Distance is great-circle reach; the lineage link does not claim a verified navigable migration route.

Founding report 2 exports start/end year and chronological events. Age rebuilding advances the clock beyond the preceding founding report even if no cities survived. Existing cities retain their founding dates and ancestry. Algorithm 11 / settlement report 12 requires regenerating algorithm-10 saves. Recipe 3 remains current. The potential asset IDs remain the same, with Hill Dwarf eligibility added to existing shared assets.

## Diaspora rounds (revision 10)

Every 1,000 simulated years, after the normal founding attempts, a separate seeded lottery selects one eligible civilization that has never founded a city in this world's recorded founding history. It selects that civilization's highest-scoring available site regardless of ordinary parent participation or migration radius. Reasons are exile, religious schism, expedition or magical displacement; the last is excluded when magic is disabled. Reasons are narrative provenance, not extra terrain/magic effects. The source remains the nearest same-parent city, preserving ancestry.

Cell habitat/safety eligibility, ruins, city spacing and origin separation remain mandatory. At least 40 residents of the civilization's existing productive allowance are required. No food or population allowance is created. If its ordinary city quota is zero, diaspora can add one slot, at most once per parent, within the unchanged 24-city lab ceiling and any smaller explicit city limit. Only the city-count/footprint quota is waived; site eligibility and food support remain binding. Effective quotas are exported into the population budget. Unused normal-quota slots need no parent bonus.

The founding simulation waits for the next diaspora interval when an eligible unused civilization remains, even if ordinary founding has finished. It stops when neither normal expansion nor a diaspora candidate remains, or reaches the existing 128-round limit. Used civilizations and consumed parent bonuses persist through subsequent ages, including destruction of their cities. Interval and bonus enablement are authored in `founding_rules.diaspora_interval_years` and `diaspora_bonus_per_parent` (0 or 1); the interval must align with the round duration.

Algorithm 12 / settlement report 13 / founding report 3 and registry revision 10 require regeneration of earlier saves. Diaspora flags, reason, bonus use and effective quotas are exported; the lab log displays each event. No new asset identity is introduced.


## Arctic settlements and Frostholds (revision 11)

Algorithm 13, settlement report 14, population budget 4, founding report 4, population profile schema 4 and registry schema 6/revision 11 introduce independent food temperature and founding minima. Earlier worlds require regeneration; recipe 3 and city planner 2 remain current.

Every population record now requires `food_temperature_ideal` and positive integer `minimum_founding_residents`. Settlement scoring still uses `temperature_ideal`; farm potential and surface/sky seasonal harvests use the separate food ideal. Existing entities retain their previous food ideal, preserving crop curves when comfort is edited. Cold Peoples use 0.9 weighted habitat km2 per city and a 30-resident minimum; Frosthold Dwarves use 0.55 km2 and 30; all other entities retain 40. The minimum applies both to regular quotas and diaspora. Founding clamps supplied quotas against food allowances, and reports the per-entity minima. It never grants extra food or population.

Each entity economy requires `winter_fishing_fraction` in 0..1. Fishing access is `1 - ice + ice * winter_fishing_fraction`, applied to the maximum ice along the fishing route. Cold Peoples retain 25% access at complete ice, Frostholds 15%; other entities retain zero. Both specialists have 1.25x fishing reach. These are provisional game calibrations, not extra fish: exclusive ocean-cell ownership, nominal fish productivity and delivery losses remain binding. The pre-founding marine allowance remains a prospective upper bound; actual harvest and winter/trade shortages are assessed afterward. Sea-trade routes still close under full ice. Hunting, herding, fuel consumption and geothermal production are not simulated by this revision.

`frosthold_dwarf` is a complete independent entity nested under dwarf. It prefers absolute latitude >=50 degrees (both hemispheres), temperature <=5 C, resource >=0.45, and exposed rock, positive upland relief, elevated slopes or coastal cliffs. Its comfort ideal is -8 C while crop ideal remains 9 C. Freshwater and safe reachable supply land remain required; permanent land ice remains excluded. `abs_latitude` is now available to surface settlement habitat rules. Frostholds share finite productive capacity with other peoples rather than creating another copy of it. Existing roads, sea routes and trade stress tests provide supply; presence and adequate food delivery are not guaranteed.

The three Frosthold city blocks use compact independent building counts, shared measured assets, winter fuel stores, supply warehouses, preservation facilities and a guild hall. Housing and apartments use the normal planner. Sheltered construction is a building brief, not a heat/insulation simulation. Capital status remains unchanged. The exhaustive compiler automatically includes Frosthold eligibility through its bindings; no new asset identity is introduced.

## Hamlet presets and rural catalogue (revision 12)

Registry revision 12 and building registry revision 4 add `structure_blocks.rural`, `housing_profiles.hamlet_house`, and a required per-entity `hamlet` preset. The [hamlet planner](hamlet-planner.md) exports independent `hamlet_plans` version 1 after final-stage city packing. City planner version and `city_plans` contract are unchanged; regenerate revision-11 worlds before age advancement.

## Opt-in hero guild planning

`fantasy_world_generator.hero_guild` supplies a version-1 standalone planning API. Its separate packaged policy registry has explicit civilization entries and zero automatic resident hero rates by default. The [canonical formulas](hero-guild.md) define integer rounding, capacity, visitor lodging and incremental staff/bed accounting. Existing master/building JSON is unchanged, including historical notes that refer to deferred hero calculations; automatic integration into generated cities remains deferred. This avoids changing their replay identity for an opt-in calculator. No new assets, permanent visitors, NPCs or population are created.
