# NPC roster: the people v1

A finished world carries an `npcs` block: one record per staffed post in every planned city,
hamlet and castle, with the cast folded in by uid. The generator is a wholly separate package,
`Sim/npc_roster/`, called once when world generation finishes (and again after every age
advance) with the world as plain JSON. It reads `city_plans`, `hamlet_plans`, `castle_plans`,
`settlements`, `humans`, `civilizations` and `heroes`; it writes only `npcs`. It never imports
`icarus_sim`: a saved `world.json` serves it as well as a live result.

Reference: `Sim/npc_roster/` (package), `policies/*.json` (authored data), the
[schema](../Contracts/schemas/npc-roster.schema.json), `Sim/tests/test_npc_roster.py`.

## Thesis

The world has always known how many people it employs. Every measured structure in
[buildings.json](../Sim/icarus_sim/buildings.json) carries a staffing roster, and the planners
place those buildings, so the count has been sitting in `city_plans` all along —
[civilizations.md](civilizations.md) says outright that "each post assumes a different NPC" and
that none is created. This package creates them.

    A person = a post that was placed + who their people are + whether they are still alive.

Nothing is invented. No personality, no backstory, no motive: those belong to the cast, which
already has them, and to the traits package, which owns what a people is like. What this block
adds is the two facts a quest generator cannot work without.

- **`important`** — the earmark. The people worth talking to, kept to a bounded few per site so
  a consumer scans a short list instead of walking thousands of records.
- **`status`** — `alive` or `dead`, so a quest is never offered by a corpse.

## Scale

Measured on a size-65 world (seed 42):

| Source | Sites | Plots | People |
|---|---|---|---|
| `city_plans` | 51 | 4,001 | 7,033 |
| `hamlet_plans` | 210 | 2,579 | 2,048 |
| `castle_plans` | 86 | 1,584 | 3,605 |
| the cast | — | — | 324 |
| | **347** | 8,164 | **13,010** |

The block is 3.2 MB against a 108.9 MB world, in line with `heroes` (1.6 MB) and `story_web`
(2.2 MB). It is normalised — a person carries a `site_uid`, not a copy of its city's name and
people — which costs one dict lookup and saves about a third of the bytes. Note that everything
in `STATE_KEYS` is deep-copied into `build_stages`, so a saved world with stages pays for the
block more than once.

## Identity, and why the uids look like that

This is the part that took the most care, because the block is re-derived after **every age
advance** and all three planners rebuild their plans each time. Anything ordinal renames people.

- City uids are genuinely stable (`surface-city-<age>-<node>-<profile>`, carried onto rebuilt
  survivors by the settlement builder), so they are used unchanged.
- `hamlet-0` and `fortress-0` are **ordinals that renumber every age**. `plot-7` is an ordinal
  inside a plan that is itself rebuilt. `humans.cultures` ids rehash every age.

So the small sites are anchored on their terrain node, the way `terrain_villains` anchors
villains to ley nodes for the same reason. Nodes are unique within a kind (verified: 210/210
hamlets, 86/86 fortresses on the size-65 world), but a hamlet and a fortress can share one, so
the kind is part of the key.

```
site key   city      <city uid>                     already stable
           hamlet    hamlet-node-<n>
           fortress  fortress-node-<n>
person     post      npc-<site key>-<building>-<ordinal>
           cast      npc-<hero uid>
```

The `-node-` is deliberate and load-bearing. The cast package builds
`hero-castellan-fortress-36` on the **ordinal** fortress id, so a bare `fortress-36` from this
package would read as the cast's id and join the wrong row with no error. The spelling says
which number space the id lives in.

`plan_id` and `plot_id` are kept on the records as convenience joins and are documented as
**never being identity**.

Display names are made unique. Two farmsteads below the same city would otherwise both read
"the farmstead below Glen"; the uids differ so nothing joins wrongly, but a giver whose
location reads exactly like another's is useless to a reader, so a repeated name gains its
node.

### What this does not fix

A hamlet that is abandoned and a different hamlet later founded on the same node reuses the
key. That points a quest at the right place with the wrong history — a much smaller lie than
an id that silently becomes someone else every age, but a real one.

And **a person whose site is ruined by an age advance simply stops appearing**. The plans are
rebuilt from survivors only, so there is no input from which a tombstone could be computed and
none is written. A consumer must treat "uid absent" as gone, not as an error. Carrying the dead
forward across ages is the obvious next slice and is not built.

## Posts

A plot exports `workers` as a count, not a breakdown, and the role ids live in the building
registry. Rather than change the three planners, `policies/posts.json` carries a snapshot of
the registry's rosters, and a test re-reads `buildings.json` and the expanded
`civilization_registry.city_plan()` for every civilization and size block, failing the day
either drifts. Role order is seniority order: the first role of a building is its senior post.

When the policy and the plot disagree, **the plot's count wins** — it is what the planner
actually budgeted and housed. A longer roster truncates, a shorter one continues under its last
role, and either way `summary.roster_mismatches` counts it. Nothing is ever padded with a
generic `worker`: padding is how a data bug becomes a person.

A per-civilization size-block `staffing` override replaces the library roster for that entry
alone. **No override exists today**, so the snapshot is correct now and could mislabel one
civilization's posts later; the block records the world's own registry revision beside the
policy so the discrepancy is visible rather than silent.

## The earmark

Authored, not rolled. `important` is true for every cast record, and for the senior post of the
highest-ranked giver buildings a site has, capped per site (`capital` 6, `medium` 4, `small` 3,
`fortress` 2, `hamlet` 1). `summary.important_capped_out` reports how many candidates the cap
refused.

**The bound is per site on the post-derived earmark, and that is the contract** — not a flat
percentage of the roster. The cast is always important and is deliberately *not* capped, so on
a small world heroes dominate the fraction: measured **906 of 12,686 (7.1%) at size 65**, but
**95 of 1,009 (9.4%) at size 17, where 47 of those 95 are heroes**. A consumer sizing itself
against a percentage would be measuring the cast rather than the cap. What it can rely on is
that each site contributes at most its cap, so the post-derived set grows with the number of
sites and never with how generous a civilization's building list becomes.

If a per-site count ever exceeds its cap, that is a defect in the cap, not a new normal — the
natural failure mode is someone raising a cap to fit a use case and nobody noticing that a
consumer assumed the ceiling. A cap can never demote a hero.

Each post is tagged with the verbs it can plausibly offer, from the ten the quest work pinned —
`reclaim, recover, defend, slay, trade, tend, convert, supply, cleanse, investigate` — eight of
which are already in `heroes.quest_hooks[].actual_effect.action`. A post with no verbs can be
held but never becomes a giver. The map is exported as `post_verbs` so a consumer reading
`world.json` alone has it.

## The cast

Heroes and Dreads get roster records cross-linked by `hero_uid`, so one list answers "who is
important and alive" instead of joining two blocks with different life-state vocabularies. They
keep their own uids in `heroes`; this package never bends that namespace.

A hero is not a staffed post, and three things follow that the schema allows rather than
pretends away: `presence` may be absent entirely (every legend, and the living but
dispossessed), so `site_uid` is null; a presence may stand somewhere this block has no row for
(a camp, ruin, college, port, shrine or nest); and `post` is the person's role, so
`building_id` is null. `presence_kind` and `presence_uid` carry the cast's own reference
verbatim, so an odd placement resolves against the block that owns it.

`living` maps to `alive`, `legend` to `dead`.

### Where a hero actually stands

This is the one place the block does real work on the cast's behalf. A castellan's
`presence_uid` is `fortress-36` — the cast's **ordinal** id — while this package keys the same
fortress `fortress-node-1062`. Neither id resolves in the other's namespace, so such a person
falls back to being filed under their home city. That city is a real place and the wrong one,
and for anything measuring travel a confidently wrong location is worse than none.

On a size-65 world that is **182 of the 906 earmarked people** (fortress 53, hamlet 48, port 37,
ruin 29, shrine 15), and none of their `presence_uid`s resolve in `sites[]`. So whenever a
person's true placement differs from the site they are filed under, the record carries
`presence_node` (plus `presence_x`/`presence_z`): the terrain node they actually stand on,
resolved against every exported block that names a place. All 182 resolve; `summary`
counts both the located and any that could not be. The join is done here because only the
generating world can do it — a consumer holding the block alone cannot.

Ruin presences name the city the ruin used to be rather than the ruin, so the canonical
`ruin-<city uid>` is tried as well. `presence_node` is **absent, not null**, when a person
stands where they are filed, so its presence is itself the signal that the fallback was in
play. `presence_x`/`presence_z` follow where the source has them; religion sites carry only a
node, so those two are omitted rather than exported as nulls.

This is the rule the block follows for what belongs on a record, and it is worth stating
because the obvious instinct gets it wrong: **the producer holds the generating world and the
consumer holds only the artifact, so a join the producer can do for free is one the consumer
cannot do at all.** Thin-record instinct is right for anything a consumer could derive and
wrong for anything it could not. Every counter in `summary` follows the same principle from the
other side — they are always present, even at zero, because a counter that appears only once it
is non-zero cannot be told apart from one that was never computed.

## Traits, and what this block deliberately does not hold

Per-race traits are constants owned by `Sim/heritage/`, keyed by civilization id. This block
carries **no `traits` field** — an empty one would sit unfilled and invite a second writer.
A person carries `civilization_id` (the primary join key for culture, language and traits) and
`parent_race_id` (the language **family** only). Never join on the parent alone. When the
parent cannot be resolved it is null and counted, never guessed: a guessed parent is a wrong
tongue.

**Appearance joins the same way and is held the same way.** `Sim/heritage/policies/appearance.json`
carries one authored body per subrace — stature and mass bands, proportions, palettes,
features, grooming, life stages, dress and art direction — and it ships in
`Contracts/catalogues/native-catalogues-v1.json`, not in this block and not in the world
document. A person here carries no height, no colouring and no portrait, for the same reason
they carry no `traits`: the population-level parameters belong to heritage, and the
per-individual draw from them belongs to the game engine. Join on `civilization_id`.

The block also exports no field called `tier` in any sense. The word already means four
incompatible things in this repository.

## Names

Every person is named at generation, through one function — `naming.name_for(civilization_id,
parent_race_id, draw)`. That function was written as a seam around interim parent-race syllable
tables, and **the swap has since happened**: names now come from the heritage language genome,
keyed on `civilization_id`, so each of the twelve cultures draws from its own tongue.
`parent_race_id` is still passed because it selects the language *family*. The interim tables
are gone; `policies/names.json` is kept only so `policy_revision` can still say which naming
contract a roster was built against (revision 1 interim, revision 2 genome), and its lint fails
if race tables ever reappear.

What the swap fixed is worth recording, because it had been true since these peoples existed:
the interim tables were keyed by parent race, so nine of the twelve cultures read as their
parent, and four — tidekin, gnome, hill_dwarf, frosthold_dwarf — had no table at all and fell
silently through to the human one.

**`name` is therefore nullable.** `heritage.resolve` requires a valid parent race and raises on
a null one, so an unresolvable people is left unnamed and counted alongside
`unresolved_parent_race` rather than given a human name. Before the swap this field was always
a string precisely *because* unresolved peoples silently drew human names — the guarantee was
the bug, not the feature.

`Fixtures/npc-roster-v1.json` pins uids, counts, post assignment, flags and status — and **no
names at all**. That was chosen while the genome was still pending, and it paid: the swap moved
zero bytes of the fixture. Keep it that way. A name in a fixture is a tripwire for a subsystem
this package does not own.

## Determinism, isolation and the switch

Every draw is `child_seed(world seed, 'npc-name-' + uid)`; the helper is a byte-for-byte copy of
the generator's and a test pins them together. One draw per record, keyed on the record's own
uid, so adding a site cannot shift another site's names. `validate_repo` generates a world twice
and byte-compares, which is the gate this block passes.

`terrain_history._attach_npcs` is the only call site (stage 16, and after the last age of an
age-API step). It runs after `_attach_story_web` because it reads `heroes`. It never raises: a
failing revision yields `{version, status: 'failed', error}`, visible in the lab, and the world
still returns. `FANTASY_WORLD_NPCS=0` leaves the key absent. `npcs` is in `STATE_KEYS` and the
lab's `historyStateKeys`, so the stage scrubber hides it before stage 16 like `heroes`.

## Lab

The terrain lab renders the block under **The people**: the summary line, any reported
unresolved counts, a collapsible posts-by-site table, and one card per site listing its
earmarked people with the verbs each can offer. The thousands of ordinary posts are counted,
not listed. A failed block shows its error in red.

## Limitations

An index of posts, not a simulation of people: nobody here works, moves, ages or dies of
anything. `status` is birth state and nothing writes back; a runtime is expected to copy the
block into its own save and flip it there. Posts are the jobs a building needs filled, not a
census — dependents, children and the unemployed are not here, and neither is anyone in a ruin,
camp, college or nest. Site coverage is whatever the planners placed: an unbuildable or partial
plan still gets a site row, with however many posts it managed. The native core does not port
this package; like the cast and the story web, it runs on the core's JSON output, so a cooked
native-only build carries none of the three.
