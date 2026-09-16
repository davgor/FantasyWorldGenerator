# Migration cultures
Owner: local agent. State: accepted.
A1: Human95/elf25/dwarf60 parent participation; High Elf display name; full independent plains-preferring Hill Dwarf entity. Registry and asset-coverage tests added.
A2: Parent origins separated by >=90 degrees, infeasible origins explicitly absent; deterministic source-city/cultural branch records and 250-year calendar. Unit tests cover origin separation, failure, lineage and calendar continuation.
A3: Algorithm11 / settlements12 / founding2 export compatibility; shared asset IDs with new civilization eligibility. Full regression passed: 182 simulation tests in188.6s and15 repository tests in160.4s.
A4: Live preview log shows years and source culture; browser verification pending.
Focused 36 tests passed. World schema passed, all origin separations exceed90 degrees (95.8/139.0/125.2), 1,157 potential asset IDs retained. JS syntax, Python compile, diff-check and HTTP smoke passed. Full suites passed (197 tests). Next: tune rates, calendar scale and habitat balance with the migration log. Live preview refreshed on8769 (session92394). No agents; preserve unrelated provenance mismatch.

Required validator attempted with python3 (unavailable Store alias) and python fallback; existing unrelated Contracts/catalogues/world-assets.json provenance mismatch still blocks it. Scoped changed-file provenance updated. Generated artifacts intentionally change civilization eligibility and migration histories; distinct production Hill Dwarf art is future work.
