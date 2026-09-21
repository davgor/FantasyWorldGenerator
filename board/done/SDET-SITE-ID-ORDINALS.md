# SDET-SITE-ID-ORDINALS — a cast uid follows a position in a list that is re-sorted every age

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** `id == index` holds for all 35 sites. Sites do carry a `uid`, but it embeds the ordinal (`surface-city-0-322-elf`), so it is not independent of position.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: reader-packages sweep, 2026-09-21. State: **DONE — slice one delivered. The producer is
unchanged and still emits ordinals; the consumer no longer spends them.**

## Delivered 2026-09-21 — the cast is anchored on the terrain node

`Sim/tests/test_site_id_stability.py` **passes unmodified.** It was run green before any prose in
it was touched: 5 tests, 0 failures, 0.071 s, no world generated. Before the change it was 5
tests / 3 failures, with these messages:

- `test_the_castellan_of_a_fortress_that_did_not_move_keeps_its_uid` —
  `'hero-castellan-fortress-0' != 'hero-castellan-fortress-1'`
- `test_a_uid_does_not_come_to_mean_a_different_place` —
  `{'hero-castellan-fortress-0': (13, 14)} != {}`
- `test_a_castellan_is_anchored_to_its_fortress_by_something_that_persists` —
  all four fields named: `uid: 'hero-castellan-fortress-1'`, `presence.uid: 'fortress-1'`,
  `claim.target_uid: 'fortress-1'`, `deeds[0].event_id: 'fortress-1'`.

Both controls passed before and after, so the three greens are the product moving and not the
harness losing sight of anybody.

`hero_generator.wells.countryside.anchor(site, kind)` builds `f'{kind}-node-{node}'` and
`_reeve` and `_castellan` spend it in **all four** places at once — `uid`, `presence.uid`,
`claim.target_uid`, `deeds[].event_id`. Repairing `uid` alone would have left three ways to
join the wrong row, which is this card's own contribution and the part a partial fix misses.

The spelling is `npc_roster/sites.py`'s, deliberately and not by coincidence: a cast presence at
a hamlet or a fortress **is** a roster site uid now, and a new test calls the roster's own row
builder rather than restating its format, so the two cannot drift apart silently again.

### Second failing test, written before the change

`Sim/tests/test_hero_countryside.py::SiteAnchorTests`, three tests, all red first:

- `test_no_countryside_field_carries_the_ordinal_site_id` — reported eight offenders across both
  roles: `('castellan', 'presence.uid'): 'fortress-0'` and its three siblings, and the same four
  for the reeve on `hamlet-1`. The card asserted hamlets had the identical defect through
  `_reeve` and that it was not separately tested; it is now.
- `test_both_roles_key_on_the_node_with_the_anchor_spelled_out` — `StopIteration`, because
  `hero-reeve-hamlet-node-150` did not exist.
- `test_the_cast_anchor_is_the_key_npc_roster_already_writes` —
  `Items in the first set but not the second: 'hamlet-1', 'hamlet-0', 'fortress-0'`.

All three pass. `Sim/tests/test_hero_countryside.py` is 8/8, and the four reader-package modules
plus `test_site_id_stability` are 232/232 together.

### Re-measured, because the card's node-occupancy figures were stale

On the current `Fixtures/sample-world-v1.json` (seed 42, size 33, generator 16, humans 9):
**98 hamlets and 56 fortresses, zero duplicate nodes within either kind, and zero fortresses
sharing a node with any hamlet** (the coordinating brief's "28 of 56 used to" is confirmed as no
longer true). The kind prefix is nonetheless load-bearing: on
`Artifacts/npc-roster/sample-size65-seed42.json` (size 65) **18 nodes carry both a fortress and
a hamlet**, so `fortress-node-<n>` and `hamlet-node-<n>` must stay distinct keys. Both figures
are recorded in `anchor`'s docstring so the next reader does not re-derive them.

### Decisions made on the owner's behalf — reverse these if you disagree

1. **The ordinal is not carried on the person as a convenience field.** *Rejected: adding
   `presence.plan_id`, the precedent `npc_roster` sets on its site rows.* On a site row the
   ordinal sits beside the node and the kind, so it cannot be mistaken for identity. On a person
   record it would be a bare number in the block a consumer reaches for first, which is the exact
   confusion this card exists to remove. The ordinal is still recoverable by joining the node
   against `humans.hamlets` / `humans.fortresses`.
2. **`heroes` was not bumped by this change, and it did not need to be — the bump had already
   happened in the same uncommitted tree.** A uid format change is consumer-visible and `heroes`
   is a published contract, so the bar calls for an increment. Checked rather than assumed:
   `git show HEAD:Sim/hero_generator/__init__.py` has `VERSION = 1`, and the working tree has
   `VERSION = 2`, bumped by the concurrent quest-contract session along with
   `Contracts/schemas/hero-generator.schema.json`'s `version.const` and a
   `<!-- conformance:version heroes=2 -->` marker in `docs/hero-generator.md`. **Neither 1 nor 2
   has shipped**, so version 2 is the unreleased version this uid change lands inside, and one
   increment covers the quest contract, this re-key and the hero diagnostics from
   CONTENT-NO-ANTAGONIST rather than three.
   **One thing is still owed and is not mine to add:** `version-bindings.json` has no `heroes`
   binding, so that marker resolves against nothing and the checker cannot catch a stale one.
   No schema edit was needed for the re-key itself: `presence.uid` is declared
   `{"type": "string"}` with no pattern.

### Blast radius — discharged, and not

Discharged:
- `Sim/npc_roster/sites.py` — the module docstring named the cast as the package that does not key
  positionally, which the card required to change in the same commit. Rewritten, along with
  `places()`'s docstring: hamlets and fortresses now join directly, and `places()` survives for
  ports, ruins, shrines, camps, colleges and nests, which are still in their own id spaces.
- `docs/hero-generator.md` — the countryside uid column and a new paragraph stating the rule.
- `Sim/icarus_sim/terrain_time.py`, `docs/time-advance.md`, `docs/conformance/time-advance.md`,
  `docs/conformance/actor-scale-writes.md` — all four cited `hero-reeve-hamlet-0` as the worked
  example of a positional uid the regenerated cast re-mints identically. The *mechanism* is
  unchanged and the reaping still does not depend on ids disappearing; only the literal was
  stale, so only the literal moved, to `hero-reeve-hamlet-node-<n>`.
- `Sim/tests/test_npc_roster.py`'s `hero-castellan-fortress-0` literals were **not** moved, as the
  card required. They are hand-built inputs to that module's synthetic world, `npc_roster` was not
  changed, and that module is 68/68 green.

**NOT discharged, and blocked rather than forgotten:**

- ~~`tools/terrain_world.js:137` `heroSite()`~~ **— discharged 2026-09-21 under a lifted fence.**
  It resolved `p.presence.uid` with `(data.humans?.fortresses||[]).find(c=>c.id===u)`, and `c.id`
  is the ordinal, so castellan and reeve pins would have vanished from the lab map and the click
  inspector — silently, because it fails soft on `if(!s)continue` and no test covers it. The two
  branches now read `(c.uid||c.id)===u`. The fallback is deliberate **here** and would have been
  wrong in a test: this is a renderer that must keep drawing a `world.json` saved before the uid
  existed, where both sides of the comparison are still the ordinal. Patched at byte level with
  the CRLF preserved (`git check-attr text` reports `unset`, so line endings are part of the
  pinned hash). `provenance/extraction-manifest.json` **was not touched**; the orchestrator owns
  that row. New sha256 `cfb10b38b66f09e45a10967a2d75828d210b27f2569ef184dd0396f3707a98ab`.
- **`docs/npc-roster.md:73`** still says the cast builds `hero-castellan-fortress-36` on the
  ordinal fortress id and that a bare `fortress-36` cannot be joined. That is now false. The file
  is fenced to the naming session.
- **`Fixtures/sample-world-v1.json` and `Artifacts/npc-roster/sample-size65-seed42.json` are
  stale.** Every castellan and reeve uid moves, and in `npcs` the effect is larger than a rename:
  `npc_roster/__init__.py:183` picks `site_uid` as the first of `(home, presence.uid)` that names
  a known site, so a castellan's `site_uid` stops falling back to the home city and becomes the
  fortress, and the `cast_located_by_presence` counter stops counting them. That is the workaround
  `places()` was maintained for, working for the first time — but it is a change in emitted output
  and both artifacts need regenerating. Neither was rebuilt here; the orchestrator rebuilds once.
- **`Sim/icarus_sim/terrain_society.py:215` extends `humans.hamlets` with coastal port rows that
  carry no `uid`** — 24 of the 98 hamlets on the seed-42 size-33 world. They can never carry a
  deed, so nothing is broken, but they are the reason
  `tests/test_world_schema_conformance.py` has to exclude `sea_node` rows explicitly. One line in
  `_ports` would let that exclusion be deleted. That file is **fenced to the sample-world session
  and provenance-pinned**, and the fence lifted for this change covered `terrain_humans.py` and
  `tools/terrain_world.js` only.
- **`terrain_read_select._near_small_sites` under-reports.** It emits
  `id_survives_an_age: False` and does not carry the `uid` that does survive, so a `near` consumer
  is told the handle it has is unstable and not told which one is not. Additive to
  `read-near.schema.json`, which belongs to `PRODUCT-READ-SURFACE`; noted in the function's
  docstring and left to that lane rather than taken in passing.
- **`terrain_nomads.py:356` `prize_uid` moves silently**, from `hamlet-3` to `hamlet-node-301`,
  because it reads `prize.get('uid') or prize.get('id')` and the rural row now has a uid. Checked
  rather than assumed: `prize_uid` appears in no test, no schema, no document and no other module,
  so nothing reads it and nothing pinned it. The direction is right — it is a raid target held
  across ages — but it is real drift in the `nomads` block and it goes into the one rebuild.
- **`npc_roster/sites.py:places()` changes behaviour on generated worlds, and that is the repair
  landing.** It indexes `row.get('uid') if ... else row.get('id')` over `humans.hamlets` and
  `humans.fortresses`, so a castellan's `presence.uid` now resolves there instead of falling to
  `cast_presence_unresolved`. `test_npc_roster` builds rural rows by hand without uids, so it
  still exercises the `id` fallback and stays green — which also means the fixture does not cover
  the new path.
- **Not established, unchanged from the card as filed:** that a real generated multi-age run
  reorders fortresses. The fixture forces the reorder. The mechanism is proven; the observation
  still needs the heavy verification window.

### Files changed

`Sim/hero_generator/wells/countryside.py` (new `anchor`, both builders),
`Sim/icarus_sim/terrain_humans.py` (**provenance-pinned, fence lifted**: `record()` mints the
node-keyed `uid` beside the ordinal `id`),
`tools/terrain_world.js` (**provenance-pinned, fence lifted**: `heroSite()`'s hamlet and fortress
branches),
`tests/test_world_schema_conformance.py` (deed resolution on `uid`, plus the two assertions that
bound the coastal-row exclusion),
`Contracts/schemas/world-output.schema.json` (the `humans` description),
`Sim/npc_roster/sites.py` (two docstrings),
`Sim/tests/test_hero_countryside.py` (new `SiteAnchorTests`; existing literals repointed),
`Sim/icarus_sim/terrain_time.py` (one docstring literal),
`docs/hero-generator.md`, `docs/time-advance.md`, `docs/conformance/time-advance.md`,
`docs/conformance/actor-scale-writes.md`.

**Conformance:** no record claims `Sim/hero_generator/**` — the whole package is in
`coverage.json`'s `uncovered` allowlist under `board/in-progress/CONFORMANCE-DOCS.md`, so there is
no record to update for the change itself. The two records that were edited were edited because
they quoted a uid that no longer exists, not because they describe this module.

### The producer keeps its ordinal and gains a uid beside it

`terrain_humans.record()` still builds `f'{kind}-{number}'`, because `hamlet_plans` and
`castle_plans` join on exactly that and moving it would move every `hamlet_id` / `fortress_id`
join in the plan blocks and `npc_roster`'s `plan_id`. **It now also mints
`'uid':f'{kind}-node-{i}'` beside it** — additive, nothing renamed, no existing consumer broken.

That was the card's own secondary question (*"whether the ordinal plan ids stay on the record as
convenience fields is a separate decision; `npc_roster` keeps them and documents them as never
being identity, which is a precedent"*), and it arrived early: with the cast keyed on the node and
`npc_roster/sites.py` already minting `fortress-node-<n>`, the `humans` block was the last of the
three holding only ordinals, and
`tests/test_world_schema_conformance.py::test_generated_world_carries_a_valid_heroes_block_only_from_stage_sixteen`
failed on `'fortress-node-190' not found in {'fortress-0' … 'fortress-16'}`.

The spelling is not a new one. `terrain_settlement_api._rural_row` already minted
`'%s-node-%d' % (kind, node)` for **player-founded** rural rows, so generator rows were the odd
ones out; the generator now matches it verbatim rather than inventing a second convention, and
`adopt()` already preserved a player row's `uid` through renumbering.

**The failing test was written first and then ablated.** Against the strict resolution set it
first failed `KeyError: 'uid'`; with the mint it passes; removing the mint again and regenerating
turns it back to `KeyError: 'uid'`. The set resolves on `uid` and never `uid or id`, because a
fallback would pass whether or not the producer minted anything.

**One gap found while doing it, and it is bounded rather than papered over.**
`humans.hamlets` has *two* producers: `terrain_humans.record` and `terrain_society`'s coastal
port rows, which `terrain_society.py:215` extends the same list with and which carry no `uid`.
They can never carry a deed — `wells/countryside.candidates` skips every row whose role contains
`harbor` — so the test excludes them by `sea_node`, the field only the port builder writes, and
then asserts that the set of uid-less hamlets is **exactly** the set of coastal ones. Dropping the
uid from `record()` therefore fails twice rather than quietly shrinking the resolution set.
`terrain_society.py` is fenced to the sample-world session and pinned, so the one-line mint there
was **not** made; it is the remaining follow-up and would let that exclusion be deleted.

`Sim/icarus_sim/terrain_humans.py` was patched at byte level with its CRLF preserved
(`git check-attr text` reports `unset`, so line endings are part of the pinned hash).
`provenance/extraction-manifest.json` **was not touched** — the orchestrator owns that row. New
sha256 `b35bada7a9ce754b39d0615510bf079e5f78434970f0208ba4a37f01d7606e63`.

`Contracts/schemas/world-output.schema.json`'s `humans` description said the ids are ordinals and
not stable identity without naming what is; it now names the uid, says to join on it, and points
at `board/done/`.

## 2026-09-20 — the pin was unsatisfiable, and is not any more

`test_a_castellan_is_anchored_to_its_fortress_by_something_that_persists` could not have passed
however the product changed. It read

    ordinal = person['presence']['uid']

and then flagged any of four carried fields whose value contains `ordinal` as a substring — and
`presence.uid` is one of those four. It was an offender for ANY value it could ever hold,
including `fortress-node-13`, which is the value the fix is supposed to produce. So the test
was pinned to fail forever rather than pinned to a defect, and this card's acceptance was
unreachable as written.

The ordinal is now read out of the world —
`next(f['id'] for f in world['humans']['fortresses'] if f['node'] == 13)` — which asks the
question that was meant: does the person record carry the number that renumbers? It is still
red, and it now names all four offenders: `uid`, `presence.uid`, `claim.target_uid` and
`deeds[0].event_id`, every one of them `hero-castellan-fortress-1` or `fortress-1`.

The `castellans()` harness now resolves `presence.uid` against a `fortress-node-<n>` map first
and the ordinal map second, so it keeps working across the fix instead of silently finding
nobody and reporting green.

**Shown satisfiable rather than assumed.** Rewriting a test filed as a defect pin is the move
that hides a defect, so the rewrite was falsified: wrapping `hero_generator.generate` to rewrite
the four fields to the node key, in memory, turns the module from 5 tests / 3 fail to 5 / 0.
All three failures are the product's and none is the predicate's.

## The producer is not where the coordinating brief said it was

The ordinal is built by `Sim/icarus_sim/terrain_humans.py:146-151` `record()`, which is
provenance-pinned. `Sim/icarus_sim/terrain_settlements.py` has no `record()` and builds no
`{kind}-{number}` site id — checked, not assumed.

## Scoped first slice, for whoever takes this

The fix belongs on the CONSUMER side, in `Sim/hero_generator/wells/countryside.py`, not in
`terrain_humans.record()`: changing the producer moves `humans.hamlets[].id` and
`humans.fortresses[].id` in the world document and with them every `hamlet_id`/`fortress_id`
join in the plan blocks and `npc_roster`'s `plan_id`. Slice one is `_castellan` and `_reeve`,
all four fields together — repairing `uid` alone leaves three ways to join the wrong row.

Blast radius established by the adversarial verifier and NOT yet discharged, listed so the next
person does not rediscover it: `tools/terrain_world.js:131` `heroSite()` resolves hero map pins
by `find(c => c.id === presence.uid)` and would silently stop placing castellans and reeves on
the lab map — and that file is provenance-pinned, making two pinned edits in the change, not
one. `Sim/hero_generator/__init__.py:247` puts `presence.uid` into user-facing summary text.
The `npcs` block's `site_uid`, `presence_node` and the `cast_located_by_presence` /
`cast_presence_unresolved` counters move in every generated world.
`Artifacts/npc-roster/sample-size65-seed42.json` goes stale with no regenerator in the tree.
And `Sim/tests/test_npc_roster.py`'s `hero-castellan-fortress-0` literals must NOT be moved:
they are hand-built inputs to that module's own synthetic world, not outputs of the cast
package, and moving them breaks `FixtureTests` against the pinned roster fixture
`Fixtures/npc-roster-v1.json`, which records both spellings.

Evidence: `Sim/tests/test_site_id_stability.py` — 5 tests, 2 controls pass, 3 fail, 0.050 s,
no world generated. Unchanged in count from the state as filed; changed in meaning, because
one of the three was previously unsatisfiable.

## The defect

`terrain_humans.record()` builds `f'{kind}-{number}'` where the number is the position in the
accepted list. Fortresses are accepted in descending `defence_score` over a `strategic` map
rebuilt from the road graph every age, and war history reweights that score. So both the
membership and the ordering change at every age boundary: `fortress-36` names different
ground after an advance.

`hero_generator.wells.countryside._castellan` builds its person on that ordinal, and spends
it **four times** — `uid`, `presence.uid`, `claim.target_uid` and `deeds[].event_id`.
`_reeve` does the same with `hamlet['id']`.

The test fixture is an ordinary advance, not a contrived one: a new fortress on node 14
scores higher than the existing one on node 13, so node 14 takes `fortress-0` and node 13
becomes `fortress-1`. A control asserts the node-13 record is otherwise identical field for
field with `id` excluded — same ground, same city, same defence score.

Result:

- **The castellan on node 13 was `hero-castellan-fortress-0` and is now
  `hero-castellan-fortress-1`.** Anything that referred to that person before the advance
  cannot find them after it.
- **`hero-castellan-fortress-0` now means node 14.** The old uid still resolves, to a real
  person at a real fortress, and it is the wrong one. Nothing reports that anything happened.

The second is the dangerous half. It is exactly what `npc_roster/sites.py` describes: *"two
keys that read alike and mean different things is how a consumer joins the wrong rows
without an error."*

## The rule already exists, three times, and nothing enforces it

- `npc_roster/sites.py:116` keys non-city sites `fortress-node-1062`, positionally, and
  spells `-node-` into the key so a reader cannot mistake which number space it is in.
- `terrain_villains.regions()` anchors a villain to a ley node id for the same stated reason.
- `npc_roster/sites.py` refuses `culture_id` on the same grounds: those ids rehash every age.

Three packages adopted the defence independently. The cast did not, and no check notices.
`places()` in `npc_roster/sites.py:166` exists specifically to bridge the two spaces by
resolving coordinates where the whole world is in hand — a workaround maintained at the
consumer for a producer that emits an unstable key.

## Proposed mechanism

**Not proposed**, but the shape is constrained by what is already here: key on the terrain
node and spell the anchor out, as `npc_roster` does. The card's contribution is the part a
fix will otherwise miss — **repairing `uid` alone leaves three other ways to join the wrong
row**, so `presence.uid`, `claim.target_uid` and `deeds[].event_id` move in the same change
or the defect survives it.

Whether the ordinal plan ids stay on the record as convenience fields is a separate decision;
`npc_roster` keeps them and documents them as never being identity, which is a precedent.

## Dependencies and unresolved decisions

- `heroes` is a published contract (`hero-generator.schema.json`), so changing a uid format
  is a consumer-visible interchange change and needs the version discipline in AGENTS.md.
- `npc_roster` builds `HERO_UID_PREFIX + uid`, so a cast uid change renames roster rows too.
- `story_web` keys on the cast; `key_locations` reads villain claims. Both need checking
  against a uid change, neither is checked here.
- Hamlets have the identical defect through `_reeve`. Not separately tested; same fix.

## Sources consulted

- `Sim/icarus_sim/terrain_humans.py:146-151` — `record`, which builds the ordinal id.
- `Sim/icarus_sim/terrain_humans.py:211-218` — the fortress acceptance loop.
- `Sim/hero_generator/wells/countryside.py:104-115` — `_castellan`.
- `Sim/npc_roster/sites.py:1-25` — the identity doctrine, stated in full.
- `Sim/npc_roster/sites.py:166-180` — `places`, the workaround that bridges the two spaces.

## Files and assets in scope

`Sim/hero_generator/wells/countryside.py`, `Contracts/schemas/hero-generator.schema.json`,
`Sim/npc_roster/__init__.py`, `Sim/npc_roster/sites.py`, `docs/hero-generator.md`,
`docs/npc-roster.md`.

## Acceptance and evidence

`Sim/tests/test_site_id_stability.py` passes unmodified:

1. the castellan of a fortress that did not move keeps its uid across an advance;
2. no uid comes to name different ground after an advance;
3. no field of a castellan carries the ordinal.

Both controls must keep passing: the same world twice gives the same person the same uid, and
the advance fixture changes the ordinal and nothing else.

## Documentation impact

`Sim/npc_roster/sites.py`'s module docstring names the cast package as the one that does not
key positionally. When that stops being true, that paragraph changes in the same commit —
it is the clearest statement of the rule in the repository and it would become a false one.

## Adversarial review and limitations

- **Not established:** that a real generated multi-age run reorders fortresses. The mechanism
  is proven — the ordinal is the position in a list re-sorted by a score that depends on war
  history and the road graph — but the fixture forces the reorder rather than observing one.
  A generated two-age run at a seed that ruins a city near a fortress would settle it, and
  needs the heavy verification window.
- **Not established:** that any current consumer actually breaks. The failure is available,
  not observed. `story_web` and the quest layer are the likely victims and neither was checked.
- The `x`/`z` fields in the fixture are positional decoration; nothing under test reads them.

## Handoff

Found by the red-team SDET session taking the coordinator's third assignment. The coordinator
supplied the lead — `hero-castellan-fortress-36` on the ordinal against `npc_roster`'s node
key — and the finding that the ordinal is carried in four fields rather than one is new.
