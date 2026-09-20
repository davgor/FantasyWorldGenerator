# Corruption: the hidden gods, and the API that lets them act

Generation locks the hidden schools' occurrence at zero and restricts player leyline edits to the known eight. **This is the only path by which a hidden school ever gets a node.**

Reference: `Sim/icarus_sim/terrain_corruption.py` (the API), `hidden_pantheon.json` (the four), `terrain_religion.hidden_records` (how they are exported). Python only, like the pantheon and the age API; the native core does not port them.

## The four

| God | School | Noticing | Takes interest where |
|---|---|---|---|
| The Long Thirst | blood | 3 | population is dense |
| The Glad Mother | rot | 6 | decay has already set in |
| The Shape Beneath | eldritch | 10 | aberrant nests cluster, or ruins stand |
| The Unwriting | void | 15 | magic has gone dead |

They live in `hidden_pantheon.json`, **not** in `pantheon.json`, and that is deliberate: `catalogue_identity()` hashes the known catalogue, so folding them in would retire every saved world each time one was touched. They are still exported, in `religion.gods` with `family: "outside"` and `status: "absent"`, because keeping them out of sight is the game's job and not the generator's. No faith names one; no world fact mentions one.

## The gate is the game's ledger

The game counts villains the player has met across playthroughs and passes it in as `encounters`. Below a god's noticing point the chance is **exactly zero**, not merely small — the gods are not watching yet. Early playthroughs are therefore guaranteed clean, which is what makes a first corruption read as an escalation the player caused rather than a bad roll. Above it, the chance climbs linearly to certain at that god's `climb`.

The four noticing points are staggered (3, 6, 10, 15), so they arrive across many runs and a player may never meet all four.

**The counter says whether; the world says which.** Once a god is watching, its identity is never rolled — each has an `interest` scorer read from world state, and the most interested eligible god acts, ties by id. Eligibility reuses `rule_holds`, the same existence-rule evaluator the known pantheon uses.

`encounters` takes its **own parameter and its own seed domain**, not an overload of `variation`:

```
child_seed(seed, f'corruption-{index}-{god_id}-escalation', encounters)   # whether it bites
child_seed(seed, f'corruption-{index}-{god_id}', variation)               # everything else
```

It is recorded in both the corruption record and `history.operations`, or `history.replay` would be a lie and a world could not be replayed from its own record.

## What a corruption does

A god seats an existing super villain — the one with the most reach, or a named `villain_uid` — and:

1. places a corrupted cluster of nodes in its hidden school at the villain's seat
2. applies that god's failure mode to every city inside **the villain's own reach**
3. rebuilds fields, biomes, civilization, nests and threats
4. binds the villain: `god`, `school`, `corrupted`, and the new nodes in `held_nodes`
5. reveals itself, and rouses the known pantheon

Step 3 is the shared rebuild tail and it is reached **indirectly**, which has already cost one wrong board card.

`terrain_corruption.py:269`

That line calls `rebuild_tail`, whose body runs the network evaluation, the environment refresh and the biome variants, in that order.

`terrain_history.py:288`

So searching this module for the names of those three functions finds nothing and proves nothing. It is a grep for the callee inside the caller. The ground does move: on a seed-42 world a corruption takes the hidden field from negative zero to 1.149990 and produces hidden-school cells where there were none.

### Four distinct failure modes

| God | What happens to a city | The tell |
|---|---|---|
| Blood | population falls, the city stands — it is being farmed | people dropping while the walls hold |
| Rot | the city ends; cause `rot_plague` | its own dead are the threat |
| Eldritch | the city stands intact and is **taken** (`taken_by`) | nothing. That is the horror |
| Void | the city ends; cause `void_unmade` | the ground goes with it |

### The pantheon reacts

Before a return there is no trace of the hidden four anywhere. Afterwards the revealed god goes `walking` with its Wild aspect, and its rivals in the known pantheon gain `roused_by` and are pushed to their own Wild faces where they have one.

That matters mechanically, not just narratively: `ASPECT_FACTOR` in the visitation API already makes a Wild god destroy **four times** what a Sovereign one does. Rousing the pantheon is how the cure becomes able to exceed the disease.

## Cleansing, which is also how a god is opposed

`cleanse_request` takes `{"corruption": <index>}` or `{"god_id": ...}` and a `power` in (0, 1].

**The structure drains as it ramps.** It does not out-compete, because out-competing is arithmetically impossible: potency saturates at a network's strength, so a corrupted node at full intensity sits above what any counter-node of equal strength can reach, and the boundary would creep inward in a ring and never take the node's own cell. Each tick removes `power × 4` from every corrupted node; a node at zero is removed; when the last one goes the corruption is `cleansed`, the holder is unseated and the god goes back to sleeping.

It takes time by construction — a partial-power structure needs several ticks — which is the point.

**Killing the villain is not cleansing the land.** The nodes are the persistent entity. Unseating a holder leaves them standing and a successor free to take them; cleansing is the other order of operations.

Opposing a walking god is the same operation under another name: an avatar is a ley cluster and not a creature, so driving one off is cleansing its nodes. **The `{"god_id": ...}` form is for a god that walks by visitation, and its effect is an early departure.** A god revealed by a corruption does not walk by visitation — it has no visitation record, because its footprint is the corrupted cluster — so that form now refuses it with a message naming the route that works. Oppose a revealed god through `{"corruption": <index>}`: the same drain, on the thing the god actually is here.

Until this was corrected the `{"god_id": ...}` form raised a bare `StopIteration` on exactly the god corruption creates, which is to say on the only god this paragraph could ever have been about. Whether refusing is the right answer, or whether opposing a revealed god should drain all of its live corruption records in one call, is an open design question recorded on the board.

## Limits

`NODE_BUDGET` caps corrupted nodes per world at 96, and cleansing frees them — a budget on what stands, not on how many times the API may be called, because an unheld node is a spawner and a call cap would contradict that.

The API is stateless: same body, same world out, and the caller's world is never touched.
