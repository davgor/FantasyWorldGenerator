# Consumer vocabulary — the field names that collide, and which one you want

A consumer joining two blocks of a generated world joins on field names. Several names mean
different things in different blocks, all of them plausible, and **the wrong answer is never
an error** — you get a number, or a string, and a wrong world.

This page is the collision list and nothing else. It is deliberately **not** a field glossary:
a glossary drifts and becomes one more authority to disagree with the schemas, while a
collision list changes only when a collision is added or removed. For what a block contains,
read that block's schema in `../Contracts/schemas/`.

Measured against the tree on **2026-09-21** by walking every `*.schema.json` in
`Contracts/schemas/` for the exact property name, the same walk
`tests/test_status_vocabulary.py` uses. Exact-name matching only: `route_status` and
`plan_status` are different fields and a question about the name `status` may not annex them.

The conventions that stop this list growing are [030 Magnitude and identity
conventions](decisions/030-magnitude-and-identity-conventions.md). No shipped field is
renamed; see C1 part 3 for why.

---

## `tier` — four meanings, three of them numeric

| Block and path | Type | What it means | Safe to compare with |
|---|---|---|---|
| `beast_nests.sites[].tier`, `wildlife.sites[].tier` | `int` 1–5 | **creature danger.** Rejected outside the range by the species-profile check in `Sim/icarus_sim/terrain_nests.py` | each other, and `beast_movements` |
| `beast_movements.groups[].tier` | `int` 1–5 | creature danger, copied from the nest profile the group came from | the two above |
| `key_locations.sites[].tier`, `key_location_plans.plans[].tier` | `int` 0–3 | **physical build-out and scale.** Its own schema description shouts "PHYSICAL SCALE AND BUILD-OUT ONLY - never danger". Tier 2 is the tier that gains an interior chamber graph | each other |
| `heroes.people[].tier`, `heroes.dreads[].tier` | `string` enum `notable` · `renowned` · `legendary` | **fame band**, derived from `fame` | each other |
| `villains.people[].tier`, `villains.outlook.regions[].tier` | `float` ≥ 0 | **continuous standing.** `SUPER_TIER` is 1.0; `reach_m = tier × REACH_SPACINGS_PER_TIER (4) × settlement_spacing`, so its product is **metres** | each other |

**If you are joining on `tier`, you almost certainly want one of these instead:**

- danger of a creature → `beast_nests` / `wildlife` / `beast_movements` `tier`, and nothing else;
- how built-up a place is → `key_locations.sites[].tier`;
- how far a villain's grip reaches → `villains.people[].reach_m`, already in metres. Do not
  multiply `tier` yourself;
- how famous a person is → `heroes.people[].fame` for the number, `tier` for the band.

**The trap.** `beast_nests.tier` (1–5) and `key_locations.tier` (0–3) overlap on 1, 2 and 3.
A join across those two produces matches, and one side means danger while the other side's
own contract says it never does.

## `status` — 18 declaration sites, eight vocabularies, two depths

Every `status` enum published in `Contracts/schemas/`, by the vocabulary it belongs to:

| Vocabulary | Declared at |
|---|---|
| `ok` · `failed` | **block level**: `heroes`, `npcs`, `story_web`, `key_locations`, `key_location_plans` |
| `living` · `legend` | `heroes.people[]`, `heroes.dreads[]` |
| `alive` · `dead` | `npcs.people[]`, and `read-place`'s `post` |
| `living` · `fallen` | `villains.people[]` |
| `complete` · `empty` | `key_location_plans.plans[]`, and `read-place`'s `location_plan` |
| `complete` · `partial` · `unbuildable` | `city_plans`, `hamlet_plans`, `castle_plans` items, and `read-place`'s `site_plan` |
| `present` · `gone` | `person-state-request`, the write API's own words |
| `supported` · `unreachable` · `schematic` · `not_started` | `asset_list.assets[]` |

### The trap that fails loudly: two depths, one name

`status` is a **block outcome** at the root of `heroes`, `npcs`, `story_web`, `key_locations`
and `key_location_plans` (`ok` / `failed`), and a **person's state** one or two levels down in
the same document. Matching on the string alone reads a failed package as a living person.

It is safe today only because no token is in both sets, and nothing enforces that.
`tests/test_status_vocabulary.py::test_a_block_outcome_cannot_be_read_as_a_person` exists so
that stops being true audibly. **Dispatch on the path you read the record from, never on the
shape of the record.**

### The trap that fails silently: `complete` is two questions

`key_location_plans.plans[].status == 'complete'` means *this plan has contents* — its
complement is `empty`.

`city_plans` / `hamlet_plans` / `castle_plans` item `status == 'complete'` means *this item was
fully placed* — its complements are `partial` and `unbuildable`.

A consumer filtering plan blocks on `status == 'complete'` is asking two different questions
and will never be told which one it got. **This is the one place where value-matching across
blocks is already unsafe, and it is unsafe quietly.**

### The trap in between: you cannot ask "is this person still here" in one word

The live token is `living` for heroes, **`alive`** for npcs, `living` for villains. So
`status == 'living'` is right twice and silently wrong once. The end token is `legend`, `dead`,
`fallen`: three words for one event, and two of them carry a judgement the third does not.

`living` is therefore also overloaded — a hero who is not `living` is a `legend`, a villain who
is not `living` is `fallen` — so a consumer that learned the word from one contract learned the
wrong other half.

**What to use instead.** The translation is published, in two places, and neither is the token:

- `Sim/icarus_sim/terrain_liveness.py` — `liveness(record, block)` returns `present` or `gone`
  across all four person lists, `token(block, state)` is its inverse, and `PRESENT_STATUS` /
  `GONE_STATUS` are the mapping tables. Dispatch is on the block the record came from, and an
  **absent `status` reads as present** — a record written before its package recorded departure
  described someone who stood.
- Out of process, `POST /world/person-state` speaks `present` / `gone`
  (`Contracts/schemas/person-state-request.schema.json`) and reports the block's own word back
  in `token` (`person-state.schema.json`).

Each person-level `status` declaration in `hero-generator`, `npc-roster` and `villains` also
carries a `liveness` annotation mapping each of its tokens to `present` or `gone`, so the
mapping is readable from the contract without running Python. See below.

## `camps` — three unrelated lists

| Path | What it is |
|---|---|
| `heroes.camps[]` | **static**. Squatter camps at ruins, with a `uid` and a `node`; a hero's `presence.site_kind` may be `camp` |
| `nomads.bands[].camps[]` | **mobile**. A band's waypoints, each with a `kind` of `winter`, `summer`, `base`, `station`, `lair`, `shrine`, `terminal` or `calving` |
| `beast_movements.groups[].camps[]` | a creature group's stopping places |

`heroes.summary.camps` is a **count** of the first of those, not a list. No id space is shared
between the three.

## `culture` and `culture_id` — a road grouping, not an ethnicity

| Path | What it is |
|---|---|
| `humans.cultures[]` | **road connectivity.** Cities joined by road links below a cost threshold. The block's own `culture_method` says the ids are "seed-local, not inferred ethnicities or political borders" |
| `villains.outlook.regions[].culture` | the `humans.cultures` id a region was grouped from, or `null` for a holding no region was produced for this age |
| `npcs.people[].civilization_id`, `heroes.people[].civilization_id`, `key_locations.sites[].culture_id` | the **registry** civilization id — this is the join key for culture, language and per-race traits |

**Do not join a `humans.cultures` id to anything that outlives an age.** A culture's id is
rebuilt every age from whatever the roads happen to join.
`Contracts/schemas/villains.schema.json` records what that cost: a tier ledger keyed to one
"silently resets and nothing can ever reach the band".

## Ids that renumber across an age boundary

An age advance rebuilds hamlet, fortress, plot, nest and culture ids. Two keys can read alike
and live in different number spaces: the cast builds a castellan uid on the **ordinal** fortress
id while `npc_roster` keys the same place by **terrain node**.

Stable id shapes, each stated in its own contract:

| Block | Shape | Survives an advance because |
|---|---|---|
| `villains.people[].uid` | `villain-<age>-<terrain node>` | neither the age nor the node is renumbered |
| `nomads.bands[].uid` | keyed to the terrain node | an ordinal or a culture id is not |
| `key_locations.sites[].id` | `keyloc-<archetype>-<node>` and its chain and cluster forms | derived from where the place is, never from where it landed in a list |
| `settlements.sites[].uid` (city uid) | stable across ages | its **position** in `settlements.sites` is not |

**Stable is not immortal.** If an advance drowns a location or destroys the culture that
justified it, the id resolves to nothing. Treat a dangling key as "the thing is gone", not as
renumbering.

[030 C2](decisions/030-magnitude-and-identity-conventions.md) is the convention this records.

---

## What this page does not do

It does not stop the next package adding a fifth `tier`. Only C1 does, and C1 is a convention
with no gate, so it works exactly as long as people read it. The table above doubles as the
grandfather list that an enforced version of C1 would need.

It is also not a claim that any of these fields is wrong. Every one of them is right inside its
own block. What collides is the **name**, and what this page buys is that the collision is
stated once instead of rediscovered per consumer.
