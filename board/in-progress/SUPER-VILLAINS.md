# SUPER-VILLAINS — World-scale antagonists and the hidden schools

Drafted: 2026-09-19. Status: in progress; S0-S8 landed, S9 (the native port) not started. Owner: super-villain session.

This ticket writes the continuation of [PLAN.md](../../PLAN.md) §21, which has been a heading with no body since extraction: *"Villains understand the same system."* PLAN.md flags the gap at lines 117, 427, 678, 766 and 844.

## Requested behavior

The cast the generator already precipitates is uniformly point-scale. Kings, guild masters, Dreads and the player all sit at the same size because structurally they are the same thing: a person attached to a city, named after events that already happened. The user asked for antagonists that operate on a different order — the reference given was Arthas, Illidan and Gul'dan, who are not simply stronger kings.

Specific requirements as stated:

- Fewer super villains than minor villains, and **existing heroes can become them** when their influence expands to devastating reach.
- Super villains are full simulation citizens: they cause wars and city fates rather than being named after them.
- Four **hidden magic schools** — Blood, Void, Rot, Eldritch — with four gods at the scale of Warhammer's Chaos gods. Exceedingly rare; a player may never meet them, or never meet them all.
- The hidden gods **wait for a player**. They transcend world creation and are only truly after corrupting the player, so generation never enables them.
- Reversible with a caveat: killing the villain does not cleanse the land. As long as corrupted nodes exist, new villains take their place. Cleansing requires overpowering the node with a built structure, and it takes time.
- The known gods know the hidden four and do not speak of them for fear of their return. Should one return, the likelihood a known god intervenes rises sharply — possibly into open conflict, where a war god seeks to annihilate the world and the player may help or oppose it.
- Cross-playthrough escalation: the game keeps a count of villains killed and passes it in, so by playthrough five the gods know the player and are hunting them.

## Proposed mechanism

### Two tiers

**Tier 1 — super villains.** Rise during generation from recorded history, using the eight known schools. Tier is **reach**, continuous: an ordinary cast member is a point, a villain covers a city or realm, a super villain spans cultural regions. Reach in metres with falloff is already how this world expresses scale.

**Tier 2 — the corrupted.** A hidden god seats an existing super villain as its instrument. Impossible during generation. Delivered as a runtime request API modelled on `terrain_visitation`, which is Python-only and never ported, so this tier costs no native parity work.

### Volume and pacing

Turmoil is one budget with two uses. Diffuse turmoil makes minor villains, which `hero_generator` already does continuously (~54 living on a seed-42 world). Concentrated turmoil raises tier: high in one contiguous region, sustained across more than one age. `threat_assessments` v3 already computes the field, so nothing new measures it.

- **The ramp is the pacing.** A villain crossing the threshold is a threat that is *growing*, not one that has arrived. Peace after a kill comes from the successor being weak, not from a cooldown; no respite mechanic is needed.
- **Ceiling scales with the world** — one per cultural region, read from `humans.cultures` and `civilization_region`.
- **Hysteresis** — the rise threshold sits above the stay threshold, so a reign is long once established. When the count at threshold equals the ceiling, pretenders stall just beneath it.
- **No floor.** Some worlds never produce one.
- **Killing one releases the concentration**: the region fragments into minor villains squabbling over the corpse.

### Archetypes

No new archetype catalogue. A super villain keeps the card it precipitated with from `archetypes.json` and each of the 32 gains an **escalation**: what that archetype becomes with unbounded reach. Escalation maps many-to-one onto six **growth functions** — Devouring, Brokering, Seated, Hoarding, Spreading, Usurping — which determine how reach expands and therefore how the villain is fought.

Direction of dependency is easy to get backwards: `hero_generator` runs after the sim and never writes back, but reach grows during ages. So the **sim owns a `growth` field** derived from the villain's own features, and `hero_generator` picks its escalation card from those same features. One direction, no circularity.

### The four hidden schools

Appended to `SCHOOLS` at indices 8-11, never inserted, because `dominant_magic` exports an index into it and `biome_variant` an index into a catalogue built in that order.

| School | Identity | Feeds on | Propagation | Creatures | City failure mode |
|---|---|---|---|---|---|
| Blood | vampirism, body horror, mutants | population density | Gaussian scaled by the living in reach | new `blood` family | population falls, city stands — it is farmed |
| Rot | disease and undeath; a true zombie apocalypse, not summoned undead | itself — fecund, contagious | cell-to-cell relaxation over the sphere graph | **none** — converts population | the city's own dead become the threat |
| Eldritch | tentacles, psychological horror, mind control | aberrant nests and ruins | Gaussian, seeded by what the world already fears | escalates existing `aberrant` | the city stands intact and is *taken* |
| Void | an immense unknowable entity; void ghosts, entropy | absence | **subtractive** — suppresses neighbours toward zero | new `void` family | city and ground unmade, ley included |

Occurrence is locked with `spec(0., 0., 0., ...)` so `validate_options` rejects any nonzero override; the precedent is `sky_occurrence`. Generation can never enable them.

Eldritch escalating `aberrant` rather than inventing a family is deliberate continuity: `god_outer_unnamed` ("The Unnamed Outside", madness and forbidden knowledge, worshipped by nobody) is already `fear_gods['aberrant']`. The world already fears aberrants and does not know why.

### The mutated land

52 authored variants — 13 cores x 4 hidden schools — at indices 104-155, with real names, colours and descriptors like the existing 104. Note that `terrain_profiles.biome_preference` falls back to the core biome for unknown variant ids, so `grassland.rot` reads exactly like `grassland` to settlement placement until `civilizations.json`'s `magic_biome_preferences` learn all 52.

### The loop

The **corrupted ley node is the persistent entity, not the villain**. A god seats a holder on one or more nodes; killing the holder leaves the nodes; an unheld node is a spawner that later seats a new holder; cleansing requires a counter-structure that ramps *and drains* until the node is gone.

### The known gods, and the scouring

Before a return there is no trace of the hidden four anywhere in any export — that is the data expression of not speaking. After one returns: aspects flip Wild through the existing `wild_push_families` path, `rivals` gain the returned god, and visitation odds rise sharply.

`ASPECT_FACTOR = {'wild': 2., 'sovereign': .5}` already means a Wild god destroys four times as much as a Sovereign one, so corruption pushing the pantheon Wild makes it an extinction event **through constants that already ship**. Above a corruption share a visitation enters a **scouring** variant: `wrath` forced to 1.0, no `REACH_SPACINGS` bound, and `_faith_factor` no longer sparing the god's own faithful. Likeliest annihilators are `god_red_field` (the one civic god that never folds into a saint) and `god_radiant`.

Opposing a god reuses what exists: an avatar is a ley cluster, not a creature, so cleansing it *is* cleansing nodes, and the effect is an early `depart_god`. `MAX_VISITATIONS = 8` stays — the pantheon can answer eight times, then it is on the player.

### Cross-playthrough escalation

The game owns the ledger and passes it in; the generator stays stateless. `encounters` takes its **own parameter and its own seed domain**, not an overload of `variation`, which already means "reroll this request differently" and is recorded as such:

```
child_seed(seed, f'corruption-{index}-{god_id}-escalation', encounters)
child_seed(seed, f'corruption-{index}-{god_id}', variation)
```

It must be monotone in effect, a no-op at zero, and recorded in **both** the corruption record and `history.operations`, or `history.replay` becomes false.

The gate is a threshold then a climb: below a god's noticing point the chance is *exactly zero*, asserted rather than tuned. Each god has its own noticing point, so they arrive staggered. **The counter says whether; the world says which** — Blood where population is dense, Rot where decay has set in, Eldritch where aberrant nests cluster, Void where magic has gone dead — read through the existing `rule_holds` evaluator, never rolled.

## Dependencies and unresolved decisions

- God names are placeholders pending sign-off: The Long Thirst (Blood), The Glad Mother (Rot), The Shape Beneath (Eldritch), The Unwriting (Void).
- The cleansing structure needs an original name. [PLAN.md:634](../../PLAN.md) already states the Sunwell comparison "supplies no borrowed lore, artwork or final naming."
- `magic.groups` grows from 3 to 4 (the hidden four want their own group), which trips `test_terrain_history.py` asserting `len(groups) == 3`.
- Hidden gods live in a separate `hidden_pantheon.json` with its own identity so `catalogue_identity()` never moves and saved worlds keep validating; they are still appended to the exported `religion.gods` as `status: absent`, because hiding them is the game's job.
- S9's native parity at nonzero `villain_rise` needs `Core/tests/world_driver.cpp` to accept option overrides, which is unscoped.
- The lab carries two hardcoded eight-school lists — `layerInfo` in `tools/terrain_lab.html:56` and the `colors` map behind `rgbFor` in `tools/terrain_world.js:238` — but neither breaks: `terrain_world.js:247` back-fills `layerInfo` from the world's actual layers, and `rgbFor` falls through to a default colour. Since a generated world's hidden fields are identically zero there is nothing to see, so both pinned files were left alone. **S7 must revisit this**: once corruption produces non-zero hidden fields, `rgbFor` should read `magic.networks[school].color`, which already carries the authored colour, rather than a hardcoded map.

## Files and assets in scope

Landed: `Sim/icarus_sim/terrain_history.py`, `terrain_visitation.py`, `terrain_leyline_history.py`, `terrain_biome_catalogue.py`, `terrain_astrology.py`, `terrain_religion.py`.

Planned: `terrain_world.py` (provenance-pinned — needs a revision row), `terrain_nest_profiles.json`, `civilizations.json`, `terrain_corruption.py` (new), `hidden_pantheon.json` (new), `Contracts/schemas/world-output.schema.json`, `age-advance-request.schema.json`, `corruption-request.schema.json` (new), `Contracts/catalogues/unreal-asset-registry-v1.json`, `Core/settlements.cpp` (bounds guard), `Core/config.hpp` (mirror), `Sim/hero_generator/policies/archetypes.json`, `Sim/story_web/policies/tropes.json`.

## Acceptance and evidence

**S0 — shared rebuild tail.** `terrain_visitation._rebuild` and `terrain_history.age_transition` ran the same tail twice with three silent divergences: a `magic_enabled` guard, a `spacing` argument that reached the same value by a different path, and where `add_religion` sat. Extracted to `rebuild_tail(result, cfg, survivors, label, age, *, evaluate=True, religion=True)`.

This was sequenced first on the assumption that `tests/test_native_world.py::test_the_finished_world_matches_the_reference` was an independent C++ oracle for this tail, and that the proof would disappear once a third caller existed. **That assumption was wrong: the native suite is already red on this tree** (see below). The rationale did not survive contact, though the extraction is still worth having on its own merits.

Evidence: `test_visitation` 6/6 green including `test_same_request_same_world_and_input_untouched`; `test_terrain_history` 11/11 green including `test_versioned_pipeline_and_replay` and `test_api_player_key_point_and_invalid_requests`.

**S1 — `KNOWN_SCHOOLS` seam.** `KNOWN_SCHOOLS` and an empty `HIDDEN_SCHOOLS` merge into `SCHOOLS`, so `SCHOOLS == KNOWN_SCHOOLS` and the slice is a provable no-op. All 32 `SCHOOLS` references audited and classified. Stays eight forever: all of `terrain_astrology` (the moon is this world's own; `REGIONS` is built at import and would `KeyError`), all of `terrain_religion` (the known pantheon), god affinities, and player leyline edits at `terrain_history.py:653` — otherwise a caller could hand-place a Blood node at an age boundary with no god involved. Sees every school: biome variants, city fate potencies, the divine lottery, ruin causes.

One consequence worth recording: `city_potencies` indexes the lunar tide dict, which is keyed by the known eight. Hidden schools therefore receive potency but **no lunar sway**, which is both the guard the code needed and correct — alien magic does not answer to this world's moon.

**S2 — biome catalogue restructure.** Two blocks through one `_entry()` helper so key insertion order, which the output bytes depend on, cannot drift. Verified byte-identical to the pre-slice formula: 104 entries, identical per-entry key order, identical JSON bytes.

**S3 — the four hidden schools.** Blood, Void, Rot and Eldritch appended at indices 8-11 under a new `Outside` group; 52 authored variants at catalogue positions 104-155; `HIDDEN_NETWORKS` in the option table with occurrence locked at `min == max == 0`; `history.version` 2 -> 3 with an honest retirement message; schema pins moved (`biome_variant` max 103 -> 155, `magical_biomes` 104 -> 156, `magic_school` enum +4); asset registry regenerated 1441 -> 1493 bindings, the 52 new rows all `terrain.mutation.*.{blood,void,rot,eldritch}`; a bounds guard in `Core/settlements.cpp` where `school_names()[dominant_magic[z][x]]` would otherwise read past an eight-entry array for a corrupted world; provenance revisions for the three pinned files touched.

Proven by a structural before/after comparison across **four** seeds — 42/73/108 at size 17 and 42 at size 33, where `PARITY_SEED` only ever covered one. Generation is byte-reproducible across identical runs, which is what makes the comparison a gate. On every seed: all 156 pre-existing layers identical, the eight new hidden fields identically zero, and `settlements`, `ruins`, `roads`, `humans`, `beast_nests`, `threat_assessments`, `religion`, `astrology`, `lunar_almanac`, `civilizations`, `world_scene` and `history.ages` unchanged. The first 104 catalogue entries are byte-identical, so every recorded `biome_variant` index still means what it meant.

Three blocks changed in ways worth naming rather than allowlisting. The planners embed a copy of the magical catalogue and a per-school colour map, so `city_plans`, `hamlet_plans` and `castle_plans` grow; with those two carried fields set aside, every plot, street, wall and anchor is identical. `debug_stats.leylines` goes 8 -> 12.

Two real defects surfaced that the S1 audit had missed, both of the same shape — code iterating `magic.networks` rather than `SCHOOLS`, then indexing the lunar tide: `lunar_request`'s `surged_strength` map and `refresh_astrology`'s per-network `surged_strength`. Both now skip schools the moon never charted, which is the same rule `city_potencies` already follows. Nothing in the schemas, the lab or the Unreal consumer requires the field, so its absence is safe and is the honest representation.

**S4 — hidden-school mechanics.** Blood multiplies its draw by the living in reach; Eldritch by aberrant and undead nests and by ruins; Rot creeps cell to cell; Void subtracts from every other school. Feeds are applied to the total *before* saturation, so a well-fed field still tops out at the network's strength. Every mechanic is skipped entirely when its network has no node, which is what makes the slice byte-neutral rather than merely arithmetically neutral. `terrain_profiles.biome_preference` and `biome_food_multiplier` now return -1.0 and 0.0 for any hidden variant — a rule, not 52 authored opinions per people, because nobody has a cultural preference about a school they have never heard of.

Both design-review findings hold in code and are pinned by tests. Rot's creep is measured in metres per graph edge, not in cells, so a 17-grid and a 33-grid world rot at the same physical rate — `test_rot_creeps_at_the_same_physical_rate_on_a_finer_grid` asserts within 35%. Void skips where it is absent rather than subtracting a zero, because `max(0., -0.)` returns positive zero and would move every magic-disabled world's bytes. Seven tests in `Sim/tests/test_hidden_schools.py`, all green.

**S4b — hidden bestiary.** 25 creatures: ten blood, ten void, five eldritch-gated aberrants, tiers 1-5, each requiring a hidden school's potency at a tier-scaled threshold. Rot deliberately gets no family. Asset registry 1493 -> 1518. Proven: all 300 placed nests in the gate world are identical, the exported monster catalogue grew by exactly 25, and every one of the 25 reports `placed: 0`.

**S5 — Tier 1 super villains.** `Sim/icarus_sim/terrain_villains.py`: tier as continuous reach, concentration read from `threat_assessments` v3, a `ceil(regions / villain_density)` ceiling with pretenders stalling at 0.999, a hysteresis band, fragmentation on a fall, a cause appended to `city_fate`'s lottery, a `villain_school` branch in `ruin_legacy`, and a `villain_outlook` export beside `war_outlook`. Three options all defaulting to a world that raises none. `Core/config.hpp` carries all three with the three-clause honest comment.

**A real bug found by exercising it rather than by testing the no-op.** Tier was first keyed to a `humans.cultures` id — but a culture's id is rebuilt every age from whatever the roads join, so accumulation silently reset and produced 26 orphaned keys for nine regions; nothing could ever reach the band. Re-keyed to the nearest **ley node**, which persists and is only ever appended to, with the seat city's uid as the fallback where a world has no magic. Keys 26 -> 12, and a villain now rises: tier 1.198, reach 38.7 km, growth `hoarding`, anchored to `earth-node-4`, and one city falls to it. This is the same churn class the plan flagged for cities, one level up.

Eleven tests in `Sim/tests/test_super_villains.py`, including that a default world carries no `villains` block at all and that no tier key is ever a culture id.

**Cumulative gate**: S3+S4+S4b+S5 pass the structural comparison on all four seeds at defaults. The only movement from the pre-S3 baseline is 27 new option keys in `recipe.resolved` (24 hidden-school, 3 villain), which is unavoidable for any new option.

**S7 — the corruption API.** `Sim/icarus_sim/terrain_corruption.py` plus `hidden_pantheon.json`. The four hidden gods live in their own file with their own identity, so `catalogue_identity()` never moves and saved worlds keep validating; they are still exported in `religion.gods` as `family: outside`, `status: absent`. The gate is a threshold then a climb, asserted exactly zero below each god's noticing point rather than tuned small, with the four staggered at 3/6/10/15. Identity is read from world state through the existing `rule_holds` evaluator plus a numeric interest score, never rolled. `encounters` is its own uint32 parameter with its own seed domain and is recorded in both the corruption record and `history.operations`.

Four failure modes, unit-tested apart: Blood farms a city that still stands, Eldritch takes one and changes nothing visible, Rot and Void end one with distinct causes. A revealed god goes `walking` with its Wild aspect and rouses its rivals in the known pantheon, which is what makes the cure able to exceed the disease — `ASPECT_FACTOR` already gives a Wild god four times a Sovereign one's destruction.

**Two bugs this slice found in itself.** `add_religion` rebuilds the religion block and carried only `visitations` forward, so the corruption ledger was discarded on the rebuild that follows every corruption; it now carries `corruptions` the same way. And the hidden schools' `strength` defaulted to 0.7, the same as the known eight — at which a corrupted cell measured 0.700 against a radiant field's 0.679 and could not clear `dominant_school`'s 0.08 margin, so **corrupted ground never actually mutated**. That is finding ① in a second guise. Hidden strength is now 1.15, and a test asserts corrupted ground wears the hidden school.

The corruption's reach follows the villain's own rather than a constant, which also fixed a case the first version got wrong: a villain whose seat city has since fallen still sits where its node is, and the nearest survivor can be further away than any fixed reach would carry.

**S8 — cleansing, and opposing a god.** One mechanic, two names. The structure **drains as it ramps** rather than out-competing, because out-competing cannot work. Driven at power 0.3 it takes four ticks; corrupted ground reverts, the holder is unseated, the god returns to sleeping, and the field goes back to negative zero so a cleansed world is not distinguishable from one never corrupted. Opposing a walking god routes to an early `depart_god`.

**A latent corruption fixed on the way.** `depart_god` removed cluster nodes by list filter without reindexing `edges[].from`/`.to`. It was safe only because avatar nodes carry no edges — and S5b's wells do. Endpoints are now remapped, and `_drain` asserts a corrupted cluster carries no edge before removing one.

**S5b — wells and claims.** A seated villain binds to a god: a new one if corruption took it, otherwise the school god of the ground it holds, which is what "old or new" means. A god-bound villain sinks a **leyline well** — a high-intensity node *joined by edges* to its other holdings, because the edges are what re-route the tracks a lone key point cannot. It also claims ground, recorded with a **mixed faction list** drawn from the peoples nearest it.

**Scoped honestly:** claims are recorded as the villain's intent, not injected into `settlements.sites`. `add_settlements` places by suitability and only inherits identity from a survivor already at that node, so a site pushed into the survivor list is simply not placed. Founding real cities means changing placement, which is a settlement-model change and not a tail on this ticket. The claim is what an orchestrator reads until then.

**S6 — villain contention.** A villain whose reach covers both cities of a pair presses them together, so its presence reaches `war_outlook`, `threat_assessments` and through `defense_priority` the thickness of city walls. Threaded through `contested_pairs`, `war_outlook` and `resolve_wars`, defaulting to an empty cast.

**What the full suite caught that per-module runs did not.** Ten failures across 140 tests. Two were pre-existing and proven so against the untouched baseline copy, which fails identically: `test_population_scales_with_the_ground` (13751/14849 over area 3.0) and `test_pyramid_and_overlap` (204 not greater than 301). The first is on *wildlife* — animals, of which this work added none.

The other eight were this work's, and three were worth the run on their own:

- **`villains` was missing from `historyStateKeys` in `tools/terrain_lab.html`.** The plan warned about exactly this and it was still missed. The failure is silent rather than loud: `materialize_stage` starts from everything *not* in that list, so the lab's stage scrubber would have shown the final cast at every earlier stage.
- **The schema's `magicalBiome.id` enum still listed 104 variants.** S3 raised `magic_school` and the count pins but not the id enum, so no generated world satisfied the published schema.
- **`_key_point_school` silently returned `None` on a partial layer set.** It wraps a twelve-school lookup in `try/except KeyError`, so a hand-built world carrying only the eight known ley layers lost the key point a magically charged city is owed when it falls. Missing now reads as zero potency.

The rest: 25 creatures described in `docs/catalogue/creatures.json`, the asset-list creature count 638 -> 663, native catalogues regenerated, and the astrology pipeline taught that a hidden school carries no lunar surge.

**A process failure worth recording, because it happened twice.** `pathlib.write_text` on Windows converted both `provenance/extraction-manifest.json` (2130 lines) and `Contracts/schemas/world-output.schema.json` (979 lines) wholesale from LF to CRLF. `.gitattributes` states the provenance hashes were recorded from the LF originals. Both were caught by diffing against a pre-change snapshot rather than by any test, and both were redone with `write_bytes`; the schema diff went from 2084 changed lines to 66. Take the snapshot before starting, and do not use `write_text` on these files.

**Native parity is red at baseline, and it is not this work.** `tests/test_native_world.py` fails 89 / errors 4 on the current tree. A scratch copy with this session's six files reverted through asserted anchors fails **identically**: 89 failures, 4 errors, and the two runs' collected `FAIL:`/`ERROR:` lines are byte-for-byte the same set, 93 lines each. Thirty-six of those are `test_native_world_reproduces_the_reference_world_for_one_seed`, the genesis comparison over stages 1-8, which nothing in S0, S1 or S2 can reach: S0 is confined to the age-transition tail and S1/S2 are provable no-ops. The headline divergence is `test_the_finished_world_matches_the_reference` asserting `14 != 40` cities, the native side producing fourteen where the reference produces forty.

This is consistent with native work in flight rather than a regression: `Core/ages.cpp` (+47/-8), `world.cpp`, `layers.cpp/hpp`, `config.hpp`, `ruins.hpp`, `scene.cpp/hpp` and `world_driver.cpp` are all modified and uncommitted, `Core/astrology.cpp`, `astrology.hpp`, `legacy.cpp` and `legacy.hpp` are untracked, `tests/test_native_world.py` is itself modified, and `Core/README.md:42` currently reads "Settlements, roads, city plans and nest anchors are not ported yet."

**The replacement gate for S3, captured before it starts.** `python -m fantasy_world_generator generate` is byte-reproducible across two runs with identical arguments, so a before/after comparison is a real gate. Pre-S3 worlds are recorded at seeds 42/73/108 size 17 and seed 42 size 33; their sha256 prefixes are `881bb3c7eaf8b516`, `3b9d161cf0c86a1c`, `f7ce7f104d2ca34f` and `2083fecf556c2092`. Appending four schools at zero occurrence must leave all four unchanged. Note this covers more seeds than `PARITY_SEED=42, PARITY_SIZE=33` ever did.

**Consequence for S3, which must be resolved before it starts.** S3's stated acceptance was that the native suite "stays fully green unchanged" — that being the load-bearing check that appending four schools moves no field. A suite that is red before and after cannot distinguish "the hidden schools changed nothing" from "the hidden schools broke something." S3 needs a different primary gate: a direct byte comparison of a generated world before and after the append, which the plan listed only as a secondary check. Either the native port lands first, or S3 proves itself against the Python reference alone and says so plainly.

## Documentation impact

`PLAN.md` §21 continuation; `docs/super-villains.md` and `docs/hidden-schools.md` (new) with entries in `docs/README.md`; `docs/terrain-world-layers.md` for `history.version` 3 and the twelve-school contract.

## Adversarial review and limitations

Three findings from design review that the code contradicted, all resolved before implementation:

1. **Cleansing by out-competing is mathematically impossible.** Potency is `strength * -expm1(-total)` and saturates at `strength`; intensity caps at 4.0. With both schools at `strength = 0.7` and a corrupted node at 4.0, corrupted potency is 0.687, the counter needs 0.767 to win by `dominant_school`'s 0.08 margin, and its ceiling is 0.700. No number of counter-nodes flips it, and falloff means cleansing pushes the boundary inward in a ring but never takes the node's own cell. **Resolution:** the counter-structure *drains* the node as it ramps, removing it at zero. This is what "fully overpower" describes, preserves the time element, and keeps the hidden schools strong — which lowering their strength to 0.62 would not.
2. **Rot's contagious spread breaks scale invariance.** N relaxation iterations cover N cells and cell size scales with `cfg.size`, so a 33-grid and a 257-grid world would rot at different physical speeds. Every distance here is a ratio of settlement spacing or a rescaled metre. Derive the iteration count from a physical distance over the mean cell arc.
3. **Void's clamp is a byte trap.** `x - 0.0` is bit-exact for all finite `x`, but `max(0., -0.0)` returns `0.0`, flipping the sign bit a magic-disabled world writes into every `ley_*` layer. Void must be a post-pass and must not clamp unconditionally.

Known limitations: appending four schools **retires every saved world** at `terrain_history.py:554` (`Expected exactly eight networks`) — unavoidable, so it is done once deliberately with `history.version` bumped in the same slice. `PARITY_SEED=42, PARITY_SIZE=33` proves one seed did not move, not that no seed moved; diff `tools/export_showcase.py` across seeds 42/73/108 by hand. `Core/settlements.cpp:214` indexes `school_names()[dominant_magic[z][x]]` without a bounds check. Blood and Eldritch read one rebuild behind, since `evaluate_networks` runs before `civilization()` and `add_nests` in both rebuild paths.

## Added scope: founding and leyline wells (S5b)

Requested after S5 landed, close to verbatim: super villains "found new cities and villages. They can be mixed race/faction, and if the villain is tied to a god old or new, they will build a leyline well (think the sunwell in world of warcraft), which will modify the leyline tracks."

Two pieces, neither built yet:

- **Founding.** A villain seats new settlements near its held nodes. `population_profile` is currently a single value per city, so mixed race/faction is a genuine data-model change rather than a placement change — that is the part to design first, not the placement.
- **The leyline well.** A structure that reshapes the network rather than adding a point to it. Mechanically this is the S8 cleansing structure used offensively: one primitive, two directions, so it should be built once and exposed twice. Everything goes through `edit_network`, which is validated at the age boundary and budgeted at 1024 nodes and 4096 edges per network.

  **If a well adds edges, `terrain_visitation.depart_god` must be fixed first.** It removes cluster nodes by list filter and does not reindex `edges[].from`/`.to`; it is safe today only because avatar nodes carry no edges. A well that adds edges makes that a live corruption.

Naming: [PLAN.md:634](../../PLAN.md) already states the Sunwell comparison "supplies no borrowed lore, artwork or final naming", so the structure needs an original name.

Coordination: a parallel session is planning NOMADS in this tree and the user wants villain-spawned cultist bands. Agreed seam is theirs — nomads carry `origin: {kind, id, age}`, a villain calls `nomad_request` with `kind: 'villain'`, and neither package imports the other's internals.

## Handoff

Slice order: {S0, S1, S2} in parallel, then S3 (the retiring slice), then {S4, S4b, S5} in parallel, then {S6, S7}, then S8, then S9. S5 is independent of the schools track and needs only the `terrain_world.py` provenance row sequenced against S3. Full design and per-slice detail in the session plan file.
