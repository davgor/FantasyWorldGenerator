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

## Current state - partially addressed

The crash is closed, not the design question. `validate_cleanse` and `validate_visitation`
now require an undeparted visitation record before routing to `depart_god`, and `depart_god`
raises a `ValueError` naming the god instead of a bare `StopIteration`. Opposing a
corruption-revealed god now refuses with a message pointing at the `{"corruption": <index>}`
route, which works today.

What is still open is whether refusing is the right answer. The alternative is that opposing
a corruption-revealed god should drain that god's live corruption records, which would make
`docs/corruption.md:70` and `SUPER-VILLAINS.md:148` true as written rather than needing the
correction they now carry. That is a design decision, not a bug fix, and it is
under-specified: `_drain(result, cfg, index, power, age)` is index-based, handles one record,
and runs a full `rebuild_tail` per invocation, so looping it over a god's records is N world
rebuilds with no defined aggregate report shape, while `cleanse_request` writes exactly one
`report` into `history.operations` and one `result['cleanse']`. There is no cleanse schema in
`Contracts/` to constrain it.

**Needs a ruling, or the SUPER-VILLAINS owner's call, since S8 is their slice.**

## Not owned

Found 2026-09-20 while refuting
[MAGIC-CORRUPTION-NEVER-REACHES-GROUND](../done/MAGIC-CORRUPTION-NEVER-REACHES-GROUND.md).
That card pointed at this area and was wrong about what was in it; this is what was actually
there. Pre-existing, reproduced end to end, and unreachable through any in-tree caller today
because nothing calls `corruption_request`.
