# BESTIARY-NOBODY-HAS-TESTED-ABOVE-THE-CROSSING — every nest measurement we have is from one side of a boundary

Filed 2026-09-21 from two independent measurements that agree with each other and that
**both stop short of the point where they would stop agreeing**.

> **2026-09-21, later the same day: the premise is measured wrong, and most of what this
> card asks for is answered.** The crossing is not at size 192 and nothing here is below
> it. Cell pitch is not one number: the grid is lat/lon, so the zonal pitch collapses
> towards the poles by `cos(lat)` and the ring beside a pole is about `pi/(n-1)` as tight
> as the equator — 611.6 m at size 33 against a 6.25 km equatorial pitch, 2.4 m at size 513
> against 390.6 m. The `2*pi*r/(n-1)` table below is the equatorial pitch only.
>
> Counted by replaying placement and asking of each refusal whether its blocker was in the
> candidate's own cell (seed 42, phase 12, 200 km): **0** cross-cell refusals at size 33,
> **50 animal and 426 monster** at size 65, **497 and 479** at size 129. The second regime
> starts between 33 and 65, and two of the three measurements this card calls
> "below the crossing" are above it.
>
> The three predicted consequences did not happen the predicted way either:
>
> | size | animal draws | placed | refused | monster draws | placed | refused |
> |---|---|---|---|---|---|---|
> | 33 | 76,107 | 12,924 | 63,183 (83%) | 13,074 | 1,494 | 11,580 (89%) |
> | 65 | 76,066 | 28,755 | 47,311 (62%) | 13,066 | 3,289 | 9,777 (75%) |
> | 129 | 76,092 | 39,454 | 36,638 (48%) | 13,075 | 5,959 | 7,116 (54%) |
>
> - **Counts do not jump.** Draws are *constant* across the raster — the budget is an
>   integral over a planet the raster does not change. Only the share that finds room
>   moves, and it moves smoothly.
> - **The refusal rate was never a plateau.** 83% → 62% → 48%, falling monotonically, and
>   the fall is driven by cell count rather than by cross-cell comparison: cross-cell is
>   still under 7% of monster refusals at 129 while the rate fell 35 points.
> - **The per-nest column did bend**, but for an unrelated reason — the pass was indexed
>   and is now 6–13x cheaper at byte-identical output, so per-nest cost fell by an order of
>   magnitude at a fixed placed count. See `docs/performance.md`.
>
> **What is still open, and it is the part worth keeping:** everything above size 129.
> Nobody has generated 257 or above, the `docs/performance.md` extrapolation to 513 is from
> three points, and whether the refusal curve keeps falling or flattens is unmeasured. The
> proposed 129/257 probe is still the right probe; only its stated reason changes. Related:
> [NEST-SAME-CELL-CLAIM-IS-FALSE](NEST-SAME-CELL-CLAIM-IS-FALSE.md).

## The claim

Monster placement behaves one way while the raster's cell pitch is wider than the widest
species territory, and a different way once it is narrower. **Every figure anyone has taken
is from the first regime.** Nobody has generated a world in the second.

## The two measurements, and why neither settles it

**Surface area varied at a fixed raster** ([BESTIARY-PYRAMID-RETUNE](../done/BESTIARY-PYRAMID-RETUNE.md)).
Every site in a cell carries that cell's own `direction`, so intra-cell distance is identically
zero. Cell pitch is 3.6–6.2 km; the widest monster territory is 1.05 km and the tier-1 mean is
67 m. **No species' reach is as wide as the raster pitch at any shipped width**, so the spacing
rule only ever compares a cell against itself — one lair per dominance class per cell. 93% of
draws are refused. Tripling the area triples the draws and leaves the cells identical: saturated
low tiers hold (215 → 208), unsaturated top tiers grow (187 → 284). **Placed count is capped by
cells reached, not by budget.**

**Raster varied at a fixed planet** (the performance session's cost ladder). `add_nests` cost per
placed nest is flat across a 16× range in count:

| size | nests | add_nests | per nest | nests/cell |
|---|---|---|---|---|
| 17 | 271 | 35.7 s | 0.132 s | 0.94 |
| 33 | 957 | 128.4 s | 0.134 s | 0.88 |
| 65 | 2,215 | 280.3 s | 0.127 s | 0.52 |
| 128 | 4,379 | 505.4 s | 0.115 s | 0.27 |

These are consistent and neither settles the other — they vary different axes. The ladder's
author states explicitly that a flat per-nest column shows cost scales **with nests placed**, not
that the work **is** per nest, and that it would diverge from the per-pair model the moment cell
pitch drops below a species' territory width.

## Where the crossing is — size 192, measured

Read from `spacing_m` on a phase-1 generation at each size, rather than computed from
`2*pi*r/(n-1)`:

| size | 17 | 33 | 65 | 128 | **192** | 257 |
|---|---|---|---|---|---|---|
| cell pitch | 12.500 km | 6.250 km | 3.125 km | 1.575 km | **1.047 km** | 0.781 km |

Against the widest monster territory at **1.05 km**, **size 192 is the first size where pitch
falls below it**. Not "somewhere near 200".

**1.047 against 1.05 is a 0.3% margin, so treat 192 as inside the transition rather than safely
below it.** The first size that is unambiguously past the crossing is 257. A probe that tests only
192 risks landing on the boundary and measuring neither regime cleanly — which is the failure this
card exists to name, repeated one level down.

The 3.6–6.2 km pitch quoted by the pyramid card corresponds to sizes 33–65, which is where that
measurement was taken.

**Nothing either party ran tests that crossing**, and both said so unprompted rather than
extrapolating through it.

## What should change above it, and why it matters

Once pitch is narrower than a territory, the spacing rule starts comparing *different* cells for
the first time. The one-lair-per-class-per-cell ceiling lifts, so placed count stops being bounded
by cells reached and starts being bounded by the budget the intensity actually asks for. Three
things follow, none of them verified:

- **Counts may jump rather than scale.** The refusal rate should fall off its 93% plateau.
- **The flat per-nest column should bend**, because cross-cell comparison is the per-*pair* work
  the pyramid card measured, and it has never been exercised.
- **The tier histogram may change shape again** — the same code already reads as a pyramid at one
  width and an inversion at three times it, entirely because of this ceiling.

## Proposed mechanism

Generate at a size either side of the crossing — 129 and 257 are the natural pair, and the
age-advance grid ceiling is 1025 so both are legal — and report, at each: refusal rate by tier,
placed count by tier, `add_nests` per placed nest, and cell pitch against the widest territory.
Do not report wall-clock alone: a faster pass that places fewer nests and a faster pass that
places more are different results, and only the per-nest column plus the placed count separates
them. The pyramid card's own change is the worked example — 58% more monsters at roughly a fifth
of the scan time.

## Dependencies and unresolved decisions

**This is a measurement card, not a fix.** Nothing here says the behaviour above the crossing is
wrong. It says no one has looked, and that two well-run investigations both stopped at the edge
without claiming to have crossed it.

A size-257 generation is expensive and the machine has been carrying five sessions; take these on
a verified-quiet box and state seed, size and machine per repo rule. Related:
[SDET-CEILING-SENTINELS](../done/SDET-CEILING-SENTINELS.md) on sampling a band that never crosses
its boundary, and [SCALE-METRE-CONSTANTS-COLLAPSE](SCALE-METRE-CONSTANTS-COLLAPSE.md), where a
threshold that degrades as the raster refines is already the subject.
