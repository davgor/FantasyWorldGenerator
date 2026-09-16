# CITY-PLANNER
Owner: local agent. State: accepted.
Scope: ordered final-world city filling for every civilization and clickable lab layout/stats.
A1: Six passes, deterministic measured plots and staffing housing. Evidence: eight city-planner tests pass (8.7 seconds after packing optimization).
A2: Map city click opens labeled interactive layout. Verified atlas pin click opens Glen City; exact city button opens Dunlin; phase filtering and guild hall details inspected. Apartment label inspected: 16 beds, zero final Dunlin shortfall.
A3: Versioned replay and exhaustive potential assets. Tests cover age identity and plotted asset IDs.
A4: Canonical docs and complete regression/validator checks. Documentation updated; full checks completed.
Known constraints: coarse terrain; provisional river corridor; partial plans reported explicitly; four worker beds, no dependents.
Next action: tune city program capacity against settlement scale; preserve explicit partial outcomes on constrained sites. No agents. Preview server session 6693.

Validation: smoke HTTP passed; JS syntax and Python compile passed; CLI-envelope schema validates. Exhaustive list is deterministic: 1,157 IDs, including 82 planner IDs. Required validator currently stops at pre-existing Contracts/catalogues/world-assets.json provenance mismatch. Full suites passed: 170 simulation tests in 160.7s and 15 repository tests in 128.3s. Obsolete pre-apartment runs stopped.

Final acceptance: A1/A2/A3/A4 verified. Browser checked atlas selection, exact city-list selection, phased housing, guild staffing and apartment capacity. Generated artifact drift is intentional: new city plans and 82 potential schematic IDs; repeated showcase exports remain byte-identical. No Unreal validation claimed. Repository validator is not green: 45 unrelated provenance mismatches remain, first at Contracts/catalogues/world-assets.json. python3 is a Windows Store alias; python fallback used. Touched provenance records match. Apartment data is building registry schema 2 revision 3.
