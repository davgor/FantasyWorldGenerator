# BESTIARY-BRIMSTONE-BATS - a creature that cannot exist in any world

## Observed behavior

`brimstone-bats` clears its hard gates - medium, temperature and its `ley_infernal: 0.025`
requirement are all satisfiable - and then **never reaches the 0.3 suitability floor
anywhere**, so it can never be placed in any world.

Its weights are `mountain: 2, volcanic: 2, ley_infernal: 2`. All three together do not occur
strongly enough on any cell measured.

## Why it matters

This is the same failure shape that seven of the seventeen creatures added by the nomad
roster pass had on first authoring, and it is silent: the catalogue validates, the world
generates, and the creature simply is not in it. Nothing raises.

It is distinct from the two ordinary reasons a creature does not appear - conditions absent
from a particular world, and losing the draw to incumbents. `Sim/tests/test_creature_movement.py`
decomposes all three and asserts only on this one.

## Current state

Recorded as `KNOWN_UNDERWEIGHTED` in `test_creature_movement.py` with the reasoning attached,
so the assertion stays meaningful rather than being disabled. **That exclusion should not be
permanent.**

## Proposed fix

Rebalance toward one dominant term - the pattern every placeable infernal creature uses is a
substantial terrain weight plus a modest ley term - or relax the volcanic requirement. Remove
it from `KNOWN_UNDERWEIGHTED` once fixed.

## Not owned

Pre-existing, not introduced by the nomads work.
