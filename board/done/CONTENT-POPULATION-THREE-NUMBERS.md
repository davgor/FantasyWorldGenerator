# CONTENT-POPULATION-THREE-NUMBERS — a city has three populations, two orders of magnitude apart

Owner: SETTLEMENTS sweep. State: **DELIVERED 2026-09-21**, landed together with
CONTENT-CITY-LAYOUT-DEAD-BLOCK because both are versioned changes to the same nested record
and the schema and the conformance record would otherwise disagree.

## Delivered

**Re-measured first, at size 17 on today's tree (seed 42, phase 16, generator 16): the claim
reproduces, and the fortress half is four times larger than carded.** `Froskor`, the largest
city, reports `population_estimate` 29,428, `urban_population_estimate` 16,185,
`city_layout.residents` 29,428, **244** beds summed across its `city_plans` plots and **247**
people in `npcs`. All **17** castles — not four — report `beds: 0` on every plot beside 35 to
53 `workers`, and `npcs` stands exactly that many people in each.

**Every emitted magnitude now names the axis it measures.**

| was | is | axis |
|---|---|---|
| `settlements.sites[].city_layout.residents` | `.population_estimate` | the site's catchment estimate, copied verbatim |
| `city_plans.cities[].stats.simulation_population` | `.urban_population_estimate`, beside a new `.population_estimate` | the site's two demographic figures, copied verbatim |
| `debug_stats.cities[].population` | `.urban_population_estimate` | the same urban share |
| `castle_plans.castles[].plots[].beds: 0` | *absent*, with `castle_plans.beds` saying why | a castle plan models no sleeping capacity |

`population_estimate`, `urban_population_estimate` and `rural_population_estimate` on the site
itself are unchanged: they already carry their axis, and renaming them touches
`population_budget`, `population_profiles`, `seasonal_food`, `terrain_corruption`,
`terrain_leyline_history`, `terrain_wars`, `terrain_nomads`, `terrain_recipes`, `world_debug`,
the settlement API, the world schema and the native parity harness. The two fields that were
renamed had **one reader between them** (`tools/city_view.js`, updated).

**The ratio is stated in the conformance record**, `docs/conformance/settlement-records.md`,
with the measurement above and the sentence that it is a ratio rather than a rounding, plus
the ruling below.

**`beds: 0` on castle plans is fixed by absence, not by invention.** No structure in the
castle registry carries a bed count, so any number placed there would be authored rather than
measured. The field is gone from castle plots, `castle_plans.beds` states that the block
declares no sleeping capacity, and the garrison axis a castle plan does report is `workers`,
which `npc_roster` opens exactly one post per. This is the same discipline the founding API
already states: absence is representable and honest; a zero that was never measured is not,
and it divides into a runtime error rather than a wrong answer.

**A test pins roster-versus-beds agreement.**
`Sim/tests/test_settlement_records.py::test_roster_size_agrees_with_built_capacity_for_every_planned_site`
asserts, for every buildable city and hamlet, that `npcs.sites[].posts` equals
`stats.workers` exactly, that `stats.worker_beds >= stats.workers`, and that no more than ten
people stand in a settlement beyond the beds built — the cast is folded into the same places
without being staffed there, which is why the roster exceeds the beds by 0 to 5 everywhere.

**Test evidence.** `Sim/tests/test_settlement_records.py` was written first and run against
the unchanged tree: `Ran 6 tests in 116.490s / FAILED (failures=25, errors=12)`, leading with
`AssertionError: 'buildings' unexpectedly found in {'version': 1, ..., 'residents': 10989, ...}`.
After the change, with the three carry-back unit tests added:
`PYTHONPATH=Sim python -m unittest Sim.tests.test_settlement_records -v` -> **Ran 9 tests in
73.416s, OK**.

## The decision made on the owner's behalf

**Which of the four numbers a future Unreal adapter should hold: the built capacity.** Written
into the conformance record. It is the only one of the four a runtime can instantiate — the
demographic estimate is two orders of magnitude above anything the plan builds, and the roster
is derived from the capacity rather than the other way round. The rejected alternative is the
catchment estimate, which is what a map label wants and what a sim that models a hinterland
wants; it is rejected for the adapter specifically because an adapter that holds it has to
invent 29,184 people it has no buildings for. Reverse it by changing one sentence under
**Artifacts it writes** in `docs/conformance/settlement-records.md`.

## Two collisions left standing, deliberately

- `settlement_candidates[].population_estimate` is a nomad band's headcount — measured at
  **227** — under the same field name a city uses for a catchment estimate of 29,428. It is
  written by `terrain_nomad_effects.py`, which `docs/conformance/nomads.md` claims, so it is
  that record's to rename.
- `key_location_plans.plans[].plots[].beds` is the same `beds: 0` a castle plot carried,
  written at `Sim/key_locations/core/exterior.py:178` and declared in
  `Contracts/schemas/key-location-plans.schema.json`. Same defect, different owner.

## The claim as it was filed

Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 6). Everything below is the
original card, kept because its measurements are the before-picture.

## Observed behavior

Seed 42, size 17, `generator_version` 16. For `Froskor`, the largest city:

| source | value |
|---|---|
| `settlements.sites[].population_estimate` | 28,306 |
| `settlements.sites[].urban_population_estimate` | 15,568 |
| `settlements.sites[].city_layout.residents` | 28,306 |
| beds summed across its `city_plans` plots | 244 |
| people `npcs` places there | 247 |

The pattern holds across all nine cities: estimates of 6,547–28,306, beds of 156–252, rosters of
159–257. The roster tracks the beds to within ten people everywhere, which is the coherent
choice and means the two blocks a runtime would actually instantiate agree with each other.
Nothing reconciles the demographic estimate.

Fortresses are the sharper case. All four `castle_plans` entries report **`beds: 0`** and 37–42
`workers`, and `npcs` places exactly 37, 40, 42 and 42 people in them. Every garrison in the
world sleeps nowhere, and `workers` is silently serving as "people present".

## Why it matters

`population_estimate` is the number a settlement record leads with and the one a UI, a map label
or a sim would read. A town sign reading "pop. 28,306" over 133 buildings and 247 residents is a
promise nothing downstream can keep, and a consumer has no way to tell from the record which of
the three numbers is the one it should hold.

The fortress case is worse than a mismatch: `beds: 0` next to 42 placed people is internally
contradictory within a single site, and a consumer computing occupancy or shelter from beds gets
a division by zero rather than a wrong answer.

## Proposed mechanism

This is a naming and documentation change before it is a modelling one. The three numbers measure
three real things and all three are worth having:

1. **Name them for what they measure.** `population_estimate` is a demographic estimate for a
   settlement's whole catchment; `urban_population_estimate` is its urban share; the plan's beds
   are built capacity; the roster is instantiated people. Four axes, four names, none of which
   should be the bare word `population`. This is `PRODUCT-CONSUMER-VOCABULARY`'s C1 convention —
   magnitude fields are named for their axis — applied to a second collision.
2. **State the relationship in the conformance record** for whichever module owns settlement
   population, including the expected ratio and that it is a ratio rather than a rounding.
3. **Fix `beds: 0` on castle plans.** Either the kit places sleeping quarters, or the field is
   not applicable to a castle and should be absent rather than zero. A garrison is the one
   settlement kind where everyone demonstrably lives on site.

Whether the demographic estimate and the built capacity should ever converge is a design
question — a plan that built 28,306 people's worth of housing is a different product — and this
card does not ask for it. It asks that the document stop presenting four numbers as one.

## Dependencies and unresolved decisions

- `hero-guild.md`'s planner estimates beds and is opt-in; whether it shares this vocabulary.
- `population_budget`, `population_profiles` and `seasonal_food` all consume population figures;
  a rename touches their readers.
- Which number the future Unreal adapter should hold. It is the built capacity, but that has not
  been decided anywhere.

## Acceptance and evidence

- No two fields in the emitted document named `*population*` measure different axes without the
  axis in the name.
- A behavioral test asserts roster size agrees with plan beds within a stated tolerance for every
  planned site, so the two blocks that already agree cannot drift.
- No castle plan reports `beds: 0` while its roster places people in it.

## Adversarial review and limitations

One seed, one size. The ratio between estimate and capacity will move with world size and the
population profile; the fact that four differently-scaled numbers share one word will not.
