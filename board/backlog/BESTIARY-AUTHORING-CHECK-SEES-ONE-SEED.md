# BESTIARY-AUTHORING-CHECK-SEES-ONE-SEED — ten creatures fail their own authoring check on worlds nobody tests

Filed 2026-09-21 out of [BESTIARY-BRIMSTONE-BATS](../done/BESTIARY-BRIMSTONE-BATS.md), which fixed
one instance of this and measured nine more while proving the fix.

## Requested behavior

The placement test should be able to tell "this creature is unplaceable because of how it is
authored" from "this creature is unplaceable on this particular world", for every creature,
rather than for whichever creatures happen to fail on seed 42.

## The gap

`brimstone-bats` was carded because it never reached the 0.3 suitability floor. Fixing it needed
five candidate rebalances measured across five worlds, because only one of the five cleared the
floor on **every** world — the mountain-dominant variants die on seed 7. That sampling turned up
the real shape of the problem:

| creature | worlds it fails on (of 5 sampled) |
|---|---|
| `sulphur-eels` | 3 |
| `cinder-jackals` | 2 |
| eight others | 1 each |

**The seed-42 test cannot see any of them.** It is green, and it is green because of the world it
samples, not because the catalogue is sound — the same shape as
`test_names_within_one_world_are_unique` using one people, recorded in
[CONTENT-AGE-SUFFIX-IN-NAMES](CONTENT-AGE-SUFFIX-IN-NAMES.md).

## Why this was not simply fixed

The agent that found it **deliberately did not widen the test to a second seed**, and that was the
right call: doing so turns the suite red for ten creatures nobody has assessed, and a permanently
red suite entry teaches people to ignore red — the same reasoning
[SDET-CEILING-SENTINELS](../done/SDET-CEILING-SENTINELS.md) used when it built a ratchet instead of
a literal assertion.

## Proposed mechanism

A census with a ratchet in both directions, as `tests/test_ceiling_sentinels.py` does it: record
the ten known-failing creature/world pairs with the reason each was not assessed, fail when a new
one appears, and fail when a recorded one starts passing so the entry gets deleted rather than
going stale. That converts an invisible ten into a visible ten that cannot grow quietly.

## Unresolved

Whether the ten are authoring faults or world faults is **not** established and must not be
assumed from this card. `brimstone-bats`' cause was that a third of its score came from
`volcanic`, which is min 0.00 / mean 0.00 / max 0.04–0.15 over land everywhere — a field that is
effectively zero. Each of the ten needs that same measurement before anyone retunes it. Some may
be correct refusals.

## Adjacent, same card or its sibling

**The monster catalogue is itself not a pyramid**: 77/86/90/66/50 by tier, bulging at tier 3.
`test_the_book_is_a_pyramid_too` passes because it only asserts `t1 > t5` and `t1 + t2 > t4 + t5`,
both of which a bulge satisfies. That is a third instance of an assertion that cannot see the
defect it appears to guard.

## Dependencies

None. [BESTIARY-PYRAMID-RETUNE](../done/BESTIARY-PYRAMID-RETUNE.md) has landed and moved every
monster site, so re-measure rather than reusing its figures.
