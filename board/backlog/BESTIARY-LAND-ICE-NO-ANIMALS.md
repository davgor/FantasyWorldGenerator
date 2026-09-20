# BESTIARY-LAND-ICE-NO-ANIMALS - the one biome with no animals in it

## Observed behavior

`biome_weight` (`Sim/icarus_sim/terrain_nests.py`) resolves habitat preference from the
species' own `biome_weights`, then from its role's, and returns `table.get(str(biome_id), 0.)`.
Its own docstring states the semantics: **an absent biome is habitat the species does not use.**

Biome `17 land_ice` appears in **0 of the 21 role tables** in `terrain_nest_profiles.json`,
and no profile anywhere carries its own `biome_weights` (0 of 680), so nothing overrides the
role. Running the real function over all 680 profiles:

```
biome 17 land_ice    animals>0: 0/311    monsters>0: 369/369
every animal  -> exactly 0.0
every monster -> exactly 1.0
```

Nineteen polar species are already authored at the `[-35, 12]` band - Arctic fox, polar bear,
muskox, reindeer (caribou), snowy owl, rock ptarmigan, Arctic hare, collared lemming, tundra
vole, snow goose, snow leopard, emperor penguin, walrus, narwhal, leopard seal, Greenland
shark, colossal squid, long-tailed jaeger, rainbow trout. **Every one scores zero on the only
biome that is unambiguously theirs.**

## Why it matters

Land ice is **100% monster territory by accident**. Monsters fall through to `1.` because none
of them carries a role or a `biome_weights` table ([BESTIARY-MONSTERS-BIOME-BLIND](BESTIARY-MONSTERS-BIOME-BLIND.md)),
so the ice sheet is the one place where that accidental default meets a total animal exclusion.
Nobody decided this.

The failure is silent in the same shape as [BESTIARY-BRIMSTONE-BATS](BESTIARY-BRIMSTONE-BATS.md):
a missing key and a deliberate zero are indistinguishable to the consumer. The catalogue
validates, the world generates, and the ice is simply empty of animals. Nothing raises.

It is **not** the zero-octave terrain defect wearing a catalogue defect's clothes, and that
distinction is what makes it actionable. It is provable from source alone and is
octave-independent: none of the land-relevant polar species carries a relief-derived weight.

```
weight fields used by the 19:    cold x19, fishing_productivity x2
requires fields used by the 19:  depth x1, cold x1, coast x1, wetland x1
```

The single relief-gated one is the colossal squid (`requires: depth`), which is marine and
could not occupy a land-ice cell in any case. So no world at any raster size can change the
weights this card proposes.

## Current state

Unfixed, and deliberately so. The change alters nest placement in every world while
[PRODUCT-WORLD-DISPOSABILITY-DECISION](PRODUCT-WORLD-DISPOSABILITY-DECISION.md) is unruled.

**There is no measurement behind the hold.** It is decision-blocked only, and can land the
moment disposability is ruled - it does not need a larger world, and it was checked rather
than assumed.

Sequence it with [BIOME-TUNDRA-SNOW-UNREACHABLE](BIOME-TUNDRA-SNOW-UNREACHABLE.md): wiring
fauna to a biome inventory that is itself under review is premature, though land ice is not
one of the biomes at risk there.

## Proposed fix

Ten of the nineteen are `land` medium and can occupy an ice cell. They span exactly eight
roles. Add biome `17` to those eight role tables:

| role | biome 17 | its cold_tundra | unblocks |
|---|---|---|---|
| `small_prey` | 0.25 | 0.5 | Arctic hare, collared lemming, tundra vole |
| `mustelid_small` | 0.25 | 0.4 | Arctic fox |
| `bird_of_prey` | 0.20 | 0.5 | snowy owl |
| `bird_other` | 0.15 | 0.3 | rock ptarmigan |
| `large_herbivore` | 0.15 | 0.5 | muskox |
| `herbivore` | 0.15 | 0.5 | reindeer (caribou) |
| `waterfowl` | 0.10 | (none) | snow goose |
| `ambush_predator` | 0.05 | (none) | snow leopard |

Every value sits **strictly below** that role's `cold_tundra` weight, so ice stays sparser than
tundra by construction rather than by tuning, and the relationship survives anyone later
adjusting either one. Sparse is correct here; zero is not.

Polar bear, walrus and emperor penguin are `shore` medium and reach the ice margin through the
`coast` gate. They need no key at all.

`ambush_predator` at `0.05` is deliberate and should not be raised. Snow leopard sits in the
same `[-35, 12]` band as the narwhal because **305 of 311 animals share just three temperature
bands**, so temperature barely discriminates. Wired at parity this would put snow leopards on
the ice sheet. Token presence is the intended outcome, not a value to "correct" into line with
its neighbours.

Eight numeric keys into existing maps: no new fields, no string keys (which throw in C++ rather
than degrading), no schema change.

## Not owned

Pre-existing. Surfaced by the biome review of 2026-09-20, not introduced by it.
