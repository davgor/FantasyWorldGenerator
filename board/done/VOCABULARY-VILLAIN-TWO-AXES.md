# VOCABULARY-VILLAIN-TWO-AXES — `villain` names two unrelated things across package boundaries

Owner: reader-packages sweep, 2026-09-21. State: **DONE — answered with words, not a rename.
The owner should read the cost correction below before accepting that.**

## Delivered 2026-09-21

The collision is now stated at every place a reader meets either `villain`: the two definition
sites in source, and all three documents.

**Failing test first.** `Sim/tests/test_villain_vocabulary.py`, 6 tests, 3 controls and 3
disambiguation assertions. Before the change, the three were red:

- `test_every_document_names_the_other_villain` —
  `['docs/hero-generator.md', 'docs/story-web.md', 'docs/super-villains.md'] != []`
- `test_both_definition_sites_disclaim_the_other_villain` —
  `['Sim/hero_generator/features.py', 'Sim/story_web/facts.py'] != []`
- `test_the_super_villain_document_points_back_at_the_feature_token` —
  `'villain:prior_age' not found in ...`

All six pass now, in 0.09 s, with no world generated. The three **controls** were written to pass
and did: the token is declared in both packages' vocabularies; a world with **no `villains` key at
all** precipitates two people carrying it (move the fixture's founding age to 2 and the
dispossessed pretenders appear), and none of them carries `region`, `reach_m`, `growth`,
`held_nodes` or `seat_uid`; and the two published contracts are read off disk rather than from
memory to fix the overlap.

### The card's cost argument does not survive measurement

The card says the token is carried in `Fixtures/hero-generator-v1.json` and
`Fixtures/story-web-v1.json` "in recorded output", so "both would need regeneration, which makes
this a fixture-moving change and not a tidy-up."

**Measured: the string `villain` occurs zero times in either fixture.** `hero-generator-v1.json`
pins nine scalar fields per person and never records `selectable` at all;
`story-web-v1.json` carries `selectable` lists as *input* and none of them holds the token.
`Contracts/schemas/hero-generator.schema.json` declares `selectable` as
`{"type": "array", "items": {"type": "string"}}` — **the feature vocabulary is in no published
schema**, so the rename is not a schema change either.

The real fixture cost is different and smaller, and the card did not name it: the token lives in
three *policy* files, each carrying an authored integer `revision` that travels in every block's
`policy_revision` and is pinned by both fixtures. A rename therefore needs
`archetypes.json` 4→5, `tropes.json` 7→8, `weights.json` 3→4, and the matching five integers
edited in the two fixtures. Nothing else in either fixture moves, because renaming the emitter and
the `requires` token together leaves eligibility — and therefore every archetype, weight, spoke and
thread — identical.

The token **is** in emitted output: 40 occurrences in `Fixtures/sample-world-v1.json` (seed 42,
size 33). So the rename does move a generated world, but that fixture is already stale from
SDET-SITE-ID-ORDINALS in the same sweep.

### A finding that rules out one of the two proposed names

The card offers `claim:prior_age` **or** `dispossessed:prior_age`. **`claim:` is taken.**
`story_web.facts` builds `{'claim:' + v for v in CLAIM_VERBS}` — `claim:hold`, `claim:retake`,
`claim:avenge` and eight more, 254 occurrences in the sample world. `claim:prior_age` would land
inside the claim-verb namespace and read as an eleventh verb, trading one same-word collision for
another. **If the rename is taken, it must be `dispossessed:prior_age`.**

### The decision, and the alternative rejected

**Chosen: document, do not rename.** The sweep's standing instruction on an unresolved design
question is to take the more conservative option, implement it fully and record the other. Renaming
changes a token in emitted output that a consumer may already read, in a world where four other
sessions are mid-change in the same two packages; documenting changes no byte of any world. Both
are inside this card's own acceptance ("*Either* the token no longer reads as a reference to a
super villain, *or* all three documents say it is not one").

**Rejected: the rename**, which the card prefers and which is now measurably cheaper than the card
believed — six source and policy files, five integers in two fixtures, no schema change, no fixture
regeneration. It is recorded here in full so the owner can trigger it in one move:

| File | Change |
|---|---|
| `Sim/hero_generator/features.py:61` | the emitted token |
| `Sim/hero_generator/archetypes.py:36` | `FEATURES` membership |
| `Sim/hero_generator/policies/archetypes.json:234` | a `requires` conjunction; `revision` 4→5 |
| `Sim/story_web/facts.py` | `HERO_FEATURES` membership |
| `Sim/story_web/policies/tropes.json:190` | a `requires` conjunction; `revision` 7→8 |
| `Sim/story_web/policies/weights.json:13` | `gainable_features`; `revision` 3→4 |
| `Fixtures/hero-generator-v1.json` | `policy_revision.archetypes` 4→5 |
| `Fixtures/story-web-v1.json` | `policy_revision.tropes` 7→8, `.weights` 3→4 |

The three documentation paragraphs written here stay useful after a rename: `terrain_villains`
keeps the word `villain`, and a reader still needs to be told that the hero-side token is not it.

### The open question, answered by measurement

*"Whether the feature vocabulary is considered a public contract."* It is **emitted but not
declared**: it reaches consumers in `heroes.people[].selectable`, and no schema in
`Contracts/schemas/` constrains it. That is the worst of both — a consumer can depend on it and
nothing tells them what they may depend on. It is not fixed here, and it is the shape
`PRODUCT-CONSUMER-VOCABULARY` is about. **If the vocabulary is ever declared as an enum, the
rename must happen first**, because declaring it freezes whichever spelling is in place.

### One more collision found while measuring, not fixed

The two contracts share seven field names: `uid`, `status`, `tier`, `born_age`, `log`, `school`,
`well`. **`tier` is the live trap** — `number` in `villains.schema.json`
(continuous, converts to a reach in metres) against `enum: [notable, renowned, legendary]` in
`hero-generator.schema.json`. That is a fifth meaning of `tier`, and it belongs with the `tier`
card rather than here. `test_villain_vocabulary.py` pins the overlap set, so a sixth shared field
appearing will fail rather than pass unnoticed.

### Files changed

`Sim/hero_generator/features.py`, `Sim/hero_generator/archetypes.py`, `Sim/story_web/facts.py`
(comments only — no expression changed, no token moved, no output moves),
`docs/hero-generator.md`, `docs/story-web.md`, `docs/super-villains.md`,
`Sim/tests/test_villain_vocabulary.py` (new).

**Conformance:** none touched, and the reason is not "nothing seemed to fit". No record claims
`Sim/hero_generator/**` or `Sim/story_web/**` — both packages sit in `coverage.json`'s `uncovered`
allowlist under `board/in-progress/CONFORMANCE-DOCS.md` — and no record describes the feature
vocabulary. Nothing a record states became true or false here.

**No version moved and none should have:** this change alters no emitted byte. Every edit is a
comment or a document.

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
