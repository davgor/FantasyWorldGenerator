# BIOME-EXPOSED-ROCK-NEEDS-RELIEF — the one roster biome the default world cannot produce, and why the relief knob cannot buy it

> **RETIRED 2026-09-21 — removed from the backlog by owner instruction, not finished and not refused.**
> This card was **measured, ruled, and deliberately not fixed**. Biome 5 is absent because the relief term it needs was ruled out, not because nobody got to it. Completing it would override that ruling.
> **One recommendation in it is not recorded anywhere else and should not be buried with the card:**
> its “Ruling to write down” section proposes recording **raster 33 as the floor for a world that must
> contain every natural biome**, treating raster 17 as producing ten of eleven by construction. The only
> other mention in the tree is `docs/reviews/7d94bf5-end-of-day-handoff.md:518`, which lists it as still
> to be acted on. If that floor is wanted it needs a home in `docs/`, not in a retired card.
> Nothing here is a blocker. Read it for what it measured, not for what it instructs.

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** Biome **5 is absent** from the `natural_biome` histogram (present: 0, 2, 3, 4, 7, 8, 13, 15, 16, 17).
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: none. State: **measured, ruled, and deliberately not fixed.** Raised by the
biome-reachability lane under user ruling 3.0, 2026-09-20, on the tree after the wave-1
river-threshold and tombstone changes landed.

Ruling 3.0 asks that each natural biome be reachable through seed-driven generation, and adds
"keep the world size, adjust the earlier data". This card is the answer for the single biome
that fails, together with the measurement showing that the earlier datum the ruling points at —
the relief budget — **cannot be moved far enough to satisfy it**, and that moving it as far as
the config admits damages every configuration that already works.

## Observed behavior

Ten of the eleven surviving natural biomes appear at the default raster. `5 exposed_rock` does
not, in any seed.

Re-measured on the current tree at phase 10 (the earlier sweep predates the wave-1 river
threshold change and was re-run rather than cited):

| raster | seeds | union | `5` present in | max land slope |
|---|---|---|---|---|
| 17 | 0..231 | ten of eleven | **0 of 232** | 31.39 deg |
| 33 | 0..11 | all eleven | 2 of 12 | 46.88 deg |
| 65 | 0..5 | all eleven | **6 of 6** | 69.61 deg |

Per-seed presence at raster 17 over 232 seeds:

```
0 ocean        232/232      2 desert       222/232
13 marsh       232/232      3 grassland    205/232
16 cold_tundra 231/232      7 rainforest   202/232
15 boreal      228/232      8 lake          63/232
17 land_ice    228/232      5 exposed_rock   0/232
4 forest       224/232
```

Every seed 0-5 at raster 65 carries all eleven ids in a single world, so the biome roster is
reachable through seed-driven generation — just not at every raster.

## Mechanism — this is not a threshold story

Slope is a centred finite difference sampled along great circles. The denominator is fixed by
the raster:

```
gx = (around(angle,0)-around(angle,math.pi))/(2*radius*angle)
```

`Sim/icarus_sim/terrain_globe.py:86`, where `angle = math.pi/(n-1)` is one meridional grid step.
The baseline is therefore `2*radius*angle`, two meridional steps, and the steepest grade the
raster can represent is about (height difference over that baseline) / (that baseline).

On the 200 km default world the physical radius is 31830.99 m:

| raster | meridional step | centred-difference baseline | rise needed for 38 deg |
|---|---|---|---|
| 17 | 6250.0 m | 12500.0 m | **9766 m** |
| 33 | 3125.0 m | 6250.0 m | 4883 m |
| 65 | 1562.5 m | 3125.0 m | 2441 m |

The recipe relief budget is `DEFAULT_RELIEF_M = 1667.` at `Sim/icarus_sim/terrain_world.py:157`.
Realised height ranges run well above the budget once surface noise is added, but not by the
factor of six that raster 17 would need. Raster 33 halves the baseline and the biome appears;
raster 65 halves it again and every seed carries it.

`slope` is also absent from both rescale key lists in `apply_world_scale`
(`Sim/icarus_sim/terrain_area.py:30`), so the published degrees are the degrees the raster
measured, with no width correction applied afterwards.

Falsification probes, both reproduced on this tree, and both producing biome 5 at raster 17
without touching the classifier:

- `{'size': 17, 'phase': 10, 'relief_m': 3000, 'circumference_km': 200}` — biome 5 appears.
- `{'size': 17, 'phase': 10, 'circumference_km': 100}` — same 1667 m relief, half the cell,
  biome 5 appears.

Hypothesis FALSIFIED and recorded so it is not re-tried: octave admission is **not** the cause.
The resolved-octave ladder is 0 of 5 at raster 17, 1 of 5 at 33 and 2 of 5 at 65, so raster 17
resolves no surface noise at all — but forcing more octaves in by lowering the plate count does
not produce the biome, and raising relief does, at a raster where the octave count is still zero.

## Why the relief knob is the wrong lever, measured rather than argued

**Relief is a pure multiplier on the gradient field at every raster at once.** Generating one
seed at exactly double the relief budget (1667 m to 3334 m) and comparing the maximum land
slope:

| raster | slope at 1667 m | slope at 3334 m | ratio of tangents |
|---|---|---|---|
| 17 | 25.04 deg | 43.28 deg | **2.0159** |
| 33 | 46.88 deg | 65.00 deg | **2.0082** |
| 65 | 56.93 deg | 72.15 deg | **2.0217** |

The tangent of the slope tracks the relief budget to within 1 percent at all three rasters. That
is the whole finding: relief slides the entire ladder, it does not close the gap between one rung
and the next. Whatever it buys at raster 17 it buys twice over at 33 and four times over at 65.

The config guard bounds relief at `5*tectonic_relief + 2*amplitude < .9*globe_radius`, which
`max_relief_m` in `Sim/icarus_sim/terrain_scale.py:113` inverts to **3696.5 m at 200 km**. So the
knob has a hard ceiling barely twice the current default. Sweeping it to that ceiling at raster
17, twelve seeds per row:

| relief | rock at raster 17 | max land slope |
|---|---|---|
| 1667 m (default) | 0 of 12 | 25.0 deg |
| 2000 m | 0 of 12 | 29.3 deg |
| 2500 m | 0 of 12 | 35.2 deg |
| 3000 m | 1 of 12 | 40.3 deg |
| 3400 m | 1 of 12 | 43.8 deg |
| 3600 m (97.4% of ceiling) | 1 of 12 | 45.5 deg |

Widening to 32 seeds, 3000 m and 3600 m both give rock in **2 of 32 seeds**. At the largest
relief budget the configuration will admit, nine of ten default worlds still have no rock.

What that 2-in-32 costs everywhere else, same six seeds per row, rock as a share of land cells:

| raster | rock share at 1667 m | rock share at 3600 m | max land slope 1667 -> 3600 |
|---|---|---|---|
| 17 | 0.00% (0 of 266) | 0.37% (1 of 271) | 25.0 -> 45.5 deg |
| 33 | 0.18% (3 of 1670) | **1.47%** (25 of 1702) | 46.9 -> 66.7 deg |
| 65 | 0.95% (74 of 7750) | **4.09%** (322 of 7872) | 69.6 -> 80.3 deg |

Raster 33 goes from rock in 2 of 12 seeds to rock in 11 of 12. Raster 65 more than quadruples
its rock and reaches an 80 degree maximum land grade — a planet of cliffs.

There is a second cost that is a hard failure rather than a degradation. A relief default of
3600 m is 97.4% of the 200 km ceiling, and `shape_overrides` raises `ValueError` at the ceiling.
The narrowest world the recipe can currently build is about **90.2 km**; at a 3600 m default it
becomes **194.8 km**, so every world narrower than the small preset stops generating, with a
correct but surprising error about needing a wider circumference.

## Is there a raster-independent formulation?

No honest one, and it is worth writing down why, because it looks like there should be.

A 38 degree grade over a 12.5 km baseline is a 9.8 km rise. At raster 17 the smallest feature
the height field contains is one 6.25 km cell wide and zero of five surface-noise octaves
survive the Nyquist filter, so there is no sub-cell structure to measure. A raster-independent
slope would have to **invent** the fine grade rather than sample it: either by extrapolating from
a band-limited field, or by declaring the slope to be something other than what the terrain says.
Both publish a number the world does not contain, and `slope` is consumed by roads, harbours,
fjords, marsh eligibility and settlement siting, which would all then be reading fiction.

The measurement is not wrong. Raster 17 is a genuinely smooth planet. `5 exposed_rock` is absent
from it for the same reason a 60 metre contour map has no cliffs.

## Ruling to write down

**Do not lower the 38 degree threshold** at `Sim/icarus_sim/terrain_biomes.py:43`, ported at
`Core/biomes.cpp:84`. Raster 65 already puts every sampled seed over 38 degrees; a lowered
threshold floods every large world with rock while barely moving the default one.

**Do not raise the relief budget to chase this.** The measurements above are the reason: the
maximum admissible budget buys rock in 2 of 32 default worlds while quadrupling it at raster 65,
pushing maximum grades to 80 degrees, and making every world narrower than 195 km ungenerable.
This is the desert lesson one raster lower — a knob tuned against the degenerate corner does not
merely fail to help, it damages the configurations that were working.

**What is recommended instead:** record raster 33 as the floor for a world that must contain
every natural biome, and treat raster 17 as producing ten of eleven by construction. A recorded
`(seed, size)` witness is what "reachable through seed-driven generation" means here, exactly as
the desert ruling treats dryness.

The reachability contract is pinned by `Sim/tests/test_biome_reachability.py`, which records the
witnesses, asserts the default raster does not carry `5`, and states the mechanism as arithmetic
so a future change to the relief budget or the raster shows up as a test failure rather than as a
quietly missing biome.

## If someone does decide to move it anyway

The lever is one constant and it is **not** in this lane's files:

- `Sim/icarus_sim/terrain_world.py:157`, `DEFAULT_RELIEF_M=1667.`

It is seed-changing for every world at every raster and preset, it invalidates every saved world
(permitted under [023-world-compatibility-policy](../../docs/decisions/023-world-compatibility-policy.md)),
and the comment immediately above it — relief stays constant across the three presets rather than
scaling with circumference — is the design statement that would be reversed. There is no native
mirror to update: `Core` never adopted the circumference presets at all, as
[SCALE-METRE-CONSTANTS-COLLAPSE](../backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md) records.

## Not owned

Pre-existing. Surfaced by the biome-reachability sweep of 2026-09-20. Related:
[PRODUCT-REACHABILITY-REPORT](../done/PRODUCT-REACHABILITY-REPORT.md), which raises the general form —
authored and reachable are different numbers and only the first is ever reported — and whose own
evidence is drawn from the archived world documents this lane has just shown do not describe the
current tree.
