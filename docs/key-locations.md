# Key locations

The charged non-settlement places a finished world implies: caves, mines, barrows,
mausoleums, shrines, watchtowers, ley nexuses, dragon lairs, drowned villages and wonders.

Before this existed, the entire non-settlement point inventory was two `regions.landmarks`
kinds — a witch hut and a necropolis — placed in five lines at
`Sim/icarus_sim/terrain_ecology.py:166`. The asset catalogue README said as much:
*"Not in this current baseline: … interactive underground halls/caves … Ruins/graves/
historical sites similarly need a future location/history generator."* This is that
generator.

## What a key location is

Not a noun from a list. A tuple:

```
(archetype, tier, state, occupant, origin)
```

- **"Forgotten fortress"** is not an archetype. It is a fortress that is `ruined` with
  occupant `none`.
- **"Dungeon"** is not an archetype either. It is any tier-2 complex whose occupant is
  hostile — a mine goblins took, a mausoleum the dead woke in, a fortress a dragon claimed.

There is deliberately no `dungeon` archetype and no `forgotten` state. Both are outcomes,
and the world produces them: `state` and `occupant` are derived from what the simulation
already recorded — whether a ruin sits nearby, whether the ground is remote, how unstable
the local weave is, what lives next door, how many ages have passed.

Ninety-seven archetypes across eleven families ship in the catalogue: 12 tier 0, 56 tier 1,
24 tier 2 and 5 tier 3.

## Tiers — scale, never danger

| Tier | Meaning | Interior |
|---|---|---|
| 0 | A marker. One line of text. | Never |
| 1 | A site; one scene you can stand in. | No |
| 2 | A multi-room complex. The dungeons. | Always |
| 3 | A unique world-scale wonder. | Sometimes |

`tier` is physical scale and how much the place still needs building out. It is **not**
danger — a tier-3 wonder can be harmless and a tier-1 barrow lethal. Read `threat` for
danger: an integer 1–5 on the same creature-tier rubric the nest catalogue uses, so ranking
a dungeon against a beast lair compares like with like.

Three other fields in this tree are also called `tier` and none of them means this one:
creature tier (int 1–5 danger, `terrain_nest_profiles.json`), villain tier (a float that
also sets reach in metres, `terrain_villains.py`), and hero tier (a string enum,
`hero-generator.schema.json`).

## Families

| Family | Driver | Examples |
|---|---|---|
| `subterranean` | lithology proxies, slope, volcanism, relict incision | karst cave, lava tube, sea cave, glacier cave |
| `extractive` | metal richness, aridity, coast, roads, ruins | iron/silver/gem/salt mine, quarry, salt pans |
| `fortification` | borders, roads, topographic prominence | border fort, watchtower, hillfort, dyke |
| `funerary` | ruins, culture, plague and war causes | barrow, mausoleum, necropolis, plague pit |
| `sacred` | religion, ley field, prominence | monastery, standing stones, holy well, drowned temple |
| `wayside` | roads, rivers, passes | bridge, ford, crossroads, hedge inn, caravanserai |
| `arcane` | ley density, instability, hazard | ley nexus, wizard's tower, binding site, academy ruin |
| `lair` | remoteness, height, nest proximity | dragon lair, giant's hall, wyvern eyrie |
| `drowned` | water depth, relict water layers | drowned village, wreck field, crannog |
| `wonder` | one-offs, 0–1 each | fallen star, titan skeleton, the Scar, maelstrom |
| `curiosity` | the long tail | observatory, library ruin, lighthouse, bandit camp |

Lairs are mostly an *occupancy* applied to a placed location rather than a fresh scatter. A
dragon in an abandoned silver mine beats a dragon in a generic cave: it arrives with a map,
a reason for the hoard, and a dead town downhill.

## Placement

Archetypes are **data**. Adding a kind of place is a catalogue edit
(`Sim/key_locations/catalogue.json`), not a code change; if a new kind needs new code, the
placement engine is underspecified and that is the bug to fix.

Each archetype declares:

- `requires` — terms that gate the ground entirely
- `prefers` — weighted terms that rank one cell above another
- `per_1000_km2`, with optional `min_count` / `max_count`
- `spacing_cells`, `settlement_clearance_cells` — cell multiples of a *fixed reference
  raster*, so they are physical distances that scale with the world and do not change when
  the same world is sampled more finely

**Requirements are percentile-relative with an absolute floor.** `volcanic >= 0.35` means
something different on every world and on a quiet one silently means *never*. Asking for the
top eight per cent of volcanism travels between worlds; the absolute floor beside it decides
whether the best available is good enough at all. A world with no volcanism gets **no lava
tubes and a diagnostic row saying so**, not its least-quiet hillside.

**A gate must name a field that varies where the archetype is allowed to stand, and the two
halves of a gate fail in opposite directions.** An absolute floor over an empty field admits
no cell: the archetype disappears and the diagnostics say so, which is loud and cheap to
find. A percentile over an empty field computes a cut equal to the one value present, every
cell clears it, and the gate silently admits the whole domain while reporting `placed` — the
archetype's defining requirement is voided and nothing in the output says so. So **an
absolute floor on an empty field fails closed; a percentile on an empty field fails open**,
and the open one is the dangerous half because it looks like success.

A percentile term over a field with no variation inside the domain therefore resolves to
nothing, with a diagnostic naming the field and the domain. This is the same line
`normalisers` already draws for scoring — a constant field carries no information about where
to put anything — applied to the harder question of whether a cell may stand at all.

The corollary is a rule about the catalogue rather than about any world: **a `requires` term
must name a layer that carries data inside the archetype's own `domain`.** Three archetypes
did not. `salt_mine` and `salt_pans` were `domain: land` gated on `salinity`, and
`whaling_station` on `fishing_productivity`; both layers are ocean quantities, reading
identically 0.0 on every land cell at sizes 17, 33, 65, 129 and 257. They were unplaceable by
construction — not unlucky, not mistuned, and unrescuable by any seed or raster. A shore
archetype that genuinely needs the sea asks a derived `coastal_` field instead, which carries
the best neighbouring water value onto the land cell; that is a different query, not a
lowered threshold.

Each of the three now asks a question its own ground can answer, and the question has to be
the one the archetype's `reason` already claims. `salt_pans` asks `coastal_exposure`, the
share of a cell's neighbours that carry water, and `whaling_station` asks the derived
`coastal_fishing_productivity`. `salt_mine` is not a shore building at all — its reason is an
evaporite basin, *"a sea dried here long ago"* — so it asks for dry ground (`rainfall`) that
sits low relative to what surrounds it (`tpi`). An intermediate revision of this fix gated it
on `metal_richness`, which is an ore proxy —
`clamp(0.45 + 0.7·perlin + 0.2·volcanic)` at
`Sim/icarus_sim/terrain_ecology.py:108` — and carries no information about rock salt at
all. **A gate that does not mean what the archetype's reason
says places the right noun for the wrong cause**, and nothing downstream can tell.

**An absolute floor must be the value below which the field means *none of the thing*, and
the reason has to sit beside it.** A floor picked from inside the field's own distribution is
tuning, and untraceable tuning is the defect this page keeps rediscovering. The two floors
that survive that test say why in the catalogue's `floor_rule`, and both turn out to be the
same statement — *touches water at all* — written in each field's own units.
`coastal_exposure` is a count of a cell's water neighbours over its neighbour count, and on
the sphere grid every non-polar cell has six or eight neighbours (`terrain_erosion.sphere_grid`
at sizes 17 to 257: degrees 6 and 8 everywhere except the two poles, which `readers.cells`
excludes), so the smallest positive value the field can take is 1/8 and `min: 0.125` admits
exactly the cells that touch water. `fishing_productivity` is `clamp(0.12 + …)` wherever
water exists and 0.0 on land
(`Sim/icarus_sim/terrain_ecology.py:104`), so `min: 0.12` on the derived shore field says
the same thing. Neither is a level. The third floor, `metal_richness ≥ 0.3`, *was*
a level — it sat inside a distribution that runs 0.15 to 0.68 on land — and it went out with
the term it was attached to.

**And the floors are one raster step from being the whole gate.** The share of land reading zero
climbs with the raster — 2.1 per cent at size 17, 28.7 at 33, **49.9 at 65** — and because
`percentile` is nearest-rank, the cut falls with it: the `coastal_exposure` p55 cut resolves to
0.500, then 0.375, then **exactly 0.125 at size 65**, which is the smallest positive value the
field can hold and is the floor. `coastal_fishing_productivity`'s p60 cut is **exactly 0.12** at
size 65 for the same reason. Once more than about **55 per cent** of the domain reads zero the
cut is zero, every inland cell clears the gate and the archetype's defining requirement is voided
— and size 65 is already at 49.9. So the floors are not decoration and not a hypothetical: at the
finest raster measured the percentile has already fallen to meet them, and past 129 they are all
that is left of the gate.

Selection is greedy over jittered suitability. The jitter matters: pure greed piles every
site on the single best ridge and the map reads as a gradient, while pure randomness ignores
the suitability field the archetype just declared.

Seven derived fields the world does not publish are computed per run — `road_distance`,
`settlement_distance`, `ruin_distance`, `nest_distance` and `villain_distance` (multi-source
cell sweeps), `frontier` (where `culture_region` owners differ across a step, since territory
here is a raster frontier and not a polygon), and `coastal_fishing_productivity` (the best
`fishing_productivity` among a land cell's water neighbours, zero inland and zero at sea).

### Density, and why it is denominated in area

Counts are `per_1000_km2` of land, scaled from the world's own measured land area. Three
things about that are easy to get wrong and all three were, before they were fixed.

**A fractional expectation is a chance, not a zero.** Rounding the expected count to the
nearest integer looks harmless. It is not: on a small world every archetype's expectation
falls below a half and the entire catalogue rounds to zero *at once*, so the world reports
"too small to support one" ninety times and grows nothing. The legacy 11 km reference world
that `tools/terrain_lab.py` builds by default has about 6 km² of land and did exactly that.
The budget now takes the floor and draws for the remainder — the same thinned point process
`terrain_nests` uses for creature anchors — so a tiny island grows one or two notable places
instead of none, and a continent is unaffected.

**A rate of zero is not a rate, and the thinned draw cannot rescue it.** The five tier-3
wonders declared `per_1000_km2: 0.0` beside `max_count: 1`. That pair reads as "at most one of
these in a world" and means "none, in any world, ever", because the expected count is the rate
times the land area and zero times any area is zero at every raster and every seed. They
reported `wanted: 0` against 15 to 78 qualifying cells on every world ever generated, and the
absence was invisible because a missing archetype looks exactly like an unlucky one. Note that
this is *not* the rounding trap above — that one was already fixed and the draw was working
correctly; the number it was handed was the zero. Wonders now declare `0.15`, which against
the roughly 2,500 km² of land this planet carries at size 17 and 4,300 km² at size 257 is an
expectation near 0.4: each wonder appears in something under half of worlds, a typical world
carries one or two of the five, and `max_count` stops a large continent growing a second of
the same one. `catalogue.lint` now refuses a scattered archetype with a non-positive rate, so
it cannot return through a catalogue edit.

**Spacing is a property of the world, not of the raster.** `spacing_cells` resolves against
a fixed reference raster, never the raster in hand. Tied to the actual raster, "two cells
apart" would mean 25 km at size 17 and 6 km at size 129 — the same world spacing its caves
differently depending only on how finely it was sampled.

**At coarse rasters the node grid binds before density does.** No two locations share a node,
so a size-17 world with 47 land cells cannot hold the ~196 locations its area implies, however
generous the catalogue. It is worse than the bare cell count suggests: **16 of those 47 land
cells already carry a ruin, nest or religion site before key locations are placed at all**, so
thirty-one are free, and every placement takes one more. Count that *intersection*, never the
length of the claim list: the same world claims 94 nodes in all, and 78 of them are water, pole
or seam nodes — mostly sea nests — which never enter a `domain: land` archetype's candidate list.
An earlier revision of this page said 30 from the bare length and the number was wrong in both
directions at once. That is honest rather than hidden — the per-archetype diagnostics name the
count, as *"no room: 16 of 24 qualifying cells already carry another feature"* — but it means
size 17 is the sparse end of the range and **size 33 or finer is representative**.

**A coarse raster also fails to resolve a tail, and that is not a reason to lower a floor.**
`geyser_basin` requires `volcanic >= 0.05`. On seed 42 the land maximum is 0.0286 at size 17 and
0.1524 from size 33 up, so the archetype has **no qualifying ground at all** at 17, **8 qualifying
cells** at 33 and **20** at 65. It places none at 33 — six of those eight already carry another
feature and spacing refused the other two, which the diagnostic says in those words — and three at
65. Ground and room are two different limits and a placement count alone cannot tell them apart:
the raster fixes the first and only enlarges the second. The percentile half of that gate
resolves to about 0.0018 at every size, two orders of magnitude below the floor, so the floor is
the whole gate and it is doing its job. Lowering it to 0.0286 to rescue size 17 would take geyser
ground on a size-257 world from 1.5% of land to 3.4% and still admit exactly one cell at 17.
**The answer to an unresolved tail is a finer raster, not a looser threshold**, because the raster
is per-run and the threshold is permanent.

Seed 42 on a 200 km world at phase 16, counting only the scattered locations and not the chained
waystone runs: **22 at size 17, 100 at size 33 and 287 at size 65** — 13, 25 and 26 of them tier
2, and 2 tier-3 wonders at every raster. Totals including chains and clusters are 111, 255 and
491. These counts move
with the terrain the world grows underneath them — the river-threshold scaling fix alone moved
every size-17 figure on this page — so treat them as a reading rather than a contract; the
invariant is the ratio, not the number. **And they are a reading of a specific world.** The lab's
bare default is not it: `default_config(3)` leaves `globe_radius` at 10000, which resolves to the
legacy 11.15 km planet with about 6 km² of land and 39 land cells at size 17, while the 200 km
`world_size: small` preset these numbers come from is resolved by `generate_request`. Two analyses
of "seed 42 at size 17" that disagree about the land-cell count are usually looking at those two
different worlds.

Tier 0 was empty at every raster before the composition pass, because markers were placed last
and lost every remaining cell to the larger tiers. That was the symptom of a design error
rather than a density one: a waystone belongs on a road at metre intervals, not scattered one
per cell. Chains fixed it rather than reweighting did.

### Ground already spoken for

Key locations **dedupe by node** against `ruins`, `beast_nests.sites`, `religion.sites`,
`magic.colleges` and `regions.landmarks`, and keep a settlement clearance from cities,
hamlets, fortresses and ports. Nothing here re-places an idea another module owns, and no
two key locations share a node.

## Succession — where dungeons come from

```
mine     → abandoned → goblin warren
temple   → ruined    → cult site / bandit camp
fortress → ruined    → lair / squatters
barrow   → sealed    → breached → undead
village  → drowned   → wreck-dive site
```

Applied only to sites already in an untended state and only once an age has passed. The
change is **recorded** on the site rather than silently overwriting the occupant, because "a
goblin warren that used to be a silver mine" is a better location than either half:

```json
"succession": {"from_occupant": "none", "to_occupant": "monsters",
               "note": "Worked out, propped up, and then taken by whatever found the entrance."}
```

## Chains and clusters

Some locations are simply wrong placed independently, and no per-cell suitability field can
fix that — a field has no way to say *and then another one, two kilometres on*.

**Chains** are ordered runs along something the world already has:

| Chain | Runs along | Interval |
|---|---|---|
| Waystone line | each road | 2.2 km |
| March stones | a political frontier | 3.4 km |
| Beacon line | each road, constrained by mutual line of sight | 9 km |
| Pilgrim stations | the approach to the three best sacred complexes | 2.6 km |

Members carry `links.chain` and `links.chain_index`, and `chains[].members` is in walk order,
so a consumer can read a chain as a spine rather than a bag. They are **named by their place
in the run** — "the first stone on the Alder road", "the second", "the third". A run of eleven
stones all called "the grey stone" is a scatter wearing a chain's clothes.

The beacon line is a real sightline check, not decoration: each tower is accepted only if
nothing between it and the previous one stands above the line joining them, sampled on the
heightfield. Where the next interval fails, it steps forward and tries again. The curve of the
world is ignored, which at these distances is far below what the sampling already rounds away.

**Clusters** hang off an anchor that has already been placed — a siege camp outside a *ruined*
fort, cottages beside a mine, barrows ringing a necropolis, hermit cells around a monastery.
Members carry `links.cluster` and `links.anchor`.

### Chain and cluster members are not node-snapped

This is the one place the one-location-per-node rule does not hold, and it has to be. A
waystone every 2.2 km on a raster whose cells are 12 km apart cannot be node-snapped without
collapsing five of them onto one point; a siege camp 1.5 km from a wall has no cell that
satisfies it at all. So composed members stand at interpolated positions, carry a real
`direction`, and use their nearest node only to read the layers beneath them.

Every site therefore declares `placement`: `node`, `path` or `cluster`. **Only `node` sites are
unique per node.** A consumer that needs the old guarantee should filter on it.

### One kind of place, one route onto the map

An archetype that a chain or cluster places must set `placement` accordingly, or the catalogue
refuses to load. Otherwise a waystone would arrive twice — strung along its road *and* dropped
on whichever cell scored best — by two passes that know nothing about each other.

The exception is declared rather than assumed: `barrow` sets `also_scatters`, because a barrow
genuinely does both. It stands alone on a ridge and it also rings a necropolis. The lint makes
that a decision instead of an accident.

Intervals and offsets are **absolute metres**, deliberately unscaled. How far apart people set
waystones, and how far from a wall an army digs in, are facts about people rather than about
the size of the world; a larger world gets more of them, not longer gaps between them.

## Interiors

Tier-2 sites carry an interior. It is a **graph, not geometry**: chambers with a depth, a
role, a rough size and connections, plus entrances. There are no metre positions, no
contents and no encounters. Five plans — `linear`, `branching`, `radial`, `warren`, `vault`
— differ in how chambers attach, and `state` decides how much is flooded or fallen in.

A metre-accurate interior layout is a later phase, the way `city_planner` sits on top of
settlements. Saying so in `limits` is the difference between an honest stub and a misleading
integration claim.

## Names

Unique within a world. A duplicate name makes two places indistinguishable to anything that
refers to them by name, and templates collide constantly — three silver mines near one city
all want to be "the deeps under Bracken". Templates are tried first, then an adjective
qualifier, then a position word.

Place naming across the rest of the tree is a known gap
(`terrain_settlements.py:842` is `['Alder', 'Bracken', …][k % 12] + ' City'`, not culture
aware, not seeded). Key locations use the descriptor idiom `hero_generator` already uses for
sites rather than trying to fix that here; a culture-aware place-name generator deserves its
own ticket.

## Exterior plans

Every location also gets an **exterior plan**: what stands on the ground, in the same plot
shape `city_plans`, `hamlet_plans` and `castle_plans` already use, so an importer that reads
those reads these without a second code path. Top-level `key_location_plans`, joined to a
location by `location_id`.

A marker tells an engine *where* a place is and nothing about what standing there looks like.
Every location rendering as a single prop is what makes a generated world read as a map rather
than as a place.

```json
{"location_id": "keyloc-silver_mine-2918", "kit_id": "mine_head", "arrangement": "terrace",
 "origin": {"direction": [...], "height_m": 30.7, "node": 2918},
 "bounds_m": {"width": 54.0, "depth": 54.0}, "slope_bearing_degrees": 355.69,
 "plots": [{"building_id": "keyloc.part.headframe", "x_m": 0.0, "z_m": 0.0,
            "rotation_degrees": 180.0, "ground_elevation_m": 489.63,
            "foundation_bottom_m": 489.56, "plot_m": {...}, "dimensions_m": {...}}]}
```

Plots are in a **local metre frame**: place the frame at the location's direction and height,
then lay the plots out in it. `building_id` is named that, rather than `part_id`, for the same
reason — the field an importer already looks for.

### Arrangement is what makes a place look like itself

Seven rules, chosen per archetype in the catalogue rather than in code:

| Rule | Shape | Used by |
|---|---|---|
| `single` | one part at the centre | waystones, barrows, towers, colossi |
| `ring` | evenly spaced on a radius, lightly jittered | stone circles, ley nexuses, crater rims |
| `scatter` | golden-angle spiral, so low counts never clump | barrow fields, camps, wrecks, rubble |
| `row` | along an axis | dykes, aqueducts, peat cuttings, ford markers |
| `courtyard` | perimeter facing inward | monasteries, forts, caravanserais |
| `terrace` | stepped along the fall of the ground | mine heads, quarries, hillside sanctuaries |
| `mouth` | an opening with its approach fanned in front | caves, lairs, adits |

A stone circle whose stones are not on a circle is a scatter with a nicer name, so the ring
rule is asserted by test. Terraced and mouth arrangements orient against
`slope_bearing_degrees`, the downhill direction in the local frame — working sites follow the
fall of the ground rather than a grid.

### Kits and parts

A kit resolves **per archetype, falling back to its family**, so all ninety-seven have one and
adding an archetype can never leave a location unbuildable. Parts are shared, so a rubble pile
is one asset identity wherever it appears.

- **opening** (3): Adit mouth, Cave mouth, Ice mouth
- **path** (1): Ore track
- **structure** (46): Altar stone, Bridge span, Broch shell, Cairn, Caravan range, Chapel, Cloister range, Coffin ledge, Colossal figure, Crannog platform …
- **terrain** (25): Barrow mound, Bone midden, Boulder, Campfire, Charcoal hearth, Chasm edge, Crater rim, Crystal spur, Cut circle, Dyke bank …

75 parts, 91 archetype kits, 11 family kits.

### Weathering

State is not only a string beside identical geometry. A `ruined` or `buried` site gains rubble
in proportion to how far gone it is, and `reclaimed` ground gets mounded over instead — so the
same fort reads differently held and abandoned.

### Ground shaping

A barrow is a mound. A quarry is a hole. A crater has a rim with a bowl inside it. Parts that
move the ground carry a `shaping` spec, and each plan reports what it does to the terrain:

```json
"terrain": {
  "bounds_m": [-14.0, -14.0, 14.0, 14.0],
  "relief_m": {"raised_m": 3.6, "lowered_m": 0.0},
  "shaping": [{"shape": "mound", "x_m": 0.0, "z_m": 0.0, "radius_m": 7.5,
               "height_m": 3.6, "part": "keyloc.part.barrow_mound"}],
  "surface": {"size": 17, "step_m": 1.75, "heights_m": [[...]]}
}
```

Seven primitives: `mound`, `cut`, `rim` (a raised ring with a bowl inside — a crater is not a
mound with a hole punched in it), `platform`, `bank`, `trench`, and `level`, which flattens
ground toward the height at the feature's centre and is applied before the additive ones.

**It is emitted twice over, on purpose.** `shaping` holds parametric primitives, which are
exact; `surface` is a sampled grid in the same shape `castle_plans` emits. An engine with a
real landscape should apply the primitives at its own fidelity — a grid at a couple of metres
a post cannot describe a barrow. The grid is there for a consumer that only reads grids. Where
they disagree the primitives are right and the grid is merely coarse.

`relief_m` reports how far the ground actually moves, so a consumer can skip locations that
leave it alone. Most do: about 137 of 324 plans on a fixture world shape anything at all, and
a waystone shapes nothing and says so with both figures at zero.

**Plots are seated on the shaped ground, not the raw layer.** This is the whole point of the
two-pass plan: positions and shaping are collected first, then every plot's corners are sampled
through the finished deformation. A grave marker standing on a barrow stands *on* the barrow.

### What exterior plans are not

Schematic footprints, not measured art: the metres are sized for legibility and every part is
a placeholder identity. **Base ground elevation is bilinear over the `height` layer**, because
the generator's own continuous height field is not importable from a reader package — at plot
scale on a multi-kilometre raster that is below one cell, so the *underlying* terrain reads as
near-flat and only the shaping gives a plan local relief. A consumer should conform plots to
its own landscape and then apply the shaping primitives on top, rather than treating these
heights as a description of real ground.

## Influences, for asset prep

Everything an art pipeline needs to decide how a location *looks* is on the record. These are
closed sets — a prep pass can enumerate them and know it has covered the space.

### On every site

| Field | Values | What it drives |
|---|---|---|
| `family` | 11 — arcane, curiosity, drowned, extractive, fortification, funerary, lair, sacred, subterranean, wayside, wonder | the broad kit |
| `kind` | 97 archetypes | the specific thing |
| `tier` | 0–3 | scale and whether it has an inside at all |
| `state` | 11 — natural, active, occupied, abandoned, ruined, buried, drowned, sealed, corrupted, reclaimed, restored | condition: intact, fallen, flooded, sealed, overgrown |
| `occupant` | 10 — none, builders, descendants, squatters, monsters, cult, undead, beasts, fae, nature | signs of habitation, and by what |
| `threat` | 1–5 | how hostile it should read |
| `origin.civilization_id` | 12 | **built style.** `architecture_style_id` on a culture is the same value, so this is the whole handle |
| `origin.school` | 12 magic schools | magical dressing where the ground is charged |
| `origin.ages_since` | integer | how much weathering |
| `environment.natural_biome` | 13, with name | **ground set:** tundra, desert, forest, rainforest, marsh, exposed rock, snow, ice … |
| `environment.biome_variant` | 0–155, or null | magically mutated ground, with `variant_asset_id` naming the mutation |
| `environment.temperature_c` / `moisture` / `slope` / `coastal` | numeric | climate and siting dressing |
| `placement` | node / path / cluster | whether it stands alone, in a run, or beside an anchor |
| `links.chain` / `chain_index` / `cluster` / `anchor` | ids | what it belongs to |

The two that matter most and are easy to miss: **`natural_biome` decides the ground set** — the
same karst cave is a different art set in tundra and in rainforest — and **`biome_variant`
overrides it** where the ground is magically mutated, naming the mutation directly.

### Interiors — 24 tier-2 archetypes

Interiors are chamber graphs, not layouts. Chamber roles are the vocabulary a builder gets:

| Family | Chamber roles |
|---|---|
| arcane | workroom, binding floor, library, observation cell, ward ring, sink |
| curiosity | entry room, main room, back room, store, stair |
| drowned | flooded hall, air pocket, silted room, collapsed stair, anchorage |
| extractive | gallery, stope, winze, pump house, spoil chamber, tool store |
| fortification | gatehouse, guardroom, barracks, cistern, undercroft, armoury |
| funerary | antechamber, burial cell, ossuary, offering niche, sealing stone, grave shaft |
| lair | approach, nest floor, bone midden, hoard, bolt hole, roost |
| sacred | narthex, nave, crypt, cell, reliquary, cloister walk |
| subterranean | gallery, sump, squeeze, chimney, grotto, rubble fall |
| wayside | yard, common room, stable, cellar |
| wonder | approach, inner space, hollow, vantage |
| *(fallback)* | chamber, passage, side room, stair |

Plans: linear, branching, radial, warren, vault. Entrance kinds: breach, door, mouth, sealed door, shaft,
plus `collapse` for a breached second way in. Every chamber also carries `depth`, `size_m`,
`connects`, `flooded` and `collapsed`; every entrance carries `hidden`.

| Archetype | Family | Plan | Levels | Chambers |
|---|---|---|---|---|
| `academy_ruin` | arcane | radial | 2–4 | 12–28 |
| `binding_site` | arcane | vault | 1–3 | 5–13 |
| `wizard_tower` | arcane | linear | 3–6 | 7–16 |
| `library_ruin` | curiosity | radial | 1–3 | 8–20 |
| `observatory` | curiosity | linear | 2–4 | 5–12 |
| `gem_mine` | extractive | branching | 2–4 | 7–18 |
| `iron_mine` | extractive | branching | 2–4 | 8–22 |
| `salt_mine` | extractive | vault | 2–3 | 8–20 |
| `silver_mine` | extractive | branching | 2–5 | 10–26 |
| `border_fort` | fortification | radial | 1–3 | 8–20 |
| `barrow_field` | funerary | vault | 1–2 | 6–16 |
| `mausoleum` | funerary | vault | 1–3 | 7–18 |
| `necropolis` | funerary | warren | 2–4 | 14–34 |
| `dragon_lair` | lair | linear | 1–2 | 4–9 |
| `giants_hall` | lair | linear | 1–2 | 4–10 |
| `drowned_temple` | sacred | radial | 1–2 | 6–16 |
| `monastery` | sacred | radial | 1–2 | 10–24 |
| `mountain_sanctuary` | sacred | linear | 1–3 | 6–15 |
| `oracle_cave` | sacred | linear | 1–2 | 4–10 |
| `crystal_cavern` | subterranean | vault | 1–2 | 4–10 |
| `glacier_cave` | subterranean | linear | 1–2 | 4–11 |
| `karst_cave` | subterranean | warren | 1–3 | 6–18 |
| `lava_tube` | subterranean | linear | 1–2 | 5–12 |
| `caravanserai` | wayside | radial | 1–2 | 8–18 |

## Where it runs

A standalone package that reads the finished world JSON and **mutates nothing**, exactly as
`hero_generator` and `story_web` do. `attach(world)` is called at stage 16 and again in
`advance_age_request`; `FANTASY_WORLD_KEY_LOCATIONS=0` leaves the key absent.

This is not a seventeenth stage, and that is deliberate. A new stage would touch three
provenance-pinned files, bump the generation algorithm past 16, and — running inside the
seeded pipeline — oblige a `Core/` port in the same change. As a reader package, seed 42
produces byte-identical `layers`, `settlements`, `ruins` and `history` with the block present
or absent, and `tests/test_native_world.py` stays green unchanged. **There is no native port**:
a client doing in-process native generation will not have this block, and would need either
the Python export or a port funded as its own ticket.

Determinism: every draw is `child_seed(world seed, 'keyloc-…')`. The package carries its own
copy of that helper and of the sphere-grid geometry, because it never imports `icarus_sim`;
both are pinned against the originals by test, so a change on either side fails loudly
instead of silently forking the replay contract.

## Output

`world['key_locations']`, schema `Contracts/schemas/key-locations.schema.json`.

```json
{"id": "keyloc-silver_mine-2918", "kind": "silver_mine", "name": "the deeps under Bracken",
 "family": "extractive", "tier": 2, "threat": 5, "state": "abandoned", "occupant": "monsters",
 "node": 2918, "x": 37, "z": 46, "direction": [...], "height_m": 30.7,
 "origin": {"age": 0, "culture_id": "gnome-e5327ce7", "ruin_id": "ruin-…", "school": "umbral", "ages_since": 2},
 "succession": {"from_occupant": "none", "to_occupant": "monsters", "note": "…"},
 "interior": {"plan": "branching", "levels": 3, "chambers": [...], "entrances": [...]},
 "asset_id": "marker.key_location.silver_mine", "reason": "A rich seam worked from above until the good rock ran out."}
```

`id` is a pure function of (archetype, node, founding age), never an ordinal, so a consumer
can hold a foreign key across an age advance. Stable is not immortal: if an age transition
drowns a location or destroys the culture that justified it, the location legitimately ceases
to exist. Treat a dangling key as *the place is gone*, not as renumbering.

Every archetype appears in `sites` or in `diagnostics` with a reason, so a world that grew
none of something says why.

## Limits

Static proposals about ground, not a populated world. Nothing here acts, spawns, patrols,
guards or holds treasure. Interiors are graphs.

Chains follow roads, frontiers and shrine approaches. They do not yet follow rivers or coasts,
and a pilgrim approach is the straight run in from the nearest city rather than a routed road,
because no road necessarily goes there. Clusters hang off four anchor kinds. Beacon sightlines
ignore the curve of the world.

Names are descriptor templates. When heritage's language layer lands, `settlement_name` becomes
the right source for the proper nouns these templates already borrow — a key location named
"the deeps under Bracken" improves for free the moment Bracken has a real name.
