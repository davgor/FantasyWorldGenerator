# SDET-CEILING-SENTINELS — a rejection test whose sentinel is "one more than the limit" becomes a performance test when the limit moves

Owner: none. State: **pattern identified; all three known instances already repaired in
`4713f9a`, and the repair reproduces the pattern.** No test written — see Acceptance.

The three instances are recorded here with their pre-`4713f9a` values because the commit has
erased them from the working tree, and the next person to raise a ceiling will otherwise
rediscover this the same way.

## The pattern

A test that checks a bound is enforced needs an input outside the bound. The obvious
sentinel is the smallest such input — one more than the current limit. That is correct on
the day it is written and becomes wrong, silently, the day the limit moves. Nothing errors.
The input is now legal, so instead of being rejected it is **executed**, and a rejection test
becomes a performance test.

There is no signal except a suite that got slower, which is the one symptom nobody
investigates.

## The three instances, at `4713f9a^`

Raising the grid ceiling from 257 to 1025 tripped all three at once.

| where | sentinel | what it became |
|---|---|---|
| `Fixtures/unreal-frame-v1.json:21` | `{"overrides": {"size": 258}}` | 258 is legal at 1025, so the one-above-ceiling rejection case stopped testing rejection and `--stage repo-tests` stopped terminating |
| `Sim/tests/test_terrain_patch.py:61` | `{'config': {'shape': 'globe', 'size': 1025}, 'patch': {}}` | the "obviously too large" case generated a real 1025 world; that file ran 0.108 s for six tests at `233182e` |
| `tests/test_native_genesis.py` | `assertEqual(registry(3)['size']['max'], 257)` and `assertIn('max_grid=257', genesis)` | both sides pinned to a literal, so the ceiling could not move without editing the test |

The first two are the pattern proper. The third is a related but distinct defect, below.

## The repair reproduces it

`4713f9a` moved the first two sentinels from 258 and 1025 to **1026** — which is one above
the new ceiling. The values are correct today and the fragility is identical: the next
ceiling move turns both back into legal work, silently, exactly as this one did.

That is not a criticism of the fix, which was the right immediate action. It is the reason
this card exists: fixing the instances does not fix the pattern, and the pattern has now
fired once and is armed again.

## Proposed mechanism

**Derive the sentinel from the declared bound instead of restating it.** The bound is already
published — `terrain_world.registry(3)['size']['max']` — so a rejection case can be
`max + 1` computed at test time, which is out of range by construction and can never become
legal work. For fixture data that cannot compute, the test that loads the fixture can assert
each size in an `invalid_*` list is genuinely outside the current bounds before using it, so
a ceiling move fails loudly and immediately rather than quietly generating a world.

Cheap, and it fails at the right moment: the instant the ceiling moves, not an hour later
when someone notices the suite is slow.

## The third instance is a different defect: a substring standing in for an identity check

`assertIn('max_grid=257', genesis)` is a substring test. **`'max_grid=257'` is a substring of
`max_grid=2570`**, so a native ceiling of 2570 against a Python ceiling of 257 passes both
of the old assertions and the divergence survives. Verified directly.

`4713f9a` replaced it with a value comparison, which is the correct fix. But the comment it
left behind states the wrong reason — that the old form let "either ceiling move alone and
this test still passed", which is not true, since either side moving alone fails one of the
two asserts. The real flaw is the substring match, and it is worse than the one recorded.
**A comment stating a rationale the code does not have is the thing AGENTS.md warns about**,
and it is now the only written account of why that test changed.

This is the same family as `path.endswith('status')` swallowing `route_status` in the
`status` vocabulary survey: a near-miss match answering a question that was not asked.

## Dependencies and unresolved decisions

- Whether fixture data should carry derived sentinels at all, or whether the loader should
  assert them, is a design choice this card does not make. The loader form is cheaper and
  keeps the fixture readable.
- `provenance/extraction-manifest.json` gates edits to `Sim/tests/test_terrain_patch.py`: it
  was recorded `status: "exact"`, which requires `destination_sha256 == source_sha256`, so
  editing it needs the status moved to `"modified"` with a note as well as a revision row.
  Anyone fixing that instance pays that cost.

## Sources consulted

- `Fixtures/unreal-frame-v1.json:21` — the current 1026 case.
- `Sim/tests/test_terrain_patch.py:58-61` — the current sentinel list.
- `tests/test_native_genesis.py:83-92` — the value comparison that replaced the substring.
- `git show 4713f9a^` for all three prior values.

## Files and assets in scope

`Fixtures/unreal-frame-v1.json`, `Sim/tests/test_terrain_patch.py`, `tests/test_native_genesis.py`,
`provenance/extraction-manifest.json`.

## Acceptance and evidence

No failing test accompanies this card, deliberately. All three instances are already green
and a test asserting they are green would pin nothing. What is worth building is the guard:

1. every size in an `invalid_*` fixture list is outside `registry(3)['size']` at load time;
2. no rejection sentinel in a test is a literal equal to a published bound plus one.

(1) is straightforward and would have failed the moment `4713f9a` landed, naming the fixture.
(2) is harder to assert mechanically and may be better served by the convention in Proposed
mechanism than by a check.

## Documentation impact

The comment at `tests/test_native_genesis.py:88-90` records a rationale that is not the
actual defect. Correct it to name the substring match, or delete it — a wrong reason in the
tree is worse than no reason, because the next reader will trust it.

## Adversarial review and limitations

- **Not established:** that these are the only three instances. I found them because a
  ceiling moved and surfaced them; a survey for other "limit plus one" literals across the
  suite has not been done, and the pattern is invisible until the relevant limit changes.
- **Not established:** the 48-second figure for the patch test, which is reported rather than
  measured by me. The pre-`4713f9a` sentinel value of 1025 is verified from the commit; the
  cost of running it is not mine.
- The substring claim is verified concretely: `'max_grid=257' in 'max_grid=2570'` is `True`.
- Timing note: every instance here was repaired within minutes of being reported, while this
  card was being written. The card describes the pattern, not an outstanding breakage, and
  should not be read as claiming the suite is currently red.

## Handoff

Found by the red-team SDET session. The coordinator supplied the three instances and the
framing that the pattern matters more than the breakages; the verification against
`4713f9a^`, the observation that the repair re-arms the trap at 1026, and the substring
analysis of the third instance are this card's.
