# Linked shared building registry

Owner: local agent. Status: complete.

- A1: buildings.json owns the 80 measured definitions and shared pack/layout libraries; civilizations.json links it and retains entity selections/overrides. No duplicate disk definitions.
- A2: All races reference neutral building.* IDs and common library; each of 30 presets retains one two-worker guild hall. Preset measurements/counts/staffing and exhaustive assets match pre-split baselines.
- A3: Loader validates references, fails missing/invalid links, reloads after either file changes and includes both in replay identity. Tests first, current docs, scoped provenance and required validation.

Focused linked-file tests were observed failing before implementation. Evidence: Artifacts/buildings-split. No commits, publishing or Unreal changes. Coordinate placement and housing remain deferred.

## Accepted evidence

A1-A3 verified. buildings.json (schema 1/revision 1) contains the shared definitions and runtime libraries; civilizations.json (schema 4/revision 5) contains a sibling-file link and independent selections. The common library uses neutral building.* measured IDs. All 30 expanded city plans equal their pre-split versions after only the ID rename; full asset output is identical.

156 simulation tests plus 15 repository tests passed (171 total). Linked-file tests cover neutral IDs and guild halls, file edits/reload/replay identity, missing/unsupported files, invalid paths and competing embedded libraries. Showcase output reproduces exactly across two builds. Lab smoke, compileall and git diff checks passed. Source package-data includes *.json, covering the new file.

Required python3 validator cannot launch through the Windows alias; Python fallback stops at the pre-existing unrelated Contracts/catalogues/world-assets.json provenance mismatch. Updated only scoped edited-file provenance. No new runtime assets or asset drift. Saved worlds under previous registry hashes need regeneration; population metadata now identifies common instead of human.

Next action: consume linked measured city plans during site filtering and coordinate placement. Housing and hero calculations remain deferred; HERO-GUILD remains in backlog. No commits or Unreal changes.
