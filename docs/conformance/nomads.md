---
conformance: 1
record: nomads
tier: EXERCISED
summary: Raises travelling bands after the simulation settles, classified by a hard geographic gate on the ground they start from, with routes, seasonal camps and four write-backs into the world they walk through.
modules:
  - Sim/icarus_sim/terrain_nomads.py
  - Sim/icarus_sim/terrain_nomad_routes.py
  - Sim/icarus_sim/terrain_nomad_effects.py
  - Sim/icarus_sim/terrain_nomad_api.py
emits:
  - path: nomads
    schema: Contracts/schemas/nomads.schema.json
versions:
  - id: nomads
    assert: 1
  - id: nomad-routes
    assert: 3
  - id: nomad-api
    assert: 1
proof:
  - path: Sim/tests/test_terrain_nomads.py
    establishes: gate eligibility, the weighted draw, route construction, stage gating, and block isolation across a generated world
  - path: Sim/tests/test_cult_leyline_writes.py
    establishes: that every cult deepens its circuit node by the same lift whatever its school, that a cult never creates a node, that a band naming no node writes nothing, and that no world carries a pending ley queue
  - path: Sim/tests/test_survivor_absorption.py
    establishes: that a refugee band is absorbed by the refuge it reached rather than founding a settlement on it, that a refuge which fell at the boundary absorbs nobody, that absorbing the same band twice does not breed people, that the credited city is resolved through the band's own refuge_uid rather than through the candidate's node, and that the absorbed count is carried across the rebuild that re-derives population_estimate
decisions: []
tickets:
  - board/done/NOMADS.md
  - board/done/SDET-LEY-QUEUE-NO-APPLIER.md
  - board/done/NOMAD-FISSION.md
  - board/done/NOMAD-SURVIVOR-SETTLEMENT.md
  - board/done/NOMAD-SUBDIVIDE-DROPS-THE-LAST-CUT.md
  - board/retired/NOMAD-CARAVAN-ECONOMY.md
  - board/done/NOMAD-IRRUPTION-TRIGGER.md
  - board/done/NOMAD-CORRUPTION-CONTRACT.md
---

# Conformance: nomads

## What it produces

Travelling bands in one of six classifications — `survivors`, `deserters`, `cultists`,
`merchants`, `bandits`, `wanderers` — each with camps, a route, a disposition, and a
`basis` naming the real world object that classified it. A candidate satisfying no gate
raises nobody; roughly one in eight produces nothing, and that is a result rather than a
failure.

Unlike `heroes`, `story_web`, `npcs` and `key_locations`, this is a pass inside
`icarus_sim` rather than a package reading the world from outside.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `add_nomads(result, cfg)` | `terrain_nomads` | the whole classification pass; writes `result['nomads']` |
| `ground(result, cfg, radius, points)` | `terrain_nomads` | the per-cell reading every gate consumes |
| `policy()` | `terrain_nomads` | the parsed `nomads.json` balance table |
| `ruggedness(fields)` | `terrain_nomads` | the 0–1 cover score the deserter and bandit gates read |
| `seasonal_swing(result, x, z)` | `terrain_nomads` | the forage swing the wanderer gate reads |
| `population_of(site)` | `terrain_nomads` | the market-floor population for the merchant gate |
| `CLASSIFICATIONS` | `terrain_nomads` | the gate order, most specific first — **append-only** |
| `GATES`, `ORIGIN_CAMP_KIND` | `terrain_nomads` | gate dispatch, and the camp kind each classification opens with |
| `add_nomad_routes(result, cfg)` | `terrain_nomad_routes` | camps, legs and day windows for every band, then lineage fission |
| `apply_fission(...)` | `terrain_nomad_routes` | the daughter clans, re-derived rather than accumulated |
| `round_forage(band, cells)` / `round_capacity(band, pol, forage)` | `terrain_nomad_routes` | the fission trigger's two halves, callable on their own |
| `ROUTES_VERSION` | `terrain_nomad_routes` | the route pass version, separate from the band block's |
| `travel_cost(points, cells, cfg)` | `terrain_nomad_routes` | the traversal cost function routes are built on |
| `midsummer_day(z, n)` / `midwinter_day(z, n)` | `terrain_nomad_routes` | the two seasonal anchors |
| `DAY_MARCH_M`, `CAMP_REST`, `CAMP_REST_CEILING`, `GRADE_RELIEF`, `MIDSUMMER_NORTH`, `BUILDERS` | `terrain_nomad_routes` | the authored route constants |
| `apply_nomad_effects(result, cfg)` | `terrain_nomad_effects` | all four write-backs |
| `apply_cultist_leylines`, `apply_raid_pressure`, `apply_caravan_trade`, `seed_survivor_camps` | `terrain_nomad_effects` | the individual write-backs |
| `absorb_survivor_camps(result, survivors, age)` | `terrain_nomad_effects` | the age-boundary pass that grows a refuge by the band that reached it; called from `terrain_history.age_transition`, not from `apply_nomad_effects` |
| `DEVOTION_GAIN`, `INTENSITY_CEILING`, `RAID_WEIGHT`, `STRIKE_SPACINGS` | `terrain_nomad_effects` | the write-back magnitudes |
| `validate_nomad_request(body)` / `nomad_request(body)` | `terrain_nomad_api` | the external request surface; `FIELDS` is the exact accepted key set |

## Inputs it reads

`ruins`, `history.ages`, `settlements`, `humans.hamlets`, `roads`, `magic.networks`,
`religion`, `villains`, and the terrain layers. It writes only `nomads`, plus the four
declared write-backs below.

## Artifacts it writes

`world['nomads'] = {version, groups[], counts{}, rolls[], method, limits}`, governed by
`Contracts/schemas/nomads.schema.json`.

A group's `uid` is `nomad-<age>-<node>`, **keyed to the terrain node** because ordinals
and culture ids are renumbered by an age transition. That keying is an **invariant**: an
id that survives an age is the only kind a consumer can hold across one.

`basis` names the actual ruin uid, war site uid, ley node id, shrine id, market uids or
villain claim that classified the band. A `basis` uid can outlive the record it points
at — an age advance moves a ruined city from `settlements.sites` into `ruins` — so
**resolve against both**. `rolls` records every candidate considered, precipitated or
not; it is diagnostic, and a consumer building encounters reads `groups`.

Write-backs additionally mutate `magic.networks` (cult devotion) and
`threat_assessments` (raid pressure).

`settlement_candidates` is a **migration ledger, not a founding queue**. Each entry's
`node` is the refuge city's own node rather than free ground -- true by construction,
because `_flight` routes a survivor band to the node of the site whose uid is
`basis['refuge_uid']` -- so at the next age boundary the refuge **absorbs** the band
instead of a settlement being founded on top of a standing city.
`absorb_survivor_camps` runs inside `age_transition` immediately before `rebuild_tail`,
after the fates are decided and against the list of cities that survived them: a refuge
that fell absorbs nobody. It stamps `absorbed_age` and `absorbed_into` on the candidate and
credits the city with `absorbed_refugees` and a sorted `absorbed_bands`, and it is
idempotent by band uid, because the candidate list can be carried unchanged into a later
advance. Measured on seed 42 size 17: the age-3 boundary leaves 3 of 12 cities standing and
takes all three refuges with it, so that world absorbs nobody -- the filter working, not the
pass failing.

Those two city fields are in `CARRIED_SURVIVOR_KEYS` because they have to be:
`add_settlements` re-derives `population_estimate` from the population budget on every
rebuild, so refugees written into that field at a boundary would be erased by the rebuild.
The count is added back after the capacity split, which keeps the split a pure function of
the ground the city farms. Nothing writes these fields during generation -- candidates
appear at stage 16, after both generation-internal age transitions -- so they are visible
only on a world that has been advanced.

**Determinism is an invariant.** Seeds derive through
`child_seed(cfg.seed, 'nomads-v1', nomad_variation)`, with per-entity domains
`nomad-class-<uid>`, `nomad-camp-<uid>` and `nomad-route-<uid>`. Because streams are
keyed by a string domain, a feature drawing only from new domains cannot perturb an
existing stream. Cult leyline writes iterate `sorted(bands, key=lambda b: b['uid'])`
specifically so that two bands requesting in a different order cannot produce two
different worlds; that covers hidden and known schools alike, since both now write
directly.

## Where it runs

Gated on `cfg.phase >= 16`, so `materialize_stage(world, 15)` has no `nomads` and stage
sixteen does. It runs at **three** sites — stage sixteen, the age-advance tail, and a
time advance — because an aged world must reclassify against the world it actually has.
The block is replaced wholesale, never merged.

The third site means **`nomads` and `nomad_routes` are not stable between reads of a live
world.** `terrain_time.advance_time_request` re-runs `add_nomads` on a one-year cadence
and `add_nomad_routes` on a one-month cadence, at an arbitrary day chosen by the caller,
with a seed derived from the absolute step index rather than from `cfg.seed` alone — that
derivation is what makes a band move at all between two ages. A consumer may cache these
blocks against a `world_clock.day`, and may not cache them against the world's identity.
`apply_nomad_effects` runs on the tick path for the same reason it runs on the age path:
`add_nomads` replaces the block wholesale, which discards `nomads.effects` and would
otherwise leave the previous population's cultist ley deepening, raid pressure, ridden
roads and survivor camps standing in a world whose bands no longer exist.

Nothing else about this capability changes: the gate, the classifications and the draw
are as described above, and a tick reaches them only through the same three public
passes.

`nomads` is in `STATE_KEYS` and in the lab's `historyStateKeys`. Omitting the second
does not raise: `materialize_stage` builds from everything *not* in that list, so the
lab would silently show the final bands at every earlier stage.

## Versions asserted

| What | Value |
|---|---|
| `nomads` block and pass | <!-- conformance:version nomads=1 --> |
| `nomads.routes` block and the route pass | <!-- conformance:version nomad-routes=3 --> |
| Request API | <!-- conformance:version nomad-api=1 --> |

The route pass moved to 2 when lineage fission landed, and the band block did not move
with it. That split is deliberate and is the precise statement of what changed: no field
of a band is new, no enum gained a member, and a v1 document still validates field for
field — `parent_uid` and the `fission` branch were both declared from the start. What a
consumer could misread is the **occupancy** of those slots. Under routes v1 `parent_uid`
was null on every band and `fission` never appeared, and the v1 `limits` sentence promised
exactly that, so code written against it may have treated every band as independently
placed and every band as present in `rolls`. Neither holds at 2.

It moved again to **3** on 2026-09-21, and for the same kind of reason: no field is new and
a v2 document still validates, but the pass's central guarantee changed. `_subdivide` now
closes a caravan leg at the last node inside the day's march instead of the first node past
it, so **no merchant leg exceeds one day's march**. At 2 the tail condition declined to cut
a remainder of half a march or less, which absorbed it backwards and let a segment reach
1.5 marches -- measured at 1.171 on seed 42 size 33, where a 12-node leg ran 40980.3 m
against a 35000 m march. A consumer that sized a day's travel off the longest leg, or
counted a route's stations, reads different numbers at 3: legs are shorter and there are
more of them.

## Proven by

`Sim/tests/test_terrain_nomads.py`, 27 test methods. Isolation is established by a
structural comparison of generated worlds before and after: a declared set of blocks
that may change, each with a specific assertion about how. Raw sha256 equality is
useless once a feature declares a new key, and a blunt allowlist waves through the
interesting failures.

## Why it works this way

**The land decides who walks it.** A start point is read for what surrounds it, and that
reading fixes the classification before any weight is drawn. The obvious implementation
— roll a classification, then find somewhere to put it — produces cults where nothing is
sacred, caravans with no road and no market, and bandits in open country with nothing to
rob. Those are not balance problems that tuning fixes; they are the feature being wrong.

So each classification carries a hard geographic gate and a failed precondition makes it
ineligible outright, whatever its weight. Only eligible classifications enter a single
weighted draw.

| Classification | Hard gate |
|---|---|
| survivors | a ruin destroyed *this age* within reach, and a surviving settlement to flee toward |
| deserters | a decided war within reach, and rugged cover at the cell |
| cultists | a ley node above intensity, a shrine, or a villain's claim within reach — and a god actually bound to that school |
| merchants | a road within reach, and at least two markets above a population floor |
| bandits | ruggedness, and wealth within strike range, and no seat close enough to police it |
| wanderers | forage above threshold, and a seasonal swing that moves it |

Each rests on a mechanism rather than a genre convention. Transhumance is two long moves
a year between summer pasture and sheltered winter ground, not continuous drift.
Caravanserai sat a day's march apart precisely so a caravan never overnighted in the
unpoliced gaps, which is a bound and not a target: `_subdivide` closes a leg at the last
node **inside** `DAY_MARCH_M` and stands a station there, so no merchant leg is longer than
one march. Cutting on the crossing instead would overshoot by a graph step -- 6250 m at
size 33 -- and the guarantee would be a slogan. What it cannot cut is a single graph step
wider than a march, or a leg with no interior node to stand a station on; both are
properties of the route graph, and neither arises at any raster the generator ships. Banditry wants rugged refuge beside prosperity and weak authority, which
is why the third bandit condition is the *absence* of a seat. Refugees overwhelmingly
stay near home. Pilgrimage is a fixed repeated circuit widely read as tracing ley lines,
which is why cultists snap to the world's existing networks rather than inventing
geometry.

Two rules the pass obeys. **Every reach is a multiple of `cfg.settlement_spacing`**,
never a metre constant: world presets span 200 to 600 km of circumference, and distances
authored against the 11.15 km reference world would either vanish or swallow a
continent. The deliberate exception is `speed_m_per_day`, because a walking pace belongs
to the traveller rather than the world. **Every gate returns a score in zero to one**, so
the weight in `nomads.json` is the only balance lever — learned the hard way, because
with raw scores ley intensity ran to 4.0 against a bandit's 0.5 and cultists won nearly
every contested draw regardless of the table, which looked tuned and was decorative.

Cult prevalence is a function of how violent the world's history was rather than an
authored constant: every destroyed city leaves a ley key point at intensity 3.5 to 4.0,
so a bloody age manufactures sacred ground. Tuning cult frequency means tuning the
weight, not the gate.

## Lineage fission

A clan whose head count passes what its own round carries splits, once, when it is
placed. The daughter is seated on a camp of the parent's round — summer pasture first,
because that is the ground a herd that has outgrown its range competes for — names the
parent in `parent_uid`, and carries one leg of branch `fission` joining its round to the
parent's start camp. That leg is the only one whose `to` names a camp of another band, it
carries no day window because the split happened once rather than every year, and it is
excluded from `round_length_m`.

Capacity is **dimensionless**: `round_capacity` reads the classification's authored
`size` band and the forage of the round picks a point on it, from the gate's forage floor
up to the authored `rich_forage`. A head-per-square-kilometre figure was rejected for the
reason the placement rate rejected a clearance *rejection*: it reads the raster rather
than the land. A cell is 52 km² at raster 17 against 13 km² at raster 33, so the same
clan on the same ground would outgrow it at one resolution and not the other.

**Cadence — an open design question, decided here so it can be reversed knowingly.**
Fission runs **once at placement**, not at every age transition. Three reasons, the first
two load-bearing:

1. Nothing kills a band, so a per-age rule grows the population every age with no term
   removing anyone. Once at placement is bounded by construction: at most one child per
   placed band and a child never splits, so a world holds fewer than twice the bands it
   placed. The rejected reading needs both a ceiling and a death term that do not exist.
2. A band does not survive an age anyway. `add_nomads` replaces the block wholesale at
   every age turn, deliberately, so there is no surviving parent at a boundary to split
   from; "fission per age" would have meant inventing a lineage across a gap the
   generator does not model.
3. An age is five thousand years ([028](../decisions/028-an-age-is-five-thousand-years.md),
   ruled the same day this was built). A rule firing once per age fires once per two
   hundred generations of herders. The cadence argument that made per-age attractive was
   written when an age was a century.

What is given up: a clan's descent is not legible across ages, and no band has a
grandchild.

A child is **not** written into `rolls`. `rolls` records what the point process considered
at a candidate point, and a child was never considered — it descends. The invariant a
consumer can hold is that every band either names a roll or names a parent that does.

`nomads.counts` is recomputed from the band set at the end of the route pass rather than
incremented, because three callers add to it — placement, the request API and fission —
and a tally that is only ever incremented cannot survive a pass that removes anybody.

## Does not establish

- Fission is a split, not a demographic model. A fissioned parent keeps its own head
  count: the route pass has no population model, and rewriting a placed band's `size`
  from here would make the authored size band a fiction. `rich_forage` is calibrated
  against measured rounds (0.32–0.57 on seed 42 at size 33) rather than derived.
- A daughter clan whose inherited camp cannot support a round of its own is **refused**,
  not recorded as a stranded child. A segment with nowhere to winter has not split.
- Circuits are static. A band walks the same round every year and nothing re-routes it
  when the world changes underneath.
- `route_status: "stranded"` is a real outcome, not an error. The wanderer gate checks
  forage and seasonal swing but not whether summer and winter ground are mutually
  *reachable*, which needs the route pass's cost function — so a herder with nowhere to
  winter is discovered late and reported rather than pretended away.
- Sizes and speeds are **authored constants**, not derived from carrying capacity. No
  band consumes forage, fights, or dies.
- Caravan throughput is a share of road nodes ridden, not a modelled cargo volume, and
  nothing consumes it.
- Survivor bands are recorded as **settlement candidates, not founded settlements**.
  Founding one at stage sixteen would mean re-running settlement generation after every
  downstream block had already read the settlements it produced.
- Raid pressure is added *after* the threat assessment was evaluated, so it widens
  `regional_threat` without having influenced anything that already read it.
- **The `pending_ley_edits` round trip is retired, not unfinished.** It rested on the
  claim that `advance_age_request` would refuse a hidden-school node at the next age
  boundary, so a cult of a hidden god had to queue its intent for a corruption-side
  applier. That claim was tested and is false: the gate validates only the caller-supplied
  edits of an age-advance request, never the world's own networks, and a world carrying a
  hidden-school node — newly created or intensified — is accepted. Every cult now writes
  directly, by the same lift. The invariant that does hold is narrower and is pinned by
  `Sim/tests/test_cult_leyline_writes.py`: a cult may only deepen a hidden node, and only
  the corruption API creates one.
- `beast_movements` and `encounters` are **not owned here**.
