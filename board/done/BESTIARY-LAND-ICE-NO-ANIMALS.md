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
of them carries a role or a `biome_weights` table ([BESTIARY-MONSTERS-BIOME-BLIND](BESTIARY-MONSTERS-BIOME-BLIND.md) - since fixed),
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

**DONE, 2026-09-20.** User ruling 0.1 made worlds disposable and user ruling 3.0 ordered land
ice stocked. All eight keys below are in `terrain_nest_profiles.json` exactly as proposed, and
the strictly-below relationship is now asserted by a test rather than eyeballed
(`Sim/tests/test_biome_habitat_coverage.py`). Measured on seed 42 size 33 phase 13, animals on
biome 17 went from **0 to 531 sites**; at size 17, from **0 to 83**. What follows is the card
as filed, with the four corrections the execution found.

Originally unfixed, and deliberately so. The change alters nest placement in every world while
[PRODUCT-WORLD-DISPOSABILITY-DECISION](PRODUCT-WORLD-DISPOSABILITY-DECISION.md) is unruled.

**There is no measurement behind the hold.** It is decision-blocked only, and can land the
moment disposability is ruled - it does not need a larger world, and it was checked rather
than assumed.

Sequence it with [BIOME-TUNDRA-SNOW-UNREACHABLE](../done/BIOME-TUNDRA-SNOW-UNREACHABLE.md): wiring
fauna to a biome inventory that is itself under review is premature, though land ice is not
one of the biomes at risk there.

## Proposed fix

Ten of the nineteen are `land` medium and can occupy an ice cell. They span exactly eight
roles. Add biome `17` to those eight role tables:

**Correction 1: `its cold_tundra` is biome 16, not biome 1.** `biomes.json` lists id 1 as core
`tundra` and id 16 as core `cold_tundra`, and the column below is the 16 key. Read as biome 1
the table is wrong in six of eight rows.

| role | biome 17 | its cold_tundra (biome 16) | unblocks |
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

**Correction 2: this claim was false, and it is the one thing in the card that would have
shipped wrong.** The card said: *"Polar bear, walrus and emperor penguin are `shore` medium and
reach the ice margin through the `coast` gate. They need no key at all."* They do need a key.
The biome gate in `_place` runs **before and independently of** the coast gate - `weight` is
computed and a zero `continue`s out before `suitability` is ever called - so a shore species on
a coastal land-ice cell is zeroed by the missing biome key no matter how well it scores. Checked
on a real biome-17 cell, polar bear, walrus, emperor penguin and long-tailed jaeger all clear
the suitability floor comfortably and are all then multiplied by zero.

Emperor penguin and long-tailed jaeger are rescued by accident, because both are `waterfowl`.
Polar bear (`apex_predator`) and walrus (`marine_mammal`) are **not**, and were deliberately
left out of this change: the ruling named eight keys and eight keys is what landed. Adding
`apex_predator` and `marine_mammal` is a live, separate decision - see the successor card.

**Correction 3: the four `marine_mammal` shore species cannot be placed in any world at any
seed.** Their role table is ocean and lake only, both of which force `water_type` non-zero,
while the shore medium gate demands a land cell. The sets are disjoint. Gray seal, harbor seal,
northern elephant seal and walrus therefore occupy nowhere at all today, and no biome key for
land ice alone is the right fix - a haul-out is on land beside water, not in it, so the role
needs coastal land generally. Filed as its own card rather than patched here.

**Correction 4: the temperature-band leakage is real but is not a regression.** The eight keys
admit about seventy animals to land ice, only twelve of which are polar-band; the rest are
warm-band species that the coarse bands let through. Every single one of them already lives on
biome 15 or 16 today, so no species reaches somewhere qualitatively new. It is still the reason
`ambush_predator` must stay at 0.05.

`ambush_predator` at `0.05` is deliberate and should not be raised. Snow leopard sits in the
same `[-35, 12]` band as the narwhal because **305 of 311 animals share just three temperature
bands**, so temperature barely discriminates. Wired at parity this would put snow leopards on
the ice sheet. Token presence is the intended outcome, not a value to "correct" into line with
its neighbours.

Eight numeric keys into existing maps: no new fields, no string keys (which throw in C++ rather
than degrading), no schema change.

## What actually landed

Eight keys, verbatim, into `terrain_nest_profiles.json`. Two permanent tests, both of which
would have caught this class of defect from the other end:

- every reachable biome in the registry is named by at least one animal role table, **and** has
  at least one animal that can stand on it. Counting the biomes from the biome side is the
  assertion whose absence let a whole biome sit empty; counting from the role side cannot find
  it, because a role table with a missing key looks complete.
- every land-ice weight is strictly below its role's cold-tundra weight where one exists, and
  `ambush_predator` is pinned at exactly 0.05 so a later tidy-up cannot quietly raise it.

Biomes 1 and 6 are excluded from both, because they are unreachable rather than unloved.

Measured, seed 42, phase 13, one process, all three catalogues compared against each other:

```
animals on biome 17    size 17: 0 -> 83 sites      size 33: 0 -> 531 sites
total wildlife         size 17: 2984 -> 3068       size 33: 11328 -> 11827
```

The land-ice animals are new habitat, not moved habitat: total wildlife rises by roughly the
number of sites the ice sheet gained.

## Not owned

Pre-existing. Surfaced by the biome review of 2026-09-20, not introduced by it. Executed
2026-09-20 under user rulings 0.1 and 3.0.
