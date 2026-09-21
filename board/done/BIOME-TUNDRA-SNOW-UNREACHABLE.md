# BIOME-TUNDRA-SNOW-UNREACHABLE - two catalogued biomes that no world can contain

## Observed behavior

`natural_catalogue()` publishes thirteen natural biomes. Two of them cannot exist in a finished
world.

`classify()` (`Sim/icarus_sim/terrain_biomes.py:40`, ported at `Core/biomes.cpp:81`) assigns
`1 tundra` when `temperature < 5` and `6 snow` when `temperature <= 0`. The ecology stage then
relabels cold land to `15 boreal_forest` / `16 cold_tundra` / `17 land_ice`
(`terrain_ecology.py:107`, `add_cold_habitats` at `Core/biomes.cpp:122`).

Sweeping both real functions over 8,820 combinations of mean temperature, moisture, latitude
and seasonality:

```
cells classify() calls tundra(1) or snow(6):  8820
overwritten by the cold pass:                 8820
surviving as 1 or 6:                             0
```

Confirmed against every world on disk: ids `1` and `6` appear in none of
them. Water cells cannot rescue either label, because `classify` already forces water to `0`
or `8` before the cold pass runs.

They are not biomes in practice. They are intermediate labels inside a two-stage pipeline.

**Correction, 2026-09-20 — "zero survivors" is not true as a proof, only as an observation.**
The tempting derivation is that the twelve cosine coefficients are symmetric about zero, so the
seventh-largest month equals the mean exactly and a cell below 5 C can never show seven warm
months. They are not symmetric: `math.cos(2*math.pi*(3-6)/12)` and `math.cos(2*math.pi*(9-6)/12)`
both evaluate to `+6.123233995736766e-17`, not to `0` and `-0`, because cosine is even. Sorted
descending the coefficients run `1.0, .866, .866, .5, .5, 6.12e-17, 6.12e-17, -.5, ...`, so the
seventh-largest month is the mean plus `amplitude * 6.12e-17`, strictly above it. A mean within
about `2.2e-15` C below `5.0` at maximum seasonal amplitude therefore gets a seventh warm month,
`cold_habitat` returns `None`, and biome `1` survives. Verified survivor: mean `4.999999999999999`,
wet `0.0`, latitude `90`, seasonality `2.0` gives seven warm months and `cold_habitat` `None`.

Biome `6` has no such band and never survives: it requires a mean at or below `0`, and
`0 + 40 * 6.12e-17` cannot exceed `5`.

The band is floating-point measure zero and no generated world has ever shown it. The tombstone
therefore rests on *no world contains these labels*, never on *the classifier cannot emit them* —
which is why `classify()` keeps both branches. The refutation is pinned by
`test_the_tombstone_is_unreachable_in_practice_and_not_by_proof` so it cannot be re-derived
wrongly a third time.

## Why it matters

`natural_catalogue()` advertises all thirteen to asset generation with
`asset_id = f'terrain.biome.{bid:03d}'`, so `terrain.biome.001` and `terrain.biome.006` are
art commissioned for ground that never renders. Decision 014 requires validating a biome in
FantasyWorldGenerator *before* the texture and foliage pipeline consumes it; these two are
exactly the case it was written to catch.

There is a second cost. Anyone reading the catalogue reasonably believes the world has a
tundra and a snow biome distinct from cold tundra and land ice, and may author fauna, assets
or rules against them. The nest role tables already do: biome `1` appears in 14 role tables and
biome `6` in 9. Those are harmless dead lookups today - `biome_weight` is only ever called with
an id that occurs in a world - but they are a standing invitation to build on ground that is
not there.

## Resolution — closed 2026-09-20 by user ruling 0.2

**Ruled: tombstone, not delete.** Rows `1` and `6` keep their ids, their contents and their
positions; only art commissioning stops.

**What shipped.**

1. `Sim/icarus_sim/biomes.json` rows 1 and 6 carry `"reachable": false` and an
   `unreachable_note`. `_registry()` in `terrain_biome_catalogue.py` validates the new keys
   strictly and fails closed on an unknown key, a non-boolean flag, a tombstone with no reason,
   or a registry that tombstoned everything.
2. `UNREACHABLE_BIOMES`, `reachable_natural_catalogue()` and `reachable_biome_catalogue()` are
   new accessors. `natural_catalogue()` is deliberately **unchanged**, and so are the dicts it
   emits — `terrain_history.py` compares `world['terrain']['biomes']` and `['natural_biomes']`
   against it for equality, so a key added there would be a key in every saved world and a
   schema change in `world-output.schema.json`. A tombstone is a statement about commissioning,
   not about the contract.
3. The 26 affected identities are **marked, not dropped**: `terrain.biome.001`, `.006` and the
   24 `terrain.mutation.tundra.*` / `snow.*` rows now compile with `"status": "unreachable"`
   instead of `"supported"`. Dropping them would have been the first case in this repo of a
   world document naming an identity the native asset registry cannot bind — every world still
   advertises all thirteen natural ids and all 156 variants. The compiled list stays at 1707
   identities and the registry keeps 1707 binding slots.
4. `_production_assets()` now rejects any brief whose *only* ground is tombstoned. Validation
   still accepts `1` and `6` as selectors, so a row naming them alongside reachable ground is
   still legal; what is rejected is a commission for a surface no world renders.

**The waste that was actually there, and where it went.** Before this change the production
catalogue's biome histogram was `{0:10, 1:40, 2:23, 3:17, 4:50, 5:48, 6:9, 7:27, 8:30, 13:34}`.
Biome `1` was the second most-commissioned biome in the repo and biome `6` had nine rows, while
`15 boreal_forest`, `16 cold_tundra` and `17 land_ice` — the three that carry every cold cell a
world actually produces — had **zero production rows between them**. This was not ten wasted
briefs. It was the only cold art in the catalogue, aimed at the only two cold ids that do not
occur.

Forty-six rows were re-pointed. The histogram is now
`{0:10, 2:23, 3:17, 4:50, 5:48, 7:27, 8:30, 13:34, 15:29, 16:16, 17:10}`.

Ten rows had no reachable ground at all and were re-aimed:

| Asset | Was | Now | Why |
| --- | --- | --- | --- |
| MAT-027 Fresh snow | 6 | 16, 17 | snow lies on cold tundra and on land ice |
| MAT-028 Compacted dirty snow | 6 | 16, 17 | trafficked snow, same two surfaces |
| MAT-030 Tundra moss and lichen | 1 | 16, 17 | cold-tundra ground cover, and ice-margin lichen |
| GEO-025 Snow drift | 6 | 16, 17 | wind-built drifts form on both |
| GEO-026 Ice ledge | 6 | 17 | needs persistent ice, not seasonal snow |
| GEO-027 Icicle cluster | 6 | 17 | needs persistent ice, not seasonal snow |
| VEG-004 Tundra tussock | 1 | 16 | needs soil; land ice has none |
| VEG-022 Tundra dwarf shrub | 1 | 16 | needs a rooting medium |
| FX-004 Snowfall | 1, 6 | 15, 16, 17 | snow falls on every cold surface, boreal included |
| SND-007 Tundra wind loop | 1, 6 | 16, 17 | open cold wind; wind through conifers is a different sound |

Thirty-six more named a tombstoned id alongside live ground. Leaving them would have left biome
`1` still reading as the most-commissioned cold biome in the catalogue, so each was re-pointed by
substitution rather than stripped — the live selectors are untouched and the dead one is replaced
by the reachable biome the brief actually depicts:

- **1 → 15 boreal forest (27 rows).** MAT-008 conifer needle litter, MAT-034 birch-like bark,
  MAT-035 conifer bark and all 24 of TREE-007 .. TREE-030 (birch, aspen, open pine, dense fir,
  each as sapling / mature A / mature B / dead standing / stump / fallen trunk). These are boreal
  species and boreal forest floor. Biome `15` had no art whatever; this is the finding restated
  from the other end, and it closes with no new briefs.
- **1 → 16 cold tundra (7 rows).** MAT-002 thin upland soil, MAT-017 granite-like rock, GEO-002
  small angular stone, GEO-003 and GEO-004 granite boulders, VEG-013 moss cushion, VEG-014 rock
  lichen patch. Cold open ground with thin soil and frost-shattered rock is exactly what
  `cold_tundra` is.
- **6 → 17 (1 row).** MAT-029 clear rough ice, `[6, 8]` → `[8, 17]`: lake ice and land ice.
- **FX-010 ley node shimmer** listed `1..8, 13` — every id `classify()` emits except ocean. That
  set is now `2, 3, 4, 5, 7, 8, 13, 15, 16, 17`, which is the same intent stated against the ids
  that survive the ecology pass.

Nothing was left alone. Every production row that named `1` or `6` was re-aimed; the shipped
catalogue names neither id anywhere, which is asserted by
`test_no_production_brief_is_commissioned_for_tombstoned_ground`.

**Land ice still has no plant.** After the re-point biome `17` carries ten rows across `material`,
`mesh`, `vfx` and `audio` kinds and **zero of kind `plant`**. MAT-030 is the only vegetation on
it and it is a material, not a plant. That is deliberate: a tussock needs soil and a dwarf shrub
needs a rooting medium, so neither is honest on permanent ice, and the second half of ruling 3.0
is *not* fully satisfied by this card. What would be honest, proposed and **not added** here
because each is a new brief with a new id:

- a cryoconite / snow-algae bloom patch — the pink and green surface staining that is the real
  primary producer on permanent ice;
- a crustose lichen crust on wind-exposed rock, for the nunatak and moraine faces inside a
  land-ice cell;
- a moss mat for the ice margin, which is where the vegetation actually lives.

**The question the card left open: should the cold rule move into `classify()`?** Recommended
**against**, for three reasons. `cold_habitat` needs twelve monthly temperatures, latitude,
seasonality and ice accumulation, so `classify()` would stop being a four-scalar pure predicate
and its C++ twin would roughly double in surface. The two run in different pipeline stages, so
merging them changes what a phase-8 world contains. And biome `6` is load-bearing as an
intermediate: `terrain_biomes.py` derives the "Snow region" feature marker from `biome == 6`, and
snow markers are present in generated worlds — deleting the branch would silently empty world
output of them. `Core/biomes.cpp` is unchanged and `test_the_tombstone_is_a_catalogue_statement_not_a_classifier_one`
pins both `return` lines so it stays that way.

**What this card does NOT close.**

- The 14 role tables keyed on `"1"` and 9 keyed on `"6"` in `terrain_nest_profiles.json` are
  untouched. That file is provenance-pinned and
  [BESTIARY-LAND-ICE-NO-ANIMALS](BESTIARY-LAND-ICE-NO-ANIMALS.md) must edit it anyway
  to add biome 17; one pass and one revision row is better than two. Two facts it needs: the
  strip is a provable no-op, because `biome_weight` is only ever called with a cell's biome,
  which is never 1 or 6; and a test currently pins the defect by asserting the land-ice weight
  is zero, so that line must flip in the same change.
- `Contracts/catalogues/biome-flora.json` still holds 7 flora prompt rows under real biomes 1
  and 6 and 84 under the 24 dead magical variants: 91 authored prompts on ground that never
  renders. Its `unreachable_note` still says "Do not commission art until the inventory decision
  lands". The decision has landed. Not this lane's file.
- `Sim/fantasy_world_generator/terrain_taxonomy.json` is a fourth copy of the biome identity
  list with its own `retired_natural_ids` vocabulary for a different meaning. `reachable` is a
  third word for a related idea and the two are not yet reconciled. Because the tombstone drops
  no identity, the portable taxonomy still resolves 1 and 6 to asset ids that still exist, so
  nothing is broken today.
- The per-biome artist pages under `docs/catalogue/world-assets/` still describe the ten
  re-pointed briefs against "Tundra" and "Snow", and COVERAGE.md still lists them under sections
  1 and 6. Those files are provenance-pinned and were not this lane's to edit.

**A naive retirement is a trap.** `NATURAL_BIOMES` is an ordered dict; `VARIANT_NAMES` holds
exactly thirteen names per school indexed *positionally* into that order; and
`biome_catalogue()` flattens to 156 entries (13 biomes x 12 schools) whose index the docstring
at `terrain_biome_catalogue.py:36` calls a contract in as many words - `biome_variant` stores a
flat index into it, and *"another column would renumber every variant in every saved world."*

So deleting rows `1` and `6` makes index 1 become desert: `VARIANT_NAMES['weave'][1]`
`"Dream tundra"` and `['infernal'][1]` `"Blighted tundra"` attach to **the desert**, every
later variant shifts, and the catalogue goes 156 -> 132, renumbering `biome_variant` in every
saved world. That is precisely the failure the docstring was written to prevent.

## Proposed fix — this is what was ruled on

Two shapes, and they are not equally expensive:

**Tombstone (recommended, and chosen).** Keep the rows and their positions, mark them
unreachable, and stop commissioning `terrain.biome.001` / `terrain.biome.006` art. Zero contract
impact, no world invalidation, and it still captures the wasted-art saving that motivated the
finding. This **does not** have to wait for
[PRODUCT-WORLD-DISPOSABILITY-DECISION](PRODUCT-WORLD-DISPOSABILITY-DECISION.md).
As shipped the identities are marked `unreachable` rather than removed, for the reason given in
the Resolution section above.

**Delete.** A clean catalogue, but it invalidates every saved world and therefore lands
squarely on that unruled question.

Tombstoning decouples this decision from disposability, which is why it is worth stating as an
option rather than presenting retirement as one thing.

Either way, consider whether `classify()` returning a label the next stage always overwrites is
the right shape, or whether the cold rule belongs in `classify` itself.

## Not owned

Pre-existing. Surfaced by the biome review of 2026-09-20.

## A near miss worth recording: desert is NOT a third case

`2 desert` looked like the same defect and is not. It appears in no small world *among the
twelve world documents under `Artifacts/`*, but it survives the cold pass intact where it does
occur - all 31 cells `classify()` calls desert in `debug-preview-final` are still desert in the
final layer. Its absence elsewhere is a moisture supply story, and the trend across those twelve
worlds is monotonic in raster size. **Read the scale line below the table before citing any of
these numbers:**

```
size 17   moisture min 0.589   cells<0.3:  0   desert:  0
size 33   moisture min 0.457   cells<0.3:  0   desert:  0
size 65   moisture min 0.294   cells<0.3:  2   desert:  0
size 65   moisture min 0.279   cells<0.3:  4   desert:  2
size 65   moisture min 0.223   cells<0.3: 36   desert: 31
```

**Scale line, added 2026-09-20 by the biome-reachability lane: every row above was measured on
the retired ~11 km world, and none of them describes this tree.** Eleven of the twelve documents
carry `globe_radius` 1774.4123532462843 and the twelfth, `before-legacy.json` at generator
version 8, carries 1834.617044641644. The live tree resolves 31830.99, a 200 km circumference.
The 0.589 row is the moisture minimum of two of those files, not one; 0.457 is the size-33 file
and 0.294 / 0.279 / 0.223 are the three size-65 previews.

Desert appears in those worlds exactly when the minimum crosses ~0.3. Every world runs the
wind-transport model, so relief drives rain shadow: a small grid on **that** planet could not
produce a dry cell, so the rain shadow had nowhere to form. The system was working.

This is the whole reason to check a suspected dead biome against the mechanism rather than
against a world. **Anyone who had "fixed" the desert thresholds against a size-17 world would
have broken warm worlds permanently.** A knob tuned against the degenerate corner does not
merely fail to help; it actively damages the configurations that were working.

**Closing note on this table, 2026-09-20: not one row of it reproduces, and the premise it
supports is false on this tree.** A seed 42, size 17, phase 10 world here takes 0.42 s and
contains 6 desert cells, not 0 — the full census is
`{0:239, 2:6, 3:2, 4:2, 7:1, 13:11, 15:2, 16:15, 17:11}`, identical in both the `biome` and
`natural_biome` layers, with the snow feature marker present. That census was taken before the
wave-1 river-threshold change; re-measured after it the same world reads
`{0:195, 2:6, 3:2, 4:2, 7:1, 13:11, 15:2, 16:14, 17:9}`, still 6 desert cells.

**Re-measured across seeds, 2026-09-20, phase 10 on this tree:** desert appears at raster 17 in
**222 of 232 seeds**. Land moisture minima over seeds 0-31 run from 0.0065 to 0.6197 — the ten
seeds without desert are the ones whose floor stays above ~0.3, not a raster limit. Seed 42 gives
a land moisture minimum of 0.0555 and six desert cells. "Absent below size 65" and "a small grid
cannot produce a dry cell" are both statements about the 11 km planet and neither is true here.

**The ruling this section exists to protect is unchanged and is still right.** Do not retune the
desert thresholds. Only its supporting evidence was wrong, and correcting it is what keeps the
protection: a reader who re-measured, found desert everywhere and concluded the card was wrong
would have put the threshold back in play.

The correct generalisation is the one `5 exposed_rock` now demonstrates, and it is stronger than
the one this section originally drew: check a suspected dead biome against a **freshly generated
world on the current scale**, because an artifact on disk records the scale it was made at, and a
world document does not stop being readable when the planet under it changes size. The rock case
is recorded at [BIOME-EXPOSED-ROCK-NEEDS-RELIEF](../retired/BIOME-EXPOSED-ROCK-NEEDS-RELIEF.md),
with the mechanism, both falsification probes, and the measurement showing that the obvious knob
makes every other raster worse. The same run is the evidence for this card's own claim: zero
cells of 1 or 6 in either layer, and `terrain['biomes']` still advertising all thirteen ids.

**Cost note.** Every biome census in this card can be taken at phase 8 or 10 for well under a
second. The biome layer does not exist below phase 8 and is fully settled at 8; the 70–120 s
phase-16 path buys nothing here.
