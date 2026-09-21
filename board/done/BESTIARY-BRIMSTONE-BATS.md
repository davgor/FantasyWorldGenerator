# BESTIARY-BRIMSTONE-BATS - a creature that cannot exist in any world

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** Its own diagnostic reads `{"species_id": "brimstone-bats", "tier": 2, "placed": 0}`. Still unplaceable.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


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

## Delivered 2026-09-21

**Premise re-tested and it reproduced.** `brimstone-bats` clears its `ley_infernal: 0.025`
gate and then never reaches the 0.3 suitability floor. Confirmed on five worlds, not one:
unplaceable at seed 42 size 33, seed 7 size 33, seed 42 size 65 and seed 99 size 17, and
placeable only at seed 1234 size 33, where three cells scraped 0.430.

**The cause, measured.** Its weights were `mountain: 2, volcanic: 2, ley_infernal: 2`, and
`volcanic` over the land of every world sampled is min 0.00, mean 0.00, max 0.04 to 0.15.
**A third of the score came from a field that is effectively zero everywhere**, and the other
two thirds could not carry it over the floor. That is the same failure shape as the seven
creatures that leaned on `ley_rot` and `ley_eldritch` - a weight on something that is never
there - but on a *live* layer rather than a dormant one, which is exactly why
`test_no_creature_scores_only_on_dormant_layers` could not see it.

The card's suggested fix, "relax the volcanic requirement", does not apply: there is no
volcanic requirement. `requires` is `ley_infernal` alone. It is the volcanic *weight* that
is the drag.

**The fix.** `volcanic` is replaced by `moisture`, giving
`mountain: 2, moisture: 2, ley_infernal: 2`. That is the family pattern the card asks for:
every placeable infernal creature in the catalogue carries `moisture: 2, ley_infernal: 2`,
and the bats keep their `mountain` term on top of it, so a roost is still a mountain roost.

Four candidate rebalances were measured against the five worlds. Cells clearing the floor:

| weights | 42/33 | 7/33 | 1234/33 | 42/65 | 99/17 |
|---|---|---|---|---|---|
| shipped `mountain 2, volcanic 2, ley 2` | 0 | 0 | 3 | 0 | 0 |
| drop volcanic, `mountain 2, ley 2` | 3 | 0 | 7 | 1 | 0 |
| `mountain 3, ley 2` | 3 | 0 | 7 | 2 | 0 |
| `mountain 5, ley 1` | 2 | 0 | 10 | 5 | 2 |
| **`mountain 2, moisture 2, ley 2`** | **7** | **2** | **17** | **19** | **9** |

Only the family pattern clears the floor on every world. The mountain-dominant variants die
at seed 7, where just two land cells pass the ley gate at all and both of them are flat.

**Test.** `Sim/tests/test_creature_movement.py::KNOWN_UNDERWEIGHTED` is now empty, which is
what the card asked for. Removing the exclusion first, with the shipped weights, gave:

    AssertionError: Lists differ: ['brimstone-bats'] != []
    : creatures that clear their gates and still cannot score: ['brimstone-bats']

and a second failure in `test_the_unplaceable_are_unplaceable_for_world_reasons`. Both green
after the weight change. 9 tests, OK.

**Ablation.** The code under test here is the one weight. Restoring `volcanic: 2` in place of
`moisture: 2` puts both assertions back to red with the message above - that is literally the
before-state that was run, so the ablation is the same experiment.

**Not done, and adjacent.** `sulphur-eels` fails the same authoring check on 3 of the 5
sampled worlds and `cinder-jackals` on 2 of 5; `geyser-serpents`, `phoenixes`, `slag-beetles`,
`toll-fiends`, `aegis-rams`, `gate-colossi`, `reliquary-bears` and `the-wild-hunt` each fail
on one. The seed-42 test cannot see any of them. That is a real second finding and it is not
carded; extending the placement test to a second seed would turn it red for creatures nobody
has looked at yet, so it was left alone deliberately rather than quietly widened.

`Fixtures/sample-world-v1.json` is stale: the bats can now place, so the catalogue draw moves.
