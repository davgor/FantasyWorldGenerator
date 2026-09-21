# BESTIARY-BIODIVERSITY-SPIKE — how much of the bestiary reaches a world, and why the apex tier does not

Owner: none. State: backlog, unowned. Filed 2026-09-21 from the nest-placement performance
pass, which left its instrumentation pointed at the diagnostics blocks once it was done.

**This is a spike, not a fix.** Nothing below says the behaviour is wrong. It says the
bestiary delivers unevenly, names the two places it delivers worst, measures how far the
obvious explanation goes, and marks the product question that has to be answered before
anyone changes a rule.

## What reaches a world

`reachability` and `diagnostics` on the two blocks, seed 42, size 65, phase 12 plus
`add_nests`, 200 km world. Then three more seeds at the same size and raster.

| seed | animals placed / 311 | monsters placed / 369 |
|---|---|---|
| 42 | 287 (92.3 %) | 264 (71.5 %) |
| 7 | 289 (92.9 %) | 228 (61.8 %) |
| 73 | 290 (93.2 %) | 267 (72.4 %) |
| 1234 | 292 (93.9 %) | 273 (74.0 %) |

**The animal half is healthy and the monster half is not.** Animals land 92–94 % of the
book on every seed and no animal is unreachable in principle. Monsters land 62–74 %, so
between 96 and 141 authored creatures are in no world at all, and the count swings by 45
species across four seeds of the same size and planet.

Shannon evenness on the animal sites is 0.880 at size 33 and 0.893 at size 129, both seed
42 — the placed animals are close to equally common, so the 92 % is genuine breadth and not
one species carrying it. **Evenness was not measured on the other three seeds**, so read it
as one world's shape rather than a property of the pass.

## Monster coverage is a function of the grid, not of the planet

Same seed, same 200 km planet, only the sampling raster changes (seed 42):

| size | cells | monsters placed / 369 |
|---|---|---|
| 33 | 1 089 | 167 (45 %) |
| 65 | 4 225 | 264 (72 %) |
| 129 | 16 641 | 279 (76 %) |

Monster diversity **nearly doubles between size 33 and 129 on an identical world**. Grid
size is documented as a detail control; here it is a content control. This is
[PERF-CITY-COUNT-TRACKS-RASTER](PERF-CITY-COUNT-TRACKS-RASTER.md) in another block, and it
has the same consequence: two people generating "the same world" at different rasters get
different bestiaries.

The mechanism is known and is not in doubt — a species holds at most one site per raster
cell, so more cells is more room. Draws are constant across the raster (76.1 k animal and
13.07 k monster at every size measured); only the share that finds room moves.

## Coverage falls monotonically with danger tier, and the apex tier is the floor

Monster species placed / authored, per tier:

| tier | authored | seed 42 | seed 7 | seed 73 | seed 1234 | worst |
|---|---|---|---|---|---|---|
| 1 | 77 | 59 | 55 | 62 | 63 | 71 % |
| 2 | 86 | 66 | 57 | 63 | 61 | 66 % |
| 3 | 90 | 61 | 51 | 61 | 69 | 57 % |
| 4 | 66 | 46 | 38 | 48 | 46 | 58 % |
| 5 | 50 | 32 | 27 | 33 | 34 | **54 %** |

All at size 65. **Between 16 and 23 of the 50 tier-5 monsters are absent from every world
tested** — the dragons, liches and titans, which is the content a player is most likely to
be pointed at. Animals show the same gradient far more weakly: tier 4 lands 15–17 of 19.

Tier 5 is also the only tier that does not reward a finer raster. Seed 42 across the
ladder: **27 / 32 / 27** at sizes 33 / 65 / 129, against tier 1's 39 / 59 / 66. It is not
merely flat — it came back *down* between 65 and 129. That is one seed and it is not
explained here; eligibility is not monotone in raster because the biome field re-resolves,
so it may be sampling rather than a mechanism.

## How far the obvious explanation goes

The obvious reading is "the missing ones are fussy". Measured at size 129, seed 42, eligible
cells per species from `diagnostics.cells`:

| tier | placed | median cells | absent | median cells |
|---|---|---|---|---|
| 1 | 66 | 334 | 11 | 3 |
| 3 | 67 | 341 | 23 | 54 |
| 5 | 27 | 404 | 23 | 32 |

**It goes most of the way.** An absent tier-5 monster has a twelfth the habitat of a placed
one. But it is not the whole story, and one control kills the simplest version of it:
**`occurrence` is identical between the two groups** — median 0.280 for placed and 0.280
for absent, over the same 0.12–0.55 range. The missing species do not ask for less. They
ask for the same share in far fewer places.

The arithmetic underneath is the part worth arguing about. The catalogue is near-flat across
tiers — 77 / 86 / 90 / 66 / 50 — while `monster_tier_falloff` is 2.0, so the budget halves
each step up. At size 129 that lands 2 659 sites on tier 1 and 316 on tier 5: **34.5 sites
per authored tier-1 species against 6.3 per authored tier-5 species.** And they are not
spread evenly — tier 5's 316 sites go to 27 species at a median of 4 each and a maximum of
67. Coverage falling with tier is not a bug in a rule; it is what a flat catalogue on a
geometric budget must produce.

## The one natural experiment already in the data, and its confound

Animals bucket territory **by species**, so two different animals never exclude each other.
Monsters bucket **by tier**, so every one of the 50 tier-5 species holds ground against every
other. Animals land 92–94 %; monsters land 62–74 %.

That is suggestive and it is **not** evidence, because the two passes differ in three more
ways at once: base density (4.5 against 0.53), tier falloff (4.0 against 2.0), and the
`nest_fantasy` multiplier on monsters only. Any of those could carry the difference. **Do not
read the bucket rule as the cause without ablating it.**

## Twenty-five monsters can never be placed, and that is not a world property

`reachability.never_satisfiable` is 25 on every seed and every size, because it is decided
from the profile alone: these creatures `require` a ley school generation never raises. Six
of them are tier 5 — `absence-titans`, `blood-barons`, `star-spawn`, `the-long-thirst`,
`the-unwriting`, `the-watching-deep`. They have zero eligible cells in every world the
generator can build, so they are 6 of the 23 missing apex monsters and no placement change
will recover them. See `docs/hidden-schools.md`; this overlaps
[SUPER-VILLAINS](../in-progress/SUPER-VILLAINS.md), whose retiring change is the one that
would append those schools.

## The sea takes a share of the sites that its share of the catalogue does not

Size 129, seed 42: the planet is 66.4 % water by the area measure placement itself uses.
Water species are 28 % of the animal book and 15 % of the monster book, and they hold
**39.3 % and 40.3 % of all sites**.

The tell is saturation rather than abundance. At size 33 the eight most common animals are
all marine and six of them sit at **exactly 230 sites**. An identical count across six
species is the raster ceiling — one site per species per cell, every marine species having
reached every marine cell it can — not an ecology. Fewer species dividing a per-medium
budget over more ground means a higher per-cell rate, so the sea saturates while the land
does not. Related: [CONTENT-ENCOUNTERS-ARE-FISH](../done/CONTENT-ENCOUNTERS-ARE-FISH.md),
which found the same skew from the consumer end.

## What this spike should do next

In order, cheapest first. None of it is a fix and the last one is not an engineering
decision.

1. **Ablate the bucket rule.** Run the monster pass with `bucket = p['id']` — the animal
   rule — at a fixed seed and size, and report species placed per tier. This is a
   two-character change to a local function and it settles whether tier-exclusion carries
   the animal/monster gap or whether density and falloff do. Do not land it; measure it.
2. **Ablate the falloff.** Sweep `monster_tier_falloff` across its 1.5–8.0 range and report
   species placed per tier at each. If coverage is a pure function of budget share, tier 5
   coverage should track it smoothly and the catalogue shape is the thing to change, not
   the rule.
3. **Resolve the size-129 tier-5 dip** — 27 / 32 / 27 is one seed. Three more seeds at
   sizes 65 and 129 says whether it is real. Cheap: phase 12 plus `add_nests`, about 25 s
   per world at size 65.
4. **Decide what to do with the 25 unreachable profiles.** Delete them, re-author their
   `requires` onto a live school, or declare them deliberately reserved for the hidden
   schools and stop counting them as a shortfall. This is a content decision and it is
   blocked on SUPER-VILLAINS either way.
5. **Then the product question, which is the owner's:** is 54–74 % of the monster book
   reaching a world the intended yield? A bestiary authored at 369 and delivering 264 may
   be correct — variety across worlds is a feature, and a world holding every monster
   would be a zoo. But nothing currently states an intended figure, so there is no way to
   tell a healthy sample from a defect, and **the apex tier is the case where the answer
   most plausibly differs from the rest.**

## Does not establish

- **Nothing above size 129.** The raster trend is three points at one seed, and whether
  monster coverage keeps climbing, flattens or turns over above 129 is unmeasured. The
  ladder and [BESTIARY-NOBODY-HAS-TESTED-ABOVE-THE-CROSSING](BESTIARY-NOBODY-HAS-TESTED-ABOVE-THE-CROSSING.md)
  have the same gap.
- **Nothing about the cause of the animal/monster gap.** Four differences move together and
  none was ablated. The bucket rule is a hypothesis with a plausible mechanism, no more.
- **Nothing about worlds other than the 200 km default.** All figures are the small preset.
  Surface area is the one axis the pyramid is explicitly budgeted against, so a 400 or
  600 km world may read differently, and
  [BESTIARY-PYRAMID-RETUNE](../done/BESTIARY-PYRAMID-RETUNE.md) found exactly that kind of
  width-dependence before.
- **Nothing about whether absent creatures matter.** No measurement here connects a missing
  species to anything a player would notice. `encounters`, `beast_movements`,
  `key_locations` and the quest hooks all read these blocks, and how a 23-species hole in
  tier 5 propagates to them was not traced.
- **No performance claim.** The pass that raised this changed cost only; its output is
  byte-identical, so every number here describes the bestiary as it was before that work
  as well as after. See [docs/performance.md](../../docs/performance.md) and
  [NEST-SAME-CELL-CLAIM-IS-FALSE](NEST-SAME-CELL-CLAIM-IS-FALSE.md).

## Evidence

Seed 42 at sizes 33, 65 and 129 and seeds 7, 73 and 1234 at size 65; recipe 3, phase 12
worlds with `add_nests` run against them, 200 km circumference, default options. Windows 11,
24-core, 31.4 GB, CPython 3.12.10. Counts read from `reachability`, `diagnostics` and
`saturation` on the emitted blocks rather than recomputed, except the eligible-cell medians
and the marine share, which group `diagnostics.cells` and `profiles[].medium` over the same
blocks.
