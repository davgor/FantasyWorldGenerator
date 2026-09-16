# ML-01a — Portable terrain taxonomy and identity

## Requested behavior

Freeze the current recipe-3 terrain vocabulary for portable consumers. Resolve natural or magical identities without ambiguous aliases, reject unsupported versions and retired IDs, and trace all potential terrain states to semantic asset requirements.

## Dependencies and scope

ML-00 has clean-checkout CI evidence. This is the first bounded ML-01 slice, not completion of the parent ticket. Preserve all generator behavior and existing export schemas. Entity IDs outside terrain, numeric/PRNG rules, coordinates and kernel capabilities remain separate work.

## Implementation

- Packaged canonical `terrain_taxonomy.json`, taxonomy version 1 / recipe 3.
- Independent `fantasy_world_generator.taxonomy` oracle with strict request fields/types, no aliases, and caller-owned results.
- `Fixtures/taxonomy-v1.json` hand-authored conformance examples and invalid requests.
- `Contracts/terrain-taxonomy.md` records identity, ordering, compatibility, rejection and asset-ownership decisions.

## Acceptance and evidence

- [x] Behavioral tests added first; initial run failed because the new oracle module did not exist.
- [x] Five focused tests pass, including all 13 natural and 104 magical state references, retired IDs and strict input validation.
- [x] Built a wheel in an isolated build environment and installed it into a temporary virtual environment. From `/tmp`, the installed package passes all 4 valid and 10 invalid JSON fixture cases and loads its packaged registry without a source checkout on the import path.
- [x] Full `python3 tools/validate_repo.py` passed on Python 3.9.6: 213 reference tests and 22 facade tests, including these five tests, two identical showcase bundles, loopback lab smoke and deterministic asset compilation. Asset bytes match HEAD; no tracked generated artifact was changed.

Asset output compared byte-for-byte against a temporary `git archive HEAD Sim` baseline: unchanged SHA-256 `128c7b20bb9c3fc427cabfb5070d7e4113b48585826a8ff8ddad8a0f935d8007`. All original extraction source hashes are unchanged. The build frontend was installed only in a temporary virtual environment because the system Python lacks `build`.

## Limitations and next action

This additive oracle is not wired into existing world validation and does not claim native/Unreal conformance. No new potential asset state is introduced; existing compiler coverage is verified without changing its output. Continue with ML-01b after verification; ML-02 still depends on completing the parent contract ticket.
