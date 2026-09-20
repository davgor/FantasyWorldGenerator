# CONTENT-POPULATION-THREE-NUMBERS — a city has three populations, two orders of magnitude apart

Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 6).

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
