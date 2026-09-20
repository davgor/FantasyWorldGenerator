# SCALE-METRE-CONSTANTS-COLLAPSE — absolute metres authored for an 11.15 km world, still in the code at 200 km

Owner: none. State: two members fixed in the working tree, five open. Raised by the
published-layer regression lane under user ruling 2.0, 2026-09-20; a sixth member found
and carded by the regression follow-up lane the same day.

This is a **class**, not a bug. Commit `21df9aa` ("checkpoint", 2026-09-19) moved the default
world from 11.15 km around to 200 km and derived `globe_radius`, `tectonic_relief`, `amplitude`,
`wavelength` and `orogeny` from the requested width. It did not move the constants that are
written in **absolute metres**. Every one of those constants was authored against a world
eighteen times smaller, and each has silently stopped spanning anything.

The failure mode is always the same and is always invisible: the constant does not error, it
stops discriminating. A published layer becomes a constant, and every consumer downstream reads
a field that is the same everywhere and concludes nothing is special anywhere.

**None of this was a generator regression.** Recomputing the island rule against all twelve
worlds under `Artifacts/` reproduces the published layer cell-for-cell for generators 8 through
16 alike. The variable was the world's width, not the generator's version.

## Members

| constant | where | authored for | at 200 km | state |
|---|---|---|---|---|
| `min(3e6, land_total*.15)` island floor | ecology islandness | 3 km² component | smallest possible component is 15.2 km² at size 17 → layer identically 0 | **fixed** |
| `river_threshold_km2` 0.15 | climate / water | 0.15 km² catchment | every land cell drains more → every land cell a river | **fixed** |
| `max(.01, min(1, area/110))` auto river threshold | `terrain_recipes.derive_water`, `Sim/icarus_sim/terrain_recipes.py:57` | a catchment in absolute km², hard-capped at **1 km²** | 1 km² is 48x below the 48.27 km² a 200 km world resolves → saturated rivers again | open, dead on recipe 3, see below |
| 180 m wetland margin | biomes `wetland_access` | 180 m from water | **0 of 1888** grid edges are ≤ 180 m; shortest is 2423.6 m | open |
| `water_reach` 400–650 m, `college_water_reach` 600–850 m | all 13 population profiles | 400–650 m to fresh water | measured freshwater distances reach 20745 m → `exp(-d/reach)` is a step function | open |
| `exp(-distance/80)` flood decay | settlements `flood` | 80 m decay length | flood_risk is a binary river mask, not a gradient | open, see below |
| `nest_settlement_clearance` 250 m | beast nests | 250 m from settled anchors | under one tenth of a cell edge at size 17 | open |

Already fixed, and the precedent for the rest: `settlement_spacing`, `support_reach`,
`culture_link_cost` (scaled by `reach_scale`) and `wavelength` (derived from the radius).

### The precedent carries a live silent clamp of its own, 3% from the large preset

Found while fixing the river half, not previously carded. The three reach keys are scaled as
`min(ceiling, raw[key]*factor)` with a 100000 m ceiling. That `min` is the same
absolute-versus-relative arm swap as the island floor, and one of the three is already close to
swapping:

| key | base | ceiling binds at |
|---|---|---|
| `settlement_spacing` | 450 m | 2477.5 km |
| `support_reach` | 1000 m | 1114.9 km |
| `culture_link_cost` | **1800 m** | **619.4 km** |

The large preset is **600 km**. `culture_link_cost` resolves to 96870 m there — **3.2% of
headroom**. A world authored at 620 km or wider silently stops scaling it, with no error and no
log line, and cultural regions quietly stop growing with the planet while everything around them
keeps scaling. Nobody has generated a world in that range yet, which is the only reason this has
not been observed.

The new `river_threshold_km2` derivation deliberately **raises** instead of clamping, naming the
circumference and the bound, so the same class does not recur in the code added by this fix. The
three reach keys were left alone because changing them is a seed-affecting retune outside the
ruling that authorised this one — but they should be converted to the same raise-don't-clamp shape
in whichever change next touches them.

### The 180 m wetland margin is the sharpest open one

The margin is a hard cutoff in a dijkstra relaxation, so it does not degrade — it simply admits
nothing. Measured on the live 200 km world at size 17: **0 of 1888** sphere-grid edges are within
180 m, against 64 of 1888 on the 11.15 km reference world and 27520 of 32128 at reference size 65.
Marsh (biome 13) can therefore only be assigned to a cell that is *itself* water or river; the
"near water" case it was written for cannot occur at any raster the generator ships.

This couples to the biome-reachability work under rulings 0.2 and 3.0: the river-threshold fix
already moves the biome histogram, so any reachability sweep taken before this lane landed is
stale and must be re-run.

## Scaling is not optional, and the units decide the exponent

Reaches take the width factor. **Catchments take its square.** That distinction is the whole
content of the river half of this fix, and it is the thing a future reader will "simplify".

Measured, at a fixed raster and seed, generating seed 42 size 17 at 200/400/600 km: per-cell
`rain_runoff` grows by exactly **4.000000** at double the width and **9.000000** at triple, on all
47 land cells. Widening the world does not move the rainfall field — climate runs on the same
normalised sphere grid — so runoff follows cell area exactly, and cell area is a square.

Applying the square makes the river network **width-invariant**, which is the property being
bought:

| | size 17 | size 33 | size 65 |
|---|---|---|---|
| 200 km, unscaled 0.15 km² | 100.00% | 99.63% | 85.18% |
| 400 km, unscaled 0.15 km² | 100.00% | 100.00% | 93.78% |
| 600 km, unscaled 0.15 km² | 100.00% | 100.00% | 96.59% |
| 200 km, derived 48.27 km² | 68.09% | 47.76% | 16.01% |
| 400 km, derived 193.08 km² | 68.09% | 47.76% | 16.01% |
| 600 km, derived 434.44 km² | 68.09% | 47.76% | 16.01% |

(land-river fraction, phase 9, seed 42. Identical at all three widths under the derived value.)

**What is deliberately NOT claimed:** that the live 200 km world's runoff is 321.8x the archived
11.15 km world's. It is not — per-cell growth between those two spans 13.2x to 764x — because
`21df9aa` re-derived wavelength, relief, amplitude and orogeny along with the radius. Those are
two different planets, not one planet at two widths, and comparing them does not test this factor.
An earlier draft of this fix cited that cross-planet comparison as its derivation; it does not
support one.

### The calibration, so the next person can retune with data instead of taste

Target: a land-river fraction that is neither saturated nor empty at sizes 17, 33 and 65, and that
does not drift with world width. Sweeping the factor at 200 km, seed 42 (phase 9, ~4 s per row):

| factor | threshold | size 17 | size 33 | size 65 |
|---|---|---|---|---|
| 1 | 0.15 km² | 100.0% | 99.6% | 85.2% |
| 100 | 15.0 km² | 91.5% | 63.8% | 33.1% |
| 220 | 33.0 km² | 78.7% | 53.7% | 21.8% |
| **321.8** | **48.27 km²** | **68.1%** | **47.8%** | **16.0%** |
| 1000 | 150 km² | 59.6% | 29.9% | 0.9% |
| 3218 | 482.7 km² | 44.7% | 0.8% | 0.0% |
| 10000 | 1500 km² | 2.1% | 0.0% | 0.0% |

The band satisfying the target at every raster is roughly 100x to 1000x. The factor maximising the
worst-case margin from both saturation and emptiness is a plateau near **200–220** (margin 0.213,
binding at size 17); `reach_scale²` = 321.8 scores 0.160, binding at size 65. The square was kept
anyway, because it is the dimensionally correct scale-free form and it is what buys the
width-invariance above — a bare 220 would hold at 200 km and drift at 400 and 600. If someone
wants the extra margin at size 65, retune the **base** 0.15, not the exponent.

## The island rule's real range — it is not "one cell everywhere"

The replacement rule is "a component holding under 15% of this world's land". Measured on the
published layer at phase 12:

| seed | size | land cells | island cells |
|---|---|---|---|
| 42 | 17 | 47 | 1 |
| 42 | 33 | 268 | 42 |
| 42 | 65 | 1174 | 77 |
| 43 | 17 | 48 | 14 |
| 43 | 33 | 271 | 36 |
| 43 | 65 | 1182 | 166 |
| 45 | 17 | 102 | **0** |

Seed 45 is the honest counterexample and belongs here: its land is two components of 49 and 53
cells, at 2.6x and 4.0x the cut, so nothing reads as an island. That is defensible — a world of
two continents has no islands — but it means **"at least one island cell" is not an invariant**,
and the regression test asserts it only for the seeds and rasters actually measured.

The rule is also raster-sensitive at coarse grids: at seed 42 size 17 the 11-cell component sits
only 6% above the cut. Expect the count to move with size.

**Open, and not settled by this fix:** nobody has stated what `island_habitat` is *for* beyond the
`islander` community trait and the `quarantine_isle` site. 15% is scale-free, raster-free and
reproduces every archived world exactly, which is why it was chosen — but on a world of seven
comparable landmasses every one of them reads as an island. Settle it by asking what the trait
should mean, not by tuning the number.

## Correction to the flood_risk finding

An earlier draft reported flood_risk as collapsing from "45 of 1062" to "47 of 47". **Those are
different rasters** — the reference figure is size 65 and the live figure is size 17 — and the
comparison overstates the regression badly.

At the **same** raster, the 11.15 km reference world was already saturated: `Artifacts/city-planner/world.json`
(size 17, 39 land cells) reads flood_risk == 1.0 on **35 of 39**, freshwater distance 0 on 35 of 39,
rivers on 35 of 39. So the true size-17 regression is **89.7% → 100%**, not 4.2% → 100%, and both
the saturation and the `holy_well` fails-open behaviour **pre-date** the 200 km world. Post-fix the
same raster reads 32 of 47 (68.1%).

This is why the new regression test asserts a **fraction bound** rather than "not identically 1.0":
the weak form would have passed the reference world by four cells.

`exp(-distance/80)` is left unscaled deliberately. Scaling it would change reference behaviour
rather than restore it — flood_risk was a river mask on the 11.15 km world too. Documented, not
fixed. Falsified if someone wants a flood gradient rather than a mask.

## `-1` in freshwater_distance means unreachable, not water

Worth recording because two separate analyses of this defect called it "the water sentinel" and one
proposed asserting `-1 count == water cell count`. It is `math.inf` substituted at publish time: no
freshwater **source** is reachable from that cell. Before this fix every land cell was its own
source, so nothing on land could be infinite and `-1` fell exactly on the water cells, which is
where the misreading came from.

It no longer does. Seed 42 size 33 has **one land cell** at `-1`: a single-cell island with no
river on it, correctly unreachable. The proposed equality is therefore **false on a correct world**
and asserting it would have failed this fix rather than guarding it. The real invariant, and the
one the test asserts, is that `-1` never lands on a river cell.

## The native gap behind all of this

`Core` never adopted `WORLD_SIZE_CIRCUMFERENCE_KM` at all. Its `world_size` presets still resolve
to `10000. * multiple` design radius — **11.15 / 22.3 / 33.4 km** physical — against the
reference's 200 / 400 / 600 km. The comment claiming the preset resolves "exactly as the reference
resolves it" was stale and has been corrected in place.

The consequence is subtle and worth stating plainly: Core's own `river_threshold_km2 = .15` default
is **correct on Core's world** and wrong on a reference-shaped one. So this is not a constant to
"fix" in `Core/config.hpp` — doing so would bake one planet width into the core. The parity route
is the one taken here: the harness passes the resolved value through the override chain, which had
to learn the key first because it throws `INVALID_INPUT` on any name it does not list.

Also noted while here: `world_shape_overrides` has **no caller** anywhere in `Core/`, `Sim/`,
`tests/` or `tools/` — only its definition and its header declaration. An earlier draft of this
fix planned to extend it. That would have been unreachable, untested and untestable code, and it
was dropped. Deriving world shape natively is a real gap; extending a dead function is not the
way to close it. Related: `NATIVE-PARITY-HARNESS-SHAPE.md` and `PRODUCT-RUNTIME-PARITY-LEDGER.md`.

### A second producer of the same constant, currently unreachable

`terrain_recipes.derive_water` (`Sim/icarus_sim/terrain_recipes.py:57`) sets
`river_threshold_km2 = max(.01, min(1, area/110))` from the generated above-sea land area.
It carries **both** halves of the defect class at once:

- the value is an absolute km² catchment, derived from an area but not from the world's
  width, so it does not scale with circumference the way the recipe-3 path now does; and
- it is a `min(<absolute>, <relative>)` pair — the exact shape flagged under "How to find
  the next one" below — with the absolute arm at **1 km²**. On the 200 km default world
  the recipe resolves 48.27 km², so this producer's hard cap is **48x too small** and
  would return the rivers to the saturated state the fix just left: measured, the
  unscaled 0.15 km² gives a land-river fraction of 100% / 99.6% / 85.2% at sizes
  17 / 33 / 65, and 1 km² is far inside that saturated band (the sweep in
  "The calibration" above puts even 15 km² at 91.5% / 63.8% / 33.1%).

**It is dead code on recipe 3**, which is why nothing is red: the recipe-3 request path
derives `river_threshold_km2` itself in `terrain_world.generate_request` and
`derive_water` only runs behind `cfg.auto_parameters`. It is filed anyway because a dead
producer of a live constant is a loaded gun — the moment `auto_parameters` is reached on
a wide world it silently overwrites the derived threshold with a value two orders of
magnitude too small, and the failure mode is the invisible one this whole card is about.

Fixing it is a one-line change to a **pinned** file that this lane does not own, so it is
carded rather than done. Whoever takes it should either scale the bound by
`terrain_scale.runoff_scale(circumference)` like the recipe-3 path, or delete the function
if the `auto_parameters` path is genuinely retired — but not leave it as it is.

## How to find the next one

The tell is a numeric literal in metres, or an area in km², sitting next to a distance that comes
from `sphere_grid`. Grep for bare decay constants inside `exp(-d/...)`, for comparisons against
`<= <number>` on a graph edge, and for any `min(<absolute>, <relative>)` pair — that last shape is
the specific trap, because it reads as a safety clamp and behaves as an arm swap the moment the
relative term grows past the absolute one.

Worlds are disposable until the first player-facing consumer ships, so fixing these is a retune,
not a migration.
[023-world-compatibility-policy.md](../../docs/decisions/023-world-compatibility-policy.md)
