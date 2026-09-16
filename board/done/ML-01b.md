# ML-01b — Capabilities, coordinates and physical units

## Requested behavior

Describe supported producer capabilities and coordinate/unit semantics in a versioned portable contract so consumers can reject unsupported requirements without guessing from package version or display labels.

## Dependencies and scope

Depends on ML-01a. Read `Contracts/terrain-taxonomy.md`, `docs/continuous-terrain.md`, `docs/unified-world-scene.md` and `docs/unreal-integration.md`. Preserve existing generator and export semantics. Resolve differences between globe, local tangent, city and tile representations explicitly.

## Acceptance

- Versioned machine-readable capabilities distinguish JSON/reference support from native, editor and cooked runtime support.
- Canonical axes, handedness, angular units, reference radius/datum, local origin and longitude seam/pole conventions are documented for each supported representation.
- Independently authored fixtures exercise cardinal directions, local frames, negative/nonzero sea level, seams/poles and metre units.
- Metre-to-Unreal-centimetre conversion is explicit at the future adapter boundary; no Unreal dependency enters the simulation package.
- Unsupported capability versions and invalid/nonfinite coordinates have defined rejection behavior and tests written before implementation.
- Canonical docs, package contents and full repository validation agree. Any changed interchange semantics receive a version decision.

## Handoff

Completed 2026-09-16. Full local repository validation passes. Python tests do not qualify an Unreal adapter.

## Implementation and evidence

- Canonical `Contracts/capabilities-and-coordinates.md` and packaged `capabilities.json` distinguish reference/JSON support from unavailable native, editor, cooked and migration capabilities.
- Strict `require_capabilities` negotiation and pure `resolve_coordinate` helpers preserve existing simulation code and output schemas. Invalid types/versions, nonfinite arithmetic and invalid coordinate bounds are rejected.
- Independent fixtures contain 24 valid coordinate vectors, 14 invalid coordinate requests, 3 valid capability requests and 9 rejected capability requests. City gnomonic and patch exponential-map projections are explicitly distinct.
- Tests were added before implementation: initial imports failed on the missing oracle; the later CLI test failed on the absent command before CLI changes.
- Eight focused behavioral tests pass, covering existing city/patch/tile agreement, right-handed frames, seam/pole and nested samples, invalid input, descriptor/schema agreement, CLI export and unsupported-version non-overwrite.
- Wheel built and installed in a temporary environment. The same eight tests pass outside the checkout using installed modules and packaged data.
- `capabilities` CLI output is byte-reproducible and matches its canonical descriptor; artifact assembly now includes it. Asset-list bytes match HEAD and ML-01a: SHA-256 `128c7b20bb9c3fc427cabfb5070d7e4113b48585826a8ff8ddad8a0f935d8007`.
- All 79 extraction entries validate; no additional provenance revisions were needed. `python3 tools/validate_repo.py` passed on Python 3.9.6: 213 reference tests, 30 facade tests, two byte-identical showcase bundles, loopback lab smoke and byte-reproducible asset compilation. `git diff --check` is clean.

## Compatibility and limitations

This is an additive capability/coordinate contract v1 and CLI command. World/asset schema versions, seeds, generation algorithms and asset identities are unchanged. Canonical terrain, city, globe, publishing and Unreal-boundary documents link the new contract. The existing generation/import validation paths do not call these helpers. Fixture tolerances are scoped to coordinate vectors; ML-01c still owns the kernel numeric/PRNG contract. No engine axis mapping, importer or runtime qualification is claimed. Current CI has not been rerun and no commit, push or publication was performed.

Next: ML-01c numeric, PRNG, ordering and serialization decisions and independent vectors. Keep ML-01 open until ML-01c/d are complete.
