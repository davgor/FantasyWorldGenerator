# NEST-SAME-CELL-CLAIM-IS-FALSE — the territory test does compare a cell against others

Owner: none. State: backlog, unowned. Raised by the nest-placement performance pass,
2026-09-21, while looking for a fast path the claim appeared to license.

The claim is still in `docs/conformance/creature-placement.md` and was in
`terrain_nests.py` until this pass rewrote the paragraph. It reads:

> Placement resolves at the raster cell: every site in a cell carries that cell's own
> direction, and no species' territory is as wide as the raster pitch at any width this
> product ships, so the spacing test only ever compares a cell against itself.

The second clause is false, and so is the conclusion drawn from it. The optimisation
landed in this pass does not depend on the claim, so nothing is currently broken; the
card exists because the claim is load-bearing prose that invites a wrong change.

## Why it is false

"The raster pitch" is one number in the sentence and two on the grid. `terrain_globe.
direction` lays points out on a lat/lon sphere grid — row `z` sits at latitude
`pi/2 - pi*z/(n-1)`, and the `n-1` points of that row are spread around a circle of
radius `R*cos(lat)`. The meridional pitch is uniform. The **zonal** pitch collapses
towards the poles, by `cos(lat)`, which at the ring next to the pole is a factor of
about `pi/(n-1)`.

Measured (`terrain_erosion.sphere_grid`, smallest non-zero neighbour gap anywhere in the
grid, against the equatorial pitch the sentence means):

| circumference | size | min neighbour gap | equatorial pitch |
|---|---|---|---|
| 200 km | 33 | 611.6 m | 6,250.0 m |
| 200 km | 129 | 38.3 m | 1,562.5 m |
| 200 km | 513 | **2.4 m** | 390.6 m |
| 600 km | 513 | 7.2 m | 1,171.9 m |

Against that, the catalogue's `spacing_m` runs 100 m to 3,500 m, and territory is
`spacing_m * nest_spacing / 2` — 1,750 m at the default `nest_spacing`, **7,000 m** at
the 4.0 the control allows. So on every shipped width at every size from 33 up, there is
ground where a territory is wider than the gap between cells.

## What it costs today

Cross-cell refusals are ordinary, not marginal. Counted by replaying the real placement
and recording, for each refusal, whether the blocker was in the candidate's own cell.
Seed 42, phase 12 world, `nest_spacing` at its 1.0 default:

| world | animal refusals | cross-cell | monster refusals | cross-cell |
|---|---|---|---|---|
| size 33, 200 km | 63,183 | 0 | 11,580 | 0 |
| size 33, 346 km | 212,657 | 0 | 37,522 | 0 |
| size 65, 200 km | 47,311 | **50** | 9,777 | **426** |

426 of 9,777 is 4.4% of monster refusals. A same-cell-only test would have placed those
476 sites, so the claim is not merely imprecise — acting on it changes worlds.

The two zero rows are the other half of the finding and are the reason for the missing
test below: **those are exactly the two worlds `Sim/tests/test_terrain_nests.py` builds.**
At size 33 an animal cannot manage a cross-cell refusal at all — its widest reach is 550 m
against a 611.6 m smallest neighbour gap, so it is geometrically impossible — and a
monster, whose 1,750 m reach makes it possible, did not happen to place in a tight ring on
either world. Verified rather than assumed: `_blocked` was sabotaged to a same-cell-only
rule and `test_animals_are_territorial_only_within_a_species` and
`test_greater_monsters_hold_ground_against_equals_only` both still passed.

## Why this is worth a card rather than a comment

The sentence is exactly the justification a reader needs to replace the territory scan
with a `node in set` test, which is O(1) against the neighbourhood scan that is correct.
It is stated twice, in the module that would be edited and in the conformance record that
would be consulted, and it is stated as a property of the product ("at any width this
product ships") rather than as a measurement anybody took. The performance pass reached
for that fast path first and only found the gap by measuring the grid.

## What the pass that raised this already did

1. `terrain_nests._blocked` carries the correct bound — a candidate can only be blocked
   from within `max(reach, widest)/pitch` grid ROWS, because latitude difference is a
   lower bound on great-circle angle whatever the longitudes do.
2. The module header and `docs/conformance/creature-placement.md` both state that instead
   of the false claim, and both point here.
3. `TerritoryAcrossCellsTests` in `Sim/tests/test_terrain_nests.py` units the rule
   directly: a neighbour in a tight polar ring holds ground, a site past the row band does
   not, and the band is taken over the widest territory in the bucket rather than the
   candidate's own. Two of the three go red against the same-cell-only rule.

## What is left

1. Decide whether the surviving consequence — a tier holds at most one lair per cell, so a
   tier whose rate exceeds the cells it reaches is pinned there — should still be stated
   as a raster ceiling. It is true and it is the real finding behind `saturation`; only
   the reasoning offered for it was wrong, and the record now says so in two paragraphs
   where one would do.
2. Pin cross-cell territory on a generated world, not only as a unit. The unit tests
   above assert the predicate; nothing asserts that a world ever exercises it, and the
   only worlds the suite builds do not. That needs a size 65 world in the suite, which
   costs about thirty seconds of nest placement, so it is a judgement about test budget
   rather than an oversight.

Deliberately not on that list: `Core/nests.cpp` carries the same scan and, separately,
still implements the retired `other.tier >= profile.tier` monster rule under a comment
describing the current one. Decision 027 rules that current native divergence is not a
defect and is not tracked, so it is noted here and nowhere else.

## Does not establish

- That any shipped world is wrong. The scan has always compared real pairs; only the prose
  describing it is false, and the pass that raised this kept output byte-identical at
  sizes 33, 65 and 129.
- How the cross-cell refusal count behaves above size 129. It was counted at 33 and 65
  only. It should rise with the raster, because the polar rings tighten while territory
  does not move, but that is an expectation and not a measurement.
- Whether `nest_spacing` near its 4.0 maximum is a configuration anybody uses. If it is,
  the cross-cell share is much larger than the 4.4% measured at the default and the
  `_blocked` row band widens to tens of rows, which is a cost nobody has measured.
