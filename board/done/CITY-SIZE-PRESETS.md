# City size presets

Owner: local agent. Status: complete.

- A1: Every independent entity has explicit small_city, medium_city and capital_city lists, with measured building references and positive quantities. No housing. Verify contract tests.
- A2: Selections grow with size and reflect culture; conditional terrain facilities retain prerequisites. Linear infrastructure sizes from routes/perimeters, not arbitrary building counts. Verify fixtures and review authored lists.
- A3: Validated resolver returns self-contained measured requirements for later placement. Registry schema/revision updated, canonical docs synchronized, existing asset output preserved. Verify tests, asset comparison and repository validator.

Scope: preconfigured requirements, not coordinate placement or replacement of the current runtime layout engine. Preserve existing unrelated edits; no commits or Unreal changes.

Tests were added and observed failing before implementation. Acceptance A1–A3 verified; evidence under Artifacts/city-presets.

## Verified outcome

All 10 entities have three explicit independent blocks (30 presets). Small presets have 28–30 instances, medium 57–62, capitals 82–87 before prerequisite filtering. Streets, drains and defenses use route/perimeter sizing. Shared measurements are provisional, including nonhuman reuse of the historical human.* library; entity lists and names remain independent.

147 simulation tests and 15 repository tests passed (162 total), including reproducible showcase export. Asset output equals the previous export; no new runtime asset states or catalogue drift. Lab smoke, compileall and git diff checks passed. Registry schema 2 / revision 2 is explicit; old registry hashes require regeneration before age advancement.

Required python3 validator could not launch due to the Windows alias. Python fallback stops at the existing unrelated Contracts/catalogues/world-assets.json provenance mismatch. Scoped provenance updated for the edited canonical world-layer document; unrelated files preserved.

Next action: connect the measured city_plan output to site-condition filtering and coordinate placement. Current runtime building placement is unchanged; these are preconfigured requirements. Housing remains deferred. No commits, publishing or Unreal assets changed.
