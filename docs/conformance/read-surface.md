---
conformance: 1
record: read-surface
tier: EXERCISED
summary: Answers five bounded questions about a world that already exists, each in kilobytes, without mutating it, minting a version or regenerating it.
modules:
  - Sim/icarus_sim/terrain_read.py
  - Sim/icarus_sim/terrain_read_select.py
emits:
  - path: (not a world block; a read document)
    schema: Contracts/schemas/read-blocks.schema.json
  - path: (not a world block; a read document)
    schema: Contracts/schemas/read-near.schema.json
  - path: (not a world block; a read document)
    schema: Contracts/schemas/read-place.schema.json
  - path: (not a world block; a read document)
    schema: Contracts/schemas/read-person.schema.json
  - path: (not a world block; a read document)
    schema: Contracts/schemas/read-quests.schema.json
versions:
  - id: read-api
    assert: 1
  - id: read-schema
    assert: 1
proof:
  - path: Sim/tests/test_read_surface.py
    establishes: that blocks names every top-level key of a real world and marks registry membership in both directions, that the radius arithmetic reproduces the generator's own neighbour distances, that no read mutates the caller's world by byte comparison, that no read reaches the generator at all, that every place id and every person uid in a generated world resolves, that each join matches the field its writer wrote, that two identical reads are byte identical and a persisted world reads the same as a live one, that a site plan and a key-location plan never share a key or a status vocabulary, that the person index agrees with the quest giver index the tick uses, that liveness agrees with the one predicate over every uid, that each read document validates against its published schema, and that twelve ways of asking wrongly are each refused by name with the shared envelope
decisions:
  - docs/decisions/026-world-handles-and-the-host-store.md
tickets:
  - board/backlog/PRODUCT-READ-SURFACE.md
---

# Conformance: read surface

## What it produces

An answer about a world, rather than the world. Five named reads — `blocks`, `near`,
`place`, `person`, `quests` — each take `{api_version, world, ...}` in the same shape every
other request API in this tree takes, and each answer with its own document of a few
kilobytes. Nothing is written, no version is minted and nothing is regenerated.

The consumer this exists for is a local model packaged inside the game, with finite
context. A generated seed-42 world measures 52.9 MB in the canonical encoding at size 17
phase 16 and 64.7 MB at size 33 with `build_stages` already off — of the size-17 figure,
29.7 MB is `build_stages` and 23.2 MB is what remains once it comes off. Those are this
record's own measurements and they agree with the figures decision 026 now carries for the
same seed and size. The weight is in the planning blocks rather than the terrain, so a world
document grows with city count, which tracks the raster. Either way the model cannot hold
one, so before these reads every question it had was answered by handing it the planet.

It is a closed verb set and not a query language. Every request function in this tree
allow-lists its body keys and refuses an unknown one by name; a parser would throw that
away at exactly the boundary where it is worth most.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `blocks_request(body)` | `terrain_read` | Which blocks this world carries, each one's declared version and encoded size. `POST /world/blocks`. |
| `near_request(body)` | `terrain_read` | What is at, or within a radius of, one terrain node. `POST /world/near`. |
| `place_request(body)` | `terrain_read` | One settlement, hamlet, fortress or key location by id, joins resolved. `POST /world/place`. |
| `person_request(body)` | `terrain_read` | One hero, dread, NPC or villain by uid, liveness resolved. `POST /world/person`. |
| `quests_request(body)` | `terrain_read` | The quest board with giver and anchor resolved. `POST /world/quests`. |
| `READS` | `terrain_read` | The five, by the name their route carries, for a host dispatching on a verb. |
| `block_summary(world)` / `near_rows(world, node, radius_m)` | `terrain_read_select` | The same selections, pure, with no request body. |
| `place_document` / `person_document` / `quest_rows` | `terrain_read_select` | Pure resolution, directly testable. |
| `person_index(world)` | `terrain_read_select` | `uid -> (record, block)` across heroes, dreads, npcs and villains. |
| `node_cell` / `arc_distance_m` / `node_count` | `terrain_read_select` | The grid arithmetic `near` is built on. |

## Inputs it reads

A world document, and nothing else. `blocks` reads any dict. `near` needs `config.size` and
a globe radius. `place` needs `settlements`; `person` needs at least one of `heroes`,
`npcs`, `villains`; `quests` needs the `quests` block that only the time capability writes.

Deliberately **not** `validate_time_world` or `validate_age_world`. Those answer whether a
world can be *changed* and carry contract requirements — a recipe, a phase floor, a grid
ceiling — that describing a world does not need. A read that refused to describe a world it
could describe would be a worse answer than the description. The consequence is stated
under *Does not establish*: these reads will happily describe a world this generator can no
longer advance.

## Artifacts it writes

None. No world block, no `history.operations` row, no handle. A read answers with a
document and the caller's world is the object it was handed.

### Binding invariants

- **No read mutates the caller's world.** Nothing here assigns into the world and nothing
  deep-copies it, so the guarantee is structural rather than defended by a copy. Proven by
  byte comparison of the serialised world across all five reads.
- **No read mints a version.** Decision 026 rules that reads produce no handle and no
  operation envelope. `world_handle.OPERATIONS` already classifies `moon` and `patch` as
  `kind: read` and raises if one is asked for an envelope; these five are the same kind and
  are not in that table, because the table names the verbs a *host* offers and adding them
  there is the host package's change, not this one's.
- **No read regenerates.** `patch_request` rebuilds the entire submitted world from its
  `Config` before cutting a patch, which is why a patch costs what a generate costs. That is
  deliberate for `patch`. The test asserts the absence of that path by replacing
  `terrain_lab.generate` with a function that raises and running all five reads through it,
  rather than by observing that they are currently fast.
- **Every join is resolved against the field the writer wrote**, and the answer carries a
  `joins` list naming the writing site for each one. Equality, never a prefix or suffix
  test: `surface-city-0-10-x` is a prefix of `surface-city-0-100-x` and `hamlet-1` is a
  suffix of `hamlet-11`.
- **A read is a function of the world it was given.** Two identical calls produce byte
  identical documents, and a world round-tripped through JSON — which is the document a game
  actually holds — reads the same as the in-memory one it came from. Both are asserted over
  all five reads.
- **Row order is the writer's order.** Each `near` category is ordered by distance and then,
  by stable sort, by the order its writer produced it. `quests` preserves the `quest_id`
  order `terrain_time` sorts the board into rather than imposing one. `blocks` is sorted by
  name, which is the order the transfer bytes are written in; a world dict's insertion
  order is an artefact of which pass ran first and is published nowhere.
- **Anything a caller may cache across an age boundary spells the node out.** `place`
  carries `anchor.node` and `anchor.id_survives_an_age`, which is false for hamlets and
  fortresses, whose ids are ordinals re-derived every age. `person` carries `anchor.node`
  wherever one is knowable. `near` carries `node` on every row that has one.
- **A plan's `status` is never merged across plan kinds.** `place` answers a city, hamlet
  or fortress under `resolved.plan` and a key location under `resolved.location_plan`, and
  the two are separate `$defs` with separate enums: `complete | partial | unbuildable` for
  the site planners and `complete | empty` for key locations. `complete` is in both
  vocabularies and asks two different questions — was this plan fully placed, and does this
  plan have contents — which is the overload `board/backlog/SDET-STATUS-VOCABULARY.md`
  records. One permissive union under one key would republish that collision at a new
  boundary and hand a consumer a `status` it could compare across blocks. Exactly one of
  the two keys is ever filled, and both are always present.
- **Bounded is a number.** `near` refuses past 512 rows and `quests` past 2048, with
  `over_capacity`, rather than truncating — both have a remedy the caller can apply. `place`
  has no such argument, so its roster posts are projected, capped at 1024, and reported with
  the exact `post_count` and a `posts_truncated` flag beside them.

### The joins, and where each one is written

| Read | From | Into the block | Matched on | Writer |
|---|---|---|---|---|
| place, a city | settlements.sites[].id | `humans.cores` | `site_id` | `Sim/icarus_sim/terrain_humans.py:222` |
| place, a city | settlements.sites[].id | `seasonal_food.models` | `site_id` | `Sim/icarus_sim/terrain_seasons.py:83` |
| place, a city | settlements.sites[].uid | `city_plans.cities` | `city_uid` | `Sim/icarus_sim/city_planner.py:134` |
| place, a hamlet | humans.hamlets[].id | `hamlet_plans.hamlets` | `hamlet_id` | `Sim/icarus_sim/hamlet_planner.py:112` |
| place, a fortress | humans.fortresses[].id | `castle_plans.castles` | `fortress_id` | `Sim/icarus_sim/castle_planner.py:233` |
| place, a key location (under `location_plan`) | key_locations.sites[].id | `key_location_plans.plans` | `location_id` | `Sim/key_locations/core/exterior.py:190` |
| place, anything staffed | npcs.sites[].uid | `npcs.people` | `site_uid` | `Sim/npc_roster/__init__.py:91` |
| near, travelling groups | encounters.by_node | `occupancy` then entries | `entry` | `Sim/icarus_sim/terrain_encounters.py:89` |
| near, distance | the node direction | great-circle metres | `neighbors` | `Sim/icarus_sim/terrain_erosion.py:30` |
| person and quests | a uid | heroes, dreads, npcs, villains | `uid` | `Sim/icarus_sim/terrain_time.py:269` |

Four of these are traps rather than lookups, and each is recorded where it is resolved.

`humans.cores[].site_id` and `seasonal_food.models[].site_id` coincide with list position on
every world measured, because both lists are appended in site order. The field is matched
anyway, so the coincidence stays a coincidence instead of becoming a dependency.

`hamlet_plans.hamlets[].hamlet_id` is the hamlet's own id and **not** `hamlet-<node>`:
`humans.hamlets[].id` is `hamlet-0` for inland sites and `coastal-1-0` for coastal ones, and
the plan carries whichever the hamlet had. Matching by node would agree on a size-17 world —
both lists are one to one over nodes — and would be a different question.

`core_id` on a hamlet or fortress is a **position** in `settlements.sites`, not a uid. The
small-site builder stores `owner[i]` and the planners dereference it by index;
`Sim/npc_roster/sites.py:66` records the same trap. The index is checked against that site's
own `id` before it is used, because `site['id']` equalling its index is an invariant
(`docs/conformance/settlement-founding.md`) rather than something to assume here.

A cast presence names a city uid, and an age advance ruins cities: the record moves from
`settlements.sites` to `ruins` keeping the same uid and the same node, and
`terrain_history` mints the ruin's own id as `'ruin-' + uid`. So `person` resolves a
presence against the standing cities first and then against `ruins[].uid`, which is the
same fact `Sim/npc_roster/sites.py:194` reaches by trying the `ruin-` prefix, without the
string surgery. Four people on the measured world stand at a ruin and would otherwise have
been placed nowhere.

`npcs.sites[].uid` is the settlement uid for a city but `hamlet-node-<node>` and
`fortress-node-<node>` for the small sites, minted that way at `Sim/npc_roster/sites.py:100`
and `:116` precisely because the ordinal ids renumber. So `place` builds the roster key from
the kind and the node and reports it as `anchor.roster_key`; a caller never has to know the
two id spaces exist.

### Facts that look incidental and are load-bearing

- **Two things standing on one node are at distance zero by identity, not by arithmetic.**
  `acos` loses about half its digits next to a dot product of one, so a cell measured
  against itself geometrically comes out roughly four tenths of a millimetre away on a
  31.8 km-radius world, and scales with the radius. Measured that way, a zero-radius `near`
  at a city node returns nothing and looks like an empty neighbourhood. Two tests failed on
  exactly this before the identity case was added.
- **The `near` radius ceiling is a property of the planet, not of the raster.**
  `effective_config.globe_radius` is 31830.99 m at both size 17 and size 33, so the ceiling
  is the same 15915 m on both. Grid size changes how many cells the radius crosses, never
  how far it reaches.
- **`blocks` walks the world, not the registry.** A report built from `STATE_KEYS` would
  omit a block a world carries and the registry does not, which is the `materialize_stage`
  failure `docs/conformance/nomads.md` and `docs/conformance/time-advance.md` both document.
  Here such a block appears with `registered: false`, and the registered blocks a world does
  not carry appear in `absent`.
- **A block JSON cannot carry is named rather than raised.** A non-finite float makes a
  world unnameable by any host; `blocks` reports it as `encodable: false` and lists it under
  `unencodable`, because which block holds it is the useful half.
- **`person_index` appends `villains` after the three lists `terrain_time._giver_index`
  walks**, keeping first-writer-wins for those three. Every uid the tick's index resolves
  therefore resolves to the same record here, which is asserted directly. Giver resolution
  disagreeing with the capability that closes a quest when a giver is gone would be silent.

### Refusals

Every refusal raises `terrain_errors.RequestError` and carries the shared envelope; no new
error shape exists. `api_version` carries `retry: false`, and so does a missing block,
because resending the same world will not produce one.

| Asking | Shape |
|---|---|
| a body that is not an object | `wrong_type` |
| an unknown request field | `unknown_field`, with the nearest names |
| an `api_version` this producer does not speak | `unsupported_api`, `retry: false` |
| a `world` that is not an object | `wrong_type` |
| a missing node, or a node or radius that is not a number | `wrong_type`, naming the field |
| a world with no `settlements` / no cast / no `quests` | `missing_block`, `retry: false` |
| a node off this world's grid | `refused_by_world`, naming the node count |
| a radius above half this world's globe radius | `refused_by_world`, naming the ceiling |
| a negative radius | `out_of_range`, with the clamp |
| a place id or person uid that does not exist | `unknown_field`, with the nearest ids |
| a quest state outside the vocabulary | `invalid_choice`, listing it |
| a query past the row ceiling | `over_capacity`, naming the ceiling |

A world carrying no `quests` block is refused as `missing_block` rather than answered with
an empty board. No quests and no quest lifecycle are different facts, and a controller that
cannot tell them apart concludes the world is quiet when it has simply never had a clock.

## Where it runs

Not part of generation and not part of any mutation. Only when a caller asks, through the
five `POST /world/*` routes in `tools/terrain_lab.py` or through the five request functions,
against a world the caller already holds.

It adds no writer to any block. It is a **new reader** of `settlements`, `humans`,
`seasonal_food`, `city_plans`, `hamlet_plans`, `castle_plans`, `key_locations`,
`key_location_plans`, `beast_nests`, `encounters`, `magic.networks`, `npcs`, `heroes`,
`villains`, `ruins`, `layers` and `quests`, and of `terrain_history.STATE_KEYS`. None of those records needed
widening: a new reader changes nothing about when a block is stable.

## Versions asserted

| What | Value |
|---|---|
| Read request API | <!-- conformance:version read-api=1 --> |
| Read document schemas | <!-- conformance:version read-schema=1 --> |

The five read documents are schema'd; the blocks they describe are not. That is the choice
the card left open, taken deliberately. Of the 49 blocks in `terrain_history.STATE_KEYS`,
seven have a schema file of their own — `beast_movements`, `encounters`, `key_locations`,
`key_location_plans`, `nomads`, `story_web`, `villains` — and the rest reach
`world-output.schema.json` as a declared property, which for most of them is a type and a
sentence. Blocking five reads on forty-two schemas would trade a shipped surface for a
registry `board/backlog/PRODUCT-BLOCK-REGISTRY.md` already owns. So each read declares its
own document at its own boundary, and a generator row carried through verbatim is typed as
an object rather than described a second time and allowed to drift.

## Proven by

`Sim/tests/test_read_surface.py`, 55 test methods in four classes: 7 block accounting,
2 geometry, 12 refusals, 34 against a world. Counts are description, not invariant; recount
rather than trusting this sentence.

Twenty-one are pure and need no world: block accounting on a synthetic world, the grid
arithmetic checked against `sphere_grid`'s own neighbour distances, and every refusal. The
row-ceiling refusal is driven from a synthetic world on purpose — seed 42 tops out at 314
rows inside the full radius ceiling at both sizes measured, so a test that only asked a real
world for a wide neighbourhood would pass while the branch it claims to cover never ran.

The other thirty-four use one size-17 seed-42 world, advanced by one day so a quest board exists.
They sweep rather than sample: every place id, every person uid, `near` at every city node.
A join that is right for the first row and wrong for the hundredth looks exactly like a join
that works. `FANTASY_WORLD_READ_BASE` names a pre-generated world so a developer iterating
does not pay ninety seconds again; the default path generates, because a test whose evidence
depends on a file being present proves nothing on a machine that has not got one.

Each read document is validated against its published schema with `tests/schema_subset.py`,
the repository's own standard-library validator, which raises on an unsupported keyword
rather than passing silently. The validator was checked against a deliberately corrupted
document before the result was believed.

### Measured cost and size

Seed 42, phase 16, CPython 3.12.10 on Windows 11 (26200), development machine, with several
other sessions generating worlds concurrently — so these are upper bounds on a contended
box rather than best-case figures. Best of three per read.

| Read | size 17 | size 33 |
|---|---|---|
| generate the world | 89.5 s | 226.0 s |
| `blocks` | 628.74 ms, 8 087 B | 734.43 ms, 7 973 B |
| `near`, quarter of the ceiling | 0.42 ms, 6 986 B | 1.33 ms, 7 603 B |
| `place`, a city | 10.36 ms, 55 703 B | 8.80 ms, 10 479 B |
| `person`, an NPC | 0.16 ms, 555 B | 0.37 ms, 556 B |
| `quests`, whole board | 0.24 ms, 32 087 B | 1.26 ms, 151 584 B |

Swept: 164 place ids at size 17 and 462 at size 33, worst answer 60 976 B; 2 368 person uids
at size 17 and 4 632 at size 33, worst answer 6 786 B; `near` at every city node at a
quarter of the ceiling, worst answer 156 450 B, none refused.

**The byte ceiling is 512 KiB per answer**, and the worst measured answer is 156 450 B.

**Four of the five reads are at least three orders of magnitude cheaper than a generate on
the same world. `blocks` is not**: it is 142× cheaper at size 17 and 308× at size 33, which
is two to two and a half orders. A byte count that was estimated would not be a byte count,
so `blocks` serialises the world once, and on a world still carrying `build_stages` that
single key is most of the work — 29.7 MB of the 52.9 MB measured at size 17. It appears in
the report as its own row so a caller can see why. This is the card's cost acceptance not
being met, stated rather than rounded.

## Why it works this way

The gap was never one round trip. The joins are the caller's: `settlements.sites[].id` is
the key three other blocks file their rows under, a quest's `giver_uid` is resolved by the
writer across `heroes.people`, `heroes.dreads` *and* `npcs.people`, first writer of a uid
winning — the card describes it as resolving into `heroes`, which is narrower than the index
`terrain_time` actually walks, though on the measured world all 49 givers happen to be
heroes — and `encounters.by_node` indexes an `occupancy` list that indexes an `entries`
list. A
consumer that wanted one city had to hold every block those joins reach and reimplement each
one correctly against a vocabulary where `tier` means four things and `status` names five.
Resolving them here costs one implementation instead of one per consumer, and the one here
is the only one that can name the writing site it mirrors.

The split into a pure selector and a request module is the `terrain_time_schedule` /
`terrain_time` pattern. It matters more here than there: the join argument and the ordering
argument are the whole product, and on the pure side they are checkable in milliseconds with
no world at all.

`blocks` landed first because it is the only read with no join, and therefore the only one
that cannot be subtly wrong. It is also the one a controller calls first, since it is what
makes the other four discoverable.

## Does not establish

- **That `blocks` is cheap.** It is two orders below a generate, not three. See the cost
  table. A caller that wants a cheap answer on a profiled world should strip `build_stages`
  first, which is what the transfer form does anyway.
- **That a read refuses a stale world.** There is no `generator_version` gate. A world this
  generator can no longer advance can still be described by all five reads, deliberately,
  because describing a world is not changing it. A host resolving a handle is where decision
  026 puts the staleness refusal, and that is the far side of this boundary.
- **Anything about the size-257 world.** Nothing here has been measured above size 33.
- **That `near` is bounded by construction.** It is bounded by a declared ceiling and a
  refusal. No generated world measured has reached the row ceiling, so the refusal is proven
  by a synthetic world and the ceiling's adequacy on a dense world is not established.
- **That `place` returns a plan.** It returns the plan's identity, status, plot count and
  size in bytes, never its body. A city plan is most of a megabyte on a size-17 world.
- **That a roster post's `status` is translated.** `place` carries `npcs.people[].status`
  verbatim, which is the roster's own `alive | dead` and one of five `status` vocabularies
  in this tree. It is declared with exactly that enum rather than folded into a common one,
  because folding it would be this boundary inventing the translation
  `board/backlog/SDET-STATUS-VOCABULARY.md` says does not exist in public. `person` is the
  read that answers liveness once, through `terrain_liveness.liveness`.
- **That the roster covers key locations.** It does not; `npcs.sites[].kind` is city, hamlet
  and fortress only. `place` for a key location reports no roster key and no posts rather
  than inventing one.
- **That a hero's anchor always resolves.** A cast presence naming a camp, college, port,
  shrine or nest resolves to no settlement and to no ruin, and the read reports
  `anchor.unresolved_uid` rather than falling back to the person's home — the home is a real
  place and the wrong one. On the measured world 6 of 2 368 people carry no node anchor, and
  all six name nowhere at all rather than naming somewhere unresolvable.
- **That any read document is *true*.** The schemas establish shape. That a resolved core is
  the right core is established by the sweep, and that the sweep asks the right question is
  established by the writing sites named beside each join and by nothing else.
- **No native side.** `Core/json.hpp` has no floating-point case, so an Unreal host cannot
  serialise a world document, let alone serve a read over one. Python only, and no parity
  with a native implementation is claimed because none exists.
- **That a quest giver can be an NPC.** The index this read resolves givers through spans
  `npcs.people` because `terrain_time._giver_index` does, but on seed 42 at size 17 all 49
  givers are heroes, so that branch is reachable and unexercised by the measured world.
- **Nothing about the browser lab's own UI.** The five routes answer JSON; no panel in
  `tools/terrain_lab.html` calls them.
