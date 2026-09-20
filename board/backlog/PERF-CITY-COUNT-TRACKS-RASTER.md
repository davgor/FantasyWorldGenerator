# PERF-CITY-COUNT-TRACKS-RASTER — settlement count follows the grid, not the ground

Owner: none. State: backlog, unowned. Raised by the generation-performance pass, 2026-09-20.

This is the reason a full-depth 513 world is unreachable. The grid ceiling was raised to
1025 in `4713f9a` and that change is complete, but it does not make a phase-16 world at 513
generatable — this does. Anyone reading the ruling as fully delivered should read this card
first.

## Observed behavior

Same seed, same planet, same settings. Only the sampling grid changes.

| | size 17 | size 33 | growth |
|---|---|---|---|
| cells | 289 | 1,089 | 3.77x |
| `area.land_km2` | 2,486.7 | 3,664.9 | 1.47x |
| `settlements.sites` | 9 | 40 | **4.44x** |
| `hamlet_plans` | 13 | 108 | 8.31x |
| `castle_plans` | 4 | 64 | 16.0x |
| `npcs` | 2,296 | 9,566 | 4.17x |
| km² of land per city | 276.3 | 91.6 | **0.33x** |

Land area does grow with the raster — a finer grid resolves coastline the coarse one
misses, which is expected and is not the finding. The finding is that settlements grow
**three times faster than the land does**: density per square kilometre roughly triples
between size 17 and size 33.

Cross-seed evidence separates the two effects. Seed 73 at size 17 carries 5,433.8 km² of
land against seed 42's 2,486.7 — 2.2x the land at identical settings — and 23 cities, or
236.3 km² per city against seed 42's 276.3. **At a fixed raster, two seeds with very
different land areas agree on density within 15%. Across rasters at a fixed seed, density
triples.** The dependence is on the grid, not on how much ground there is.

## Why this is a defect and not a tuning value

`docs/nomads.md` states the opposite rule as design intent, for the bands it owns: counts
follow habitable area "so the count follows the ground rather than the raster: the same
world holds the same bands at any grid size." Settlement placement does not hold to that.

The consequence is that grid size is not a level-of-detail control. It is a content
control wearing a level-of-detail label: raising it does not sample the same world more
finely, it produces a different world with more in it.

## Why it is the barrier to 513

Measured cost is `city count x per-city cost`, and the per-city cost is raster-independent:
`city_planner.plan_city` samples a **local metre grid** (`CELL=4`, half-extent 240/320/400 m
by city class), roughly 40,000 terrain cells plus a `(size+1)²` surface grid, at five
detailed `HeightField.height` evaluations per terrain cell — about 240,000 multi-octave 3D
Perlin evaluations per city regardless of world size.

At size 17, on the tree at `651ab00`, with every producer wrapped and exclusive time
charged (41 of 41 instrumented, none skipped):

| producer | executions | share |
|---|---|---|
| `add_nests` | 10 | 49.2% |
| `fill_cities` | 1 | 44.6% |
| `fill_hamlets` | 1 | 2.4% |
| `age_transition` | 2 | **26 ms exclusive** |

`add_nests` and `fill_cities` are **93.9%** of the run between them.

Two corrections to earlier figures from this pass, recorded because they were published
before they were corrected. `add_nests` was reported as 9.0% and `age_transition` as 39.4%:
the first instrument charged exclusive time by suppressing any wrapped call nested inside
another wrapped call, which is correct only for a producer that runs once. `add_nests` runs
ten times from four sites, four of them inside `age_transition`, so its time was charged to
its caller. `age_transition` is not a producer at all — it is a scheduler, and 99.9% of the
time credited to it belonged to ten producers running inside it.

Every share above is from the tree at `651ab00`. The earlier `fill_cities` figure of 46.2%
was taken **before** `422f9c3` and is not comparable: that commit moved `fill_cities` -8.0%
and `fill_hamlets` -7.8%. Do not reconcile a pre-`422f9c3` share against a post one.

The size-33 shares quoted earlier in this pass (`fill_cities` 36.9%, `age_transition`
44.1%) came from the defective instrument and are **withdrawn**, not corrected — a
corrected size-33 run has not been taken.

Extrapolating the observed 0.035 cities per cell to 513 (263,169 cells) gives roughly
**9,000 cities**, which at the measured per-city cost is hours of city planning alone. So
a phase-16 world at 513 is not currently generatable in a sitting, and that is unrelated to
the ceiling that was just raised.

## What is NOT the fix

- Not a constant-factor optimisation. `422f9c3` removed genuinely wasted work from the
  hottest producer (a full sampler call per surface-grid point where only the elevation was
  read) and bought 5.6%. Nothing of that shape closes a 100x gap.
- Not the grid ceiling. That is landed and correct, and it is what lets a 513 world be
  aged at all. It does not change how many cities a 513 world asks for.
- Not the tier-3 wonder zero. That is a separate area-scaled rounding defect with its own
  evidence; see the note below.

## Proposed direction, not a decision

Make settlement count follow habitable area the way `docs/nomads.md` already specifies for
bands, so that grid size changes how finely a world is sampled and not how much is in it.
The repository already contains the shape for an area-derived count that must not round to
zero: the thinned draw in `terrain_nests._place`, `floor(lambda) + [u < frac(lambda)]`.

## What this will cost, and why it needs a ruling rather than an implementation

**Every existing world changes.** Settlement placement is upstream of ruins, roads, culture
regions, heroes, the story web, npcs, key locations and nomads. This is a seed-changing
change to a public contract, it needs its `Core/` port in the same change, and it interacts
with PRODUCT-WORLD-DISPOSABILITY-DECISION, which is unruled. It is not a performance fix
that can be landed quietly on the grounds that it makes things faster.

## Evidence

Seed 42 and seed 73, phase 16, published documents (no `build_stages`, no `timing_ms`),
Windows 11, CPython 3.12, machine contended — shares are reliable, absolute times inflated.
Profiler wrapped producer entry points by module attribute, charged exclusive time with a
stack (children subtracted from parents), reported its own coverage explicitly rather than
skipping silently, and accounted for 99% of wall time. Per-producer shares and the entity census are in the generation-performance pass
transcript; the documents themselves were generated at seed 42 sizes 17 and 33 and seed 73
size 17.

## Does not establish

- That density keeps tracking cells above size 33. Two sizes cannot distinguish linear in
  cells from mildly superlinear, and the 9,000-city figure for 513 is an extrapolation from
  two points, not a measurement. A third size bounds it; a cost ladder at 33/65/129 was in
  flight when this card was written.
- That settlement placement is the only raster-bound count. `key_locations` (98 to 247) and
  `beast_nests` (369 to 1,023) also grew, and neither was traced to its placement rule.
- Anything about the tier-3 wonders reporting `wanted: 0` with 24–289 qualifying candidates.
  That zero does not move when land doubles (seed 73 carries 2.2x the land and still raises
  none), so it is an area-scaled expectation rounding to nothing rather than a raster
  effect, and raising the grid ceiling will not produce them.
