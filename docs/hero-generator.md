# Hero generator: the cast v1

A finished world carries a `heroes` block: the larger-than-life people its history
precipitated. The generator is a wholly separate package, `Sim/hero_generator/`, called
once when world generation finishes (and again after every age advance) with the world and
its story so far as plain JSON. It reads `history.ages`, `ruins`, `settlements`,
`beast_nests`, `civilizations` and `humans.cultures`; it writes only `heroes`. It never
imports `icarus_sim`: a saved `world.json` serves it as well as a live result, and a
future native core's output will too.

Reference: `Sim/hero_generator/` (package), `policies/*.json` (authored data), the
[schema](../Contracts/schemas/hero-generator.schema.json), `Sim/tests/test_hero_generator.py`.

## Thesis

A character is a named handle on an event the world already recorded. Nothing is rolled
from a template: the heir points at the ruin, the warlord at the war, the Dread at the
nest the ruin's own evidence names. This keeps every deed traceable through the history
log the lab already shows, and it is what lets an optional prose layer describe a person
without inventing history.

Nothing is planned for anyone. A person exports an **event log** (one entry per recorded
event, in age order, each pointing at its event id) and a one-sentence **situation**; an
orchestrator improvises arcs, betrayals and quests from those on the fly. There are no
pre-written arcs, reveal conditions, levers or secrets in the block.

    Character = Deed + Stake + Claim, shaped by an Archetype, coloured by an Alignment.

- **Deed**: an event reference (`ruin-…`, `war-…`) with the person's role in it: `heir`, `credited`, `victim`, `actual`.
- **Stake**: what they are attached to now: a living city (`home`), or nothing (a legend).
- **Claim**: what they want next (`retake` the ruin, `hold` the city).
- **Archetype**: the shape of how they carry the claim; alignment-neutral.
- **Alignment**: two axes in −1..1 (law, good) with a nine-cell label; decides how the shape is lived.

## Wells: ruins

The ruins well reads `ruins[]` in export order and builds one **candidate** per record.
Not every candidate precipitates: each rolls once, `child_seed(seed, 'hero-roll-' + uid)`,
against `policies/wells.json` (`chance = min(cap, base + bonus)`, the bonus reading the
fallen city's class, the war kind and count, or the nest tier), and every roll is exported
in `rolls[]` with its chance, draw and outcome, so the block records what history could
have produced and did not. `summary.candidates` and `summary.precipitated` count them.

| Record | Precipitates | uid | Status |
|---|---|---|---|
| a ruin (chance 0.4 + class bonus) | a **Pretender** (heir) with claim `retake` | `hero-pretender-<city uid>` | living if a city of the same civilization survives and the ruin is at most one age old, else legend |
| a war ruin (chance 0.25 + war kind, +0.15 per extra war) | the victor city's **Warlord** with claim `hold`, deeds appended per war; with `one_per_city` (on since 2026-09-19) only the most recent victor per city precipitates | `hero-warlord-<age>-<victor uid>` | living if the victor city stands, else legend |
| a dragon/monster ruin (chance 0.5 + 0.08 per nest tier) | a **Dread** keyed to `evidence.nest_id`, deeds appended per kill | `dread-<nest id>` | living if the nest is still placed, else legend |

## Wells: magic

| Record | Precipitates | uid | Status |
|---|---|---|---|
| a ruin's key point `<ruin id>-key` in `magic.networks` (chance 0.2 + 0.12 × intensity) | a **Domain-holder** warding it, claim `hold` the node, deed role `keeper` | `hero-domain-<city uid>` | living for one age, presence `ruin`/`warding` |
| a `self_magic` ruin (chance 0.75) | the surviving **Magister** of its college, claim `exploit` the key point, deed role `actual` | `hero-magister-<city uid>` | dispossessed: placed by the rules below |
| a living college in `magic.colleges` (chance 0.6) | its head **Magister**, claim `hold` the college, no deeds | `hero-magister-<college id>` | living, presence `college` |

`school` is the key point's school (from the ruin legacy) or the dominant ley layer under
the college. `school:dark` (umbral, infernal, weave in `wells.json`) is what makes a
Deceiver possible; nothing forces it.

## Wells: cities

| Record | Precipitates | uid | Notes |
|---|---|---|---|
| a realm's capital (chance 0.9) | its **Sovereign**, claim `hold` the realm, deeds = the capital's wars; the realm's `sovereign_uid` | `hero-sovereign-<city uid>` | a founding capital's sovereign heads a **dynasty** org |
| every living city, one seat per `wells.json` `seats[city_class]` (chance 0.3, +0.15 in a capital) | a **Council** member (`seat`), claim `hold` the city (`exploit` for the market steward) | `hero-council-<city uid>-<seat>` | precipitated seats form a **council** org; `seat:trade`, `routes:2` from shipments, `role:schemer`/`stakes:2` when the city has a living former opponent |
| a city founded by a diaspora (chance 0.7) | its **Prophet** (or **Heresiarch** while the mother civilization's cities stand), **Exile**, or **Founder** | `hero-<role>-<city uid>` | deed kind `founding`; a heresiarch claims `convert` on the mother capital |

## Wells: guilds

| Record | Precipitates | uid | Notes |
|---|---|---|---|
| a living city within `reach_factor` × range of a dangerous nest (dark family or dragon; chance 0.35 + 0.1 × tier) | its **Champion**, deed kind `nest`, claim `kill`; an **order** org chartered against the nest's family | `hero-champion-<city uid>` | `deed:credited_not_actual` and a `betrayed` bond when a warlord actually won that city's war |
| a city a beast destroyed | the Champion who failed (`defence:failed`, `dread:failed_against`), dispossessed and placed like a master; a **remnant** org | `hero-champion-<city uid>` | the Knight Errant, Fallen Hero and Obsessed Hunter come from here |

## Cross-cutting features

Once the cast is known, `features.py` adds relations no single well can see: `ley:tainted_home`
(umbral or infernal potency under the home above `features.tainted_threshold`),
`deeds:two_civilizations`, `villain:prior_age` + `stake:regained` (an heir whose people founded
again after the loss), `rival:spared` (a seated person whose people have a living camp
leader), `council:outranks_sovereign` / `sovereign:advised` (by fame), `mentor:successor`
(renowned, with a later-born living compatriot; a `mentor` bond), `seat:none`, `heir:unclaimed`.
Seated people (sovereigns, warlords) are finished first; the civilizations they rule as
Tyrants mark everyone unseated there `realm:tyrant`, so Rebels can only exist under a Tyrant.
Councillors also gain `ally` bonds to their sovereign.

## Camps, relics and placement

Every ruin rolls for a **Camp** (`camp-<city uid>`, chance 0.3 + class bonus): squatters
in the ruin, with the ruin's node and coordinates, exported in `camps[]`. Every ruin
leaves a **relic** resting in it (`relics[]`: a focus of its legacy school for magical
ends, a crown for a capital, a banner for a war, a reliquary for a beast kill).

Placement gives the dispossessed somewhere to stand, seeded like everything else: an heir
whose people have no city left leads the camp in their own ruin if one precipitated
(`role:camp_leader`, so a Trickster or Rebel can follow) instead of passing into legend; a
surviving college master is `captive` or `hidden` at the camp in their ruin if there is
one, else a `refugee` in the nearest surviving city, else a legend. A living person whose
situation is captive, hidden or refugee is `companion.eligible` with `join_condition`
rescued, found or hired. The captive necromancer of the original brief is one thing this
can produce; it is not scripted, and most worlds will produce something else.

## Faces and quest hooks

A card may declare faces: `public`/`true` (Deceiver, False Hero), `calm`/`unleashed`
(Beast), `first`/`second` (Fractured Heart). Each face carries its own alignment, apparent
role, claim and persona; the public face of a Deceiver mirrors the good axis positive and
wears a cover role from `names.json`, so it speaks with a Good overlay while the true
face underneath does not. `persona` at the top level is always the true one.

Living people's claims compile into `quest_hooks[]`, typed against things the world has:
`retake` → reclaim the ruin and recover its relic; a warlord's `hold` → defend the city; a
key point `hold`/`exploit` → strengthen the person's own node and weaken the nearest node
of the opposite school (`wells.json` `magic.opposites`, ±`hook_intensity_delta`), read from
the exported ley networks; a college head → supply the college. For a one-faced person the
stated purpose says what the effect does. For a two-faced person the stated purpose comes
from the public face and `unwitting` is true: "cleanse the shrine; something there is
poisoning the valley" for an effect that weakens a radiant node. Which nodes are named is
read from the world, never authored.

**Realms** are the road-linked culture groups (`humans.cultures`) named for their capital
(`realm-<culture id>`, "Realm of Alder"). `sovereign_uid` stays null until the cities well.

**Bonds** are edges from shared deeds: the heir and the warlord who took the city, the heir
and the beast. **Mantles** are `retake` claims whose holder is a legend, left open for a
successor. A living heir whose people already have such a legend gains the
`legend:predecessor` feature and a `predecessor_uid`.

Every archetype in the catalogue can now fire from some well; the reserved features that
remain unset are listed in `hero_generator.archetypes.FEATURES`.

## Fame

`fame = magnitude × (1 + reach)`, from exported numbers only. Magnitude: class of the
fallen city (small 1, medium 2, capital 3) for an heir; war weight (civil 1, regional 2,
international 3) times the defeated class for a credited victor; half the war weight for a
defeat suffered; `0.6 × nest tier × class` per city a Dread destroyed. Reach: the home
city's class plus a quarter per realm city, or `0.5` for a legend; a Dread reaches its
`range_m` in kilometres, capped at 3. Tiers: notable below 8, renowned from 8, legendary
from 24. Raising the fallen city's class or the nest tier must raise fame; a test holds it.

## Alignment, then archetype

Alignment is derived **before** the archetype so a card is chosen for a person who already
has a moral colour:

1. Centre from `policies/alignment.json` `civilization_bias` (authored flavour).
2. Deed shifts (`war_civil_victor` +0.25 law / −0.3 good, …). The sign a deed decides is never flipped by jitter.
3. Seeded jitter, `child_seed(seed, 'hero-alignment-' + uid)`, ±0.35.
4. Label: thresholds at ±0.34 on each axis; both neutral reads "True Neutral". `code` is `[LNC][GNE]`.

An archetype is then chosen from `policies/archetypes.json`: a card is eligible when any
one of its `requires` conjunctions is a subset of the person's features (`role:warlord`,
`war:civil_victor`, `home:fell`, `fame:renowned`, …; the full vocabulary is
`hero_generator.archetypes.FEATURES`). Eligible cards are weighted by `boosts` and by a
soft `prior` (a Conqueror is more often lawful, never only lawful), and the seed picks.
`intensity` then pushes the alignment to a corner (Incarnate) or a moral pole (Broken Soul,
Malevolent/Benevolent). Every archetype exists in all nine cells.

## Persona

The catalogue carries an alignment-neutral **core** per card (`belief`, `wants`, `fears`,
`tells`, `mechanic`, `never`) and four **pole notes**. The exported persona is

    core + axis overlay(law pole) + axis overlay(good pole) + pole notes

with the shared overlays in `policies/axis_overlays.json`: the law pole sets voice,
word-keeping and what happens when cornered; the good pole sets whose cost counts and how
the person treats a stranger. `never` is the union of every hard line, so a proposal that
crosses one can be rejected mechanically. `line` is the sample utterance nearest the
person's alignment code. The same Tyrant card therefore reads as a Chaotic Good strongman
or a Lawful Evil autocrat.

## Export

```
heroes: {version 1, status ok|failed, error?, policy_revision {archetypes, axis_overlays, alignment, names, wells},
  final_age, summary {living, legends, dreads, realms, orgs, camps, hooks, candidates, precipitated},
  people[] {uid, role: pretender|warlord|magister|domain_holder|sovereign|council|champion|prophet|heresiarch|exile|founder,
            well: ruins|magic|cities|guilds, status, name, epithet, display_name, race_id, civilization_id, realm_uid,
            born_age, school, node_id, seat, nest_id,
            home, presence {site_kind, uid, situation}, fame, tier, alignment {law, good, label, code, drift},
            archetype, archetype_name, persona {...}, faces[] {label, name, apparent_role, alignment, claim, persona},
            deeds[], log[] {age, event_kind, event_id, role, text}, situation, claim,
            companion {eligible, join_condition, offered_from_face}, rivals[], kin[], allies[],
            org_uid, predecessor_uid, selectable[] (the features that were true), seed},
  dreads[] {uid, nest_id, species, family, nest_tier, status, presence, deeds[], destroyed[], fame, tier, name,
            display_name, archetype?, alignment, persona?, log[], situation, selectable[], seed},
  realms[] {uid, name, civilization_id, civilization_name, capital_uid, city_uids[], culture_id, sovereign_uid},
  bonds[] {a, b, kind, from_event}, mantles[] {claim, predecessor_uid, civilization_id, vacant_since_age},
  rolls[] {candidate_uid, kind: heir|warlord|dread|domain_holder|magister|college_magister|camp, event_id, age, chance, roll, precipitated},
  camps[] {uid, ruin_uid, name, node, x, z, direction, origin, civilization_id, since_age, leader_uid?},
  relics[] {uid, kind, name, origin_event, resting_at, holder_uid, school},
  quest_hooks[] {hook_id, giver_uid, offered_from_face, stated_purpose, actual_effect {kind, uid|node_id, action|school+intensity_delta}, unwitting, target},
  orgs[] {uid, kind: order|dynasty|council|remnant, name, home, members[], charter}, method, limits}
```

## Determinism, isolation and the switch

Every draw is `child_seed(world seed, 'hero-<purpose>-' + uid)`; the helper is a byte-for-byte
copy of the generator's and a test pins them together. The same world under the same policy
revisions yields the same block; a policy edit changes `heroes` and nothing else, because
the core never reads the block back.

`terrain_history._attach_heroes` is the only call site (stage 16, and after the last age of
an age-API step, before the snapshot is captured). It pops any previous block and calls
`hero_generator.attach`, which never raises: a failing revision yields
`{version, status: 'failed', error}`, visible in the lab, and the world still returns.
`FANTASY_WORLD_HEROES=0` in the environment leaves the key absent; this is an environment
switch rather than a recipe parameter so that the world's own recipe, replay identity and
native parity are untouched. `heroes` is in `STATE_KEYS` and the lab's `historyStateKeys`,
so the stage scrubber hides it before stage 16 like `ruins`.

## Lab

The terrain lab renders the block under **The cast**: living cast, legends and dreads as
cards with civilization, race, role, archetype, alignment, fame tier, position and situation;
"Event log and bonds", "Persona" and (behind a checkbox) "Truth" details plus the roll ledger; realm and mantle
summary lines. Living people appear as diamond pins on the atlas, coloured by the good
axis, and the hover readout names them. A failed block shows its error in red.

## Countryside, ports and shrines (wells added 2026-09-19)

Heroes were city-bound: every well read ruins, wars, nests, colleges, city seats, guild
halls or diaspora cities. Four wells now read the small sites, so the people who actually
starve, hold a wall, run a quay or tend an altar precipitate too. Each is a named handle on
a site the world already placed; each rolls once against `policies/wells.json`.

| Site (export field) | Precipitates | uid | Facts it sets | Claim |
|---|---|---|---|---|
| a hamlet (`humans.hamlets`, not a harbour) | a **Reeve** | `hero-reeve-<hamlet id>` | `role:reeve`, `hamlet:farming` or `hamlet:resource`, `hamlet:starving` when its core runs a food deficit, `hamlet:threatened` when a dangerous nest is within `reach_factor` of its range on the grid | `protect` the hamlet |
| a fortress (`humans.fortresses`) | a **Castellan** | `hero-castellan-<fortress id>` | `role:castellan`, `order:member`, `warden:post`, `fortress:pressed` when the core city carries war pressure | `hold` the fortress |
| a port (`fisheries.ports`) | a **Harbourmaster** | `hero-harbourmaster-<port id>` | `role:harbourmaster`, `seat:trade`, `port:terminal`, `routes:2` when sea routes touch it | `exploit` the harbour |
| a shrine (`religion.sites`, kind `shrine`) | a **Keeper** | `hero-keeper-<site id>` | `role:keeper`, `shrine:ruin` | `hold` the shrine |
| a cult (`religion.sites`, kind `cult`) | a **Heresiarch** | `hero-heresiarch-<site id>` | `role:heresiarch`, `shrine:cult`, `school:dark` when born under a surge | `convert` the nearest living city |

Hamlets and fortresses have no globe direction, so nest reach is measured on the node grid
in metres (`spacing_m` per node). Names come from the core city ("the farmstead below
Alder", "the fortress above Ivy", "the harbour of Glen", "the shrine of The Red Field at
Larch") and are carried as `site_name`. A keeper shelters at the nearest surviving city of
the ruin's people, or stands at the shrine with no home. Deeds use the new event kinds
`hamlet`, `fortress`, `port` and `shrine` with role `keeper`; hooks use effect kinds of the
same names. Archetype entry points: a reeve is a Reluctant Hero, or an Obsessed Hunter when
threatened; a castellan a Warden; a harbourmaster a Corrupt or Magnate; a keeper an
Oathbound or Zealot. Fame adds a small site weight (hamlet and shrine 0.5, fortress and port
1.0) on top of the home city's reach.

## Limitations

An artistic reading of exported history, not a demographic claim. Council seats are a
policy table by city class, not the placed rosters; claims and hooks are exported intent
and nothing acts on them. Small worlds place no colleges, so college heads appear
only at larger sizes. Names are syllable draws
with deed epithets, not linguistically modelled. The native core does not port this
package; it runs on the core's JSON output like any other consumer.
