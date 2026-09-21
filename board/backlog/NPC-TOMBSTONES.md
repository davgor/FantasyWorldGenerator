# NPC-TOMBSTONES — Carry the roster's dead across an age advance

> **BLOCKED 2026-09-21, not abandoned. Owner: none — it needs one whose fences allow it.**
> The premise was re-tested and reproduces; the design below is settled, both open questions are
> answered, a failing test pins the defect, and the exact patch each file needs is written out.
> **No product change was made, because every surface this needs is fenced to another live
> session**: `Sim/npc_roster/__init__.py`, `Sim/tests/test_npc_roster.py`, `docs/npc-roster.md`
> (naming session) and `Sim/icarus_sim/terrain_history.py` (sample-world and perf sessions). There
> is no part of this that can land without one of them, so none of it was started.

## Re-tested 2026-09-21 — confirmed, with a number

`Sim/tests/test_npc_tombstones.py` is new and **deliberately red**: 5 tests, 3 controls green,
2 defect pins failing, 0.02 s, no world generated. Treat it exactly as
`tests/test_status_vocabulary.py` is treated — **exactly two failures is correct, and zero means
someone deleted the evidence.**

- `test_a_person_whose_site_was_ruined_is_carried_as_dead_rather_than_dropped` —
  `24 uids vanished with no record that they ever existed`, beginning
  `npc-fortress-node-512-keep_tower-0`. One ruined city in the hand-built fixture takes its city
  posts, its hamlet's posts and its fortress's whole garrison with it.
- `test_a_carried_record_says_when_and_why_it_died` —
  `[] is not true : no record is marked as carried forward from the prior block`.

The three controls are what make those mean anything: a cast legend is **already** carried as
`status: 'dead'` (so this widens an existing exception rather than crossing a line for the first
time, exactly as the pairing note below says); the fixture advance removes one city and nothing
else; and the surviving city keeps every one of its people, so the failures are not the roster
collapsing.

**The pop-before-attach trap is real and is at `Sim/icarus_sim/terrain_history.py:480`:**
`result.pop('npcs',None)` runs before `attach(result)`, so the prior block is destroyed before the
only code that could read it is called. All **five** attach helpers do it — `_attach_heroes` (423),
`_attach_story_web` (435), `_attach_key_location_plans` (449), `_attach_key_locations` (466),
`_attach_npcs` (480).

The card's unrelated correction is also confirmed: `_attach_npcs`'s docstring says "It runs last
because it reads `heroes`", and the call block at lines 572–576 runs it **third of five**, before
`_attach_key_locations` and `_attach_key_location_plans`. It does read `heroes`, and heroes does
run first, so only the sentence is wrong.

## The two open questions are answered — take these, do not re-decide

Both are shared with `VILLAIN-FALL-UNRECORDED`, and both were settled there and have **already
landed in `docs/super-villains.md`**. Read off that document rather than taken second-hand:

1. **Retention: there is no horizon.** "`villains.fallen` is appended and never pruned, exactly as
   `ruins` is. There is no retention horizon and that is not a new policy: it is the one the world
   already runs for its dead cities. The world has a finite population, so its dead are a knowable
   set rather than an unbounded stream — which is the argument for recording them properly rather
   than the argument against." The roster takes the same answer, for the same reason and with the
   same words, so the two blocks do not diverge. **Delete this card's "Open: retention" bullet and
   the policy-authored horizon it proposes; do not implement a horizon, and do not add a
   `retention` policy key.** The card's acceptance line "the retention rule, whatever it becomes,
   is exercised by a test that runs enough ages to trigger it" becomes: a test that runs several
   ages and asserts **nothing is dropped**.
2. **A carried record keeps its `important` earmark.** The house shape is one list, a status
   field, and the reader filters — `heroes` `living|legend`, `npcs` `alive|dead`, `story_web`
   filtering on `living`, and now `villains` `people` with `status: 'fallen'` beside
   `standing()`. `important` answers "was this person worth naming", which stays true of a corpse
   and is what makes the corpse addressable for "recover what he was carrying". **The offer gate
   is `status == 'alive'`, not `important`**, and that sentence belongs in `docs/npc-roster.md`
   and in the schema's `important` description. Separating the earmark from the offer would make a
   second axis for a question one field already answers, which is precisely how the block ended up
   with three status vocabularies.

## The patch each fenced file needs

Written out so whoever holds the fences can land it without re-deriving anything.

**`Sim/icarus_sim/terrain_history.py` — `_attach_npcs`, three lines.** Read before popping, and
hand the prior block to `attach` rather than leaving it in the world, so `generate` stays a pure
function of its arguments:

```python
from npc_roster import attach
prior = result.get('npcs')          # BEFORE the pop, which is the whole design
result.pop('npcs', None)
block = attach(result, prior)
if block is not None: result['npcs'] = block
```

Fix the docstring's "It runs last" to "It runs third of five, after `_attach_story_web`" in the
same edit. **Do not copy this into the other four helpers.** They do not need prior state, and
four speculative copies of a seam is how the pop-before-attach trap got there.

**`Sim/npc_roster/__init__.py`.** `attach(world, prior=None)` and
`generate(world, policies=None, prior=None)`; `generate` diffs `prior['people']` against the
people it just derived and appends every uid the new derivation no longer produces, with
`status: 'dead'`, `carried: True`, `died_age`, and a `cause` of `site_ruined` when the site moved
into `world['ruins']` (which retain `uid`, `name`, `city_class` and `civilization_id`) or
`post_removed` when the site survives and the plot is gone. Add `prior_age` to the block and
`carried` / `vanished` to `summary`. Carried records sort into `people` by the existing key, so
`validate_repo`'s double-generate byte-compare is unaffected: a fresh generation has no prior
block on either run.

`_validate` must **refuse** a prior block whose `version` it does not understand rather than
silently dropping the dead — silently discarding a tombstone is the failure this card exists to
prevent. `attach` already turns a raise into `{version, status: 'failed', error}`, which is the
right visibility.

The line-190 expression `'alive' if person.get('status') == 'living' else 'dead'` is the seam a
concurrent session wants to publish through `terrain_liveness`. **These two changes are
compatible and want serialising, not merging**: the liveness change replaces that one expression,
this card adds a second writer of `status` beside it. Land the liveness mapping first and this
card writes through it.

**Version:** `npcs` moves 1 → 2. A block that is no longer a pure function of the current world
is a contract change and a consumer could otherwise misread a carried record as a live one. Add
an `npcs` binding to `docs/conformance/version-bindings.json` — there is none today — and bump
`Contracts/schemas/npc-roster.schema.json`.

**`docs/npc-roster.md`.** The limitations section states this gap explicitly and becomes false;
the schema's `status` description says absence means gone and becomes false. Both need rewriting,
plus the two rulings above. Line 73 of that file is *separately* already false, from
`SDET-SITE-ID-ORDINALS` in the same sweep: it says the cast builds `hero-castellan-fortress-36` on
the ordinal, which it no longer does.

**A decision record** is still wanted, as this card asks — but it records a **widening**, not a
first crossing: `npc_roster/__init__.py:190` already writes `status: 'dead'` for a cast legend, so
the block already is not a pure function of who is currently alive.

## Requested behavior

The `npcs` block must remember the people it used to hold. Today a person whose city is ruined by an age advance simply stops appearing: there is no tombstone, no cause, no record that they ever existed. A consumer holding a uid across the advance cannot tell "this person died" from "this person never existed" from "the producer renamed the key", and the only correct reading is that an absent uid means gone.

That was an accepted limitation when [NPC-ROSTER](../done/NPC-ROSTER.md) shipped, on the grounds that `status` is birth state and a runtime owns death in its own save. It is now load-bearing for a second package: the nomads work resolves a band's `refuge_uid` against `sites | ruins` precisely because a band's `basis` can outlive the roster records it points at. A quest anchored on "recover what he was carrying" needs the corpse addressable, which the quest work asked for explicitly and this block cannot currently provide.

## Proposed mechanism

`npc_roster.attach` reads the **incoming** `npcs` block as prior state before it is popped, diffs it against the new derivation, and carries forward every uid the new one no longer produces as `status: 'dead'` with a `died_age` and a typed `cause`.

The wiring detail that decides whether this works at all: `_attach_npcs` in `terrain_history.py` currently pops the previous block before calling `attach`, copied from `_attach_heroes`. It must read the prior block first, then pop, then attach — a verbatim copy of the cast's helper silently defeats the whole design.

Causes are derivable from what the world already exports: `site_ruined` when the site moved into `world['ruins']` (which retain `uid`, `name`, `city_class` and `civilization_id`), and `post_removed` when the site survives but the plot is gone. Add `carried: true` to a carried record, `prior_age` to the block so a consumer can tell a first derivation from a continued one, and `carried` / `vanished` counters to `summary`.

## Dependencies and unresolved decisions

- Determinism is preserved: a fresh generation from the same seed produces the same sequence of prior blocks, and `tools/validate_repo.py` generates a seed-42 size-17 world twice with no prior block on either, so the byte-compare gate is unaffected. Confirm this rather than assume it.
- `_validate` must **reject** a prior block whose `version` it does not understand rather than silently dropping the dead. Silently discarding a tombstone is the failure this ticket exists to prevent.
- Open: whether a carried record keeps its `important` earmark. A dead quest giver is still addressable as a corpse but must never be offered, so the earmark and the offer may need separating.
- Open: retention. Carrying every person who ever lived grows the block without bound across many ages; a horizon (drop after N ages, or keep only the earmarked dead) is probably wanted, and the choice should be authored in policy rather than hardcoded.
- Not in scope: runtime death. Nothing here kills anyone the world did not kill.

## Sources consulted

`Sim/npc_roster/**` and `docs/npc-roster.md` (the limitation as shipped), `Sim/icarus_sim/terrain_history.py` (the plan rebuild and the pop-before-attach trap in both attach helpers), the nomads card (`refuge_uid` against `sites | ruins`), and the quest work's request that a corpse stay addressable.

## Acceptance and evidence

- A two-age world whose city is ruined in the second age: its people are present with `status: 'dead'`, `cause: 'site_ruined'` and the correct `died_age`, and a uid held from the first age still resolves.
- A surviving post keeps its uid and stays alive across the advance; a removed plot marks its occupant dead rather than vanished.
- An unreadable or unversioned prior block fails loudly instead of dropping the dead.
- Replay stays byte-identical and `validate_repo`'s double-generate comparison still passes.
- The retention rule, whatever it becomes, is exercised by a test that runs enough ages to trigger it.

## Paired with VILLAIN-FALL-UNRECORDED — shape reconciliation

Added by the bug-hunt session. The coordinator asked for these two to be answered together, since
both ask the same question: what persists when someone stops existing. Reading them as a pair
produced two corrections, one to each card.

**This card's mechanism is right, and it is less of a change than it says it is.** The opening
claim — "there is no tombstone, no cause, no record that they ever existed" — is true for a person
whose site was ruined, and **not** true of the block in general. `npcs.people` already carries
records with `status: 'dead'` today: `Sim/npc_roster/__init__.py:190` writes
`'status': 'alive' if person.get('status') == 'living' else 'dead'` when it folds the cast in. So
the dead already live in this list, for one subset of people, with the field this card proposes.

That reframes the work. It is not "make the block stop being a pure function of the world" as a
new property — it is already not one, for heroes. It is extending an existing exception to the
people the block derives itself. The decision record this card asks for is still worth writing,
but it records a widening rather than a first crossing.

**The house shape is settled and neither card needed to invent it.** Three blocks already do this
the same way — one list, a status field, consumers filter:

- `hero_generator`: `status: living | legend`, enum-declared in `hero-generator.schema.json`.
- `npc_roster`: `status: alive | dead`, as above.
- `story_web`: `Sim/story_web/__init__.py:66` filters the cast on `status == 'living'`.

`VILLAIN-FALL-UNRECORDED` originally proposed a separate `fallen` key for villains. That is
**withdrawn** — it would have made a fourth shape for the same axis. Both cards now propose
in-list status, which is what `terrain_villains` already half-implements.

**One thing the pair should settle that neither card can settle alone:** the three blocks use
three vocabularies for one axis — `living|legend`, `alive|dead`, `living|fallen`. A consumer
joining two of them cannot write a single predicate for "is this person still here". Worth
routing as its own decision while both cards are open; it is a schema change on two published
contracts, so neither card should do it in passing.

**Retention is one answer, not two.** This card raises the unbounded-growth problem and suggests a
horizon authored in policy. The villain card inherits exactly the same problem. Whatever horizon
is chosen should apply to both, and be written once — two separately-chosen horizons for the same
question is how the vocabulary above happened.

**The wiring trap this card identifies is real and is not villain-specific.** `_attach_npcs` popping
before `attach` is the shape, but all four helpers do it — `_attach_heroes`, `_attach_story_web`,
`_attach_key_locations` and `_attach_key_location_plans` pop their block before calling. Any of
them that later needs prior state inherits the same defeat. Worth fixing as a pattern when the
first one genuinely needs it, rather than four times separately.

*(Unrelated correction found while reading the attach helpers: `_attach_npcs`'s docstring says "It
runs last because it reads `heroes`". It runs third of five, at both call sites. It does read
`heroes`, and heroes does run first, so the behaviour is correct and only the sentence is wrong.
Not worth its own card; fold it into whichever change touches this helper next.)*

## Documentation impact

`docs/npc-roster.md` (the limitations section states this gap explicitly and must be rewritten when it closes), the schema's `status` description (which currently says absence means gone), and a short decision record: a block that is no longer a pure function of the current world is a genuine contract change and deserves one.
