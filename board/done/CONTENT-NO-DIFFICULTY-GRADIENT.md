# CONTENT-NO-DIFFICULTY-GRADIENT — danger has no spatial relationship to safety

**Delivered 2026-09-21. The fix this card proposed had already shipped and the card could
not see it.** The continuous distance factor is `danger_ramp`, landed 2026-09-20 in
`4778a3e` against this card's own name. It works — danger is ordered outward across every
tier it moves, and the order collapses when it is ablated — but **none of that reaches the
statistic this card chose to measure**, because the placed set is pinned to the cells a tier
reaches at every width this product ships.

So what landed here is the measurement, the two numbers that make the gradient legible where
it is exact, a corrected acceptance criterion, and a ruling on the design question.
**Nothing about placement changed. No site moved.**

The short version of the rewrite: *"median distance monotonic in tier across at least three
tiers, by a margin larger than the spread within a tier"* is wrong in three separate ways —
the median of the placed set is the wrong series, five tiers is one more than the mechanism
can order, and the margin clause is unsatisfiable by arithmetic rather than by placement.

Everything below the resolution is the original text, kept because its mechanism analysis is
still correct and its `key_locations` half is still open work that this card does not close.

---

## Resolution

### The premise, re-tested

Seed 42, size 33, phase 13, on the current tree — which is after `BESTIARY-PYRAMID-RETUNE`
moved every monster site. Distance from each site to the nearest of the 188 settled anchors
`settled_directions()` actually uses (settlements, ports, hamlets), so this is the code's own
anchor set and not the cities-only one the reconciliation used. Cell pitch 3.419 km.

| | t1 | t2 | t3 | t4 | t5 | spread |
|---|---|---|---|---|---|---|
| `beast_nests` median km | 5.51 | 5.51 | 5.37 | 5.58 | 5.77 | **0.41** |
| `wildlife` median km | 4.42 | 4.85 | 5.58 | 5.89 | — | **1.47** |

**The monster claim reproduces** — 0.41 km across five tiers, and not monotone. **The animal
claim does not.** This card records animals as flat to 0.37 km with a tier-1 prey and a
tier-4 predator both at 6.45 km; they are 1.47 km apart and monotone across all four live
tiers. That figure predates tonight's settlement changes and should not be requoted.

### The mechanism the card proposed is already in the tree and does not reach the metric

`danger_ramp` multiplies the placement rate by a continuous function of distance, signed by
tier — exactly the fix this card asked for. Ablating it to a constant `1.0` and re-running
both passes on the same world — every arm below is the same world with one term changed,
never a different world — gives monster medians of 5.51 / 5.51 / 5.19 / 5.51 / 5.58.
**Removing the whole mechanism moves the tier spread from 0.41 km to 0.39 km.** Animals
move from 1.47 km to 1.30 km. A
fourth arm with the ramp's span multiplied by twenty reproduces the ablated arm to the metre,
which is the mechanism confirming its own documentation: a *constant* multiplier renormalises
away exactly in `budget`, so only the ramp's slope can do anything at all.

Turning the ramp up instead of off — floor 0 rather than 0.2, which is as strong as this shape
can be made — moves the monster spread to 0.76 km. **The strongest version of the mechanism
buys 0.35 km against a within-tier spread of 6.9 km** (p10 3.1 km, p90 10.0 km).

### Why: the same ceiling the pyramid card found

`saturation` says it directly. Monster cells reached and lairs placed, by tier:

| tier | cells reached | placed | share of the ceiling |
|---|---|---|---|
| 1 | 358 | 350 | 98% |
| 2 | 366 | 359 | 98% |
| 3 | 345 | 304 | 88% |
| 4 | 326 | 277 | 85% |
| 5 | 342 | 204 | 60% |

A tier holds one lair per cell, and at this raster every tier is nearly full. **A saturated
tier fills the cells it reaches whatever the rate said about which of them it preferred**, so
the placed distribution is the *cell* distribution — whose medians are 5.51 / 5.51 / 5.19 /
5.19 / 5.51, flat for the same reason the card already gives: the only tier-keyed gate on a
cell is a clearance of 250 m to 1250 m against a 3.4 km pitch.

### Above the shipped raster the mechanism does reach the placed set

Seed 42 at **size 129**, pitch 875 m — chosen because tier-5 clearance crosses one cell there,
and it is below the 192 territory crossing that
[BESTIARY-NOBODY-HAS-TESTED-ABOVE-THE-CROSSING](../backlog/BESTIARY-NOBODY-HAS-TESTED-ABOVE-THE-CROSSING.md)
names, so only one boundary is being crossed. 410 settled anchors. Tier 1 is 48% of its
ceiling and tier 5 is **7.5%**, so the rate decides placement for the first time:

| arm | t1 | t2 | t3 | t4 | t5 | t5 − t1 |
|---|---|---|---|---|---|---|
| shipped | 2.64 | 3.11 | 1.98 | 2.52 | 5.02 | **2.38 km** |
| ramp ablated | 2.97 | 3.20 | 2.05 | 2.34 | 4.21 | 1.23 km |
| ramp at full strength | 2.34 | 3.03 | 2.05 | 2.73 | 6.25 | 3.90 km |

The ramp's own contribution to the top-to-bottom gap is **0.19 km at size 33 and 1.15 km at
size 129**, six times larger, and the reason is saturation rather than anything about the
ramp. So the card's "no seed can produce a gradient" is right inside the measured band and
wrong above it, and the boundary is saturation, not the clearance arithmetic the card
extrapolates from.

### The clearance is inert as a gradient and is not inert

This card's strongest line is that `nest_settlement_clearance` is "too small to move
anything". As a *distance* term that is right — 250 m to 1250 m against a 3.4 km pitch. As a
*membership* term it is not, and the reachability work in the same package found it:
**57 monster profiles, 15% of the catalogue, are unplaceable on the reference world because
of this constant** — 32 on seed 7 and 1 on seed 73, so it is a world property and not a
catalogue one. They are the graveyard and barrow creatures. `graves` is a field that exists
where people bury people, so their eligible cells can all be cells settlements stand on,
and those are exactly the cells the clearance refuses. Raising the constant — which this
card recommends doing anyway, "for the same reason `settlement_spacing` was" — would delete
more of them, on every seed. That is a live consequence and it is filed on
[PRODUCT-REACHABILITY-REPORT](PRODUCT-REACHABILITY-REPORT.md), which now reports it per
species rather than leaving it as an unexplained zero.

### The acceptance criterion cannot be met as written — the margin clause is the blocker

The criterion asks for medians monotone across at least three tiers *by a margin larger than
the spread within a tier*. The order is achievable; the margin is not.

**The margin is arithmetically out of reach, for any mechanism.** The within-tier spread is
6.9 km at size 33 (p10 3.1, p90 10.0) and 8 to 11 km at size 129. The largest between-tier
gap in any arm at any raster measured is 2.4 km, and the whole distance-to-settlement range
of the reference world is 1.8 km to 18 km. Three tiers each separated by more than the
within-tier spread would need more range than the world has. **This clause is unsatisfiable
independently of placement**, and it should be replaced by a stated margin — the test uses
700 m for monsters and 300 m for animals against ablated values of 236 m and −76 m.

**A five-tier order is impossible by construction, and the mechanism says so itself.** Tier
three is `danger_ramp`'s pivot: `danger_ramp(3, d, span)` is `(1 + NEST_DANGER_FLOOR) / 2`
at every distance, which `test_danger_ramps_with_distance_instead_of_stepping` has asserted
since the ramp landed. A tier the mechanism does not move cannot be ordered by it, and the
measurement confirms it exactly — tier three's `rate_distance_m` is **identical in every
ablation arm** (5051 m for monsters, 5771 m for animals) while every other tier moves. It
sits wherever habitat puts it, which on this world is below tier two.

**Across the four tiers the ramp does move, the rate is strictly ordered**: 4910 / 5285 /
5565 / 6184 m for monsters and 4847 / 5232 / 5391 m for animals, and both orders collapse
when the ramp is ablated (5371 / 5561 / 5335 / 5607 and 5279 / 5494 / 5203). So "monotonic
across at least three tiers" is **met**, in the rate, on the tiers the mechanism claims —
and cannot be met across five by this shape of factor at any tuning. That is the finding
the acceptance criterion should have been written against.

### What landed

`saturation` gains two columns per tier, in the shape the pyramid card established an hour
earlier — assert the claim where it is exact, publish the clipped view beside it:

- `rate_distance_m` — mean distance from settled ground of the groups the rate asks for,
  weighted by the rate. This is `danger_ramp` integrated over the world. Monsters:
  4910 / 5285 / 5051 / 5565 / 6184 m, **1.27 km end to end**, against 236 m with the ramp
  ablated. Tier three is byte-identical in every arm (5051 m), because `danger_ramp(3, ·)` is
  constant and a constant renormalises away — the mechanism's own docstring, confirmed.
- `placed_distance_m` — the same statistic on what was placed: 5730 / 5706 / 5281 / 5426 /
  5787 m, 0.51 km end to end. The rate carries 2.5× the gradient the sites do.

`Sim/tests/test_nest_diagnostics.py` asserts both halves:
`test_the_danger_gradient_is_carried_by_the_rate` (red when the ramp is ablated: 236 m and
−76 m against thresholds of 700 m and 300 m) and
`test_the_raster_clips_the_gradient_out_of_the_placed_set` (also red when ablated, because
without the ramp the placed spread exceeds the rate spread).

`wildlife` 2 → 3 and `beast_nests` 3 → 4, additive; conformance record
`docs/conformance/creature-placement.md` updated in the same change.

### Ablation matrix

Every arm regenerates the reference world with one piece disabled and runs all seven tests
in `test_nest_diagnostics.py`. Shared with
[PRODUCT-REACHABILITY-REPORT](PRODUCT-REACHABILITY-REPORT.md), whose tests are the last four.

| arm | red |
|---|---|
| baseline | 0 |
| `danger_ramp` → constant 1.0 | 2 — `…gradient_is_carried_by_the_rate`, `…raster_clips_the_gradient…` |
| `reach_reason` → always `placed` | 3 — `…accounted_for_with_a_reason`, `…dormant_school…`, `…refused_by_the_clearance…` |
| `never_satisfiable` → always false | 2 — `…dormant_school…`, `…absence…is_not_a_proof…` |
| the `cleared_out` branch removed | 1 — `…refused_by_the_clearance…` |
| `reachability` → zeros | 2 — `…three_integers…`, `…absence…is_not_a_proof…` |
| restored | 0 |

Every test goes red under at least one arm and every arm turns at least one test red, so
none of the seven is passing on something other than what it names.

### Decisions taken on the owner's behalf — reversible, flagged

**1. The world does not want danger rings. Ruled: keep the continuous rate factor, add no
second mechanism, and do not tune the clearance up.** This was the card's own open question.
The conservative reading is that a shipped mechanism that is exact in the rate should not be
joined by a second one aimed at the same effect, and the card's own analysis of the
alternative stands: a clearance is a cutoff, a cutoff makes nested dead zones, and at size 17
a tier-5 ring at the declared 3,000 m ceiling removes most of the map.

*Rejected:* signed per-tier exclusion rings. *Also rejected, and this one is a genuine loss:*
the alternative design in which danger tracks corruption, ley instability and ruins, with
those distributed relative to settlement. That is coherent, it is a larger change than this
card, and it is the one an owner might reverse this ruling for — it would put the gradient in
a field rather than in a rate, and a field is not clipped by saturation.

**2. The cross-block rule has no owner and I did not appoint one.** The card is right that a
gradient only nests respect is worse than none. I did not touch `Sim/key_locations/`, by
instruction and on the merits: a rule for three blocks to respect is premature while the nests
half cannot express the metric at shipped rasters, and `key_locations` fails for a different
reason anyway — `threat` is computed *after* placement, so there is no term there to sign.
**That half of this card is not closed by this change.**

**3. The age question is answered by existing behaviour, not by a new rule.**
`terrain_history` re-runs both passes around every age boundary, so the rate — and therefore
`rate_distance_m` — is always against the settlements standing when the pass last ran, not
against the ones that were there at founding.

### Not done

- `Fixtures/sample-world-v1.json` is stale: `saturation`, `diagnostics` and the block versions
  are new bytes. Not rebuilt here, by instruction.
- `board/README.md` still links this card at `backlog/`, and
  `provenance/extraction-manifest.json` has a `terrain_nests.py` revision citing the same
  stale path plus a hash row to add. Both are orchestrator-owned files and `docs_check` is
  red on exactly those three lines until they move.
- No native port. Decision 027 defers `Core/` wholesale.
- The size-129 arms are one seed on a loaded box and are a placement measurement, not a
  timing one. Nothing here crosses the size-192 territory boundary
  `BESTIARY-NOBODY-HAS-TESTED-ABOVE-THE-CROSSING` names.

---

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** Mean distance to the nearest settlement by tier: **13.2 / 14.8 / 13.0 / 12.6 / 13.1 km**. Tier 5 sits **−1.1%** from tier 1. Flat.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 2).

## Observed behavior

Seed 42, size 17, `generator_version` 16. Great-circle distance from each `beast_nests` site to
the nearest settlement, grouped by the nest's danger `tier`:

| tier | n | median | min | max |
|---|---|---|---|---|
| 1 | 63 | 13.5 km | 6.2 | 37.1 |
| 2 | 59 | 16.1 km | 6.2 | 37.1 |
| 3 | 24 | 13.2 km | 6.3 | 25.7 |
| 4 | 61 | 13.6 km | 4.8 | 37.1 |
| 5 | 94 | 13.8 km | 4.8 | 37.1 |

Five medians inside a 2.9 km band, and tier 5 reaches **closer** to a city (4.8 km) than tier 1
does (6.2 km).

`key_locations` behaves the same against its own `threat` axis: threat 1 a median 4.5 km from a
city, threat 2 5.2 km, threat 3 6.6 km, threat 4 4.8 km, threat 5 7.4 km, with ranges that
overlap almost entirely (threat 1 spans 2.2–6.9 km, threat 5 spans 5.7–10.7 km).

## Why it matters

### Confirmed at size 33, on 3.4× the nest population

The same measurement against `world-42-33.json` (same seed, same 200 km planet, 1,023 nests, 40
settlements, 3,665 km² of land), with hamlets and fortresses added to the safety anchors as well
as cities:

| tier | n | median | min | max |
|---|---|---|---|---|
| 1 | 229 | 6.9 km | 3.1 | 21.8 |
| 2 | 261 | 7.0 km | 3.1 | 19.3 |
| 3 | 86 | 6.3 km | 2.4 | 12.9 |
| 4 | 226 | 6.7 km | 3.1 | 15.4 |
| 5 | 221 | 6.5 km | 3.1 | 19.3 |

**Spread across all five tiers: 0.7 km**, and non-monotonic — tier 3 is the *closest* to safety.
Flatter at size 33 than at size 17, on 3.4× the population. Measured a second way, the share of
tier-4-and-5 nests runs 45.3% within 10 km, 43.7% within 25 km, 43.7% within 50 km and 43.7%
world-wide — flat to 1.6 points. The gamer-persona session got 45.2 / 44.8 / 43.7 / 43.7 using
settlements alone as anchors; two anchor sets and two statistics agree.

**The flatness is a design fact, not a raster artefact.** That was the open question on this card
and it is now closed.

### What resolution does change: the pyramid moves, the tier-3 hole does not

| tier | size 17 | size 33 |
|---|---|---|
| 1 | 63 (20.9%) | 229 (22.4%) |
| 2 | 59 (19.6%) | 261 (25.5%) |
| 3 | **24 (8.0%)** | **86 (8.4%)** |
| 4 | 61 (20.3%) | 226 (22.1%) |
| 5 | 94 (31.2%) | 221 (21.6%) |

The top-heavy inversion `BESTIARY-PYRAMID-RETUNE` diagnoses is largely a size-17 effect: tier 5
falls from the mode (31.2%) to 21.6% and tier 2 becomes the mode at size 33. **Tier 3 is a hole
at both rasters** — 8.0% and 8.4% against 20–25% for every neighbour — and a defect that survives
a 3.4× change in population is a catalogue property rather than a placement accident. That half
belongs on `BESTIARY-PYRAMID-RETUNE` and should be measured against the catalogue's own tier
distribution, which `docs`-side notes record as `[(1,250),(2,147),(3,136),(4,81),(5,49)]` over 663
profiles — a shape that does not predict an 8% trough at tier 3.

### Why it matters

A player leaving any settlement in this world meets tier 1 and tier 5 with equal probability.
There is no starting region, no frontier, and no direction in which the world gets harder. Every
generated-world game needs somewhere safe to begin and somewhere to graduate to, and that
structure has to be in the placement — a downstream game cannot reconstruct a gradient from data
that does not encode one.

It also makes the danger numbers unusable for pacing even though they are present and correct.
`threat` and `tier` are honest about how dangerous a thing is; they just say nothing about where
it is.

## The mechanism: one unscaled constant, and it could not produce a gradient even if it were scaled

Found by the gamer-persona session, which asked that the exhaustiveness claim be re-verified
before being written down. I read `terrain_nests._place` (`Sim/icarus_sim/terrain_nests.py`
138-222) line by line and confirm it.

**Monster placement has exactly one settlement-aware term.** `settled_directions()` collects
settlements, ports and hamlets; `_place` computes `nearest`, the distance from each cell to the
closest of them, once; and `nearest` is consumed in exactly one place:

```python
if clear_of < clearance(p): continue
```

Nothing else in the function reads it.

**There are two `clearance` definitions in the file and they belong to two different blocks.**
Cite both, because a reader who finds one after only the other will think the analysis missed
something:

```python
terrain_nests.py:272   add_monsters ->  beast_nests
    def clearance(p): return o['nest_settlement_clearance'] * p['tier']

terrain_nests.py:245   add_animals  ->  wildlife
    def clearance(p): return o['nest_settlement_clearance'] * p['tier'] / 3
        # "Game keeps its distance from people in proportion to how dangerous it is."
```

These are **not two paths a nest might take** — `add_monsters` filters the catalogue to
`class == 'monster'` and `add_animals` to `class == 'animal'`, so a `beast_nests` site always
takes `:272` and never the `/3`. The monster figures in this card are unaffected by `:245`. `biome_weight` reads the biome, `suitability` reads
habitat and magic fields, `room` and the tier `budget` carry no settlement term, the `nest_limit`
valve sorts by tier and id, and `dominance` compares a candidate against **already-placed nests**
rather than against settlements — its own docstring says so: *"an animal only competes with its
own species, a monster with anything of equal or greater tier."*

**The constant is ~18× too small and never scaled with the world.**
`terrain_world.py:38` declares `nest_settlement_clearance` at **250 m** (max 3,000 m), the value
tuned for the ~11 km reference world. `terrain_world.py:251-253` grows exactly three quantities
by `reach_scale(circumference)`:

```python
for key,ceiling in (('settlement_spacing',100000.),('support_reach',100000.),
                    ('culture_link_cost',100000.)):
```

`nest_settlement_clearance` is not in that tuple — and because it is a `world_options` entry
rather than a `Config` field, it is not in the dict that loop walks at all. So a **tier-5 apex
monster must keep 1,250 m from a town**, against a raster cell of **6,638 m at size 17** and
**3,419 m at size 33** — the strongest repulsion in the system is **19% of one cell at size 17
and 37% at size 33**. It cannot displace a nest by a single cell at any resolution anyone runs,
which is why the medians above are flat.

**The same blindness covers `wildlife`, on a much larger sample, and it erases a design intent.**
Measured at size 33 against the code's own anchor set (`settled_directions()`: settlements, ports
and hamlets), with the clearance each tier must satisfy, as a share of the 3.42 km cell:

| | tier | n | median distance | required clearance | % of a cell |
|---|---|---|---|---|---|
| monsters | 5 | 221 | 6.45 km | 1.250 km | 36.6% |
| monsters | 1 | 229 | 6.88 km | 0.250 km | 7.3% |
| animals | 4 | 551 | 6.45 km | 0.333 km | 9.7% |
| animals | 1 | 8,729 | 6.45 km | 0.083 km | 2.4% |

Spread across tiers: **0.73 km for 1,023 monsters, 0.37 km for 14,035 animals.** Every site
satisfies its own clearance — zero violations in either block — so nothing is malfunctioning; the
radius is simply too small to move anything.

The clearest statement of the defect is in the last two rows: **the generator deliberately makes
a monster keep three times the distance an animal does, and a tier-5 apex monster and a tier-1
prey animal both sit at a median 6.45 km from the nearest settlement.** A 3:1 design ratio,
stated in a comment, producing a 0 km difference in the emitted world.

**And the stronger repulsion governs the half of the world nobody sees.** Framing from the
gamer-persona session; the three counts are measured here. The `/3` formula governs `wildlife` —
**4,065 sites at size 17, every one `real: true`**, and the source of **786 of the 792
`beast_movements` groups** that in turn supply 792 of the 805 `encounters` entries a consumer
would query. The undivided formula governs `beast_nests` — **301 sites, every one `real: false`**,
which the block's own `limits` calls *"a claim on ground, not a simulated creature"*. So the
tuning effort went to the layer that is never instantiated, and the layer that actually reaches a
player is the one told to keep a third of the distance. See `CONTENT-ENCOUNTERS-ARE-FISH` for what
that does to the proximity index.

**This closes the seed question.** This card previously said flatness on one seed is not the same
as a rule that cannot produce a gradient. It is now the second one: on the rasters measured, the
only term that could push danger away from people is smaller than the grid it operates on, for
every tier, in both blocks. **No seed can produce a gradient at size 17 or 33.**

### Correction: "inert at every raster" was wrong, and the bound matters now

An earlier revision of this card said the clearance is sub-cell *at every resolution*. That is
false above size 65, and it matters because the grid ceiling moved to 1025 — the sizes where it
is false are the sizes people will now run. Cell edge is `2r√π / n`; the formula reproduces the
measured cell of both documents to 0.0 m (6,637.5 m at size 17, 3,419.3 m at size 33), so the
extrapolation is anchored rather than assumed:

| size | cell edge | tier-5 clearance ÷ cell | tier-1 clearance ÷ cell |
|---|---|---|---|
| 17 | 6,637 m | 0.19 | 0.04 |
| 33 | 3,419 m | 0.37 | 0.07 |
| 65 | 1,736 m | 0.72 | 0.14 |
| **129** | 875 m | **1.43** | 0.29 |
| 257 | 439 m | 2.85 | 0.57 |
| **513** | 220 m | 5.68 | **1.14** |
| 1025 | 110 m | 11.35 | 2.27 |

**Tier-5 clearance crosses one cell at size 129; tier-1 not until 513.** So there are three
regimes, and only the first is measured:

1. **Below 129 — inert for every tier.** Both worlds in this card. Nothing is displaced.
2. **129 to 257 — bites at the top, not at the bottom.** Tier 5 is pushed out 1.4–2.9 cells while
   tier 1 stays sub-cell. This is the closest the mechanism ever comes to a gradient, and it is
   still a *step per tier*, not a ramp.
3. **513 and above — bites at every tier**, tier 5 by 5.7 cells.

**The donut argument is what survives all three regimes and is the load-bearing one.** A clearance
is a binary cutoff: beyond its radius every tier is equally likely at every distance. Regime 3
gives nested dead zones of 15 km and 3 km at the declared ceiling, not a difficulty curve. So the
defensible claim is narrower than the card first made it and still reaches the same fix:
**a monotone difficulty gradient is not producible by this mechanism at any resolution**, because
it is the wrong shape of term — inert below 129, and a step function above it.

Credit for catching the overclaim: the gamer-persona session. I filed the unhedged version and it
was wrong.

**And scaling the constant alone will not fix it.** A clearance test is a binary cutoff, so it
produces a *hole* around settlements, not a ramp — every tier outside its own radius is equally
likely at every distance beyond it. Pinning the knob to its declared 3,000 m ceiling gives tier 5
a 15 km exclusion and tier 1 a 3 km one, which is a set of concentric dead zones rather than a
difficulty curve, and on the size-17 raster a 15 km hole removes most of the map. **The fix is
the distance factor in `suitability` described below, not a larger cutoff** — the cutoff should
be scaled anyway, for the same reason `settlement_spacing` was, but it is a separate and smaller
change.

## Relationship to `BESTIARY-PYRAMID-RETUNE`

Different defect, same block, and the two are visible together here: 94 tier-5 nests against 63
tier-1, consistent with that card's diagnosis that a monster is excluded by an equal-or-greater
tier within range, so a tier-1 lair is refused by everything and a tier-5 only by other tier-5s.

**Fixing the pyramid does not produce a gradient.** Correcting the counts gives more low-tier
nests, distributed just as uniformly. These are two changes and the second is the one a player
feels.

## Proposed mechanism

Make placement suitability a function of distance from settled ground, with the sign set by tier.
The machinery already exists — every nest carries a `suitability` and `suitability_factors`, and
`key_locations` carries factors like `ruin_distance_low` — so this is a new factor in an
established shape rather than new plumbing:

- a low-tier factor that rewards proximity to a settlement,
- a high-tier factor that penalises it,
- both bounded so the world does not become a set of rings, and neither overriding the habitat
  requirements that make a species make sense where it is.

The same factor belongs in `key_locations` placement against `threat`.

## Dependencies and unresolved decisions

- **Who owns the rule.** Nests, key locations and wildlife each place independently; a gradient
  that only one of them respects is worse than none, because the safe ring around a town would
  still hold tier-5 key locations.
- **Whether the world wants rings at all.** An alternative is that danger tracks the magical and
  historical features it already tracks — corruption, ley instability, ruins — and that those are
  what should be distributed relative to settlement. That is a design decision, not a tuning one,
  and it should be made before anything is tuned.
- Settlements move between ages. The distance a nest was placed against may not be the distance
  that holds after an age advance; the rule needs to state which it means.

## Acceptance and evidence

- On a reference world, median distance-to-nearest-settlement is monotonic in tier across at
  least three tiers, by a margin larger than the spread within a tier.
- A behavioral test asserts the monotonicity so it cannot silently flatten again.
- The conformance record for nest placement states the gradient as current description, and
  states the seed and world size its figures come from.

## Adversarial review and limitations

**The evidence is a mechanism plus two independent statistics, and the seed question is closed by
the mechanism rather than by measurement** — but only within the measured regime. One constant is
the whole of monster placement's settlement-awareness, and below size 129 it is smaller than one
raster cell for every tier, so no seed can produce a gradient at the sizes measured. The seed-73
run is no longer load-bearing for this card. It is still worth running for the variety question
it settles elsewhere.

**The falsifiable test, worth writing down before it runs.** At 513 tier-5 clearance is 5.7
cells, so the prediction (the gamer-persona session's, and I agree with it) is that the tier-4+5
share in the innermost distance band falls below the world-wide share for the first time, while
the mid and outer bands stay flat within noise. **If the inner band does not move at 513,
something other than clearance is pinning the distribution and this card's mechanism is
incomplete.** Either result is worth having, and it is the one place the analysis can still be
wrong. The statistic is already written and runs unchanged against any document.

## The `key_locations` half, now read the same way — a different mechanism, same flat result

Filled in by the content-placement lane, which was in that package anyway. The card was right to
refuse to assume one fix covers both: the two blocks fail for **different reasons**, and only one
of them is the unscaled constant.

**`key_locations` placement never sees danger at all.** `threat` is computed in
`Sim/key_locations/core/succession.py` *after* a site is placed, from its state, its occupant, the
nearest nest and the nearest villain holding. Nothing in `placement.py` or `fields.py` reads it.
So the threat-vs-distance flatness above is not a weak repulsion failing to bite — **there is no
term to bite.** A site's danger is decided by what happened to be near the ground it was already
standing on, which is close to the definition of no gradient.

**The per-archetype clearance that does exist is monotone in `tier`, and `tier` here is not
danger.** Measured over the 90 scattered archetypes, `settlement_clearance_cells` × the fixed
3,125 m reference cell:

| archetype tier | n | median clearance | ÷ cell at 17 | ÷ 33 | ÷ 65 | ÷ 129 |
|---|---|---|---|---|---|---|
| 0 | 10 | 625 m | 0.09 | 0.18 | 0.36 | 0.71 |
| 1 | 51 | 1,250 m | 0.19 | 0.37 | 0.72 | 1.43 |
| 2 | 24 | 1,875 m | 0.28 | 0.55 | 1.08 | 2.14 |
| 3 | 5 | 4,688 m | 0.71 | 1.37 | 2.70 | 5.36 |

Cell edge is the same `2r√π / n` this card uses for nests, so the two tables are comparable.

Two things follow, and they cut in opposite directions.

**This clearance *does* scale with the world**, which is the one place the two blocks genuinely
differ in kind. `spacing_cells` and `settlement_clearance_cells` resolve against a **fixed
reference raster of 65**, never the raster in hand, so they are absolute metres tied to the
world's circumference. The nest constant is 250 m regardless of anything. So the key-location
clearance crosses one cell at size 33 for tier 3 and by 129 for every tier, where the nest one
does not reach tier 1 until 513. The unscaled-constant diagnosis is **specific to
`terrain_nests`** and must not be carried over.

**And it still cannot produce a difficulty gradient**, for the reason this card already
establishes and for one more. It is a binary cutoff, so it makes nested donuts rather than a ramp
— unchanged. And it is keyed on `tier`, which in this package is **scale, not danger**:
`docs/key-locations.md` says so outright, that a tier-3 wonder can be harmless and a tier-1 barrow
lethal. A ladder built on scale answers "how big is it", and pushing big things away from towns is
a sensible siting rule that says nothing about how dangerous they are.

So the fix shape this card proposes — a distance factor in suitability, signed by danger — is the
right one here too, but it has to be keyed on something placement can know *before* it places,
and `threat` today is not. That is a real dependency and it is not a tuning question.

What is *not* established:
- **Whether a gradient is what this world wants.** Unchanged from the first draft and still the
  decision that should precede any tuning. The alternative — danger tracking corruption, ley
  instability and ruins, with *those* distributed relative to settlement — is a coherent design
  and would need a different change.
- **The terrain caveat, which cuts the other way here.** Both measured worlds have
  `resolved_octaves` 0 of 5 and 1 of 5, and `beast_nests` gates on absolute field values
  (`terrain_nests.py:84`), so a smooth world suppresses terrain-keyed species generally. That
  affects *which* species place — see the review's octave section and
  `BESTIARY-BRIMSTONE-BATS` — but it does not affect this card, because clearance is a distance
  test that never reads the heightfield.

`world-42-33.json` is provisional pending the performance session's byte-stability confirmation
of a `city_planner.py` / `hamlet_planner.py` change. A content-count change there would move the
anchor set slightly; it would have to move it enormously to turn a 0.7 km spread into a gradient,
and it would not touch the constant.
