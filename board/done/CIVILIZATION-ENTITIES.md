# Standalone civilizations and city classifications

Owner: local agent. Status: accepted for the requested implementation; repository-wide provenance drift remains external to this change.

## Scope and acceptance

- A1: Replace generic human/highland/woodland profiles with six independent, complete entities: Maritime, Desert, Cold, Large island, Deep rainforest and European-inspired fallback. No entity inherits the old human dataset. Verify complete records, old-ID rejection and habitat fixtures.
- A2: Select cities by environmental suitability without forcing any group to exist. Every nonempty civilization has exactly one capital, including single-city groups. Remaining cities are small or medium by suitability. Verify zero/one/multiple, deterministic ties, no fabricated populations and age rebuilding.
- A3: Propagate entity identity through surface/sky communities, rural support, UI and exports. Preserve survivor founding identity. Version changed contracts and reject old state. Verify replay, upstream isolation and catalogue coverage.
- A4: Update canonical documentation, compatibility decision and provenance for intentional edits. Run required validation, report any pre-existing drift explicitly.

## Work items

- Entity registry and behavioral tests: accepted. Six complete independent human entity records replace generic human/highland/woodland. Nonhuman records are also explicit, with no `extends` field.
- Generation, capital classification, UI and export integration: accepted. Data-driven habitat partition, bounded shared quotas, deterministic capitals, medium/small threshold, support-region map, age-state validation and building-reference civilization IDs are integrated.
- Documentation, provenance and verification: accepted for scope. Decision 016 and canonical behavior/contracts/publishing docs updated. Intentional edits to 19 extracted files have revision records; exact-byte Git attributes protect those reviewed bytes.

## Decisions

User confirmed one capital per human culture and explicitly rejected extending the old human profile. Each civilization owns all numerical traits. Cultural inspiration does not describe real-world people or constrain later art implementation.

Prior housing/structure data is unrelated work to preserve. Its shared structures can be referenced by multiple independent entities without profile inheritance.

## Verification evidence

- New tests failed first for absent entities/module/classes, missing cultural-region indices, malformed habitat validation, and missing asset-reference civilization IDs, then passed after implementation.
- Final `PYTHONPATH=Sim python -m unittest discover -s Sim/tests -q`: **137 passed** (99.306 s).
- Final `PYTHONPATH=Sim python -m unittest discover -s tests -q`: **15 passed** (106.129 s), including showcase byte reproducibility. An earlier showcase comparison ran while its JS source was still being edited and failed; rerun after freezing sources passed.
- Python compileall, `node --check tools/terrain_world.js`, loopback lab HTTP smoke and `git diff --check` passed.
- Seed 42, size 33, final age: 10 active cities / 5 capitals / 5 medium cities, 3 ruins. Maritime and Cold each have one city and one capital; absent entities retain zero and null capital. This sample is evidence, not a quota promise. Small classification is covered with low-suitability fixtures.
- Asset compiler is deterministic: 1,075 identities, including the existing 84 building assets. Digest changed intentionally from `48ed1ff41f8f0a542940ccfecd3a8a6b99879e85e7fe10b3eb929da2a59c6d6a` to `9cbff3a70f82c688d500e6b009801c55910cefcf7e339240bb4007e3da9f3baf` because building references now expose civilization eligibility. No production asset identities were added.
- Logs and sample summary: `Artifacts/civilization-checks/` (local ignored verification output).

## Repository-wide limitation

Required `python3 tools/validate_repo.py` was attempted; Windows has no working python3 alias. Fallback `python tools/validate_repo.py` stops at existing `Contracts/catalogues/world-assets.json` provenance drift. Audit found 47 remaining mismatches in unchanged files, zero among changed provenance-tracked files. Do not reinterpret the passing separately run suites as a passing wrapper or repair historical hashes without reviewing that existing drift.

## Handoff

All requested entity/city-class behavior is implemented. Algorithm 9 intentionally changes population/settlement seed results; algorithm-8 worlds require regeneration. Capital classes apply to active surface cities; sky communities keep separate budgets. Cultural art, final building geometry and Unreal runtime validation remain future work. Next action: generate a fresh world and inspect Civilization region plus city classifications before returning to building layouts and the later production catalogue rebuild. No commit, push, publishing or Unreal asset mutation performed.
