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

**Zero survivors.** Confirmed against every world on disk: ids `1` and `6` appear in none of
them. Water cells cannot rescue either label, because `classify` already forces water to `0`
or `8` before the cold pass runs.

They are not biomes. They are intermediate labels inside a two-stage pipeline.

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

## Current state

Undecided, and the decision is not mine to take. Decision 014 is explicit that the workflow
gate does not settle the biome inventory.

**A naive retirement is a trap.** `NATURAL_BIOMES` is an ordered dict; `VARIANT_NAMES` holds
exactly thirteen names per school indexed *positionally* into that order; and
`biome_catalogue()` flattens to 156 entries (13 biomes x 12 schools) whose index the docstring
at `terrain_biome_catalogue.py:36` calls a contract in as many words - `biome_variant` stores a
flat index into it, and *"another column would renumber every variant in every saved world."*

So deleting rows `1` and `6` makes index 1 become desert: `VARIANT_NAMES['weave'][1]`
`"Dream tundra"` and `['infernal'][1]` `"Blighted tundra"` attach to **the desert**, every
later variant shifts, and the catalogue goes 156 -> 132, renumbering `biome_variant` in every
saved world. That is precisely the failure the docstring was written to prevent.

## Proposed fix

Two shapes, and they are not equally expensive:

**Tombstone (recommended).** Keep the rows and their positions, mark them unreachable, and stop
emitting `terrain.biome.001` / `terrain.biome.006` assets. Zero contract impact, no world
invalidation, and it still captures the wasted-art saving that motivated the finding. This
**does not** have to wait for
[PRODUCT-WORLD-DISPOSABILITY-DECISION](PRODUCT-WORLD-DISPOSABILITY-DECISION.md).

**Delete.** A clean catalogue, but it invalidates every saved world and therefore lands
squarely on that unruled question.

Tombstoning decouples this decision from disposability, which is why it is worth stating as an
option rather than presenting retirement as one thing.

Either way, consider whether `classify()` returning a label the next stage always overwrites is
the right shape, or whether the cold rule belongs in `classify` itself.

## Not owned

Pre-existing. Surfaced by the biome review of 2026-09-20.

## A near miss worth recording: desert is NOT a third case

`2 desert` looked like the same defect and is not. It appears in no small world, but it
survives the cold pass intact where it does occur - all 31 cells `classify()` calls desert in
`debug-preview-final` are still desert in the final layer. Its absence elsewhere is a moisture
supply story, and the trend across the twelve worlds on disk is monotonic in raster size:

```
size 17   moisture min 0.589   cells<0.3:  0   desert:  0
size 33   moisture min 0.457   cells<0.3:  0   desert:  0
size 65   moisture min 0.294   cells<0.3:  2   desert:  0
size 65   moisture min 0.279   cells<0.3:  4   desert:  2
size 65   moisture min 0.223   cells<0.3: 36   desert: 31
```

Desert appears exactly when the minimum crosses ~0.3. Every world runs the wind-transport
model, so relief drives rain shadow: a small grid cannot produce a dry cell, so the rain shadow
has nowhere to form. The system is working.

This is the whole reason to check a suspected dead biome against the mechanism rather than
against a world. **Anyone who had "fixed" the desert thresholds against a size-17 world would
have broken warm worlds permanently.** A knob tuned against the degenerate corner does not
merely fail to help; it actively damages the configurations that were working.
