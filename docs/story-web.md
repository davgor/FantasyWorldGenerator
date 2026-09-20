# Story web: the arcs every hero could walk v1

A finished world carries a `story_web` block beside `heroes`: for every living person and
Dread, the trope spokes their own record admits, the deterministic weight of each, the
offered resting hook, the offered trope's three acts bound to the hero's own names, and
the threads each act can exit along. The compiler is a wholly separate package,
`Sim/story_web/`, called once right after the hero generator attaches its block (and again
after every age advance). It reads `heroes` and a few exported world facts and writes only
`story_web`. It never imports `icarus_sim` or `hero_generator`: a saved `world.json` with a
cast serves it as well as a live result.

Reference: `Sim/story_web/` (package), `policies/*.json` (authored data), the
[schema](../Contracts/schemas/story-web.schema.json), `Fixtures/story-web-v1.json`,
`Sim/tests/test_story_web.py`, `tools/story_web_report.py`.

## Thesis

The hero generator exports a diary, not a script: an event log, a situation, a claim,
bonds, a persona. The story web is what an orchestrator would otherwise have to plan from
that diary, precomputed. Each **trope** is a spoke: a character arc (Revenge, Redemption,
The Siege, The Warden's Line, …) with an entry predicate over facts, three acts, and a
pull on the alignment plane. A hero's **web** is the set of spokes their facts admit,
weighted, with the heaviest offered as the hook they rest with. No draw and no model
decide an assignment: the same world and policy revisions give the same web byte for byte.

    weight = boosts × alignment_fit × archetype_fit × claim_fit

- **boosts**: the trope's factor for every listed fact the hero carries (`policies/tropes.json`).
- **alignment_fit**: `max(floor, 1 + gain × (pull · alignment) / |pull|)`; a spoke that pulls
  the way the hero already leans is favoured, an opposed one is damped, never removed.
- **archetype_fit**: `fits_factor` when the hero's archetype is named in the trope's `fits`.
- **claim_fit**: `claim_factor` when the hero's claim verb is named in the trope's `claims`.

The offered spoke is the heaviest; ties break on trope id. The rest are **armed**. All
constants live in `policies/weights.json` and the breakdown is exported per spoke.

## Facts

A precondition token is `namespace:value`; a leading `!` negates. Person facts come from
the exported record: its selection features verbatim, `role:`, `status:`, `tier:`,
`archetype:`, `claim:<verb|none>`, `bond:<kind>`, `home:set|none`, `lost:set`,
`presence:<situation>`, `faces:two`, `companion:eligible`. The countryside wells add `role:reeve|castellan|harbourmaster|keeper`, `hamlet:farming|resource|starving|threatened`, `fortress:pressed`, `port:terminal` and `shrine:ruin|cult`; The Famine, The Siege, The Hunt, The Vow, The Blight and The Founding carry entries for them. World facts are computed once per
compile and asked per hero: `world:war_pressure` and `world:threatened` from the home city's
threat assessment, and from its version-3 war outlook `world:war_recent`, `world:enemy_living`
and `world:war_risk` (the forecast The Siege reads; the chronic pressure only arms threads) and
`world:war_hunger` (the hungry side of a supply-pressed pair, which The March reads);
`world:food_deficit` from its rural core and `world:famine` from the seasonal food model
(coverage below `weights.famine_coverage`, which The Famine reads); person facts
`war:veteran`, `war:victor_recent` and `war:defeated_recent` from war deeds against the
cast's final age, which The Spoils, The Veteran, The Peace and The Pursuit read; `world:surge` and
`world:hollow_night` from the lunar almanac, `world:node_intense` at a held key point,
`world:rival_living` / `world:rival_dread` from bonds against the living cast,
`world:relic_resting` and `world:camp_at_lost` at the lost ruin, `world:mantle_open`,
`world:other_realm`, `world:dread_living`, `world:realm_has_sovereign`, `world:realm_tyrant`.
The full vocabulary is `story_web.facts.FACTS`; the catalogue lint rejects any other token.

## Acts, options and threads

Each trope has exactly three acts. An act has one **prompt** (the ask, in character, with
`{hero}`, `{rival}`, `{home}`, `{lost}`, `{relic}`, `{realm}` slots bound from the record), a
typed **completion** (`target` + `state`), an **abandonment** deadline in days (plus the
implicit `protagonist_dead` and `target_gone`), and two to four **options**, each carrying a
bounded alignment delta and an effect tag. Outcomes are not pre-recorded: `examples` are prose.

**Threads** say where the hero can step at any act exit; they belong to the web, not to one
act. For every other trope the compiler tries every entry conjunction and keeps the cheapest
way in: `open` when the trope is eligible now and its pull agrees with the hero (the dot
product of pull and alignment is not negative); `alignment` when it is eligible but pulls
against the hero, naming the axis that pulls hardest, so the walker takes it only if the
alignment moved that way during the act; `claim` when only a different claim verb is
missing; `feature` when one or two runtime-gainable facts (`weights.gainable_features`)
would make it eligible. The thread's weight is the trope's weight once the condition holds
(changed verb or gained facts applied). A thread is **cut** when the archetype's typed
constraints (`policies/constraints.json`: claim locked, drift locked, allowed verbs) forbid
the change it needs. Threads are ranked open first, then alignment, claim, feature, then by
weight, and capped by `weights.max_threads_per_act`.

## Rest

Every woven hero rests with one **hook** (the offered trope's first-act prompt; empty for
The Lair, the one silent, world-driven spoke a Dread walks), the **armed** spokes in weight
order, and an **initiative day** (`weights.initiative_days` plus a seeded stagger of up to
30 days). The walker that fires hooks on a world event, a player
bite or initiative, applies deltas, and resolves abandonment offstage is later work; this
block is its compiled input.

## Export

```
story_web: {version 1, status ok|failed, error?, policy_revision {tropes, constraints, weights}, heroes_revision,
  summary {woven, unwoven, tropes, reachable_tropes, offered {trope: count}, mean_spokes},
  webs[] {uid, display_name, role, archetype, alignment {law, good, code, angle}, claim, facts[], constraints,
          spokes[] {trope_id, name, weight, breakdown, angle}, offered,
          rest {hook {trope_id, act_id, prompt, expires_day}, armed[] {trope_id, weight}, initiative_day},
          acts[3] {id, title, ring, prompt, completion, abandonment, options[]},
          threads[] {to, weight, condition, cut}, considered[] {trope_id, missing[]}, examples[]},
  unwoven[] {uid, display_name, archetype, facts[], nearest[]},
  tropes[] {id, name, pull, cast, angle}, unreachable_tropes[], method, limits}
```

## Determinism, isolation and the switch

There are no draws in assignment; the only seeded value is the initiative stagger,
`child_seed(world seed, 'web-initiative-' + uid)`, byte-for-byte the generator's helper.
`terrain_history._attach_story_web` is the only call site (stage 16 and after the last age
of an age-API step, immediately after `_attach_heroes`). It pops any previous block and
calls `story_web.attach`, which never raises: a failing revision yields
`{version, status: 'failed', error}`, visible in the lab, and the world still returns.
`FANTASY_WORLD_STORY_WEB=0` leaves the key absent. `story_web` is in `STATE_KEYS` and the
lab's `historyStateKeys`, so the stage scrubber hides it before stage 16 like `heroes`.

## Lab

The terrain lab renders the block under **Story webs**: an offered-trope histogram, then one
card per woven hero with a spiderweb (spokes at their pull angle, thickness by weight, the
offered spoke gold with its three act nodes, the web's threads drawn from those nodes: solid
open, dashed conditional, red cut; the hero's alignment as a coloured marker), the hook, the
armed spokes, a details block with all three acts, their options and the threads, and, behind
the cast panel's truth checkbox, the weight breakdown, facts and nearest refused tropes.
Unwoven heroes and unreachable tropes are listed under the cards. The atlas hover names the
offered spoke beside each living hero.

## Calibration

`python tools/story_web_report.py --fixture` (or `--world path.json`, or `--seed N --size S`)
prints every woven hero with their log, situation, weight table and hook, then flags
assignments to look at: a generic seat spoke beating a spoke that names the hero's
archetype, an offered spoke that rejects the hero's claim verb, a runner-up within ten
percent, and unwoven heroes. The equation is tuned by editing `policies/*.json` and
re-running the report; the pinned fixture then has to be regenerated on purpose.

## Limitations

A compiled offer, not a running story: nothing here advances an act, applies a delta,
resolves an abandonment or writes to the cast. World facts are coarse (a surge anywhere
counts for every magic-adjacent person; reach is the home city). Tropes whose every entry
needs a feature nothing computes yet (`story_web.NEVER_COMPUTED`: person-shaped Dreads,
lost allies, two-school deeds) would be listed as unreachable rather than hidden; with the
current catalogue every trope has at least one satisfiable entry. Several tropes with a
neutral pull share angle 0 on the web; the lab fans tied spokes apart by a few degrees for
legibility only. The native core does not port this package; it runs on the core's JSON
output like any other consumer.
