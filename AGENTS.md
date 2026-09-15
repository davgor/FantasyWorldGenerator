# Agent development

- At task start or resume, read `docs/README.md`, `docs/agent-workflow.md`, and the relevant canonical system document.
- Preserve deterministic generation, schema versions, seed compatibility, and existing regression coverage. Treat changes to any of these as public-contract changes.
- Add a behavioral test before changing simulation, export, catalogue, or validation behavior.
- Update affected canonical documentation in the same change. If behavior is unchanged, record a concrete no-documentation-impact rationale in the handoff or PR.
- Keep the simulation engine-independent. Unreal-specific code belongs in a future adapter/plugin; the canonical boundary here is versioned JSON.
- The exhaustive asset list describes every supported potential final state, not one sampled world. Update its compiler and tests whenever a generator state can reference a new asset.
- Run `python3 tools/validate_repo.py` before closeout. Report tests, generated-artifact drift, known limitations, and the next action.
- Preserve unrelated work. Do not commit, push, publish, or mutate Unreal assets unless explicitly requested.

## Code review rules

- Flag nondeterminism, unversioned interchange changes, broken seed replay, missing potential-state assets, and behavior/documentation discrepancies.
- A passing Python test does not prove an Unreal importer or packaged game works; do not claim engine integration without engine evidence.

## Unreal tooling

- When a downstream Unreal adapter exists, use connected Unreal tooling for asset inspection and editor validation, verify the connected project first, and never edit `.uasset` or `.umap` binaries directly.
- Keep source dimensions in metres and make the metre-to-Unreal-centimetre conversion explicit at the adapter boundary.

