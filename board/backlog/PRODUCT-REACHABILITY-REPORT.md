# PRODUCT-REACHABILITY-REPORT — "authored" and "reachable" are different numbers and only the first is ever reported

Owner: none. State: open, unowned. Filed as the lowest severity of the product red team's `233182e`
findings because the fix already exists in one package and nowhere else — **and promoted after the
2026-09-20 grid ruling**, which established that the reference world admits zero of its five terrain
octaves. A reachability number measured on that world measures the degenerate corner of the
parameter space, which is the strongest argument for this card and was not available when it was
written.

## Requested behavior

Every catalogue that advertises a count reports, for a reference world, how many of its entries can
appear in *any* world and how many appeared in *this* one — with a reason for each that did not.
`key_locations` already does this. Nothing else does.

## The defect

The repository advertises catalogue sizes as capability: ninety-seven key-location archetypes, 663
creature profiles, 104 magical states. Those are counts of **authored** entries. The count of
entries a world can actually contain is smaller, sometimes much smaller, and is never stated.

Known instances:

- **Unplaceable by construction.** `board/backlog/BESTIARY-BRIMSTONE-BATS.md`: `brimstone-bats`
  clears every hard gate and then "never reaches the 0.3 suitability floor anywhere, so it can never
  be placed in any world." That card records this was the shape of **seven of the seventeen**
  creatures added in one pass, and that the failure is silent — "the catalogue validates, the world
  generates, and the creature simply is not in it. Nothing raises."
- **Gated on a player that does not exist yet.** Relayed from the coordinator: 25 creatures are
  keyed to hidden schools locked at zero occurrence until a player unlocks one. `docs/hidden-schools.md`
  states that generation can never raise one, so this is by design — but it means a quarter-ish of a
  creature tier is unreachable in every world the generator can currently produce, and the catalogue
  count does not say so.
- **Present but empty.** Relayed from the coordinator's dossier: `nomads.groups[].legs` is empty;
  camps are start points only; `key_locations[].interior` is a chamber graph with no contents and no
  encounters. `pending_ley_edits` has a round trip nothing has exercised.
- **Scale-dependent, and the reference world is not the sparse end — it is the degenerate corner.**
  `key_locations` yields 10 sites on seed 42 at size 17 and 91 at size 33; size 17 has 47 land cells
  against size 33's 268. Worse than sparse: the octave admission filter at
  `Sim/icarus_sim/terrain_tectonics.py:178` admits an octave only while its `wavelength` exceeds
  twice the grid step, so **size 17 admits 0 of 5 octaves**. Recomputed from the recipe-3 defaults
  and confirmed against thirteen worlds under `Artifacts/`, every one of which carries
  `resolved_octaves` 0 at size 17 and 2 at size 65. **No world in this repository has more than two
  of its five octaves, and the conformance reference world has none.** Every count measured against
  it is measured on terrain that does not exist yet.

## Why it matters

A count is the most quotable thing a capability has, and these counts are the ones that will end up
in a roadmap slide, a release note, or a phase-2 prompt telling an LLM what kinds of place exist.
The gap between 97 archetypes and 10 sites is not a defect — it is correct behaviour on a small
world — but **nothing in the repository distinguishes the two numbers**, so a reader has no way to
know which one they are holding.

The silent-unplaceable case is worse than a wrong count, because it is indistinguishable from a
world that happened not to roll one. `BESTIARY-BRIMSTONE-BATS` makes this point well and is the
reason this card exists at all: seven of seventeen, caught once, by hand.

## Proposed mechanism

**Copy what `key_locations` already does.** Every archetype appears either in `sites` or in
`diagnostics` with a reason, so "this world has no lava tubes" is answerable rather than silent.
That pattern is the deliverable; the rest is applying it.

- The creature catalogue gains the same treatment: every profile appears in a per-world diagnostic
  with one of — placed, conditions absent from this world, lost the draw to incumbents, or **never
  satisfiable**. `Sim/tests/test_creature_movement.py` already decomposes exactly these three plus
  the fourth, and already records `brimstone-bats` as `KNOWN_UNDERWEIGHTED` with reasoning attached
  rather than disabling the assertion. The decomposition exists; it is not exported.
- A release-time reachability summary per catalogue: authored / ever-reachable / present in the
  reference world. Three integers.

Deliberately **not** proposed: fixing `brimstone-bats`, retuning the tier pyramid, or unlocking
hidden schools. Those are `BESTIARY-BRIMSTONE-BATS`, `BESTIARY-PYRAMID-RETUNE` and the
super-villains work respectively. This card is only about making the number visible.

## Dependencies and unresolved decisions

- Sequence **after** `BESTIARY-PYRAMID-RETUNE`, which changes which creatures are reachable — the
  tier pyramid is currently inverted, so a reachability number measured before it lands will be
  wrong in a way that looks like a regression afterwards.
- Overlaps `BESTIARY-BRIMSTONE-BATS`, which should stay open on its own merits: that card fixes one
  creature, this one reports the class.
- Open: whether "ever-reachable" is computable or only samplable. Proving a creature can never place
  anywhere is a search over the whole parameter space, not one world, and may not be cheap. If it is
  not, the honest version reports "not seen across the reference seed set" and says so, which is
  weaker and still much better than silence.

## Sources consulted

`board/backlog/BESTIARY-BRIMSTONE-BATS.md`; `board/backlog/BESTIARY-PYRAMID-RETUNE.md` (via
`board/README.md`); `Sim/icarus_sim/terrain_nests.py:53,96-105`; `Sim/key_locations/__init__.py:58`
and the `diagnostics` contract; `docs/hidden-schools.md` (generation can never raise a hidden
school); `Contracts/README.md:12`; the coordinator's dossier §7, §10, §13 (relayed — hidden-school
creature count, empty `legs`, scale trap, size-17/33 yields).

## Files and assets in scope

Creature catalogue diagnostics in the nests package; a release-time summary wherever the asset list
is compiled. Reporting only — no placement rule changes, and a change that alters which creatures
place has exceeded this card.

## Acceptance and evidence

A reference world's output answers "why is there no `brimstone-bats`" with `never satisfiable`
rather than by omission. The three-integer summary exists for at least the creature catalogue and
`key_locations`, and the numbers differ, which is the point.

## Documentation impact

`docs/publishing.md` — the exhaustive asset list already has a policy of describing every supported
potential final state, and this is the same idea pointed at the other end of the pipe. Worth
checking whether the asset-list compiler already answers half of this before building anything.

## Adversarial review and limitations

**This card reports an absence of measurement, which is cheap to say and easy to overvalue.** It is
the weakest of the product red team's findings and is filed as a nit. Nothing is broken for lack of it; the
worlds are correct and the tests pass.

**The real objection is cost.** Proving unreachability properly is a search, not a check, and a
half-proof that says "not seen in three seeds" invites exactly the false confidence this card
complains about. If the honest answer is only samplable, the card's value drops sharply and it
should be closed as "report what we sample, say it is a sample" rather than built out.

**Where I may be double-counting:** the hidden-school creatures are unreachable *by design* —
`docs/hidden-schools.md` says generation can never raise one, and that is the whole point of the
design. Counting them as a reachability gap is arguably unfair to a deliberate decision. I have kept
them in because a catalogue count that includes them is still overstating what any current world can
show, but a reviewer who strikes that bullet has a fair case and the card survives on the
`brimstone-bats` evidence alone.

## Handoff

Found by reading `board/README.md`'s catalogue counts against the bestiary cards and the
`key_locations` diagnostics contract. The `key_locations` pattern is the whole proposal; everything
else here is an argument for copying it. Full reasoning in
`docs/reviews/233182e-product-red-team.md`, Finding 6 — note that document's own placement warning.
