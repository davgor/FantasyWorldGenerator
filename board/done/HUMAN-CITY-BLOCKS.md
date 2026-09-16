# Human city civilization blocks

## Requested outcome

Record reusable human city structure data for future city layouts and a later production catalogue rebuild. Housing is deferred. User additionally requested measurements for map generation.
Owner: local agent. No runtime placement, new simulation asset references, or Unreal edits.

## Acceptance

- A1: Human non-housing functions grouped in canonical JSON with stable IDs, purpose, priority, prerequisites, placement, module families, provisional measurements and existing asset reuse candidates. Verify with catalogue tests and content review.
- A2: Explain scope, game-scale reuse and deferred housing in canonical documentation.
- A3: Run catalogue tests and repository validation; check existing asset-list digest for drift.

## Work items

- Data and tests: accepted; `Contracts/catalogues/human-civilization-blocks.json` contains 80 requirements in 11 blocks. Three catalogue tests pass, including footprint/clearance arithmetic, finite measurements, deferred housing, resolved reuse references and no runtime export enablement.
- Documentation: accepted; `docs/catalogue/human-civilization-blocks.md` describes measurement semantics, all 80 structures, sharing and layout conditions. Documentation and contract indexes link it.
- Verification: accepted for scoped data; three new tests and six existing asset-list tests pass. Full repository validation was attempted and remains blocked by the pre-existing provenance mismatch described below.

## Evidence and known limitations

Existing exports: 1,075 assets; SHA-256 `48ed1ff41f8f0a542940ccfecd3a8a6b99879e85e7fe10b3eb929da2a59c6d6a`.
No existing file or section is named human civilization blocks. The closest runtime data is the city building pack catalogue. This new design catalogue deliberately stages requirements for later use.

Tests were added before data and failed because the catalogue did not exist. The measurement test then failed before dimensions were added. All three now pass.

`python3 tools/validate_repo.py` could not run because the Windows python3 alias has no interpreter. Fallback `python tools/validate_repo.py` stops at the existing unrecorded provenance drift in `Contracts/catalogues/world-assets.json`; the file was not changed in this task. Full-suite and smoke evidence is therefore unavailable. Do not regenerate provenance merely to suppress this error.

Six existing asset-list tests pass. Existing export count and digest above are unchanged; no generated-artifact drift was introduced. `git diff --check` passes. No simulation code, recipe, seed contract, production catalogue or Unreal assets changed.

## Handoff

Scoped design data complete. Measurements are provisional, not historical survey values or validated Unreal geometry. Next action: use these plot reservations and service relationships to design the city layout resolver, including terrain fit, conditional structures, shared facilities, door/gate clearance and route connections. Housing remains a separate later pass; production catalogue rebuilding follows layout decisions.
