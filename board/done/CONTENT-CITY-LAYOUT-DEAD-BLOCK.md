# CONTENT-CITY-LAYOUT-DEAD-BLOCK — every city reports it has no buildings, beside a planner that built them

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** `placed_count` is 0 for every option in all **35** cities, while `city_plans.cities[].plots` carries **1,105** plots with a building reference (max 148 in one city) and `stats` reports `houses: 0`. Two blocks describing the same city disagree.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: SETTLEMENTS sweep. State: **DELIVERED 2026-09-21**, landed together with
CONTENT-POPULATION-THREE-NUMBERS because both are versioned changes to the same nested record.

## Delivered

**Re-measured first, at size 17 on today's tree (seed 42, phase 16, generator 16, after the
planner flood fix): the claim reproduces and is sharper than carded.** All **12** cities report
`placed_count: 0` against option targets of 32-68, with 3 or 4 options flagged `required` and
nothing placed, `required_asset_count: 0` and `required_node_slots: 0` in every one of them --
beside `city_plans` entries that are now `partial` rather than `unbuildable` and hold **47 to 148
placed plots** each. The card's own figures (nine cities, 82-137 plots) are superseded; the
contradiction is not.

**`city_layout.buildings` is deleted.** `settlements.sites[].city_layout` is version **2** and
carries `layout_profile_id`, `layout_profile_name`, `population_profile`,
`population_estimate`, `river`, `building_pack_id`, `required_assets`,
`required_asset_count`, `required_node_slots`, `asset_anchors_missing`, `features`,
`constraints` and an optional `fallback`. The asset requirement the building draw produces
survives; the per-option placement claim does not. `buildings.missing_anchors` is promoted to
`city_layout.asset_anchors_missing` so no information is lost.

**`city_plans` is authoritative for placed buildings**, stated in
`docs/conformance/settlement-records.md`, which is the record that now claims
`Sim/icarus_sim/city_planner.py`. `Sim/tests/test_settlement_records.py` asserts for every city
in a generated world that no settlement record carries a building-placement claim and that
every site joins a `city_plans` entry, so the two cannot drift apart again.

**Test evidence.** `Sim/tests/test_settlement_records.py` was written first and run against
the unchanged tree: `Ran 6 tests in 116.490s / FAILED (failures=25, errors=12)`, leading with
`AssertionError: 'buildings' unexpectedly found in {'version': 1, ..., 'residents': 10989, ...}`.
After the change, with the three carry-back unit tests added:
`PYTHONPATH=Sim python -m unittest Sim.tests.test_settlement_records -v` -> **Ran 9 tests in
73.416s, OK**.

## The alternative that was rejected, and why

The card offered a second option -- repoint `city_layout.buildings` at the `city_plans`
result so `placed_count` reflects plots actually placed -- and the sweep brief asked for the
conservative choice, which for an interchange change means not removing a published field.
**It was rejected because it is not implementable, not because deletion is tidier.**

- The two blocks draw from **different catalogues**. `city_layout.buildings.options` comes from
  `buildings.json` building packs; `city_plans.plots` comes from the per-civilization city
  preset in `civilizations.json`. There is no mapping between them that is not invented.
- They are at **different scales**. One claims whole terrain nodes of the world raster; the
  other places rotated footprints in local metres inside one of those nodes.
- They are built at **different stages**. `city_layout` at stage 9, `city_plans` at stage 16,
  and `Sim/tests/test_city_planner.py::test_fill_does_not_change_population_or_world_layers`
  pins that `fill_cities` writes nothing back into `settlements`. Making stage 9 report a
  stage-16 number would mean either coupling the two stages or breaking that invariant.

Deletion is also the discipline the tree already chose this week: a consumer that reads the
removed field gets a `KeyError` at the line that made the wrong assumption, the way the
`flood` -> `channel` split was deliberately made to fail loudly rather than silently.

## The root cause underneath, which is another card's

`placed_count: 0` is not a planner defect. `_collect_land_anchor_candidates`
(`Sim/icarus_sim/terrain_settlements.py`) walks a band of `max(180, 4 * river_buffer_m + 180)`
**metres** over a raster whose cells are kilometres across, so the search never leaves the
city's own node. The same famine empties `city_layout.features` -- 0 or 1 anchors against
targets of 24 to 43 -- which this card did not name and did not fix. That is a member of
[SCALE-METRE-CONSTANTS-COLLAPSE](../backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md): a constant in absolute
metres authored for an 11 km world. **It should be added to that card's member table.** When
it is fixed, the district plan starts finding anchors again and the asset roll-ups start being
non-zero; nothing deleted here has to come back for that to work.

## Versions and blast radius

`city_layout` 1 -> 2; `city_plans` 7 -> 8 (it moved for the sibling card in the same change).
**`settlements.version` was NOT bumped and should have been**: the gate that would have to
move with it, `world['settlements']['version']!=15`, is in `Sim/icarus_sim/terrain_history.py`,
which this sweep was forbidden to touch. Reported to the orchestrator as a blocked one-line
change. `tests/test_native_world.py` stopped comparing the per-option rows, which
[027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md) rules is not a defect.
`Fixtures/sample-world-v1.json` is stale and was deliberately not rebuilt.

## The claim as it was filed

Found by the Python-output red team reading a generated world as game content
(`docs/reviews/233182e-python-output-red-team.md`, finding 1). Everything below is the
original card, kept because its measurements are the before-picture.

## Observed behavior

Seed 42, size 17, `generator_version` 16. `settlements.sites[].city_layout.buildings.options`
reports, for **all nine cities**:

- `placed_count: 0` against `target_count` totals of 43 to 68,
- three or four options flagged `required` with nothing placed,
- `city_layout.fallback.reason` = *"Not enough valid non-water land anchors for requested feature
  and building placement counts within local search band."*

`city_plans.cities[]`, keyed by `city_uid` to those same nine settlements, holds **82 to 137
placed plots** each — building id, metre position, rotation, footprint, road access, workers and
beds. `npcs` then places 2,236 people into those plots and every one of the 2,236 references
resolves.

So the world has architecture. The record nested inside each settlement says it does not.

## Why it matters

`settlements.sites[]` is where a consumer looks to find out about a settlement, and
`city_layout` is a child of that record. A reader who trusts it concludes the generator failed
to build any city in the world, and a reader who does not trust it has no way to know which of
the two blocks is authoritative without reading both and guessing.

It also poisons the failure signal. A genuine anchor shortage in one city would be invisible,
because the field reports a shortage in all nine.

## Proposed mechanism

Decide which of the two is the product, then make the document say so. Either:

- **delete `city_layout.buildings`** and leave `city_layout` carrying only what nothing else
  emits (`residents`, `river`, `layout_profile_id`, `building_pack_id`), or
- **repoint it** at the `city_plans` result so `placed_count` reflects plots actually placed.

Deleting is the smaller change and the one the evidence supports: no consumer reads
`city_layout.buildings` today, and `city_plans` is the block the schema, the planner tests and
the NPC roster all key against.

Whichever is chosen, a shortfall that is real still needs to surface. `key_locations` already
does this — every archetype appears in `sites` or in `diagnostics` with a reason — and that
pattern is the subject of `PRODUCT-REACHABILITY-REPORT`.

## Dependencies and unresolved decisions

- Whether `city_layout` has a downstream reader nobody has named. The Unreal adapter is the
  obvious risk; it does not exist yet, so this is the cheap moment.
- `settlements.version` is 10 and `city_plans.version` is separate. Removing a published field is
  an interchange change and needs the version bump and the conformance record edit that
  `AGENTS.md` requires.

## Acceptance and evidence

- A generated reference world either contains no `city_layout.buildings` key, or contains one
  whose `placed_count` totals match the plot count in the matching `city_plans` entry.
- A behavioral test asserts that agreement for every city in a reference world, so the two cannot
  drift apart again silently.
- The conformance record owning `Sim/icarus_sim/city_planner.py` states which block is
  authoritative for placed buildings.

## Adversarial review and limitations

Only seed 42 at size 17 was measured, where the coordinator reports the raster is clipped (47
land cells). It is possible — though it does not change the finding — that the anchor search
genuinely fails at this resolution and succeeds at size 33, in which case `city_layout` is
accurate here and still contradicts `city_plans`, which placed 133 plots on the same ground. The
contradiction is the defect either way. Re-measure at size 33 when a document exists.
