---
conformance: 1
record: creature-placement
tier: EXERCISED
summary: Places the creature catalogue on the ground as two independent thinned point processes - animal hunting grounds and monster territory - at a rate that is a geometric pyramid in danger tier and slides outward from settled ground with it, and publishes the gap between that rate and what the raster could hold, species by species and tier by tier.
modules:
  - Sim/icarus_sim/terrain_nests.py
emits:
  - path: wildlife
    schema: (none; declared as an object in Contracts/schemas/world-output.schema.json)
  - path: beast_nests
    schema: (none; declared as an object in Contracts/schemas/world-output.schema.json)
versions:
  - id: wildlife
    assert: 3
  - id: beast-nests
    assert: 4
proof:
  - path: Sim/tests/test_terrain_nests.py
    establishes: that the rate falls strictly with danger tier and tracks habitable area, that the placed set never exceeds the cells its tier reaches, that a wider world holds strictly more, that an animal is territorial only within its species and a monster only within its tier, that every monster tier reaches the open ocean, that the catalogue and the danger ramp are both pyramids, replay and block isolation, and the disable and cap controls
  - path: Sim/tests/test_nest_diagnostics.py
    establishes: that the danger ramp puts the top tier measurably further from settled ground than tier one in the rate, that the placed set carries less of that gradient than the rate does, that every profile carries a reason from a fixed vocabulary, that a species the settlement clearance alone refuses is named as such rather than as a world reason, that the reachability integers agree with the rows and the sites, and that the provable unreachable set stays strictly smaller than the set this world merely lacks
  - path: Sim/tests/test_creature_movement.py
    establishes: that no creature clears its hard gates and then fails to score anywhere, decomposed from the two ordinary reasons a creature is absent from a particular world
decisions: []
tickets:
  - board/done/BESTIARY-PYRAMID-RETUNE.md
  - board/done/BESTIARY-BRIMSTONE-BATS.md
  - board/done/CONTENT-NO-DIFFICULTY-GRADIENT.md
  - board/done/PRODUCT-REACHABILITY-REPORT.md
---

# Conformance: creature placement

## What it produces

Two blocks, from two passes that never read each other. `wildlife` holds animal hunting
grounds; `beast_nests` holds monster territory over the same ground. Each site is a centre,
a `range_m`, a species, a danger `tier` of one to five, and the suitability score that put
it there. `den` marks the sites that are a findable place to raid rather than only a range
where the creature is met.

Each block also carries `diagnostics`, one row per species with what it placed, how many
`cells` it could have lived in and a `reason` it is not here; `saturation`, one row per
tier with the raster `cells` that tier can reach, the groups the rate `drawn`, what was
`placed`, what territory `refused`, and the two distances `rate_distance_m` and
`placed_distance_m`; and `reachability`, four integers and a scope line.

`saturation` is there because the two halves of this pass disagree and a reader cannot tell
which one a histogram is describing. The rate is an exact geometric pyramid — on the
reference world, monster draws by tier are 6762 / 3305 / 1716 / 862 / 429, each about half
the one below. What is placed is 350 / 359 / 304 / 277 / 204, which is nearly flat. The
difference is not ecology.

(Re-measured 2026-09-21 on seed 42, size 33, phase 13 — the world `test_terrain_nests.build()`
makes. An earlier revision of this paragraph read 6747 / 3323 / 1707 / 868 / 438 and
376 / 381 / 312 / 292 / 211, which reproduces on neither that world nor the threefold one
beside it; the threefold world reads 20295 / 10072 / 4991 / 2541 / 1324 drawn and
368 / 376 / 347 / 314 / 296 placed. Quote the block, not this paragraph, if the two ever
disagree again.) Placement resolves at the raster cell: every site in a cell carries that
cell's own direction, so two sites in one cell are at distance zero and the second is
always refused. A tier therefore holds at most one lair per cell, a species at most one den
per cell, and any tier whose rate exceeds the cells it reaches is pinned at that ceiling.
That ceiling is the finding behind `saturation` and it is not in question.

The reasoning this record used to give for it was wrong, and the sentence is worth
correcting rather than deleting because it is the sentence that invites an incorrect
optimisation. It read: no species' territory is as wide as the raster pitch at any width
this product ships, so the spacing test only ever compares a cell against itself. The grid
is lat/lon. The meridional pitch is uniform but the zonal pitch collapses by `cos(lat)`, so
the ring beside a pole is packed about `pi/(n-1)` as tight as the equator — 2.4 m against a
391 m equatorial pitch at size 513 on a 200 km world — while territory is 1,750 m at the
default `nest_spacing` and 7,000 m at the 4.0 the control allows. Cross-cell refusals are
therefore ordinary polar ground: measured at seed 42, size 65, 426 of 9,777 monster
refusals and 50 of 47,311 animal refusals have their blocker in another cell. What
`terrain_nests._blocked` actually relies on is the bound that is true — latitude difference
is a lower bound on great-circle angle whatever the longitudes do, so a blocker must lie
within `max(reach, widest)/pitch` grid rows. See board/NEST-SAME-CELL-CLAIM-IS-FALSE.md,
which also records that no test pins cross-cell territory at all.

The danger gradient is the second thing that ceiling swallows, and `saturation` reports it
the same way. `rate_distance_m` is the mean distance from settled ground of the groups the
rate asks for, weighted by the rate; `placed_distance_m` is the mean distance of the sites.
On the reference world the monster rate runs 4910 / 5285 / 5051 / 5565 / 6184 m and the
placed set runs 5730 / 5706 / 5281 / 5426 / 5787 m — the rate carries 1.27 km end to end
and the sites carry 0.51 km, because at this raster every tier is 60% to 98% of the way to
its cell ceiling and a saturated tier fills the cells it reaches whatever the rate said
about which of them it preferred.

Neither series is monotone across all five tiers, and the tier that breaks both is tier
three — the ramp's own pivot. `danger_ramp(3, d, span)` is `(1 + NEST_DANGER_FLOOR) / 2` at
every distance, so tier three is pushed neither in nor out and sits wherever its habitat
puts it. Its `rate_distance_m` is identical in every ablation arm, 5051 m for monsters and
5771 m for animals, while every other tier moves. **A five-tier ladder is therefore not
something this mechanism can produce at any tuning on any world**, and that is a property of
the shape rather than of the constants. Across the four tiers it does move, the rate is
strictly ordered: 4910 / 5285 / 5565 / 6184 m.

`reachability` is `authored`, `eligible`, `placed` and `never_satisfiable`. On the reference
world: 680 / 561 / 453, with 25 provable. The middle two are this world's and move with the
seed — 53 of 680 profiles change eligibility across five seeds at one raster, so a per-world
count is a sample and the `scope` string in the block says so. `never_satisfiable` is decided
from the profile alone — a `requires` on a ley school generation can never raise — and is the
only verdict here that holds for every world.

`diagnostics.reason` takes one of the five values in `REACH_REASONS`. The fifth,
`its only ground is inside a settlement clearance`, exists because graveyard and barrow
creatures — whose `graves` habitat is the ground settlements stand on — can score only on
cells `nest_settlement_clearance` refuses. They are unplaceable because of a placement rule,
not because the world lacks their conditions, and reporting them as a world reason sends a
reader to look at terrain that is fine. How many there are is a property of the world and
not of the catalogue: 57 on seed 42, 32 on seed 7, 1 on seed 73, all at size 33.

Reference world, monsters: 167 placed / 107 lost the draw / 57 cleared out / 25 never
satisfiable / 13 conditions absent. Animals: 286 / 1 / 0 / 0 / 24.

## Entry points

`add_nests(result, cfg)`, which runs `add_animals` then `add_monsters`. Both are gated on
`cfg.world_recipe` and `cfg.phase >= 7`. `terrain_history` re-runs both around every age
boundary and writes `beast_nests.evaluated_age`.

`profiles()`, `roles()`, `biome_weight()`, `suitability()`, `habitat_cells()`,
`tier_density()` and `danger_ramp()` are the published pieces; `terrain_beast_movement`,
`terrain_encounters`, `terrain_visitation`, `terrain_religion`, `terrain_corruption`,
`terrain_leyline_history`, `hero_generator`, `key_locations` and `npc_roster` all read one
or both blocks.

## Inputs it reads

`result['layers']` through `habitat_cells`, which resolves each cell's medium, depth,
dryness, coast, mountain, plains, wetland and cold from the raw fields; the natural biome
id; `settlements.sites`, `fisheries.ports` and `humans.hamlets` for clearance; the globe
radius; and `terrain_nest_profiles.json`, which holds 680 species and 21 feeding roles.

The world options it reads are `nest_density`, `animal_density`, `monster_density`,
`nest_fantasy`, `animal_tier_falloff`, `monster_tier_falloff`, `nest_spacing`,
`nest_min_suitability`, `nest_settlement_clearance`, `nest_per_species`, `nest_limit` and
`nest_variation`.

## Artifacts it writes

`result['wildlife']` and `result['beast_nests']`, each with `version`, `sites`,
`diagnostics`, `saturation`, `profiles`, `catalogue_count`, `method` and `limits`;
`wildlife` additionally carries `roles`. Neither has a schema of its own. Both are declared
as objects in the world output schema and are exported to the native catalogue table by
`tools/export_catalogues.py`.

## Where it runs

In process, inside generation, at stage `beasties` and again around each age boundary. No
I/O beyond reading the profile document, which is cached.

## Versions asserted

| What | Value |
|---|---|
| `wildlife` block | <!-- conformance:version wildlife=3 --> |
| `beast_nests` block | <!-- conformance:version beast-nests=4 --> |

`wildlife` moved to 2 when `saturation` was added. That is additive — no field of a site
changed and no site moved — but it is the field that tells a consumer whether a flat tier
histogram is the ecology or the raster, so a document without it is not the same document
to read.

`wildlife` 3 and `beast_nests` 4 are the same kind of move and landed together: the two
distance columns on `saturation`, `cells` and `reason` on every `diagnostics` row, and the
`reachability` summary. Additive again — no site moved and no existing field changed — and
again the addition is what makes the rest legible. A reader holding version 2 sees a flat
distance histogram and a species with `placed: 0` and cannot tell a clipped gradient from
no gradient, or a creature this world lacks from one no world can hold.

`beast_nests` moved to 3 for `saturation` and for a rule change that moves every site. A
lair used to be refused by an equal **or greater** lair; it is now refused by an equal only.
The prose in three places already said the second thing — "a greater monster excludes an
equal, and tolerates a lesser", "a dragon's range may contain a goblin camp" — and the code
said the first, so a lesser lair nested inside a greater territory only when the draw
happened to reach it first. Refusing by rank also refused the pyramid: a tier one candidate
was held off by every lair on the world while a tier five was held off only by other tier
fives, which on a world three times the reference area put tier five **above** tier one.

## Proven by

`Sim/tests/test_terrain_nests.py` builds a reference world and a world of three times its
surface, and asserts the rate and the placed set separately, because they are different
claims:

- `test_pyramid_and_overlap` — `saturation.drawn` falls strictly with tier on both passes
  and both worlds; `placed` never exceeds `drawn`; the placed histogram equals
  `saturation.placed` row for row; tier one still outnumbers the top tier; and no
  `beast_nests` tier places more sites than it has cells.
- `test_population_scales_with_the_ground` — the rate tracks habitable area to within 30%
  across a threefold change in surface, and a wider world holds strictly more sites, which
  is what a reintroduced anchor cap would break.
- `test_every_monster_tier_reaches_the_open_ocean` — no monster tier reaches fewer than
  half the sea cells the widest tier reaches.
- `test_greater_monsters_hold_ground_against_equals_only`, `test_constraints_and_finite`,
  `test_animals_are_territorial_only_within_a_species`, `test_replay_and_isolation`,
  `test_disabled_and_capped`, `test_phase_gate`.
- `Sim/tests/test_creature_movement.py::test_no_creature_passes_its_gates_and_still_cannot_score`
  and `::test_the_unplaceable_are_unplaceable_for_world_reasons` decompose absence into an
  authoring defect and two ordinary facts about a particular world, and assert only on the
  first. Its exclusion list is empty.

## Why it works this way

The pyramid is a claim about the world, so it is budgeted for the world rather than per
cell: tier `t` gets `density * falloff^(1-t)` groups per square kilometre of its own medium,
renormalised over whatever ground the tier can actually use. Sharing per cell instead loses
a tier its share wherever no member qualifies, and the specialised low monster tiers were
measured to invert the pyramid outright that way.

Land and open water are budgeted apart, because a species belongs to one of them and
budgeting together let the sea decide how empty the land was.

Settlement clearance and the danger ramp live in the rate rather than rejecting a draw that
already happened; a rejected draw quietly empties the world below the density asked for.

The refusal test is scoped to the candidate's own bucket — its species for an animal, its
tier for a monster — rather than scanning every site already placed. That is the same
predicate over a small slice of the list instead of all of it, and it is what keeps this
pass affordable: it is the dominant cost of a generation, and scanning the whole placed
list is quadratic in it.

Habitat breadth per tier is the real ceiling on the placed histogram, which is why one
missing species can show up as a tier-wide hole. Tier three had four marine species, all
of them gated on a reef or a ley school, so it reached 37 of 724 sea cells against 230 to
260 for every other tier — on a world three quarters water, that alone put tier three at
97 placed against tier four's 209.

## Does not establish

It does not establish that the placed histogram is a pyramid, and at the raster this
product ships it is not: tiers whose rate exceeds their cells are all pinned at the same
ceiling and read flat. The pyramid is asserted where it is exact, on `saturation.drawn`.

It does not establish that the placed count tracks area. It cannot, at a fixed raster: the
cell count does not grow with circumference, so a saturated tier cannot grow with the
ground. Only the rate is asserted against area; the placed set is asserted to grow.

It does not establish that the danger gradient is ordered across all five tiers, and it is
not, in either series, at either raster measured, with the ramp on or off. Tier three is the
ramp's pivot and is unmoved by it, so it sits wherever habitat puts it. What is asserted is
the order across the four tiers the ramp moves, and the span from the bottom of that ladder
to the top.

It does not establish that the placed set carries no gradient at a finer raster. At size 129
the monster placed span is 2.38 km against 1.23 km with the ramp ablated, because tier five
is then only 7.5% of its cell ceiling instead of 60%. The clipping claim is about the widths
this product ships and is asserted on the reference world.

It does not establish that `reachability.eligible` is a capability. It is this world's count
and it moves with the seed, which is why `scope` says so in the document.

It does not establish anything about the 23 profiles absent from every sampled world without
being provably unreachable. Whether those are authoring faults or worlds that did not roll
their ground is `BESTIARY-AUTHORING-CHECK-SEES-ONE-SEED`, and this record's numbers are a
five-seed sample.

It does not establish that a species removed by the `nest_limit` cap is distinguished from
one that lost the draw. The cap runs after placement and rewrites `counts`, so a species it
empties reads as `lost the draw to incumbents`. The cap is a safety valve and is zero by
default.

It does not establish that `saturation.placed` equals `len(sites)` on a world where a
divine visitation has run. Visitation purges lairs from `sites` afterwards and does not
revisit `saturation`, which reports what placement produced.

It does not establish anything about populations, prey carrying capacity, herd sizes,
breeding, patrol or runtime spawning. A range is where a creature may be met.

It does not establish a native port. Under decision 027 the `Core/` port is deferred to a
full rewrite; `Core/nests.cpp` and `Core/ecology.cpp` are not claimed here.
