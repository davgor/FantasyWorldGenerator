# VILLAIN-CLAIM-FROZEN — a villain's claim is fixed at its first build and never updated again

Owner: none. State: open, unowned. Found by the bug-hunt session reading `terrain_villains.py`.

## The defect

`terrain_villains.build()` runs every age for every seated villain, and calls
`claim_settlements()`, which recomputes the claim from the world as it stands — the three nearest
cities, their peoples, and whether the villain's tier has passed `SUPER_TIER × 1.5`. Then:

```python
claim = {'id': f"claim-{villain['uid']}", ..., 'kind': 'seat' if villain['tier'] >= SUPER_TIER * 1.5 else 'village',
         'factions': sorted(set(mix)), 'drawn_from': [uid for _, uid, _ in near[:MIXED_FACTIONS]], ...}
villain.setdefault('claims', [])
if not any(c['id'] == claim['id'] for c in villain['claims']):
    villain['claims'].append(claim)
```

The id is `claim-{uid}` — one constant per villain. From the second age onward the guard is always
true, the freshly computed claim is dropped on the floor, and the stored one never changes again.

Three things go stale as a result:

- **`kind`.** A villain seated at tier 1.0 is recorded as a `village` and stays one forever. The
  tier-1.5 promotion to `seat` can only ever fire for a villain that crosses the line *in the same
  age it first builds* — that is, one that rises past 1.5 in a single step. A villain that grows
  there over three ages, which is the normal case and the whole point of the ramp, never promotes.
  The threshold is effectively unreachable by the path the model is designed around.
- **`drawn_from`.** Three city uids, fixed at first build. Those cities can be ruins several ages
  later. The claim still names them as the peoples it drew from.
- **`factions`.** Same, one step removed.

The `well` field is the exception that proves it: `sink_well` runs once by its own guard, so the
claim's copy of the well id happens to stay correct. That is why the staleness has gone unnoticed
— the one field anyone would check by eye is the one that is right.

## Consumers

Both live consumers read claims and neither can tell a fresh one from a five-age-old one:

- `Sim/key_locations/core/world.py:92-103` — `villain_holdings` reads claim positions into the
  `villain_distance` field, which gates `near_villain` in succession.
- `Sim/icarus_sim/terrain_nomads.py:191-195,276-278` — the cultist gate reads `claim['id']` and the
  holder's `school` and `tier`.

Neither reads `kind` or `drawn_from` today, so nothing is currently *wrong* downstream. The
defect is that the block asserts a present-tense fact about the world that stopped being true, and
the first consumer to join `drawn_from` against `settlements` will silently join against the dead.

## Proposed mechanism

Update in place rather than append-once: find the existing claim by id and replace its mutable
fields, keeping `age` as the age it was first taken and adding the age it was last refreshed. The
id stays stable, so nothing that keys on it moves.

Deliberately not proposed: making the id age-scoped so a villain accumulates one claim per age.
That would grow the block linearly in ages and change what `claims` means to two consumers.

## Dependencies and unresolved decisions

- Open, and the reason this is a card rather than a patch: **is a claim a snapshot or a standing
  fact?** If the stored claim is meant to record "what this villain took, when it took it", then
  freezing `drawn_from` is correct and only `kind` is wrong. If it is meant to describe the holding
  as it stands now, all three fields are wrong. The docstring argues for the second reading — "The
  claim is what an orchestrator reads until then" — but nobody recorded a decision.
- `docs/super-villains.md` describes claims without saying which, so fixing this may be a
  documentation change as much as a code one.

## Sources consulted

`Sim/icarus_sim/terrain_villains.py:318-360`, `docs/super-villains.md`,
`Sim/key_locations/core/world.py:92-103`, `Sim/icarus_sim/terrain_nomads.py:191-195,276-278`.

## Files and assets in scope

`Sim/icarus_sim/terrain_villains.py`, `Sim/tests/test_super_villains.py`, possibly
`docs/super-villains.md`.

## Acceptance and evidence

A villain that rises from below `SUPER_TIER × 1.5` to above it across two age advances carries a
claim of kind `seat`, and its `drawn_from` names cities that are alive at the age the claim
reports. Needs a multi-age run at `villain_rise` above zero — **a run request for the
coordinator, not run here.**

## Adversarial review and limitations

The `kind` half is a firm defect under either reading of the open question: a threshold that can
only be crossed by a single-step rise is not the threshold the ramp model describes, and no
reading of "snapshot" makes a tier band correct to freeze. The `drawn_from` half genuinely depends
on the unresolved decision above and should not be changed until someone answers it.

Not verified by running: this is read from the source. The claim that the second-age recomputation
is discarded rests on `claim['id']` being constant per villain, which it is — `villain['uid']` is
assigned once at seating and never reassigned.

## Handoff

Third finding from the same read-only pass over `terrain_villains.py` and `terrain_corruption.py`.
See `VILLAIN-FALL-UNRECORDED.md` and `VILLAINS-NO-SCHEMA.md`; a schema for the block would have
made the `kind` values assertable.
