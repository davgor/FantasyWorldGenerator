# CONTENT-ENCOUNTERS-ARE-FISH — the "what is near here" index answers with sharks

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
