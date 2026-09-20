# PLAYER-FOUNDED-SETTLEMENTS — a player can raise a city the world has to treat as real

Owner: none. State: open, scoped 2026-09-20 from a user requirement. No code written.

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
it**. `board/backlog/NOMAD-SURVIVOR-SETTLEMENT.md` reaches the same wall from the nomad
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
`suitability`, `war_history`); `board/backlog/NOMAD-SURVIVOR-SETTLEMENT.md`;
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
