# PLAYER-FOUNDED-SETTLEMENTS — a player can raise a city the world has to treat as real

> **HEADER CORRECTED 2026-09-21, then closed the same day.** The status line used to read
> “No code written” directly above a section reading “Delivered 2026-09-20, for cities only”
> with 12 passing tests and a conformance record at `docs/conformance/settlement-founding.md`.
> The remainder it identified — hamlets and fortresses as founded kinds, and the player's
> layout not persisting — is delivered below.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

Owner: SETTLEMENTS sweep. State: **DELIVERED 2026-09-21**. Scoped 2026-09-20 from a user
requirement; cities landed 2026-09-20, hamlets and fortresses and the layout carry-back
landed 2026-09-21.

**The line that used to stand here read "No code written", directly above a section recording
delivery with twelve passing tests and a conformance record. It was false when it was written
and it is corrected rather than deleted, because the failure it caused — a reviewer trusting a
status line over the body beneath it — is the reason the board was reconciled at all.**

## Delivered 2026-09-21: the remainder

**Hamlets and fortresses are founded kinds.** `found_settlement_request` takes
`kind: city | hamlet | fortress` at settlement API **2**. A rural kind writes into
`humans.hamlets[]` or `humans.fortresses[]` — the block that already holds that kind, never a
parallel `player_settlements` — and its id is appended to the parent city's `cores` row so
`terrain_wars` counts it and `exchange_food` sees it.

**On a node-and-kind key, without touching the ordinal id space.** The row keeps the ordinal
`hamlet-N` / `fortress-N` `id` its block has always used, because `hamlet_plans` and
`castle_plans` join on exactly that and the id space is `SDET-SITE-ID-ORDINALS`' question, not
this card's. Beside it the row carries `uid` — `hamlet-node-117` — which is the key
`npc_roster` already mints for the same row, so no parallel space is invented. `add_humans`
re-derives the whole rural layer on every rebuild and now adopts player rows through it:
the ordinal is reissued, the owning city, culture and access path are recomputed, and the
`uid`, the node and the player's own choices are not. Their nodes join the occupied set before
the generated passes run, so nothing is placed on top of them and
`test_no_two_settlements_share_a_node_in_a_finished_world` still holds.

**The player's layout persists.** `terrain_settlements.carry_survivor` is the carry-back the
`founded_by` marker was written for and that the conformance record recorded as not existing.
A site marked `founded_by: player` keeps its `city_layout` across the rebuild that overwrites
every other site's, the stage-9 re-derivation is skipped for it, and `city_planner.plan_city`
returns `status: "unbuildable"` with `authored_by: "player"` and a stated reason rather than
packing a city the player designed. `unbuildable` is a status the planner already emitted, so
no consumer needs a new branch.

**A node that already holds a settlement of any kind is refused.** It used to check cities and
ruins only, so a city could be founded on a hamlet's node and the clash would surface an age
later. Hamlets and fortresses are held to their own separations — 120 m and 200 m, the same
numbers `terrain_humans.separated` spaces generated ones by — rather than to the city spacing,
because a hamlet exists to be near its city.

**Test evidence.** `tests/consumer_founder.py` grew from 12 tests to **22**. The new ones were
written before the change; they were not run against the unchanged tree, because the module
imports the API and would have failed at collection. The pre-change failure was measured
instead by executing HEAD's `_validate` against the same request bodies:

```
pre-change API_VERSION = 1
pre-change FIELDS = ['api_version', 'civilization_id', 'layout', 'name', 'node',
                     'population_estimate', 'rebuild', 'world']
kind=hamlet  -> INVALID_INPUT field=kind | No request field named 'kind'.
kind=village -> INVALID_INPUT field=kind | No request field named 'kind'.
```

After: `PYTHONPATH=Sim python -m unittest discover -s tests -p consumer_founder.py -v` ->
**Ran 22 tests in 119.061s, OK**, including the age advance and `validate_age_world` on a
world carrying a player fortress. The carry-back branch is additionally covered by
`Sim/tests/test_settlement_records.py::SurvivorCarryBackTests` (3 tests), which are new-branch
unit tests and therefore passed on their first run -- the branch they exercise did not exist
before this change.

## The central open question, answered

**Does founding rebuild immediately, mark the world dirty for the next tick, or take an
argument? It takes an argument, and the argument defaults to not rebuilding.**

A dirty flag was rejected: it puts an age-transition-sized cost (`add_nests` and `fill_cities`
are 93.9% of a generation between them) somewhere the caller cannot see, cannot decline and
cannot schedule, and it makes "is this world consistent" a question with no answer at the call
site. Rebuilding unconditionally was rejected because it charges every founding for work most
callers do not want and re-rolls blocks a consumer may have cached. `rebuild: "humans" | "none"`
makes the trade the caller's at the call that caused it, and the response enumerates what
moved. Reverse it by changing the default in `terrain_settlement_api._validate`.

## Still not delivered, named

- **There is no way to hand a layout in.** `layout: "player"` marks the site and stops the
  generator overwriting whatever `city_layout` it then carries. The call validates no layout
  document and has no field for one. "The player owns the layout" is met in the sense that the
  generator no longer overwrites it; it is not met in the sense of an upload.
- **A player fortress is laid out by the castle kit.** `layout` is a city-only argument, so
  `fill_castles` plans a player keep like any other.
- **`NOMAD-SURVIVOR-SETTLEMENT` is not closed by this.** Adopting a `settlement_candidates`
  entry is now the same call with the candidate's node and estimate, but nothing calls it and
  no test covers that path.
- **Settlement API 1 is not retryable.** A request naming `kind` is a version 2 request, and
  version 1 is refused by `unsupported_api` rather than accepted as cities-only.

## The scoping as it was filed

## Delivered 2026-09-20, for cities only

`Sim/icarus_sim/terrain_settlement_api.found_settlement_request`, settlement API 1, routed at
`POST /world/found-settlement`, recorded in `docs/conformance/settlement-founding.md`, proved
by `tests/consumer_founder.py` (12 tests).

**Four things the scoping in this card got wrong, all found by measurement:**

1. **"Village" is not a settlement kind.** `settlements.sites[].kind` is the literal constant
   `'city'`; small/medium/capital is `city_class`, a per-civilization suitability *rank*. The
   API takes cities only.
2. **The binding constraints are not field presence.** A site has 48 fields, not 33 — the
   35-field figure came from a stale artifact. What actually binds is three structural
   invariants no field list captures: `id` must equal the index in `sites[]` (it is a direct
   index into three parallel blocks, so a wrong one joins silently); `city_class` must be
   exactly what `classify_cities` derives or `validate_age_world` refuses the world forever;
   and `roads.routes[].from/to` are indices into the same list.
3. **The leaf packages are the most tolerant readers, not the least.** `key_locations`,
   `npc_roster` and `story_web` guard every read with `.get` and degrade silently. Only
   `hero_generator` raises. Silent degradation is the harder failure to debug.
4. **A founded city is not erased by the next age advance.** `found_cities` seeds survivors
   into its site list. It is frequently *destroyed*, which is different: on an untouched
   seed-42 size-17 world an age advance ruins ten of twelve cities across six causes.

**Two findings that shaped the implementation:**

- Re-running the nest pass after a founding is a **determinism-contract violation**, not an
  expense: `_place` draws from one sequential stream keyed on distance to settled ground, so
  one town re-rolled 152 of 248 monster nests, the furthest at the antipode. The call refuses
  to do it and says so in its report.
- `add_humans` renumbers hamlet and fortress ordinals — 15 hamlets reassigned on one founding
  — and `hamlet_plans`/`castle_plans` key on exactly those ordinals with no uid beside them.
  `rebuild: "humans"` therefore drops both plan blocks rather than leaving rows naming ground
  that moved.

**Still open, and the card's own premise:** the player's layout does not persist.
`site['city_layout']` is overwritten for every site at `terrain_settlements.py:938` and
`city_plans` is popped and rebuilt from empty. A `founded_by` marker is written so a
carry-back could recognise a player site, but no carry-back exists. Extending the five-key
carry-back at `terrain_settlements.py:920` is the shape of that fix and is a change to the
generator rather than an addition beside it.

Hamlets and fortresses as player-founded kinds remain unbuilt, deliberately: their ordinal
ids renumber at every age boundary, so a player keep would change name under its owner. They
want the node-and-kind key `npc_roster` already mints.

## Requested behavior

The player founds a new city, village, hamlet or fortress. **The player owns the layout** —
where the buildings go is their design, not the planner's. **The world owns the metadata**,
and it must be indistinguishable in kind from a generated settlement: the site carries the
same identity, classification, civilization binding and founding provenance that
`found_cities` produces, so every downstream block continues to work.

On the map the result is simple — a located, classified settlement. It is not a generated
`city_plans` entry and must not be forced to become one.

The caller is the orchestrator, never the player. The player acts in the game; the
orchestrator interprets that action and translates it into this request. Nothing here is a
player-facing control surface.

## The gap

There is no "found a settlement" call of any kind. A settlement can only come into being by
running `found_cities` inside a full generation or an age transition, which places sites by
suitability search rather than by instruction.

The block that should already be the seam is inert. `settlement_candidates`
(`Sim/icarus_sim/terrain_nomad_effects.py:183`) carries `{id, node, direction,
migration_source_node, migration_distance_m, population_estimate, reason}` — a
proto-settlement — it rides in `STATE_KEYS` (`terrain_history.py:406`), and **nothing reads
it**. `board/done/NOMAD-SURVIVOR-SETTLEMENT.md` reaches the same wall from the nomad
side: refugee bands that reached a refuge are recorded and never adopted. That card and this
one want the same missing function, and it should be written once.

## What a site actually needs, traced

The founding record (`Sim/icarus_sim/founding.py:67-73`) is only the first third:

```
node, population_profile, parent_race_id, founding_turn, founding_capital,
founding_year, migration_source_node, source_civilization_id,
migration_distance_m, cultural_branch
```

Then `terrain_civilizations.py:74-75` assigns `city_class` (`small` / `medium` / `capital`,
from suitability against a threshold, capital retained) and `classification_reason`. Then
`terrain_history.py:263` mints identity:

```python
city.setdefault('uid', f"surface-city-{age}-{city['node']}-{city['population_profile']}")
```

Node-keyed, which is the right discipline — it survives an age boundary, unlike the ordinal
`hamlet-N` / `fortress-N` ids that `SDET-SITE-ID-ORDINALS` shows renumber every age. A
player settlement must be minted by the same rule and must not invent a parallel id space.

**Twenty-seven non-test modules subscript `settlements`**, and they are not confined to
`icarus_sim`. Inside it: `terrain_settlements`, `terrain_humans`, `terrain_society`,
`terrain_seasons`, `terrain_magic`, `terrain_leyline_history`, `terrain_corruption`,
`terrain_visitation`, `terrain_religion`, `terrain_astrology`, `terrain_villains`,
`terrain_nests`, `terrain_nomads`, `terrain_nomad_routes`, `terrain_nomad_effects`,
`terrain_recipes`, `terrain_history`, `terrain_time`, `city_planner`, `hamlet_planner`,
`castle_planner`, `world_scene`, `world_debug`. And in all four leaf packages:
`hero_generator/history.py`, `key_locations/core/world.py`, `npc_roster/sites.py`,
`story_web/facts.py`.

That is the blast radius of adding one site, and it is the reason this cannot be a dict
appended to a list. The leaf packages matter most: they were written to read an exported
world they did not build, so they are the readers least likely to tolerate a site shaped
differently from the ones `found_cities` produces.

## Proposed mechanism

`terrain_settlement_api.found_settlement_request(body)`, settlement API 1, stateless in the
shape of the other request functions — world in, new world out, caller persists,
`history.operations` records the call.

```json
{"api_version": 1, "world": {}, "node": 1481, "kind": "city",
 "civilization_id": "human_desert", "name": null,
 "population_estimate": 400, "layout": "player"}
```

- `kind` is `city | village | hamlet | fortress`. Each already has a home block —
  `settlements.sites[]`, `humans.hamlets[]`, `humans.fortresses[]` — and this must write to
  the existing one rather than open a parallel `player_settlements` block. A consumer that
  has to check two places for "is there a town here" is the defect this exists to avoid.
- `layout: "player"` writes a `city_plans` entry with `status: "unbuildable"` and a stated
  reason, which is a value the planner **already emits** (`city_planner.py:133`), so no
  consumer needs a new branch. `layout: "generated"` runs the planner as normal, so the same
  call serves "found it and lay it out for me."
- Classification runs the real rule rather than accepting a caller's word for it: the
  request may *request* a `city_class`, and the response reports what was assigned and why,
  through the existing `classification_reason`.
- Refusals are envelope failures, by the same contract the rest of the request boundary is
  moving to: water node, node outside the world, uninhabitable ground for that civilization,
  a node already holding a settlement, an unknown `civilization_id`.
- Adopting a `settlement_candidates` entry is the same call with the candidate's node and
  estimate, which closes `NOMAD-SURVIVOR-SETTLEMENT` as a consequence rather than as a
  second mechanism.

## Dependencies and unresolved decisions

- **When downstream blocks refresh.** Adding a site invalidates roads, `humans`, `npcs`,
  `threat_assessments`, `seasonal_food` and `world_economy`. `rebuild_tail`
  (`terrain_history.py:288`) exists and is what `advance_age` and visitation already use,
  but running it on every founding is expensive and re-rolls blocks a consumer may have
  cached. **Undecided and the central question of this card:** does founding rebuild
  immediately, mark the world dirty for the next tick, or take a `rebuild: true|false`
  argument. Sequence with `TIME-ADVANCE`, whose Season band is where a deferred rebuild
  would naturally land.
- **Determinism.** A player settlement is not reproducible from `config` plus seed, because
  it came from an instruction. Decision 023 makes worlds disposable today, so this is
  tolerable now, but `history.operations` becomes load-bearing: config-only replay
  reconstructs genesis, and the operation log is the only record of what the player built.
  Whoever takes this must say plainly that a world with player settlements replays only
  through its operation log.
- **Which id space a player fortress or hamlet uses.** `humans.hamlets[]` and
  `humans.fortresses[]` use ordinal `hamlet-0` / `fortress-0` ids that re-sort every age.
  A player-built fortress keyed that way would move under its owner at the next boundary.
  It probably needs the node-keyed discipline `key_locations` uses; that is a decision, and
  it may mean the two kinds of fortress do not share an id rule.
- Blocked in practice by `TIME-PERSISTED-WORLD-CANNOT-ADVANCE`: a world written by the CLI
  cannot re-enter any of the rebuild paths.

## Sources consulted

`Sim/icarus_sim/founding.py:67-92`; `Sim/icarus_sim/terrain_civilizations.py:74-75,92`;
`Sim/icarus_sim/terrain_history.py:263,288,406`; `Sim/icarus_sim/city_planner.py:83-94,122,133,342`;
`Sim/icarus_sim/terrain_nomad_effects.py:175-199`; `Contracts/schemas/world-output.schema.json`
(`settlements.sites[]` declares `city_class`, `civilization_id`, `population_profile`,
`suitability`, `war_history`); `board/done/NOMAD-SURVIVOR-SETTLEMENT.md`;
`board/backlog/SDET-SITE-ID-ORDINALS.md`; `board/backlog/TIME-ADVANCE.md`;
`docs/decisions/023-world-compatibility-policy.md`.

## Files and assets in scope

New `Sim/icarus_sim/terrain_settlement_api.py`, its schema, and a conformance record.
Changed: `terrain_history.py` (operation record, rebuild hook), `Contracts/README.md`,
`docs/README.md`. A route in `tools/terrain_lab.py` — note that file is provenance-pinned
and an edit needs an appended revision row.

## Acceptance and evidence

A world with a player-founded city satisfies `world-output.schema.json` unchanged. Every
cross-block join in the consumer harness's join table resolves against the new site. The
site keeps its `uid` across an age advance. `city_plans` reports `unbuildable` with a reason
rather than omitting the city. A refused founding names the field, the value and the reason.
Adopting a `settlement_candidates` entry produces a site indistinguishable in shape from a
generated one.

## Documentation impact

`docs/terrain-world-layers.md` gains the call beside the age API. `Contracts/README.md`
indexes the schema. The conformance record states the determinism carve-out explicitly.

## Adversarial review and limitations

**The honest objection: this is the first call that makes a world unreproducible from its
recipe.** Every existing request function is a pure function of a world and its arguments;
this one injects authored content. That is what the user asked for and it is the right
capability, but it changes what "deterministic" means for any world it touches, and the
card should not pretend otherwise.

**Where it is weakest:** the rebuild question is unanswered, and the answer decides whether
this is a cheap call or an expensive one. Founding a city that nothing routes a road to is
a city in a field. Founding one that triggers a full `rebuild_tail` costs roughly an age
transition — `add_nests` and `fill_cities` are 93.9% of a generation between them
(`PERF-ADD-NESTS-DOMINATES`), and `rebuild_tail` runs both.

**Not established:** that the fourteen downstream readers tolerate a site they did not
place. They are written against sites `found_cities` produced, and several read fields this
card has not audited — `suitability` in particular is a placement score, and a player site
has no search behind it. Whoever takes this should enumerate every field read off a site
before choosing what a founding request must supply.

## Handoff

Scoped from a user requirement on 2026-09-20: the player builds and designs settlements,
the world carries the metadata regardless. Traced by following a founding record from
`found_cities` through classification to uid minting, and by listing the modules that read
`settlements`. No code written and no world generated; the fourteen-reader figure is a grep
over non-test `Sim/` modules, not a runtime trace.
