# Key locations

Owner: local. State: complete. No delegates.

## Delivered

- A standalone reader package, `Sim/key_locations/`, that reads a finished world's JSON and writes one block, `key_locations`, mutating nothing. Attached at stage 16 and again in `advance_age_request`, beside `heroes`, `story_web` and `npcs`. `FANTASY_WORLD_KEY_LOCATIONS=0` leaves the key absent.
- **Ninety-seven archetypes across eleven families as catalogue data, not code.** Subterranean, extractive, fortification, funerary, sacred, wayside, arcane, lair, drowned, wonder, curiosity. Adding a kind of place is a catalogue edit; if a new kind needs new code, the placement engine is underspecified and that is the bug.
- A location is `(archetype, tier, state, occupant, origin)`, not a noun from a list. **There is deliberately no `dungeon` archetype and no `forgotten` state**: "forgotten fortress" is a fortress that is `ruined` with occupant `none`, and a dungeon is any tier-2 complex with a hostile occupant. Both are outcomes, derived from what the simulation already recorded — a nearby ruin ages a site, remoteness empties it, an unstable weave corrupts it, a nest nearby fills it — and a succession pass lets something move into what the builders left.
- Requirements are **percentile-relative with an absolute floor**, so a world with no volcanism gets no lava tubes *and a diagnostic row saying so*, rather than its least-quiet hillside. Every archetype appears in `sites` or in `diagnostics` with a reason, and the reason distinguishes four outcomes: no ground satisfies the requirements (an authoring fault), the area does not fund one, spacing left room for fewer, or placed.
- **Chains and clusters**, for the places that are wrong when placed alone. Waystones every 2.2 km along each road, march stones every 3.4 km along a political frontier, a beacon line every 9 km gated on a real mutual-sightline check against the heightfield, and pilgrim stations on the approach to the three best sacred complexes; siege works outside ruined forts, cottages beside mines, barrow rings around necropolises, hermit cells around monasteries. `chains[].members` is in walk order and members carry `links.chain_index`, so a consumer reads a chain as a spine.
- Tier-2 sites carry an **interior chamber graph** — depth, role, rough size, connections, flooded and collapsed flags, entrances — in five plans. A graph, not geometry.
- `threat`, an integer 1–5 on the existing creature-tier rubric, so ranking a dungeon against a beast lair compares like with like. Added on request from the quest session, which would otherwise have synthesised a parallel danger number.
- Ninety-seven `marker.key_location.*` identities in the exhaustive asset compiler; registry regenerated. Own schema at `Contracts/schemas/key-locations.schema.json`; `key_location` added to the shared `site_kind` enum in `hero-generator.schema.json` rather than standing up a second vocabulary. Lab panel, family filter, per-family glyphs and chains drawn as connected runs.

## The contract narrowing consumers must know

**The one-location-per-node guarantee now binds only `placement == "node"`.** Every site declares `placement`: `node`, `path` or `cluster`.

Chain and cluster members genuinely cannot be node-snapped. A waystone every 2.2 km on a raster whose cells are 12 km apart would collapse five onto one point; a siege camp 1.5 km from a wall has no cell that satisfies it at all. So they stand at interpolated positions, carry a real `direction`, and use their nearest node only to read the layers beneath them.

Ids stay position-derived and never renumber: `keyloc-<archetype>-<node>` for node sites, `keyloc-<archetype>-<chain key>-<metres along it>` for chain members, `keyloc-<archetype>-<anchor node>-<offset>-<index>` for cluster members. Stable is not immortal — if an age transition drowns a location or destroys the culture that justified it, the id resolves to nothing, and a dangling key means *the place is gone* rather than renumbering. The quest session has adopted that reading for every reference in its own block; it and the closed NPC-ROSTER both hold foreign keys on these ids.

## Acceptance evidence

- **Replay safety, the claim the architecture rests on:** seed 42 with and without `FANTASY_WORLD_KEY_LOCATIONS=0` gives byte-identical `layers` (482baff769dc), `settlements` (ba918854b92f), `ruins` (4931c8f6f48e) and `history` (7d4b121d9aed). The block is a pure reader; nothing upstream moves.
- `Sim/tests/test_key_locations.py`: 61 tests on hand-built worlds. Per-archetype gating, spacing, clearance, budgets, claimed-node dedupe, state and occupant derivation, every succession roll, threat bounds, interior graph connectivity, name uniqueness, chain ordering and interval, beacon sightlines, cluster offsets, and that a composed archetype never also arrives by scatter.
- **Both copied primitives pinned:** `seeds.child_seed` equals `terrain_tectonics.child_seed`; `core/grid` node index, cell, direction and area equal `sphere_grid`/`terrain_globe` at sizes 9, 17 and 33. Package source never mentions `icarus_sim`, asserted by test.
- `attach()` twice is byte-identical; the source world deep-compares unchanged; JSON is finite.
- Conformance on a real generated world: block present, validates, node-placed sites unique and off claimed ground, no two names shared, chains ordered, cluster anchors resolve, and `assertNotIn('key_locations', materialize_stage(world, 15))`.
- Asset list asserts one marker per catalogue archetype, pinned to the catalogue rather than to a count, so markers going missing fails loudly while legitimate growth stays quiet.
- Seed 42, 200 km world: 10 locations at size 17 (47 land cells), 91 at size 33 (268 land cells, 24 tier-2, 13 with a hostile occupant). Fixture world: 324 sites — 38 tier-0, 215 tier-1, 71 tier-2 — 35 occupied complexes, 6 chains, 21 clusters, placement split 217 node / 69 path / 38 cluster, zero duplicate names.
- Provenance revisions appended for `tools/terrain_lab.html` and `tools/terrain_world.js`; `verify_provenance` green across all 79 files. `terrain_history.py` is not pinned — verified, zero manifest hits.

## What this cost four times, and is worth reading before doing area-denominated work

Absolute distances below cell resolution caused four separate defects here, and **every one was silent**.

- Budgets *rounded*. On the legacy 11 km reference world `tools/terrain_lab.py` builds by default (~6 km² of land) every archetype's expectation fell below a half and the whole catalogue rounded to zero at once — ninety rows saying "too small to support one", a block that validated perfectly while containing nothing. Now floor-plus-fractional-draw, the thinned process `terrain_nests` already uses.
- `spacing_cells` multiplied the *actual* cell size, so the same world spaced its caves 25 km apart at size 17 and 6 km at size 129: resolution silently changing content. Now resolved against a fixed reference raster.
- Cluster offsets of 0.6–3.2 km could never resolve on a 12 km raster, so clusters produced **zero**. Fixed by continuous positioning, not by bigger offsets.
- Chain intervals were multiplied by a world-scale factor and came out 18× too large — 61 km between waystones.

Related: **the lab CLI default is not the world `generate_request` builds** (radius 1774 m against 31831 m), and a hand-built fixture is usually mostly land where a real world is ~20%. Both hid these.

A fifth was the same shape in text rather than distance: `{ordinal}` was passed into the naming context but never substituted, so every member of a run produced the same literal string, collided, and fell through to the generic name — **the chain rendered as scatter while looking correct in the data**.

## Limitations and next action

- **Static proposals about ground, not a populated world.** Nothing here acts, spawns, patrols, guards or holds treasure. Interiors are graphs with no metre positions, contents or encounters; a real interior layout is a later phase, the way `city_planner` sits on top of settlements.
- **No `Core/` port**, declared rather than skipped. A client doing in-process native generation will not have this block and needs either the Python export or a port funded as its own ticket. The record shape is deliberately port-friendly: no `pow`, integer modulo before division, stable association order, SHA-256 child seeds.
- Chains follow roads, frontiers and shrine approaches, not rivers or coasts, and a pilgrim approach is the straight run in from the nearest city rather than a routed road. Clusters hang off four anchor kinds. Beacon sightlines ignore the curve of the world.
- **At coarse rasters the node grid binds before density does.** No two node-placed locations share a node, so size 17 with 47 land cells cannot hold the ~196 locations its area implies. Size 33 or finer is representative; the conformance world is the sparse end of the range.
- Tier 0 was zero at every raster before the composition pass, because markers were placed last and lost every remaining cell to larger tiers. That was a *design* error rather than a density one — a waystone belongs on a road at metre intervals, not scattered one per cell — and the prediction that composition would fix it rather than reweighting held: **38 tier-0 sites now place**.
- Names are descriptor templates and this package is a **consumer** of naming, not a second system. `heritage.settlement_name` owns place names; these templates borrow settlement names, so they improve on their own as heritage lands. `chains[].name` is a type label ("Waystone line"), never a proper noun — a pilgrim road that should be *called* something is heritage's surface.
- Four reader packages now carry pinned copies of the sphere-grid helpers. See `board/backlog/SHARED-GEOMETRY.md`; unowned.
- Next action: `test_native_world` must stay green **and unchanged** — if it reddens, something mutated the world and this architecture has been violated. Then the size-33 lab screenshot (`--world_size small`, not size 17, where ten locations undersell it).
