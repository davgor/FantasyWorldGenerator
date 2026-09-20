# Agent development

- At task start or resume, read `docs/README.md`, `docs/agent-workflow.md`, and the conformance record for the capability you are changing (`docs/conformance/`).
- Preserve deterministic generation, schema versions, seed compatibility, and existing regression coverage. Treat changes to any of these as public-contract changes.
- Add a behavioral test before changing simulation, export, catalogue, or validation behavior.
- Update affected canonical documentation in the same change. If behavior is unchanged, record a concrete no-documentation-impact rationale in the handoff or PR.
- Keep `docs/conformance/` true. It states what the product does now; `board/` states what changed. See the section below.
- Keep the simulation engine-independent. Unreal-specific code belongs in a future adapter/plugin; the canonical boundary here is versioned JSON.
- The exhaustive asset list describes every supported potential final state, not one sampled world. Update its compiler and tests whenever a generator state can reference a new asset.
- Run `python tools/validate_repo.py` before closeout. Report tests, generated-artifact drift, known limitations, and the next action.
- Preserve unrelated work. Do not commit, push, publish, or mutate Unreal assets unless explicitly requested.

## Conformance records

`docs/conformance/` is the present-tense breakdown of what this product does. `board/`
is the change log. A record states current behavior; a sentence that only makes sense as
history belongs in a ticket.

- Every module under `Sim/` is claimed by exactly one record, in that record's `modules:`
  front matter. `tools/docs_check.py` enforces it and runs inside `--stage checks`.
- **Adding a capability.** Claim the new module in the record that owns its area, or add
  a record and claim it there. State the inputs, the block it emits and that block's
  version, the determinism guarantee, and the failure modes.
- **Changing a capability.** Change the record in the same commit. If a schema, report or
  planner version moves, update its `<!-- conformance:version id=N -->` marker and the
  sentence beside it. The checker compares the marker against the code, so a stale marker
  fails and a stale sentence does not — write the sentence honestly anyway.
- **Removing a capability.** Delete the claim and the text describing it. A record
  describing code that no longer exists is a false statement with a passing suite
  standing behind it.
- **Widening a record you do not own.** If your change means a block another record owns
  can now change at a time it could not before — a new writer, a new trigger, a new
  failure mode — edit that record in the same change, even though no version moved and
  none of its modules changed. `## Where it runs` is a claim about when a thing is
  stable, and a consumer caches on it.
- **Changing nothing a record describes.** Change nothing. A timestamp-only edit is not an
  update, and rewording a paragraph so a diff appears is worse than leaving it alone
  because it costs a reviewer's attention and buys nothing. Put the rationale in the
  handoff.
- Records distinguish **binding invariants** — determinism, replay identity, draw and
  iteration order, byte reproducibility, id stability across ages — from **current
  description** such as cost and counts. Do not break an invariant because the
  mathematics looks equivalent; float addition is not associative. Any cost figure states
  its seed, world size and machine.
- Do not widen a glob, add a `frozen_docs` entry or add an `exempt` reason to quiet the
  checker. Adding a module to the uncovered allowlist is the one exception, it requires a
  board ticket, and the allowlist may only shrink.
- A green `docs_check.py` proves a record points at things that exist and that its version
  markers match the code. It proves nothing about whether the record is true. Do not cite
  it as documentation review.

## Code review rules

- Flag nondeterminism, unversioned interchange changes, broken seed replay, missing potential-state assets, and behavior/documentation discrepancies.
- A passing Python test does not prove an Unreal importer or packaged game works; do not claim engine integration without engine evidence.

## Unreal tooling

- When a downstream Unreal adapter exists, use connected Unreal tooling for asset inspection and editor validation, verify the connected project first, and never edit `.uasset` or `.umap` binaries directly.
- Keep source dimensions in metres and make the metre-to-Unreal-centimetre conversion explicit at the adapter boundary.

