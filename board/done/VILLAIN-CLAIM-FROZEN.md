# VILLAIN-CLAIM-FROZEN — a villain's claim is fixed at its first build and never updated again

Owner: villains session. State: **closed 2026-09-21.** The premise reproduced; the open
snapshot-versus-standing question is answered and the rejected alternative recorded. See
"Resolution" at the foot. Found by the bug-hunt session reading `terrain_villains.py`.

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

## Resolution — villains session, 2026-09-21

**Premise re-tested and it reproduces exactly.** `claim_settlements` recomputed the whole
claim every age and appended it only when no claim with that id was already present, and the
id is `claim-{uid}`, one constant per villain. A behavioural test written first:

```
AssertionError: 'village' != 'seat' : a villain at tier 3.0 is well past 1.5 and its claim
still reads 'village'. The stored claim is appended once under a constant id and never
updated, so the promotion can only fire for a villain that crosses 1.5 in the single age it
first builds.
```

and, for the second half, `KeyError: 'refreshed_age'`. Both now pass.

### The open question, decided — and the alternative that was rejected

**Is a claim a snapshot or a standing fact? Decided: a snapshot with a standing half**, and
the split is now part of the published contract.

| Frozen at the age it was taken | Tracks the present |
|---|---|
| `age`, `direction`, `node`, `factions`, `drawn_from` | `kind`, `refreshed_age`, `holder_status`, `holder_fell_age`, `influence` |

**Rejected: treat the whole claim as a standing fact and redraw `factions` and `drawn_from`
every age.** The docstring's "the claim is what an orchestrator reads until then" argues for
it, and the card's own body leans that way. It was rejected because it makes `age` mean
nothing, it rewrites history silently on every age, and neither field has a consumer today —
so the cost is certain and the benefit is hypothetical. A `drawn_from` uid that names a ruin
by now is this record being honest about a claim taken from the living, which is the reading
that survives someone actually joining it.

**This is reversible in one function.** If the owner rules the other way, `claim_settlements`
refreshes `factions` and `drawn_from` from `near[:MIXED_FACTIONS]` alongside `kind`; nothing
else changes, because the id is stable either way.

### What changed

- `claim_kind(villain)` and `SEAT_TIER` — the band, named once instead of being an inline
  expression that only one of the two call paths ever evaluated to a stored value.
- `claim_settlements` finds the held claim by id and refreshes `kind` and `refreshed_age`
  rather than discarding the freshly computed record. `drawn_from` and `factions` are left
  alone, deliberately, per the ruling above.
- `refreshed_age` is written at creation as well as at refresh, so absence is never a state
  a reader has to interpret.

`kind` moves in **both** directions, which the card did not ask for and the fix gives for
free: a villain whose region quietens demotes its claim from `seat` back to `village`. That
is visible in the multi-age run below and is the correct reading of a band on a live tier.

### Evidence

- `Sim/tests/test_super_villains.ClaimTests` — 2 new tests, synthetic, 0.001 s.
- The multi-age run recorded in `SDET-VILLAIN-FALL-UNREACHABLE` shows it in a real world:
  `claim-villain-2-100` reads `village` at age 2, promotes to `seat` at age 4 at tier 1.526,
  and demotes to `village` at age 6 at tier 1.236, with `refreshed_age` tracking each age.
  Under the old code it would have read `village` at every one of them.
- `Contracts/schemas/villains.schema.json` `$defs/claim` describes the split, with `kind`
  enumerated and the frozen half marked as such.
- `docs/super-villains.md` gains "What a claim records, and which half of it moves",
  including the rejected alternative.

### Not done, and why

**`drawn_from` is untouched.** The card is explicit that it must not move until the
snapshot-versus-standing question is answered, and the answer above is that it is part of the
snapshot. So there is nothing to do to it rather than a decision deferred.

### Ablation — the tests were checked against a deleted implementation

"I wrote it failing first" is not sufficient on its own, so each test was re-run against a
copy of the tree with the code it covers removed. Both went red, and each went red for only
its own mechanism:

| Ablation | Test that went red |
|---|---|
| `held['kind'] = claim['kind']` deleted | `test_a_claim_promotes_to_a_seat_when_its_villain_grows_into_one` |
| `held['refreshed_age'] = age` deleted | `test_what_a_claim_drew_from_is_the_snapshot_and_does_not_move` |
| **the rejected alternative implemented** — `drawn_from` and `factions` redrawn each age | `test_what_a_claim_drew_from_is_the_snapshot_and_does_not_move` |

The third is the one worth having. A frozen-field test is green from birth and can never be
watched to flip, so deleting code proves nothing about it — only building the alternative
does. It goes red, which means the test discriminates between the two readings of the
snapshot question rather than merely describing the one that shipped.
