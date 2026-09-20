# MAGIC-CORRUPTION-NEVER-REACHES-GROUND - a forbidden school is seated but no ground wears it

## Observed behavior

The design, as ruled by the user on 2026-09-20: the generator must **never** produce a hidden
school independently, and villain triggers bring those nodes into existence afterwards, so
converting a node to a forbidden school has to be a capability that exists.

The first half is correct today and was verified rather than assumed. A seed-42 world at
phase 13 carries zero hidden-school nodes, and `biome_variant` never indexes past 103 - the
exact top of the known-school block - so no hidden variant is ever generated.

The second half stops one step short. Seating a node the way `_cluster` does, then running the
two recompute passes, isolates where:

```
generated                      blood nodes=0   ley_blood max=-0.000  hidden-school cells=0
after seating a blood node     blood nodes=1   ley_blood max=-0.000  hidden-school cells=0
after evaluate_networks        blood nodes=1   ley_blood max= 1.129  hidden-school cells=0
after add_biome_variants       blood nodes=1   ley_blood max= 1.129  hidden-school cells=1
```

The conversion needs all three steps. `corruption_request` performs only the first:
`terrain_corruption.py` contains no reference to `evaluate_networks`, `add_biome_variants`,
`refresh_environment` or `ley_` anywhere. `_cluster` edits `magic.networks[school]` and returns.

So a villain corruption seats the node, and the world's magical biomes do not change.

## Why it matters

The corruption API is otherwise complete and symmetric - `corruption_request`, `cleanse_request`,
`validate_corruption`, `validate_cleanse`, its own `API_VERSION`, a snapshot, and a stateless
contract that never touches the caller's world. It even guards `result.setdefault('timing_ms', {})`,
which is the guard [TIME-PERSISTED-WORLD-CANNOT-ADVANCE](TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md)
shows `add_terrain_labels` is missing. This is a finished feature missing its last hop.

The consumer is ready and was proved ready independently: feed a hidden ley field and
`add_biome_variants` produces `ocean.blood`, `desert.blood`, `grassland.blood` correctly. All
twelve ley layers are created at generation, so nothing needs to be added for hidden schools to
be representable. The catalogue publishes all 156 variants. **Every part of this works except
the call that connects them.**

The effect is silent in the way this repo keeps finding: corruption reports `acted: True`, the
node is really there, the snapshot records it, and nothing about the visible world changes. A
player would see a corruption event land and the ground stay ordinary.

## Current state

Not reproducible end to end on any current world, for a second and separate reason:
`validate_corruption` raises *"Corruption needs a super villain to seat; this world has none"*
on a seed-42 phase-16 world. That is [CONTENT-NO-ANTAGONIST](CONTENT-NO-ANTAGONIST.md) and the
active SUPER-VILLAINS work, not this card - but it does mean this defect cannot be observed
through the front door today, which is likely why it has survived.

The route also cannot be reached by the ordinary leyline-edit path, and should not be:
`terrain_history.py:741` refuses any edit whose school is not in `KNOWN_SCHOOLS`, so all four
hidden schools are rejected there. Per the ruling that is **correct behaviour** and should stay -
conversion is a villain trigger, not a player edit. Cross-reference
[SDET-LEY-QUEUE-NO-APPLIER](SDET-LEY-QUEUE-NO-APPLIER.md), which found the same closed route
from the `pending_ley_edits` end.

## Proposed fix

After `corrupt()` acts, recompute the derived fields the way `advance_age_request` already does:
`evaluate_networks(result, cfg)` then `add_biome_variants(result, cfg)`. Both are already
imported-and-used patterns elsewhere in the codebase, and the snapshot should be taken after the
recompute so the recorded diff contains the ground change rather than only the node.

Two constraints on landing it:

- This is **seed-affecting** for any world where corruption acts, so it needs its `Core/` port in
  the same change under the standing rule. It changes no world where corruption does not act,
  and corruption cannot act today, so the blast radius is currently zero - which makes this the
  cheapest moment to land it, not the most expensive.
- Decide whether `cleanse_request` needs the mirror treatment. Draining a node without
  recomputing leaves the same inconsistency in the other direction, and a cleanse that does not
  visibly clean is the worse bug of the two.

Needs a test that asserts hidden-school cells appear after a corruption and disappear after a
cleanse, driven through the request API rather than through the internals - the internals are
what this card already proves work.

## Not owned

Pre-existing. Found while verifying the hidden-school route during the biome catalogue
data-ization, 2026-09-20; not introduced by it.
