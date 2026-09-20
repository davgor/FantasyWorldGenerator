# CONTENT-QUEST-HOOKS-NO-VERB-NO-TARGET — the best quest content in the world carries no verb, no difficulty, and points at a direction vector

Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 8).

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
