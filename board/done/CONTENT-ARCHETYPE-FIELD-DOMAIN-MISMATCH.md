# CONTENT-ARCHETYPE-FIELD-DOMAIN-MISMATCH — five archetypes gate on a field that carries no data where they are allowed to stand

Owner: content-placement lane. State: **CLOSED 2026-09-21.** Class A fixed and re-measured; class
B resolved elsewhere by the island-habitat world-scale fix; class C's structural fix kept although
the river-threshold fix removed the instance that motivated it; and the two items the card stayed
open on — the saturated-percentile gate and an audit against a generated world — are both
delivered. **The card's open design question was decided under the sweep's pick-implement-flag
ruling and the decision is recorded in full in *The open question, decided* below, with both
rejected alternatives and the measured cost of the one taken. It is reversible in one line.**
Found by
the Python-output red team; the coordinator asked for it as a card of its own because it is the
one key-location finding that needs no generated world and waits on nothing
(`docs/reviews/233182e-python-output-red-team.md`, finding 8, cause 1).

## Status after the content-placement pass, and after the follow-up that re-measured it

**Read this section, not the wave-1 one it replaces.** An adversarial audit of the first pass
found that several of its published numbers did not reproduce, and it was mostly right: every
size-17 row of its before/after table was wrong and its bolded claim that nothing stopped
placing was false. All of it has been re-measured from scratch, in one process, against frozen
world documents at sizes 17, 33 and 65, and what follows is the reading rather than the memory
of one. **Two of the audit's own numbers do not reproduce either** and are corrected in place
below: `gem_mine` does not go 1→0 at size 17 (it places one under every revision), and
`geyser_basin` does not go 3→2 at size 65 (it is 20 candidates and 3 placed under every
revision, which is what the wave-1 card claimed). An audit of an audit earns the same treatment
as the thing it audits.

**Why the first pass's numbers did not reproduce, stated so it is not read as carelessness.**
Two causes, and only the second is a mistake.

- **The world moved underneath it.** The river-threshold scaling fix landed in the same window.
  Before it, `river_threshold_km2` was left at its 11 km value on a 200 km world, so every land
  cell drained enough to be a river, `freshwater_distance` was 0 across all land and `river` was a
  flat 1.0. Those are exactly the two layers this card's classes B and C turn on. The size-33 rows
  of the old table largely still reproduce — `holy_well` 129 candidates and 5 placed, unchanged;
  `quarantine_isle` 42 candidates; `geyser_basin` 8 candidates; totals 250→254 against a measured
  251→256 — while **every size-17 row moved**, because that is the raster where the river fix bites.
- **The land-cell claim was a measurement error.** "30 of 47 land cells already carry a ruin, nest
  or religion site" was `len(readers.claimed_nodes(world))`, not its intersection with the land
  domain. The correct figure is **16 of 47**. The same world claims 94 nodes in all, and 78 of
  them are water, pole or seam nodes — mostly sea nests — which no `domain: land` archetype can
  ever consider. One number was wrong in both directions at once, and it had been copied into
  `docs/key-locations.md` and into an inline comment in `Sim/key_locations/__init__.py`. Both are
  corrected, and both now say to count the intersection.

### How this was measured, so the next person can repeat it rather than re-derive it

Three copies of `Sim/key_locations` — `HEAD`, the wave-1 worktree, and the worktree after this
follow-up — imported in turn **in one process** and run against **identical frozen world
documents**. That is the only way to separate this lane's effect from the five others editing the
same repository at the same time, and it is what makes the three-way table below a comparison
rather than three readings.

The worlds are seed 42, `recipe_version` 3, phase 16, at sizes 17, 33 and 65, generated through
`generate_request` and frozen to disk with everything `key_locations` cannot read stripped out —
which is a 59 MB document reduced to 1 MB, asserted byte-identical in the block it produces rather
than assumed. **`generate_request`, not `default_config`.** The lab's bare default leaves
`globe_radius` at 10000, which resolves to the legacy **11.15 km** planet with 6.4 km² of land and
**39** land cells at size 17; the 200 km `world_size: small` preset this card is written against
has 2,487 km² and **47**. That is the whole of the open reconciliation `board/README.md` records
between this card's 47 land cells and the coordinator's 39: `Artifacts/city-planner/world.json` is
the 11 km world at `generator_version` **9** — measured, `globe_radius` 1774.41 — and on it
`island_habitat` is nonzero in 2 of 39 land cells and `freshwater_distance` in 4 of 39, which is
this card's own "gen 9" row. Neither reading was wrong. They are two different planets.

### Before and after, the same world documents, three package revisions

| | size 17: HEAD → wave 1 → now | size 33 | size 65 |
|---|---|---|---|
| sites emitted | 106 → **112** → **111** | 251 → **256** → **255** | 494 → **497** → **491** |
| scattered sites (no chains, no clusters) | 21 → **22** → 22 | 99 → **100** → 100 | 286 → **287** → 287 |
| archetypes placing at least one | 24 → **25** → **26** | 53 → **57** → **55** | 82 → **88** → 88 |
| wonders placed (of 5) | 0 → **2** → 2 | 0 → **2** → 2 | 0 → **2** → 2 |
| archetypes with zero candidates | 9 → **6** → 6 | 6 → **3** → 3 | 6 → **2** → 2 |
| `salt_mine` candidates / placed | 0 / 0 → **6 / 1** → **9 / 1** | 0 / 0 → **47 / 1** → **46 / 1** | 0 / 0 → **216 / 1** → **199 / 1** |
| `salt_pans` candidates / placed | 0 / 0 → **7 / 0** → **5 / 0** | 0 / 0 → **26 / 0** → **16 / 0** | 0 / 0 → **122 / 3** → **71 / 3** |
| `whaling_station` candidates / placed | 0 / 0 → **24 / 0** → 24 / 0 | 0 / 0 → **119 / 0** → 119 / 0 | 0 / 0 → **588 / 2** → 588 / 2 |
| `holy_well` candidates / placed | 32 / 0 → 32 / 0 → 32 / 0 | 129 / 5 → 129 / 5 → 129 / 5 | 412 / 6 → 412 / 6 → 412 / 6 |
| `geyser_basin` candidates / placed | 0 / 0 → 0 / 0 → 0 / 0 | 8 / 0 → 8 / 0 → 8 / 0 | 20 / 3 → 20 / 3 → 20 / 3 |
| `summoning_circle` candidates / placed | 22 / 0 → 22 / 0 → 22 / 0 | 121 / 0 → 121 / 0 → 121 / 0 | 529 / 8 → **529 / 3** → **529 / 1** |
| land cells | 47 | 268 | 1,174 |
| land cells already claimed | 16 | 136 | 795 |

The wave-1 card's **size-65** class-A row reproduces exactly — `salt_mine` 216 candidates and one
site, `salt_pans` 122 and three, `whaling_station` 588 and two, `holy_well` 412 and six,
`geyser_basin` 20 and three. It is the size-17 column that was wrong and the size-33 one that was
close, which is consistent with the river fix being the cause: it moves the coarse raster most.

**Class A is fixed, and at a raster with room all three place.** At size 65 the world grows a
salt mine, three salt pans and two whaling stations where before it grew none at any size — the
acceptance this card was filed for. At 17 and 33 only `salt_mine` places; the other two have
ground and lose it to node exhaustion, and the diagnostic says so in its own words — *"no room:
16 of 24 qualifying cells already carry another feature, and spacing or settlement clearance
refused the remaining 8"*. The wave-1 card said all three had ground but placed nothing, which
was wrong about `salt_mine` at every raster and wrong about all three at 65.

**Class C's structural fix is right and its measured instance has gone.** `holy_well` is no longer
eligible on every land cell, because `freshwater_distance` now varies: 15 of 47 land cells are
nonzero at size 17 and 139 of 268 at size 33. The fail-closed rule takes **nothing** away at
either raster now — 32 candidates before and after at 17, 129 before and after at 33 — so the rule
is a guard against a shape that the river fix happened to remove rather than a change that cost
content. It should stay, and at size 65 it likewise takes nothing: `holy_well` is 412 candidates
and 6 placed under all three revisions. `river` now varies on land (24 of 47 nonzero at size 17),
so the four wayside archetypes the rule caught are gated on a real river again at that raster.
**At 33 and 65 they are not: `ford` and `ferry_crossing` are eligible on all 268 and all 1,174
land cells respectively**, and at 65 they go on to place 10 and 3 sites each — so the voided
gate is no longer merely reporting a wrong candidate count, it is putting fords on ground with
no river. That is the *saturated* percentile described further down and nothing here fixes it.

### Correction: "nothing that placed before stopped placing" is FALSE

The wave-1 card bolded that claim. It does not survive measurement, and worse, **it is not a claim
this system can support at all.** Measured, HEAD → wave 1 on identical worlds:

| raster | stopped or shrank |
|---|---|
| 17 | `bandit_camp` 1→0, `caravanserai` 1→0, `wizard_tower` 1→0, `siege_camp` 2→0 |
| 33 | `hedge_inn` 6→5, `logging_camp` 4→2, `pass_hospice` 3→1, `siege_camp` 8→6 |
| 65 | **`summoning_circle` 8→3**, **`wayside_shrine` 5→1**, `siege_camp` 12→10, `pilgrim_station` 5→4 |

All four disappear from the size-17 world entirely, and none of them had its gate touched. The size-65 row is the largest movement in the whole change and the audit was right to single it out — though it named `summoning_circle` 7→2 and `geyser_basin` 3→2, and the measurement gives 8→3 for the first and **no movement at all** for the second.

**The mechanism, traced to a line rather than guessed at.** A cluster's existence is keyed on its
anchor's *node id*. `build_clusters` seeds a generator on the cluster spec and the anchor's id and
compares one draw against the spec's `chance`
(`Sim/key_locations/core/composition.py:207-208`).
A site's id is `keyloc-<kind>-<node>`, so the node *is* the seed. At size 17 the two `border_fort`
sites sit on
nodes 131 and 209 under `HEAD` and on nodes 85 and 209 after wave 1. The siege coin for node 131
is 0.385 and clears the 0.55 chance; for node 85 it is 0.570 and does not. **One fort moved one
cell and a whole cluster of two siege camps stopped existing.** Nothing about siege camps changed.

So the honest general statement, which should replace the bolded claim wherever it is repeated:
**at a raster where the node budget binds, any change that displaces one site re-rolls every draw
keyed on that site's node, and content appears and disappears with no relation to the gate that
was edited.** `select` also skips claimed nodes *before* consuming a jitter draw
(`Sim/key_locations/core/placement.py:307-310`), so adding one claimed node anywhere re-pairs the jitter sequence
with the candidate list for every archetype placed afterwards. Both are deterministic and neither
is a bug; they make "nothing stopped placing" an unprovable claim rather than a false one.

**Re-confirmed 2026-09-21 against the current tree, and there is a third arm the section above
misses.** The two named still hold at their lines: the cluster coin is
`rng_for(f"keyloc-cluster-{spec['id']}-{anchor['id']}")` compared against `chance` at
`composition.py:207-208`, and a site's id is `f'keyloc-{archetype["id"]}-{cell["node"]}'` at
`__init__.py:376`, so the anchor's node is literally a substring of the cluster's seed. In
`select` the `continue` on a claimed node is at `placement.py:307` and the `draw.random()` it
skips is at `:310` — the skip is genuinely before the draw. The third arm: **every site's own
draw is `rng(seed, f'keyloc-site-{archetype["id"]}-{cell["node"]}')`** (`__init__.py:373`), so a
site that moves one cell does not merely still exist — it gets a different state, occupant,
succession, threat, name and interior graph. What does *not* move is `budget`, which draws from
`rng(seed, 'keyloc-place-' + archetype['id'])` (`__init__.py:257`), a per-archetype generator
nothing else can reach, so `wanted` is stable across all of this.

**The consequence for anyone measuring two content changes at once: you cannot.** Two lanes that
each displace a site produce a combined delta that is not the sum of their separate deltas, and
neither lane's delta is attributable. The only way to attribute one is the method this card's
follow-up used: freeze one world document, and run each package revision against that same frozen
document in one process.

### What this follow-up changed, and what it cost

| | size 17 | size 33 | size 65 |
|---|---|---|---|
| sites emitted | 112 → 111 | 256 → 255 | 497 → 491 |
| gained | `cliff_coffins` 0→1 | `hedge_inn` 5→6, `hillfort` 1→2, `pass_hospice` 1→2 | `wayside_shrine` 1→2, `wild_magic_scar` 1→2 |
| lost | `barrow` (scattered) 1→0, `miners_cottages` 5→4 | `smelter_ruin` 1→0, `standing_stones` 1→0, `reliquary_chapel` 3→2, `siege_camp` 6→5 | `siege_camp` 10→6, `miners_cottages` 7→5, `summoning_circle` 3→1 |

Reported rather than buried, because it is the same effect as the section above: `salt_mine` moved
to a different node, `salt_pans` lost candidates, and everything downstream of the node budget
re-rolled. **Net one site fewer at 17 and 33 and six fewer at 65**, two archetypes lose their only
size-33 site, and no class-A placement is lost at any raster — `salt_mine` still places one at
all three and `salt_pans` still places three at 65 on 71 candidates instead of 122. The changes
below are still right — an unjustified floor and an unjustified threshold are defects whatever
they happen to be worth in one world's node budget — but the cost is a cost, and at size 65 it
is four siege camps and two miners' cottages that exist in one arrangement of the world and not
the other.

**Count the sites, not the diagnostics.** These deltas are from the `sites` array grouped by
`(kind, placement)`. A per-archetype reading of `diagnostics` misses some of them: `barrow`
declares `also_scatters`, so it gets **two** diagnostic rows — one from the scatter pass and one
from `barrow_ring` — and a reader keyed on the archetype id keeps whichever comes last. At size 17
that hid `barrow`'s scattered site disappearing, and made the totals fail to add up: 112 sites
against 111 summed placements. The `sites` array is the ground truth; `diagnostics` is one row per
*pass*, not one per archetype.

### `summoning_circle` at size 65: its gate is innocent, and its count is not a measurement of anything

The audit reported `summoning_circle` falling from 7 placed to 2 at size 65, called it the largest
content movement in the change, and said nobody had decided whether it was a defect the fix
exposed or one the fix introduced. Re-measured on the current tree it is **8 → 3** under wave 1
and **8 → 1** after this follow-up, so the audit was right about the size and right that nobody
had explained it. **It is neither kind of defect. It is the node budget, and the count is not a
property of the archetype.** Six runs of the *current* engine against one frozen size-65 world,
varying only the catalogue handed to it:

| catalogue | sites | `summoning_circle` placed, of 8 wanted, from 529 candidates |
|---|---|---|
| the full catalogue as it stands | 491 | **1** |
| minus the five wonders | 492 | **3** |
| minus the three class-A archetypes | 483 | **4** |
| minus both | 494 | **8** |
| `HEAD`'s catalogue | 494 | **8** |
| a document holding *only* `summoning_circle` | 8 | **8** |

Four things this settles, and the apportionment is the interesting one.

**The gate did not move.** `summoning_circle` requires `magic_density above_percentile 0.55` and
neither wave touched `magic_density` or that term. Its candidate count is **529 in every row of
that table**, and so is `wanted` at 8, because `budget` draws from
`rng(seed, 'keyloc-place-summoning_circle')`, a generator seeded per archetype that nothing else
can reach. Whatever moved, it was not the archetype's relationship to the ground.

**Remove the eight new sites and it recovers completely.** "Minus both" is `HEAD` in placement
terms while still running the current engine, and it puts all 8 back. The loss is caused by the
eight sites wave 1 added — one salt mine, three salt pans, two whaling stations, two wonders — and
by nothing else.

**Neither cause alone accounts for it, which is the signature of a reshuffle rather than a
crowd-out.** Removing the five wonders alone recovers 2 of the 7; removing the three class-A
archetypes alone recovers 3; removing both recovers all 7. Eight extra claimed nodes out of 1,174
land cells cannot *crowd out* five sites. What they do is re-order: `select` skips a claimed node
**before** consuming its jitter draw
(`Sim/key_locations/core/placement.py:307-310`), so one extra claimed node
anywhere in the list re-pairs the entire jitter sequence with the remaining candidates, and a
greedy pass under a binding spacing rule packs a re-ordered list differently. `summoning_circle`
is tier 0, `sorted(scattered, key=lambda a: (-a['tier'], a['id']))` places tier 0 last, and its
own spacing is 0.8 reference cells against an arcane family spacing of 1.2 — so it is the
archetype most exposed to exactly that.

**An archetype in that position has a count that is a residue, not a measurement.** Alone in a
document it takes every site it wants at all three rasters — 5 of 5 at size 17, 7 of 7 at 33, 8 of
8 at 65 — and in the real catalogue it takes 0, 0 and 1. Reading a swing in that number as
evidence about summoning circles is reading the residue as the signal. **The honest fix is not to
this archetype**: it is either to stop tier 0 being last in line for ground, or to stop reporting
a residue as though it were a placement decision. Both are larger than this card.

### Three absolute floors arrived with no justification. Two are justified; one is gone.

An absolute floor is the one part of a gate that does not travel between worlds, so it has to be
**the value below which the field means none of the thing**, with the reason written down beside
it. A floor taken from inside the field's own distribution is tuning, and untraceable tuning is
the defect class this repository keeps rediscovering. The catalogue now carries a `floor_rule`
note stating that, and the three floors were put to it one at a time.

**`salt_pans`: `coastal_exposure >= 0.125`. Justified — it is 1/8, and 1/8 is the field's smallest
possible positive value.** `coastal_exposure` is a cell's water-neighbour count divided by its
neighbour count (`Sim/icarus_sim/terrain_ecology.py:93-95`).
The sphere grid gives every cell six or
eight neighbours at sizes 17, 33, 65, 129 and 257 — only the two poles differ, with 2(n−1)
neighbours each, and `readers.cells` excludes the poles — so no cell can hold a positive value
below 1/8. Measured: the smallest positive value on land is exactly 0.125 at sizes 17 and 33. The
floor therefore says *touches water at all* and admits nothing less. It is not a level.

**`whaling_station`: `coastal_fishing_productivity >= 0.12`. Justified — it is the constant term
in the source field's own definition.** `fishing_productivity` is `clamp(0.12 + 0.55·shallow +
0.3·estuary + 0.2·kelp + 0.15·reef)` wherever water exists and `0.0` on land
(`Sim/icarus_sim/terrain_ecology.py:104`), so 0.12 is the least value it can take
where it exists. Measured: the minimum on water is exactly 0.1200 at sizes 17 and 33. The derived shore field takes the best
water neighbour, so it is ≥ 0.12 on any land cell touching water and exactly 0 inland — the same
statement as the one above, in the other field's units.

**Both floors are one raster step from being the entire gate, and that is measured rather than
predicted.** The share of land reading zero climbs with the raster and the nearest-rank cut
falls to meet the floor:

| size | land cells | `coastal_exposure` zero on land | p55 cut | p60 cut on the shore field |
|---|---|---|---|---|
| 17 | 47 | 1 (2.1%) | 0.500 | 0.42 |
| 33 | 268 | 77 (28.7%) | 0.375 | 0.42 |
| 65 | 1,174 | 586 (**49.9%**) | **0.125** | **0.12** |

At size 65 the p55 cut **is** 0.125 — the smallest positive value `coastal_exposure` can hold —
and the p60 cut on `coastal_fishing_productivity` **is** 0.12. The percentile has already fallen
the whole way to the floor. One raster further and it goes to zero: `percentile` is nearest-rank,
so the cut is the value at index `round(0.55·(n−1))` and reaches zero once more than about **55
per cent** of the domain reads zero — checked directly against `placement.percentile` at n = 100,
268, 1174 and 4870, positive at 54 per cent zero and zero at 56. Size 65 is at 49.9. **Past size
65 these two floors are the only thing standing between a shore archetype and every inland cell
in the world**, which is the fail-open shape this card exists to describe, and it is why they are
not decoration.

**`salt_mine`: `metal_richness >= 0.3`. Removed, with the term it sat on.** This one was a level.
`metal_richness` runs 0.148–0.682 on land at size 17 and 0.120–0.765 at size 33, so 0.3 is an
interior cut with no meaning attached, and nothing anywhere said why it was 0.3. The deeper
problem is the one the audit named: the field is an ore proxy —
`clamp((0.45 + 0.7·perlin3 + 0.2·volcanic) · metal_abundance)` at
`Sim/icarus_sim/terrain_ecology.py:108`.
The archetype's own `reason` says *"a sea dried here long ago and left rock salt under dry
ground"*. **Evaporite is not ore, and a gate that does not mean what the reason says places the
right noun for the wrong cause** — invisibly, because the output records the reason string and not
the gate that produced it.

`salt_mine` now asks for an arid basin, which is what the reason describes: `rainfall
below_percentile 0.35` and `tpi below_percentile 0.35`, low ground relative to its surroundings.
Both fields vary on land at both rasters, so the fail-closed rule does not bite, and neither term
carries a floor because a basin is a relative notion and has no absolute "none of the thing" value
to name. Candidates: **9 at size 17** (against 6 for the ore gate) and **46 at size 33** (against
47), and it places one site at both, so the semantic fix is free at 17 and costs one candidate at
33.

**`whaling_station`'s other floor, `coastal_exposure >= 0.03`, predates this work and was left
alone.** It cannot bind — the field has no positive value below 0.125 — so it is inert rather than
wrong, and changing it would move content for no reason. Noted here so the next reader does not
have to re-derive that.

### `salt_pans`' slope term was loosened in the same edit for no stated reason. Reverted.

The class-A fix also changed `slope below_percentile` from 0.3 to 0.4, which has nothing to do
with a gate naming an ocean field. Nothing anywhere justified it, so it is back at 0.3. What that
costs, measured: candidates 7 → 5 at size 17 and 26 → 16 at size 33. `salt_pans` placed zero sites
at both rasters before and after the revert, so **the revert costs no salt pans on either world**;
what it costs is the reshuffle described above, which is where the one net site at each raster
went.

The general point is worth keeping: a threshold moved inside an edit that was about something else
is invisible in review, because the diff reads as part of the fix. All three floors above and this
slope term arrived exactly that way, in a change whose stated subject was a gate naming an ocean
field.

**The structural rule, stated so it cannot be rediscovered a third time.** *An absolute floor on an
empty field fails closed; a percentile on an empty field fails open.* The closed failure costs a
kind of place and says so in `diagnostics`. The open one voids the archetype's defining requirement
and reports `placed`. Four of the five archetypes here carried a floor; `holy_well` did not, and it
is the only one that was producing wrong output rather than no output.

### What the fail-closed rule turned up that nobody had filed

The rule was written for `holy_well` and immediately caught four more, which is the argument for
writing the rule rather than fixing the instance. **`river` reads a flat 1.0 on every land cell of
the size-17 reference world.** So `ford` and `ferry_crossing` were eligible on all 47 land cells —
their entire domain — and `bridge` and `toll_station` were gated only by their second term. Four
wayside archetypes whose defining requirement is *a river* were being placed without reference to
one. They now report the gap instead. The same concurrent river change should restore them; if it
does not, that is a finding of its own and larger than this card.

**Followed up and half true.** The river fix landed and `river` does vary now — 24 of 47 nonzero
at size 17 — so the fail-closed rule no longer fires on any of the four and all four are gated on
a real river again at size 17: `ford` and `ferry_crossing` are down from all 47 land cells to 24,
and `bridge` and `toll_station` to 13. At size 33 it did **not** work: the layer went from
saturated to sparse, 22 of 268 nonzero, and an `above_percentile` cut over a field that is zero on
92 per cent of the domain lands at zero, so `ford` and `ferry_crossing` are eligible on all 268
land cells exactly as before. The gate is voided by the opposite extreme and looks identical from
the outside. That is the saturated-percentile item further down, and it is what this card now
stays open for.

**This is resolution-independent.** Every other cause of a missing key location — tail
calibration, the spacing squeeze, area-scaled rounding — recovers or changes with the raster.
These do not. Raising the ceiling to 1025 will not put ocean salinity inland.

## Observed behavior

> **Everything from here to the end of this section is the world *as it was when the card was
> filed*, and two of its three sub-classes have since been overtaken by world-scale fixes
> elsewhere.** It is kept because the reasoning is what the card is for, and because the
> refutations of two plausible wrong readings are still worth having. Where it says
> `freshwater_distance` is 0 on every land cell, `river` is a flat 1.0 or `island_habitat` is
> identically zero, the current tree reads 15 of 47, 24 of 47 and 1 of 47 at size 17. Class A —
> `salinity` and `fishing_productivity` on land — is unchanged and always will be; those are
> ocean quantities by construction.

Seed 42, sizes 17 and 33, `generator_version` 16. Scanning every archetype's `requires` terms
against the field values **restricted to the domain that archetype declares** finds five whose
gate field is entirely zero within their own domain. They split into three sub-classes with
different fixes, and one of them fails in the opposite direction to the others.

**Measure land the way the generator does.** `readers.cells(world, 'land')`
(`Sim/key_locations/core/world.py:150-172`) selects on the **`water_type` layer**, not on
`height > 0`, and excludes the poles and the seam column. That gives **47 land cells at size 17
and 268 at size 33**. A `height > 0` test gives 50 and 279 and wrongly counts coastal water cells
as land — it produced a "2 land cells clear the floor at size 33" reading in an earlier revision
of this card, and in a parallel analysis, that does not exist. All figures below use the
generator's own selection.

### A — land archetype, ocean field (3 archetypes)

| archetype | gate | land max, 17 / 33 | land cells ≥ floor | water (size 17) |
|---|---|---|---|---|
| `salt_mine` | `salinity ≥ 0.02` | **0.0000 / 0.0000** | 0 of 47, 0 of 268 | max 1.0000, **239 of 239** |
| `salt_pans` | `salinity ≥ 0.02` | **0.0000 / 0.0000** | 0 of 47, 0 of 268 | max 1.0000, 239 of 239 |
| `whaling_station` | `fishing_productivity ≥ 0.02` | **0.0000 / 0.0000** | 0 of 47, 0 of 268 | max 0.9718, 239 of 239 |

Identically zero on every land cell at **both** rasters — not sparse, not small, absent. All
three report `candidates: 0`, *"no ground in this world satisfies the requirements"*.

The fields are real and saturated; they are simply water quantities. `whaling_station` gating on
`fishing_productivity` is the clearest statement of the shape: an obviously-oceanic field gating
an obviously-shore building, with nothing reconciling them.

**The binding constraint is the absence, not the threshold.** It is tempting to read this as a
floor set too high, or as a percentile taken over a water-dominated population — both were
proposed and both are wrong. `__init__.py:243` is `cells = cells_by_domain[archetype['domain']]`
and `:252` passes those same cells to `eligible`, so **the percentile is already computed over the
archetype's own domain.** There is no wrong population to fix and no floor to lower: the field has
no values there at all. Lowering the floor to zero would admit every land cell, which is class C.

### B and C are one finding: two layers stopped being populated between generator 9 and 16

This replaces an earlier reading of "dead layer" and "empty field". Both were wrong, and the
truth is a **regression with a version boundary**, which is far more actionable.

Same reader, same seed, same size, same phase — only `generator_version` differs. Whole-grid
counts, stated exactly, because "identically zero" is falsifiable and one cell falsifies it:

| layer | gen 9, size 17 (289 cells) | gen 16, size 17 (289) | gen 16, size 33 (1089) |
|---|---|---|---|
| `island_habitat` nonzero | **2** | **0** | **0** |
| `freshwater_distance` nonzero | **5** (max 348.41) | **0** | **1** (max 2388.49) |
| `freshwater_distance` = −1 sentinel | 248 | 239 | 810 |
| `readers.cells` land / water | 39 / 201 | 47 / 193 | 268 / 724 |

`island_habitat` is the clean case: fully collapsed at both generator-16 rasters, no sentinel
involved, while **`ocean_archipelagos` is 3 in all three documents**. `freshwater_distance`
collapses to zero or near-zero rather than emptying — say "0 of 289 at size 17 and 1 of 1089 at
size 33, against 5 of 289 at generator 9", because a reviewer who greps for a nonzero value at
size 33 will find one.

**The features those layers measure still exist.** Archipelagos are unchanged, and the current
world has **47 river segments** against gen 9's 19 — more rivers, and a distance-to-them layer
reading zero.

**The sentinel still works, which narrows the bisect.** `−1.0` marks water in both versions — 248
cells at gen 9, 239 and 810 at gen 16. So the layer was not dropped and its water handling was
not broken; **only the land-side distance stopped being computed.** That rules out "the layer was
removed" without anyone needing to look.

**What `settlements.sites[].freshwater_distance_m` is and is not.** It is `0.0 .. 348.4` across 7
sites at gen 9 and **`0.0` for all 9 sites at size 17 and all 40 at size 33**. It is *not*
independent evidence: checked cell by cell, **zero settlements in any of the three documents
report a value differing from the layer beneath them**, and at gen 9 the one settlement standing
on a nonzero cell (`Bracken City`, 0/13) reports exactly that cell's 348.4. The field is a
faithful read of the layer, so it corroborates nothing the layer does not already say — the
regression evidence rests on the generator 9 versus 16 comparison alone.

It is still the **cheapest probe for a bisect**: forty numbers, no grid traversal, and it moves
with the layer.

So `quarantine_isle` (class B) reports `candidates: 0` because `island_habitat` is no longer
populated, not because the archetype is mismatched. It is the only one of the five that is not a
catalogue defect at all.

**Correcting a plausible reading that does not survive.** It is tempting to conclude the field is
zero because the world has no fresh water — seed 42 at size 17 does have **zero `water_type` 2
cells**, and size 33 has only 2. But gen 9 had zero freshwater cells too and still populated the
layer from its rivers, and the current world has 47 river segments. **The absence of lake cells
does not explain the absence of the layer.**

### C — the regression failing OPEN, which is worse than failing closed (1 archetype)

`holy_well` is `domain: land` and gates on `{'layer': 'freshwater_distance',
'below_percentile': 0.35}` — percentile-only, no absolute floor.

`freshwater_distance` on land is 0.0000 in all 47 cells at size 17, and nonzero in 1 of 268 at
size 33 (water carries the sentinel −1.0). Because the term is percentile-only over a field that
is all zero, **the computed cut is 0 and effectively every land cell passes**:

```
size 17   holy_well  candidates  47  = every land cell   wanted 4   placed 0   (spacing squeeze)
size 33   holy_well  candidates 267  of 268 land cells   wanted 5   placed 5   "placed"
```

The candidate counts are the land-cell counts. That is the tell: the gate is admitting the
domain rather than selecting within it.

**At size 33 this world contains five holy wells placed without their defining requirement ever
being enforced.** The archetype means "near fresh water"; the gate admits everywhere. A closed
failure is visible in `diagnostics`; this one reports `"placed"` and looks correct.

The asymmetry is structural: `resolve()` (`Sim/key_locations/core/placement.py:181-190`) turns a
percentile into a threshold over the domain's own values, so an empty field yields a cut of zero.
**An absolute floor on an empty field fails closed; a percentile on an empty field fails open.**
Four of the five here carry a floor; `holy_well` does not.

## Why it matters

Three separate consequences, one per sub-class:

- **A** removes three archetypes from every world permanently — including `salt_mine`, a tier-2
  interactable, on a reference world that has seven of them.
- **B and C are the same regression** and its severity depends only on which kind of gate reads
  the dead layer. `quarantine_isle` carries a floor, so it fails closed and disappears from the
  world — visible in `diagnostics`. `holy_well` is percentile-only, so it fails open.
- **C is the dangerous one, and it is dangerous because it reports success.** It does not reduce
  the count; it **silently voids a requirement**. Any archetype whose only gate is percentile-only
  over a sparse or empty field is placed effectively at random with respect to that gate. This
  world places five holy wells and reports `"placed"` for all five.
- **The regression itself outranks all five archetypes.** Two published layers collapsed between
  generator 9 and 16 while the features they describe still exist, and the settlement field that
  reads one of them collapsed with it. Whatever else `key_locations` does with those layers,
  anything else reading them is reading zeros. That is worth its own investigation and it is not
  scoped to this card.

## Proposed mechanism

1. **Audit, not guess.** The scan is twenty lines: for each archetype, for each `requires` term,
   compute the field's min/max/nonzero count **restricted to that archetype's `domain`**. Five
   archetypes fail it today. Run it over all 97 and over both domains rather than fixing the
   five by hand.
2. **Class A — decide per archetype whether the domain or the field is wrong.** A salt pan is a
   coastal-evaporation feature and a whaling station is a shore building; both plausibly want a
   *coastal* land cell scored by an adjacent water cell's value, which is a different query from
   the one they make. That is a catalogue-definition change, not tuning.
3. **Classes B and C — find the generator 9 → 16 regression first; it is not a catalogue
   problem.** `island_habitat` is 0 nonzero at both generator-16 rasters against 2 at generator
   9, and `freshwater_distance` is 0 of 289 and 1 of 1089 against 5 of 289 — while
   `ocean_archipelagos` is 3 in every document and river segments are *up* from 19 to 47. The
   `−1` water sentinel still populates correctly in both versions, so **bisect the land-side
   distance computation, not the layer's existence or its water handling.**
   `settlements.sites[].freshwater_distance_m` is the cheapest probe — forty numbers, no grid
   traversal — though it is a faithful read of the layer rather than independent evidence.
4. **Class C — make an empty-field percentile fail closed.** When a term's field has no nonzero
   values within the domain, `resolve()` should return `None` — the shape it already uses for
   "the world cannot serve this archetype", which callers report as a diagnostic rather than
   approximating around. Today it returns a cut of zero and admits everything.
5. **Add the reason to `diagnostics`.** `key_locations` already reports why an archetype did not
   place; it should be able to say *"its gate field carries no data in its domain"*, which is
   distinct from *"no ground in this world satisfies the requirements"* and points at the
   catalogue rather than at the world.

## Dependencies and unresolved decisions

- Whether `island_habitat` is meant to exist. If a populating pass was planned and not built,
  this is a missing capability rather than a dead entry, and the card should follow that work.
- Whether any *creature* profile has the same shape. The nest catalogue gates on absolute values
  only (`terrain_nests.py:84`), so it can only fail closed, but `medium` there plays the role
  `domain` plays here and the same audit applies. Not yet run.
- Step 4 changes placement behavior for any archetype currently benefiting from a fail-open gate.
  `holy_well` is the only one found, but the audit in step 1 should run before the change lands,
  because it would turn silent placements into reported absences and that will look like a
  regression in counts.

## Acceptance and evidence

- [x] No archetype gates on a field with zero nonzero values inside its declared domain, or the
  catalogue records why that is intended. **Done.** The three class-A archetypes were re-gated on
  land fields, and the catalogue carries a `gate_rule` note stating the rule.
- [x] A behavioral test asserts the property over the whole catalogue against a reference world, so
  a new archetype cannot be added with a mismatched field. **Done**, in two halves that cover
  different holes, with the limit of each written into its own docstring. See *The guard is two
  tests and neither is sufficient alone* below.
- [x] Every absolute floor in the catalogue is either the value below which its field means *none
  of the thing*, with the reason recorded, or it is removed. **Done** for the three floors this
  work introduced; the catalogue carries a `floor_rule` note stating the rule, and `salt_mine`'s
  floor went out with the term it sat on. **Not audited across the other ninety-odd archetypes**,
  which is the obvious next sweep and is not done here.
- [x] Every archetype's gate means what its `reason` string says. **Done for `salt_mine` only**,
  which is the one the audit named. Nobody has read the other ninety-six with that question in
  mind, and nothing in the output would show it if one of them were wrong.
- [x] An empty-field percentile term yields no candidates rather than all of them, with a test
  covering the `holy_well` shape specifically. **Done**, and widened from "empty" to "no variation",
  because a field that is a flat *nonzero* constant fails open in exactly the same way and `river`
  is one.
- [x] `diagnostics` distinguishes "field carries no data in this domain" from "no ground satisfies".
  **Done**, and a third case was separated at the same time: *"no room: N of M qualifying cells
  already carry another feature"*, which used to be reported as *"spacing and clearance left room
  for fewer"* even when the number placed was zero.
- [x] The generator 9 → 16 collapse of `island_habitat` and `freshwater_distance` is diagnosed.
  **Done, and not by this card.** Both were world-scale bugs fixed in the same wave, each with the
  same shape: a constant authored for the 11.15 km reference world, left absolute on a 200 km one.
  `island_habitat` carried an absolute `min(3e6, …)` island-size arm — 3 km², against a single
  size-17 cell of 15.2 km² at 200 km — so no component could ever be small enough to count
  (`Sim/icarus_sim/terrain_ecology.py:131-134`).
  The river side was the same shape: `river_threshold_km2` left at its 11 km value,
  so every land cell drained enough to be a river, `freshwater_distance` read 0 everywhere and
  `river` read a flat 1.0. Measured on the current tree: `island_habitat` is nonzero in 1 of 47
  land cells at size 17 and 42 of 268 at size 33; `freshwater_distance` in 15 of 47 and 139 of 268;
  `river` in 24 of 47 and 22 of 268. This card's step 3 is obsolete — the bisect it asks for has
  been done and the answer was neither the layer's existence nor its water handling but the metre
  constants, which is the generalisation worth keeping.
- [x] A percentile term that admits the entire domain is refused, not just one over a constant
  field. **Done, 2026-09-21.** `resolve` tests the *resolved* rule — floor included — against
  the domain and returns `None` when every cell clears it; `gap` reports a fourth reason naming
  the layer, the percentile and the share admitted. The open design question this carried was
  decided rather than deferred: see *The open question, decided* below, including the two
  alternatives rejected and why, so the ruling can be reversed in one place.
- [x] The catalogue-versus-world audit runs against a **generated** world, not a fixture and not a
  hand-curated table. **Done, 2026-09-21**, as `GeneratedWorldGateAudit` in
  `Sim/tests/test_key_locations.py` — one seed-42 size-17 phase-16 world built once for the class,
  four assertions. It immediately found something both cheap halves are structurally blind to:
  **`peat_cuttings` requires `wetland_distance`, a layer nothing in this repository writes.** See
  *What the generated-world audit found on its first run* below.

### The test guards reintroduction; it did not and could not find this

Worth stating plainly, because the opposite is the natural assumption. The test module builds a
hand-written world rather than generating one, and its fixture gave `salinity` a smooth gradient
across the map with no reference to the water mask. So the fixture made all three class-A
archetypes look placeable while they were unplaceable in every world the generator has ever
produced — a fixture kinder to the catalogue than the world is hides exactly the defects a
catalogue can have. The fixture now mirrors the measured semantics: `salinity` 1.0 on water and
0.0 on land, `fishing_productivity` 0.0 on land. **The audit only became a real guard once the
fixture stopped lying**, and the audit against a generated world is still worth adding separately.

### The guard is two tests and neither is sufficient alone

The audit above runs only against the hand-built fixture, so it guards exactly the two semantics
that fixture was just taught — which was the audit's own finding about itself, and it is correct.
The fix is not to pretend otherwise but to add the half the fixture cannot supply, and to write
each half's limit into its own docstring.

`test_no_archetype_requires_a_layer_measured_dead_in_its_own_domain` checks the catalogue against
`CONSTANT_IN_DOMAIN`, a curated table of layers that carry no data inside a domain **by
construction** — each one written as `<expr> if water[i] else 0.` or its mirror in
`terrain_ecology.derive`, or a definition, as with the depth of water where there is no water.
Sixteen entries, every one confirmed by reading the full size-17 document, and the eight that
survive into the pruned worlds re-confirmed at size 33. It never looks at the fixture.

The table is curated on purpose and the reason is the distinction this whole card turns on. A raw
`min == max` sweep of one document returns about a hundred layer/domain pairs, and most of them —
`ley_blood`, `zone_dead_sea`, `suitability_tidekin` — are constant because *this world* has no
blood magic, no dead sea and no tidekin. **That is an unlucky world. A layer that is constant
because the code that writes it skips the domain is a catalogue fault waiting to be committed.**
Only the second kind is in the table, which is why it is short.

The two halves catch different things, demonstrated rather than asserted. Pointing `salt_mine` at
`water_depth` or at `reef` — both `domain: land`, both identically 0.0 on land in every generated
world measured — makes the new test fail and the fixture audit **pass**, because the fixture gives
both fields variation on land. Pointing it back at `salinity` fails both, because the fixture was
taught that one. Conversely the fixture audit catches any archetype naming a layer the table does
not list, including a layer nobody has measured yet. Neither test subsumes the other and the card
should not claim either does.

What is still missing, stated so it is not mistaken for done: **an audit against a generated
world.** Both halves are catalogue-versus-something-cheap; neither runs the generator, and the
table is a reading from one seed at two rasters rather than a property of the code that writes
those layers.

### The fail-closed rule is necessary and not sufficient: a *saturated* field fails open too

Found while measuring the fix, and it is the next thing anyone working here should know. The rule
implemented catches a field with **no variation** in the domain. It does not catch a field that
varies but is saturated, and that case is live right now:

```
size 33   ford   requires river above_percentile 0.55   candidates 268 of 268 land cells
```

`river` is not constant at size 33 — so the rule lets it through — but it is saturated enough that
the 55th-percentile cut lands at a value every land cell clears. The gate admits the entire domain
exactly as `holy_well` did, and reports success. Same defect, one step further along.

**Re-measured after the river-threshold fix landed, because the obvious guess is that it cured
this too. It did not.** `river` now varies properly on land — 24 of 47 nonzero at size 17 and 22
of 268 at size 33, against a flat 1.0 before — and `ford` and `ferry_crossing` are **still 268 of
268** at size 33. The field is now *sparse* rather than saturated, and a `below`-style reading of
an `above_percentile 0.55` cut over a field that is zero on 92 per cent of the domain lands at
zero, so everything clears it. Zero variance, saturation and sparsity are three routes to the same
place, which is the argument for a rule shaped on the outcome rather than on the field.

Stating the general form so it is not rediscovered as a third instance: **a percentile gate carries
no information whenever the cut it computes does not separate the domain.** Zero variance is the
degenerate case of that, not the whole of it. A rule shaped on the *outcome* — refuse a resolved
term that admits every cell in the domain, or more than some share of it — would cover both, and it
is a bigger decision than this lane should take alone, because it changes the meaning of a
percentile from "the top N per cent" to "the top N per cent, and it has to be a real top". Two
archetypes (`ford`, `ferry_crossing`) are eligible on all 268 land cells at size 33 and all
1,174 at size 65 today, and at 65 they place 10 and 3 sites from that unfiltered domain. **This
is the one item on the card that is producing wrong content right now rather than absent
content**, which is the argument for it being what the card stays open on.

**Decided and implemented 2026-09-21** under the sweep's pick-implement-flag ruling, with both
rejected alternatives written down — see *The open question, decided* below. Re-measured on
worlds generated that day, it is bigger than this section's two archetypes: **fourteen archetypes
at size 17 and eighteen at size 33** resolve to a cut that admits every land cell, and the largest
single cause is `settlement_distance` rather than `river`. `bridge` was the wrong-content case,
placing five sites at size 33 through a river term resolving to zero.

### The open question, decided: a percentile has to be a genuine top

The section above says the outcome-shaped rule *"is a bigger decision than this lane should take
alone, because it changes the meaning of a percentile from 'the top N per cent' to 'the top N per
cent, and it has to be a real top'."* Under the sweep's standing ruling — **pick the conservative
option, implement it fully, record the choice and the alternative** — it was taken rather than
deferred. Written out so the owner can reverse it in one place.

**Decided.** A `requires` term is refused when its **resolved** rule admits every cell in the
archetype's own domain, and the archetype is then refused whole, exactly as the zero-variance rule
already does. Implemented at `Sim/key_locations/core/placement.py`, in `resolve` and reported by
`gap`. Reversing it is deleting the two-line `_admits_everything` guard in `resolve`.

Three things make that the conservative reading rather than the strict one.

- **It fails closed.** The whole card is an argument that the open direction is the dangerous one:
  a closed failure costs a kind of place and says so in `diagnostics`, an open one puts a place
  somewhere its own `reason` string does not hold and reports `placed`. Refusing keeps the system
  on the side it is already on.
- **It introduces no authored constant.** "Admits every cell" is falsifiable and derived; a share
  is a number somebody chose. `floor_rule` exists because untraceable tuning is the defect class
  this catalogue keeps rediscovering, and a threshold in the engine would be the same defect one
  level up.
- **It is the same predicate, not a second one.** The admission is tested with `satisfies` — the
  function `eligible` goes on to call — rather than a reimplementation of it, so the gate cannot
  refuse a term that would have discriminated or keep one that would not.

**Rejected A: refuse at a share of the domain rather than all of it** — "more than 90 per cent
clears the cut" and variants. Rejected on a measurement, not on taste: at size 17
`whaling_station`'s `coastal_fishing_productivity` term resolves to a cut of 0.42 that admits
**44 of 47** land cells — 93.6 per cent — and that archetype is the content the class-A fix was
filed to create. A 90 per cent rule deletes it. Any share below 100 is a number with no
derivation sitting exactly where `floor_rule` forbids one, and the band between "doing real work"
and "doing nothing" is measured here at 93.6 versus 100, which is too narrow for a chosen
constant to sit in honestly.

**Rejected B: make the percentile always select a real top, by rank instead of by value** — take
the best `ceil((1 − q)·n)` cells rather than every cell at or above the `q`-th value. This is the
tempting one, because it preserves content: `hermitage` would get a genuine top 30 per cent of 268
cells instead of being refused. It is rejected because of what it has to do at the boundary. When
70 per cent of the domain ties at the field's minimum, a rank rule must pick some of those tied
cells and drop the others, **inventing a distinction the field does not carry** — two cells the
world says are identical, separated by list position. That is a fabricated preference dressed as a
measurement, and it is worse than the absence it replaces. It would also move content for all 97
archetypes rather than close one fail-open hole, which is a larger blast radius than this card.

**What it does not change.** An archetype with no `requires` at all is untouched — the chain and
cluster furniture stands anywhere by declaration, and this is a rule about a percentile that
stopped discriminating, not about a wide gate. An absolute floor beside a percentile is untouched
and still rescues the term, because the admission is tested against the resolved rule with the
floor in it; that is precisely the job `floor_rule` gives a floor, and it is asserted in the test.

### What the refusal costs, measured on worlds generated the same day

Seed 42, `recipe_version` 3, phase 16, the 200 km `world_size: small` preset through
`generate_request`, generated 2026-09-21 and frozen; the engine run against the same frozen
document before and after the change, in one process — the only method that attributes a delta to
this lane rather than to the four others editing the tree. Generation cost on a contended box:
104 s at size 17, 356 s at 33, 483 s at 65. Sizes 129 and 257 were **not** measured.

| | size 17 | size 33 | size 65 |
|---|---|---|---|
| land cells | 47 | 268 | 1,174 |
| sites emitted | 100 → **94** | 243 → **241** | 487 → **479** |
| scattered sites (no chains, no clusters) | 13 | 92 | 270 → **257** |
| archetypes refused for a collapsed percentile | 0 → **14** | 0 → **18** | 0 → **5** |

**The small net is not a small change.** Fourteen, eighteen and five archetypes stop placing; the
totals barely move because the node budget hands the freed ground to whatever was next in line,
which is the same reshuffle this card documents elsewhere. At size 65 the refused archetypes were
carrying **24** sites between them — `ford` 10, `bridge` 6, `ferry_crossing` 3, `toll_station` 3,
`tar_pit` 2 — and the world ends eight sites down, so two thirds of what they held was taken up by
something else. At size 33 the archetypes that lose sites are `hermitage` 6, `bridge` 5,
`hedge_inn` 5, `beast_den` 5, `bandit_camp` 4, `refuge_broch` 3, `ferry_crossing` 2, `monastery` 2,
and one each of `binding_site`, `dragon_lair`, `giants_hall`, `hunting_lodge`, `wizard_tower`.
`hermit_cell` loses its one cluster site and `pilgrim_station` drops from 7 to 2, neither because
they are gated — a cluster or chain member never enters `eligible` — but because their anchors
went.

**The refusal count falls with the raster, and that is the most useful thing measured here.**
Thirteen of the fourteen refusals at size 17 and thirteen of the eighteen at size 33 are one
cause — `settlement_distance` — and **at size 65 that cause is gone entirely.**

| layer | zero on land, 17 | 33 | 65 | archetypes refused |
|---|---|---|---|---|
| `settlement_distance` | 41 of 47 | 189 of 268 | **323 of 1,174** | 13 at 17, 13 at 33, **0 at 65** |
| `deposition` | 37 of 47 | 201 of 268 | 743 of 1,174 | `tar_pit`, at every raster |
| `river` | 23 of 47 | 246 of 268 | 1,143 of 1,174 | `ford`, `ferry_crossing`, `bridge`, `toll_station`, at 33 and 65 |

`settlement_distance` reads zero where a settlement stands. This world stands **41** settlements
on 47 land cells at size 17, **213** on 268 at 33 and **408** on 1,174 at 65 — so the share of land
that *is* settlement falls from 87 per cent to 71 to **28**, and by size 65 there is a genuine top
thirty per cent of distance-from-a-settlement to be had again. **So thirteen archetypes vanishing
is a coarse-raster artefact that resolves by itself at a raster the project already calls
representative**, and it is not a catalogue fault. Nothing is re-gated to work around it; that
would hide the thing that produced it. One thing worth checking rather than assuming, and **not
measured here**: 28 of 56 fortresses stopped sharing a node with a coastal hamlet on 2026-09-21,
which moves the count of *distinct* cells reading zero. Whether that made this better or worse was
not measured, and no world from before that change was available to compare against.

**What does not resolve with the raster is `river`, and it gets worse.** Zero on 49 per cent of
land at size 17, 92 per cent at 33 and **97 per cent at 65** — so the four wayside archetypes are
refused at both finer rasters and would be at any finer one. That is the genuinely open finding
this rule surfaces rather than fixes: a river layer that marks 31 of 1,174 land cells cannot
support a percentile gate, and either the layer or the four gates is wrong. It belongs with
SCALE-METRE-CONSTANTS-COLLAPSE rather than here.

**The archetype producing wrong content rather than absent content was `bridge`**, five sites at
size 33 and six at 65 through a `river` term resolving to a cut of 0 — with `ford` (10 at 65),
`ferry_crossing` (3) and `toll_station` (3) beside it. That is the case the card named as the
argument for staying open, and at size 65 it is 22 sites, not two.

### What the generated-world audit found on its first run

The audit is four assertions against one world the generator actually made, and it earned its
cost immediately.

**`peat_cuttings` requires `wetland_distance`, and nothing in this repository writes that layer.**
Not the generator, not `fields.derive`. It appears in exactly two places: the docstring at
`Sim/key_locations/core/fields.py:4`, which asserts the world publishes it, and the hand-built
test fixture, which publishes it — so the fixture audit is green on it and always was. `resolve`
returns `None` on a missing layer, so this fails *closed* and `diagnostics` has been saying *"the
world never generated the wetland_distance layer"* in every world ever generated. It costs a kind
of place and says so, which is the loud half of the asymmetry, so it is recorded rather than
fixed: re-gating the archetype or deriving a wetland field is a separate decision about what marsh
means in this world, and the retired BIOME-MARSH-IS-THE-RIVER-MASK suggests that question is not
as simple as it looks. The audit pins the set **exactly** — it cannot grow without failing, and it
cannot be quietly fixed without failing either.

**No archetype's required layer is constant inside its own domain on a generated world.** The
fixture-and-table halves both claim this; now something has checked it against real ground. Green
at sizes 17, 33 and 65.

**The audit's own limit, written into its docstring so it is not mistaken for more than it is.**
One seed at one raster, and size 17 was chosen for cost. A gate that collapses only at a finer
raster passes it — and `river` is exactly that shape, getting worse with the raster rather than
better. The audit is a guard against reintroduction, not a sweep.

**`crannog` has no domain at size 17.** Seed 42 at size 17 has zero `lake` cells, so
`readers.cells(world, 'lake')` is empty. That is an unlucky world rather than a fault and the
audit skips an empty domain, as the fixture audit already does.

### Delivered 2026-09-21

Failing test first, in both halves. `test_a_percentile_that_admits_its_whole_domain_is_refused`
failed with *"[{'layer': 'river', 'min': 0.05}] is not None : a cut every land cell clears is not
a top 45 per cent of anything"* — no synthetic layer, the fixture's own `river` puts `ford`'s
shipped gate on all 219 fixture land cells. `test_nothing_is_placed_through_a_gate_that_admitted_its_whole_domain`
failed on the generated world with *"[('beast_den', 'land', 47, ['settlement_distance']),
('monastery', 'land', 47, ['settlement_distance'])] != []"*. Both green after.

- `Sim/key_locations/core/placement.py` — `_percentile_rule` (one statement of the resolution,
  read by both `resolve` and `gap`, because two copies is how a diagnostic starts describing a
  different question from the gate), `_admits_everything` (calls `satisfies`, does not restate
  it), the guard in `resolve`, the fourth reason in `gap`.
- `Sim/key_locations/__init__.py` — block `VERSION` 1 → **2**, with the reason beside it.
- `Sim/key_locations/catalogue.json` — new `percentile_rule` note stating the rule, its two
  non-degenerate routes and its measured cost; `revision` 3 → **4**.
- `Contracts/schemas/key-locations.schema.json` — `version` const 1 → **2**; the `diagnostics`
  description now names all four gap reasons and says the rows are one per *pass*, not one per
  archetype.
- `docs/key-locations.md` — the gate section, the fourth diagnostic reason, the block version, and
  the site-count paragraph re-measured. The previous counts there (22/100/287 scattered,
  111/255/491 total) predate `AGE_YEARS` 100 → 5000, four planner version moves and this change,
  so they were replaced rather than adjusted: **13, 92 and 257 scattered and 94, 241 and 479 total
  at sizes 17, 33 and 65.** Sizes 129 and 257 were not measured.
- `Sim/tests/test_key_locations.py` — one unit test and the four-assertion
  `GeneratedWorldGateAudit` class. 98 tests green.

**No `docs/conformance/` record claims any module under `Sim/key_locations/`.** All fourteen are
on the `docs/conformance/coverage.json` uncovered allowlist, ticketed to
`board/in-progress/CONFORMANCE-DOCS.md`. `docs/key-locations.md` is the present-tense document for
this block and was updated instead; no conformance record was created, because that would mean
deleting fourteen entries from a shared allowlist that an in-progress card owns.

**`Fixtures/sample-world-v1.json` is stale.** This change moves generated output. It was not
rebuilt.

### Deliberately not done: `geyser_basin` and `lava_tube` are correctly calibrated and the raster is too coarse

This is the tail-calibration cause the card names as distinct from its own, and it was measured
rather than assumed because the temptation to lower the floor is strong and acting on it would be
irreversible. **`geyser_basin` needs a bigger raster, not a smaller floor.** It wants its own card;
this lane could not create one, so the measurement is recorded here.

Seed 42, phase 9, `volcanic` restricted to land by the generator's own cell selection:

| size | land cells | land max | p82 cut | ≥ 0.05 | ≥ 0.08 | `geyser_basin` / `lava_tube` candidates |
|---|---|---|---|---|---|---|
| 17 | 47 | **0.0286** | 0.00057 | **0** | **0** | 0 / 0 |
| 33 | 268 | 0.1524 | 0.00145 | 8 | 3 | 8 / 3 |
| 65 | 1,174 | 0.1524 | 0.00154 | 20 | 5 | 20 / 5 |
| 129 | 4,870 | 0.1524 | 0.00167 | 66 | 21 | 66 / 21 |
| 257 | 19,521 | 0.159 | 0.00179 | 286 | 93 | 286 / 93 |

Three things this settles.

**The field fires and the gate is not broken.** The candidate count grows smoothly with the
raster and only size 17 has no qualifying ground at all.

**One correction and one confirmation, because an audit of this section got one of each.** The
audit reported `geyser_basin` moving from 3 placed to 2 at size 65 and called this section's
premise contradicted. It does not reproduce: measured at phase 16 on the frozen size-65 world,
`geyser_basin` is **20 candidates and 3 placed under all three package revisions**, exactly as the
wave-1 card said, and it is likewise unmoved at 17 (0/0) and at 33 (8/0). *"Unmoved at every
raster"* stands.

What does not stand is the sentence above it. **"Both archetypes place from size 33 upward" is
false**, and the reason is worth keeping: the candidate table here is a **phase 9** sweep, and what
an archetype does with its candidates at phase 16 is a different question, because by then ruins,
nests and religion sites have taken ground. At phase 16, size 33, `geyser_basin` has its 8
candidates and places **none** — *"no room: 6 of 8 qualifying cells already carry another
feature"* — and `lava_tube` has 3 and places none; at size 65 `geyser_basin` places 3 and
`lava_tube` still places none from 5. **Candidates are ground; placements are ground that is still
free.** Everything in this section is a claim about the first, and the conclusion it reaches — the
floor is right and the raster is what is short — rests on the candidate column alone and is
untouched.

**The percentile is never the binding term; the absolute floor is.** The p82 cut sits around
0.0018 at every size — two orders of magnitude below the 0.05 floor. So this is the floor doing
precisely the job it was written for, which the catalogue note describes as stopping "the most
volcanic ground on a world with no volcanism" from qualifying. At size 17 the land max is 0.0286
and there genuinely is no volcanic ground; 47 land cells cannot resolve a hotspot.

**Lowering the floor would cost every larger world permanently and buy one cell on one seed.**
Dropping it from 0.05 to 0.0286 — the least change that could admit anything at size 17 — takes
geyser ground on a size-257 world from 286 cells to 661, from 1.5% of land to 3.4%, and the same
2.3× at size 129. It would still put exactly one candidate at size 17, and only on this seed.
That is the shape of retune the settled ruling in this repository exists to refuse.

### A separate defect found in passing and deliberately left alone

`budget()` is called with land area for **every** archetype, including the `water`, `ocean` and
`lake` ones, so a `maelstrom` and a `drowned_temple` are budgeted by how much *land* the world has.
It is uniform and arguably defensible as "content density tracks how much world there is to
explore", but it is not what the field name says. Changing it would move the counts of roughly
fifteen water archetypes at once, which is a wider blast radius than this card, so it is recorded
here rather than acted on.

## Adversarial review and limitations

Seed 42 only, at sizes 17 and 33, so the land/water statistics are one world's. That does not
weaken classes A and B — `salinity` and `fishing_productivity` are oceanic by construction and
`island_habitat` is zero in all four domain/raster combinations measured — but a seed whose
coastline differs could in principle put a stray nonzero cell where this world has none. The
claim most worth a second seed is the `holy_well` fail-open, because it depends on the field
being empty rather than merely sparse; the gamer-persona session reports `island_habitat` also
zero on seed 73, which covers class B for one more world.

**Two measurement errors were made reaching this card and both are worth recording, because they
point opposite ways.** Classifying land by `height > 0` rather than by the `water_type` layer
counts coastal water as land and produced a "2 land cells clear the floor at size 33" reading in
an earlier revision here and in a parallel analysis; on the generator's own selection the count
is zero at both rasters, so the finding was *understated*. And that false reading then invited a
second inference — that the percentile must be taken over a water-dominated population — which
`__init__.py:243` refutes. **Neither error would have survived running `readers.cells` instead of
reimplementing it.** Any future audit here should import the block's own reader rather than
re-deriving the domain test.

`freshwater_distance` reads 0.0000 on land and −1.0 on water, which looks like a sentinel
convention rather than a measured distance. If the intended semantics are "−1 means no data",
then class C is a sentinel being read as a value, which would be a smaller and more local fix
than step 4 — worth checking before implementing anything. **Still live, and now visible on land
too:** after the river fix the minimum on land at size 33 is **−1.0**, so at least one land cell
is carrying the water sentinel. Any archetype reading that layer with a `below_percentile` term
treats it as the nearest water in the world.

**A third measurement error, from the pass this card documents, and the most instructive of the
three.** `len(readers.claimed_nodes(world))` was read as "land cells already taken". It is not:
it counts every node any module claimed, most of them at sea. 94 against the 16 that matter. The
common thread with the other two is that all three came from asking a question the block never
asks — `height > 0` instead of the water mask, a whole-grid population instead of the domain's, a
whole-grid claim count instead of its intersection with the domain. **Every one of them would
have been caught by starting from `readers.cells(world, archetype['domain'])` and intersecting,
which is what the block itself does.**

**What was and was not re-measured in this follow-up.** Sizes 17, 33 and 65, seed 42, phase 16,
on the 200 km preset, three package revisions each against one frozen document per raster. **Not**
measured: any other seed, and sizes 129 and 257 — which matters most for the floors, because the
percentile-collapse crossing they exist to catch is predicted to fall between 65 and 129 and has
not been observed. A size-65 phase-16 world costs about ten minutes of CPU on a contended box, so
a second seed is affordable and a 129 is not obviously so; the claim most worth a second seed is
still the shape of `coastal_exposure`'s zero share, since everything about the floors rests on
it climbing monotonically with the raster and that is three points on one world.
