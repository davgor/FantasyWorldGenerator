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

> **`villain:prior_age` is not a super villain.** The word `villain` names two unrelated things
> across package boundaries, and this is the one that is only a metaphor. A **super villain** is a
> *field* — a continuous tier, a reach in metres, a seat, held ley nodes — at most one per cultural
> region, owned by `icarus_sim.terrain_villains` and published in the `villains` block under
> [its own schema](../Contracts/schemas/villains.schema.json); see
> [super villains](super-villains.md). `villain:prior_age` is a **feature token on an ordinary
> person**: a pretender whose civilization founded a city again after they were born, so their
> claim was overtaken while they lived. It carries no tier, no reach, no region and no seat, and a
> world can be full of people holding it with an empty `villains` block.
>
> Two joins a consumer will reach for and both are wrong. Filtering `selectable` for
> `villain:prior_age` to find "people connected to a super villain" returns dispossessed
> claimants, silently and with no error. Reading it as evidence that a super villain stood here in
> a prior age is worse, because that question has a real answer elsewhere — `villains.fallen` —
> and this token sits exactly where someone would go looking for it.
>
> The one field name the two share is `tier`, and it means two things: `notable`/`renowned`/
> `legendary` here, a continuous number convertible to metres there.
> `Sim/tests/test_villain_vocabulary.py` holds this paragraph and its two counterparts in place.

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

### The quest contract: anchor, verb, difficulty

<!-- conformance:version heroes=2 -->
A hook is the closest thing this generator emits to a quest, and at `heroes` version 2 it
carries the whole contract. **The generator emits an anchor, a verb and a difficulty; the
consuming game prices the reward.** There is no `reward`, `loot` or `xp` field, and the
schema's hook object is the place to check that rather than this sentence.

- **`verb`** — what the player does, from the ten-word vocabulary `npc_roster` tags its
  posts with (`npcs.verbs`): `reclaim`, `recover`, `defend`, `slay`, `trade`, `tend`,
  `convert`, `supply`, `cleanse`, `investigate`. A hero-given hook and a post-given offer
  are therefore the same kind of thing to a consumer. A ley effect carries no action of its
  own, so its verb is the sign of its `intensity_delta`: deepening a node is `tend`,
  thinning one is `cleanse`. The vocabulary lives in `hero_generator.hooks.VERBS`;
  `hero_generator` may not import a sibling package, so the list is declared in both places
  and `test_hero_generator.py::QuestContractTests` is what keeps the two copies one list.
- **`difficulty`** — an integer 1–5 on the creature-tier rubric `beast_nests` already
  publishes: 1 harmless, 2 can hurt you, 3 kills the careless, 4 kills the prepared, 5 a
  campaign threat. Derived, never invented:

      difficulty = clamp(1, 5, floor(opposition + pressure + 0.5))

  **Opposition** is what stands at the target and is the only term that can reach 5 on its
  own — a lair answers with its own `tier`, a ley node with its own `intensity`
  (`ley_floor + ley_intensity_weight × intensity`), and every other kind takes a floor from
  `wells.json` `quests.opposition`: 2 for ground somebody holds (ruin, relic, city, hamlet,
  fortress, port) and 1 for an errand (shrine, college). **Pressure** is the danger the
  world already records around it — `pressure_per_tier` per tier of the worst nest whose
  own declared `range_m` reaches the target's ground, capped at `pressure_cap`. It is
  measured in grid metres (`spacing_m` per node), the same measure the countryside well
  uses to decide whether a hamlet is threatened, and it is never applied to a nest target,
  whose tier is already the whole answer. Banding is `floor(x + 0.5)` rather than `round`,
  because CPython rounds halves to even.
- **`target_node`** — the terrain node a player stands on, or `null` with an
  `unsited_reason` saying why there is none. A **ley key point**, whose id is a ruin's id
  plus `-key`, stands at that ruin and is sited there; a **bare ley node** is a direction
  and an intensity inside `magic.networks.<school>.nodes[]` with no footprint anywhere in
  the world, and is reported `ley_node_has_no_site` rather than given an invented position.
  The other two reasons, `target_not_found` and `target_has_no_node`, say the world moved
  out from under the hook, which is a world change rather than a defect.
  `hero_generator.hooks.UNSITED_REASONS` is the one home of that list.

`target` is the id of whatever the effect names and is no longer null on a slay hook: a
nest effect carries `nest_id`, and reading only `uid` or `node_id` left every one of them
pointing at nothing.

Measured on seed 42 size 17, generator 16: 46 hooks, difficulty 1×3 / 2×29 / 3×13 / 4×1,
42 sited and 4 `ley_node_has_no_site`. Nothing reaches 5 on that world because nothing on
it targets a lair; the equation reaches 5 only through a tier-5 nest. These are current
counts for one seed at one size, not invariants. Calibration across seeds belongs to the
quest package when it is built, which is where a difficulty *breakdown* belongs too: a
hook publishes one integer and no arithmetic to audit it by.

**Difficulty is not emitted into the `quests` block.** That block is the time capability's
lifecycle over these hooks and carries the contract's anchor and verb only; see
[time-advance](conformance/time-advance.md). A consumer wanting a priced offer joins
`quests.quests[].quest_id` to `heroes.quest_hooks[].hook_id`.

Adding these four fields changes the `heroes` bytes of every world, so **saved worlds must
be regenerated** — routine under
[023 worlds are disposable](decisions/023-world-compatibility-policy.md), and the
regeneration statement this record owes.

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
heroes: {version 2, status ok|failed, error?, policy_revision {archetypes, axis_overlays, alignment, names, wells},
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
  quest_hooks[] {hook_id, giver_uid, offered_from_face, stated_purpose, actual_effect {kind, uid|node_id|nest_id, action|school+intensity_delta}, unwitting,
                 target, verb, difficulty (1-5), target_node, unsited_reason},
  orgs[] {uid, kind: order|dynasty|council|remnant, name, home, members[], charter},
  diagnostics[] {role, placed, candidates, sources, source_kind, reason}, method, limits}
```

## Diagnostics: why a role is empty

Every role declared in `policies/wells.json`'s `precipitation` table gets a row in
`diagnostics`, sorted by role, whether it placed anybody or not — the shape `key_locations`
publishes for its archetypes, and what `PRODUCT-REACHABILITY-REPORT` asks every catalogue for.
The table is the **policy's** list, not the output's, so a role that stops firing cannot fall out
of the report by falling out of the block.

**The two zeros are different facts and the row separates them.** `candidates: 0` means no
candidate was ever built — the world holds none of the records that well reads — and `reason`
names what was missing. `candidates` above zero with `placed: 0` means every candidate was built,
rolled and lost, and `reason` gives the best chance that was offered. Before this, both read as a
silent `0` in `summary` and a consumer could not tell either from "the role is not implemented".

`sources` is the population the well iterated before any roll, and `source_kind` says in words
what was counted, so the number is readable without opening the well. It exceeds `candidates`
wherever the well walked records that did not qualify — 35 living cities read for 2 champions,
because only two stand within a dangerous nest's reach.

On seed 42 at size 33 the Dread row reads **`no ruins a beast destroyed in this world, so nothing
rolled`**: all 39 ruins there fell to war, water or air, so the antagonist role never built a
candidate and never appeared in `rolls` at all. `magister`, `college_magister` and `cult` are
empty for the same kind of reason and say so; `diaspora` is the other zero — one candidate rolled
at a chance of 0.7 and lost.

One row is not a person. **`camp` precipitates a place**: its `placed` counts rows in `camps`,
not in `people`.

## Determinism, isolation and the switch

Every draw is `child_seed(world seed, 'hero-<purpose>-' + uid)`; the helper comes from
`world_geometry`, a package of pure arithmetic shared by every reader, and
`Sim/tests/test_world_geometry.py` pins it to the generator's. The same world under the same policy
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
| a hamlet (`humans.hamlets`, not a harbour) | a **Reeve** | `hero-reeve-hamlet-node-<n>` | `role:reeve`, `hamlet:farming` or `hamlet:resource`, `hamlet:starving` when its core runs a food deficit, `hamlet:threatened` when a dangerous nest is within `reach_factor` of its range on the grid | `protect` the hamlet |
| a fortress (`humans.fortresses`) | a **Castellan** | `hero-castellan-fortress-node-<n>` | `role:castellan`, `order:member`, `warden:post`, `fortress:pressed` when the core city carries war pressure | `hold` the fortress |
| a port (`fisheries.ports`) | a **Harbourmaster** | `hero-harbourmaster-<port id>` | `role:harbourmaster`, `seat:trade`, `port:terminal`, `routes:2` when sea routes touch it | `exploit` the harbour |
| a shrine (`religion.sites`, kind `shrine`) | a **Keeper** | `hero-keeper-<site id>` | `role:keeper`, `shrine:ruin` | `hold` the shrine |
| a cult (`religion.sites`, kind `cult`) | a **Heresiarch** | `hero-heresiarch-<site id>` | `role:heresiarch`, `shrine:cult`, `school:dark` when born under a surge | `convert` the nearest living city |

**A reeve and a castellan are keyed on their terrain node, not on the site's id.**
`humans.hamlets[].id` and `humans.fortresses[].id` are ordinals — the position in a list
`terrain_humans` re-sorts by defence score at every age boundary — so a person built on one is
renamed by an advance that did not touch their ground, and the old uid goes on resolving to a
real person at a real fortress that is not the one the consumer meant. The node does not
renumber, and the key spells the anchor out (`fortress-node-13`, never `fortress-13`) so it
cannot be confused with the ordinal space. All four places the anchor is spent carry the same
key — `uid`, `presence.uid`, `claim.target_uid` and `deeds[].event_id` — because repairing one
leaves three ways to join the wrong row. This is the spelling `npc_roster` already writes for
the same sites, so a cast presence at a hamlet or a fortress *is* a roster site uid.

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
and nothing acts on them. `difficulty` is a danger band derived from creature tier, ley
intensity and what a place is — not a simulation of an encounter, not a creature count, not
a party-relative budget, and not a promise the quest is completable. No hook names a reward
at any version: the consuming game is what turns the number into treasure. Small worlds place no colleges, so college heads appear
only at larger sizes — and `diagnostics` now says which of those a given world is, rather than
leaving a `0` for a consumer to guess at. What `diagnostics` does **not** establish is whether a
zero is *correct*: it reports that no ruin named a beast, not whether a world of that size and
age ought to have produced one. A role gated on something that never fires would report
faithfully and look exactly like a world that simply lacks the ground. Names are syllable draws
with deed epithets, not linguistically modelled. The native core does not port this
package; it runs on the core's JSON output like any other consumer.
