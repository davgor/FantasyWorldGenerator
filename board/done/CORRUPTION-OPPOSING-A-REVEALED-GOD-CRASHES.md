# CORRUPTION-OPPOSING-A-REVEALED-GOD-CRASHES - `cleanse_request({"god_id": ...})` raises StopIteration for the only god corruption ever makes walk

## Observed behavior

`cleanse_request` is the documented way to oppose a walking god. On a corrupted world it
raises a bare `StopIteration` out of a validated request API:

```
seed 42 / size 17 / villain_rise 1.0, corruption_request at encounters 40
  visitations: []
  god status: walking
cleanse_request({'api_version':1,'world':<world>,'target':{'god_id':'god_shape_beneath'},'power':1.0})
  File terrain_corruption.py, line 416, in cleanse_request
  File terrain_visitation.py, line 343, in depart_god
  StopIteration
  EXC TYPE: StopIteration | args: ()
```

The same exception is reachable in two lines with no world at all, because the precondition
is purely structural:

```
depart_god({'religion': {'gods': [{'id': 'g', 'status': 'walking'}], 'visitations': []}}, None, 'g', 1, rebuild=False)
  EXC TYPE: StopIteration | args: ()
```

## Why it happens

There are two ways a god comes to be `walking`, and only one of them writes a visitation
record.

- `validate_cleanse` at `terrain_corruption.py:382-387` accepts any god whose `status` is
  `walking`. That is its whole check.
- `_reveal` at `terrain_corruption.py:302-308` sets `status = 'walking'` on the hidden god
  as the last act of a corruption, and never writes a visitation record - corruption's
  footprint is the ley cluster, not a visitation.
- `depart_god` at `terrain_visitation.py:343` then evaluates
  `next(v for v in reversed(religion['visitations']) if v['god_id'] == god_id and v['departed_age'] is None)`
  with no default, so the generator's exhaustion escapes as `StopIteration`.

So the guard checks a status that corruption sets, and the code behind it requires a record
that corruption never creates. The only god corruption ever makes walk is exactly the god
this call cannot handle.

## Why it matters

This is the documented happy path, not a corner. `docs/corruption.md:70` says "Opposing a
walking god is the same operation under another name: an avatar is a ley cluster and not a
creature, so driving one off is cleansing its nodes, and the effect is an early
`depart_god`." `board/in-progress/SUPER-VILLAINS.md:148` repeats it: "Opposing a walking god
routes to an early `depart_god`."

A bare `StopIteration` is also the wrong failure shape for a module whose entire contract is
validate-then-act. It carries no message, names no field, and inside a generator expression
in a caller it would be swallowed as a normal stop instead of surfacing at all.

## The same hole at the other door

`visitation_request({'depart': True})` reaches the identical unguarded `next()` through the
identical status-only guard: `validate_visitation` at `terrain_visitation.py:91-93` checks
only `if god['status'] != 'walking'`. The stub reproduction above is that path.

## Current state - CLOSED 2026-09-21

**Re-tested first.** The crash does not reproduce; the structural two-liner this card gives
as its minimal case now returns the refusal it should:

```
depart_god({'religion': {'gods': [{'id': 'g', 'status': 'walking'}], 'visitations': []}}, None, 'g', 1, rebuild=False)

Traceback (most recent call last):
  File "<string>", line 5, in <module>
  File "Sim\icarus_sim\terrain_visitation.py", line 385, in depart_god
    raise ValueError('No undeparted visitation for ' + str(god_id) + '; that god does not '
ValueError: No undeparted visitation for g; that god does not walk by visitation
EXC TYPE: ValueError | args: ('No undeparted visitation for g; that god does not walk by visitation',)
```

`validate_cleanse` in `terrain_corruption` and `validate_visitation` in
`terrain_visitation` both require an undeparted visitation record before routing to
`depart_god`, and `depart_god` defaults its `next()` and raises a `ValueError` naming the
god rather than a bare `StopIteration`. Line numbers are deliberately not repeated here:
this card's original ones are already three edits stale, and the functions are the stable
address. Both doors are covered by
`Sim/tests/test_corruption.CleanseTests.test_opposing_a_revealed_god_by_god_id_refuses_and_never_raises_stopiteration`
and `test_departing_a_revealed_god_is_refused_at_the_visitation_door_too`, each of which
fails the test explicitly if a `StopIteration` escapes, and by
`test_the_corruption_route_is_the_one_that_works`, which proves the route the refusal
names actually finishes.

### The design question, ruled

The open half was whether refusing is the right answer, or whether opposing a
corruption-revealed god should **drain that god's live corruption records**.

**Ruled: refusing stands.** This was the conservative option and it was taken under the
sweep's pick-implement-flag instruction rather than by the SUPER-VILLAINS owner, so it is
reversible and stated here for that purpose.

Reasons, in the order they weighed:

1. **The alternative moves worlds and the refusal does not.** Draining is a ley write; it
   changes key-point intensity and therefore the field, so it is seed-visible. A ruling
   that changes generated output is not one to take on someone else's behalf at the end of
   a sweep.
2. **It is under-specified in a way a card cannot close.** `_drain(result, cfg, index,
   power, age)` is index-based, handles one record and runs a full `rebuild_tail` per
   invocation, so looping it over a god's records is N world rebuilds — at the measured
   cost of a rebuild that is minutes, not seconds — with no defined aggregate report
   shape, while `cleanse_request` writes exactly one `report` into `history.operations`
   and one `result['cleanse']`. There is no cleanse schema in `Contracts/` to constrain
   the aggregate, and `VILLAINS-NO-SCHEMA` is the card for that.
3. **Nothing is lost by refusing.** The `{"corruption": <index>}` route does the same
   drain on the thing a revealed god actually is here, and it is tested end to end. The
   refusal names that route by name in its message, so a caller is redirected rather than
   stopped.

**What the rejected option would have bought**, so the owner can weigh it: it would make
`docs/corruption.md` and `board/in-progress/SUPER-VILLAINS.md:148` true as originally
written, instead of the correction `docs/corruption.md` now carries and the correction
`SUPER-VILLAINS.md` still needs.

### One inbound claim still needs repointing, and it is not this card's to edit

`board/in-progress/SUPER-VILLAINS.md:148` still says "Opposing a walking god routes to an
early `depart_god`." That is now false for the only god corruption ever makes walk. It is
another session's in-progress card and was deliberately left alone; handed to the
orchestrator.

## Not owned

Found 2026-09-20 while refuting
[MAGIC-CORRUPTION-NEVER-REACHES-GROUND](../done/MAGIC-CORRUPTION-NEVER-REACHES-GROUND.md).
That card pointed at this area and was wrong about what was in it; this is what was actually
there. Pre-existing, reproduced end to end, and unreachable through any in-tree caller today
because nothing calls `corruption_request`.
