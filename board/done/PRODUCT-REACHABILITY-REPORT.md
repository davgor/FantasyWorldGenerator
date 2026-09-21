# PRODUCT-REACHABILITY-REPORT — "authored" and "reachable" are different numbers and only the first is ever reported

**Delivered 2026-09-21, as the narrow version this card told itself to close as.** The open
question — whether "ever-reachable" is computable or only samplable — was measured and the
answer is **only samplable, except for a small provable core**. So the creature catalogue now
reports what this world holds and says out loud that it is a sample, and the three-integer
cross-world capability number is **not** built and should not be.

Everything below the resolution is the original text and is unchanged.

---

## Resolution

### The open question, measured

Five worlds, seeds 42 / 7 / 73 / 101 / 900, size 33, phase 13, one eligibility scan per
profile per world (clears medium, temperature and `requires`, scores at or above the 0.3
suitability floor, on a cell whose biome it uses). This scan deliberately ignores the
settlement clearance, so that the world question and the placement-rule question stay apart
— which is what turned up the defect two sections down. Seed 42 reads 618 here and 561 in
the block, and the 57 between them are the whole of that defect:

| | profiles |
|---|---|
| authored | 680 |
| eligible on **all five** worlds | 579 |
| eligible on **some but not all** | **53** |
| eligible on **none** of the five | 48 |
| provably unreachable from the profile alone | **25** |

**53 of 680 change answer across five seeds at a single raster**, which settles it: a
per-world eligibility count is a sample, not a capability, and no single world's number is
the "ever-reachable" one. `sulphur-eels` is eligible on 2 of 5, `kelpies` on 1 of 5,
`geyser-serpents` on 1 of 5, and more than twenty freshwater species — trout, carp, newts,
pond snails, kelpies — swing on whether a world rolled enough fresh water. That reproduces
[BESTIARY-AUTHORING-CHECK-SEES-ONE-SEED](../backlog/BESTIARY-AUTHORING-CHECK-SEES-ONE-SEED.md)'s ten
from an independent scan and finds five times as many.

**And the sampled-absent set is not the unreachable set.** 48 profiles appear on none of the
five worlds, but only 25 of those are provable — every one for the same reason, a `requires`
on a ley school `docs/hidden-schools.md` says generation can never raise. The other 23 are
`polar-bear`, `sea-otter`, `plains-zebra`, `saltwater-crocodile` and their kind: creatures
wanting ground five worlds did not roll. **A report that called all 48 unreachable would be
wrong about 23 of them**, which is precisely the false confidence this card was filed to
avoid. Proving the 23 either way is a search over seed × raster × forty world options, and
nobody has run it.

The figure worth recording because it is the one a roadmap slide would want, and it is this
world's and not a capability: on seed 42 at size 33 the creature catalogue is **680 authored
/ 561 eligible / 453 placed**. Split: monsters 369 / 274 / 167, animals 311 / 287 / 286.

### The reason vocabulary found a defect the card did not predict

A first draft of this had four reasons — the card's own list. Cross-checking the block's
`eligible` (561) against an independent scan that ignored the settlement clearance (618)
left 57 profiles unexplained, and they are all one thing: **graveyard and barrow creatures
whose only habitat is the ground a settlement stands on.** `graves` exists where people bury
people, so `barrow-rats`, `coffin-beetles`, `bone-crows` and 54 others score on exactly 7
cells, and those 7 cells are the ones `nest_settlement_clearance` refuses outright. **15% of
the monster catalogue is unplaceable on this world because of a placement rule, not because
of the world**, and the four-value vocabulary would have filed every one of them under
`conditions absent from this world` and sent a reader to look at terrain that is fine.

**And it is violently seed-dependent**, which is the card's own thesis arriving from a
direction nobody aimed at: 57 profiles on seed 42, **32 on seed 7, 1 on seed 73**. It
depends on how much grave ground a world happens to put outside a settlement's own cell. A
reader who measured this on seed 73 and wrote "the clearance costs us one creature" would be
wrong by a factor of 57 — on the same code, at the same raster.

So there is a fifth reason, `its only ground is inside a settlement clearance`, and a test
that recomputes eligibility with the gate removed and requires the block to name it.
Whether the *right* answer is to let a barrow rat lair in a graveyard is a content question
this card does not decide; it only stops the number lying about which question it is.

The block-level integers across those three seeds, for the same reason — they are a sample:

| seed | authored | eligible | placed | cleared out |
|---|---|---|---|---|
| 42 | 680 | 561 | 453 | 57 |
| 7 | 680 | 584 | 445 | 32 |
| 73 | 680 | 626 | 491 | 1 |

Full decomposition on the reference world: monsters 167 placed / 107 lost the draw / 57
cleared out / 25 never satisfiable / 13 conditions absent; animals 286 placed / 24
conditions absent / 1 lost the draw.

### What landed — reporting only, no placement rule changed

Copying the `key_locations` pattern the card asked for, one level down and per species. Both
`wildlife` and `beast_nests`:

- every `diagnostics` row gains `cells` — how many raster cells that species could have lived
  in — and `reason`, one of five values published as `REACH_REASONS`: the card's own
  `placed`, `lost the draw to incumbents`, `conditions absent from this world` and
  `never satisfiable`, plus `its only ground is inside a settlement clearance` for the reason
  above.
- each block gains `reachability`: `authored`, `eligible`, `placed`, `never_satisfiable`, and
  a `scope` line that states in the document itself that the middle two are this world's and
  move with the seed.
- `never_satisfiable(p)` is published as a function and is the whole of what is decidable
  without generating worlds. Its docstring carries the five-seed measurement so the next
  reader does not have to re-derive why it is so narrow.

`Sim/tests/test_nest_diagnostics.py` asserts the honesty rather than only the plumbing:
`test_absence_from_this_world_is_not_a_proof_of_unreachability` requires the provable set to
stay **strictly smaller** than the set this world merely lacks, so the block cannot start
claiming a proof it does not have. `test_a_dormant_school_requirement_is_the_world_independent_verdict`
pins the one verdict that does hold for every world, in both directions.

`wildlife` 2 → 3 and `beast_nests` 3 → 4, additive; `docs/conformance/creature-placement.md`
updated in the same change.

### Decisions taken on the owner's behalf — reversible, flagged

**1. "Ever-reachable" is not built, and the card's own instruction is followed rather than its
proposal.** This card says: *"If the honest answer is only samplable, the card's value drops
sharply and it should be closed as 'report what we sample, say it is a sample' rather than
built out."* Measured, it is only samplable. So what shipped is per-world, labelled per-world,
with the provable subset named separately. *Rejected:* a release-time multi-seed sweep
publishing an "ever-reachable" integer — it would be a sample wearing a capability's name,
and 53 profiles are enough to make it wrong.

**2. The hidden-school creatures are counted as `never satisfiable`, and the card's own
doubt about that is worth keeping.** They are unreachable *by design*, and `never_satisfiable`
reads as an accusation. It is reported separately from the world reasons precisely so a reader
can subtract it: `reachability.never_satisfiable` is its own integer and not folded into
`eligible`. Reverse by treating a dormant `requires` as `conditions absent` instead; the
vocabulary constant is one line.

**3. `key_locations` was not touched.** It already publishes this and the card says so.
Nothing here changes its numbers or its vocabulary.

### Not done

- **No cross-catalogue release-time summary.** The card asks for one "wherever the asset list
  is compiled". Two of the three catalogues it names — magical states and key-location
  archetypes — are outside this lane, and the honest summary for all three is the sampled one
  this card just ruled against building. `Sim/fantasy_world_generator/asset_list.py` already
  carries the same idea for biomes via `UNREACHABLE_BIOMES` / `reachable_natural_catalogue`,
  which is worth reading before anyone revisits this.
- **The 23 sampled-absent-but-not-provable profiles are not assessed**, and assessing them is
  [BESTIARY-AUTHORING-CHECK-SEES-ONE-SEED](../backlog/BESTIARY-AUTHORING-CHECK-SEES-ONE-SEED.md)'s census
  with a ratchet, not this card. That card should now be worked against these 53, not its own
  ten.
- `Fixtures/sample-world-v1.json` is stale. Not rebuilt here, by instruction.
- `board/README.md` still links this card at `backlog/`; repointing it is orchestrator-owned
  and `docs_check` is red on that line until it moves.
- **No cross-seed census is run at generation time and none should be.** The five-seed and
  three-seed numbers in this card come from scratch scripts, not from anything the product
  ships. Making them a gate is the thing this card ruled against.

---

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
