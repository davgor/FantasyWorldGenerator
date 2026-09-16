# City building staffing

Owner: local agent. Status: complete.

- A1: All 80 measured structure definitions carry provisional minimum/target/maximum role rosters, counting distinct people across all shifts. Housing location separates city and hinterland workers. Verify structure/validation tests.
- A2: Every resolved city preset multiplies staffing by building count, separates conditional additions and reports worker-bed estimates without inventing household size or house counts. Verify arithmetic, culture overrides and shared infrastructure crews.
- A3: Registry schema/revision and canonical docs updated; runtime layouts and assets unchanged. Verify full suites, smoke, asset comparison and required validator.

Scope: staffing data and planning calculations only. Preserve existing building selections, deferred housing and unrelated edits. No commits, publishing or Unreal changes. Tests observed failing before implementation. Evidence: Artifacts/city-staffing.

## Acceptance evidence

A1-A3 accepted. All 80 measured structures carry validated role rosters. All 30 city presets resolve minimum/target/maximum totals, conditional additions and city/hinterland worker beds. Per-entry civilization overrides work; linear infrastructure cannot acquire duplicated segment rosters. Resident and house totals remain unknown until households and occupancy are modeled.

152 simulation tests plus 15 repository tests passed (167 total), including five new staffing behavior tests and reproducible showcase builds. Asset export matches the preceding preset export exactly. Lab smoke, Python compilation and git diff checks passed. Evidence logs and per-preset summaries are in Artifacts/city-staffing.

Required python3 validator cannot launch through this machine's Windows alias. Python fallback stops on the pre-existing unrelated Contracts/catalogues/world-assets.json provenance mismatch. Scoped canonical-document provenance updated; unrelated mismatches preserved.

Registry schema/revision are now 3/3; older registry hashes require regeneration before age advancement. Runtime population, layouts, asset output and NPC generation remain unchanged. Next step: use staffed-worker estimates together with dependents, households and dwelling occupancy to size housing, and reconcile the generous service presets with available city area. No commits or Unreal changes.
