# HERO-GENERATOR — Larger-than-life cast precipitated from world history

## Requested behavior

The user wants "larger than life" characters at the core of the game: monsters give guilds, cities and kingdoms give politicians, turmoil gives villains. Characters carry an archetype (Conqueror, Exiled Hero, Oathbound, … plus roped-in tropes) that is separate from their role, sit on the lawful-good → chaotic-evil grid, and the alignment must mutate the archetype's personality. The generator must be a wholly separate block from the world generator, called when generation finishes with the world and its story so far, changeable without bricking the generator. The lab page reports the generated people: race, name, alignment, archetype, position. North-star scenario (later slice): a captive at a bandit camp who is really a necromancer, joins the player, and hands out quests that weaken opposing leyline nodes unwittingly.

Full theory and slices: the approved plan at `~/.claude/plans/want-to-start-looking-atomic-swan.md` (2026-09-18/19).

## Proposed mechanism

Characters are precipitated from recorded events, never rolled from templates: a ruin may leave an heir, a war a remembered victor, a beast kill a named Dread. Each candidate rolls once (seeded per uid) against `policies/wells.json`, and every roll is exported in `heroes.rolls`. Nothing is planned for anyone: each person carries an event log (one entry per recorded event with its id) and a present situation; the orchestrator improvises arcs on the fly. `Sim/hero_generator/` reads the world JSON only, derives alignment from civilization bias and deeds, chooses an archetype whose data-driven preconditions the person's own record satisfies (priors weight, nothing clamps), composes a persona from an alignment-neutral card plus shared axis overlays, and exports `heroes`. One call site in `terrain_history._attach_heroes`, behind `FANTASY_WORLD_HEROES`, that reports failure as a block instead of raising.

## Dependencies and unresolved decisions

- Slice 1 (this ticket): ruins well (Pretender, Warlord, Dread), realms from culture groups, alignment, full archetype catalogue with personas, bonds, facts, mantles, schema, docs, lab panel.
- Slice 2 (done 2026-09-19): magic well (key-point wardens, surviving college masters, college heads), camps squatting ruins (failed foundings carry no location), relics, placement of the dispossessed, companion eligibility, faces per card, quest hooks with stated-vs-actual divergence. No pre-planned arcs and no scripted necromancer: that scenario is an illustration of what the data allows.
- Slice 3 (done 2026-09-19): cities well (sovereigns, dynasties, councils by seat, prophets/heresiarchs/exiles/founders from the diaspora record), guilds well (orders and champions against dangerous nests, remnants and failed champions), cross-cutting features, seated-first archetype pass so Tyrants make Rebels; every archetype can now fire.
- Decided: the enable switch is an environment variable, not a recipe parameter, so the world's recipe/replay identity and native parity stay untouched.
- Open: fame calibration is provisional; a capital taken in an international war is legendary by construction.

## Sources consulted

`PLAN.md` §11/13/17/21 (rulers, knowledge, villains heading only), `docs/hero-guild.md` (additive non-mutating precedent), `terrain_history.py` (age transitions, ruins, STATE_KEYS), `terrain_wars.py` (war records), `terrain_nests.py` / `fantasy_nest_threats` (dread evidence), `terrain_humans.py` (cultures), `tools/terrain_world.js` (lab cards and pins).

## Files and assets in scope

`Sim/hero_generator/**` (new), `Sim/tests/test_hero_generator.py` (new), `Contracts/schemas/hero-generator.schema.json` (new), `docs/hero-generator.md` (new), `docs/README.md`, `Sim/icarus_sim/terrain_history.py` (STATE_KEYS + helper + two call lines), `tools/terrain_world.js`, `tools/terrain_lab.html` (`historyStateKeys`), `tests/test_world_schema_conformance.py` (heroes conformance on the existing generated world), `pyproject.toml` (package inclusion). No asset identities.

## Acceptance and evidence

- Hand-built fixture world: expected roles, deed ids, homes, claims, bonds, mantles, realm names, and every precipitation roll (chance, draw, outcome).
- Replay byte-identical; source world untouched; JSON finite.
- Fame monotonic in fallen class and nest tier.
- Every archetype composes nine distinct personas across the grid and rejects no cell; catalogue names only known features.
- Seed helper equals `icarus_sim.terrain_tectonics.child_seed`; package source never mentions `icarus_sim`.
- `attach` returns a failed block on a bad world and `None` when switched off.
- Generated world (conformance suite): `heroes` present, validates against the schema, hidden before stage 16 by `materialize_stage`.
- Lab: cast panel renders, pins drawn, hover names people (built-in browser screenshot beside the JSON).

## Documentation impact

`docs/hero-generator.md` (new), `docs/README.md` entry, this ticket.

## Adversarial review and limitations

Only the ruins well exists; sovereigns, champions, magisters, camps, faces and quest hooks are documented but unreachable. Claims are intent, not behaviour. Names are syllable draws. The C++ core does not port this; it is a consumer of JSON. A `heroes` block in `STATE_KEYS` enlarges `build_stages` by one snapshot state entry.

## Evidence — 2026-09-19 (slice 1)

- `Sim/tests/test_hero_generator.py`: 15 tests, 0.04 s, green (wells, replay, fixture, fame monotonicity, sign-preserving jitter, nine-cell persona distinctness for every card, catalogue lint, seed parity with `icarus_sim`, `attach` failure block and switch, no `icarus_sim` import).
- `tests/test_world_schema_conformance.py`: green with the new `heroes` check on the shared seed-42 size-17 world (block valid against `Contracts/schemas/hero-generator.schema.json`, every deed id resolves to a real ruin or war, absent at stage 15, present at stage 16).
- Real world, seed 42 size 17: 25 people (17 living, 8 legends), 0 dreads (no beast ruins in that seed), 9 realms, 13 bonds, 4 mantles; generate 70 s, one age advance 46 s regenerates the cast (11 living, 21 legends).
- `tools/verify_provenance.py` passes after revision rows for `tools/terrain_lab.html` and `tools/terrain_world.js`.
- Lab (built-in browser, `python tools/terrain_lab.py --serve --port 8765 --size 17 --phase 1`, then Generate random world at 16×16): "The cast" panel renders 36 cards for a 30-living / 6-legend world, with civilization, race, role, archetype, alignment, fame tier, position, Deeds and bonds, Persona (belief, manner, voice, tells, lies, cornered, never, sample line) and Truth details; diamond pins on the atlas at living people's cities; hover readout names them with archetype and alignment. Verified after a page reload, i.e. from the patched file, not a live DOM edit.
- `python tools/validate_repo.py`: checks, repo tests and artifacts green; the sim suite reported three failures in `test_terrain_nests`, `test_terrain_world_layers` and `test_visitation`, none touching this package. Files behind them (`terrain_visitation.py`, `test_terrain_nests.py`) were modified by concurrent sessions while the 64-minute run was in progress; on rerun the world-layers and visitation tests pass and the nests failure reports different numbers, so it tracks the in-flight wildlife work, not this change.

## Evidence — 2026-09-19 (slice 2)

- `Sim/tests/test_hero_generator.py`: 24 tests green (adds magic well, camps and placement, relics, faces, hooks, companions, precipitation ledger).
- `tests/test_world_schema_conformance.py`: green against the slice-2 schema (camp directions had to be exported as lists; the live world carries tuples).
- Saved seed-42 world: 31 of 53 candidates precipitated, 5 wardens at key points, 7 camps, 28 honest hooks; no dark-school magister in that seed, so no two-faced person, which is the point: nothing is forced.
- Lab (random world, 16×16): 52 of 91 candidates, 34 living, 13 camps, 57 hooks; warden card shows school, log, claim, rival, asks, honest hook effects in Truth; camps and relics summary lines; pins resolve ruin/camp/college presences.
- Fast checks stage and provenance green.

## Evidence — 2026-09-19 (slice 3)

- `Sim/tests/test_hero_generator.py`: 28 tests green (adds realms/sovereigns/dynasties, council seats and orgs, champions and orders/remnants, diaspora leaders, refounded-heir redemption, seated-first Tyrant → Rebel, tainted ground and mentor bonds).
- `tests/test_world_schema_conformance.py`: green against the slice-3 schema (orgs, new roles and wells, `nest`/`founding` event kinds).
- Saved seed-42 world: 57 of 103 candidates precipitated, 50 people across 5 roles and 16 archetypes (sovereigns split across Conqueror, Incarnate and the moral poles; councils across Mastermind, Forgiving, Trickster, Kingmaker, Corrupt), 8 orgs, 7 camps, 38 hooks; validates.
- Lab (random world, 16×16): 71 of 120 candidates, 64 living, 13 orgs, 70 hooks; sovereign and council cards render with seat, allies, log and truth; orgs, camps and relics summary lines.
- Provenance and fast checks green. Full `python tools/validate_repo.py` (70 min): checks, repo tests and artifacts green; sim suite 363 tests with 2 failures, both in `test_terrain_nests` (`test_population_scales_with_the_ground`, `test_pyramid_and_overlap`), the wildlife work another session is editing (its test file changed mid-session); they fail identically with `FANTASY_WORLD_HEROES=0`, so they are independent of this package.

## Handoff

Slices 1–3 complete: four wells (ruins, magic, cities, guilds) with probabilistic precipitation and a roll ledger, realms and orgs, camps and relics, placement, faces, quest hooks, cross-cutting features, alignment-then-archetype with every card reachable, personas per face, bonds, event logs and situations, mantles, schema, fixture, docs, lab panel. Deviation from the plan: the enable switch is the `FANTASY_WORLD_HEROES` environment variable, not a recipe parameter, to keep recipe and native parity untouched. Next concrete actions: calibrate precipitation and fame on larger worlds (colleges only appear at size 33+), read council seats from placed rosters once `city_plans` exports them, and the feedback interface (`accept_event`) once the runtime kernel exists. Arcs stay with the orchestrator.

## Slice 4 - countryside, ports and shrines wells (2026-09-19, story-web session)

Requested after the story-web calibration showed heroes were city-bound (38 of 43 living heroes in 9 cities on seed 42) while 13 hamlets, 4 fortresses, 6 ports and 13 shrines precipitated nobody. Added `wells/countryside.py` (reeves, castellans), `wells/ports.py` (harbourmasters) and `wells/shrines.py` (keepers, cult heresiarchs) with precipitation rules in `policies/wells.json` (revision 4), epithets in `policies/names.json` (revision 4), archetype entry points in `policies/archetypes.json` (revision 4: Reluctant Hero, Oathbound, Obsessed Hunter and Zealot accept the new roles), feature vocabulary in `archetypes.py`, log/situation/hook/fame branches, schema enums (roles, wells, event kinds, site kinds, roll kinds, hook effect kinds), the lab site lookup, and the conformance test's deed-id map. Evidence: `Sim/tests/test_hero_countryside.py` (5 tests on the hand-built world with hamlets, a fortress, a port, a shrine and a cult added: roles, facts, claims, names, logs, hooks, schema validity, replay, silence without sites, precipitation reading the site, and the story web weaving them). Seed 42 (saved export, cast regenerated): 56 living, 13 from the new wells (3 reeves, 1 castellan, 4 harbourmasters, 5 keepers); The Skim, The Founding and The Vow now fire. `Fixtures/hero-generator-v1.json` only moved its policy revisions: the hand-built world has none of these sites.

Later the same day (Siege density follow-up): wells revision 5 lowers the warlord base to 0.25 and adds `one_per_city`, so only a city's most recent victor precipitates; earlier victories stay in the city's `war_history` and the survivor's deeds. The hero fixture was re-pinned for it.
