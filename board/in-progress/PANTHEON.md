# PANTHEON — God catalogue and world-decided pantheons

Drafted: 2026-09-18. Status: in progress, folded into the lunar-cycle work ([ASTROLOGY](ASTROLOGY.md)); canonical contract in [docs/pantheon.md](../../docs/pantheon.md). Owner: lunar-cycle session.

Decisions taken since the draft: cosmology is chosen per world; folded civic gods stay listed as saints; a moon god (`god_turning_moon`, aspects Pale Warden / Turning Face from the almanac's leaning) and a Turning Moon cosmology join the catalogue; feasts derive from the lunar almanac (surge days, full moons, hollow nights); gods stay dormant in generation and act only through `POST /world/summon` (see the visitation API in docs/pantheon.md), which is highly disruptive and leaves a footprint on departure. Implemented: `Sim/icarus_sim/pantheon.json`, `terrain_religion.py`, `terrain_visitation.py`, `Sim/tests/test_religion.py`, `test_visitation.py`.

## Requested behavior

The user asked for a short list of the gods that *could* exist, derived from the types of magic and the peoples already in the generator, plus a wide set of pantheon options that can be mixed and matched, so that each generated world decides which gods actually exist.

## Proposed mechanism

Three layers, all authored as data and all resolved deterministically from the finished world:

1. **God catalogue** (authored, ships as data per decision 020). Every god is an independent record with domains, an *existence rule* evaluated against world state, per-parent-race epithets, and allies/rivals. Nothing inherits; a god is either manifest in a world or absent.
2. **Cosmology templates** (authored). A template says how the manifest gods are *arranged*: who is high, who is lesser, who is an outsider, who is dead. Each template has prerequisites, so the world state also decides which templates are eligible. One template is chosen per world from the eligible set by seeded weighted draw.
3. **Faiths** (generated). Each civilization that founded a city picks the gods it worships from the manifest set, weighted by its parent race, its habitat, the leyline potencies under its cities, nearby threats and the cosmology's high gods. It names them with its own epithets. Diaspora foundings with reason `religious_schism` become a sect: same gods, the primary and a rival swapped, and a new epithet.

The world therefore decides existence (layer 1), the world plus seed decides structure (layer 2), and the peoples decide worship (layer 3). Mix-and-match happens at every layer without authoring a single fixed pantheon.

### Existence inputs already exported by the generator

| Input | Where it comes from today |
|---|---|
| Which schools manifest and how strongly | `magic.networks[school].enabled`, node/line intensities, `biome_variant` coverage |
| Which parent races and civilizations founded cities | founding report `used_civilizations`, `settlements.sites`, `ruins` |
| Ocean share, maritime/island/Tidekin presence | `natural_biome` coverage, civilization IDs of live cities |
| Sky settlements | `sky` islands and sites (magic-enabled worlds only) |
| Dragon, undead, infernal and aberrant nests | `beast_nests` families, the same test `city_fate` uses |
| Ruins and their causes | `ruins[].cause` (`leyline`, `self_magic`, `war_*`, nest) |
| Wars | `war_history` |
| Diaspora and schisms | founding events with `diaspora_reason` |
| Magic disabled worlds | `config.magic_enabled == 0` |

### The god catalogue (24 gods)

**A. School gods** — one per leyline, two aspects each. The god manifests when its network is enabled and has at least one key point. The *aspect* the world shows is decided by that network's mean intensity and instability: below the midpoint the Sovereign aspect, above it the Wild aspect. Cosmologies may show both as twins.

| ID | School (group) | Sovereign aspect | Wild aspect | Core domains |
|---|---|---|---|---|
| `god_weave` | Weave (raw) | The Loom-Mother, patron of makers and mages | The Laughing Unmaker, chance and impossible things | creation, creativity, chance, magic itself |
| `god_umbral` | Umbral (raw) | The Quiet Judge, keeper of the ordered dead | The Hollow Hunger, entropy and the restless dead | death, endings, memory, order |
| `god_infernal` | Infernal (holy/unholy) | The Chained Tyrant, pacts, dominion and price | The Devourer Below, corruption without bargain | ambition, pacts, ruin, temptation |
| `god_radiant` | Radiant (holy/unholy) | The Dawn Healer, mercy and renewal | The Burning Verdict, righteousness without mercy | healing, light, law, judgement |
| `god_fire` | Fire (primordial) | The Hearth-Forger, warmth, craft and renewal | The Wildfire, purging destruction | fire, forge, renewal, passion |
| `god_water` | Water (primordial) | The Tide-Keeper, currents, rain and trade winds on water | The Winter Drowned, ice and the cold deep | sea, rain, ice, patience |
| `god_earth` | Earth (primordial) | The Green Grandmother, harvest and roots | The Titan Under the Hill, stone that reclaims | harvest, stone, growth, endurance |
| `god_air` | Air (primordial) | The Wayfarer of Winds, travel, messages and birds | The Storm-Crown, force and thunder | wind, storms, travel, freedom |

**B. Parent-race gods** — manifest when that parent race founded at least one city in the world's history (ruins count). These are the ancestor-founders and are the anchor of every faith of that race.

| ID | Race | Name | Domains | Epithets by civilization |
|---|---|---|---|---|
| `god_first_hearth` | Human | The First Hearth | founding, kinship, the walled town | Maritime: Harbour-Mother; Desert: Well-Father; Cold: Long-Night Keeper; Large island: Shore-Ancestor; Rainforest: Feathered Founder; Heartland: The Old King |
| `god_elder_star` | Elf | The Elder Star | living wood, long memory, starlight | High Elf: The Grove-Singer; Tidekin: The Foam-Born |
| `god_deep_forge` | Dwarf | The Deep Forge | stone, craft, oaths, hoard | Dwarf: The Anvil-Father; Gnome: The Tinkering Spark; Hill Dwarf: The Full Table; Frosthold: The Ember Under Ice |

**C. World-feature gods** — manifest from geography, threats and history rather than from any school. These are what make two worlds with the same schools feel different.

| ID | Name | Manifests when | Domains |
|---|---|---|---|
| `god_drowned_mother` | The Drowned Mother | ocean covers at least half the globe, or any Maritime, Large-island or Tidekin city exists | the sea, fishing, storms at sea, drowning |
| `god_sky_court` | The Sky Court | at least one sky settlement exists | floating islands, altitude, the far view |
| `god_great_wyrm` | The Great Wyrm | at least one dragon nest exists | dragons, hoards, fear, fire from above |
| `god_outer_unnamed` | The Unnamed Outside | at least one aberrant-family nest exists | madness, the wrong shape of things, forbidden knowledge |
| `god_fallen_cities` | The Keeper of Fallen Cities | at least one ruin exists | ruins, lost knowledge, warnings |
| `god_wanderer` | The Wanderer | at least one diaspora founding occurred | exile, roads between peoples, second chances |

Undead nests do not add a god; they raise `god_umbral` toward its Wild aspect. Infernal nests do the same for `god_infernal`.

**D. Civic gods** — always manifest, including in worlds with magic disabled, so no world is godless unless the Silent Heavens cosmology says so. They give faiths a spine that does not depend on leylines.

| ID | Name | Domains | Merges when |
|---|---|---|---|
| `god_hearth_harvest` | The Hearth and the Harvest | home, bread, children | folds into `god_earth` Sovereign if Earth manifests |
| `god_forge_craft` | The Maker | tools, walls, guilds | folds into `god_fire` Sovereign if Fire manifests |
| `god_road_market` | The Coin and the Road | trade, oaths between strangers, travel | folds into `god_air` Sovereign if Air manifests |
| `god_crown_law` | The Crowned Scale | kingship, law, treaties | folds into `god_radiant` Sovereign if Radiant manifests |
| `god_grave_memory` | The Grave Keeper | natural death, ancestors, remembrance | folds into `god_umbral` Sovereign if Umbral manifests |
| `god_fortune_fate` | The Turning Wheel | luck, weather, fate | folds into `god_weave` if Weave manifests |
| `god_red_field` | The Red Field | war, courage, the honoured dead | never merges; prominence scales with `war_history` |

"Folds into" means the civic god becomes a saint or aspect of the school god under cosmologies that allow it, and stays separate under Mosaic and Ancestor Halls. That keeps the total per world short: a magic-disabled world has 7 civic gods plus up to 3 ancestors and the feature gods; a full-magic world has 8 school gods with most civic gods absorbed.

### Cosmology templates (10)

| ID | Name | Prerequisites | Arrangement |
|---|---|---|---|
| `cos_elemental_court` | The Elemental Court | at least three primordial networks | Fire, Water, Earth, Air are high; Weave and Umbral are titans before the court; Radiant and Infernal are outsiders |
| `cos_dual_dawn` | Dawn and Pit | Radiant and Infernal both manifest | two high gods; every other god is a saint of one or a devil of the other |
| `cos_ancestor_halls` | The Ancestor Halls | at least two parent races founded cities | parent-race gods are high; school gods are impersonal powers with no temples |
| `cos_spirits_of_place` | Spirits of Place | Weave or Earth manifests | no high gods; every leyline key point is a named local spirit; civic gods are household spirits |
| `cos_one_sun` | The One Sun | Radiant manifests, or magic disabled | one over-god (Radiant Sovereign, else the Crowned Scale); all others become saints or angels |
| `cos_silent_heavens` | The Silent Heavens | at least two ruins, or Umbral manifests | the gods are dead or withdrawn; only the Keeper of Fallen Cities, the Wanderer and cults of the Wild aspects are active |
| `cos_sea_and_sky` | Mother Sea, Father Sky | Drowned Mother manifests, or a sky settlement exists | Drowned Mother and Air (or the Sky Court) are the high pair; others are their children |
| `cos_wyrm_thrones` | The Wyrm Thrones | at least one dragon nest | the Great Wyrm is high; each dragon nest is a demigod with a territory |
| `cos_the_woven` | The Woven | Weave manifests | magic itself is divine; the Loom-Mother is high and colleges are its churches |
| `cos_mosaic` | The Mosaic | always eligible | no world-level high gods; each civilization ranks its own faith |

Selection: filter to eligible templates, weight each by a fit score (for example Elemental Court weight = summed primordial coverage, Wyrm Thrones weight = dragon nest count), and draw once with `child_seed(seed, 'pantheon-v1')`. Mosaic keeps a small constant weight so it is the fallback, not the default.

### Faith selection per civilization (default affinities)

Each civilization takes its parent-race god as first patron, then draws up to three more from the manifest set with these weights added to the cosmology's high-god bonus and the mean leyline potency of each school across its cities. Values are provisional game calibration.

| Civilization | Strong affinity (+2) | Mild affinity (+1) | Aversion (−2) |
|---|---|---|---|
| Maritime humans | Drowned Mother, Water | Road and Market, Air | Titan Under the Hill |
| Desert humans | Fire, Water (as scarcity) | Crowned Scale, Wanderer | Drowned Mother |
| Cold peoples | Winter Drowned, Hearth and Harvest | Red Field, Umbral Sovereign | Wildfire |
| Large islanders | Drowned Mother, Air | Elder Star (borrowed), Fortune | Infernal |
| Rainforest humans | Earth, Great Wyrm (propitiation) | Fire, Umbral | Winter Drowned |
| Heartland humans | Crowned Scale, Hearth and Harvest | Radiant, Red Field | Outer Unnamed |
| High Elf | Elder Star, Weave, Earth Sovereign | Radiant | Infernal, Wildfire |
| Tidekin | Elder Star, Drowned Mother | Water, Air | Titan Under the Hill |
| Dwarves | Deep Forge, Earth, Fire Sovereign | Red Field | Air, Weave Wild |
| Gnomes | Deep Forge, Weave Sovereign, Maker | Air, Fortune | Umbral |
| Hill Dwarves | Hearth and Harvest, Earth Sovereign | Fortune, Road | Great Wyrm |
| Frosthold Dwarves | Deep Forge, Winter Drowned, Fire Sovereign | Red Field | Sky Court |

Threat modifier: a city within reach of a dragon, infernal, undead or aberrant nest (the same reach `threat_assessments` uses) adds a propitiation entry for the matching god, marked `fear` rather than `devotion`.

### Evolution across ages

Existence and faiths are re-evaluated on every `advance-age`, using the same inputs the age already recomputes. A school whose network intensities decay to zero makes its god `sleeping`; a magical self-destruction ruin leaves a Weave key point and a cult of the Loom-Mother at the ruin; a war ruin adds a Red Field shrine record; a schism diaspora records a sect. Sleeping gods are retained with their last aspect so the timeline can show a god dying.

### Export

New top-level `religion` section, version 1: `catalogue_revision`, `cosmology`, `gods` (manifest and sleeping, with aspect and evidence), `faiths` keyed by civilization ID (patron, worshipped gods, epithets, fear entries, sects), and `sites` (cult and shrine records tied to ruins and nests). Existing `religious_building`, `temple`, `great_temple` and `hamlet_shrine` structures gain a `dedication` string on placed instances in a later slice; this slice adds no coordinates and no asset IDs.

## Dependencies and unresolved decisions

- Whether a cosmology is chosen per world (proposed) or per parent race. Per race allows a dwarven Ancestor Hall beside a human One Sun in the same world, which is richer but harder to narrate; a schism sect already gives some of that variety.
- Naming: the catalogue supplies canonical names and per-civilization epithets in English. Generated names in each culture's language are out of scope until a name generator exists.
- Whether civic gods that "fold into" a school god should still be listed as saints in the export, or dropped. Proposed: listed, so consumers can always find `god_hearth_harvest` regardless of magic.
- Balance of the affinity table and the cosmology fit weights are provisional and need a sampled review across seeds.
- Magic-disabled worlds cannot draw `cos_the_woven`, `cos_elemental_court`, `cos_dual_dawn`, `cos_spirits_of_place` or `cos_sea_and_sky` via sky; the table already encodes this.

## Sources consulted

- `Sim/icarus_sim/terrain_leyline_history.py` — the eight schools, three groups, descriptors and dominance rule.
- `Sim/icarus_sim/terrain_biome_catalogue.py` — variant names per school, used to keep god flavour consistent with terrain.
- `Sim/icarus_sim/civilizations.json` and `docs/civilizations.md` — twelve civilizations, three parents, founding participation, diaspora rules.
- `docs/decisions/016-standalone-civilizations.md` — cultural inspirations behind the epithets.
- `Sim/icarus_sim/founding.py` — diaspora reasons including `religious_schism`.
- `Sim/icarus_sim/terrain_history.py` — threat families, ruin causes, leyline destruction text.
- `Sim/icarus_sim/terrain_society.py` — sky settlements.
- `Sim/icarus_sim/buildings.json` — existing faith structures per race.
- `PLAN.md` section on schools and civilization classification.

## Files and assets in scope

Proposed for the implementation slice, none touched yet:

- `Sim/icarus_sim/pantheon.json` — god catalogue and cosmology templates (schema 1, revision 1).
- `Sim/icarus_sim/terrain_religion.py` — existence, cosmology draw, faith selection, age re-evaluation.
- `Sim/tests/test_religion.py` — behavioral tests.
- `docs/pantheon.md` — canonical document; link from `docs/README.md`.
- `Contracts/schemas/world-output.schema.json` — additive `religion` section.
- No new asset IDs. Temple dedication is a later slice and would then require exhaustive asset-list coverage if dedications select art.

## Acceptance and evidence

- Same seed and registry produce byte-identical `religion` output.
- A magic-disabled world exports the seven civic gods, manifest parent-race gods, feature gods with satisfied rules, and a cosmology drawn only from the eligible set.
- Disabling one school network removes exactly that god (or marks it sleeping after an age) and changes no other god's existence.
- A world with a dragon nest lists the Great Wyrm; removing the nest removes it.
- Every civilization with a live city has a faith whose first patron is its parent-race god and whose remaining gods are all manifest.
- A diaspora founding with reason `religious_schism` produces exactly one sect record on that city.
- Age advancement with decayed Weave intensities marks `god_weave` sleeping and retains its last aspect.

## Documentation impact

New canonical `docs/pantheon.md`; additions to `docs/terrain-world-layers.md` (export section and age evolution) and `docs/civilizations.md` (faith affinity authoring). World output schema version bump for the additive section.

## Adversarial review and limitations

- Gods are narrative provenance only; this ticket grants no terrain, food, threat or influence effects. Any gameplay effect is a separate ticket with its own tests.
- Existence rules read final-stage world state; they must not be evaluated during genesis stages before nests and ruins exist, or the export becomes stage-dependent.
- Epithets and cosmology names are authored English flavour and will need localisation or culture-driven naming later.
- Twenty-four gods and ten cosmologies is a design ceiling for the first slice; adding more should go through the same catalogue format rather than code.

## Handoff

Next action: user review of the god list, cosmology set and the per-world versus per-race cosmology question. After sign-off, implement the JSON catalogue and `terrain_religion.py` behind a failing behavioral test, then the export schema and docs.
