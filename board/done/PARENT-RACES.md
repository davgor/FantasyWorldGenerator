# Parent race blocks
Completed: 2026-09-15. Owner: local agent.
Authoring JSON schema 5 / revision 7 wraps full civilization definitions in parent_races.<id>.civilizations.
Human: six human cultures. Elf: elf and tidekin. Dwarf: dwarf and gnome.
Explicit civilization_order preserves prior generation order. Runtime flattening adds derived parent_race_id for report metadata; no inheritance or shared capitals.
Behavioral tests cover nested source, parent membership, invalid parent IDs, duplicate nested IDs, ordering, JSON-only expansion and generated reports. No new asset IDs: 1,157 remain.
Validation: python3 alias unavailable; python validator still fails on existing Contracts/catalogues/world-assets.json provenance mismatch. Targeted tests recorded in handoff.
Preview regenerated under the new registry. Saved worlds from revision 6 must be regenerated before age advancement. Next action: use nested blocks for future civilization additions.
