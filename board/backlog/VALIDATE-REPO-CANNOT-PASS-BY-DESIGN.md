# VALIDATE-REPO-CANNOT-PASS-BY-DESIGN — the closeout command AGENTS.md mandates has never been able to succeed

Filed 2026-09-21 from the closeout of the backlog sweep.

## The contradiction

`AGENTS.md` says: *"Run `python tools/validate_repo.py` before closeout."*
`docs/agent-workflow.md` says the same, and treats a passing validator as the closeout gate.

**It cannot pass.** The repository deliberately carries red tests as evidence, and
`validate_repo.py` has no concept of an expected failure — `run()` raises
`subprocess.CalledProcessError` on any non-zero exit, and a `unittest` suite exits non-zero if
anything at all fails.

Two sets of deliberate pins, both **tracked at HEAD and unmodified**, so neither was introduced by
this sweep:

| file | failures | what they pin |
|---|---|---|
| `tests/test_status_vocabulary.py` | 3 | SDET-STATUS-VOCABULARY — three blocks use three words for the same end state. This *is* the finding. |
| `Sim/tests/test_npc_tombstones.py` | 2 | NPC-TOMBSTONES — no carry-forward exists in `npc_roster`; red for unbuilt work. |

The first three fail the `repo-tests` stage; the last two fail `sim-tests`. Either alone is enough
to make the whole command exit non-zero.

## Measured 2026-09-21

    $ python tools/validate_repo.py
    + tools/build_asset_registry.py --check     ok
    + tools/export_catalogues.py --check        ok
    + tools/export_controls.py --check          ok
    + tools/verify_provenance.py                ok (79 extracted files)
    + tools/docs_check.py                       ok (231 documents, 0 errors)
    + compileall                                ok
    + unittest discover -s Sim/tests            FAILED (failures=3)
    subprocess.CalledProcessError: ... returned non-zero exit status 1

The **`checks` stage passes completely.** The failure is entirely the deliberate pins plus one
genuine open finding ([WAR-RUIN-CHARGES-GROUND-NO-SCHOOL-HELD](WAR-RUIN-CHARGES-GROUND-NO-SCHOOL-HELD.md)).

## Why this matters more than it looks

A mandated gate that cannot be satisfied trains people to skip it, and once it is skipped nobody
notices when it starts failing for a *real* reason. That is the same defect
[PRODUCT-CONFORMANCE-PROOF-UNCHECKED](../done/PRODUCT-CONFORMANCE-PROOF-UNCHECKED.md) closed on the
documentation side — a gate whose green means less than its reader assumes — arriving from the
opposite direction: here the gate's **red** means less than its reader assumes.

It also interacts badly with the practice this repo relies on. Writing a test that fails to pin a
finding is good discipline and several cards depend on it. But every such pin permanently disables
the closeout command for everyone, so the two practices are in direct conflict and one of them has
to give.

## Proposed mechanism — not chosen, three options

1. **An expected-failure ledger.** A file listing `module::test` plus the ticket that will remove
   each entry; the runner subtracts them and fails if a listed test **passes** (so a stale entry is
   caught, the ratchet shape `tests/test_ceiling_sentinels.py` already uses). Strongest, most work.
2. **`unittest.expectedFailure` on the pinned tests**, which `unittest` already exits zero for.
   Cheapest. Cost: the failure message stops being visible in the run, and these messages are the
   evidence — `'living' != 'alive'` is the finding, not decoration.
3. **Move deliberate pins into a suite the validator does not run**, discovered by its own pattern
   the way `consumer_*.py` already is. Keeps the messages loud, keeps the gate green, and costs a
   convention nobody currently has.

Option 1 preserves the most and is the most work; option 2 destroys exactly the thing the pins
exist to publish. That trade is the decision this card asks for.

## Unresolved

Whether a deliberately-red test should exist at all, or whether a finding belongs in a card and a
`skip` with a reason. This repo has clearly chosen red pins — twice — so the convention is
established in practice and undocumented in `AGENTS.md`. Whichever option is taken, `AGENTS.md`'s
closeout sentence needs to say what a passing validator now means.

## Acceptance

`python tools/validate_repo.py` exits zero on a tree whose only failures are declared pins, and
fails loudly when a pin starts passing or an undeclared test fails. `AGENTS.md` states the rule.
