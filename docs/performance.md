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
RAM, CPython 3.12.10, box at 21 % background load when the run started.

**1 244 s (20 min 44 s) wall, peak resident 2 773 MB.**

> **Two of the largest figures below are stale, and the run cannot be repeated to fix them
> without first quieting the tree.** This measurement finished at 01:45 on 2026-09-21. A
> concurrent session then restructured `city_planner.py` at 02:10 and `terrain_nests.py`
> **twice**, at 02:18 (`3360718c14301b8f`) and again at 02:33 (`c5af625157f10ee2`). Those
> two modules carry `add_nests` (505 s, 41 %) and `fill_cities` (275 s, 22 %) — together
> 62 % of this run. **Treat the 505 s and 275 s figures, the two exponents derived from
> them, and the whole-run total as describing the tree as it stood at 01:45, not as it
> stands now.**
>
> No figure for the size of the `add_nests` change is quoted here, and that is deliberate.
> Two were offered while this paragraph was being written and the first was obsolete within
> half an hour, because the second change altered what the predicate does rather than how
> fast it does it. The session that made them reports a full phase-16 generation moving from
> 356 s to 209 s at their reference world, on a contended box, as an upper bound — their
> measurement, not this one, and provisional. A number that keeps moving is better named as
> a moving number than pinned at whichever value it held when someone wrote it down.
>
> Everything else here is unaffected. `add_world_society` (`terrain_society.py`, last
> touched 01:06), `fill_hamlets` (01:22) and `add_beast_movements` (2026-09-19) all predate
> the run, and the structural findings — the stage split, the call counts, the two
> superlinear exponents, the search-count tables — do not depend on the two stale passes.
>
> `tools/stage_profile.py` now records a digest of every measured module in each report, so
> this ambiguity cannot recur: a report states the code it measured. This run predates that,
> which is why it needs a paragraph instead of a hash. The two modules stood at versions
> this document cannot name. At 02:22 on 2026-09-21 they were `terrain_nests.py`
> `3360718c14301b8f` and `city_planner.py` `e6133a003130fb7f` — stated with their timestamp
> rather than as "current", because on this tree a hash is current only for as long as it
> takes to write the sentence. Compare against the tree before trusting any figure above.

| # | Stage | Body s | Capture s | Total s | Share | Cum | RSS MB | ΔRSS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Plate layout | 0.8 | 0.0 | 0.8 | 0.1 % | 0.1 % | 37 | +8 |
| 2 | Tectonic relief | 1.1 | 0.0 | 1.1 | 0.1 % | 0.2 % | 47 | +10 |
| 3 | Surface detail | 1.4 | 0.0 | 1.4 | 0.1 % | 0.3 % | 56 | +9 |
| 4 | Erosion and sediment | 1.9 | 0.0 | 2.0 | 0.2 % | 0.4 % | 84 | +28 |
| 5 | Connected water | 2.0 | 0.0 | 2.0 | 0.2 % | 0.6 % | 107 | +23 |
| 6 | Second tectonic relief | 1.5 | 0.1 | 1.6 | 0.1 % | 0.7 % | 109 | +2 |
| 7 | Valleys and gorges | 0.4 | 0.1 | 0.4 | 0.0 % | 0.8 % | 111 | +2 |
| 8 | Wind and rain | 1.2 | 0.3 | 1.5 | 0.1 % | 0.9 % | 157 | +46 |
| 9 | Leylines | 3.2 | 0.2 | 3.5 | 0.3 % | 1.2 % | 205 | +48 |
| 10 | Founding | 2.8 | 0.1 | 2.9 | 0.2 % | 1.4 % | 221 | +16 |
| 11 | Roads | 4.3 | 0.0 | 4.3 | 0.3 % | 1.7 % | 230 | +9 |
| 12 | Populated regions | 88.9 | 0.1 | **89.1** | 7.2 % | 8.9 % | 245 | +15 |
| 13 | Beasties and animals | 103.9 | 0.4 | **104.3** | 8.4 % | 17.3 % | 318 | +74 |
| 14 | Age transition 1 | 307.9 | 0.6 | **308.5** | 24.8 % | 42.1 % | 384 | +65 |
| 15 | Age transition 2 | 290.2 | 0.5 | **290.7** | 23.4 % | 65.4 % | 468 | +84 |
| 16 | Simulation complete | 426.5 | 3.6 | **430.1** | 34.6 % | 100 % | 1 044 | +576 |

The first eleven stages — the entire physical world, its climate, its leylines, its cities
and its roads — are **21.6 s, 1.7 % of the run**. Everything else is stages 12 to 16.

Snapshot capture is 6.2 s across the whole run, 0.5 %. It is not a time problem. It is a
memory one: the sixteen snapshots retain a copy of every layer that changed, and
`generate_history` builds them whether or not a caller exports them.

## The four passes that are the run

Self time, summed across every call, at size 128:

| Pass | Calls | Self s | Share | Slowest call |
|---|---:|---:|---:|---:|
| `terrain_nests.add_nests` | 5 real (+5 free) | 505.4 | 40.6 % | 108.1 s |
| `city_planner.fill_cities` | 1 | 274.8 | 22.1 % | 274.8 s |
| `terrain_society.add_world_society` | 3 real (+5 free) | 259.8 | 20.9 % | 92.8 s |
| `hamlet_planner.fill_hamlets` | 1 | 88.4 | 7.1 % | 88.4 s |
| `terrain_beast_movement.add_beast_movements` | 1 | 41.7 | 3.4 % | 41.7 s |

Those five are **1 170 s of 1 244 s — 94 % of the run.** Nothing else reaches 20 s.

"Free" calls are the ones in stages 1 to 5, where the phase is too low for the pass to have
anything to do; see [Stages 1 to 5 build the world five times](#stages-1-to-5-build-the-world-five-times).

## How each stage scales

Four full generations at seed 42, phase 16: sizes 17, 33, 65 and 128. The exponent is a
least-squares fit of log(seconds) against log(cells), so **1.0 is linear in cell count and
2.0 is quadratic**. The size-65 run started on a box at 44 % background load; the others
were between 19 % and 28 %, so read 65 as slightly pessimistic.

| Stage | 17 s | 33 s | 65 s | 128 s | exp |
|---|---:|---:|---:|---:|---:|
| Plate layout | 0.02 | 0.05 | 0.20 | 0.78 | 0.92 |
| Tectonic relief | 0.02 | 0.08 | 0.29 | 1.15 | 0.98 |
| Surface detail | 0.02 | 0.08 | 0.32 | 1.44 | 1.04 |
| Erosion and sediment | 0.03 | 0.09 | 0.39 | 1.96 | 1.08 |
| Connected water | 0.03 | 0.10 | 0.39 | 2.05 | 1.08 |
| Second tectonic relief | 0.02 | 0.08 | 0.32 | 1.58 | 1.07 |
| Valleys and gorges | 0.01 | 0.02 | 0.09 | 0.42 | 1.05 |
| Wind and rain | 0.02 | 0.07 | 0.29 | 1.53 | 1.10 |
| Leylines | 0.05 | 0.18 | 0.71 | 3.46 | 1.04 |
| Founding | 0.11 | 0.23 | 0.68 | 2.92 | 0.80 |
| Roads | 0.10 | 0.37 | 1.18 | 4.31 | 0.92 |
| **Populated regions** | 0.19 | 1.10 | 17.83 | 89.07 | **1.58** |
| Beasties and animals | 6.38 | 24.11 | 55.12 | 104.29 | 0.68 |
| Age transition 1 | 14.42 | 51.54 | 127.03 | 308.50 | 0.75 |
| Age transition 2 | 15.49 | 55.45 | 131.78 | 290.72 | 0.72 |
| Simulation complete | 52.84 | 147.63 | 300.99 | 430.06 | 0.52 |
| **Whole run** | **89.7** | **281.2** | **637.6** | **1 244.2** | **0.65** |
| Peak resident MB | 379 | 460 | 713 | 2 773 | 0.49 |

And the same fit per pass, which is where the shape actually lives:

| Pass | 17 s | 33 s | 65 s | 128 s | exp |
|---|---:|---:|---:|---:|---:|
| `terrain_society.add_world_society` | 0.07 | 1.34 | 44.21 | 259.77 | **2.09** |
| `terrain_beast_movement.add_beast_movements` | 0.06 | 0.57 | 6.85 | 41.69 | **1.66** |
| `terrain_nomad_routes.add_nomad_routes` | 0.01 | 0.05 | 0.36 | 1.27 | 1.27 |
| `terrain_nomads.add_nomads` | 0.01 | 0.04 | 0.28 | 1.05 | 1.24 |
| `terrain_ecology.add_environment` | 0.03 | 0.15 | 0.68 | 3.32 | 1.14 |
| `terrain_tectonics.generate_tectonics` | 0.08 | 0.31 | 1.31 | 5.96 | 1.08 |
| `terrain_settlements.add_settlements` | 0.48 | 1.46 | 4.65 | 18.78 | 0.90 |
| `hamlet_planner.fill_hamlets` | 3.58 | 26.10 | 79.66 | 88.37 | 0.80 |
| `terrain_nests.add_nests` | 35.66 | 128.42 | 280.26 | 505.42 | 0.65 |
| `city_planner.fill_cities` | 46.78 | 110.98 | 189.23 | 274.82 | 0.43 |

The whole-run exponent of 0.65 is the headline that misleads. Total cost is **sublinear**
in cells because the planet is a fixed 200 km world: raising the grid samples the same
ground more finely rather than adding more of it, so the content counts that drive most
passes grow far slower than cells do. That is why 57× the cells costs only 14× the time.

For the largest pass that is not a guess at a mechanism but a measured relationship. Cost
per *placed nest* is flat across the whole ladder, over a 16× range in nest count:

| Size | Cells | Nests placed | `add_nests` | Per nest | Nests per cell |
|---:|---:|---:|---:|---:|---:|
| 17 | 289 | 271 | 35.7 s | 0.132 s | 0.94 |
| 33 | 1 089 | 957 | 128.4 s | 0.134 s | 0.88 |
| 65 | 4 225 | 2 215 | 280.3 s | 0.127 s | 0.52 |
| 128 | 16 384 | 4 379 | 505.4 s | 0.115 s | 0.27 |

So `add_nests` is linear in nests placed at about **0.12 s each**, and the grid enters only
by changing how many get placed. That is the model to re-test after the restructure, and it
is a sharper prediction than the 0.65 exponent: a pass that got genuinely cheaper should
move the per-nest column, while one that merely places fewer nests will move only the count.

### Re-measured 2026-09-21: the pass is 6–13× cheaper and places exactly the same nests

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
per nest at size 33 and 6× less at 129, so "0.12 s per nest" was never a mechanism.

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
budget. Their axis is not this one: they varied surface area at a fixed raster and saw
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

### `add_beast_movements` is the second tail

Exponent 1.66, 41.7 s at size 128 from 0.06 s at 17, producing 11 119 groups. It is only
3.4 % of a size-128 run, but at that exponent it passes `fill_hamlets` somewhere above size
200 and keeps going.

## Where the repeated work is

The profile counts calls, and the counts are the finding. Several passes run many times on
the finished world, each run replacing the last one's output.

**`add_nests` runs five times.** Once at stage 13, then **twice per age transition**: once
directly in `age_transition` ("nests before fates", so city fate can read them) and again
inside `rebuild_tail`. At size 128 the five calls are:

| Stage | Calls | Total | Slowest | Other |
|---|---:|---:|---:|---:|
| 13 | 1 | 103.8 s | 103.8 s | — |
| 14 | 2 | 206.2 s | 108.1 s | 98.1 s |
| 15 | 2 | 195.5 s | 102.2 s | 93.3 s |

Read those carefully, because two different sums are quotable and only one answers a given
question. **All five calls are 505.5 s, 41 % of the run.** The *second* call of each
age-transition pair — the one a reader asks about when asking whether this is repeated
work — is one call from each of stages 14 and 15, so between 191 s and 210 s depending on
which of each pair ran first, which the profile does not record. Call it **about 200 s, 16 %
of the run**. It is not 206.2 s; that figure is one whole stage, both its calls.

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

Peak resident is 2 773 MB at size 128, and 2 200 MB of that arrives inside stage 16 alone:
resident is 469 MB entering the stage, peaks at 2 773 MB during it, and settles at 1 044 MB
when it ends. So the peak is a transient in the planners and the satellite packages, not
retained world state.

Peak memory grew 379 → 460 → 713 → 2 773 MB across the ladder. The jump from 65 to 128 is
3.9× for 3.9× the cells, far steeper than the three points below it, so the sublinear fit
of 0.49 is a bad summary and the true curve steepens. A size-257 run on this machine is
memory-plausible but was not attempted.

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
  as soon as the cell pitch drops below a species' territory width. That crossing is at
  size 192 and this ladder tops out at 128, so nothing here tests it.
- **Nothing about the nest counts after the restructure.** The session that made it reports
  58 % more monsters placed on their reference world, animals byte-identical. If that
  carries, the content counts in this document move and the per-nest column has to be
  re-taken, not adjusted.
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
