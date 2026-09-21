# CONTENT-QUEST-HOOKS-NO-VERB-NO-TARGET — the best quest content in the world carries no verb, no difficulty, and points at a direction vector

Owner: local. State: **delivered** 2026-09-21 as `heroes` version 2.

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** **235 hooks**, keys exactly as carded, no `verb` and no `difficulty` on any; `target` is a bare string on 234 of 235. The `verb` in `hero_generator` is on the person's claim, never on the hook.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 8).

## Delivered

`heroes.quest_hooks[]` carries the quest contract: **anchor, verb, difficulty 1–5, and the
node a player stands on**. The generator prices nothing; the consuming game does.

Four fields per hook, all at `heroes` version 2:

| field | what it is |
|---|---|
| `verb` | one of the canonical ten (`npcs.verbs`), never a parallel list |
| `difficulty` | integer 1–5 on the creature-tier rubric, derived |
| `target_node` | the terrain node a player stands on, or `null` |
| `unsited_reason` | why there is no node, from a published vocabulary of three |

and `target`, which was `null` on every slay hook because a nest effect names `nest_id`
while the field read only `uid` or `node_id`, is now never null.

**The rule, which is the decision this card was really asking for:**

    difficulty = clamp(1, 5, floor(opposition + pressure + 0.5))

*Opposition* is what stands at the target and is the only term that can reach 5 — a lair's
own `tier`, a ley node's own `intensity` (`1 + intensity/2`), or a floor by what the place
is: 2 for ground somebody holds (ruin, relic, city, hamlet, fortress, port), 1 for an
errand (shrine, college). *Pressure* is 0.25 per tier of the worst nest whose own declared
`range_m` reaches the target's ground, capped at 1.0 and never applied to a nest target —
its tier is already the whole answer, and its range would otherwise count it twice. The
floors, weights and caps are policy (`wells.json` `quests`, revision 6); the verb
vocabulary is a closed contract and is code (`hooks.VERBS`).

**On the ley-node question (gap 3), the answer is neither of the two the card proposed.**
The card offered "site them" or "stop targeting them". Measured, the set splits: a ley
**key point** — id `<ruin id>-key`, ten of 78 nodes on seed 42 size 17, all ten resolving —
already stands at a ruin with a node, and `_node_name` was already making that join for
prose. So a key point is **sited at its ruin**, and only a **bare** node is reported
`ley_node_has_no_site`. On the reference world that is 4 of 46 hooks rather than 8. No
position is invented for anything, and no content is deleted.

Rejected, with reasons, per the owner's pick-implement-flag rule:

- **Giving bare ley nodes a sited presence.** They carry a direction and an intensity and
  nothing else; any position would be one this package invented, and siting them is a
  `magic` change owned by whoever owns that block.
- **Dropping ley hooks entirely.** They are 18% of the block, they are the only hook kind
  whose completion has a declared world effect (`terrain_time._apply_resolutions` applies
  the `intensity_delta`), and deleting them to avoid stating a limitation trades content
  for tidiness.
- **A `difficulty_breakdown`.** The plan puts the auditable arithmetic in the quests
  package. A hook publishes one integer; a breakdown that no consumer reads is a second
  place for the equation to drift.
- **A `regional_threat` term.** `threat_assessments.cities[].regional_threat` maxes at
  0.361 on the reference world, so with round-half-up banding it could not move a single
  hook. A knob that cannot change the answer is worse than no knob.

**Measured after, seed 42 size 17 generator 16:** 46 hooks, difficulty 1×3 / 2×29 / 3×13 /
4×1, verbs `defend` 24 / `tend` 5 / `cleanse` 4 / `reclaim` 4 / `recover` 4 / `trade` 4 /
`convert` 1, 42 sited and 4 `ley_node_has_no_site`, 0 null targets. Nothing reaches 5
because nothing on that world targets a lair; the equation reaches 5 only through a tier-5
nest, which the hand-built reference world does exercise. **All 19 city hooks land on 2**,
because no nest range reaches a city cell at that raster — the flattest part of the
distribution and the first thing to look at if this is ever calibrated.

**Two premises in this card no longer reproduce** (both on a freshly generated seed-42
size-17 world, not the fixture):

- The count is **46 hooks, not 49**, and the kind mix is city 19 / ley_node 8 / hamlet 7 /
  ruin 4 / relic 4 / fortress 3 / shrine 1 — no ports and no colleges, because
  `fisheries.ports` and `magic.colleges` are both empty at that size.
- **`unwitting` is true on 4 of 46, not false on all of them.** The betrayal mechanic does
  fire; gap 3 of this card is stale and was left alone as the card asked.

**One live collision, absorbed rather than worked around.** A concurrent session
(`SDET-SITE-ID-ORDINALS`) re-keyed reeve and castellan claims from `humans.hamlets[].id`
onto the positional `hamlet-node-<n>` / `fortress-node-<n>` that `npc_roster` uses, while
this card was being implemented. Ten hooks began reporting `target_not_found` — correctly,
which is the point of the field, but they were sitable. `_small_sites` now indexes both
spellings and **imports `wells/countryside.anchor`** rather than copying its format, so the
lookup follows whatever that session settles on. The hook counts above moved from 44 to 46
under that same change; they describe the tree as delivered.

**Not done, and named:** difficulty is not carried into the `quests` block, so
`POST /world/quests` still answers without it. That block's own schema states the absence
as deliberate (`read-quests.schema.json`), and moving it would bump `quests` and the read
document's `schema_version` — a contract decision for whoever owns the time capability, not
a side effect of a hooks card. The join is `quests.quests[].quest_id` →
`heroes.quest_hooks[].hook_id`.

### Files

`Sim/hero_generator/hooks.py`, `Sim/hero_generator/__init__.py` (VERSION 1→2, method and
limits prose), `Sim/hero_generator/policies/wells.json` (`quests` section, revision 5→6),
`Contracts/schemas/hero-generator.schema.json` (version const, the four fields, the verb
enum and the unsited vocabulary), `Fixtures/hero-generator-v1.json` (fixture 9, policy
revision only — no draw reads the new section, so not one person, roll, bond or mantle
moved), `Sim/icarus_sim/terrain_time.py` (`_quest_step` reads the hook's own `verb`, which
is what stops a ley quest reading as verbless), `docs/hero-generator.md`,
`docs/conformance/time-advance.md`, `docs/time-advance.md`,
`docs/conformance/version-bindings.json` (new `heroes` binding),
`Sim/tests/test_hero_generator.py` (`QuestContractTests`, five tests).

`Sim/hero_generator/hooks.py` is claimed by no conformance record — the whole package sits
on `coverage.json`'s uncovered allowlist under `board/in-progress/CONFORMANCE-DOCS.md`, so
the canonical `docs/hero-generator.md` took the change and the coverage question was left
where it is owned.

## Observed behavior

Seed 42, size 17, `generator_version` 16. `heroes.quest_hooks` holds 49 records of shape
`{hook_id, giver_uid, offered_from_face, stated_purpose, actual_effect, unwitting, target}`:

```json
{"hook_id": "hook-hero-domain-surface-city-0-101-human_desert-1",
 "giver_uid": "hero-domain-surface-city-0-101-human_desert",
 "offered_from_face": "public",
 "stated_purpose": "Weaken the umbral node umbral-node-6; it chokes the radiant.",
 "actual_effect": {"kind": "ley_node", "node_id": "umbral-node-6",
                   "school": "umbral", "intensity_delta": -0.5},
 "unwitting": false, "target": "umbral-node-6"}
```

Every `giver_uid` resolves to a named hero with a persona, a claim and an alignment. Every
`target` resolves. The prose is in the world's own voice. This is the closest thing the generator
emits to a quest, and it is good.

Three gaps:

1. **No verb and no difficulty.** The record has neither field. The world publishes difficulty on
   two other axes — `key_locations.threat` 1–5 and `beast_nests.tier` 1–5 — and `encounters`
   carries `threat_tier`, but nothing joins a hook to any of them. Per
   `fwg_quest_contract`, the agreed shape is anchor + verb + difficulty 1–5 with the game pricing
   rewards; a hook currently supplies the anchor and nothing else.
2. **Ten of 49 target a ley node.** `actual_effect.kind` breaks down as city 14, **ley_node 10**,
   ruin 6, relic 6, shrine 5, port 4, hamlet 3, fortress 1. A ley node is a direction vector and
   an intensity inside `magic.networks.<school>.nodes[]` — no footprint, no asset, no interior,
   nothing to stand in front of. "Weaken the umbral node" is a fine sentence and an unbuildable
   objective.
3. **`unwitting` is `false` on all 49.** The field exists to mark a hook whose `stated_purpose`
   and `actual_effect` diverge — a giver using the player. `offered_from_face` is `public` on 47
   and `first` on 2. The betrayal mechanic the schema is shaped around never fires in this world.

## Why it matters

The generator's product bet is that a game can be built on this output. `heroes` and `story_web`
are the blocks that bet rests on, and `quest_hooks` is where they reach toward a consumer. As
emitted, a quest compiler can read who is asking and what they want, and cannot answer how hard
it is, what the player does, or where to put the marker for a fifth of the hooks.

## Proposed mechanism

1. **Add the verb.** `npcs.verbs` already defines the canonical ten — reclaim, recover, defend,
   slay, trade, tend, convert, supply, cleanse, investigate — and `npcs.post_verbs` maps posts to
   them. A hook's verb should come from the same vocabulary, so a hero-given hook and a
   post-given offer are the same kind of thing to a consumer.
2. **Add the difficulty, derived rather than invented.** The target usually already carries one:
   a `key_locations` target has `threat`, a nest target has `tier`, an `encounters` entry has
   `threat_tier`. Where the target carries none — a city, a ley node — the hook needs a rule, and
   that rule is the decision this card is really asking for.
3. **Decide what a ley-node objective is.** Either give ley key points a sited presence so a
   player can reach one — they already have position, school, intensity and a stable id, and
   fourteen of them are raised by destroyed cities, which is a strong premise — or stop targeting
   them from hooks and let the ley effect be the *consequence* of a hook that targets the ruin.
4. **Leave `unwitting` alone until 1–3 land.** It is the most interesting field in the block and
   it needs a consumer before it is worth tuning.

## Dependencies and unresolved decisions

- **The quest consumer does not exist.** `fwg_quest_contract` was agreed and the build deferred;
  `encounters.limits` says the same thing in the code (*"no objectives, stakes, rewards or
  difficulty, because the consumer that would define them does not exist yet"*). This card
  should not invent one. It asks for the two fields that contract already specifies.
- Ley nodes are addressable only inside `magic.networks.<school>.nodes[]`; `magic.nodes` is a
  bare list of 78 direction vectors with no ids. Any consumer resolving a hook target of kind
  `ley_node` must know the school first. That is a lookup gap worth fixing alongside 3.
- `hero-generator.schema.json` has four enum sites of similar shape; adding a verb enum means
  picking the right one (`site_kind` is :399 and is not it).

## Acceptance and evidence

- Every `quest_hooks` record carries a verb from the canonical vocabulary and a difficulty 1–5.
- Every hook target resolves to something with a position a player can walk to, or the hook
  states why it does not.
- A behavioral test asserts both over a reference world.

## Adversarial review and limitations

One seed. The `unwitting: false` on all 49 may be a small-world artefact rather than a dormant
mechanic — it needs size 33 and a second seed before anyone concludes the field never fires. The
missing verb and difficulty are structural and do not depend on the seed.
