# Arctic civilizations

Owner: local. State: complete. No delegates.

## Delivered

- Cold Peoples use 0.9 weighted habitat km2 per city and a 30-resident founding minimum; other existing civilizations retain 40. Normal and diaspora quotas remain food-capped.
- Crop temperature is independent of settlement comfort in annual and seasonal surface/sky calculations. Cold Peoples retain 25% winter fishing access under complete route ice; Frostholds retain 15%, with exclusive fishing grounds and finite production unchanged.
- Independent Frosthold Dwarf entity under dwarf: northern mineral uplands/coastal cliffs, supply reach, compact city presets, fuel stores, preservation facilities and guild halls. Shared measured assets and housing remain covered by the exhaustive compiler.
- Algorithm 13, settlements 14, population budget 4, founding 4, population profiles 4, registry schema 6/revision 11. Canonical docs and affected schema/provenance updated. Existing worlds require regeneration.

## Acceptance evidence

- Behavioral tests added before implementation; seven Arctic tests pass, including actual frozen fisheries and seasonal crop independence.
- Full Sim suite: 197 tests passed in 444.582s.
- Full repository suite: 16 tests passed in 307.284s, including reproducible showcase exports.
- Compileall, lab HTTP smoke, final-world JSON schema, deterministic exhaustive asset compilation and git diff --check passed.
- Seeds 42/73/108 have 2/3/2 Cold Peoples cities and Frosthold presence at founding. Seed 42 final allocation 651 <= world cap 948; delivered fish 73.8 <= nominal 158.35.
- Seed 42 physical height, temperature, rainfall and natural biome match the preceding algorithm baseline exactly. Its Frosthold capital is destroyed by a glacier dragon in Age 1 and correctly retained as ruins; survival is not guaranteed.
- Updated preview served on port 8769. Founding view shows the Frosthold capital and no browser errors were observed.

## Limitations and next action

- Required python3 validator command is unavailable through the Windows Store alias; python tools/validate_repo.py reaches the existing provenance mismatch in Contracts/catalogues/world-assets.json and stops. This unrelated catalogue was not rewritten. Export tests passed; new civilization eligibility is intentional generated metadata change, with no new asset identities.
- Hunting, herding, fuel consumption, insulation and geothermal production remain future work. Pre-founding marine support remains a prospective upper bound; later seasonal trade/food simulation can expose shortages.
- Next action: refresh the lab and regenerate worlds using algorithm 13; inspect Founding as well as final history to distinguish failed settlement from subsequent destruction.
