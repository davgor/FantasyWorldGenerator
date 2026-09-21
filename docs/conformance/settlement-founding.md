---
conformance: 1
record: settlement-founding
tier: EXERCISED
summary: Founds a player-chosen city, hamlet or fortress at a terrain node, deriving its metadata from the ground it stands on so the world reads it as a settlement rather than as an insertion.
modules:
  - Sim/icarus_sim/terrain_settlement_api.py
emits:
  - path: settlement_founding
    schema: (none; see Does not establish)
  - path: settlements.founded_by_player
    schema: (none; see Does not establish)
versions:
  - id: settlement-api
    assert: 2
proof:
  - path: tests/consumer_founder.py
    establishes: the id-equals-index invariant, that city_class is derived rather than supplied, that the eight terrain fields are exact layer reads, that every cross-block join still resolves, that the world still passes validate_age_world and still advances, that six ways of asking wrongly are each refused by name, that a hamlet and a fortress land in the blocks that already hold them under a node-and-kind key that survives a rural rebuild, that village is refused as a kind, and that an authored layout is not packed by the generator
  - path: Sim/tests/test_settlement_records.py
    establishes: that the survivor carry-back copies a player-authored layout onto the rebuilt site and leaves a generated one to be re-derived
decisions:
  - docs/decisions/025-controls-are-a-machine-contract.md
tickets:
  - board/done/PLAYER-FOUNDED-SETTLEMENTS.md
---

# Conformance: settlement-founding

## What it produces

A new world carrying one more city. The site is built from the layers that already describe
its ground, so it holds the numbers a generated city would have held in the same place
rather than plausible invented ones. The caller's world is untouched, the call is recorded
in `history.operations`, and a `settlement_founding` report states what the call changed and
what it deliberately left alone.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `found_settlement_request(body)` | `terrain_settlement_api` | the whole call: validate, judge the ground, insert, classify, optionally rebuild, report |
| `kind` | the request | `city`, `hamlet` or `fortress`; each writes into the block that already holds that kind |
| `POST /world/found-settlement` | `tools/terrain_lab.py` | the same, over the loopback lab |
| `PLAYER_MARK` / `PLAYER` | `terrain_settlement_api` | the key and value marking a site the player founded |

## Inputs it reads

`layers` (nine fields by name, including the per-civilization `suitability_<id>` and
`magic_risk_<id>` grids), `settlements.sites`, `ruins`, `config`, `effective_config`, and
the civilization registry through `terrain_profiles`. It needs a world generated at least
through stage 9, because before that there is no settlement list to add to.

## Artifacts it writes

`settlements.sites[]` gains one record for a city, or `humans.hamlets[]` /
`humans.fortresses[]` gains one for a rural kind, plus its id on the parent city's `cores`
row. `settlements.founded_by_player` is the index of player-founded city uids.
`settlement_founding` is the per-call report. One `history.operations` row whose `kind` is
`founding` and whose `settlement_kind` is the kind of settlement founded -- two axes, two
names, because a row that spelled both `kind` would be read as one.

**Invariant: a rural site is keyed on its node and its kind.** `humans.hamlets[].id` and
`humans.fortresses[].id` are ordinals reissued every time the rural layer is rebuilt, and
`hamlet_plans` and `castle_plans` join on exactly those, so the ordinal is kept and is not
identity. Beside it the row carries `uid` -- `hamlet-node-1062` -- which is the key
`npc_roster` already mints for the same row, and which `add_humans` preserves across a
rebuild along with the node and the player's own choices. No parallel id space is invented;
the ordinal space itself belongs to `SDET-SITE-ID-ORDINALS`.

**Every rural row carries that `uid` now, not only a player-founded one.**
`terrain_humans.record` mints `f'{kind}-node-{i}'` with the same expression this route uses, so a
consumer joining on it does not have to ask which route built the row, and
`hero_generator.wells.countryside` keys castellans and reeves on exactly it. That is a widening of
this block by a producer this record does not own: a generated world's rural rows gained the field
at a time they previously did not have it, and a consumer that treated `uid`'s presence as the
mark of a player founding would now read every row as one. `founded_by` is that mark and always
was.

**Invariant: `layout: "player"` means the generator does not pack this city.** The site
carries a `city_layout` whose profile is `player`, `terrain_settlements.carry_survivor`
copies it onto the site every rebuild produces, and `city_planner.plan_city` returns a plan
with `status: "unbuildable"`, `authored_by: "player"` and a stated reason rather than a
packing of its own. `unbuildable` is a status the planner already emits, so no consumer
needs a new branch.

**Invariant: `site['id']` equals the site's index in `sites[]`.** It is used as a direct
list index into `humans.cores`, `seasonal_food.models` and per-site profile lists, so an id
that is not the ordinal position joins the wrong rows *silently* rather than raising. The
call appends, so the new id is `len(sites)` before insertion, and the test asserts the
invariant across every site rather than only the new one.

**Invariant: `city_class` is derived, never supplied.** It is a per-civilization suitability
*rank*, not a size. `validate_age_world` re-derives it and refuses the entire world on a
mismatch, so a caller-supplied class makes the world permanently unadvanceable — and the
failure surfaces at the next advance rather than at the call that caused it. Because it is a
rank, a strong new site can demote an incumbent; the report names any city whose class moved.

**Invariant: the uid is the generated rule verbatim** —
`surface-city-{age}-{node}-{population_profile}`, the same expression as
`terrain_history.py`. A player city takes no parallel id space, which is what lets the
survivor carry-back recognise it.

Recorded because it looks incidental and is not: the eight terrain fields are *exact* layer
reads, verified field by field against every site of a generated world. An implementation
that recomputed them from a formula would drift from the generator by a float and produce a
city whose ground disagrees with the ground it stands on.

## Where it runs

At the request boundary, on a world the caller already holds. Never during generation.

## Versions asserted

Settlement API version 2 <!-- conformance:version settlement-api=2 -->. Version 1 took cities
only and is not retryable; a request naming `kind` is a version 2 request.

## Proven by

`tests/consumer_founder.py` — 12 tests, run as a consumer persona rather than a unit test,
because the question is what an orchestrator receives. Six refusals each assert the field
named; six assertions cover the invariants above plus the operation log and the disclosure
report.

## Why it works this way

Two things it refuses to do carry the reasoning.

**It does not re-run the nest pass.** `terrain_nests._place` opens one sequential RNG over a
fixed cell order whose per-cell draw count depends on distance to the nearest settled thing,
so one new town changes the draw stream in every cell on the planet — measured at 152 of 248
monster nests replaced, the furthest at the antipode. Framed as cost, someone eventually pays
it "for correctness" and silently re-rolls the bestiary, expiring every quest keyed on a nest
id. Framed as a determinism-contract violation, they cannot.

**Rebuilding is an argument, and it defaults to off.** Whether founding should rebuild the
dependent blocks immediately, mark the world dirty for a later tick, or take an argument was
the open question. It takes an argument. A dirty flag puts an age-transition-sized cost
somewhere the caller cannot see and cannot decline, and rebuilding unconditionally charges
every founding for work most callers do not want; an argument makes the trade the caller's,
at the call that caused it.

**It defaults to leaving the rural layer alone.** `add_humans` re-derives hamlets and
fortresses from scratch in site order with length-at-append-time ids, so adding a city trades
ordinals among settlements that were already there — measured at 15 hamlets reassigned on a
single founding. `rebuild: "humans"` is offered because a town with no hinterland is a town
in a field, but it drops `hamlet_plans` and `castle_plans` rather than leaving rows that name
ground which moved. Absence is representable; a stale row that resolves to the wrong place is
the failure this API exists to avoid.

## Does not establish

- **That a founded city survives.** It usually will not, and that is the world working. On an
  untouched seed-42 size-17 world an age advance ruins ten of twelve cities across six causes;
  a player town dying is ordinary attrition. The test asserts the world still advances, never
  that the town lived — asserting survival would be asserting the war model is gentle.
- **That the player can supply layout content.** The call takes `layout: "player"` and
  preserves whatever `city_layout` the site then carries; it has no field for a layout
  document and validates none. What is established is that the generator stops overwriting
  it — `terrain_settlements.carry_survivor` is the carry-back the `founded_by` marker was
  written for, and it now exists — not that there is a way to hand one in.
- **That a player fortress is laid out by its owner.** It is not: `fill_castles` plans it
  with the castle kit like any other, because `layout` is a city-only argument today.
- **Nothing about `village`.** It is not a settlement kind anywhere in the tree;
  `settlements.sites[].kind` is the constant `'city'`, and small/medium/capital is the
  classification rank rather than a size vocabulary.
- **No schema.** `settlement_founding` and `settlements.founded_by_player` are emitted and
  declared in no schema, so a consumer cannot validate them. That is the open-container
  question `VILLAINS-NO-SCHEMA` and `PRODUCT-BLOCK-REGISTRY` own.
- **Not measured above size 17.** The legality sweep walks the node list linearly and the
  spacing check is O(sites); neither has been timed on a larger grid.
