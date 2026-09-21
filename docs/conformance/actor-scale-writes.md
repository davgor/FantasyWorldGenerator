---
conformance: 1
record: actor-scale-writes
tier: EXERCISED
summary: Writes the two things a playing session changes that only it can know - what its party did with a quest offer, and whether a person is still in the world - at the scale a session works at rather than at age or era scale.
modules:
  - Sim/icarus_sim/terrain_quest_actions.py
  - Sim/icarus_sim/terrain_quest_api.py
  - Sim/icarus_sim/terrain_person_state.py
  - Sim/icarus_sim/terrain_person_api.py
emits:
  - path: quest_actions
    schema: Contracts/schemas/quest-actions.schema.json
  - path: person_state
    schema: Contracts/schemas/person-state.schema.json
versions:
  - id: quest-api
    assert: 1
  - id: person-api
    assert: 1
proof:
  - path: Sim/tests/test_quest_actions.py
    establishes: the two transitions and their refusals without a world, that a taken quest does not expire on its offer window, that abandon closes with its reason and its day, one operation per call that changes the world and none otherwise, byte identity of repeated calls, that the caller's world is untouched on every refusal including mid-batch, and what an age boundary does to a taken quest
  - path: Sim/tests/test_person_state.py
    establishes: that every block translates in both directions through terrain_liveness, that a block handed in where a person belongs raises, that a no-op writes nothing, the refusal envelope over uid, status, reason and day, that the census moves by one, that a gone giver closes its quest on the next tick and not before, that the roster mirror is not updated, and that npc_roster's private translation still agrees with the published one
decisions: []
tickets:
  - board/done/PRODUCT-ACTOR-SCALE-API.md
  - board/done/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md
  - board/backlog/NPC-TOMBSTONES.md
  - board/done/VILLAIN-FALL-UNRECORDED.md
---

# Conformance: actor-scale writes

## What it produces

A world in which one quest has been taken or let go, or one person is recorded as gone or
back. Both are facts only a playing session holds: the world decides whether an offer still
*stands*, never whether a party accepted it, and it does not model the combat, travel or
illness that would remove a person from it.

Everything else the API offers moves the world at age or era scale. `generate`,
`advance-age`, `advance-time`, `summon`, `found-settlement`, `corrupt`, `cleanse` and
`nomad` move continents, ages, gods and nations. These two routes are the writes a session
makes between those.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `quest_request(body)` | `terrain_quest_api` | Quest API 1. World in, new world out. `POST /world/quest`. |
| `validate_actions(actions)` | `terrain_quest_actions` | The normalised `actions` array, or a refusal. Pure. |
| `transition(quest, action, day, alternatives)` | `terrain_quest_actions` | The new quest record and its log entry. Pure; the given record is not mutated. |
| `person_state_request(body)` | `terrain_person_api` | Person API 1. World in, new world out. `POST /world/person-state`. |
| `index(world)` | `terrain_person_api` | `uid -> [(block key, list, liveness block, position)]` over every person list. |
| `validate_changes(changes)` | `terrain_person_state` | The normalised `changes` array, or a refusal. Pure. |
| `plan(record, block, status)` | `terrain_person_state` | The new person record, the state before and the state after. Pure; `None` when nothing needs writing. |
| `token(block, state)` | `terrain_liveness` | The word `block` writes for `present` or `gone`. The inverse of `liveness`. |

## Inputs it reads

The same world gate a tick asks, `terrain_time.validate_time_world`: a recipe 3 world
through creatures (phase 13) with `terrain` 6, `generator_version` 16, `recipe` 3 and
`astrology` 1. Asking a weaker question here would admit a world `advance-time` refuses a
moment later, and a caller would learn that on its next call rather than on this one.

The quest route additionally requires a `quests` block, which only exists once the world
has been advanced by at least one day -- that is what opens the offers. The person route
requires at least one of `heroes`, `npcs` and `villains` to carry people.

Neither route reads a layer, a grid or a catalogue, and neither consults `world_options`.

## Artifacts it writes

`quests` -- the block [time-advance](time-advance.md) owns. The quest route sets `state` and,
for an abandonment, `closed_day` and `closed_reason`, and appends one entry to `quests.log`
per action. **No key is added to a quest record and no version moves**: `taken` and
`abandoned` are two of the states that capability already writes, and the day an offer was
taken is in the log rather than on the record.

`heroes.people[].status`, `heroes.dreads[].status`, `npcs.people[].status` and
`villains.people[].status` -- one field on one record per change, in that block's own
vocabulary. Nothing else in those blocks is touched.

`quest_actions` -- `{api_version, day, applied, actions[]}`, the report for the call just
made. `person_state` -- `{api_version, applied, changes[], notes[]}`, the same. Both are
overwritten by the next such call and describe no earlier one. They are **not** registered
in `terrain_history.STATE_KEYS`, which is correct and matches `time_advance` and
`settlement_founding`: that tuple lists blocks `materialize_stage` must rebuild per stage,
and the report of a call is not state. The blocks these routes genuinely change --
`quests`, `heroes`, `npcs`, `villains` -- are all registered already.

`history.operations` gains one entry per call **that changes the world**, carrying the
actions, or the changes that were actually applied, verbatim. A quest call with an empty
`actions` array, and a person call whose every change asks for the state a record already
holds, change nothing and record nothing; a person call that applies two of three changes
records two. This matches the age band's estimate path. `history.replay` is left exactly as
found; rewording it would make that key flip between two strings depending on which route
ran last.

Neither route writes `timing_ms`. Every value in it is wall clock, and a document whose
byte-reproducibility is a contract should not gain a fresh one because a party accepted a
quest.

### Binding invariants

- **Neither route consumes randomness.** There is no stream to key, so there is no way for
  one to be keyed on a call ordinal. A quest's one random quantity, its offer window, is
  drawn by `terrain_time` from the absolute step index and is never redrawn here.
- **The caller's world is byte-identical afterwards, on every path.** The person route
  resolves and refuses every change before it copies anything, so no partly written world
  exists even transiently. The quest route validates the request shape before it copies and
  applies against its own copy, which is discarded on a raise.
- **Only the blocks a call touches are copied.** Everything else in the returned document is
  the caller's own object, shared rather than duplicated, as the instant band of
  `advance-time` already shares what it does not write. Nothing is mutated in place. A block
  a change named but did not move is still copied, identically; a call in which *nothing*
  moved discards its copies and returns the caller's blocks unchanged.
- **No sixth status vocabulary is published.** The person route speaks `present` and `gone`,
  which are `terrain_liveness`'s own states, and writes only `living`, `legend`, `alive`,
  `dead` and `fallen` -- every one a word its block already used.
- **Every liveness read and write goes through `terrain_liveness`.** The current state is
  read with `liveness`, the new word comes from `token`, and the result is read back through
  `liveness` before it is returned. A record carrying `people`, `quest_hooks` or
  `policy_revision` raises, because `hero_generator` and `npc_roster` both write a
  block-level `status` of `ok`/`failed` under the same key name as the person-level one.
- **An absent status still reads as present, and a no-op writes nothing.** Asking for the
  state a record already holds returns it unchanged rather than stamping a word in, so a
  record written before its package recorded departure keeps having none.

### Facts that look incidental and are load-bearing

- **A take past the offer window is refused.** `terrain_time._quest_step` tests the window
  only while a quest is `offered`, so a take applied after the window closed but before the
  next sweep would leave `offered` and never reach the expiry branch again. The offer would
  be immortal. This is the one refusal the quest route adds that the resolution array has no
  analogue for.
- **An abandonment closes with `closed_reason: 'abandoned'`, not `'resolved'`.** Both reach
  the `abandoned` state. A resolution is the game reporting an outcome it played; this is
  the party putting the promise down without claiming one, and a consumer reading the board
  should be able to tell them apart without re-reading the log.
- **`token` lives in `terrain_liveness` beside `PRESENT_STATUS`, not in the writer.** A
  second table of the same words elsewhere is the defect that module exists to prevent.
- **The one translation between two published contracts stays where it is.**
  `Sim/npc_roster/__init__.py` maps a hero's `living` to a roster record's `alive`. That
  expression cannot be replaced by a call to `token`, because the leaf packages are
  forbidden from importing the generator -- `npc_roster/policy.py` states the rule, and the
  readers take `child_seed` from the shared, generator-free `world_geometry` package rather
  than break it. So the mapping is
  published in `terrain_liveness` and `Sim/tests/test_person_state.py` binds the roster's
  copy to it, which is the shape `test_npc_roster` already uses for that package's
  `posts.json` snapshot. Since 2026-09-21 it is **also** published where a consumer that
  cannot run Python will find it: each person-level `status` in
  `hero-generator.schema.json`, `npc-roster.schema.json` and `villains.schema.json` carries
  a `liveness` annotation mapping its own tokens to `present` and `gone`, and
  `tests/test_status_vocabulary.py` compares the two statements rather than deriving either
  from the other. Nothing here reads the annotation; `terrain_liveness` remains the running
  half.
- **A uid claimed by two blocks is refused, not resolved.** No generated world has one, but
  that is a fact about the uid minters rather than a guarantee any of them makes, and
  resolving it by iteration order would silently write the wrong person.
- **`terrain_person_api.index` is a second resolver on purpose, and is bound to the first.**
  `terrain_time._giver_index` answers a narrower question -- who can hold a quest open -- so
  it spans `heroes.people`, `heroes.dreads` and `npcs.people` only, keeps the first writer
  of a uid, and returns `(record, block)`. A writer needs the list and the position to put
  a record back, needs villains, and must refuse a contested uid rather than prefer one. The
  two are held to the same answer by a test rather than by a shared function, because the
  shared function would have to be the wider one and widening `_giver_index` would change
  which people the quest lifecycle considers.

### Refusals

Every refusal raises `terrain_errors.RequestError` with the envelope
[request-failures](request-failures.md) describes. `api_version` carries `retry: false`.

| Refusal | Shape |
|---|---|
| unknown request field, unknown `quest_id`, unknown `uid`, a missing person-change field | `unknown_field` |
| `action` outside take/abandon, `status` outside present/gone | `invalid_choice` |
| a non-list `actions`/`changes`, a non-object item, a bad `uid`, `reason` or `day` | `wrong_type` |
| more than 1024 actions or changes, a `reason` over 200 characters | `over_capacity` |
| a world with no `quests` block, or no person lists at all | `missing_block` |
| a quest that is already closed, already taken, or whose offer window has lapsed; a uid in two blocks | `refused_by_world` |

`refused_by_world` is the distinction that matters: the request was well formed and the
world is the constraint. A caller that cannot tell that from a malformed argument keeps
correcting a value that was never wrong.

### Partial failure

There is none, and on the person route there is none even in principle: every change is
resolved against the caller's world before anything is copied. On the quest route a raise
mid-batch discards the copy, so the caller holds exactly the world it passed in.

## Where it runs

Not part of generation. Only when a caller asks, through `POST /world/quest`,
`POST /world/person-state` or the two request functions, against a world generation has
already finished and a tick has already opened quests.

These are **new writers of blocks other capabilities own**. `quests` was written only by
`advance-time`; `heroes`, `npcs` and `villains` were written only at generation or at an age
boundary. After these routes exist, all four can change at any moment a caller chooses.
[time-advance](time-advance.md) states this on the quest side. The records for
`hero-generator`, `npc-roster` and the villain cast do not exist yet and must state it when
they are written; the canonical documents [hero-generator](../hero-generator.md) and
[npc-roster](../npc-roster.md) describe generation and are not made false by this, because
neither claims its block is written once.

**Nothing cascades.** A person marked gone keeps their quests open until the next tick,
which is when `terrain_time._quest_step` reads liveness and closes an offer as `giver_gone`
-- exactly as it already does for a giver the world itself removed. A hero marked gone does
not update the roster mirror `npc_roster` copied out of `heroes` at generation time; that
copy is a snapshot and is rebuilt at the next age boundary. A villain marked gone keeps its
claims and its held nodes and does not appear in `villains.fallen`. The report says all
three in its `notes`.

### The age boundary

**A taken quest does not cross an age, and there is no durable anchor because none is
wanted.** An age is five thousand years
([028](../decisions/028-an-age-is-five-thousand-years.md)) and `heroes` is regenerated
wholesale at the boundary, so the people who offered and populate an offer are gone. When
`advance-time` turns an age it closes every quest still `offered` or `taken` with
`closed_reason: 'age_turned'`, records each closure in `quests.log`, and rebuilds the board
from the new age's hooks. A game that accepted those quests loses that work, visibly and
under a reason it can show a player.

`age_turned` is not `hook_gone`, and a consumer must not collapse them. `hook_gone` is one
hook leaving `heroes.quest_hooks` while the world around it stands; `age_turned` is the
world moving on. Reaping used to arrive only as the first of those, by accident: the sweep
walked hook ids, most were re-minted as different strings, and the quests behind them
closed as `hook_gone`. The ones the regenerated cast happened to mint identically --
`hero-reeve-hamlet-node-<n>`, `hero-sovereign-<city uid>` -- survived instead, carrying the old
age's `anchor`, `verb` and `stated_purpose` against the new age's target check and a
`giver_uid` naming nobody. It is keyed on the age turning now, not on which ids
disappeared, and the previous age's rows are retired with it rather than kept beside the
new ones, because a retained row whose id the new cast re-mints could not be told apart
from the offer that id now names. `Sim/tests/test_quest_actions.py` pins the whole board
rather than the two halves of an accident.

**`POST /world/advance-age` does not do this.** The reap is `terrain_time`'s, because the
day a quest closed on is the clock's and the clock is that capability's; a caller that turns
an age through the age route directly carries its board across unchanged and is holding the
chimera this describes.

## Versions asserted

| What | Value |
|---|---|
| Quest request API | <!-- conformance:version quest-api=1 --> |
| Person request API | <!-- conformance:version person-api=1 --> |

Neither the `quests` block version nor any person block's version moves. The quest route
writes states that block already declared, and the person route writes words those blocks
already used.

## Proven by

`Sim/tests/test_quest_actions.py` and `Sim/tests/test_person_state.py`. Roughly half the
tests are pure and need no world; the rest advance one size-17 seed-42 world by a month and
act on the quest board it opens. That world is generated once and the second module borrows
it from the first, which is the fixture-sharing idiom `test_story_web` already uses. One
class advances an age, which is the expensive one and the reason it stands alone. Counts are
description, not invariant; recount rather than trusting a sentence.

The load-bearing ones are `test_take_is_honoured_by_the_lifecycle_that_already_reads_it`,
which is the whole point of the quest route;
`test_the_callers_world_is_never_touched_on_any_path` in both files, including the
mid-batch refusal that a late-validating route would fail;
`test_a_plan_goes_through_the_predicate_and_refuses_a_block`, which is the seam the person
route exists to stay inside; and the two age-boundary tests, which are the ruling.

## Why it works this way

Two routes rather than two more arrays on `advance-time`. Taking a quest happens at an
instant and not over a span, and a caller that only wants to record an acceptance should not
have to name an elapsed time it does not mean. The operation record then says what happened
instead of recording a player's decision as a side effect of a clock.

The quest channel is a writer for a state the reader has had all along. `taken` has been in
the lifecycle since the clock landed and is already honoured -- it is what stops a quest
expiring on its offer window -- but no request field set it, so a game that accepted a quest
wrote that state into the persisted document by hand. Once a consumer edits a world outside
a request boundary, every invariant the boundary exists to enforce stops being enforceable.

The person channel publishes the predicate's vocabulary rather than a new one because there
are already five sets of words for `status` in the published contracts and
`tests/test_status_vocabulary.py` enumerates them. A sixth claiming to unify them would be
the sixth.

## Does not establish

- **Nothing about what persists when someone stops existing.** No tombstone is written, no
  claim decays, no post is vacated, no roster mirror moves.
  [NPC-TOMBSTONES](../../board/backlog/NPC-TOMBSTONES.md) and
  [VILLAIN-FALL-UNRECORDED](../../board/done/VILLAIN-FALL-UNRECORDED.md) share that
  question with this one and `board/README.md` requires the three to take the same answer,
  so it is not answered here alone.
- **No combat, inventory, economy, settlement population, quest authoring or party
  position.** Each is a modelling commitment the generator has deliberately not made --
  [nomads](nomads.md) records that no band consumes forage, fights or dies -- and nothing
  here reverses it.
- **Nothing about a taken quest surviving an age.** The behaviour above is described and
  pinned; it is not endorsed, and the ruling is open.
- **Nothing about the state of `timing_ms` elsewhere.** Both routes act on a world the CLI
  persisted, and a world one returns is still the reproducible document it was handed,
  because neither writes a timing. That is a smaller claim than it looks: the seam these
  routes would otherwise have hit is guarded at `terrain_history.adopt_world` for every
  stateless API that does copy a world, which is what closed
  [TIME-PERSISTED-WORLD-CANNOT-ADVANCE](../../board/done/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md).
  Nothing here re-establishes that for anyone else.
- **No native `Core/` port exists** and none is claimed. `Core/` implements generate and
  advance-age only.
