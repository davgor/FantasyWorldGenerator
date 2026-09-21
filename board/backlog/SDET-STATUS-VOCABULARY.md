# SDET-STATUS-VOCABULARY — one field name, seven namespaces, and no way to ask who is alive

Owner: contracts-and-vocabulary sweep. State: **STAYS OPEN. Half delivered 2026-09-21; the
three failures stand and are meant to.** `tests/test_status_vocabulary.py` is now 12 tests,
9 pass, 3 fail, 0.1 s, no world generated — the same three, unchanged and untouched.

**The unification was considered and deliberately not taken.** The three failures can only go
green if the person `status` enums of `heroes`, `npcs` and `villains` become one identical
enum, which is a rename of three shipped contracts. The conservative option this card itself
names — *a `liveness` sibling keyword on each person-level `status`* — was implemented instead,
and it closes the consumer-facing half without closing the tests. Both the choice and the
rejected alternative are written out under **"The ruling, and how to reverse it"** below, with
the two hard blockers the rename hits. Read that before taking this card further.

Earlier state, kept: partly closed by another lane; the harness control repaired here.

## What changed, 2026-09-20

**Two of the three defects are closed, by a different lane.** `Contracts/schemas/villains.schema.json`
now exists and `asset-list.schema.json` now carries an enum
(`supported | unreachable | schematic | not_started`), so
`test_every_status_a_block_emits_is_constrained_by_its_contract` passes. It is kept, because the
two ways of being undescribed — no enum, no schema — are permanent shapes and the assertion is
over the whole surface rather than over those two sites.

**The overload finding grew.** Publishing the villains schema put `living` into a second
vocabulary beside `hero-generator`'s, so `test_no_token_means_two_different_things` now reports
two overloaded tokens, `complete` and `living`, where it reported one. The complements differ
(`legend` against `fallen`), which is exactly the failure the card describes: a consumer that
learned `living` from one contract learned the wrong other half.

**The harness control had the ceiling-sentinel defect and fired for the wrong reason.** It read

    self.assertEqual((len(rows), sum(1 for r in rows if r[2])), (13, 12), ...)

and the villains schema made the surface `(14, 14)`, so a control whose job is to prove the
harness is not vacuous went red because somebody added a contract the board had asked for.
That is `SDET-CEILING-SENTINELS` in a different costume: a literal that is correct on the day
it is written and wrong the day the thing it counts legitimately moves. It now asserts the
structural walk agrees with an independent raw-text count of `"status": {` — which catches a
walker that starts annexing `route_status`, the near-miss this card warns about, because
`"route_status": {` does not contain `"status": {` — and names the thirteen sites the module
argues about instead of tallying them. A fifteenth `status` anywhere in `Contracts/` leaves it
green.

**Still open, and NOT fixed here:** the two liveness assertions. `LIVE` and `ENDED` are module
dict literals and `assertEqual(len(set(LIVE.values())), 1)` compares a literal against itself,
so neither can go green however the product changes. Deriving them needs a published
liveness mapping — a `liveness` sibling keyword on each person-level `status`, or a token
rename — which is a decision the Contracts owner has to take and which this lane does not own
(`hero-generator.schema.json`, `npc-roster.schema.json` and `villains.schema.json` are all
outside it). Both are left red and honest rather than rewritten into something weaker. See
`board/backlog/TIME-LIVENESS.md`, which needs exactly that predicate.

The surface table below is the pre-2026-09-20 state and is kept for the argument; the module
docstring in `tests/test_status_vocabulary.py` carries the current one.

Executable half of `PRODUCT-CONSUMER-VOCABULARY`. The enumeration below was produced by
walking every `*.schema.json` for a property literally named `status`, not by reading them.

## The surface

Thirteen declaration sites, twelve with an enum, five distinct vocabularies, plus one
unconstrained and one absent:

| tokens | where |
|---|---|
| `ok` · `failed` | block level in hero-generator, npc-roster, story-web, key-locations, key-location-plans |
| `living` · `legend` | `heroes.people[]`, `heroes.dreads[]` |
| `alive` · `dead` | `npcs.people[]` |
| `complete` · `empty` | `key_location_plans.plans[]` |
| `complete` · `partial` · `unbuildable` | city, hamlet and castle plan items |
| *(any string)* | `asset_list.assets[]` — declared `type: string`, no enum |
| `living` · `fallen` | `villains.people[]` — **declared in no schema at all** |

`route_status` (`routed` · `stranded`, in beast-movements and nomads) and `plan_status` are
**not** counted: they are different field names, and a collision analysis of the name
`status` may not borrow them.

## Two defects, separately

### 1. No consumer can ask who is alive

The live token is `living` for heroes, **`alive`** for npcs and `living` for villains. So
`status == 'living'` is right twice and silently wrong once. The end token is `legend`,
`dead`, `fallen` — three words for one event, two carrying a judgement the third does not, so
a consumer cannot even map them without first deciding what a legend is.

The only translation between two published contracts anywhere in the repository is a
hand-written expression inside a private record builder at `Sim/npc_roster/__init__.py:190`:

```python
'status': 'alive' if person.get('status') == 'living' else 'dead',
```

**That expression is the mapping.** It is published nowhere, so every downstream consumer
either rediscovers it or gets it wrong.

### 2. `complete` already means two different things

`key_location_plans.plans[]` uses it for *this plan has contents*; the city, hamlet and castle
plan items use it for *this item was fully placed*. A consumer comparing plan blocks on
`status == 'complete'` is asking two questions and will never be told which one it got.

### The villain leg is the worst of the three, and compounds another card

`villains.people[].status` is emitted with **no published definition**, so a consumer cannot
discover that `fallen` is a value it must handle. And per
`SDET-VILLAIN-FALL-UNREACHABLE.md`, no world that can be built ever contains one: the field
can only ever hold `living`. So a consumer writing `if status == 'fallen'` is writing dead
code that looks defensive — **and it cannot find that out**, because there is no schema to
tell it the value exists and no world that will ever show it one. That intersection with
`VILLAINS-NO-SCHEMA.md` is worse than either card alone.

`living` *is* declared — by `hero-generator.schema.json`, for a different block. A consumer
that found it there learned the wrong complement: a hero who is not `living` is a `legend`, a
villain who is not `living` is `fallen`.

## Proposed mechanism

**Not proposed**, and deliberately so: this is a schema change across at least two published
contracts, which `VILLAIN-FALL-UNRECORDED.md` already flagged as *"a recommendation to route,
not something either card should do on its way past"*. The cheapest honest step is to publish
the mapping that `npc_roster:190` currently keeps private, whatever else is decided.

## Dependencies and unresolved decisions

- `hero-generator.schema.json` and `npc-roster.schema.json` are published contracts; changing
  either enum is a consumer-visible interchange change needing a version move.
- `legend` and `fallen` are not synonyms for `dead` — they carry meaning a roster's `dead`
  does not. Collapsing them would lose information; keeping them needs a published mapping.
  Nobody has chosen.
- Blocked on nothing, but sequence behind `VILLAINS-NO-SCHEMA.md`: the villain leg cannot be
  fixed before the block has a contract to fix it in.

## Sources consulted

- `Contracts/schemas/hero-generator.schema.json` — block and person enums.
- `Contracts/schemas/npc-roster.schema.json` — block and person enums.
- `Contracts/schemas/key-location-plans.schema.json` — the `complete`/`empty` plan enum.
- `Contracts/schemas/world-output.schema.json` — the three plan-item enums.
- `Sim/npc_roster/__init__.py:190` — the only cross-contract translation there is.
- `board/backlog/PRODUCT-CONSUMER-VOCABULARY.md` — the prose argument.

## Files and assets in scope

`Contracts/schemas/hero-generator.schema.json`, `Contracts/schemas/npc-roster.schema.json`,
`Contracts/schemas/key-location-plans.schema.json`, `Contracts/schemas/world-output.schema.json`,
`Contracts/schemas/asset-list.schema.json`, `Sim/npc_roster/__init__.py`, `docs/npc-roster.md`,
`docs/hero-generator.md`.

## Acceptance and evidence

`tests/test_status_vocabulary.py` passes unmodified:

1. one token means alive across every block with people;
2. one token means no longer alive across the same;
3. no token appears in two `status` vocabularies;
4. every `status` a block emits is constrained by a contract — no free strings, nothing
   emitted that no schema declares.

Three tests must keep passing. Two are controls — the surface is 13 sites and 12 enums, and
the hand-written token maps match what the schemas declare. The third,
`test_a_block_outcome_cannot_be_read_as_a_person`, is a guard rather than a defect: `ok`/
`failed` and `living`/`legend` are disjoint today, so value-matching between those two depths
is safe, and the test exists so that stops being true audibly.

## Documentation impact

Whatever mapping is settled is published, or this recurs. `docs/npc-roster.md` is the natural
home since that package owns the only translation that exists.

## Adversarial review and limitations

- **Global disjointness is not claimed, and an earlier draft of this card claimed it.**
  `complete` disproves it. The surviving guard is scoped to person-versus-block, which is the
  axis the evidence supports. Both peer sessions caught the overclaim independently.
- **Not a defect, checked and dropped:** `npc_roster` reads a missing `status` as `dead` while
  `terrain_villains.is_standing` reads it as `living`. `status` is a *required* property of a
  person in both schemas, so no valid world omits it, and the villain default is deliberate
  backward compatibility for records written before a fall could be recorded. Each is
  defensible alone and the two never both fire. Recorded here so it is not re-found and filed.
- The villain tokens are derived by running the model rather than reading a literal, using
  `hold=99.` as a labelled instrument to make it emit its second token. That band is
  unreachable in any legal configuration; it is not a configuration and must not be read as one.
- `fallen` also appears in `key-locations.schema.json` as prose about a fallen *city*. It is
  unrelated and is not the villain vocabulary.

## Handoff

The lead came from the product red-team session. Its original form — block-level `ok|failed`
confusable with person-level `living|legend` — is **not currently true**: the two sets are
disjoint, so no adapter can read a failed block as a living person today. That is now a
passing guard, and the finding moved to the cross-block liveness predicate, which is real and
already bites. The coordinator supplied the `complete` overlap, with one correction: its table
counted `routed|stranded` as a sixth `status` vocabulary, and that is `route_status`.

---

## What was actually there — contracts-and-vocabulary sweep, 2026-09-21

The premise was re-run rather than re-read. **It reproduces, and the surface has grown again.**

- `tests/test_status_vocabulary.py` before any work: 7 tests, 4 pass, **exactly 3 fail**, and
  the three are `test_no_token_means_two_different_things`,
  `test_one_token_means_alive_across_every_block_that_has_people` and
  `test_one_token_means_no_longer_alive_across_every_block_that_has_people`. No fourth failure.
- The card's table says thirteen declaration sites and five vocabularies. The walk now finds
  **eighteen sites and eight vocabularies**. `read-place.schema.json` and
  `person-state-request.schema.json` landed tonight and added `present`/`gone` and a third
  statement of `alive`/`dead`. The harness control absorbed both without firing, which is the
  ceiling-sentinel repair working as intended.
- Both overloads are live: `complete` across `key_location_plans.plans[]` and the three plan
  item vocabularies, and `living` across `hero-generator` and `villains`.

## The ruling, and how to reverse it

The owner's standing instruction for this sweep is *pick the more conservative option, implement
it fully, and record the rejected alternative*. This card names exactly two options and the
choice between them is the card's own open question:

> Deriving them needs a published liveness mapping — a `liveness` sibling keyword on each
> person-level `status`, or a token rename — which is a decision the Contracts owner has to take.

**Chosen: the `liveness` sibling keyword.** Additive, changes no emitted byte, renames nothing,
invalidates no fixture, and publishes the translation where a consumer that cannot run Python
will find it.

**Rejected: the token rename**, which is the only thing that makes the three tests green. Four
reasons, two of them hard blockers rather than judgement calls:

1. **It requires a fenced file.** Every possible unification makes `docs/npc-roster.md:152`
   ("`living` maps to `alive`, `legend` to `dead`") false, and unifying on anything but
   `alive`/`dead` also makes `:29` false. That document is fenced to the naming session for this
   sweep, and the briefing rule is to stop and report rather than work around a fence.
2. **It would break a delivered, conformance-recorded API.** `PRODUCT-ACTOR-SCALE-API` is in
   `board/done/`. `Contracts/schemas/person-state.schema.json` publishes
   `token: living | legend | alive | dead | fallen`, and
   `docs/conformance/actor-scale-writes.md` states as a guarantee that the route "writes only
   `living`, `legend`, `alive`, `dead` and `fallen` — every one a word its block already used".
   A rename falsifies a shipped contract and a present-tense record on the day they landed.
3. **`TIME-LIVENESS` already answered this question the other way, and is closed.**
   `Sim/icarus_sim/terrain_liveness.py` opens by saying "no vocabulary is migrated: the
   per-package predicates stay authoritative". The sibling lane that hit the identical problem
   with the word `villain` recorded the same answer in `VOCABULARY-VILLAIN-TWO-AXES` —
   "answered with words rather than a rename".
4. **Blast radius on a tree five sessions share.** Twenty source files under `Sim/`
   (`hero_generator` alone touches ten), `Sim/npc_roster`, `Sim/story_web`, `Sim/key_locations`,
   `terrain_villains`, `terrain_corruption`, `terrain_liveness`; twelve test modules of which
   five are other lanes' untracked work tonight; `Fixtures/hero-generator-v1.json` and the
   162 MB `Fixtures/sample-world-v1.json`; five schemas with version moves; `Contracts/README.md`
   and `docs/hero-generator.md`. C1 part 3 of
   [030](../../docs/decisions/030-magnitude-and-identity-conventions.md) — no shipped schema is
   renamed — was ruled in this same sweep and points the same way.

**The cost of the choice, stated plainly:** `status == 'living'` is still right twice and
silently wrong once. A consumer that reads only the token is still wrong. What changed is that
the token is no longer all there is to read.

**To reverse it**, the owner has to decide three things first, and none of them is obvious:

- **Which pair.** `living`/`legend` loses the roster's `dead`; `alive`/`dead` loses `legend` and
  `fallen`. Neither is a synonym for the other: **`fallen` is a reign ending, not a death** — a
  fallen villain may still be alive — so collapsing it into `dead` publishes something untrue,
  and this card already warned that "collapsing them would lose information".
- **What happens to the judgement the lost word carried.** Either it is dropped, or it moves to a
  new field, which adds a field to three person records and moves every emitted byte again.
- **The `complete` overload separately.** Unifying the person vocabularies does not touch it.
  `key_location_plans.plans[]` (`complete`/`empty`) and the three plan-item vocabularies
  (`complete`/`partial`/`unbuildable`) must also stop sharing the word before
  `test_no_token_means_two_different_things` can pass, and that is a fourth shipped enum, three
  planners and `Sim/key_locations/core/exterior.py`.

Also required, in the mechanical direction: the three enums must be written in the **same order**,
because `vocabularies()` compares tuples, so `("living","dead")` and `("dead","living")` would
read as two vocabularies and re-fail the overload test.

## Delivered

### The mapping is published in the contracts, not only in Python

Each person-level `status` declaration now carries a `liveness` sibling mapping **its own
tokens** to `present` or `gone`:

| Declaration | Published mapping |
|---|---|
| `hero-generator.schema.json` `$defs/person`, `$defs/dread` | `living` → present, `legend` → gone |
| `npc-roster.schema.json` `$defs/person` | `alive` → present, `dead` → gone |
| `villains.schema.json` `people[]` | `living` → present, `fallen` → gone |

`present` and `gone` are not a new vocabulary: they are `terrain_liveness`'s own two states and
are already published by `person-state-request.schema.json`. **No sixth meaning of `status` was
added and no fifth `tier`.**

Each description also states the trap that made the annotation necessary — that the complement
differs across blocks, so a consumer that learned `living` from `hero-generator` learned the
wrong other half — and the villain one adds the clause a reader needs: `fallen` is a reign
ending, so `gone` there means gone from the band rather than dead.

`tests/schema_subset.py` gains `liveness` in `SUPPORTED`. That file **raises** on an unknown
keyword rather than ignoring it, deliberately, so an annotation has to be declared or every
validation of these three schemas dies. It constrains nothing; the comment beside it says so.

### Five tests, added, with the three failures untouched

`PublishedLivenessMappingTests` in `tests/test_status_vocabulary.py`:

- a control that the sites it maps are exactly the blocks `terrain_liveness` answers for, in both
  directions, so a fifth person block fails here until it is mapped;
- every person-level `status` publishes a mapping;
- the mapping is total over its own enum and two-valued, with exactly one token meaning present;
- the mapping agrees with `terrain_liveness.PRESENT_STATUS` / `GONE_STATUS` — compared rather
  than derived, because deriving one from the other would compare a value with itself;
- end to end: `liveness({'status': token}, block)` returns what the contract says for every
  token, **and an absent status resolves to `present`**, which is the clause every consumer gets
  wrong and the one that would turn every pre-departure world into a world of ghosts.

Nothing above the new class was edited except the module's shared walker, which was left alone:
`status_objects` and `declarations` were added beside `status_sites` rather than widening it,
because three existing tests unpack that one and a shape change to a shared walker is a silent
change to what they assert.

### Ablation — every new test watched to flip

Written first, run first, and red first: before the annotation existed, all four non-control
tests failed. Then each was re-ablated individually.

| Ablation | Result |
|---|---|
| (before implementation) no annotation anywhere | all four **red** |
| `villains.schema.json` loses its annotation | *publishes its mapping*, *is total*, *agrees*, *resolves a record* all **red**, naming `villains` |
| npc mapping disagrees with `terrain_liveness` (`alive` → gone) | *agrees* **red**, *resolves a record* **red** at `token='alive'` |
| npc mapping gains a token its enum does not declare | *is total* **red** |
| the control loses a block `terrain_liveness` answers for | *the sites this class maps* **red** |
| everything restored | back to exactly 3 failures |

**One test passed its first ablation and was repaired for it.** *Resolves a real record* looped
over the mapping's entries and, with no mapping, looped over nothing — the absent-status clause
carried the whole test and it went green with the feature removed. It now asserts the mapping is
non-empty before applying it. A comment in the test records this, because a green with the
feature deleted is a test of the fixture.

### Verification

- `python -m unittest tests.test_status_vocabulary` — **12 tests, 3 failures**, the same three,
  with the same messages, before and after.
- `python -m unittest tests.test_world_schema_conformance` — **18 tests, OK**, 70 s. This is what
  proves the annotation did not break validation: that module validates the `heroes`, `npcs` and
  `villains` blocks of a generated world against these three schemas, and a keyword
  `schema_subset` did not know would have raised rather than failed.

### Files

`Contracts/schemas/hero-generator.schema.json`, `Contracts/schemas/npc-roster.schema.json`,
`Contracts/schemas/villains.schema.json` (annotation only — no enum, no `required`, no version
moved); `tests/schema_subset.py`; `tests/test_status_vocabulary.py`;
`docs/conformance/actor-scale-writes.md`.

**No version was bumped, deliberately.** An annotation changes nothing a consumer could misread:
the same documents validate, the same values are legal, and the emitters are untouched. The
version consts in these schemas are bound to emitter constants in
`docs/conformance/version-bindings.json`, so moving one would require moving the emitter, which
would move every generated byte for a change that alters no data.

### Conformance record

`docs/conformance/actor-scale-writes.md` gains two sentences in the bullet that already states
where the cross-contract translation lives, because the answer to "where is it published" changed
from one place to two. `terrain_liveness`'s behaviour did not change and nothing else in the
record moved. No other record claims a module this touched — the three schemas are contracts and
`tests/schema_subset.py` is a test helper, neither of which `tools/docs_check.py` requires a
record to claim.

## What is NOT done

- **The three failures.** They are the finding and they still pin it. Anyone reading a green
  suite here should stop and check what was deleted.
- **The `complete` overload.** Untouched, and it is the one this card calls "unsafe quietly".
- **`read-place.schema.json`'s `post.status`** carries `alive`/`dead` with no annotation. It is a
  read-API projection rather than a block contract and belongs to the read-surface lane; the test
  scopes itself to the four emitted person records and says why.
- **Nothing reads the annotation.** `terrain_liveness` remains the running half and no code path
  consults the schema. That is deliberate — a second implementation of one rule is the defect
  that module exists to prevent — but it does mean the annotation's only enforcement is the test.
