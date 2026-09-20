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
  - id: nomad-api
    assert: 1
proof:
  - path: Sim/tests/test_terrain_nomads.py
    establishes: gate eligibility, the weighted draw, route construction, stage gating, and block isolation across a generated world
  - path: Sim/tests/test_cult_leyline_writes.py
    establishes: that every cult deepens its circuit node by the same lift whatever its school, that a cult never creates a node, that a band naming no node writes nothing, and that no world carries a pending ley queue
decisions: []
tickets:
  - board/done/NOMADS.md
  - board/done/SDET-LEY-QUEUE-NO-APPLIER.md
  - board/backlog/NOMAD-FISSION.md
  - board/backlog/NOMAD-SURVIVOR-SETTLEMENT.md
  - board/backlog/NOMAD-CARAVAN-ECONOMY.md
  - board/backlog/NOMAD-IRRUPTION-TRIGGER.md
  - board/backlog/NOMAD-CORRUPTION-CONTRACT.md
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
| `add_nomad_routes(result, cfg)` | `terrain_nomad_routes` | camps, legs and day windows for every band |
| `travel_cost(points, cells, cfg)` | `terrain_nomad_routes` | the traversal cost function routes are built on |
| `midsummer_day(z, n)` / `midwinter_day(z, n)` | `terrain_nomad_routes` | the two seasonal anchors |
| `DAY_MARCH_M`, `CAMP_REST`, `CAMP_REST_CEILING`, `GRADE_RELIEF`, `MIDSUMMER_NORTH`, `BUILDERS` | `terrain_nomad_routes` | the authored route constants |
| `apply_nomad_effects(result, cfg)` | `terrain_nomad_effects` | all four write-backs |
| `apply_cultist_leylines`, `apply_raid_pressure`, `apply_caravan_trade`, `seed_survivor_camps` | `terrain_nomad_effects` | the individual write-backs |
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
| Request API | <!-- conformance:version nomad-api=1 --> |

## Proven by

`Sim/tests/test_terrain_nomads.py`, 22 test methods. Isolation is established by a
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
unpoliced gaps. Banditry wants rugged refuge beside prosperity and weak authority, which
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

## Does not establish

- **Lineage fission does not exist.** No band has a child and `fission` never appears as
  a branch.
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
