# SDET-SITE-ID-ORDINALS — a cast uid follows a position in a list that is re-sorted every age

Owner: none. State: **defect pinned by failing tests; no fix attempted.**
Evidence: `Sim/tests/test_site_id_stability.py` — 5 tests, 2 controls pass, 3 fail, 0.048 s,
no world generated.

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
