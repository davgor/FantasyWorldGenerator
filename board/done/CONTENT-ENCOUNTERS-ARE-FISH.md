# CONTENT-ENCOUNTERS-ARE-FISH — the "what is near here" index answers with sharks

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** **2,627 entries, `wary` on 2,589 = 98.6%**; the top six kinds are all marine and account for 55.6%. The carded “98% wary” reproduces to within 0.6 points at a different world size.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 3).

## Observed behavior

Seed 42, size 17, `generator_version` 16. `encounters` is the block a consumer is told to query
for proximity — its own `method` reads *"indexed by month and by terrain node so a consumer
answers 'what is near here'"*. It holds 805 entries over 159 nodes and 1,513 occupancy records.

- **792 of 805 entries come from `beast_movements`; 13 from `nomads`.**
- The seven most common kinds are narwhal (89), Greenland shark (75), Atlantic bluefin tuna (69),
  blue shark (69), shortfin mako (69), swordfish (69), oceanic whitetip (43) — **483 entries, 60%
  of the index, are pelagic fish.**
- **790 of 805 entries are `disposition: wary`.** Six hostile, five fleeing, four devout.
- `threat_tier` runs 1 (286), 2 (215), 3 (291), 4 (13). **No entry is tier 5**, although the
  world holds 94 tier-5 nests.

The cause is upstream and is the same one as `CONTENT-NO-DIFFICULTY-GRADIENT` finding 2b: 232 of
301 nests are `aquatic territory` because the world is 80.5% ocean, and `beast_movements` draws
786 of its 792 groups from `wildlife`. The index faithfully reports a world whose mobile
population is marine.

## Why it matters

`encounters` is the only block in the document that carries a difficulty number attached to a
position. It is the natural join for "who could a player meet on the way to X", and it is the
access path the nomads contract names for exactly that. As emitted it returns, for most land
nodes, a wary fish.

This is not a correctness defect — every record is true — and the block is candid in its
`limits`: *"An index, not a quest generator: no objectives, stakes, rewards or difficulty,
because the consumer that would define them does not exist yet."* The defect is that the index
has no way to express the distinction a consumer needs, so every consumer will have to
re-implement the same filter.

## Proposed mechanism

Three changes, smallest first, none of which require the quest consumer to exist:

1. **Carry the domain.** Each entry knows whether its group lives in water, on land or in the
   air — `beast_nests.sites[].kind` already distinguishes `aquatic territory` / `lair` / `roost` /
   `colony`, and every point record in this document already carries a `domain`. Put it on the
   entry so a land query does not have to join back through two blocks to drop 60% of the index.
2. **Carry the source class.** `kind: "animal"` versus `kind: "monster"` is on the
   `beast_movements` group (786 animal, 6 monster) and is lost at the entry. A consumer asking
   "what could threaten a traveller" needs it and currently gets the species id.
3. **Report the tier-5 absence.** 94 tier-5 nests produce no tier-5 encounter because nests are
   static and only movers are indexed. That is correct and surprising; state it in `limits` so
   nobody reads the histogram as the world's danger profile.

## Dependencies and unresolved decisions

- Whether static sites should be indexed at all. Today `encounters` covers movers only, so the
  most dangerous things in the world — lairs — are absent from the index that answers "what is
  near here". Including them is a bigger change and a design decision, not a field addition.
- `encounters.version` is 1 and there is a schema (`Contracts/schemas/encounters`), so adding
  fields is an interchange change with the version bump and record edit `AGENTS.md` requires.

## Acceptance and evidence

- An entry carries enough to answer "is this reachable on foot" without joining to another block.
- A behavioral test asserts the land/water split on a reference world, so a future placement
  change that empties the land is visible.
- `limits` states that static sites are not indexed and that the `threat_tier` histogram
  therefore describes movers only.

## Adversarial review and limitations

One seed at one size. The 60%-marine share is a consequence of `area.land_fraction` 0.195 and
will move with any world whose land fraction differs; the finding is that the index cannot
express the difference, which does not move. The gamer-persona session independently measured the
same marine skew from the nest side and is carding the player-facing half.

## Delivered 2026-09-21

**Premise re-tested and it reproduced.** On a freshly generated seed 42 size 33 phase 16
world: 2,778 entries, `wary` on 2,735 = **98.5%**, against the carded 98% and the
reconciliation's 98.6%. The six most common kinds are still all marine - greenland-shark 313,
narwhal 302, swordfish 230, bluefin tuna 228, mako 203, blue shark 196. `threat_tier` runs
1119 / 843 / 785 / 31 / **0**: the world holds tier-five lairs and the index carries no
tier-five entry at all, exactly as the card says.

**Delivered: steps 1, 2 and 3, all three.** `encounters` is at version 2 and every entry now
carries:

- `domain` - `land`, `ocean` or `lake`, resolved from the species' authored medium. On the
  word `key_locations` already uses, rather than a fourth vocabulary for the same idea. A
  `shore` species is `land`, because `suitability` refuses a shore medium every water cell and
  then asks for a coast, so a puffin colony is on the beach and a traveller can walk to it.
- `class` - `animal`, `monster` or `people`, on the word `wildlife` and `beast_nests` already
  use. `kind` was already spent on the species id or the band classification, which is why
  the class was being lost.
- `airborne` - the species flies. Deliberately **not** a fourth domain value: a roost is
  somewhere you can stand, and folding flight into `domain` would stop `domain == "land"`
  meaning reachable on foot.

Measured on the same world, the split is **ocean 1,586 / land 1,184 / lake 8**. A land query
now drops 57.4% of the index with one field test instead of joining back through
`beast_movements` to `beast_nests`.

`limits` now states step 3 outright: static sites are not indexed, so the lairs - the most
dangerous things in the world and the ones that hold still - are absent, and the
`threat_tier` histogram describes travelling groups rather than the world's danger profile. A
world holding tier-five nests can and does produce an index with no tier-five entry.

**The unresolved decision in the card**, whether static sites should be indexed at all, was
**not** taken. The conservative option is to say so in `limits`, which is what was done; the
card is explicit that including them "is a bigger change and a design decision, not a field
addition". Recorded here so the owner can reverse it.

**Test: `Sim/tests/test_encounters.py`, 9 tests, against a hand-built block rather than a
generated world.** That is the point of it, and it is the coordinator's warning taken
seriously: the claim is about a *split*, and a generated world is a terrible fixture for a
split because it is 98.5% one disposition and roughly three quarters one domain, so a
share-based assertion passes for almost any mapping including a constant one. The fixture
carries one real species per medium and per class in equal numbers, and every assertion is
per entry against the catalogue.

Before the implementation all 9 were red - 7 errors on the missing keys, `1 != 2` on the
version, and `'threat_tier' not found in` the old limits string.

**Ablation.** Five arms, each breaking one thing:

| ablation | tests red |
|---|---|
| every domain forced to `land` | 5 |
| `shore` and `marine` swapped | 4 |
| `freshwater` folded into `ocean` | 3 |
| `class` forced to `animal` | 1 |
| `airborne` never set | 1 |
| `VERSION` left at 1 | 1 |

A constant mapping kills five of the nine, by named uid. Not ablated: the `limits` prose
assertion, whose ablation is deleting the sentence - already observed red before the change.

The generated block validates against the updated schema
(`Contracts/schemas/encounters.schema.json`, version const 2, `domain`/`class`/`airborne`
required).

**Not done.** The entry still cannot be filtered to routed-versus-stranded groups; that is
`CONTENT-BEAST-MOVEMENTS-STRANDED`, which this card names as an overlap and which is blocked
on a live editor - see that card.

`Fixtures/sample-world-v1.json` is stale: every encounter entry gained three fields.
