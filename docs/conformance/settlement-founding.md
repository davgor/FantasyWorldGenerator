---
conformance: 1
record: settlement-founding
tier: EXERCISED
summary: Founds a player-chosen city at a terrain node, deriving its metadata from the ground it stands on so the world reads it as a settlement rather than as an insertion.
modules:
  - Sim/icarus_sim/terrain_settlement_api.py
emits:
  - path: settlement_founding
    schema: (none; see Does not establish)
  - path: settlements.founded_by_player
    schema: (none; see Does not establish)
versions:
  - id: settlement-api
    assert: 1
proof:
  - path: tests/consumer_founder.py
    establishes: the id-equals-index invariant, that city_class is derived rather than supplied, that the eight terrain fields are exact layer reads, that every cross-block join still resolves, that the world still passes validate_age_world and still advances, and that six ways of asking wrongly are each refused by name
decisions:
  - docs/decisions/025-controls-are-a-machine-contract.md
tickets:
  - board/backlog/PLAYER-FOUNDED-SETTLEMENTS.md
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
| `POST /world/found-settlement` | `tools/terrain_lab.py` | the same, over the loopback lab |
| `PLAYER_MARK` / `PLAYER` | `terrain_settlement_api` | the key and value marking a site the player founded |

## Inputs it reads

`layers` (nine fields by name, including the per-civilization `suitability_<id>` and
`magic_risk_<id>` grids), `settlements.sites`, `ruins`, `config`, `effective_config`, and
the civilization registry through `terrain_profiles`. It needs a world generated at least
through stage 9, because before that there is no settlement list to add to.

## Artifacts it writes

`settlements.sites[]` gains one record. `settlements.founded_by_player` is the index of
player-founded uids. `settlement_founding` is the per-call report. One `history.operations`
row of kind `founding`.

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

Settlement API version 1 <!-- conformance:version settlement-api=1 -->.

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
- **That the player's layout persists.** It does not. `site['city_layout']` is overwritten for
  every site at `terrain_settlements.py:938` and `city_plans` is popped and rebuilt from
  empty, with no module reading a prior plan to preserve it. The `founded_by` marker is
  written so a future carry-back can recognise a player site, but **no such carry-back
  exists**, so today "the player owns the layout" is a requirement this API does not meet.
- **Nothing about hamlets or fortresses as player-founded kinds.** Only cities can be founded.
  Those blocks use ordinal ids that renumber at every age boundary, and a player keep keyed
  that way would change name under its owner.
- **Nothing about `village`.** It is not a settlement kind anywhere in the tree;
  `settlements.sites[].kind` is the constant `'city'`, and small/medium/capital is the
  classification rank rather than a size vocabulary.
- **No schema.** `settlement_founding` and `settlements.founded_by_player` are emitted and
  declared in no schema, so a consumer cannot validate them. That is the open-container
  question `VILLAINS-NO-SCHEMA` and `PRODUCT-BLOCK-REGISTRY` own.
- **Not measured above size 17.** The legality sweep walks the node list linearly and the
  spacing check is O(sites); neither has been timed on a larger grid.
