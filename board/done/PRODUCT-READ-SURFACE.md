# PRODUCT-READ-SURFACE — a caller can name a world and still cannot ask what is in it

> **CLOSED 2026-09-21 — delivered, and the board had not noticed.** `docs/conformance/read-surface.md`
> stands at tier `EXERCISED` over `Sim/icarus_sim/terrain_read.py` and `terrain_read_select.py`, with five
> schemas and 76 tests. Measured on the run: seed 42 size 17 answers in `blocks=8229, near=7540,
> person=6590, place=60234, quests=28806` bytes, against the 64.6 MB whole-world document this card was
> filed about. Verified by [the 2026-09-21 reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

Owner: none. State: open, unowned. Named as the critical path by
[decision 026](../../docs/decisions/026-world-handles-and-the-host-store.md), which ruled the
store and deliberately left this open.

## Requested behavior

A bounded read API over one world. A caller asks a question about a world that already
exists; the answer is kilobytes, is a document in its own right, and is not a world. No read
mints a version, no read mutates, and no read regenerates.

## The gap

Ten POST routes exist. Eight take a whole world and return a whole world. Two — `/world/moon`
and `/patch` — answer with their own document, and neither answers a question about a world's
contents: `moon` is a closed-form almanac query and `patch` cuts a local mesh. The lab's GET
routes are `/` and `/generate`, and both answer HTML. There is no route that answers *what is
near this node*, *who is in this city*, *what quests are open*, or even *which blocks does
this world carry*.

Decision 026 states the consequence in its own words:

> A caller that can name a world still cannot ask what is in it without receiving all of it.
> That is the next package and it is the critical path; a handle without reads is a hand
> without eyes.

The arithmetic that makes it critical was understated everywhere until 2026-09-21, and is now
half-corrected. Decision 026 has been re-measured and states the smallest world anyone
generates — seed 42 size 17 phase 16 — as 52.9 MB generated, 29.7 MB of it `build_stages`,
**23.2 MB in the transfer form**, 5.1 MB gzipped. Measured the same day on the seed-42
**size 33** sample: 147.4 MB total, 82.7 MB `build_stages`, **64.6 MB of world proper**.

What has **not** been corrected is `Sim/icarus_sim/terrain_time.py:60`, whose `COST_BASIS_MB`
is still 30 MB at size 129 against 116 MB at 257 — figures 026 itself now flags as predating
several changes. That one is code rather than prose: it feeds `cost_estimate`, so a caller
asking what an age advance will cost receives a number derived from a world size that no
longer describes anything. It needs its own card.

The mechanism matters more than the multiple, because it says which way the curve bends. The
weight is not in the terrain: `layers` is 1.9 MB. It is in the planning blocks — `city_plans`
18.6 MB, `hamlet_plans` 11.2 MB, `world_scene` 10.1 MB, `wildlife` 5.1 MB, `castle_plans`
4.8 MB. City count tracks the raster at roughly 0.035 × cells
([PERF-CITY-COUNT-TRACKS-RASTER](../backlog/PERF-CITY-COUNT-TRACKS-RASTER.md)), so the blocks that
dominate a world document grow with the grid and the consumer's problem gets worse exactly as
the world gets good enough to play in. Those figures are description, not invariant, and a
figure quoted anywhere states its seed, size and machine.

The named consumer is a local model packaged inside the game with finite context. It cannot
hold a world, so every question it has today is answered by handing it the planet.

The gap is worse than one round trip, because the joins are the caller's, and they are not
uniform. `humans.cores` and `seasonal_food.models` each carry a `site_id` **field**
(`terrain_humans.py:222`, `terrain_seasons.py:83`) and a reader must join on that field — while
other generator code indexes the same lists **positionally** (`terrain_seasons.py:88` reaches
`models[a]` and `sites[a]` from a road's endpoints; `terrain_humans.py:225` reaches
`site_profiles[site['id']]`), which is precisely why `settlement-founding.md` makes
`site['id'] == index` a binding invariant. A reader that copies the positional form inherits an
invariant it cannot enforce. `heroes.quest_hooks[].giver_uid` does **not** resolve into
`heroes` alone: `terrain_time._giver_index` resolves across `heroes.people`, `heroes.dreads`
and `npcs.people`, first writer of a uid winning, and on seed 42 size 17 every giver happens to
be a hero, so the npc branch is reachable and unexercised. `encounters` carries `by_node` and
`by_month` indices into an `occupancy` list that indexes an `entries` list. A consumer that
wants one city must hold every block those joins reach and reimplement each of them correctly,
against a vocabulary where `tier` means four things
([PRODUCT-CONSUMER-VOCABULARY](PRODUCT-CONSUMER-VOCABULARY.md)) and `status` names five
([SDET-STATUS-VOCABULARY](../backlog/SDET-STATUS-VOCABULARY.md)).

## Proposed mechanism

### A closed verb set, not a query language

Every existing request function allow-lists its body keys and refuses an unknown one by name.
A query language throws that away at exactly the boundary where the failure envelope is the
product's best feature, and it commits the repository to a parser and an evaluation model
before it has a single reader. Five named reads, each backed by a block that already exists
and each with its own allow-list, cost less and refuse better.

1. **`blocks`** — which blocks this world carries, each one's declared version and its size in
   transfer bytes. This is the read that makes every other read discoverable, and it is the
   one a controller calls first. It is also the cheapest honest answer to "what is in this
   world", and it needs no join.
2. **`near`** — what is at, or within a radius of, a terrain node: the layer fields at that
   cell, plus the settlements, `key_locations`, `beast_nests` sites, ley nodes and
   `encounters` occupancy rows that fall inside it. `encounters.by_node` already exists for
   exactly this question — the NOMADS card shipped it so "a future quest handler can ask what
   is near here and when" — and this read is that handler's front door.
3. **`place`** — one settlement, hamlet, fortress or key location by id, with the rows that
   join to it **resolved**: its `humans` core, its `seasonal_food` model, its plan block, the
   `npc_roster` posts staffed there. The joins are the generator's own and belong on this
   side of the boundary.
4. **`person`** — one hero, NPC or villain by uid, with liveness resolved through
   `terrain_liveness.liveness`, which already dispatches on the block a record came from and
   already refuses a record carrying `people`, `quest_hooks` or `policy_revision`. A caller
   must never have to know which of the five `status` vocabularies applies to the record it
   just received.
5. **`quests`** — open, taken and recently closed quests with giver and anchor resolved, from
   the `quests` block the time capability writes.

Each read takes `{api_version, world, ...}`, exactly like the eight mutators, so the glue a
host writes to resolve a handle into a document is the same glue, and `icarus_sim` still never
learns what a handle is.

### Split as the rest of the tree splits

Pure selection in one module, request validation and assembly in another, on the
`terrain_time_schedule` / `terrain_time` pattern. A selector takes a world and arguments and
returns rows; it does no validation, raises nothing versioned, and is directly testable
without a request body.

### What a read must never do

- **Never mint a handle.** Decision 026: reads produce no version.
- **Never mutate.** `consumer_orchestrator.py` already asserts a call never touches the
  caller's world; the reads inherit that assertion rather than restating it.
- **Never regenerate.** `patch_request` rebuilds the entire submitted world from its `Config`
  before cutting a patch, which is why a patch costs what a generate costs. That is a
  deliberate property of `patch` and must not be copied into a read whose whole purpose is to
  be three orders cheaper than a generate.
- **Never invent a join.** A read resolves a join by reading the field the writer wrote. A
  near-miss — `endswith` for equality, `id` where the writer keyed on `kind` — silently answers
  a different question and looks correct.

## Dependencies and unresolved decisions

- **[PRODUCT-BLOCK-REGISTRY](PRODUCT-BLOCK-REGISTRY.md).** That card's headline figure is
  stale and this one must not requote it. Measured 2026-09-21: `len(STATE_KEYS)` is **49**, not
  48, and `world-output.schema.json` declares **56** top-level properties against **16**
  required — so every `STATE_KEYS` block is now at least declared, which was not true when the
  card was written, and [SDET-WORLD-SCHEMA-SURFACE](../done/SDET-WORLD-SCHEMA-SURFACE.md)'s "requires
  six keys, declares ten of forty-eight" is stale in the same way. The live question is
  narrower: a read that returns a block's rows publishes them at a new boundary. Decide whether
  each read is schema'd at its own boundary — the cheaper answer, and it does not wait — or
  whether the reads block on the registry. Recommended: schema the *read documents*, not the
  blocks, and say so.
- **[PRODUCT-CONSUMER-VOCABULARY](PRODUCT-CONSUMER-VOCABULARY.md) and
  [SDET-STATUS-VOCABULARY](../backlog/SDET-STATUS-VOCABULARY.md).** `place` and `person` resolve joins
  across blocks that disagree on field names. This is where a translation gets chosen. Choosing
  one silently is worse than reporting both, and the card must state which.
- **[SDET-SITE-ID-ORDINALS](SDET-SITE-ID-ORDINALS.md).** Hamlet, fortress, plot, nest and
  culture ids all renumber at an age boundary. Anything a read returns that a caller may cache
  across a boundary keys on the terrain node and spells the anchor out.
- **No store exists.** These reads take a world document, exactly like the mutators. Handle
  resolution is the host's and is out of scope here.
- **No native side, and none is owed.** Under
  [decision 027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md), ruled
  2026-09-21, the `Core/` port happens at the end of the project as a full rewrite, no Python
  change owes it anything, and the current native divergence is not a defect and not a hold.
  This card is Python, states so, and writes no C++ speculatively.

## Files and assets in scope

- New: a pure selector module and a request/glue module under `Sim/icarus_sim/`.
- New: read-document schemas under `Contracts/schemas/`.
- Edit: `tools/terrain_lab.py` — route registration only, one insertion beside the existing
  POST allow-list and its dispatch chain.
- New: `tests/` coverage, and `docs/conformance/read-surface.md`.
- Edit: `docs/README.md` map entry; `board/README.md` line.

## Acceptance and evidence

- Every read answers within a stated byte ceiling on a size-33 world, and the ceiling is a
  number in the record, not the word "bounded".
- No read mutates: byte comparison of the caller's world before and after, for all five.
- Every id any read returns resolves in the same world, swept rather than sampled.
- Refusals carry the shared envelope: unknown field, unknown id, node off the grid, and a
  world missing the block asked for refused as `missing_block` rather than answered empty.
- Cost: each read is at least three orders of magnitude below a generate on the same world,
  reported with seed, world size and machine.
- `blocks` agrees with `terrain_history.STATE_KEYS` — a block present in a world and absent
  from the report is the `materialize_stage` failure mode that `nomads.md` and `time-advance.md`
  both already document, arriving at a new surface.

## Documentation impact

New conformance record `docs/conformance/read-surface.md`, claiming its modules. Decision 026's
"What this does not decide → The read surface" retargeted at this card. `docs/README.md` map
entry. `board/README.md` line.

## Adversarial review and limitations

- **Resolving a join is writing a second implementation of it.** The writer's join is the
  specification; a read that recomputes it from a plausible-looking field answers a different
  question and looks right. Every resolved join names the writing site it mirrors.
- **"Bounded" is a claim that needs a number.** A `near` with a large radius on a dense world
  is not bounded by construction; the radius takes a ceiling and the ceiling is tested.
- **A read surface publishes every block it touches.** Thirty of them have no schema today.
  This card makes that visible rather than causing it, but it does make it visible.
- **`blocks` is the only read with no join, and it is therefore the only one that cannot be
  subtly wrong.** Land it first; it is also the one that unblocks a controller soonest.
- Tier is `EXERCISED` at best. No native side exists and none is claimed.
- Determinism, draw and iteration order and id stability across ages are invariants and bind
  this work; a read that sorts differently than the writer iterated is a contract change.

## Sources consulted

`docs/decisions/026-world-handles-and-the-host-store.md`, `docs/conformance/world-handles.md`,
`docs/conformance/time-advance.md`, `docs/conformance/settlement-founding.md`,
`docs/conformance/request-failures.md`, `tools/terrain_lab.py`,
`Sim/icarus_sim/terrain_encounters.py`, `Sim/icarus_sim/terrain_patch.py`,
`Sim/icarus_sim/terrain_liveness.py`, `Sim/icarus_sim/terrain_time.py`.
