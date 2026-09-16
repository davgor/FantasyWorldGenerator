# Civilization master registry

Owner: local agent. Status: complete.

## Acceptance

- A1: One versioned packaged JSON authoring source owns all current civilization definitions, traits, special rules, presentation, building/layout data, city classes and measured structure blocks. No independent duplicate datasets.
- A2: Generation, UI and asset compilation consume the master through validated generic loaders. A new entity can be added with JSON edits, without species-specific Python branches.
- A3: Preserve current placement, supply and asset behavior. Capture baseline worlds and compare after migration; add failing tests before behavior/loader edits.
- A4: Document extension and schema/version rules; record scoped provenance. Run full suites and required repository validation, reporting unrelated blockers.

## Scope

Preserve prior uncommitted civilization and structure work. No commits, publication or Unreal assets. Existing JSON entry paths may become explicit redirects to sections of the master, so they cannot remain competing edit sources.

## Work items

- Baselines and behavioral tests: accepted. Three pre-migration worlds match after excluding timing and intentional civilization report metadata; full asset output unchanged. Six focused registry tests and 143 simulation tests pass.
- Master data and generic consumers: accepted. JSON-only copper_folk fixture generates cities and appears in exhaustive asset references.
- Docs, validation and provenance: accepted. Authoring guide and decision 017 complete; modified extracted files match scoped provenance revisions. All 15 repository tests pass, including two identical showcase builds.

## Verification evidence

Local evidence: `Artifacts/civilization-registry-checks/` (baseline-comparison.txt, sim-tests.log, repo-tests.log, validator.log, provenance-audit.json).

- Simulation suite: 143 passed. Registry tests include invalid input, independent JSON-only extension, class thresholds, saved-registry mismatch and disabled layout features.
- Asset compilation: two byte-identical outputs, equal to pre-migration export. No asset drift.
- Loopback lab smoke, Python compilation, JavaScript syntax and git diff checks passed.
- Required `python3 tools/validate_repo.py`: Windows Python alias unavailable. Fallback `python tools/validate_repo.py` stops on the pre-existing world-assets provenance mismatch. 46 unrelated mismatches remain; every modified provenance-tracked file matches its revision. The formerly mismatched terrain-math-lab document was edited for this task and received a scoped revision.
- Initial repository suite launch omitted PYTHONPATH and failed imports; corrected rerun with PYTHONPATH=Sim passed all 15 tests. Total: 158 passing tests.
- Wheel build could not run because this environment has no pip; package-data configuration includes all icarus_sim JSON files. No installed-wheel validation claimed.

## Compatibility and next action

Civilization report 2 pins registry schema/revision/hash and exports presentation. Report-1 worlds require regeneration; changed registry definitions reject old age state. Recipe 3 and algorithm 9 retain baseline placement with the shipped definitions. Measured non-housing blocks remain planning input; integrating their plot measurements into city layout placement is the next design step. Housing and catalogue rebuild remain deferred. No commits or Unreal edits.
