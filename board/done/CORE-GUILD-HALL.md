# Core guild hall

Status: complete. Owner: local agent.

All 30 civilization/size presets contain exactly one unconditional guild hall. The existing measured hall is core and retains its dimensions. Staffing is one cook and one bartender (two workers at minimum/target/maximum); former officers and clerks are removed. No heroes are added to population or housing estimates. Authored registry revision is 4; schema remains 3. Earlier registry hashes require regeneration before age advancement.

Created backlog ticket `board/backlog/HERO-GUILD.md` for hero-guild calculations and updated canonical civilization and structure documentation. Runtime placement remains deferred.

Behavioral test observed failing before edits. All 26 focused registry, city-preset, staffing, structure and asset tests pass. Full asset export unchanged; git diff check passed. Evidence: Artifacts/core-guildhall. Required python3 validator cannot launch through the Windows alias; Python fallback encounters the unchanged pre-existing Contracts/catalogues/world-assets.json provenance mismatch. No unrelated provenance updates, commits or Unreal changes.

Next action: take HERO-GUILD from backlog when its calculation inputs and housing dependencies are ready.
