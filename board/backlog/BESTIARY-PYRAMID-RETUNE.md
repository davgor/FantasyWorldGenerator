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

## Not owned

Neither test belongs to the nomads work. This card exists so the failure stays attributable
rather than absorbed.
