# Nomads and moving beasts

Owner: local. State: complete. No delegates.

## Delivered

- **Six nomad classifications decided by the ground, not by a roll.** Every candidate start point is tested against a hard geographic gate — survivors need a ruin destroyed this age *and* a surviving settlement to flee toward; deserters a decided war *and* rugged cover; cultists a ley node above threshold, a shrine or a villain's claim *and* a god actually bound to that school; merchants a road *and* two markets above a population floor; bandits ruggedness *and* wealth in strike range *and* no seat close enough to police it; wanderers forage *and* a seasonal swing that moves it. A classification whose gate fails is ineligible whatever its weight, and a candidate satisfying none raises nobody. The user's stated acceptance criterion was that cultists must not spawn nonsensically; this is the mechanism that prevents it.
- **Every gate returns a score in zero to one**, so the weight in `nomads.json` is the only balance lever. Unnormalised scores made that table decorative: ley intensity ran to 4.0 while a bandit's sat near 0.5, and cultists won nearly every contested draw regardless of what the weights said.
- **Migration routes per classification**: a two-move seasonal round for herders, a market chain subdivided so no caravan leg exceeds a day's march, a closed circuit over one god's sacred ground for cults, a lair with out-and-back spurs for raiders, and a single terminating move for the bands running from something. Day windows come from leg length over speed, anchored so a winter camp holds midwinter, with the seasonal phase inverting across the equator.
- **Five creature movement classes** on the catalogue — nester, migratory, irruptive, follower, drifter — defaulting to nester so no existing creature changed behaviour. The undead split follows a rule rather than a tag: an undead with a grave nests at it, an undead without one wanders. Seventeen creatures added that only exist because movement does, including a barrow wight as the deliberate stationary contrast. Profiles 663 to 680.
- **`beast_movements`**: herds, swarms, followers and the unhoused dead walking circuits, sharing the shape of `nomads.groups` so one consumer reads both. Followers derive a host's circuit rather than searching, and prefer people or herds by role.
- **`encounters`**: an index of what travelling thing is near here and when, over both sources, with `by_month` and `by_node`. An index, not a quest generator.
- **Four write-backs**: cults deepen their circuit node through `edit_network`; raiders add a distance-weighted `nomad_pressure` beside the nest, ley and war pressures; ridden roads record their riders; refugee bands that reached safety become settlement candidates.
- **`nomad_request`**, a stateless spawn API mirroring `visitation_request`, so a villain can raise cultists later without either feature importing the other. The band is still classified by the ground it is placed on; a request for cultists where nothing is sacred is refused rather than quietly honoured.
- `STATE_KEYS` 41 to 47, `historyStateKeys` matching. Four registry options. Three published schemas. Asset registry 1632 bindings, both regenerators `--check` clean. `docs/nomads.md` and `docs/beast-movement.md`, both indexed.

## Acceptance evidence

- Wired at **both** attach sites — stage sixteen and the age-advance tail. Verified on seed 42 size 17: before an advance, 13 bands at origin age 2; after, 21 bands all at origin age 3, block replaced rather than carried, every survivor refuge resolving, caller's world unmutated.
- Stage isolation holds for all five new blocks: absent at `materialize_stage(world, 15)`, present at 16.
- `tests/test_world_schema_conformance.py`: three new methods pass, including an assertion that `by_month` and `by_node` agree with a linear scan — an index that disagrees with the data it indexes is worse than no index.
- `Sim/tests/test_creature_movement.py`: 9 tests. Decomposes the three reasons a creature does not place and asserts only on the one that is a defect.
- `Sim/tests/test_terrain_nomads.py`: 22 tests covering the classification gates, route schedules, contiguous leg walks, the day-march bound, and hemisphere inversion.
- Structural before/after comparison on seeds 42 and 73 at size 17: every pre-existing block byte-identical. The gate has a negative control — two different seeds produce 41 correctly attributed failures — and on its first live run it correctly caught `npcs` and `key_locations` appearing from concurrent sessions, which was fixed by attributing additions rather than widening an allowlist.
- Provenance rows appended for all four pinned files touched; `verify_provenance.py` clean across 79.
- Pipeline cost at seed 42 size 17: nomads 6 ms, routes 7 ms, beasts 48 ms, encounters 53 ms.
- Full `Sim/tests` and `tests` suites and `tools/validate_repo.py` were **not** run here; verification was consolidated centrally against a settled tree.

## Limitations and next action

Three bugs found by checking rather than reasoning, all silent, all fixed: seven of the seventeen new creatures could never place because their `requires` thresholds were two to three times what any ground reaches or they leaned on schools locked at zero; the candidate clearance test was a binary cell skip, so the same world held a different number of bands at raster 17 and raster 33; and rest split evenly across camps put a bandit in the hamlet it had just raided for four months.

`test_pyramid_and_overlap` and `test_population_scales_with_the_ground` were failing before this work and **the roster widened the first deliberately** — 11 monsters weighted to the middle and top. Catalogue tiers moved from `[(1,250),(2,147),(3,136),(4,81),(5,49)]` to `[(1,253),(2,151),(3,141),(4,85),(5,50)]`. Stated up front rather than absorbed into a pre-existing red.

Cult prevalence is a function of how violent the world's history was, not an authored constant: every destroyed city leaves a ley key point at intensity 3.5 to 4.0, so a bloody age manufactures sacred ground. One age advance took cultists from 5 of 13 bands to 14 of 21. Tuning that means tuning the weight, not the gate.

Next actions are carded rather than left in prose:

- `board/backlog/NOMAD-FISSION.md` — `fission` is a declared branch kind that never appears.
- `board/done/NOMAD-SURVIVOR-SETTLEMENT.md` — nothing adopted `settlement_candidates`; closed 2026-09-21 by absorption into the refuge rather than by founding.
- `board/backlog/NOMAD-CARAVAN-ECONOMY.md` — nothing reads `caravan_throughput`.
- `board/backlog/NOMAD-IRRUPTION-TRIGGER.md` — swarms erupt every year because there are no years; depends on the queued time-control work.
- `board/backlog/NOMAD-CORRUPTION-CONTRACT.md` — the `pending_ley_edits` applier contract was agreed with a session that has since closed and can no longer be confirmed by its author.
- `board/backlog/BESTIARY-PYRAMID-RETUNE.md` — the inverted tier pyramid and its now-moved baseline.
- `board/backlog/BESTIARY-BRIMSTONE-BATS.md` — a pre-existing creature that cannot exist in any world.
