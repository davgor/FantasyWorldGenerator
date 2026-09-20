# VOCABULARY-VILLAIN-TWO-AXES — `villain` names two unrelated things across package boundaries

Owner: none. State: open, unowned. Found by the bug-hunt session, hunting the next same-word
different-axis collision after `tier` (four), `camps` (three) and `culture` (two).

## The collision

**`icarus_sim.terrain_villains`** — a super villain is a *field*: a continuous tier, a reach in
metres, a seat, held ley nodes, claims. There is exactly one per cultural region, at most.

**`hero_generator` and `story_web`** — `villain:prior_age` is a **feature token on an ordinary
person**, and it has nothing to do with the above. `Sim/hero_generator/features.py:47-48`:

```python
if person['role'] == 'pretender' and person['born_age'] < final and latest_founding.get(person['civilization_id'], 0) > person['born_age']:
    f |= {'villain:prior_age', 'stake:regained'}
```

It marks a pretender whose civilization refounded a city after they were born — a dispossessed
claimant, not an antagonist with a reach. The token travels: it is in
`hero_generator/archetypes.py:33`, `hero_generator/policies/archetypes.json:234`,
`story_web/facts.py:28`, `story_web/policies/tropes.json:190` and
`story_web/policies/weights.json:13`, where it is a **gainable feature** — a person can acquire it
during play.

So a world document can contain a hero whose `selectable` list includes `villain:prior_age` while
`villains.people` is empty, and a seated super villain who is in nobody's feature list. The two
uses share no field, no id space and no derivation.

## Why it bites

Nothing collides at runtime — the packages never import each other, which is the architecture
working. It bites the first consumer that joins two blocks, which is the failure mode the
orchestrator is *for*. The plausible wrong joins, in the order someone would try them:

1. Filter heroes by `'villain:prior_age' in selectable` to find "characters connected to a super
   villain". Returns dispossessed pretenders; returns nothing about super villains. Silently
   wrong, plausibly shaped, no error.
2. Read `villain:prior_age` as evidence that a villain stood in a prior age, and therefore as a
   substitute for the villain history that `VILLAIN-FALL-UNRECORDED.md` shows does not exist. It
   is not evidence of that at all, and it is exactly what someone looking for that history would
   find first.

The second is the dangerous one, because the correct answer to the question — "did a super villain
stand here before?" — is currently *unavailable*, and this token looks like it.

## Proposed mechanism

Rename the hero-side token, not the sim-side concept: `terrain_villains` owns the word in the
world model and in `docs/super-villains.md`, and the hero token is the one whose meaning is a
metaphor. `claim:prior_age` or `dispossessed:prior_age` says what the code actually tests.

That is not a free rename. The token is a **key in three shipped policy JSON files** and a member
of a declared feature vocabulary asserted by test, so it moves in one change across
`hero_generator` and `story_web` together or not at all. `Fixtures/hero-generator-v1.json` and
`Fixtures/story-web-v1.json` carry it in recorded output and would both need regeneration, which
makes this a fixture-moving change and not a tidy-up.

If the rename is judged too expensive, the fallback is to record the collision where a consumer
will meet it — `docs/hero-generator.md`, `docs/story-web.md` and `docs/super-villains.md` each
stating that the other `villain` exists and is unrelated. That is strictly worse than renaming and
strictly better than the current silence.

## Dependencies and unresolved decisions

- Owned by nobody: it spans `icarus_sim`, `hero_generator` and `story_web`. Needs routing.
- Open: whether the feature vocabulary is considered a public contract. If it is, the rename is a
  versioned interchange change and `AGENTS.md`'s public-contract rules apply to it.

## Sources consulted

`Sim/icarus_sim/terrain_villains.py`, `Sim/hero_generator/features.py:47-48`,
`Sim/hero_generator/archetypes.py:33`, `Sim/hero_generator/policies/archetypes.json:234`,
`Sim/story_web/facts.py:28`, `Sim/story_web/policies/tropes.json:190`,
`Sim/story_web/policies/weights.json:13`.

## Files and assets in scope

If renamed: the five source and policy files above, plus `Fixtures/hero-generator-v1.json` and
`Fixtures/story-web-v1.json`. If documented instead: three files under `docs/`.

## Acceptance and evidence

Either the token no longer reads as a reference to a super villain, or all three documents say it
is not one. A grep for `villain` across `Sim/` returns two vocabularies that a reader can tell
apart without opening the definition.

## Documentation impact

Direct, and it is most of the value of the card either way.

## Adversarial review and limitations

The honest counter-argument: this collides in a reader's head, not in any running code, and a
rename that moves two fixtures to prevent a hypothetical wrong join may cost more than the join
would. That case is real. What tips it is the second failure above — the token sits precisely
where someone will go looking for villain history that does not exist, which is not a hypothetical
join but the obvious next question about a block two other packages already consume.

This card claims a collision, not a bug. No world is wrong today.

## Handoff

Found while tracing consumers of `villains.people` for `VILLAIN-FALL-UNRECORDED.md`: a grep for
`villain` across the reader packages returned the hero feature token, which on first read looked
like a live cross-package dependency on villain history and is not one.
