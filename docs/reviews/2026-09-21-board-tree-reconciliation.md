# Board / tree reconciliation, 2026-09-21

Every backlog card's central claim re-tested against the tree as it stands, by running the
predicate rather than re-reading the card. Prompted by finding, mid-conversation, that two cards
named as the critical path had been delivered hours earlier and the board had not noticed.

## Method, and what it is worth

Claims were checked three ways, in descending order of confidence:

1. **Against a generated world.** `Fixtures/sample-world-v1.json` — seed 42, **size 33**,
   `generator_version` 16, written 2026-09-21 00:50, 64 top-level keys. This is the LAB-SAMPLE
   world and it is the freshest full document in the tree.
2. **By running the test** the card names.
3. **By reading the code path** the card cites, at its current line rather than the carded one.

**The size caveat is load-bearing.** Almost every content card measured seed 42 at **size 17**.
The sample is size 33. Structural claims (a field is absent, a block is empty, a ratio holds)
carry over; absolute counts do not, and every count below is the size-33 figure, not a correction
of the card's size-17 one. Where a proportion reproduces across the two sizes that is stated,
because it is much stronger evidence than either number alone.

Not re-tested: cards whose claim is a measurement of cost (`PERF-ADD-NESTS-DOMINATES`,
`PERF-CITY-COUNT-TRACKS-RASTER`, `SDET-PRODUCER-CALL-GRAPH`) — re-measuring those needs a quiet
machine and a fresh timed run, and this box has had three test suites on it all session.

## Delivered while the board said otherwise

| Card | Board said | Tree says |
|---|---|---|
| `PRODUCT-READ-SURFACE` | "no route answers a question about a world that already exists" | **Delivered.** `docs/conformance/read-surface.md` at tier `EXERCISED`, `terrain_read.py` + `terrain_read_select.py`, five schemas, 76 tests. The run prints its own sizes for seed 42 size 17: `blocks=8229, near=7540, person=6590, place=60234, quests=28806` bytes — against a 64.6 MB world. |
| `PRODUCT-ACTOR-SCALE-API` | "the complete set of actor-scale writes is two optional arrays" | **Delivered.** `docs/conformance/actor-scale-writes.md` at tier `EXERCISED`, four modules, `quest_actions` and `person_state` blocks with schemas. |
| `PLAYER-FOUNDED-SETTLEMENTS` | header: "No code written" | **Contradicts its own body**, which reads "Delivered 2026-09-20, for cities only" with 12 tests and a conformance record. Real remainder: hamlets and fortresses, and the player's layout not persisting. |

**The delivered work is green.** Run the way `tools/validate_repo.py:224` runs it — `PYTHONPATH=Sim`,
`python -m unittest discover -s Sim/tests` — `test_person_state` passes: **23 tests, 114.9 s, OK**.

The one error seen earlier was mine, not the product's: invoking by dotted path
(`python -m unittest tests.test_person_state`) breaks `Sim/tests/test_person_state.py:40`, which does a
bare `import test_quest_actions as quest_fixture` that only resolves when `Sim/tests` is itself on
`sys.path`. Worth knowing before anyone runs a single module by name, but it is not a gap in the
delivery and should not be filed as one.

## Confirmed — the claim reproduces

| Card | Predicate run | Result |
|---|---|---|
| `CONTENT-CITY-LAYOUT-DEAD-BLOCK` | `placed_count` across every option of every city | **0 for all 35 cities**, while `city_plans.cities[].plots` carries **1,105 plots with a building reference** (max 148 in one city) and `stats` reports `houses: 0, service_buildings: 0, worker_beds: 0`. Two blocks describing the same city disagree. |
| `CONTENT-QUEST-HOOKS-NO-VERB-NO-TARGET` | hook record keys | **235 hooks**, keys exactly `{actual_effect, giver_uid, hook_id, offered_from_face, stated_purpose, target, unwitting}`. No `verb`, no `difficulty`. `target` is a bare string on 234 of 235. The `verb` that exists in `hero_generator` is on the *person's claim*, never on the hook. |
| `CONTENT-ENCOUNTERS-ARE-FISH` | kind and disposition histogram | **2,627 entries; `wary` is 2,589 = 98.6%.** Top six kinds are all marine — greenland-shark 309, narwhal 299, bluefin tuna 230, swordfish 227, mako 201, blue shark 195 — 55.6% from six species. The card's "98% wary" reproduces to within 0.6 points at a different size. |
| `CONTENT-NO-DIFFICULTY-GRADIENT` | mean distance from each nest to its nearest settlement, by tier | **Flat.** tier 1: 13.2 km, tier 2: 14.8, tier 3: 13.0, tier 4: 12.6, tier 5: 13.1. Tier 5 sits **−1.1%** from tier 1. Danger has no spatial relationship to safety. |
| `CONTENT-BEAST-MOVEMENTS-STRANDED` | `routed` vs `stranded` | **856 of 2,610 stranded = 32.8%.** The card measured 260 of 792 = 32.8% at size 17. Identical proportion at 3.3× the scale. |
| `CONTENT-AGE-SUFFIX-IN-NAMES` | regex for `(Age N)` in the document | **2,323 strings**, including names — `"Fenweg (Age 1)"`, `"Borkadr (Age 1)"`. |
| `SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE` | the last line of `add_seasonal_food` | Confirmed, with evidence the card did not have: the function replaces `result['seasonal_food']` wholesale and then does `result['warnings'].append(...)` into a list nothing replaces. The world carries **28 warnings, 15 distinct**, the top one repeated **4 times** — once per age pass. |
| `TIME-PERSISTED-WORLD-CANNOT-ADVANCE` | `Sim/icarus_sim/terrain_biomes.py:100` | Unchanged and unguarded: `result['timing_ms']['classification']=elapsed; result['timing_ms']['total']+=elapsed`. Line number still exact. |
| `MAGIC-ADD-MAGIC-DEAD-WRITER` | callers of `add_magic` | `terrain_leyline_history.py:11` **imports it and never calls it.** Still an unreachable second writer. |
| `SHARED-GEOMETRY` | the exact primitives, per reader package | Confirmed: `child_seed` in all four of `hero_generator`, `story_web`, `npc_roster`, `key_locations`; `node_index` additionally in `key_locations`. |
| `BIOME-EXPOSED-ROCK-NEEDS-RELIEF` | `natural_biome` histogram | Biome **5 absent**. Present: 0, 2, 3, 4, 7, 8, 13, 15, 16, 17. (Also confirms 1 and 6 absent, consistent with the tombstoning.) |
| `BESTIARY-BRIMSTONE-BATS` | the species' own diagnostic | `{"species_id": "brimstone-bats", "tier": 2, "placed": 0}`. Still unplaceable. |
| `SDET-VILLAIN-FALL-UNREACHABLE` | `villains.fallen` | **0 fallen against 10 seated.** Consistent with the fall branch being dead in every buildable configuration. |
| `SDET-SITE-ID-ORDINALS` | `id == index` across `settlements.sites` | **True for all 35.** Sites do carry a `uid`, but it embeds the ordinal — `surface-city-0-322-elf` — so the uid is not independent of the position. |
| `PERF-SUITE-RUNNER-ORPHANS-CHILD` | cleanup at the two spawn sites | `tools/validate_repo.py:26` and `tests/test_showcase.py:21-22` both call `subprocess.run(..., check=True)` with **zero** `terminate`/`kill` between them. Note the card cites `tools/smoke_lab.py` as the *good example* that shows it could be done, not as a defect site — smoke_lab's terminate→wait→kill→wait at `:65-70` is that exemplar, not a fix. Reading the docs_check CITE warning on `smoke_lab.py:50` as "the card is stale" would be wrong; the line merely moved. |

## Changed — the card no longer describes the tree

**`BESTIARY-PYRAMID-RETUNE` — the inversion is gone, the shape is still wrong.** The card records
"204 tier-1 against 301 tier-5". Now: tier 1 = 199, tier 5 = **199**, exactly equal. So the
specific inversion no longer reproduces. But the distribution is 199 / 237 / 88 / 204 / 199 —
flat, not a pyramid, with tier 3 anomalously low at 88. The card's test asserts tier 1 **>**
tier 5, which still fails at 199 vs 199, so the ticket stays open; its stated numbers and its
diagnosis both need rewriting.

**`CONTENT-NO-ANTAGONIST` — half stale.** `heroes.dreads` and `magic.colleges` are still both
empty and still report no shortfall, so the card's mechanism holds. But the title no longer does:
`villains` now carries 10 people, 39 tiers and 10 works, because SUPER-VILLAINS S0–S8 landed
after the card was written. The world has antagonists; two specific wired systems still emit
nothing.

**`PRODUCT-BLOCK-REGISTRY` — the number moved against it.** The card says 48 published blocks, 30
without an envelope declaration or schema. The sample publishes **58 container blocks**, of which
**7** have a same-named schema. Same-name matching is a heuristic and not the card's own
predicate, so treat 7 as a floor rather than the figure — but the direction is unambiguous: the
gap widened while the card sat.

**`PRODUCT-CONSUMER-VOCABULARY` — confirmed and quantified.** A `tier` field appears at **12
distinct paths**, as `int` in `wildlife`, `beast_nests` and `beast_movements` and as `float` in
`villains.people` and `villains.outlook.regions`. The card's "four things" is an undercount of
the paths, though not necessarily of the meanings.

## Errors in the board's own summaries

`board/README.md` describes `CONTENT-BEAST-MOVEMENTS-STRANDED` as "movement records that no
consumer reaches." **That is not what the card says and it is false.** The card is about groups
that never walk, and it states outright that "`encounters` indexes all 792 anyway." Measured:
`encounters` carries 2,610 entries sourced from `beast_movements` and 17 from `nomads` — every
group reaches the index. A reader triaging off the README summary would fix the wrong thing.

## Two method notes, recorded because they nearly produced wrong findings

**A truncated key list nearly refuted a true card.** Printing `sorted(nest.keys())[:16]` cut off
`tier`, `x` and `z`, and the first read of `CONTENT-NO-DIFFICULTY-GRADIENT` was heading for "the
nests carry no tier field." They do.

**A guessed path returned a plausible zero.** `city_plans.cities[].buildings` does not exist —
the buildings are under `plots` — so a probe for it returned 0 per city and looked like
confirmation that `city_plans` places nothing. The real number is 1,105. An absent key and an
empty result are indistinguishable through `.get`, which is the same failure mode
`CONTENT-ARCHETYPE-FIELD-DOMAIN-MISMATCH` names as its most valuable finding: a predicate that
fails open returns a plausible answer to a question nobody asked.
