# NOMAD-SURVIVOR-SETTLEMENT - adopt refugee camps as settlements

**DONE 2026-09-21 by absorption, not by founding. Owner ruling: the band reached a town and
stopped, so the refuge grows.** Nothing is founded, and `settlement_candidates` is now a
migration ledger rather than a founding queue — which is exactly what option 1 below said it
would become, and the owner chose it knowingly. See "What was delivered" at the foot.

Re-scoped 2026-09-21; see "What the measurement found" and "Proposed rewrite" below. The
rewrite's second half — making a survivor band able to terminate somewhere that is *not* an
existing settlement — is **not** carried forward by this card and is not filed as a new one:
the ruling closed the founding question rather than deferring it.

## Requested behavior

A survivor band that reached its refuge and stayed is exactly how a hamlet starts. Today
that is recorded in `settlement_candidates` and **nothing adopts it**, so a world can carry
candidate settlements indefinitely without one ever becoming real.

Each candidate already carries `node`, `direction`, `migration_source_node`,
`migration_distance_m`, `population_estimate` and a prose `reason` naming the ruin fled and
the refuge reached - deliberately the same fields `founding.py` uses, so a founding pass can
adopt them directly.

## What the measurement found

Half the card holds and half does not.

**Holds:** nothing adopts them. `settlement_candidates` is written only by
`terrain_nomad_effects.seed_survivor_camps` and read by nothing in the tree except
`tests/test_world_schema_conformance.py`, which only checks that `from_band` resolves.

**Does not hold: a candidate does not name ground a settlement could be founded on. It
names the refuge city's own node.** Measured on two generated worlds, 4 candidates of 4,
and it is true by construction rather than by luck:

| world | candidate node | city already at that node | refuge named in the band's basis |
|---|---|---|---|
| seed 42, size 17 | 147 | `surface-city-0-147-elf` | `surface-city-0-147-elf` |
| seed 42, size 17 | 206 | `surface-city-2-206-frosthold_dwarf` | same |
| seed 42, size 17 | 192 | `surface-city-2-192-hill_dwarf` | same |
| seed 42, size 33 | 426 | `surface-city-0-426-human_desert` | same |

The construction: `terrain_nomad_routes._flight` routes a survivor band to the node of the
site whose uid is `basis['refuge_uid']`, and `seed_survivor_camps` records the candidate at
`terminal['node']` — which is therefore always the refuge's own node. None of the four
candidate nodes carries a hamlet; all four carry a standing city.

So "adopt the candidate as a settlement" would found a second settlement on top of a city
that is already there. The band did not reach empty ground and start a hamlet. It reached a
town and stopped, which is a different event with a different consequence.

## Why this was not worked around

Three fixes were considered and all three are somebody's decision rather than this card's:

1. **Absorb into the refuge** — add the band's `population_estimate` to the standing city at
   the age boundary. Demographically right, needs no placement, bounded. But it is not what
   this card asks for: nothing is founded, no hamlet starts, and `settlement_candidates`
   stops being a founding queue and becomes a migration ledger. That is a rename of the
   block, not an adoption pass.
2. **Move the camp off the refuge node** — record the candidate at the last approach node
   before the refuge, so it names free ground beside the town the way a refugee camp
   actually forms. One short edit in `seed_survivor_camps`. Rejected here because the offset
   is one raster cell, which is 8 km at size 17 and under 1 km at size 129: a
   resolution-dependent placement constant is the exact failure this subsystem is built to
   avoid, and every reach in it is a multiple of `settlement_spacing` for that reason.
3. **Found it anyway and let the site list carry two settlements at one node** — refused
   outright. `validate_age_world` re-derives `city_class` as a rank over the site list and
   twenty-seven modules join on `node`.

## Proposed rewrite

Split the card in two, because it is two pieces of work with different owners:

- **NOMAD-REFUGEES-REACH-A-TOWN** — decide what happens when a survivor band terminates at a
  standing settlement. Absorption into the refuge's population is the obvious answer and is
  small. This is the case that actually occurs today, in every world measured.
- **NOMAD-SURVIVOR-SETTLEMENT (this card, rewritten)** — first make a survivor band able to
  terminate somewhere that is *not* an existing settlement, in settlement-spacing units and
  not in raster cells; only then does adopting the camp mean founding anything. Note that
  the survivors gate requires a surviving settlement within `refuge_reach_spacings`, so the
  refuge is the destination by design and changing that is a change to the gate, not to the
  route.

## The adoption seam, which was worked out and is still correct

**Half of it survived contact.** The location did: absorption runs in `age_transition`
before `rebuild_tail`, and no fixture rebuild is owed for the reason given below. The
mechanism did not: `population_estimate` is re-derived by the rebuild, so the count has to
ride `CARRIED_SURVIVOR_KEYS` instead. See "What was delivered" at the foot for the
measurement. Read the rest of this section as the founding plan it was written as.

Should adoption be built after the rewrite, the mechanism is settled and cheap, and it is
recorded here so it is not re-derived:

- Adopt at the **start** of `terrain_history.age_transition`, before `rebuild_tail`, by
  appending to the `survivors` list. `civilization()` puts that list in `result['_survivors']`
  and `terrain_settlements.add_settlements` feeds it to `found_cities(survivors=...)`, so an
  adopted row is carried through the rebuild instead of being regenerated away.
- It must be a `settlements.sites` row, **not** a `humans.hamlets` row. `add_humans`
  re-derives the rural layer from scratch on every rebuild, so a hamlet row appended before
  `rebuild_tail` would be wiped by the very rebuild the card wanted to ride.
- A survivor row needs `node`, `population_profile` and `founding_year`; `remember_cities`
  mints the node-keyed `uid` and `founded_age` afterwards.
- **No fixture rebuild is owed by adoption.** `settlement_candidates` is written by
  `apply_nomad_effects`, which runs only at the end of generation and at the final age of an
  advance, so a generation-internal age transition never sees one. Adoption would be visible
  only through `advance_age_request` on a finished world.
- The card's own filter — refuge still standing at the boundary — is the right one and is a
  one-line lookup against `result['settlements']['sites']` after the fates are decided.

## Dependencies

`terrain_history.rebuild_tail`. NOMAD-FISSION was delivered separately on 2026-09-21 and did
not need to be designed alongside this after all: fission runs at placement and touches no
age boundary, so the two do not share a decision.

## What was delivered, 2026-09-21

`absorb_survivor_camps(result, survivors, age)` in `terrain_nomad_effects.py`, called from
`terrain_history.age_transition` immediately before `rebuild_tail`. For each candidate it
resolves `from_band` -> the band -> `basis['refuge_uid']`, looks that uid up **in the
survivors list**, and credits the standing city with the band's `population_estimate`. The
candidate is stamped `absorbed_age` and `absorbed_into`; the city carries
`absorbed_refugees` and a sorted `absorbed_bands`. A refuge that fell at this boundary is
absent from `survivors`, so it absorbs nobody and nothing is recorded — the card's own
filter, expressed as the argument rather than as a lookup.

### The seam on the card is right about where, and wrong about what — re-verified, not assumed

The card's adoption seam was worked out for **founding**, and the ruling changed the verb.
The location transfers: the start of `age_transition`, before `rebuild_tail`. The mechanism
does not.

**`population_estimate` cannot carry the refugees.** `add_settlements` re-derives it from the
population budget on every rebuild — `residents = allowance//len(members) + (index <
allowance % len(members))` — so a number written into a survivor row before `rebuild_tail`
is erased by the rebuild it was meant to ride. The carried fact is `absorbed_refugees`,
which joins `CARRIED_SURVIVOR_KEYS` beside `war_history` and is added back **after** the
capacity split, so the split stays a pure function of the ground the city farms and the
arrivals stay separately auditable in `absorbed_bands`.

**Idempotency is required, and is by band uid.** `seed_survivor_camps` only assigns the
block when it has candidates, so a world can carry a previous advance's list unchanged into
the next one; absorbing that list again would breed people every age out of one migration.
A band uid is `nomad-<age>-<node>` and is never reused by a later age, so `absorbed_bands`
is a safe ledger to filter on. Matching on the candidate's `node` instead would answer a
different question — which city stands there now — and city ids renumber across ages.

**No fixture rebuild is owed, and the card's reason for that holds.** `settlement_candidates`
is written at stage 16, after both generation-internal age transitions (stages 14 and 15),
so `absorbed_refugees` is absent from every generated world and the added term is `+0`.
Absorption is visible only through `advance_age_request` on a finished world.

### Measured, and the owner should see it: on the one world tested it absorbs nobody

An advance of seed 42 size 17 was driven end to end with the pass instrumented. All three
candidates resolve their band and their `refuge_uid` — `surface-city-0-147-elf`,
`surface-city-2-206-frosthold_dwarf`, `surface-city-2-192-hill_dwarf` — and **all three of
those refuges are destroyed at the same boundary**. The age-3 lottery leaves 3 of 12 cities
standing and produces 19 ruins, so the pass correctly returns `(0, 0)` and nothing is
credited.

That is the filter working, not the pass failing: a town that fell this age cannot take
refugees in. But it means the feature's visible effect on the world that exists today is
zero, and whether a boundary that kills three cities in four is the intended mortality is a
separate question this card does not answer. It is also why the rebuild-seam test drives
`rebuild_tail` directly with every city handed in as a survivor: a test driven through
`advance_age_request` on this world would pass while asserting nothing.

### What was deliberately not done

The age record in `history.ages[]` does **not** report the absorption. It would have been the
natural place for a count, and adding a key there changes generated output — every age of
every generated world would carry `refugees_absorbed: 0` — which stales the 162 MB fixture to
report a number that is always zero at generation. The audit trail is on the candidate and on
the city instead, both of which are written only when something actually happened.

Of those two, **the city's `absorbed_bands` is the durable one**. `seed_survivor_camps`
replaces `settlement_candidates` wholesale whenever the next advance raises candidates of its
own, so `absorbed_age` and `absorbed_into` are a stamp on the row that was read rather than a
permanent record. That is also why the idempotency filter is on the city and not on the
candidate: the stamp can vanish, the ledger cannot.
