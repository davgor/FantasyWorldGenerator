# SDET-LEY-QUEUE-NO-APPLIER — RESOLVED: the queue is removed, not drained

Owner: none. State: **resolved 2026-09-20 by removing the mechanism.** The card asked for a
decision rather than a mechanism, and this is the decision plus the evidence that forced it.

Evidence at filing: `Sim/tests/test_pending_ley_edits_contract.py` — 9 tests, 8 pass, 1 fails,
0.019 s, no world generated. Reproduced independently before acting. That file is replaced by
`Sim/tests/test_cult_leyline_writes.py` — 8 tests, OK, 0.001 s.

## The decision

**The queue is removed and a cult of a hidden school now writes its node directly, exactly
as a known-school cult always did.** No applier was built, and none should be.

## Why — the founding premise was tested and is false

The queue existed because of one sentence, carried in the `terrain_nomad_effects` module
docstring and in `NOMAD-CORRUPTION-CONTRACT.md`: *`advance_age_request` rejects any leyline
edit whose school is outside `KNOWN_SCHOOLS`, so a blood cult writing its own node would be
refused at the next age boundary.*

That is not what the gate does. It sits inside `advance_age_request`'s loop over
`body['leyline_edits']` — the edits a **caller supplies with the request**. It never inspects
the world's networks. `validate_age_world` was run against a real world with a hidden-school
node injected at intensity 3.0, and accepted it; the node was then intensified to 3.54 and it
accepted that too. Its only school-level assertion is that all twelve networks are present,
which is the opposite of a ban.

And this pass never passed through that validator in the first place. It writes via
`edit_network` directly, from `apply_nomad_effects`, at three call sites — generation stage
16, the age-advance tail, and every `nomad_request`. The known-school half had been doing
exactly the thing the hidden half was told it could not do, in the same function, since the
day it was written.

So the queue was working around a gate that did not apply to it, for a consumer that was
never built, in a block that rode in `STATE_KEYS` and was appended to rather than replaced.

## Two defects die with the mechanism

Both were found by running the producer, and both are now pinned as regressions in
`Sim/tests/test_cult_leyline_writes.py` so they cannot come back with a future applier.

1. **The unit divergence.** Same band, three shrines, node at intensity 3.0. The known-school
   path wrote **3.54** — `current['intensity'] * 1.18`, absolute, shrine count ignored. The
   hidden-school path queued **0.54** — `DEVOTION_GAIN * shrines`, a gain. `edit_network`
   SETS intensity rather than adding to it, so an applier reading the queue the obvious way
   would have cut that node by 82% in the act of deepening it. Nothing in the repository
   decided which unit was meant, and the author is gone. After the removal both schools land
   3.54 and the test asserts they are equal.

2. **Entries naming no node.** A cultist band raised on a villain claim or a shrine carries no
   `ley_node_id`. The known-school path skipped those on `if not net or not basis_node:
   continue`. The hidden path had no such check and queued `{"id": null}`. The `str(e['id'])`
   coercion in the old sort key is the tell that this was known about. That guard now covers
   both halves, so the null entries stop being produced for free.

## The invariant that actually holds, and now has a test behind it

`docs/hidden-schools.md` said "the corruption API is the only way a node enters a hidden
network". The true, narrower statement is that **the corruption API is the only way a node is
CREATED in a hidden network**; deepening one that already exists is a separate act. The code
enforced the split all along — `current = next(...)` followed by `if current is None:
continue` — but nothing tested it and the doc stated it too broadly. Both are fixed.

## Content effect, which is real and is not zero

With the queue gone, a hidden-school cult's node is re-lifted x1.18 on **every**
`nomad_request` and every age advance, because `apply_nomad_effects` runs at all three sites.
A corrupted ring node seated at `RING_INTENSITY` 2.5 reaches the 4.0 ceiling in three passes.

That is parity with the known-school path, which has always ratcheted the same way, not a new
defect — but it is a behaviour change and it belongs on the record. The ceiling holds, and
that is tested.

## Blast radius — conditional, and the condition is landing now

**This was written when `villain_rise` defaulted to 0.0**, so a default world had no villain,
so corruption could not act, so no hidden node existed, so no hidden-school cult could form,
so the producer's hidden branch had never executed in any generated world. Under those
conditions the removal changed no output at all.

**That sentence expires with user ruling 0.3**, which turns super villains on by default and is
landing in the same wave. Once corruption runs in the default pipeline, hidden nodes exist,
`_gate_cultists` can take a hidden school from the nearest node or from
`claim['villain']['school']`, and this path goes live for seed 42. Which is precisely why the
removal lands **before** 0.3 rather than after: otherwise every shipped world starts an
accumulator that no age boundary clears.

No native port. `Core/` contains no nomads and no corruption; its only hit for the word is the
infernal ruin-reason string. `validate_repo`'s artifacts stage compares two fresh generations
against each other rather than against anything checked in, so a seed change cannot fail it as
long as generation stays deterministic, and worlds are disposable under ruling 0.1.

## What the acceptance criteria become

The card's five criteria are **retired with the mechanism, not unmet**:

1. a world carrying `pending_ley_edits` comes back with the queue emptied — no world carries
   one; `tests/test_world_schema_conformance.py` now asserts absence unconditionally, where it
   used to assert it only on a branch;
2. each applied entry has moved its node's intensity — the write is immediate, and the
   intensity it lands is asserted equal to the known-school one;
3. entries resolve by node id, never by index — there are no entries; the write resolves by id;
4. an entry naming a known school is rejected — there is one path for both, which is the
   point;
5. two worlds queuing in opposite order come back identical — order independence survives, via
   `sorted(bands, key=lambda b: b['uid'])`, and is still tested.

## What was left alone

- `tools/terrain_lab.html` still names `pending_ley_edits` in `historyStateKeys`. It is
  provenance-pinned, the list is a display allowlist, a name for a key no world emits is inert,
  and the one test that couples the two is a **subset** assertion, so it stays green. This is
  the same judgement `SUPER-VILLAINS.md:96` recorded for two other stale lists in that file.
- `NOMAD-CORRUPTION-CONTRACT.md` is not resolved here only because it was outside this
  session's ownership. Its "Next action" — confirm whether `terrain_corruption` implements the
  contract — is answered: it does not, and it should not, because the contract rested on a
  premise that is false. It should move to done with this card.
- The separate false seed-domain claim in `docs/conformance/nomads.md` under "Determinism is an
  invariant" is untouched and still belongs to the code red-team session.

## Adversarial review and limitations

- **Not established:** that a hidden-school cultist band forms in a generated world. The chain
  is read, not run: a corrupted villain, then a claim or ley node in a hidden network, then
  `_gate_cultists`. Running it costs a corruption plus an age advance. If it turns out no such
  band can form, the queue was dead code rather than a live accumulator, which strengthens the
  removal rather than weakening it.
- The removal is justified by the gate not applying, which was established by running
  `validate_age_world` twice against a mutated world. If a future change makes that validator
  inspect the world's networks by school, this decision must be revisited — and the test that
  would catch it is the create-vs-deepen one, not a repeat of this argument.

## Handoff

Filed by the red-team SDET session, which built a fixture world with a hidden-school cultist
and found nothing to run it against. Resolved by the session that went looking for the applier
and found the reason there was never a need for one.
