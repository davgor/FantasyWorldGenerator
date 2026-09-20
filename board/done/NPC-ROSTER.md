# NPC roster

Owner: local. State: complete. No delegates.

## Requested behavior

A simplistic structure for the NPCs: "We know about how many NPCs are in the game. We need to be able to mark them as important/quest giver — these are NPCs that we have earmarked as people who can give out quests if the quest generator detects it. They will also need a state for alive/dead so we aren't passing quests to dead NPCs to give out." Racial traits were explicitly out of scope, coming from the concurrent heritage work; the quest generator is the stated follow-up once the in-flight epics close.

The count was already implied and never materialized. `docs/civilizations.md` says outright that "each post assumes a different NPC" and that no NPC is created, while the three planners place buildings whose staffing rosters sum to roughly 12,700 posts on a size-65 world.

## Delivered

- New consumer package `Sim/npc_roster/` in the `hero_generator` / `story_web` mould: reads the finished world as plain JSON, writes only the `npcs` block, never imports `icarus_sim`, derives every draw from a copied `child_seed`, and its `attach` never raises. `FANTASY_WORLD_NPCS=0` leaves the key absent. **No recipe, seed, planner or schema version moves**, so nothing needs regenerating and there is no `Core/` port to keep in parity.
- One record per staffed post across `city_plans`, `hamlet_plans` and `castle_plans`, expanded senior-first from a policy snapshot of the building registry, with the plot's own worker count winning over the snapshot when a civilization overrides the roster.
- `important`: the quest-giver earmark, authored and capped per site (capital 6, medium 4, small 3, fortress 2, hamlet 1). Every hero is important and no cap can demote one.
- `status`: `alive`/`dead` birth state, `legend` mapping to dead. The block is never mutated; a runtime copies it into its own save and flips it there.
- Every hero and Dread folded in cross-linked by `hero_uid`, so one list answers "who is important and alive" rather than joining two blocks with different life-state vocabularies.
- `post_verbs` tags each post with the verbs it can plausibly offer, from the ten the quest work pinned, exported on the block so a consumer reading `world.json` alone has them.
- `presence_node` carries where a hero actually stands whenever that differs from the site they are filed under — 182 of 906 earmarked people on a size-65 world, all resolving.
- Contract: `Contracts/schemas/npc-roster.schema.json`, `Fixtures/npc-roster-v1.json`, `docs/npc-roster.md`, entries in `docs/README.md` and `Contracts/README.md`. Wiring: `STATE_KEYS` + `_attach_npcs` + two call sites in `terrain_history.py`, `historyStateKeys` in `terrain_lab.html`, a roster panel in `terrain_world.js`, one method in `tests/test_world_schema_conformance.py`, `pyproject.toml`, and provenance revision rows for both lab files. Two now-false "no NPCs are created" claims in `docs/civilizations.md` and `docs/hero-guild.md` scoped.

## Identity

The block is re-derived after every age advance and all three planners rebuild their plans each time, so anything ordinal renames people. City uids are stable and used unchanged; `hamlet-0`, `fortress-0` and `plot-7` are ordinals that renumber, and `humans.cultures` ids rehash. Small sites are therefore anchored on their terrain node and the keys spell the anchor out — `hamlet-node-1062`, not `hamlet-1062` — because the cast builds `hero-castellan-fortress-36` on the *ordinal* id, and two keys reading alike in different number spaces is how a consumer joins the wrong row with no error. Nothing is keyed on a culture id. Ordinal plan ids stay on the records as documented non-identity convenience fields.

## Acceptance evidence

- `Sim/tests/test_npc_roster.py`: 50 tests, 0.1 s, green (post expansion and worker-count identity, unbuildable and partial plans, reconciliation truncate/continue/report, node anchoring and the renumbering test, castle civilization inheritance, null parent race, no culture-id keying, earmark cap and senior-only, hero linkage and `legend -> dead`, presence resolution including the ruin-prefix and unresolvable paths, duplicate display names, name stability, registry snapshot versus live `buildings.json` and every expanded civilization size block, policy lint, pinned fixture, replay byte-identical, isolation, lab wiring, counters present at zero).
- `tests/test_world_schema_conformance.py`: the `npcs` method passed three times on generated seed-42 size-17 worlds (83 s each), most recently against the current tree — block present and schema-valid, hidden before stage 16, every `site_uid` and `hero_uid` resolvable, per-site earmark within cap.
- End-to-end: a generated size-17 world carries `npcs` with `status: ok` — 2,296 people across 26 sites, 131 earmarked, 60 cast-linked, 6 dead — through both the genesis and age-advance paths.
- Scale, measured not estimated (seed 42, size 65): 13,010 people across 347 sites (7,033 city + 2,048 hamlet + 3,605 castle posts + 324 cast), 906 earmarked, 3.26 MB against a 108.9 MB world, generated in 0.3 s.
- `python tools/validate_repo.py --stage checks`: passed, including after the final schema edit.
- Lab verified by rendering rather than inspection (static export, built-in browser): the "The people" panel draws the summary line, reported counts, the collapsible posts-by-site table and per-site cards — "Ylelas — commander · offers defend, slay, reclaim". No console errors from the panel.

## Adversarial review

An adversarial design pass before implementation raised eleven defects. Taken: hamlet/fortress ordinal renumbering (would have silently swapped the identity of 23% of the giver pool every age); hero rows breaking the record's own invariants (`presence` can be absent or point at a camp, ruin, college, port, shrine or nest with no row here); `core_id` being a position in `settlements.sites` rather than a uid, which was silently failing every castle join and naming them all "the fortress"; string plot sort putting `plot-10` before `plot-2`; and the latent size-block staffing override, now visible through the exported registry identity. Rejected: failing the block on a registry-hash mismatch, since the registry revision moves for reasons unrelated to staffing and that would produce constant false failures for other sessions.

Four further defects came from running it rather than reading it: `post_verbs` aliased the cached policy so a consumer mutating the block would corrupt every later roster; every non-city hero was mislabelled `site_kind: city`; two fortresses above one city shared a display name; and the `important` fraction reached 9.4% at size 17 because the uncapped cast dominates a small world, which moved the contract from a percentage to a per-site cap. A fifth came from a consumer compiling against the real block: 182 of 906 earmarked people had a true location in the cast's ordinal namespace that resolved nowhere, and 153 silently fell back to their home city — a real place and the wrong one.

## Limitations and next action

- **The block does not carry its dead forward across an age advance.** Plans rebuild from survivors, so a person whose city is ruined stops appearing rather than turning dead; a consumer must read "uid absent" as gone. This is now load-bearing for another package — the nomads work resolves `refuge_uid` against `sites | ruins` for the same reason. Carded as [NPC-TOMBSTONES](../backlog/NPC-TOMBSTONES.md).
- A site refounded on an abandoned node reuses its key, pointing a quest at the right place with the wrong history. Much smaller than the annual renumbering it replaces, and recorded rather than hidden.
- Posts are the jobs a building needs filled, not a census: dependents, children and the unemployed are absent, as is anyone in a ruin, camp, college or nest.
- The native core does not port this package; like the cast and the story web it runs on the core's JSON output, so a cooked native-only build carries none of the three. That boundary is an ML-03 question and was escalated rather than decided here.
- **Not established here, and deliberately held**: the full `--stage sim-tests` / `--stage repo-tests` runs and a targeted run of the six neighbouring suites. That run was killed 14 minutes in on a fleet-wide instruction to stop long verification while up to eight sessions were generating worlds concurrently — every result from that period measures a moving tree. Handed to the coordinating session with exact commands. It is the one real gap: this change adds three lines to the stage-16 and age-advance tails of `terrain_history.py` and puts `'npcs'` into `STATE_KEYS`, so those suites are what would catch a regression. The package only reads what they produce and a test asserts the source world is untouched, but that is reasoning, not evidence.
