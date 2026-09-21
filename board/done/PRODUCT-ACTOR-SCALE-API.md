# PRODUCT-ACTOR-SCALE-API — every verb is world-scale, and a session is not

> **CLOSED 2026-09-21 — delivered.** `docs/conformance/actor-scale-writes.md` stands at tier `EXERCISED`
> over `terrain_quest_actions.py`, `terrain_quest_api.py`, `terrain_person_state.py` and
> `terrain_person_api.py`, emitting `quest_actions` and `person_state` with schemas. **Green under the
> canonical invocation**: `PYTHONPATH=Sim python -m unittest discover -s Sim/tests` runs `test_person_state`
> at 23 tests, OK. (Invoking it by dotted path instead breaks on the bare `import test_quest_actions` at
> `test_person_state.py:40`; that is an invocation quirk, not a gap.) Verified by
> [the 2026-09-21 reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

Owner: none. State: open, unowned. Pairs with
[PRODUCT-READ-SURFACE](PRODUCT-READ-SURFACE.md): that card is the eyes, this one is the hands.

## Requested behavior

A channel for the mutations a playing session makes to the people and the promises in a world,
at the scale a session works at. Today the eight mutators move continents, ages, gods and
nations; a party accepting a quest has nowhere to go.

## The gap

The eight world verbs are `generate`, `advance-age`, `advance-time`, `summon` (with `depart`),
`found-settlement`, `corrupt`, `cleanse` and `nomad`. Every one of them moves the world at age
or era scale. The complete set of actor-scale writes the API offers is two optional arrays on
`advance-time`: `leyline_edits`, and `resolutions` of shape `{quest_id, outcome}`.

The hole is already documented, in the generator's own record. From
[time-advance.md](../../docs/conformance/time-advance.md), on the quest lifecycle:

> It also *honours* `taken`, which stops a quest expiring on its offer window, but **no request
> field sets it**: a game that has accepted a quest for its player writes that state into the
> document it persists. The absence of an accept channel is a gap, not a design.

That sentence is this card in miniature. The generator has already conceded that the game
writes into the persisted document by hand. Once a consumer edits a world outside a request
boundary, every invariant the boundary exists to enforce — purity, determinism, id stability
across ages, the join rules — stops being enforceable, and most of what it would be writing
into is thinly checked. Do not requote
[PRODUCT-BLOCK-REGISTRY](PRODUCT-BLOCK-REGISTRY.md)'s "48 blocks, 30 unschema'd": measured
2026-09-21, `len(STATE_KEYS)` is **49** and `world-output.schema.json` declares **56**
top-level properties against **16** required, so the blocks are declared and mostly
unconstrained rather than undeclared.

There is a second consequence that no document states, and a consumer will find it the hard
way. `heroes` is regenerated wholesale at an age boundary, and the quest reaper closes any
quest whose hook disappeared with `closed_reason: 'hook_gone'`. **Measured 2026-09-21** with
all 49 open quests taken and one age advanced: **39 closed `hook_gone`, 10 survived still
`taken`**. The survival is not a guarantee — it is an incidental uid collision, because the
regenerated cast re-mints positional uids (`hero-reeve-hamlet-0`,
`hero-sovereign-<city uid>`) as the same string, so a surviving quest silently re-targets
whoever now holds that uid. That is worse than reaping it. A game built on an accept channel
that does not say this loses most of its players' accepted work at the first age turn and
quietly redirects the rest.

## Scope

**In scope, and what closing this card means:**

- A quest channel: take and abandon, with the operation record and report both.
- A person channel: one published liveness vocabulary, translated at the boundary into whichever
  block-local vocabulary the record uses, with one writer.
- The age-boundary ruling above, stated in the record either way.

**Explicitly out of scope, each a follow-up card rather than a silent omission:** combat
resolution, inventory or economy, settlement population edits, authoring a new quest, party
position and travel. Each of those is a modelling commitment the generator has deliberately not
made — `docs/conformance/nomads.md` records that no band consumes forage, fights or dies, and
that is a design position, not an oversight. This card does not reverse it.

## Proposed mechanism

### `POST /world/quest`

`{api_version, world, actions: [{quest_id, action, day?}]}` with `action` in `take` and
`abandon`. A separate route rather than more arrays on `advance-time`, because taking a quest
happens at an instant and not over a span, and because the operation record should say what
happened rather than record it as a side effect of a clock. It reuses the validation shape of
`terrain_time._apply_resolutions` — same capacity bound, same refusal envelope, same
`unknown quest_id` refusal — rather than writing a second one.

`taken` already exists in the lifecycle and is already honoured; this route is the missing
writer for a state the reader has had all along.

### `POST /world/person`

`{api_version, world, changes: [{uid, status, reason, day}]}`, where `status` is drawn from one
published vocabulary and is translated at the boundary. The seam already exists and is correct:
`terrain_liveness.liveness(record, block)` dispatches on the block a record came from, and
refuses a record carrying `people`, `quest_hooks` or `policy_revision` — because
`hero_generator` and `npc_roster` both write a block-level `status` of `ok`/`failed` and a
person-level `status` of `living`/`legend` under the same key, so matching on the string alone
reads a failed package as a living person. A writer must go through that predicate, not around
it.

This shares one question with [NPC-TOMBSTONES](../backlog/NPC-TOMBSTONES.md) and
[VILLAIN-FALL-UNRECORDED](../done/VILLAIN-FALL-UNRECORDED.md) — what persists when someone stops
existing — and `board/README.md` already requires that the three take the same answer. Do not
answer it here alone.

### Invariants this must not break

- **Purity.** World in, new world out, caller's world untouched, no half-written world on a
  raise. All eight existing mutators hold this and `consumer_orchestrator.py` asserts it.
- **The RNG domain is keyed by simulated time, never by call count.** If any actor-scale write
  consumes randomness it keys on the day and the uid, never on an ordinal or a call counter.
  Preferably it consumes none.
- **Ids that cross an age boundary.** A quest keys on `hook_id` and hooks vanish wholesale at an
  age transition. Under [028](../../docs/decisions/028-an-age-is-five-thousand-years.md) a quest
  is reaped at an age turn under its own distinct reason, whether or not some id happened to be
  minted twice — so this channel must never assume a quest it opened is reachable after one, and
  must not treat a re-minted id as continuity.
- **`history.operations` gains a row per call that changes the world**, and a call that changes
  nothing records nothing, matching the age band's estimate path.

## Dependencies and unresolved decisions

- ~~Needs a ruling: does a taken quest survive an age boundary?~~ **Ruled 2026-09-21: it does
  not, and no durable anchor is wanted.** Recorded at
  [028](../../docs/decisions/028-an-age-is-five-thousand-years.md). An age is five thousand
  years and the people who offered a quest are gone, so the board is reaped and rebuilt from the
  new age's hooks. That makes the ten incidental survivors a **defect rather than a feature to
  preserve**: they live only because the regenerated cast re-mints positional uids as the same
  string, and each is a chimera carrying the old age's prose, the new age's target check and a
  giver from neither. Closing it is scoped under 028, not here.
- ~~Sequence behind [TIME-PERSISTED-WORLD-CANNOT-ADVANCE](TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md).~~
  **This dependency was stated in error and is withdrawn.** That card was resolved on
  2026-09-20: `terrain_history.adopt_world` is the seam every stateless request API takes a
  caller's world through, and it guarantees `timing_ms` on entry, disarming roughly thirty
  unguarded writes across seventeen files at once. Verified 2026-09-21 by generating a CLI
  world, reading it back and advancing it. The card's Resolution section says so; only its head
  reads like a live defect, which is how the error was made. Its open remainder is
  [SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE](../backlog/SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE.md), a
  different key and not a blocker here.
- **[SDET-STATUS-VOCABULARY](../backlog/SDET-STATUS-VOCABULARY.md) and
  [PRODUCT-CONSUMER-VOCABULARY](PRODUCT-CONSUMER-VOCABULARY.md)** own the vocabulary this
  card's person channel publishes. Thirteen properties named `status`, five distinct
  vocabularies, and the only translation between two published contracts is a private
  expression at `npc_roster/__init__.py:190` (verified still there 2026-09-21). **"Promote that
  expression" was the wrong instruction and is withdrawn**: `npc_roster/policy.py` states the
  leaf packages must not import the generator, and `icarus_sim.terrain_history:478` already
  imports `npc_roster`, so calling into the generator from the roster reverses the arrow. The
  shape that works is the one taken: publish the mapping in `terrain_liveness` and bind the
  roster's own copy to it with a test, the same way `test_npc_roster` binds its `posts.json`
  snapshot, plus a test asserting the four leaf packages still import no `icarus_sim`.
- **[VILLAINS-NO-SCHEMA](../done/VILLAINS-NO-SCHEMA.md) / [PRODUCT-BLOCK-REGISTRY](PRODUCT-BLOCK-REGISTRY.md)**
  — the blocks written here need declarations at their own boundary.
- **No native side, and none is owed.** Under
  [decision 027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md), ruled
  2026-09-21, the `Core/` port happens at the end of the project as a full rewrite, no Python
  change owes it anything, and the current native divergence is not a defect and not a hold.
  This card is Python, states so, and writes no C++ speculatively.

## Files and assets in scope

- New: a quest-action module and a person-state module under `Sim/icarus_sim/`, each split
  into a pure part and a request/glue part.
- Edit: `tools/terrain_lab.py` — route registration only.
- New: schemas under `Contracts/schemas/` for both request bodies and both reports.
- New: `tests/` coverage; edit `docs/conformance/time-advance.md` where the quest lifecycle
  gains a writer, per the "widening a record you do not own" rule.
- New: `docs/conformance/` record for the person channel.

## Acceptance and evidence

- A behavioural test lands **before** the behaviour, per `AGENTS.md`.
- Purity: caller's world byte-identical after every call, including every refusal path.
- A taken quest does not expire on its offer window; an abandoned one closes with its reason
  and its day; both appear in `history.operations`.
- The age-boundary behaviour is asserted, whichever way it is ruled — a test that advances an
  age with a taken quest outstanding and pins the outcome.
- A person change through every one of the five vocabularies resolves through
  `terrain_liveness` and not around it, including the block/person `status` collision the
  predicate already refuses.
- Refusals: unknown `quest_id`, unknown `uid`, a `status` outside the vocabulary, over
  capacity, and an `api_version` carrying `retry: false`.
- Determinism: the same actions in the same order against the same world produce byte-identical
  worlds, and no action consumes an RNG stream keyed on call count.

## Adversarial review and limitations

- **This card legitimises writes that are happening anyway.** The value is a boundary and a
  schema, not new capability. If it ships without refusals as good as the existing envelope,
  the consumer keeps hand-editing and nothing is gained.
- **A person channel is where five vocabularies meet.** Publishing a sixth to unify them is the
  failure mode; the card must translate into existing ones and add no new word.
- **The age-boundary answer is the card's real risk.** Shipping an accept channel without
  stating it loses player state silently and correctly, which is the worst combination.
- **Scope creep toward a gameplay engine.** The out-of-scope list above is load-bearing. The
  generator does not model combat, forage, cargo or economy, and several records say so
  deliberately; a slice that starts modelling them here has changed the product.
- Determinism, replay identity, draw and iteration order, byte reproducibility and id stability
  across ages are invariants and bind this work.
- Tier `EXERCISED` at best; no native port, none claimed.

## Sources consulted

`docs/conformance/time-advance.md`, `docs/conformance/nomads.md`,
`docs/conformance/settlement-founding.md`, `docs/conformance/request-failures.md`,
`docs/decisions/026-world-handles-and-the-host-store.md`, `Sim/icarus_sim/terrain_time.py`,
`Sim/icarus_sim/terrain_liveness.py`, `tools/terrain_lab.py`, `board/README.md`.
