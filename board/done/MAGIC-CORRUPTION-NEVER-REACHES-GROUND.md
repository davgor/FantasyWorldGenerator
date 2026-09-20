# MAGIC-CORRUPTION-NEVER-REACHES-GROUND - REFUTED, the connecting call was already there

## Status: REFUTED 2026-09-20. Do not apply the fix this card proposed.

The card claimed corruption seats a hidden-school node and never recomputes the derived
fields, so the ground never wears the school. That is false. The recompute runs. The
proposed fix would have added a **second** recompute after one that already happens, and it
would have landed after `add_religion(result, cfg)` at `terrain_corruption.py:286`,
reordering religion resolution against the ground rebuild for no reason.

## Observed behavior - what actually happens

A seed-42 / size-17 / `villain_rise` 1.0 world, corrupted at 40 encounters, moves the ground
in the same call:

```
before corruption_request   hidden-school cells {}            ley_eldritch max -0.000000
after  corruption_request   hidden-school cells {'eldritch':1} ley_eldritch max  1.149990
```

The corrupted school was `eldritch` under `god_shape_beneath`, four nodes. This is the same
assertion `Sim/tests/test_corruption.py:91`
`test_the_hidden_field_is_live_and_the_ground_mutates` already makes, and that suite was run
to completion while refuting this card: `CorruptedTests`, 8 tests, 109.5 s, OK.

## The call the card missed

`corrupt()` calls `rebuild_tail(result, cfg, survivors, 'corruption', age, religion=False)`
at `terrain_corruption.py:269`, immediately after `_cluster` seats the nodes. `rebuild_tail`
is `terrain_history.py:288-302`, whose body is `if evaluate: evaluate_networks(result, cfg)`
then `refresh_environment(result, cfg)` then `add_biome_variants(result, cfg)`. `corrupt()`
passes no `evaluate`, so it defaults to `True` and all three run.

## The cleanse question this card left open is also already answered

No mirror recompute is needed. `_drain` calls the same
`rebuild_tail(result, cfg, survivors, 'cleanse', age, religion=False)` at
`terrain_corruption.py:461`. A power-1.0 cleanse finished in one tick, removed all four
`corrupt-god_shape_beneath-0-*` nodes, and returned `ley_eldritch` to `-0.000000` with hidden
cells back to `{}`. The symmetry the card asked for is present and works.

## How this was missed

The evidence was a grep for the callee's name inside the caller's file. It is literally true
that `terrain_corruption.py` contains no reference to `evaluate_networks`,
`add_biome_variants`, `refresh_environment` or `ley_`, and false that the call is therefore
missing - the call is indirect, through `rebuild_tail`. This is the near-miss failure mode
this repository keeps finding: a predicate that answers a different question plausibly.

Two things in the tree already said so and were not read. The module's own `ORDER` constant
at `terrain_corruption.py:37-38` declares `leyline update` and `biomes` as steps corruption
performs, and `docs/corruption.md` step 3 says corruption "rebuilds fields, biomes,
civilization, nests and threats". The document was right and the card was wrong.

## What survives from the card

Three statements in it are correct and were re-confirmed, and none of them needed this card:

- The generator never produces a hidden school independently. A seed-42 world at phase 13
  carries zero hidden-school nodes and `biome_variant` never indexes past 103.
- The gate at `terrain_history.py:741` refusing hidden schools on caller-supplied leyline
  edits is correct and stays. Note the narrowing established since: it validates only
  `body['leyline_edits']`, never the world's own networks, which is how a corrupted world
  survives an age advance at all.
- Corruption is reachable from no caller in the tree. That is a real observation and it is
  the SUPER-VILLAINS lane's, not this card's.

## What was found in its place

[CORRUPTION-OPPOSING-A-REVEALED-GOD-CRASHES](../backlog/CORRUPTION-OPPOSING-A-REVEALED-GOD-CRASHES.md) -
a reproduced `StopIteration` on the documented way to oppose the only god corruption ever
makes walk. That is the real defect this card was standing in front of.

## Not owned

Filed 2026-09-20 after a user ruling, refuted the same day by running it. Not introduced by
the biome catalogue data-ization that found it.
