# Hidden schools: the twelve-school taxonomy

The world knows eight schools of magic. There are twelve.

The four it does not know — Blood, Void, Rot and Eldritch — are declared in the taxonomy but unreachable from generation. Every generated world carries four empty networks and four all-zero fields for them, and nothing in the world can name, measure, chart or worship them. They exist so that something outside the world has somewhere to arrive.

Reference: `Sim/icarus_sim/terrain_leyline_history.py` (`KNOWN_SCHOOLS`, `HIDDEN_SCHOOLS`, `SCHOOLS`), `terrain_biome_catalogue.py` (the 156-entry catalogue), `terrain_world.py` (`NETWORKS`, `HIDDEN_NETWORKS` and the locked occurrence).

## The four

| School | Group | Descriptors |
|---|---|---|
| Blood | Outside | sacrifice, lineage, vitality, hunger |
| Void | Outside | absence, entropy, unmaking, silence |
| Rot | Outside | disease, undeath, decay, rebirth |
| Eldritch | Outside | madness, wrong geometry, dominion of minds |

They share one group, `Outside`, which is the fourth group in `magic.groups` and belongs to no known school. A consumer that groups the school order by `group` sees three groups of known magic and one of something else.

## Why appended, never inserted

`dominant_magic` exports an index into the school order, and `biome_variant` exports an index into the magical catalogue, which is built as natural cores crossed with schools. Inserting a school anywhere would renumber both in every world ever generated.

So the taxonomy is built as `{**KNOWN_SCHOOLS, **HIDDEN_SCHOOLS}`, the known eight keep positions 0–7, and the catalogue is built in two passes rather than as one wider cross product:

- positions **0–103**: the 13 natural cores crossed with the known eight, byte-identical to the catalogue before the hidden schools existed
- positions **104–155**: the same 13 cores crossed with the hidden four

A `biome_variant` index recorded before any of this still means exactly what it meant.

## Generation can never raise one

`<school>_occurrence` for each hidden school is declared with `min == max == 0`, the same lock `sky_occurrence` uses. `validate_options` rejects any nonzero value, so no `generate_request` override can raise one, and `generate_networks` always takes the disabled branch: empty `nodes`, empty `edges`, `distribution: None`.

An unmanifested network's potency is exactly `-0.0`, which is why adding four of them moves nothing. `magic_density`, `magic_hazard` and `magic_growth` sum over the schools and adding exact zeros to a float sum is bit-identical; `dominant_school` requires potency `>= 0.35` to win, so a zero-potency school never does.

## Outside the world's instruments too

Being absent from generation is not the same as being invisible to it. These four are also excluded from the machinery the world uses to understand its own magic:

- **The moon charts no tide for them.** `tide` and the lunar almanac cover the known eight, so a hidden school has no `surged_strength` key at all rather than being reported as unmoved, and `city_potencies` gives hidden schools potency but no lunar sway. Alien magic does not answer to this world's sky.
- **No god of the pantheon claims one.** `lint_catalogue` requires the school gods to cover the known eight exactly once, and `world_facts.schools` — which is exported as `religion.facts` — reports only the known eight, so a world's religion record shows no trace of them.
- **Player leyline edits cannot reach them.** `advance_age_request` validates an edit's `school` against the known eight, so no caller can hand-place a hidden node at an age boundary. `age-advance-request.schema.json` pins the same eight.

That last one is the load-bearing restriction: the corruption API is the only way a node enters a hidden network.

## What a consumer sees

In a generated world:

- `magic.school_order` has 12 entries, the known eight first
- `magic.groups` has 4, `Outside` last
- `magic.networks` has 12 entries; the hidden four are empty
- `layers.ley_<hidden>` and `layers.instability_<hidden>` exist and are identically zero
- `terrain.magical_biomes` has 156 entries
- `debug_stats.leylines` lists 12
- the planners carry the 156-entry catalogue and a 12-key `magic_colors` map through to each city, hamlet and castle

Nothing else moves. `history.version` is **3**; a world built against the eight-school contract cannot advance an age and must be regenerated.
