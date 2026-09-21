# Generation performance

What a world costs, stage by stage, and where the cost actually is. Measured with
`tools/stage_profile.py`, which is described in
[docs/conformance/stage-profile.md](conformance/stage-profile.md).

Every figure here is **description, not invariant**. A cost changes when the code changes
and that is expected; what must not change silently is the seed, size and machine a number
was taken on, so each table carries them. Nothing in this document is a gate, and no test
asserts any of it.

```bash
python tools/stage_profile.py --size 128 --seed 42
```

## The reference measurement

Seed 42, size 128 (16 384 cells), phase 16, recipe 3. Windows 11, Intel 24-core, 31.4 GB
RAM, CPython 3.12.10, box at 2 % background load when the run started. Measured-code digest
`de592f00bfc582e7` over 30 modules.

**450.3 s (7 min 30 s) wall, peak resident 2 792 MB.**

| # | Stage | Body s | Capture s | Total s | Share | Cum | RSS MB |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Plate layout | 0.7 | 0.0 | 0.8 | 0.2 % | 0.2 % | 37 |
| 2 | Tectonic relief | 1.1 | 0.0 | 1.1 | 0.2 % | 0.4 % | 47 |
| 3 | Surface detail | 1.3 | 0.0 | 1.3 | 0.3 % | 0.7 % | 56 |
| 4 | Erosion and sediment | 1.6 | 0.0 | 1.6 | 0.4 % | 1.1 % | 84 |
| 5 | Connected water | 1.6 | 0.0 | 1.6 | 0.4 % | 1.4 % | 106 |
| 6 | Second tectonic relief | 1.2 | 0.1 | 1.3 | 0.3 % | 1.7 % | 109 |
| 7 | Valleys and gorges | 0.3 | 0.0 | 0.3 | 0.1 % | 1.8 % | 112 |
| 8 | Wind and rain | 1.0 | 0.2 | 1.2 | 0.3 % | 2.1 % | 157 |
| 9 | Leylines | 2.6 | 0.2 | 2.8 | 0.6 % | 2.7 % | 205 |
| 10 | Founding | 2.0 | 0.2 | 2.2 | 0.5 % | 3.2 % | 221 |
| 11 | Roads | 3.2 | 0.0 | 3.2 | 0.7 % | 3.9 % | 230 |
| 12 | Populated regions | 70.3 | 0.1 | **70.4** | 15.6 % | 19.5 % | 246 |
| 13 | Beasties and animals | 4.7 | 0.3 | 5.0 | 1.1 % | 20.7 % | 321 |
| 14 | Age transition 1 | 89.3 | 0.6 | **89.9** | 20.0 % | 40.6 % | 412 |
| 15 | Age transition 2 | 94.0 | 0.5 | **94.5** | 21.0 % | 61.6 % | 492 |
| 16 | Simulation complete | 169.0 | 4.1 | **173.1** | 38.4 % | 100 % | 1 060 |

Stages 1 to 11 — the entire physical world, its climate, its leylines, its cities and its
roads — are 17.4 s, 3.9 %. Snapshot capture is 6.2 s, 1.4 %. Peak resident is 2 792 MB, a
stage-16 transient that settles back to 1 060 MB.

### Four runs, three optimisations, measured one at a time

Same seed, size and machine across 2026-09-21. Each pair differs by a known set of modules,
confirmed by the subject digest rather than by reading a changelog.

| Run | Digest | Changed since previous | Total |
|---|---|---|---:|
| 01:45 | unknown (predates digests) | — | 1 244.2 s |
| 10:00 | `6c17d71d47833ef5` | `terrain_nests.py`, `terrain_beast_movement.py`, `city_planner.py` | 699.8 s |
| 11:41 | `2eb01cdc5f6307fe` | **`city_planner.py` only** | 602.3 s |
| 12:35 | `de592f00bfc582e7` | **`city_planner.py` only** | **450.3 s** |

**1 244 s → 450 s, a 64 % cut, in three steps.** The whole ladder moved with it, and by
more at the small sizes than the large:

| Size | 01:45 | now | Change | Factor |
|---:|---:|---:|---:|---:|
| 17 | 89.7 | **13.3** | −85.2 % | 6.7× |
| 33 | 281.2 | **55.5** | −80.2 % | 5.1× |
| 65 | 637.6 | **177.0** | −72.2 % | 3.6× |
| 128 | 1 244.2 | **450.3** | −63.8 % | 2.8× |

That gradient is the whole story of what is left. Every optimisation so far has cut work
that was sublinear in cells, so the gain shrinks as the world grows, and what remains is
weighted ever more heavily toward the passes that are not.

### The city planner, second pass: −83 % at identical output

| Pass | 11:41 | 12:35 | Change | Code |
|---|---:|---:|---:|---|
| **`city_planner.fill_cities`** | 166.7 | **27.7** | **−83.4 %** | **changed** |
| `terrain_society.add_world_society` | 221.2 | 213.3 | −3.5 % | same |
| `hamlet_planner.fill_hamlets` | 86.8 | 86.2 | −0.7 % | same |
| `terrain_beast_movement.add_beast_movements` | 36.4 | 34.6 | −4.7 % | same |
| `terrain_nests.add_nests` | 24.7 | 24.0 | −2.7 % | same |
| `castle_planner.fill_castles` | 17.1 | 17.0 | −0.4 % | same |
| `terrain_settlements.add_settlements` | 14.5 | 14.2 | −2.5 % | same |

Seven byte-identical passes moved between −4.7 % and −0.4 % — the tightest noise floor of
the four runs. `fill_cities` at −83 % clears it about eighteenfold.

**Identical output again, and this time it also got flatter.** Every content count matches
at all four sizes. The cut is consistent across the ladder — −74.8 %, −81.6 %, −80.6 %,
−83.4 % at 17, 33, 65 and 128 — and unlike the first city pass, the exponent moved too:
**0.45 → 0.36**. So this one is a large constant factor *and* slightly better scaling, where
the previous pass was constant-factor only.

Across the two city passes together `fill_cities` has gone 252.8 s → 27.7 s, **9.1×**, from
the largest pass in the generator to the fourth largest, with the world it produces
unchanged at every size measured.

### What the beast and monster work changed

The 01:45 → 10:00 pair. Same seed, same size, same machine:

| Stage | Before | After | Change |
|---|---:|---:|---:|
| **13 Beasties and animals** | 104.3 | **5.2** | **−95 %** |
| **14 Age transition 1** | 308.5 | **95.2** | **−69 %** |
| **15 Age transition 2** | 290.7 | **106.4** | **−63 %** |
| 12 Populated regions | 89.1 | 73.9 | −17 % |
| 16 Simulation complete | 430.1 | 401.3 | −7 % |
| 1–11 combined | 21.6 | 17.8 | −18 % |
| **Whole run** | **1 244.2** | **699.8** | **−44 %** |

One pass accounts for essentially all of it:

| Pass | Before | After | Change |
|---|---:|---:|---:|
| `terrain_nests.add_nests` | 505.4 | **26.5** | **−95 %** |
| `city_planner.fill_cities` | 274.8 | 252.8 | −8 % |
| `terrain_society.add_world_society` | 259.8 | 229.6 | −12 % |
| `hamlet_planner.fill_hamlets` | 88.4 | 87.4 | −1 % |
| `terrain_beast_movement.add_beast_movements` | 41.7 | 35.8 | −14 % |

**Read the other four rows as the noise floor, not as wins.** The box was quieter for the
second run (11 % against 21 % load), and three of those four passes are byte-identical
across it: `hamlet_planner.py`, `terrain_society.py` and `castle_planner.py` did not change,
and they moved −1 %, −12 % and −0 %. So an unchanged pass moved anywhere between −1 % and
−18 % on this pair of runs, and that band is what a real change has to clear.
`add_nests` at −95 % clears it by two orders of magnitude. The rest do not clear it at all.

**And it is the good case.** A pass can get faster by doing less, and the counts say this
one did not: nests placed went **4 379 → 6 128, up 40 %**, with `beast_movements`,
`encounters`, `npcs` and every settlement count flat. Faster *and* more world. Cost per
placed nest fell from 0.115 s to 0.0043 s, **26.7×**.

**`add_beast_movements` shows no win at this size.** That module was rewritten too
(15 662 → 23 481 bytes), and it moved −14 % with its group count flat at 11 119 → 11 184 —
inside the noise band above. On the ladder its exponent moved the wrong way, 1.66 → 1.81.
Whatever that rework achieved is not a speed-up at size 128.

## The passes that are the run

Self time, summed across every call, at size 128 on the current tree:

| Pass | Calls | Self s | Share | Exponent |
|---|---:|---:|---:|---:|
| `terrain_society.add_world_society` | 3 real (+5 free) | 213.3 | **47.4 %** | **2.05** |
| `hamlet_planner.fill_hamlets` | 1 | 86.2 | 19.1 % | 0.83 |
| `terrain_beast_movement.add_beast_movements` | 1 | 34.6 | 7.7 % | **1.79** |
| `city_planner.fill_cities` | 1 | 27.7 | 6.2 % | 0.36 |
| `terrain_nests.add_nests` | 5 real (+5 free) | 24.0 | 5.3 % | 0.91 |
| `castle_planner.fill_castles` | 1 | 17.0 | 3.8 % | 0.65 |
| `terrain_settlements.add_settlements` | 5 real (+5 free) | 14.2 | 3.2 % | 0.85 |

**`add_world_society` is now nearly half the generation and it has never been touched.** It
has moved 259.8 → 213.3 s across the day, all of it box variation, while its share went from
21 % to 47 %. Three passes have been optimised out from under it. It is also the quadratic
one, so its share keeps rising with world size as well as with every further optimisation
elsewhere.

"Free" calls are the ones in stages 1 to 5, where the phase is too low for the pass to have
anything to do; see [Stages 1 to 5 build the world five times](#stages-1-to-5-build-the-world-five-times).

## How each stage scales

Four full generations at seed 42, phase 16, at each of sizes 17, 33, 65 and 128, re-run on
each tree. The exponent is a least-squares fit of log(seconds) against log(cells), so
**1.0 is linear in cell count and 2.0 is quadratic**.

| Whole run | 17 | 33 | 65 | 128 | exp |
|---|---:|---:|---:|---:|---:|
| 01:45 | 89.7 | 281.2 | 637.6 | 1 244.2 | 0.65 |
| 10:00 | 51.2 | 150.1 | 330.6 | 699.8 | 0.64 |
| 11:41 | 33.5 | 112.4 | 270.9 | 602.3 | 0.71 |
| **12:35** | **13.3** | **55.5** | **177.0** | **450.3** | **0.87** |

The whole-run exponent has climbed 0.65 → 0.87 across the day, and **that is the cost of
the wins rather than a regression**. Every optimisation so far cut a pass that was
sublinear in cells, so the remaining mix is weighted toward the two that are not. The
generator is far cheaper at every size measured and its cost now grows closer to linearly
with cell count than it did this morning.

Per pass, current tree, with the previous ladder's exponent beside it:

| Pass | 17 | 33 | 65 | 128 | exp | prev exp |
|---|---:|---:|---:|---:|---:|---:|
| `add_world_society` | 0.07 | 1.29 | 42.71 | 213.32 | **2.05** | 2.07 |
| `fill_hamlets` | 2.78 | 25.69 | 66.16 | 86.17 | 0.83 | 0.83 |
| `add_beast_movements` | 0.03 | 0.42 | 5.36 | 34.63 | **1.79** | 1.80 |
| `fill_cities` | 6.73 | 12.90 | 23.17 | 27.74 | **0.36** | 0.45 |
| `add_nests` | 0.62 | 1.75 | 6.18 | 24.04 | 0.91 | 0.92 |
| `fill_castles` | 1.24 | 7.24 | 16.81 | 17.03 | 0.65 | 0.64 |
| `add_settlements` | 0.46 | 1.41 | 4.43 | 14.16 | 0.85 | 0.85 |

**The harness reproduces across four ladders.** Six of those seven passes are byte-identical
between the last two and every exponent came back within 0.02: 2.05/2.07, 0.83/0.83,
1.79/1.80, 0.91/0.92, 0.65/0.64, 0.85/0.85. That stability is what makes a changed row
readable — `fill_cities` moving 0.45 → 0.36 is five times the reproducibility spread and so
a real change in shape, not scatter.

### Where this goes at the next size up

Projecting each pass from its size-128 figure at its own fitted exponent to size 257
(4× the cells). **Projection only — nothing at 257 has been run, and the size-192 crossing
described below sits between here and there, so treat these as the shape of the problem
rather than as numbers:**

| Pass | 128 s | exp | 257 s (projected) | share |
|---|---:|---:|---:|---:|
| `add_world_society` | 213.3 | 2.05 | **~3 720** | **78 %** |
| `add_beast_movements` | 34.6 | 1.79 | ~418 | 9 % |
| `fill_hamlets` | 86.2 | 0.83 | ~276 | 6 % |
| `add_nests` | 24.0 | 0.91 | ~85 | 2 % |
| `fill_cities` | 27.7 | 0.36 | ~46 | 1 % |
| **Projected total** | **450** | | **~4 750 (79 min)** | |

This is now the entire argument for what to do next. Three optimisations have taken the
size-128 run from 1 244 s to 450 s without touching `add_world_society`, and the projected
size-257 total has barely moved with them — 5 290 s then, 4 750 s now — because that run is
three quarters one pass. **At 257 the two superlinear passes are a projected 87 % of the
work.** Every further gain elsewhere is bounded by what is left: `fill_cities`, `add_nests`,
`fill_castles` and `add_settlements` together are 83 s at 128 and a projected 180 s at 257.

### One change inside `add_nests`, isolated: 6–13× cheaper at identical placements

Written by another session, measuring **one indexing change in isolation** rather than the
whole interval the ladder above spans. Both statements are true and they are not about the
same thing:

- *This* section's change reindexed three flat scans and moved no placement at all.
- The ladder above spans **every** change to `terrain_nests.py` between 01:45 and 09:42,
  which also includes a refusal rule moving from `a['tier'] >= p['tier']` to `==`. That is
  a semantic change and it raises placements: `beast_nests.sites` goes 957 → 1 571 at size
  33, 2 215 → 3 346 at 65 and 4 379 → 6 128 at 128, the same key read the same way in both
  reports.

So "places exactly the same nests" is a property of the indexing change, not of the
generator between the two reference runs. The counts in this section are also a different
quantity from the ladder's — 14 418 at size 33 here against 1 571 there — so the two columns
should not be divided into one another.

The prediction above was the right one to make and it came out cleanly. A later pass
indexed three flat scans inside `add_nests` without changing a single placement — the
`wildlife` and `beast_nests` blocks were captured before and after and compare byte for
byte, floats by `repr`, at all three sizes — so the nest column is fixed and only the cost
column moves.

Timed around one `add_nests` on a baked phase-12 world, seed 42, 200 km, Windows 11 /
24-core / 31.4 GB / CPython 3.12.10, box at 6 % load. This is one call; the ladder above
reports all five real calls of a phase-16 run, so multiply by five to compare.

| Size | Nests placed | Before | After | Speedup | Per nest before | Per nest after |
|---:|---:|---:|---:|---:|---:|---:|
| 33 | 14 418 | 4.43 s | **0.35 s** | 12.7× | 0.307 ms | 0.024 ms |
| 65 | 32 044 | 10.37 s | **1.21 s** | 8.6× | 0.324 ms | 0.038 ms |
| 129 | 45 413 | 27.19 s | **4.75 s** | 5.7× | 0.599 ms | 0.105 ms |

The per-nest column moves by an order of magnitude and the placed counts do not move at
all, which is the result the paragraph above asked for. It also shows the flat per-nest
model was reading a coincidence: the same pass at the same placements now costs 25× less
per nest at size 33 and 6× less at 129, so "0.12 s per nest" was never a mechanism. The
end-to-end ladder agrees from the other direction — per-nest cost is no longer flat there
either, rising 3× across the four sizes.

Where the time went, by phase inside `_place`, both passes summed:

| Phase | What it does | 33 before→after | 65 before→after | 129 before→after |
|---|---|---|---|---|
| `draw` | territory/spacing test per drawn group | 4.00 → **0.20** | 7.80 → **0.36** | 15.69 → **0.72** |
| `nearest` | distance to the nearest settled thing, per cell | 0.15 → **0.02** | 1.24 → **0.14** | 5.29 → **0.57** |
| `rooms` | habitat gates, per cell per species | 0.24 → **0.08** | 1.11 → **0.45** | 5.03 → **2.33** |

The shape of the remaining cost is different from the shape it replaced. `draw` was 91 % of
the pass at size 33 and is now 18 % at 129; `rooms` is now the largest term and is the one
that is **exactly linear in cells with no plateau**, so it is what a larger raster will pay
for. Extrapolating the three terms at their measured exponents to size 513 gives roughly
66 s per call against roughly 244 s before — about 5½ minutes of nest placement in a
phase-16 run against about 20. Both of those are extrapolations from three points and
neither has been run.

One thing was tried and rejected on measurement: `suitability` is the largest remaining
named cost and recomputes `sum(p['weights'].values())` on each of 684 000 calls. Hoisting
that into the candidate table is 13 % faster per call, which is about 3 % of the pass, and
it costs a second copy of the habitat gates beside a published function. Replacing its dict
comprehension with a generator — the obvious way to avoid building a dict the caller
discards — is **21 % slower**, not faster.

A caution on reading it too far. The session that restructured this pass reports that the
refusal scan is per-*pair* within a single raster cell, that no species' territory is as
wide as the cell pitch at any shipped world width, and that 93 % of draws were being
refused — so the placed count is bounded by cells reached rather than by the density
budget. **The middle clause of that is false and the last is a point on a falling curve;
both were measured directly afterwards — see the superseded section below.** The first
clause survives: the scan was per-pair, which is what the indexing removed. Their axis is not this one: they varied surface area at a fixed raster and saw
saturated tiers barely move, while this ladder varies the raster at a fixed planet and sees
nests grow 16×. The two are consistent and neither settles the other. What follows from
theirs is that a per-cell cost model will mispredict, which is worth knowing because the
flat per-nest column above is not a per-cell model either.

### Every measurement here is below a crossing nobody has tested

> **Superseded 2026-09-21 — the crossing is not at size 192 and the pass is already past
> it.** This section computes cell pitch as `2πr/(n-1)`, which is the pitch **at the
> equator**. The grid is lat/lon: `terrain_globe.direction` puts row `z` at latitude
> `π/2 - πz/(n-1)` and spreads that row's `n-1` points around a circle of radius
> `r·cos(lat)`, so the zonal pitch collapses towards the poles by a factor of about
> `π/(n-1)`. Smallest neighbour gap on the 200 km world: 611.6 m at size 33, 38.3 m at
> 129, **2.4 m** at 513, against the 390.6 m equatorial pitch at 513.
>
> Counted directly, by replaying placement and asking of each refusal whether its blocker
> was in the candidate's own cell: **0** cross-cell refusals at size 33, then 50 animal and
> 426 monster at size 65, then 497 and 479 at size 129. The crossing is between 33 and 65.
>
> The consequence the section predicts is also not what happens. Draws are **constant**
> across the raster, because the budget is an integral over a planet the raster does not
> change — 76.1 k animal and 13.07 k monster draws at every size below. What the raster
> changes is how many of that fixed number find room, and the refusal rate falls smoothly
> rather than stepping at a threshold:
>
> | Size | Animal draws | placed | refused | Monster draws | placed | refused |
> |---:|---:|---:|---:|---:|---:|---:|
> | 33 | 76 107 | 12 924 | 63 183 (83 %) | 13 074 | 1 494 | 11 580 (89 %) |
> | 65 | 76 066 | 28 755 | 47 311 (62 %) | 13 066 | 3 289 | 9 777 (75 %) |
> | 129 | 76 092 | 39 454 | 36 638 (48 %) | 13 075 | 5 959 | 7 116 (54 %) |
>
> So the 93 % refusal rate was a point on a falling curve, not a plateau, and the fall is
> driven by cell count — one site per bucket per cell, more cells, more room — and not by
> cross-cell comparison, which is still under 7 % of monster refusals at size 129. Seed 42,
> phase 12, 200 km throughout. What remains genuinely untested is anything above 129.
>
> See board/NEST-SAME-CELL-CLAIM-IS-FALSE.md. The original reasoning follows unedited.

Their mechanism rests on cell pitch exceeding the widest creature territory, so that the
spacing rule only ever compares a cell against itself. Pitch is `2πr/(n-1)`, and on the
200 km default world it is:

| Size | 17 | 33 | 65 | 128 | **192** | 257 |
|---|---:|---:|---:|---:|---:|---:|
| Cell pitch | 12.500 km | 6.250 km | 3.125 km | 1.575 km | **1.047 km** | 0.781 km |

Measured by generating at phase 1 and reading `spacing_m`, not derived. Against a widest
monster territory of 1.05 km (their figure), **the crossing is at size 192**: that is the
first size where pitch falls below the widest territory and the spacing rule begins
comparing a cell against its neighbours.

1.047 km against 1.05 km is a margin of 0.3 %, so **192 is inside the transition rather
than safely below it**, and a probe that tests only 192 risks landing on the boundary and
measuring neither regime cleanly. The first size unambiguously past the crossing is 257, so
the probe is a pair: 129 below, 257 above. It does not need phase 16 — `add_nests` first
runs at stage 13, and stopping there is most of the cost avoided.

Every number in this document, and every number in their investigation, comes from below
that crossing; their own figures were taken at sizes 33 to 65, three to six times below it.
Above it the per-pair-within-one-cell mechanism stops holding, the 93 % refusal rate has no
reason to survive, and the flat per-nest column has no reason to either. **Neither model
has been tested where it stops applying**, and this ladder tops out at 128.

Exactly two passes do not follow that, and they are the ones that decide whether a large
world is reachable at all.

### `add_world_society` is quadratic

0.07 s at size 17 and 259.8 s at 128 — **3 700× for 57× the cells**, a fitted exponent of
2.09. It goes from 0.1 % of the run to 21 % of it between the smallest and largest size
measured, and it is the only reason stage 12 ("Populated regions") is 7 % of a size-128
run when it is 0.2 % of a size-17 one.

The shape is in the sea-trade pass at
[`terrain_society.py:224`](../Sim/icarus_sim/terrain_society.py#L224): every trade terminal
is paired with every other, and each pair rebuilds a cost vector over every node in the
world and then runs one Dijkstra across the whole sphere graph.

```python
for a, port in enumerate(ports):
    for other in ports[a+1:]:
        ...
        cost = water_cost(points, water, depth, hazard, limit, o['sea_draft'])
        distances, parent = shortest_paths(graph, port['sea_node'], cost, {other['sea_node']})
```

That is O(ports² · cells · log cells) with a full O(cells) allocation per pair. Ports grow
with city count and the graph grows with cells, which is the quadratic. The coastal-hamlet
loop above it has the same shape one order down — one full-graph search per city.

Counted directly, by attributing every `shortest_paths` call to the line that made it,
for one phase-12 generation at each size. Counts, not timings, so a contended box does not
affect them:

| Size | Cells | Cities | `:166` per city | `:230` per port pair | Total |
|---:|---:|---:|---:|---:|---:|
| 17 | 289 | 13 | 13 | 0 | 13 |
| 33 | 1 089 | 42 | 42 | 203 | 245 |
| 65 | 4 225 | 52 | 52 | 3 364 | 3 416 |
| 128 | 16 384 | 49 | 49 | 3 788 | 3 837 |

The pair loop is the pass: **3 788 of the 3 837 searches at size 128**, against 49 for the
per-city loop. At size 17 it does not run at all, which is why the pass is 0.1 % of a
size-17 generation and 21 % of a size-128 one — it is not that this code got slower with
scale, it is that below some coastline threshold it does not execute.

3 788 pairs implies about 88 ports, which is the ≤2 coastal hamlets per city that
`coastal_hamlets` permits, times 49 cities, less the same-core and non-terminal pairs the
guards drop. That figure is implied by the pair count, not separately measured.

Read the last two rows against the timings. From 65 to 128 the pair count rises only
1.13× — city count has stopped growing — yet the pass still gets 5.9× slower, because each
of those ~3 800 searches now walks a graph four times larger. Both halves are real: the
count is O(ports²) and each search is O(cells · log cells). Removing either alone leaves
the other.

For scale against what it buys: that whole pass produces **4 sea routes** at size 128, and
4 at size 65 as well.

### `add_beast_movements` is the other superlinear pass

Exponent 1.81 on the current tree, up from 1.66 before its module was rewritten. 35.8 s at
size 128, 5.1 % of the run — third by size, behind `fill_cities` and `add_world_society`.

It is here because of the exponent, not the seconds. On the projection above it reaches
roughly 445 s at size 257, about the same as `fill_cities`, having been an eighth of it at
128. Its rewrite between the two reference runs did not change that: the pass moved −14 %,
inside the −1 % to −18 % band that unchanged passes moved on the same pair of runs, with
its group count flat at 11 119 → 11 184.

## Where the repeated work is

The profile counts calls, and the counts are the finding. Several passes run many times on
the finished world, each run replacing the last one's output.

**`add_nests` runs five times.** Once at stage 13, then **twice per age transition**: once
directly in `age_transition` ("nests before fates", so city fate can read them) and again
inside `rebuild_tail`. At size 128 the five calls are:

| Stage | Calls | Before | Now |
|---|---:|---:|---:|
| 13 | 1 | 103.8 s | 4.9 s |
| 14 | 2 | 206.2 s | 8.9 s |
| 15 | 2 | 195.5 s | 9.2 s |

The repetition is unchanged; only its price is. All five calls were 505.5 s and 41 % of the
run, and are now 23.0 s and 3.3 %. The pair-repeat that used to be worth about 200 s — one
call from each of stages 14 and 15 — is now worth roughly 9 s. **This is no longer a place
to save time**, and the paragraph survives because the structure is still worth knowing,
not because the number is.

**The second call is not redundant**, and this profile did not establish that — a separate
investigation did. `city_fate` runs between the two, reads `beast_nests` and feeds it to the
predicate deciding whether a city dies
([`terrain_history.py:230`](../Sim/icarus_sim/terrain_history.py#L230), called from
`age_transition`), and over half the monster lairs move between the calls: 44.8 % and 42.4 %
of the first field survives in place across the two ages, neither pair byte-identical. Those
survival figures are that investigation's, not measured here. So this ~200 s is the price of
a correct city-fate decision, not waste — which is exactly why a call count is a question
and not a finding.

**`add_world_society` runs three times** on real data — stage 12, then once inside each age
transition's `rebuild_tail` — at 83.2 s, 92.8 s and 83.8 s. Stage 12's output is wholly
replaced at stage 14. It is not wasted for a caller who asked for phase 12, but for the
phase-16 default it is 83 s of work nothing reads.

**`add_settlements` runs three times in stages 10, 11 and 12** at rising phases (7, 8, 9),
and twice more in the age transitions: 18.8 s total. Small, same shape.

### Stages 1 to 5 build the world five times

Stages 1 to 5 each call `generate_base(replace(cfg, phase=stage))`, which rebuilds the
physical world **from scratch** at the new phase rather than continuing the previous one:
`generate_tectonics` runs five times for 6.0 s of self time where one run at phase 5 would
be about 1.4 s.

`terrain_area.apply_world_scale` then runs the *whole* civilization chain on each of those
five — water, climate, labels, settlements, humans, colleges, seasonal food, society and
nests — which is why `add_nests` and `add_world_society` show ten and eight calls in the
profile rather than five and three. Those extra calls are nearly free only because the
phase is low enough that they return early.

At size 128 the entire waste is about 5 s, 0.4 % of the run, so this is **not** where to
start. It is recorded because it is a structural surprise that reads as a bug, and because
its cost rises with the exponent of the physical stages (≈1.05) rather than with the
sublinear whole.

## Memory

Peak resident is 2 775 MB at size 128, and 2 290 MB of that arrives inside stage 16 alone:
resident is 482 MB entering the stage, peaks at 2 775 MB during it, and settles at 1 040 MB
when it ends. So the peak is a transient in the planners and the satellite packages, not
retained world state.

Peak memory grew 379 → 460 → 711 → 2 775 MB across the ladder. The jump from 65 to 128 is
3.9× for 3.9× the cells, far steeper than the three points below it, so the sublinear fit
of 0.49 is a bad summary and the true curve steepens. A size-257 run on this machine is
memory-plausible but was not attempted.

**The beast and monster work did not move memory at all** — 379/460/711/2 775 MB now against
379/460/713/2 773 MB before, identical within a megabyte at every size, while placing 40 %
more nests. Time halved and the memory curve did not notice, which says the peak is not
nest state. It is stage 16.

## What this does not tell you

- **Nothing about the C++ port.** Every number is CPython. `Core/` was not measured.
- **Nothing per line.** The profile names passes, not lines. `add_nests` is 41 % of the run
  and this document does not say which part of it. The `add_world_society` call-site split
  above *is* measured, by a separate counting run, but nothing in `tools/stage_profile.py`
  produces it and no test keeps it true.
- **Nothing about what `add_nests` spends its time on.** The per-nest figure says the cost
  scales with nests placed; it does not say the work is per nest. A separate investigation
  reports it as per-*pair* scanning within one raster cell, which produces the same flat
  column whenever the nests-per-cell distribution holds steady, and would diverge from it
  as soon as the cell pitch drops below a species' territory width. That crossing was
  put at size 192; it is not there. Pitch is not one number on a lat/lon grid, the polar
  rings cross first, and a direct count puts the crossing between 33 and 65 — so this
  ladder is entirely above it, not below it. See the superseded section above.
- **Nothing about why `add_nests` got steeper.** Its exponent moved 0.65 → 0.93 and its
  per-nest cost stopped being flat. Both are measured; neither is explained here, and the
  section on the isolated indexing change points at `rooms` as the term that is linear in
  cells without a plateau. Nothing here confirms that is the cause of the ladder's move.
- **Nothing at size 257, where it now matters most.** The projection above is four
  extrapolations from four points each.
  `add_world_society` reaching 73 % of a 257-run is the most consequential claim in this
  document and it is the least measured.
- **Nothing about whether the 4 sea routes are worth 3 788 searches.** That is a design
  question about what the pass is for, and this document only prices it. A pass can be
  worth a great deal and still cost what it costs.
- **Nothing about how much repeated work is redundant.** The call counts are measured; the
  claim that a second `add_nests` mostly reproduces the first is not. Establishing it means
  comparing the two fields, which nothing here does.
- **Nothing at one seed but 42, or one phase but 16.** Content counts drive most of these
  passes, and a seed with more coastline has more ports and a worse `add_world_society`.
- **Nothing about a contended box.** The 65-point ran at 44 % background load against 19 to
  28 % for the others. Timings under contention are slow, not wrong in shape, but the
  exponents carry that noise.
- **Nothing about the overhead of measuring.** These are the costs of a *profiled*
  generation. The wrappers are cheap next to the passes they wrap and `psutil` is sampled
  sixteen times, but nobody has measured the difference.

## Reproducing

```bash
python tools/stage_profile.py --size 128 --seed 42
```

Writes `Artifacts/stage-profile-128.json`, `...md`, and a `...progress.json` rewritten as
each stage closes so a killed run still leaves the stages it measured. `Artifacts/` is
ignored by git, so the numbers live here and the raw records stay out of the tree.

Cost to reproduce the ladder on a comparable machine: about 89 s, 281 s, 638 s and 1 244 s
for sizes 17, 33, 65 and 128 — roughly 38 minutes in total.
