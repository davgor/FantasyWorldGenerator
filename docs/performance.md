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
RAM, CPython 3.12.10, box at 4 % background load when the run started. Measured-code digest
`e9922f7ee1c6754b` over 30 modules.

**137.0 s (2 min 17 s) wall, peak resident 1 069 MB.**

| # | Stage | Total s | Share | Cum | RSS MB |
|---|---|---:|---:|---:|---:|
| 1–11 | physical world, climate, leylines, cities, roads | 17.1 | 12.4 % | 12.4 % | 229 |
| 12 | Populated regions | 4.3 | 3.2 % | 15.6 % | 235 |
| 13 | Beasties and animals | 5.0 | 3.6 % | 19.2 % | 321 |
| 14 | Age transition 1 | **16.8** | 12.3 % | 31.5 % | 413 |
| 15 | Age transition 2 | **20.3** | 14.8 % | 46.4 % | 495 |
| 16 | Simulation complete | **73.5** | 53.6 % | 100 % | 1 067 |

### Six runs, five rounds of optimisation

Same seed, size and machine across 2026-09-21. Each pair differs by a known set of modules,
confirmed by the subject digest rather than by reading a changelog.

| Run | Digest | Changed since previous | Total |
|---|---|---|---:|
| 01:45 | unknown (predates digests) | — | 1 244.2 s |
| 10:00 | `6c17d71d47833ef5` | `terrain_nests`, `terrain_beast_movement`, `city_planner` | 699.8 s |
| 11:41 | `2eb01cdc5f6307fe` | `city_planner` only | 602.3 s |
| 12:35 | `de592f00bfc582e7` | `city_planner` only | 450.3 s |
| 13:38 | `17f0f741e3d6a69b` | `terrain_society`, `hamlet_planner`, `terrain_settlements`, `city_planner`, `terrain_erosion` | 184.6 s |
| 16:08 | `e9922f7ee1c6754b` | `terrain_beast_movement` **only** | **137.0 s** |

**1 244 s → 137 s, a 9.1× reduction**, at content identical to the first run in every count
this report tracks, at every size on the ladder.

| Size | 01:45 | now | Factor |
|---:|---:|---:|---:|
| 17 | 89.7 | **12.2** | 7.4× |
| 33 | 281.2 | **35.3** | 8.0× |
| 65 | 637.6 | **75.2** | 8.5× |
| 128 | 1 244.2 | **137.0** | 9.1× |

### The quadratic is gone

`add_world_society` was the pass this document has pointed at since the first measurement:
21 % of the run in the morning, 47 % by midday, exponent 2.05–2.09 reproduced across four
separate ladders, and a projected 78 % of a size-257 generation. It has now been cut, and
the shape went with the seconds.

| | 12:35 | 13:38 |
|---|---:|---:|
| `add_world_society` at size 128 | 213.3 s | **1.85 s** (−99.1 %) |
| Its exponent | **2.05** | **0.80** |
| Stage 12 "Populated regions" | 70.4 s | **4.5 s** (−93.6 %) |
| Projected size-257 total | ~4 750 s | **~790 s** |

That last row is the one that matters. Four rounds of optimisation had taken the size-128
run from 1 244 s to 450 s while barely moving the projected 257 cost, because that run was
three quarters one quadratic pass. Removing the quadratic moves it 6× in a single step.

`fill_hamlets` was cut in the same round: **86.2 s → 17.5 s (−79.7 %)**, exponent 0.83 → 0.57.

### What this round does not establish

Unlike the two city-planner rounds, this one is **not** a clean single-variable experiment
and its noise floor is much looser. Five modules changed at once — `terrain_society`,
`hamlet_planner`, `terrain_settlements`, `city_planner` and `terrain_erosion` — so the
hamlet work and the society work cannot be separated from each other here.

Only four measured passes were byte-identical across the pair, and they moved by
−0.6 %, +0.4 %, +11.7 % and +13.1 % at size 128, with `add_environment` at +23.5 %. That is
a noise floor of roughly ±20 %, against −4.7 % to −0.4 % in the previous round. The two
large wins clear it by a wide margin; **nothing smaller in this round is interpretable**,
including the +14.8 % on `add_settlements` and the +6.5 % on `fill_cities`, both of which
changed and both of which sit inside the band.

One movement is unexplained and worth recording rather than smoothing: `add_beast_movements`
is byte-identical and its exponent moved **1.79 → 1.61**, nine times the ±0.02 spread the
previous four ladders reproduced to. Its size-128 figure rose 11.7 % while its size-65
figure fell 15 %. No explanation is offered here.

The size-128 run also overlapped an independent size-128 profile started by another session
in the same window. The two agree to 0.7 % — 183.3 s against 184.6 s on the same digest —
which is a genuine cross-session reproduction, but both may carry the same shared-box cost.
Single-threaded CPython on 24 cores makes that small; it is not zero.

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

*(That rework was the irruption trigger, which bought behaviour rather than speed. The
speed came separately, in the round below.)*

### The fifth round: `add_beast_movements`, and the memory went with it

The 13:38 → 16:08 pair, and **the cleanest single-variable experiment in this document**:
`terrain_beast_movement.py` is the only file in the measured digest that changed, confirmed
by modification time against the 13:38 run as well as by the digest.

| | 13:38 | 16:08 |
|---|---:|---:|
| `add_beast_movements` at size 128 | 38.68 s | **3.60 s** (−90.7 %) |
| Its exponent | 1.62 | **1.10** |
| Whole run at size 128 | 184.6 s | **137.0 s** (−25.8 %) |
| **Peak resident at size 128** | **2 823 MB** | **1 069 MB** (−62 %) |
| Its rank among passes | 1st of 8, 21.0 % | **8th, 2.6 %** |
| Projected size-257 cost of the pass | ~366 s | **~17–25 s** |

**The memory is the second finding and it was not the target.** Timed around the pass alone
on a baked size-128 world, resident set sampled during the call: the old form peaked
**2 208 MB above entry** and the new one **158 MB**, a 93 % cut, because the old one cached
a full-width distance and parent array for every one of ~9 000 start nodes and never
dropped one. At size 65 the same measurement is 216 MB against 48 MB, and the whole-run
peak does not move there (765.7 → 765.6 MB) because something else sets it; at 128 this
pass *was* the peak.

**Noise floor.** At size 65 every unchanged pass moved between 0.0 % and −0.7 % on this
pair, so the floor is under a percent and the −86.7 % there is unambiguous. At size 128 the
floor is much looser — unchanged passes moved −22.7 % (`add_settlements`), −12.1 %
(`add_nests`) and +25 % (`_attach_key_location_plans`, a 0.4 → 0.5 s rounding) — and the
−90.7 % clears even that. **Nothing else in the size-128 column of this pair is
interpretable**, including the apparent improvements in `add_nests` and `add_settlements`,
which run entirely before stage 16 and cannot have been caused by this change.

**Content is unmoved, and by the strongest available check.** The `beast_movements` block
was captured before and after at sizes 17, 33, 65 and 128 and compares **byte for byte with
every float printed by `repr`** — same groups, same camps, same leg node paths, same
`routed`/`stranded`/`solitary` counts. No seed changes, no version moves and no world needs
regenerating. See
[PERF-BEAST-MOVEMENTS-IS-THE-PASS](../board/done/PERF-BEAST-MOVEMENTS-IS-THE-PASS.md).

## The passes that are the run

Self time, summed across every call, at size 128 on the current tree:

| Pass | Calls | Self s | Share | Exponent |
|---|---:|---:|---:|---:|
| `city_planner.fill_cities` | 1 | 27.7 | 20.2 % | 0.37 |
| `terrain_nests.add_nests` | 5 real (+5 free) | 23.9 | 17.4 % | 0.94 |
| `castle_planner.fill_castles` | 1 | 17.3 | 12.6 % | 0.66 |
| `hamlet_planner.fill_hamlets` | 1 | 17.2 | 12.6 % | 0.57 |
| `terrain_settlements.add_settlements` | 5 real (+5 free) | 12.6 | 9.2 % | 0.87 |
| `terrain_tectonics.generate_tectonics` | 5 | 5.2 | 3.8 % | 1.05 |
| `terrain_history.rebuild_tail` | 2 | 4.2 | 3.1 % | — |
| `terrain_beast_movement.add_beast_movements` | 1 | **3.6** | 2.6 % | **1.10** |
| `terrain_society.add_world_society` | 3 real (+5 free) | 1.4 | 1.0 % | 0.80 |

**The profile is flat, and it is flat at both ends now.** No pass is more than a fifth of
the run and the top four are within 11 s of each other. `add_world_society` has gone from
first place at 47 % to ninth at 1 %; `add_beast_movements` from first at 21 % to eighth at
2.6 %.

**Nothing left is meaningfully superlinear.** `add_beast_movements` still carries the
largest exponent, but at 1.10 against 1.62 it is now barely above linear in cells and it is
2.6 % of the run, so its exponent no longer decides anything. Read the 1.10 loosely: the
size-17 figure it is fitted through is 0.05 s, at the edge of what the profile resolves,
and an isolated harness that times the pass alone on a baked world fits **1.47** over the
same four sizes against **1.79** for the old code. Both say the shape improved; the second
is the better-resolved number and the more conservative one.

The exponents in the `add_beast_movements` row and the ladder below are from the 16:08 run.
Every other row is unchanged from 13:38, because every other module is.

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
| 12:35 | 13.3 | 55.5 | 177.0 | 450.3 | 0.87 |
| 13:38 | 12.1 | 35.1 | 79.3 | 184.6 | 0.67 |
| **16:08** | **12.2** | **35.3** | **75.2** | **137.0** | **0.59** |

The whole-run exponent climbed 0.65 → 0.87 over the first three rounds, fell back to 0.67
when the society quadratic went, and is now 0.59. That is the same mechanism each time:
those early rounds cut passes that were sublinear in cells, leaving the mix weighted toward
the two that were not, and the last two rounds cut both of those. **The generator is now
far cheaper than it started and better shaped than it has ever been.**

Per pass, current tree, with the previous ladder's exponent beside it:

| Pass | 17 | 33 | 65 | 128 | exp | prev exp |
|---|---:|---:|---:|---:|---:|---:|
| `fill_cities` | 6.71 | 12.79 | 22.18 | 27.70 | 0.37 | 0.36 |
| `add_nests` | 0.62 | 1.75 | 6.19 | 23.90 | 0.94 | 0.94 |
| `fill_castles` | 1.16 | 7.02 | 16.62 | 17.30 | 0.66 | 0.66 |
| `fill_hamlets` | 1.65 | 6.80 | 13.40 | 17.20 | 0.57 | 0.57 |
| `add_settlements` | 0.47 | 1.32 | 3.99 | 12.60 | 0.87 | 0.87 |
| `generate_tectonics` | 0.07 | 0.31 | 1.26 | 5.22 | 1.05 | 1.05 |
| `add_beast_movements` | 0.05 | 0.08 | 0.57 | 3.60 | **1.10** | **1.62** |
| `add_world_society` | 0.07 | 0.35 | 0.78 | 1.40 | 0.80 | 0.80 |

Only the last-but-one row moved on this ladder, because only its module did. The other
rows' small size-128 movements — `add_nests` 27.18 → 23.90, `add_settlements` 16.26 → 12.60
— are box variance on passes whose bytes did not change and which run entirely before the
one that did; **do not read them as wins.** The size-65 column is the tight one: every
unchanged pass there moved by less than a percent.

### Where this goes at the next size up

Projecting each pass from its size-128 figure at its own fitted exponent to size 257
(4× the cells). **Projection only — nothing at 257 has been run, and the size-192 crossing
described below sits between here and there:**

| Pass | 128 s | exp | 257 s (projected) | share |
|---|---:|---:|---:|---:|
| `add_nests` | 23.9 | 0.94 | ~88 | 28 % |
| `fill_cities` | 27.7 | 0.37 | ~46 | 15 % |
| `fill_castles` | 17.3 | 0.66 | ~43 | 14 % |
| `add_settlements` | 12.6 | 0.87 | ~42 | 13 % |
| `fill_hamlets` | 17.2 | 0.57 | ~38 | 12 % |
| `add_beast_movements` | 3.6 | 1.10 | **~17** | 5 % |
| **Projected total** | **137** | | **~310 (5 min)** | |

Against ~4 750 s projected two rounds ago and ~790 s one round ago: **fifteen times cheaper
at 257 over two changes.** A size-257 world moves from "an hour and a quarter, if the memory
holds" to about five minutes, which is the difference between a size nobody runs and a size
somebody runs without thinking about it.

**No pass is a candidate for the same treatment any more.** The projected 257 cost is now
spread across five passes between 12 % and 28 %, none of them superlinear, and the largest
remaining exponent belongs to the pass with the smallest share. **A size-257 run is cheap
enough to measure rather than project** — and the memory that used to make that doubtful is
also gone, since peak resident at 128 fell from 2 823 MB to 1 069 MB in the last round. It
would also settle the size-192 crossing described below.

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

### `add_beast_movements` was the other superlinear pass — **closed 2026-09-21**

This section used to say: exponent 1.81, 35.8 s at size 128, here because of the exponent
rather than the seconds, projected to roughly 445 s at size 257. That is now history and the
numbers above supersede it. The pass is **3.60 s at size 128 and 2.6 % of the run**, its
exponent is 1.10 in situ and 1.47 on an isolated harness, and it projects to ~17–25 s at
257. The block it writes is byte-identical across the change at every size.

Four things were wrong with it, and each had grown with the world rather than with the
routes: a nearest-host scan that compared every follower against every group already routed;
an unbounded Dijkstra per group, cached at full map width so the cache alone reached 2.2 GB;
a re-scan of every cell in the world to recover the two hundred each search reached; and one
route built per group where a route depends only on the cell it starts from. See
[PERF-BEAST-MOVEMENTS-IS-THE-PASS](../board/done/PERF-BEAST-MOVEMENTS-IS-THE-PASS.md) and
[The fifth round](#the-fifth-round-add_beast_movements-and-the-memory-went-with-it).

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

**Peak resident is 1 069 MB at size 128, down from 2 823 MB, and the transient that made
the difference is gone.** Resident is 495 MB entering stage 16, peaks at 1 069 MB during it
and settles at 1 067 MB when it ends — so what is left is retained world state rather than a
spike. Before the 16:08 round it peaked at 2 823 MB during that stage and settled at
1 100 MB, a transient of 1 723 MB with nothing to show for it.

That transient was one pass. Timed around `add_beast_movements` alone on a baked size-128
world, with resident sampled during the call, it peaked **2 208 MB above entry**; it now
peaks **158 MB** above entry. It was caching a full-width distance and parent array for
every start node it searched from and never dropping one.

Peak memory across the ladder is now 187 → 473 → 766 → 1 069 MB, against
187 → 473 → 766 → 2 823 MB before. **The three smaller sizes are unchanged to the megabyte
and only 128 moved**, which is the shape to expect: below 128 something else sets the peak
and this pass never reached it. The 65 → 128 jump was 3.7× for 3.9× the cells and is now
1.4×, so the curve no longer steepens at the top and a size-257 run is memory-plausible
with far more room than it had. It has still not been attempted.

**The beast and monster work — the earlier rewrite, not this one — did not move memory at
all**: 379/460/711/2 775 MB then against 379/460/713/2 773 MB before it, identical within a
megabyte at every size while placing 40 % more nests. So the peak was never nest state, and
the round that finally moved it named the pass directly.

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
