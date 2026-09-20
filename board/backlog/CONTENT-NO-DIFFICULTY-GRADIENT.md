# CONTENT-NO-DIFFICULTY-GRADIENT — danger has no spatial relationship to safety

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
