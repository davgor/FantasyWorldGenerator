# CONFORMANCE-DOCS — A present-tense product breakdown under docs/conformance/

## Requested behavior

`docs/conformance/` becomes the record of what this product does now: every Python module claimed
by exactly one record, each stating what it produces, its entry points, what it emits, at what
version, and what proves it. The board stays the verbose change log. A record describes current
behavior; a sentence that only makes sense as history belongs in a ticket.

The records are also the acceptance spec for the future native port. `Core/` is being redone for
the Unreal import and will be validated against them, so precision about versions, determinism and
emitted shapes is load-bearing rather than decorative.

## Proposed mechanism

Capability-noun records in a flat folder, each with the same fixed headings in the same order, so
heading position carries no information and navigation cannot mislead the way a chronologically
ordered document does. Front matter carries the coverage claim (`modules:`), the emitted blocks,
the asserted versions and the proof citations, parsed with stdlib string handling only — the
package declares `dependencies = []` and this gate must not add the first one.

`tools/docs_check.py` enforces the structure in `validate_repo.py --stage checks`:

- Coverage is a total partition over the Python modules under `Sim/`, checked in both directions —
  every claimed module exists, and every module is claimed exactly once.
- `coverage.json` carries a seeded-once `uncovered` allowlist that may shrink and not grow, so the
  gate ships green before the backfill and any module added afterwards fails on its first run.
- Documented version integers are `<!-- conformance:version id=N -->` markers resolved against the
  code that emits them. The checker never scrapes prose, because several historical version
  sentences in the canonical docs are correct as history.
- Every correspondence is checked both ways. Emitted keys against declared schema keys as well as
  the reverse; index against cards as well as cards against index.

## Dependencies and unresolved decisions

- The 42 `Core/` stems are parked in `uncovered` against the Unreal import; no native records are
  written in this ticket.
- Three questions raised by the evening fleet and not yet ruled on by the owner: whether consumer
  blocks carrying standalone schemas is the convention or drift; who owns provenance-manifest
  discipline; and the disposition of the ownerless cards `ASTROLOGY`, `PANTHEON` and
  `SUPER-VILLAINS`. This ticket records existing practice and does not invent policy.

## Sources consulted

`AGENTS.md`, `docs/agent-workflow.md`, `docs/README.md`, `PLAN.md` evidence-layers table,
`board/templates/task.md`, `provenance/README.md`, `tools/validate_repo.py`,
`tools/verify_provenance.py`, the 25 documents under `docs/`, and the coordinator's
2026-09-19 fleet backlog.

## Files and assets in scope

New: `docs/conformance/` (charter, template, records, `coverage.json`, `version-bindings.json`,
three generated indexes), `tools/docs_check.py`, `tests/test_docs_check.py`.

Changed: `AGENTS.md`, `docs/agent-workflow.md`, `docs/README.md`, `tools/validate_repo.py`,
`.github/workflows/publish.yml`. The 23 unpinned subsystem documents under `docs/` fold into
records and are removed.

Provenance-pinned files touched, each with an appended revision row: `Sim/README.md`,
`docs/terrain-world-layers.md`, `docs/terrain-math-lab.md` — the mandated `python3` invocation in
each, which cannot launch on the development machine.

## Acceptance and evidence

Verification for this repository is centralised on the coordinator session while a performance
measurement is in progress; test suites and world generation are not run from here. Evidence to be
requested rather than self-reported:

- `python tools/validate_repo.py` passes.
- `python tools/verify_provenance.py` stays green at 79 files.
- `python tools/docs_check.py` reports zero findings in the hard-fail families.
- Negative tests fail with their named error strings: a corrupted `proof:` citation, an unclaimed
  module, and a code constant bumped without its marker.

## Adversarial review and limitations

A green `docs_check.py` proves that a record points at things which exist and that its version
markers match the code. It proves nothing about whether the record is true. A record can be
complete, passing and vacuous; the only defence is that each is small enough to be read.

The coverage ratchet needs a merge base, so on a direct push or shallow clone it reports itself
skipped rather than passing silently. In that window a module could land in `uncovered` in the same
commit that creates it. Adding an entry still costs a ticket file and a visible diff, which is a
social control on top of a machine one and is not claimed as more.

## Handoff

Phase 1 mechanical sweep in progress. Later phases land the charter and checker with an empty
finding set, two prototype records, then the remaining records in small groups.
