# CONTENT-CITY-LAYOUT-DEAD-BLOCK — every city reports it has no buildings, beside a planner that built them

Owner: none. State: open, unowned. Found by the Python-output red team reading a generated world
as game content (`docs/reviews/233182e-python-output-red-team.md`, finding 1).

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
