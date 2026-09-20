# CONTENT-NO-ANTAGONIST — two wired systems emit nothing, and neither says so

Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 7).

## Observed behavior

Seed 42, size 17, `generator_version` 16.

**`heroes.dreads: []`.** `heroes.rolls` holds 131 candidates; `heroes.summary` reports
`{"living": 54, "legends": 6, "dreads": 0, "realms": 9, "orgs": 8, "camps": 7, "hooks": 49,
"candidates": 131, "precipitated": 67}`. Sixty people precipitate across ten roles — council
(41 rolls), heir (14), domain holder (14), camp (14), keeper (13), warlord (9), sovereign (9),
reeve (7), harbourmaster (6), castellan (4). **The antagonist role fires zero times.**

`story_web` then weaves 54 of those 60 into 51 reachable tropes, offering `the_court` 8 times,
`the_blight` 7, `the_march` 7, `the_siege` 6, `reclamation` 4, `the_vow` 4, `revenge` 2. A cast
with beliefs, wants, fears, tells and claims, and nobody to oppose.

**`magic.colleges: []` against `effective_config.college_count: 2`.** `magic_enabled` is 1,
twelve schools resolve, 78 ley nodes place, fourteen of them are key points raised by destroyed
cities, and `human_magic_limit` is 0.45. Zero institutions.

**Neither shortfall is reported as a shortfall.** `heroes.summary.dreads` is `0` with no reason
attached. `magic` emits no diagnostic for the colleges it did not place; its `college_method`
says *"Sites may be fewer than requested"*, which covers one of two and reads differently at
zero.

## Why it matters

A world with 60 named heroes, 51 tropes and no antagonist is a story with no second half. `the_siege`
is offered six times and there is nobody besieging. Whatever the quest consumer turns out to be,
`heroes` and `story_web` are the strongest authored content in the document and the half that
would give them stakes is empty.

The missing colleges matter less on their own and more as the second instance of the same
reporting gap: a consumer reading this document cannot distinguish "this world has no colleges
because the world is small" from "colleges are not implemented" from "colleges failed to place".
That distinction is exactly what `PRODUCT-REACHABILITY-REPORT` asks every catalogue to publish,
and `key_locations` already does — every archetype appears in `sites` or in `diagnostics` with a
reason, including `{"archetype": "maelstrom", "placed": 0, "wanted": 0, "candidates": 78,
"reason": "the world is too small to support one"}`.

## Proposed mechanism

Two separable pieces; the second is the cheap one and should not wait for the first.

1. **Report the absence.** Give `heroes` and `magic` the diagnostic shape `key_locations` uses:
   for each role or institution that could exist, whether it placed, how many candidates were
   evaluated, and the reason none did. This is a reporting change, needs no design decision, and
   turns two silent zeros into two answerable questions.
2. **Then decide whether the zeros are correct.** If the dread role is gated on world size or age
   count and this world clears neither, the diagnostic will say so and there is nothing further
   to do here. If it is gated on something that never fires, that is a separate defect and the
   diagnostic is what finds it. The `VILLAIN-*` cards cover the villain system's code; this card
   is about the emitted world containing none of its output.

## Dependencies and unresolved decisions

- Whether `heroes.dreads` and `terrain_villains` are the same population under two names. The
  document mentions `villain` 18 times and emits no `villains` block; the relationship between
  the two is not stated anywhere a consumer can read, and `VILLAINS-NO-SCHEMA` already notes the
  block has no contract.
- Whether either is size-gated. Both should be re-measured at size 33 and 65 before any
  conclusion that they never fire — the diagnostic in step 1 makes that measurement trivial.

## Acceptance and evidence

- A generated world in which a role or institution does not appear carries a reason it did not,
  in the block that owns it.
- A behavioral test asserts that every role in the hero policy appears in `people` or in a
  diagnostic, so a role that stops firing is visible.
- The conformance records for `heroes` and `magic` state the gates.

## Adversarial review and limitations

One seed at one size. Both zeros may be correct behavior for a 200 km world and this card does
not claim otherwise — it claims the document gives a consumer no way to find out. That claim does
not depend on the seed.
