# Nomads: the bands that walk v1

A finished world carries a `nomads` block: the travelling groups the land raised once the
simulation settled. Unlike `heroes`, `story_web`, `npcs` and `key_locations`, this is not a
separate package reading the world from outside — it is a pass inside `icarus_sim`, run at
stage sixteen and again at the end of every age advance. It reads `ruins`, `history.ages`,
`settlements`, `humans.hamlets`, `roads`, `magic.networks`, `religion`, `villains` and the
terrain layers; it writes only `nomads`.

Reference: `Sim/icarus_sim/terrain_nomads.py`, `nomads.json` (authored balance),
the [schema](../Contracts/schemas/nomads.schema.json), `Sim/tests/test_terrain_nomads.py`,
`board/in-progress/NOMADS.md`.

Versions: the band block is <!-- conformance:version nomads=1 --> and the route pass,
which owns lineage fission and the caravan cut, is <!-- conformance:version nomad-routes=3 -->.
The request API is <!-- conformance:version nomad-api=1 -->.

The route pass moved to 3 on 2026-09-21: `_subdivide` now cuts a caravan leg *before* the
day's march is exceeded rather than after, so no merchant leg is longer than one march. At 2
a leg could reach 1.5 marches, and did -- 1.171 on seed 42 size 33. Leg and station counts
move with it; no field and no enum changed.

## Thesis

**The land decides who walks it.** A start point is read for what surrounds it, and that
reading decides the band's classification before any weight is drawn. There is no roster of
nomads waiting to be placed and no die that picks a kind; there is ground, and the ground
either supports a particular kind of travelling group or it does not.

This matters because the obvious implementation — roll a classification, then find
somewhere to put it — produces cults in places with nothing sacred, caravans with no road
to walk and no market to reach, and bandits in open country with nothing to rob. Those are
not balance problems that tuning fixes. They are the feature being wrong.

So each classification carries a **hard geographic gate**. A classification whose
preconditions fail is ineligible outright, whatever its weight. Only the eligible ones enter
a single weighted draw. **A candidate that satisfies no gate raises nobody** — empty ground
is a result, not a failure, and roughly one candidate in eight produces nothing.

## The six classifications

| Classification | Hard gate | Result |
|---|---|---|
| **survivors** | a ruin destroyed *this age* within reach, **and** a surviving settlement to flee toward | one-way displacement, terminal camp |
| **deserters** | a decided war within reach, **and** rugged cover at the cell | flight from the war site, then a lair |
| **cultists** | a ley node above intensity threshold, a shrine, or a villain's claim within reach — **and** a god actually bound to that school | closed pilgrimage circuit |
| **merchants** | a road within reach, **and** at least two markets above a population floor | linear circuit, stations a day's march apart |
| **bandits** | ruggedness, **and** wealth within strike range, **and** no seat close enough to police it | lair with a strike orbit |
| **wanderers** | forage above threshold, **and** a seasonal swing that moves it | seasonal round, two long moves |

Each rests on a real mechanism rather than a genre convention. Transhumance is two long
moves a year between high summer pasture and sheltered winter ground, not continuous drift.
Caravanserai sat a day's march apart precisely so a caravan never overnighted in the
unpoliced gaps. Banditry wants rugged refuge *beside* prosperity — hills for safety, plains
for targets — and weak authority, which is why the third bandit condition is the absence of
a seat rather than the presence of one. Refugees overwhelmingly stay near home. Pilgrimage
is a fixed repeated circuit whose routes are widely read as tracing ley lines, which is why
cultists snap to the world's existing networks rather than inventing their own geometry.

The gate order — survivors, deserters, cultists, merchants, bandits, wanderers — is most
specific first. It is exported and **appended to, never inserted into**: anything holding an
index into that order would otherwise be renumbered in every world ever generated.

## Two rules the pass obeys

**Every reach is a multiple of `cfg.settlement_spacing`**, never a metre constant or a
raster cell, following the rule `terrain_visitation` already states. World size presets span
200 to 600 km of circumference, and absolute distances authored against the 11.15 km
reference world would either vanish or swallow a continent. The one deliberate exception is
`speed_m_per_day`: a walking pace belongs to the traveller, not to the world.

**Every gate returns a score in zero to one**, so the weight in `nomads.json` is the only
balance lever. This was learned the hard way. With raw scores, ley intensity ran to 4.0
while a bandit's score sat near 0.5, and cultists won nearly every contested draw regardless
of what the weights said — a table that looked tuned and was decorative.

## Export

```
nomads: {version, groups[], counts{}, rolls[], method, limits}
```

A **group** carries `uid` (`nomad-<age>-<node>`, keyed to the terrain node because ordinals
and culture ids are renumbered by an age transition), `classification`, `origin
{kind, id, age}`, `god_id` and `school` for cultists, `size`, `speed_m_per_day`,
`column_length_m`, `disposition`, `seeks`, `carries`, `camps[]`, `legs[]` and `basis`.

`basis` is the field a consumer should build on. It names the actual ruin uid, war site uid,
ley node id, shrine id, market uids or villain claim that classified the band — so a
survivor group names the ruin it fled and the town it is heading for, which is a quest with
no further inference. Note that a `basis` uid can outlive the record it points at: an age
advance moves a ruined city from `settlements.sites` into `ruins`, so **resolve against
both**.

`rolls` records every candidate considered, precipitated or not, with the evidence each gate
produced. It answers "why is there a cult here" and, just as usefully, "why is there nothing
here". It is diagnostic; a consumer building encounters should read `groups`.

## Determinism and isolation

Seeds derive through `child_seed(cfg.seed, 'nomads-v1', nomad_variation)`. Because streams
are keyed by a string domain, a new feature drawing only from new domains cannot perturb any
existing stream. Per-entity domains are `nomad-class-<uid>`, `nomad-camp-<uid>` and
`nomad-route-<uid>`.

The pass is gated on `cfg.phase >= 16`, so `materialize_stage(world, 15)` has no `nomads`
and stage sixteen does. It runs at **both** attach sites — stage sixteen and the age-advance
tail — because an aged world must reclassify against the world it actually has. A band
carried across an advance would name ruins that had moved and refuges that no longer stood.
The block is replaced wholesale, never merged.

Isolation is proven by a structural comparison of generated worlds before and after: a
declared set of blocks that may change, each with a specific assertion about how. Raw
sha256 equality is useless once a feature declares a new key, and a blunt allowlist waves
through the interesting failures.

## Lab

Bands appear from stage sixteen. `nomads` is listed in `STATE_KEYS` and in the lab's
`historyStateKeys`; omitting the latter does not raise, it silently shows the final bands at
every earlier stage, because `materialize_stage` builds from everything *not* in that list.

## Lineage fission

A herding clan whose head count passes what its own round carries splits. The daughter is
seated on a camp of the parent's round — summer pasture first — names the parent in
`parent_uid`, and carries one leg of branch `fission` joining its round to the parent's
start camp. That is the only leg whose `to` names a camp of a *different* band; it has no
day window, because the split happened once rather than every year, and it is left out of
`round_length_m`.

Capacity is dimensionless. `round_capacity` reads the classification's authored `size`
band and the forage of the round picks a point on it. Head per square kilometre was
rejected for the same reason clearance scales the placement rate instead of skipping
cells: an absolute figure reads the raster rather than the land, and the same clan on the
same ground would outgrow it at one resolution and not another.

**Fission runs once, at placement, not once an age.** That was an open question and the
answer is recorded rather than assumed. Nothing kills a band, so a per-age rule grows the
population every age with no term removing anyone; a band does not survive an age turn
anyway, because `add_nomads` replaces the block wholesale; and an age is five thousand
years ([028](decisions/028-an-age-is-five-thousand-years.md)), so a per-age rule fires
once per two hundred generations of herders. The cost is that a clan's descent is not
legible across ages and no band has a grandchild. See `docs/conformance/nomads.md`.

A child is **not** recorded in `rolls`, which answers what the point process considered at
a point; a child was never considered. Every band either names a roll or names a parent
that does.

## Limitations

A fissioned parent keeps its own head count: the route pass has no demographic model, and
rewriting a placed band's size from there would make the authored size band a fiction.
`rich_forage` is calibrated against measured rounds rather than derived. A daughter whose
inherited camp cannot support a round of its own is refused rather than recorded as a
stranded child.

Circuits are static: a band walks the same round every year and nothing re-routes it when
the world changes underneath.

A band whose circuit cannot be built carries `route_status: "stranded"` and keeps its start
camp. That is not a failure to hide — it is the case the classification gate cannot see on
its own, because the wanderer gate checks forage and seasonal swing but not whether both
summer and winter ground are actually *reachable*. Reachability needs the traversal cost
function the route pass builds, so a herder with nowhere to winter is discovered here and
reported rather than pretended away.

Sizes and speeds are authored constants, not derived from local carrying capacity. No band
consumes forage, fights, or dies.

The write-backs are deliberately uneven in depth. Cult devotion and raid pressure are
genuine edits to `magic.networks` and `threat_assessments`. Caravan throughput is a share
of road nodes ridden, not a modelled cargo volume, and nothing consumes it yet. Survivor
bands that reached safety are recorded as **settlement candidates rather than founded
settlements**, because founding one at stage sixteen would mean re-running settlement
generation after every downstream block has already read the settlements it produced.

A candidate is **absorbed by the refuge at the next age boundary**, not founded there later.
Its `node` is the refuge city's own node -- `_flight` routes the band to the node of the
site named by `basis['refuge_uid']` -- so founding would put a second settlement on a
standing city. `absorb_survivor_camps` credits that city with the band's headcount if it
survived the boundary, stamping `absorbed_age` and `absorbed_into` on the candidate and
`absorbed_refugees` and `absorbed_bands` on the city. The block is therefore a **migration
ledger, not a founding queue**.

Raid pressure is added *after* the threat assessment was evaluated, so it widens
`regional_threat` without having influenced anything that already read it.

**Every cult writes its own ground, hidden school or known.** There used to be a
`pending_ley_edits` queue here, on the grounds that an age advance would refuse a
hidden-school node; that was tested and is false — the refusal applies to leyline edits a
caller hands to an age-advance request, not to the world's own networks — so the queue was
removed rather than given the applier it never had. Order independence is unaffected: the
pass iterates bands by `uid`, so two bands requesting in a different order cannot produce
two different worlds.

What a cult can do is narrow, and deliberately so: it **deepens** a node that already
exists, lifting it by a fixed fraction of its current charge toward a ceiling of four. It
never opens new ground. A band whose circuit names no ley node, or names one that is not in
its school's network, writes nothing at all. Only the corruption API puts a node into a
hidden network in the first place.

Cult prevalence is a function of how violent the world's history was, not an authored
constant. Every destroyed city leaves a ley key point at intensity 3.5 to 4.0, so a bloody
age manufactures sacred ground and cults follow it. On seed 42 at size 17, one age advance
took cultists from 5 of 13 bands to 14 of 21. That is the simulation being coherent rather
than a fault, but it means tuning cult frequency means tuning the weight, not the gate.
