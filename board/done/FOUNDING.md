# Founding rounds and preview fidelity
Owner: local agent. State: accepted.
A1: One viable capital per parent in first round, expanding radius and participation thereafter. Founding unit tests pass; real seed42/65-sample initial report has one human, elf and dwarf parent capital and reaches 11/11 cities in 11 rounds.
A2: Prefer unused cultures; deterministic termination with quotas and safety limit. Tested synthetic cases.
A3: Preserve survivors, no new asset IDs, explicit version migration. 176 simulation tests passed; 16 founding/history tests passed after the additional survivor-at-target guard.
A4: Live resolution selector and same-seed regenerate plus round log. Browser verified same-seed regeneration, 64-cell resolution, Founding stage and per-round log.
Implementation: founding.py, settlement selection, registry participation fields, algorithm 10 / settlement report 11, preview controls. Defaults human80/dwarf60/elf45.
Final repository suite passed: 15 tests in 134.2 seconds, including byte-identical showcase exports. Next: tune parent participation percentages and quota calibration through the live preview. Scoped provenance updated. Known validator blocker remains unrelated asset catalogue provenance. Active live preview: port8769, session17133.

Closeout: generation changes intentionally alter city, society and history artifacts; terrain inputs and 1,157 potential asset IDs remain supported. World schema verifies algorithm10/settlements11 exports. JS syntax, compileall, diff-check and HTTP smoke passed. python3 unavailable (Store alias); python validator stops at existing Contracts/catalogues/world-assets.json provenance mismatch. No commit, publish or Unreal changes.
