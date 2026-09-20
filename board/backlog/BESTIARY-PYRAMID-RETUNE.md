# BESTIARY-PYRAMID-RETUNE - the tier pyramid is inverted and its test measures a moved target

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
