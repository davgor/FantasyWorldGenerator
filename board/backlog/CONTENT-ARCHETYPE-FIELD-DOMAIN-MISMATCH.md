# CONTENT-ARCHETYPE-FIELD-DOMAIN-MISMATCH — five archetypes gate on a field that carries no data where they are allowed to stand

Owner: none. State: open, unowned. Found by the Python-output red team; the coordinator asked for
it as a card of its own because it is the one key-location finding that needs no generated world
and waits on nothing (`docs/reviews/233182e-python-output-red-team.md`, finding 8, cause 1).

**This is resolution-independent.** Every other cause of a missing key location — tail
calibration, the spacing squeeze, area-scaled rounding — recovers or changes with the raster.
These do not. Raising the ceiling to 1025 will not put ocean salinity inland.

## Observed behavior

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

The asymmetry is structural: `resolve()` (`Sim/key_locations/core/placement.py:110-115`) turns a
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

- No archetype gates on a field with zero nonzero values inside its declared domain, or the
  catalogue records why that is intended.
- A behavioral test asserts the property over the whole catalogue against a reference world, so a
  new archetype cannot be added with a mismatched field.
- An empty-field percentile term yields no candidates rather than all of them, with a test
  covering the `holy_well` shape specifically.
- `diagnostics` distinguishes "field carries no data in this domain" from "no ground satisfies".

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
than step 4 — worth checking before implementing anything.
