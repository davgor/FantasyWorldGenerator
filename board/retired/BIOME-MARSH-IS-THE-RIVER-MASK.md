# BIOME-MARSH-IS-THE-RIVER-MASK — marsh is reachable in every seed and is the wrong phenomenon

> **RETIRED 2026-09-21 — removed from the backlog by owner instruction, not finished and not refused.**
> This card was **measured and never applied**. The finding stands and reproduces. But it was not
> declined by any ruling: the card's own fix section is headed *“Proposed fix — NOT to be applied
> without a ruling”*, and **no such ruling was ever made**. It is unapplied and unruled, which is not
> the same as refused. If anyone later wants the marsh margin derived from circumference, the decision
> is still open and must be asked for, not inferred from this retirement.
> Nothing here is a blocker. Read it for what it measured, not for what it instructs.

Owner: none. State: measured, **not applied.** Raised by the biome-reachability lane under user
ruling 3.0, 2026-09-20, and re-measured after the wave-1 river-threshold change landed.

Marsh does **not** fail ruling 3.0. `13 marsh` appears in 232 of 232 seeds at the default raster.
It is on the board because what it publishes is not a wetland margin. It is the river mask with
three extra predicates applied, and it has been that since the world grew to 200 km.

This is a member of the class recorded in
[SCALE-METRE-CONSTANTS-COLLAPSE](../backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md) — a constant written in
absolute metres against the 11.15 km reference world, still in the code at 200 km, silently no
longer spanning anything. That card already lists this constant as its sharpest open member; this
card is the measurement behind that row, plus the cells.

## Observed behavior

The wetland margin is a hard cutoff inside a Dijkstra relaxation:

```
            if candidate<=180 and candidate<distance[j]:
```

`Sim/icarus_sim/terrain_biomes.py:32`. A hard cutoff does not degrade as the world grows. It
either admits a neighbour or it admits nothing.

On the live 200 km world the sphere grid's shortest edge is more than thirteen times the margin
at the default raster. Measured by importing `sphere_grid` at the effective physical radius
31830.99 m and counting undirected edges (the graph stores each edge twice, so the directed
counts recorded elsewhere on the board are double these):

| raster | edges | shortest edge | edges within 180 m |
|---|---|---|---|
| 17 | 944 | 2423.6 m | **0** |
| 33 | 3936 | 611.6 m | **0** |
| 65 | 16064 | 153.3 m | 128 |
| 129 | 64896 | 38.3 m | 1024 |

The 128 admitted edges at raster 65 and the 1024 at 129 are polar-convergence edges, where the
longitude columns crowd together and nothing lives.

So the relaxation relaxes nothing. `distance[i]` is `0` on a water or river cell and `inf`
everywhere else, the published `wetland` layer is `>= 0` only on the seed nodes themselves, and
marsh can only be assigned to a cell that is **itself** water or river.

Confirmed on generated worlds at phase 10, every marsh cell cross-tabulated against `rain_river`:

| seed | raster | marsh cells | of which river cells |
|---|---|---|---|
| 42 | 17 | 11 | **11** |
| 0 | 17 | 9 | **9** |
| 9 | 17 | 20 | **20** |
| 0 | 33 | 33 | **33** |
| 0 | 65 | 31 | **31** |

Five for five, including the two rasters where some edges do fall inside the margin. The "near
water" case the predicate was written for does not occur at any raster the generator ships.

## Why it matters

The published biome says wetland margin. What it means is "river cell that is also wet, unfrozen
and gently sloping". Three consumers read it as the former:

- the `Wetland margin` feature marker, selected from `biome == 13` in `add_terrain_labels`;
- the world's own published method string, which promises land "within 180 m and 4 m above
  mapped water" (`Sim/icarus_sim/terrain_biomes.py:98`);
- every asset and fauna decision keyed on biome 13 — the production catalogue carries 34 rows
  against it, per the histogram recorded in
  [BIOME-TUNDRA-SNOW-UNREACHABLE](../done/BIOME-TUNDRA-SNOW-UNREACHABLE.md).

A fen sits *beside* water. Nothing in this world does.

## Mechanism

180 m was authored against the 11.15 km reference world, where the same `sphere_grid` at raster
17 has a median edge of 473.5 m, a shortest edge of 135.1 m, and **32 of 944** edges inside the
margin — so the margin reached roughly a third of a typical cell and admitted a real ring of
neighbours, which is what a margin means on a raster. At raster 33 the reference world had 1344
of 3936 edges inside it and at 65 it had 13760 of 16064. At 200 km the same 180 m is 2.9% of one
meridional cell step at raster 17 and admits nothing.

`wetland_access` returns two layers, and only the first is dead. The second, height above the
nearest water surface, is computed from `source[i]`, which is the cell itself whenever the
distance is zero — so `height_above_water` is `height - water_surface` on the cell, and the
`0 <= height_above_water <= 4` arm of the predicate still discriminates. The margin arm is the
one that has collapsed.

## Proposed fix — NOT to be applied without a ruling

Derive the margin once from the effective circumference through the existing
`reach_scale(circumference_m)` in `Sim/icarus_sim/terrain_scale.py:30`, and thread the single
derived value into both `wetland_access` and `marsh_suitable` so the two constants cannot drift.
At 200 km that resolves to `180 * 200000/11148.96`, about **3229 m** — roughly half a cell edge
at raster 17, which restores the "one ring of neighbours" meaning the constant was authored with.

Leave `0 <= height_above_water <= 4` alone. Four metres is a genuine vertical statement about how
high above water a fen sits. It does not scale with circumference and scaling it would be the
same error in the other direction.

## Every gate this fix crosses, listed once so nobody applies it believing it is free

1. **Seed-changing.** It moves marsh onto a large number of cells that are not marsh today, which
   feeds settlement siting, `farming_potential` and the nest habitat fields. Permitted under
   [023-world-compatibility-policy](../../docs/decisions/023-world-compatibility-policy.md), but
   it invalidates every saved world and every recorded biome census on the board.
2. **Provenance-pinned file.** `Sim/icarus_sim/terrain_biomes.py` is pinned with status
   `modified`; a byte change needs an appended revision row and a new `destination_sha256`, or
   `tools/verify_provenance.py` goes red.
3. **Native port required in the same change.** `Core/biomes.cpp` mirrors all three sites: the
   comment at `Core/biomes.cpp:12`, the relaxation at `Core/biomes.cpp:32`, and the predicate at
   `Core/biomes.cpp:78`. That last anchor is a **partial line** — it continues on line 79 with
   the `height_above_water` arm — so a patch must take both lines or it will silently match
   nothing. Without the port the marsh cells diverge between the two implementations.
4. **The reachability witnesses move.** `Sim/tests/test_biome_reachability.py` records realised
   biome sets per `(seed, size)`; changing the marsh rule changes them and the table must be
   re-measured, not weakened.

## Do not confuse this with the other water BFS

`freshwater_distance` is a different Dijkstra living in `terrain_settlements.py` and
`terrain_humans.py`, with a different seed set and no code shared with `wetland_access`. Its own
scale defect is a separate row on
[SCALE-METRE-CONSTANTS-COLLAPSE](../backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md) (the 400-650 m
`water_reach` profile constants). Fixing one does not fix the other, and a change that touches
both should say so explicitly.

## Not owned

Pre-existing. Surfaced by the biome-reachability sweep of 2026-09-20. Class parent:
[SCALE-METRE-CONSTANTS-COLLAPSE](../backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md). Sibling finding from the
same sweep: [BIOME-EXPOSED-ROCK-NEEDS-RELIEF](BIOME-EXPOSED-ROCK-NEEDS-RELIEF.md). General form:
[PRODUCT-REACHABILITY-REPORT](../done/PRODUCT-REACHABILITY-REPORT.md) — a biome can be reachable in every
seed and still not be the thing its name claims, which is a reachability report the current
instrument cannot produce.
