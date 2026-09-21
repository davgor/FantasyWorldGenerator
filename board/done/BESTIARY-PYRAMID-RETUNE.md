# BESTIARY-PYRAMID-RETUNE - the placed pyramid is the rate clipped by the raster

**Delivered 2026-09-21.** The premise below is rewritten: the defect this card was opened
for is not the one that was there. The stated one - "204 tier-1 against 301 tier-5" - does
not reproduce, and neither does the reconciliation's flat "199 / 237 / 88 / 204 / 199". The
whole of the original diagnosis is superseded by the section **What was actually wrong**.
The original text is kept below it, struck through in substance rather than deleted, because
the measured two-arm experiment in it is still the evidence that the dominance rule is a
cause.

> **RE-MEASURED 2026-09-21 — the stated defect no longer reproduces; the ticket still stands.**
> This card records “204 tier-1 against 301 tier-5”. On the current generator (seed 42, **size 33**)
> placement by tier is **199 / 237 / 88 / 204 / 199**: tier 1 and tier 5 are exactly equal, so the
> *inversion* is gone. What is there instead is a flat distribution with tier 3 anomalously low at 88 —
> not a pyramid either. The test asserts tier 1 **>** tier 5 and still fails at 199 vs 199. **Rewrite the
> numbers and the diagnosis before working this.** [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

## What was actually wrong

Re-measured 2026-09-21 by running the placement pass directly, every arm on the same world
with only the refusal test changed. Seed 42, phase 13, at the default width and at sqrt(3)
times it, which is the pair `test_pyramid_and_overlap` itself uses.

**The rate is a perfect pyramid and always was.** Monster draws by tier, before anything
refuses them:

    reference world   6907 / 3342 / 1657 /  799 /  369
    3x the surface   20382 / 9969 / 5129 / 2524 / 1225

Each tier is half the one below it, which is exactly `monster_tier_falloff` at 2.0, and the
total tracks area to 1.000. The budget, the renormalisation and the discretisation are all
correct. Nothing in `tier_density` needed retuning, so this card's own title was wrong.

**93% of those draws were refused, and the refusal rate is itself the inversion.** On the
reference world, by tier: 96.9% / 92.9% / 94.1% / 73.8% / 49.3%. What survives is
215 / 236 / 97 / 209 / 187 - flat - and on the wide world 208 / 233 / 110 / 238 / 284, which
is inverted. **The same code reads as a pyramid at one width and as an inversion at three
times it**, which is why this card, the reconciliation and the test each measured different
numbers and each of them was right.

**The mechanism is the raster, not the ecology.** Every site in a cell is stamped with that
cell's own `direction`, so two sites in one cell sit at distance 0 from each other. The cell
pitch is 3.6 km at the reference width and 6.2 km at three times it; the widest territory in
the monster catalogue is 1.05 km and the tier-one mean is 67 m. **No species' reach is as
wide as the raster pitch at any width this product ships**, so the spacing test never
compares two distinct positions - it only ever compares a cell against itself. It degenerates
into "one lair per dominance class per cell", and a tier's placed count is capped by the
cells it reaches:

| tier | cells reached | drawn (3x world) | placed |
|---|---|---|---|
| 1 | 369 | 20382 | 208 |
| 2 | 376 | 9969 | 233 |
| 3 | 163 | 5129 | 110 |
| 4 | 335 | 2524 | 238 |
| 5 | 357 | 1225 | 284 |

Tripling the area triples the draws and leaves the cell count identical, so the saturated low
tiers do not move at all (215 to 208, 236 to 233) while the unsaturated top tiers grow with
the ground (187 to 284). That is the inversion, and it is a raster artifact.

**Tier 3 at 88/97/110 is a catalogue hole, and a precisely locatable one.** Tier three is
eligible in 152 cells against 326-366 for every other tier, and the whole of the difference
is the sea. Marine cells reached by tier, reference world: 260 / 254 / **37** / 230 / 254.
The catalogue has four marine tier-three monsters and every one is gated on something rare -
`brine-revenants` and `kelp-wardens` on a ley school, `reef-stalkers` and
`reefback-leviathans` on `reef`, which is 0.0 across almost the whole ocean. **Tier three is
the only tier with no open-ocean monster.** Every other tier has at least one species whose
score rests on `fishing_productivity` alone and so reaches 222-230 sea cells; tier three has
none. On a world three quarters water that alone halves the tier.

Structural rather than one seed's luck - tier-three marine reach against its neighbours':

| seed / size | tier 3 | tiers 1 / 2 / 4 / 5 |
|---|---|---|
| 42 / 33 | 37 | 260 / 254 / 230 / 254 |
| 7 / 33 | 39 | 229 / 225 / 203 / 225 |
| 1234 / 33 | 45 | 247 / 240 / 214 / 240 |
| 42 / 65 | 65 | 517 / 489 / 316 / 489 |
| 99 / 17 | 26 | 104 / 104 /  98 / 104 |

## What was delivered

1. **The monster dominance rule is `==` rather than `>=`.** `terrain_nests.add_monsters`
   refused a candidate when an already-placed lair had a tier greater than *or equal to* it,
   while the prose in three places said a greater monster "tolerates a lesser" and that "a
   dragon's range may contain a goblin camp". The code delivered that only when the goblin
   was drawn first. Fixing the contradiction moves the histogram in the pyramid's direction
   and leaves tier five **exactly unmoved** - 187 to 187 at the reference width, 284 to 284
   at three times it - which is the falsification this card itself named.
2. **`reefback-leviathans` lost its `reef` weight.** Its own published description is "slow
   marine giants **carry** living reefs", so requiring it to find one was the bug and not the
   flavour. That one field takes tier three's marine reach from 37 to 230 and puts it level
   with tier four at every seed and size sampled.
3. **Both blocks publish `saturation`**, one row per tier: `cells`, `drawn`, `placed`,
   `refused`. The pyramid is exact in `drawn` and clipped in `placed`, and until now a reader
   had no way to tell which one a flat histogram described. `wildlife` 1 to 2,
   `beast_nests` 2 to 3.

Placed counts after, monsters:

    reference   352 / 358 / 305 / 277 / 200   (was 215 / 236 /  97 / 209 / 187)
    3x world    368 / 376 / 346 / 314 / 298   (was 208 / 233 / 110 / 238 / 284)

Tier one outnumbers tier five at both widths and the tier-three hole is gone. Animals are
byte-identical: the animal pass places the same 12,924 and 15,620 sites with the same ids as
before, because its rule was already species-scoped.

**Unasked-for, and worth knowing: the pass got four to six times cheaper.** Scoping the
refusal scan to the candidate's own bucket instead of the whole placed list cut placement
from 30.1 s to 6.5 s on the reference world and 104.8 s to 17.2 s on the wide one, and a full
phase-16 generation from 356 s to 209 s. Five sessions shared this CPU, so treat every
wall-clock figure here as an upper bound. `add_nests` did **not** get slower.

## Decided here, and reversible

**`test_pyramid_and_overlap` and `test_population_scales_with_the_ground` now assert on the
rate, not on the placed set.** Both used to assert on `sites` and both were red. After all
three fixes above, two of their assertions still cannot pass and never could at this raster:

- `spread[1]+spread[2] > 2*(spread[4]+spread[5])` needs the bottom two tiers to be more than
  twice the top two. Tiers one, two and three are all pinned at their cell ceilings of about
  370, so the left side cannot exceed roughly 750 whatever the budget says, and getting the
  right side under 375 means gutting tiers four and five - about 27 tier-five lairs on a
  reference world against the 187 there are now. `tier_density`'s own docstring already warns
  that this "empties small worlds of anything worth fearing".
- `(large/small)/area` within 0.7..1.4 on placed counts needs placement to track area. It
  cannot: the raster does not grow with circumference.

So the pyramid is asserted on `saturation.drawn`, where it is exact and seed-independent, and
the placed set keeps the assertions it *can* carry - tier one outnumbers the top tier at both
widths, no tier places more sites than it has cells, and a wider world holds strictly more,
which is what a reintroduced anchor cap would break.

**The alternative rejected: realise the point process below the cell.** Give each site a
deterministic sub-cell position so the spacing rule compares real separations, and both
original assertions pass in their original form, the pyramid is real in `sites`, and
population tracks area. It is the correct fix and it is large: 14x more monsters at the
reference width and 36x at three times it unless `monster_density` is retuned to compensate;
site ids are `nest-<species>-<node>` and would need an ordinal; `beastmove-<species>-<node>`
likewise; and every consumer that joins on `node` - `encounters`, `key_locations`,
`hero_generator`, `npc_roster`, `terrain_read_select` - is affected. That is a decision about
how full a world is, not a test fix. **If the owner would rather have the real point process
than the rate assertions, this is the card to reopen.**

## Ablation, per assertion

Each arm breaks one thing and confirms the test goes red on it. Run as a monkeypatched
rebuild of both worlds, not as an edit to the tree.

| ablation | result |
|---|---|
| restore `a['tier'] >= p['tier']` | `beast_nests` tier 1 > top tier goes **RED**, 203 vs 298 |
| restore the `reef` weight | every-monster-tier-reaches-the-ocean goes **RED**, tier 3 at 37 of 724 |
| `tier_density` made constant | drawn-is-decreasing goes **RED** on both passes |
| a fixed 400-site cap | wider-world-holds-more goes **RED**, 400 vs 400, on both passes |

Note that under the `rank` arm the reef fix is still in place and the histogram is
203 / 221 / 191 / 214 / 298 - still inverted. **Neither fix alone is sufficient**; that is
why both are here.

One assertion did **not** die under any arm: `placed <= cells` on `beast_nests`. It is an
invariant of the rule rather than a guard on the fix, and it is there to name the ceiling so
the next reader of a flat histogram does not re-derive this card. Recorded rather than
dressed up as coverage.

## What this did not do

- It did not make the placed histogram a pyramid. It cannot at this raster; see above.
- It did not touch `test_the_book_is_a_pyramid_too`, which asserts the *catalogue* is widest
  at tier one. It passes, and it is worth noting that the monster catalogue is 77 / 86 / 90 /
  66 / 50 - a bulge at tier three, not a pyramid. That is a separate, smaller finding.
- It did not measure `sulphur-eels` and `cinder-jackals`, which fail the same authoring check
  as `brimstone-bats` on 3 of 5 and 2 of 5 sampled worlds respectively. Not carded, not
  caught by the seed-42 test. Worth a card.
- It did not correct `docs/terrain-world-layers.md:183`, which still states the old rank rule
  and is now wrong. That file is fenced to another session and provenance-pinned.
- `Fixtures/sample-world-v1.json` is stale: every monster site moved.

## Original text, superseded

## Observed behavior

`Sim/tests/test_terrain_nests.py::test_pyramid_and_overlap` asserts that tier 1 outnumbers
tier 5 across **placed** sites. It is inverted, and was failing before any of tonight's
work: **204 tier-1 against 301 tier-5** on `beast_nests`.

The cause is in the placement rule rather than the catalogue. A monster is excluded by an
equal-or-greater-tier monster within range, so a tier-1 lair is refused by *everything*
while a tier-5 lair is refused only by other tier-5s. The rank rule inverts the pyramid it
is meant to produce.

## Why this card exists now

The catalogue grew three times in one evening, and the **nomad roster pass deliberately
widened the inversion**: it added 11 monsters weighted to the middle and top - one tier-1,
one tier-2, four tier-3, four tier-4, one tier-5.

Catalogue tier distribution moved:

    before  [(1, 250), (2, 147), (3, 136), (4, 81), (5, 49)]
    after   [(1, 253), (2, 151), (3, 141), (4, 85), (5, 50)]

That direction was stated up front rather than left to be discovered, but it means the
assertion is now measuring a target that moved for known reasons. A permanently red test is
one nobody reads, and this one guards a real property.

`test_population_scales_with_the_ground` is in the same position - failing at 13751/14849
over area 3.0, on `wildlife`, which the roster also touched.

## Proposed mechanism

Either fix the dominance rule so lower tiers are not refused by everything above them, or
re-express the assertion against expected counts derived from `tier_density` rather than raw
placed totals. The first is the real fix; the second makes the test meaningful meanwhile.

## Measured, 2026-09-20: the dominance rule is a cause, and it is not the only one

The card proposes fixing the dominance rule "so lower tiers are not refused by everything
above them". That proposal is now measured rather than reasoned, on one seed-42 size-33
phase-13 world, with only the monster pass re-run and every other input held fixed.

`add_monsters` refuses a candidate when `a['tier'] >= p['tier']` within reach, so a tier-one
lair is refused by every lair already placed while a tier-five lair is refused only by other
tier fives. Narrowing that to `a['tier'] == p['tier']`:

    tier            1    2    3    4    5   total
    as shipped    177  210   85  209  188     869
    equal-tier    336  342  120  265  188    1251

Tier one nearly doubles and tier five does not move at all, which is the signature of the
suppression the card predicted. **But the pyramid is still not monotone afterwards** - tier
three sits at 120 against tier four's 265 - so `spread[1] > spread[max]` passes and
`spread[1]+spread[2] > 2*(spread[4]+spread[5])` still fails at 678 against 906. There is a
second cause in the catalogue's own tier composition, and a dominance change alone will not
turn this test green.

Recorded rather than applied. The rule the change would overturn is stated twice in
`terrain_nests.add_monsters` as deliberate design - "a monster is excluded only by an equal or
greater monster" - and its own stated consequence, "so a dragon's range may contain a goblin
camp", is the opposite of what the code does. That contradiction is worth resolving on
purpose, by whoever owns monster ecology, and not as a side effect of making a test green.

**Falsification:** re-run the two-arm comparison at another seed and raster. If tier five moves
at all between the arms, the suppression reading is wrong and something else is in play.

## Not owned

Neither test belongs to the nomads work. This card exists so the failure stays attributable
rather than absorbed.
