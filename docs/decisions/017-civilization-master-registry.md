# 017: Civilization master registry

Civilization data lives in `Sim/icarus_sim/civilizations.json`, including independent entity rules, presentation and construction-library bindings. Shared libraries live in the same master file. Former entry paths contain redirects only. Generic consumers replace species-specific code branches.

Recipe 3 and algorithm 9 remain unchanged because sampled placements, supplies and exhaustive asset output match the pre-migration baselines. The civilization report advances to version 2 to publish registry identity and appearance; age advancement rejects a mismatched registry. Existing report-1 worlds require regeneration. See [authoring and compatibility](../civilizations.md).

The measured human structure library remains planning input, with housing deferred. This change does not claim measured building placement or Unreal validation.
