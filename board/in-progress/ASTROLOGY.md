# ASTROLOGY — One moon, temporary ley surges, ruin legacies, gods who may walk

Drafted: 2026-09-18. Status: in progress. Owner: lunar-cycle session. Companion ticket: [PANTHEON](PANTHEON.md).

## Requested behavior

The user asked for a lunar cycle that adds perceived chaos to magical fluctuation, published in the final generation so a game can tie day and night to the moon; one moon whose hemispheres carry different magics so every school gets its turn; surges that mutate leyline strength temporarily rather than permanently; ruins that leave lasting leyline nodes matching the region, culture or source of destruction; and gods that may exist as back-burner characters unless the orchestrator summons one, in which case the god walking the mortal plane is highly disruptive.

## Proposed mechanism

See [docs/astrology.md](../../docs/astrology.md) and [docs/pantheon.md](../../docs/pantheon.md), which are the canonical contracts. In one paragraph: a seeded moon with three coprime-preferring integer-day cycles (phase, spin, nod) and eight school regions on two hemispheres yields a per-school tide multiplier in 0.5–1.8; the almanac and closed-form formulas are exported; `lunar_sensitivity` says how far each cell sways; the age lottery rolls under the surge in force on the age's day (`lunar_influence`, default 0.5); every ruin seeds a key point (source, then region, then culture); the pantheon resolves gods, cosmology and faiths from world state with no world effect; `POST /world/summon` places an avatar cluster, rolls a divine fate lottery, purges rival nests, converts survivors, and leaves a footprint on departure.

## Dependencies and unresolved decisions

- The "Tectonic plates and city scale" session owns `terrain_history.py`, the schema and the scale contracts until it signals done. Everything here is calibrated in ratios of `settlement_spacing`, never metres or raster cells.
- Native parity evidence for the moon port is blocked by that session's scale change until its parity card lands; reported as blocked, not chased.
- The moon's region layout and the ruin legacy tables are code constants; the civilization registry is their future home.
- Metre-denominated ley widths in `OPTIONS` will not survive the scale change; flagged to the tectonic session, not fixed here.
- The moon is controllable from the API (user request, 2026-09-19): generation overrides `moon_variation`, `moon_synodic_days`, `moon_spin_days`, `moon_nod_days`, `moon_tilt_degrees`; `POST /world/moon` (`terrain_astrology.lunar_request`) for the sky and surge at any day or hour; `moon_day` on advance-age and `day` on summon. Still noted for later: per-god festival calendars beyond the almanac feasts, and a runtime clock inside the Unreal plugin.

## Sources consulted

`terrain_leyline_history.py` (schools, dominance, edit boundary), `terrain_history.py` (ages, fates, age API, snapshot deltas), `terrain_seasons.py` and `terrain_ecology.py` (months), `founding.py` (years), `terrain_tectonics.child_seed`, `Core/ages.cpp` and `Core/magic.cpp` (parity surface), `Fixtures/native-world-v1.json` (numeric contract), `board/in-progress/PANTHEON.md`, decisions 016 and 020.

## Files and assets in scope

New: `Sim/icarus_sim/terrain_astrology.py`, `terrain_ruins.py`, `pantheon.json`, `terrain_religion.py`, `terrain_visitation.py`; `Sim/tests/test_terrain_astrology.py`, `test_terrain_ruins.py`, `test_religion.py`, `test_visitation.py`; `docs/astrology.md`, `docs/pantheon.md`; `Core/astrology.hpp/.cpp`.
Edited: `terrain_world.py` (`lunar_influence`), `terrain_history.py` (pipeline wiring, age lottery, legacies, departure, pins), `tools/terrain_lab.py` (`/world/summon`), `tools/terrain_lab.html` (state keys, layer label), `tools/terrain_world.js` (Moon and Gods panels), `Contracts/schemas/world-output.schema.json` and `tests/test_world_schema_conformance.py`, `docs/terrain-world-layers.md`, `docs/README.md`, `Core/README.md`; `Core/config.hpp`, `layers.*`, `world.*`, `ruins.hpp`, `ages.cpp`, `tests/world_driver.cpp`, `tests/test_native_world.py`; new `Core/legacy.hpp/.cpp`. Every pinned file carries a provenance revision.
No new asset identities: ruins reuse `marker.city_ruins`; the avatar is a ley cluster, not an actor; no temple dedications. The exhaustive asset list is unchanged.

## Acceptance and evidence

Green in the tree (2026-09-18, sizes 17 and 33 on the rescaled world): 7 astrology pure-function tests; 5 ruin legacy tests; 11 pantheon tests; 5 visitation tests on a generated seed-42 world (determinism, input untouched, avatar saturation, walking status, departure footprint and restoration, rejections); the existing history, magic, wars, threat and biome-contract suites with the pipeline wired (STATE_KEYS, stage 9 astrology, stage 13 and per-age religion, surge-scaled fate lottery, legacies for every ruin, walking-god departure at age transitions, age-API pins, almanac refresh on advance-age); `tools/verify_provenance.py` on 79 files; JS syntax of the lab script.
Pipeline tests in `Sim/tests/test_astrology_pipeline.py` cover export presence and replay, age moon records and legacies, `lunar_influence: 0`, the age-API pins and `moon_day`, generation overrides of the moon's cycles, magic-disabled worlds and the lab page's state-key list (green 2026-09-19 together with the wars, visitation and moon-query tests, 30 + 6 + 9 tests). Export byte-reproducibility verified on a quiet tree; a differing `heroes` section comes from another session's untracked module, not the generator.
Native: `Core/astrology.cpp` is bit-exact against Python (six seeds, 19,200 tide samples); `Core/legacy.cpp` and the age-transition port build into the full driver. The finished-world parity test is expected red for a reason outside this ticket: the tectonic session's circumference change is not yet ported to `Core/`, so the two sides generate different planets. Reported as blocked, not chased.

## Documentation impact

`docs/astrology.md` and `docs/pantheon.md` (new), `docs/README.md` index lines, `docs/terrain-world-layers.md` moon subsection and age/API additions, `Core/README.md` note, `PANTHEON.md` updated with the decisions taken.

## Adversarial review and limitations

Artistic astronomy; the age lottery samples one day per age; standing assessments and wars ignore surges; gods have no effect unless summoned; a visitation is bounded and stateless; previously exported worlds must be regenerated; the Unreal plugin does not yet act on religion or visitation JSON.

## Handoff

Next: `python tools/validate_repo.py` once the tectonic session's slice settles (repo-tests will stay red on the native world test until its parity card lands); then the lab walkthrough in `docs/astrology.md` and `docs/pantheon.md`. Follow-ups outside this slice: port the world-scale change to `Core/` (restores parity for the moon and legacies too), move the legacy and region tables into the civilization registry, temple dedications from faiths, Unreal importer reading the religion and visitation JSON.
