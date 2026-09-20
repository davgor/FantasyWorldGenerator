# SDET-LEY-QUEUE-NO-APPLIER — `pending_ley_edits` is written, carried forever, and never read

Owner: none. State: **defect pinned; the producer is now tested, the consumer does not exist.**
Evidence: `Sim/tests/test_pending_ley_edits_contract.py` — 9 tests, 8 pass, 1 fails, 0.016 s,
no world generated.

This answers the "Next action" of `NOMAD-CORRUPTION-CONTRACT.md` — *"confirm against
`terrain_corruption` whether it implements this contract"*. It does not. It does not mention
the queue at all.

## The defect

A cult of a hidden school cannot write its own leyline edit, because `advance_age_request`
refuses any school outside `KNOWN_SCHOOLS`. So it queues the intent into a top-level
`pending_ley_edits` block for the corruption pass to drain. Every mention of that key in the
repository:

- `Sim/icarus_sim/terrain_nomad_effects.py:54` — reads the existing queue.
- `Sim/icarus_sim/terrain_nomad_effects.py:86` — writes it back, sorted.
- `Sim/icarus_sim/terrain_history.py:398` — one mention, inside `STATE_KEYS`.
- `Contracts/schemas/nomads.schema.json` — a description of the field.
- `tools/terrain_lab.html` — `historyStateKeys`.
- three documents, and one test that inspects its contents.

**No consumer.** And the shape makes it worse than unread. The producer reads the existing
list and appends rather than replacing it, and the block rides in `STATE_KEYS`, so it is
carried across every age advance. The first world that unlocks a hidden school starts an
accumulator that nothing drains and no age boundary clears. `nomads` is replaced wholesale
each age precisely to avoid this, which makes the asymmetry look deliberate and is not.

## Why it was never caught, and what changed

`tests/test_world_schema_conformance.py:247` loops over `pending_ley_edits` asserting each
entry names a hidden school with a bounded intensity and a `requested_by`. The four hidden
schools are locked at zero occurrence until a player unlocks one, so the queue is absent on
every world ever generated: **that loop body has never executed once.** The only branch that
has ever run is the `assertNotIn` below it.

`NOMAD-CORRUPTION-CONTRACT.md` named the way out — hand-construct the world rather than wait
for one — and the eight passing tests take it. They run the producer's contract for the
first time since it was written: the hidden-school queue-instead-of-write path, every field
the contract names, hidden-schools-only, the intensity bound, the endpoint being a node id
and never an index (the bug `depart_god` had), the known-school direct-write path, and the
producer's half of the order-independence guarantee. **All eight hold. The producer is
sound.** It is the other end of the pipe that was never built.

## Proposed mechanism

**Not proposed.** The card this follows already framed the choice — add the applier to
`terrain_corruption`, or move the drain into the nomad pass — and says the important part:
decide, rather than leaving a queue that nothing drains. What this card adds is that the
decision is now urgent in a way it was not, because the queue is an accumulator rather than
a buffer.

## Dependencies and unresolved decisions

- The contract was agreed with a session that has since closed and can never confirm it. It
  survives in the `terrain_nomad_effects` module docstring and in
  `NOMAD-CORRUPTION-CONTRACT.md`; those are the only records.
- Ordering within a rebuild — villain and corruption edits first, then nomads — is part of
  the agreed contract and is untested, because there is nothing to order against.
- Whether the queue should be drained or merely bounded is open. Nothing decides today what
  happens to an entry whose node was removed between write and apply.

## Sources consulted

- `Sim/icarus_sim/terrain_nomad_effects.py:1-25` — the contract, in the module docstring.
- `Sim/icarus_sim/terrain_nomad_effects.py:46-87` — `apply_cultist_leylines`, the producer.
- `Sim/icarus_sim/terrain_history.py:398` — `STATE_KEYS`, which carries the block.
- `tests/test_world_schema_conformance.py:247` — the loop that has never run.
- `board/backlog/NOMAD-CORRUPTION-CONTRACT.md` — the contract and its Next action.

## Files and assets in scope

`Sim/icarus_sim/terrain_corruption.py` (the applier, if it goes there),
`Sim/icarus_sim/terrain_nomad_effects.py`, `Contracts/schemas/nomads.schema.json`,
`docs/nomads.md`, `docs/conformance/nomads.md`.

## Acceptance and evidence

`ApplierContractTests.test_something_in_the_simulation_drains_the_queue` passes — a module
outside the producer and `STATE_KEYS` reads the key. Its docstring carries the five criteria
that cannot be written against a function that does not exist, and replacing it with the real
round trip is the point:

1. a world carrying `pending_ley_edits` comes back with the queue emptied, not ignored;
2. each applied entry has moved its node's intensity in `magic.networks[school]`;
3. entries resolve by node id, never by index;
4. an entry naming a known school is rejected rather than applied;
5. two worlds queuing the same entries in opposite order come back identical.

`test_the_carrier_only_carries` guards the allowlist this rests on: it asserts
`terrain_history`'s single mention is inside `STATE_KEYS`, and breaks if that stops being true.

## Documentation impact

`docs/conformance/nomads.md:186` already records that the round trip cannot be tested end to
end. That sentence is now half wrong in the useful direction — the producer half **is**
tested — and should say so, and say that no applier exists.

A **separate** false claim sits in the same record and is not this card's to fix. Under
"Determinism is an invariant", `docs/conformance/nomads.md:90-94` states that seeds derive
"with per-entity domains `nomad-class-<uid>`, `nomad-camp-<uid>` and `nomad-route-<uid>`" and
concludes that "a feature drawing only from new domains cannot perturb an existing stream".
**None of those three strings exists anywhere in the repository.** The pass has one
sequential stream, `child_seed(cfg.seed, 'nomads-v1', nomad_variation)`, so the stated
guarantee is not merely undocumented but inverted: any added draw shifts every decision after
it. Verified independently by this session and by the code red-team session, which owns the
record's truth and is carrying it.

## Adversarial review and limitations

- The search was for the literal string `pending_ley_edits` across `Sim/`, `Core/`, `tools/`,
  `Contracts/`, `docs/` and `tests/`. An applier that reached the block by a computed key
  would not be found. Nothing in this codebase does that, but the claim is "no module names
  it", which is what the test asserts.
- **Not established:** that a hidden-school cultist can be produced by any generated world.
  It cannot today, by design. The fixture is hand-built and says so.
- The first version of the failing test **passed**, because `path.parts[0]` on an absolute
  Windows path is the drive letter, so the exclusion meant to skip test files never fired and
  the scan matched the test module itself. Caught only because a test designed to be red came
  out green. Noted here because the same trap is available to anyone re-running this search.

## Handoff

Found by the red-team SDET session taking the coordinator's second assignment, which was to
hand-construct a fixture world with a hidden-school cultist and run the applier against it.
The fixture was built; there was nothing to run it against.
