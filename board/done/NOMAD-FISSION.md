# NOMAD-FISSION - lineage fission for nomad bands

**Delivered 2026-09-21.**

## Requested behavior

A wanderer clan that outgrows its range should split, and the child should inherit part of
the parent's ground rather than being placed fresh. `fission` is already a declared branch
kind in `Contracts/schemas/nomads.schema.json` and in `terrain_nomad_routes`, and
`parent_uid` already exists on every band. **Neither is ever populated**, so the vocabulary
promises something the generator does not do.

## Premise, re-measured before implementing

Reproduced, on a generated world rather than by reading the card. Seed 42, size 33, phase
16: 17 bands, `parent_uid` populated on 0 of them, branch kinds present `{base_limb,
trunk}`, `fission` on 0 legs, and `nomads.routes.limits` saying "Lineage fission is not
built" in as many words. Seed 42 at size 17 raises no wanderers at all, so the size-33
world is the one that can exercise this.

## The unresolved question, and the ruling taken

**Chosen: fission runs ONCE, when a band is placed.**
**Rejected: fission runs again at every age transition.**

The owner can reverse this; here is what it would cost.

1. *Nothing kills a band.* Per-age fission adds population every age with no term removing
   anyone, so the band count rises with no ceiling. Once at placement is bounded by
   construction — at most one child per placed band, and a child never splits — so a world
   holds fewer than twice the bands it placed. Reversing the ruling needs both a ceiling
   and a death term, neither of which exists.
2. *A band does not survive an age anyway, and this is the argument the card did not have.*
   `add_nomads` replaces the whole block at every age turn, deliberately: an aged world
   reclassifies against the world it actually has, because a carried band would name ruins
   that had moved and refuges that no longer stood. There is therefore no surviving parent
   at an age boundary to split from. "Fission per age" would have meant inventing a lineage
   across a gap the generator does not model.
3. *An age is five thousand years* — `docs/decisions/028`, ruled 2026-09-21, the same day
   this was built. A rule that fires once per age fires once per two hundred generations of
   herders, which is not a demographic model of anything. The cadence argument that made
   per-age look attractive was written when an age was a century.

What is given up: a clan's descent is not legible across ages, and no band has a
grandchild.

## What was built

The trigger is the card's own: a band's head count against the forage its round actually
carries, not a flat probability.

- `round_forage(band, cells)` — mean forage over the cells the round's camps sit on. The
  round, not the start cell: the route pass picks the best ground in reach, so a routed
  herding round measures 0.32–0.57 against the wanderer gate's 0.07 floor at the start
  cell. The two are not the same quantity.
- `round_capacity(band, pol, forage)` — head count the round carries, read off the
  classification's authored `size` band with the round's forage picking a point on it.
  **Dimensionless on purpose.** Head per square kilometre reads the raster rather than the
  land: a cell is 52 km² at raster 17 against 13 km² at raster 33, so the same clan on the
  same ground would outgrow it at one resolution and not the other — the same failure the
  placement rate avoids by scaling clearance instead of skipping cells.
- `apply_fission(...)` at the tail of `add_nomad_routes`. It runs there rather than in a
  new pass because `add_nomad_routes` is already wired at every site that wants routes —
  stage 16, the age-advance tail, `nomad_request`, and the monthly `nomad_routes` cadence
  of a time advance — so no edit to `terrain_time_schedule` (another session's file) was
  needed for the tick path to stay consistent.

A daughter is seated on a camp of the parent's round, summer pasture first. It must pass
its classification's **real gate** at that cell — `GATES[...]` is called, not restated — so
every precondition the classification tests assert of a placed band holds of a daughter
too. If its inherited camp cannot support a round of its own it is refused rather than
recorded as a stranded child: a segment with nowhere to winter has not split.

`nomads.json` gained a `fission` section and moved to version 2. `rich_forage = 0.55` is
calibrated, not derived, and the number is stated with its measurement: across six nomad
populations sampled on one terrain it seats a child for 27% of routed herders, against 9%
at 0.50 and 45% at 0.60.

Idempotence is a requirement, not a nicety, because the route pass re-runs: every child is
discarded and re-derived from the surviving parents. `nomads.counts` is recomputed from the
band set for the same reason — three callers add to it and a tally that is only incremented
cannot survive a pass that removes anybody.

## Decisions taken inside the implementation

- **The fission leg is carried by the child and its `to` names the parent's start camp.**
  It is the only leg whose `to` names a camp of a different band, which is what makes it a
  join between two rounds rather than a leg inside one. It carries no day window — the
  split happened once, not every year — and is excluded from `round_length_m`.
- **A child is not written into `rolls`.** `rolls` answers what the point process
  considered at a candidate point; a child was never considered. The invariant a consumer
  can hold becomes "every band names a roll or names a parent that does", and both
  `Sim/tests/test_terrain_nomads.py` and `tests/test_world_schema_conformance.py` were
  updated to assert that instead.
- **A fissioned parent keeps its head count.** The route pass has no demographic model, and
  rewriting a placed band's `size` from there would make the authored size band a fiction
  — and would not be idempotent, since the pre-split size is not recoverable.
- **The band block stayed at version 1 and the route pass moved to 2.** No band field is
  new and no enum gained a member, so a v1 document still validates field for field. What
  changed is the *occupancy* of slots that were already declared, and the routes v1
  `limits` sentence promised that occupancy explicitly, so that is the version that moved.

## Proof

`Sim/tests/test_terrain_nomads.py`, in `NomadRouteTests`:

- `test_a_clan_that_outgrows_its_round_splits_onto_ground_it_already_held` — before:
  `AssertionError: [] is not true : no band names a parent: lineage fission never ran`.
- `test_the_trigger_is_head_count_against_the_round_and_nothing_else` — two populations
  built one head above and one head below each band's own computed capacity, so a trigger
  that fired for everybody and one that fired for nobody both go red.
- `test_fission_is_bounded_because_a_child_never_splits_again`,
  `test_rebuilding_the_routes_does_not_breed_more_bands`,
  `test_the_counts_include_the_children`,
  `test_every_band_traces_back_to_a_roll_or_to_a_parent` — guards.

Every one was ablated and watched go red; see the delivery report.

## Files

`Sim/icarus_sim/terrain_nomad_routes.py`, `Sim/icarus_sim/terrain_nomads.py` (policy
validation only), `Sim/icarus_sim/nomads.json`, `Contracts/schemas/nomads.schema.json`,
`docs/nomads.md`, `docs/conformance/nomads.md`, `docs/conformance/version-bindings.json`,
`Sim/tests/test_terrain_nomads.py`, `tests/test_world_schema_conformance.py`.

Changes generated output, so `Fixtures/sample-world-v1.json` is stale and the orchestrator
rebuilds it.
