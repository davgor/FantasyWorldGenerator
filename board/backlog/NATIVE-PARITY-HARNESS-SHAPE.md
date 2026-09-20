# NATIVE-PARITY-HARNESS-SHAPE — the native suite compared two different worlds

Owner: none. State: **harness fixed; the ley-width root cause fixed and measured; a short,
classified residual carded below.** Found and fixed by the bug-hunt session holding the
verification baton; re-measured and the magic diagnosis corrected by the native-parity lane,
2026-09-20.

## What was believed

That the native suite was "red at baseline" with roughly ninety genuine behavioural failures —
reported independently by two sessions, neither able to verify it, and read by a third as
"code-red, not environment-red" on the strength of the failure pattern having passes interspersed.

Two theories were in play: a toolchain switch to MinGW (tested and refuted), and the documented
one-ulp `pow()` divergence between the static CRT and `ucrtbase.dll`, which
`tests/native_cxx.py:51-57` warns drifts terrain heights through `perlin3`.

## What is actually true

**The native core is bit-exact with the Python reference.** Given the same world shape, every
compared layer matched to the last bit — 289/289 cells, `maxdiff` exactly `0`, including `base`,
`height`, `continental`, `structure`, `surface`, `tpi`, `boundary_distance`, `temperature` and
`moisture`.

The suite was **comparing two different worlds**. It generates its oracle through
`generate_request(recipe_version=3)`, which resolves a world *shape*; it then ran the native
driver with no overrides at all, so the native side built from `Core/config.hpp`'s raw authoring
constants. At seed 42:

| parameter | Python recipe 3 (design space) | `Core/config.hpp` | ratio |
|---|---|---|---|
| `globe_radius` | 179388.90337493608 | 10000. | **17.94x** |
| `tectonic_relief` | 9394.65957250707 | 800. | 11.74x |
| `amplitude` | 12917.65691219722 | 1100. | 11.74x |
| `wavelength` | 82856.1853225209 | 4300. | 19.27x |
| `settlement_spacing` | 8072.500651872125 | 450. | 17.94x |
| `support_reach` | 17938.89033749361 | 1000. | 17.94x |
| `world_scale` | 0.17744123532462844 | 0.17744123532462844 | **1.00** |

## The evidence that should have been read first

The failure pattern was never uniform, and the shape of the non-uniformity was the answer:

- **Bit-identical, zero difference:** `noise`, `plates`, `crust`, `convergence`, `divergence`,
  `shear`, `archipelago_relief`.
- **Wildly divergent:** every layer carrying metres — `base` off by 3845 m at size 17.

`noise` is the `perlin3` output. It was **exact**, which refutes the `pow()`/ulp theory outright:
a compiler-level numeric difference cannot leave the noise field bit-identical and move the height
field by kilometres. Dimensionless layers matched and metric layers did not, which is the
signature of a scale mismatch and of nothing else. `volcanic` was the only layer showing genuine
float noise, at `4.16e-17` — tolerance-level, and the real shape of an ulp difference for
comparison.

`boundary_distance` diverged by a factor of 17.94 — the design-radius ratio exactly.

## The fix

`tests/test_native_world.py` only. **Nothing in `Core/` or `Sim/` moved.**

`native()` now appends the oracle's own resolved shape as `set:` overrides — the driver's existing
override channel — for the eight operations that build a world from a seed and a size. One place,
so the reason is stated once rather than at fourteen call sites.

Five parameters are deliberately **not** passed, checked rather than assumed: `ley_width` (180),
`ley_nodes` (10), `magic_instability` (.45), `rain_passes` (48) and `wind_bearing` (90) are
resolved by recipe 3 to exactly the values `Core/config.hpp` already holds, and
`override_bounds()` does not name them.

## Three defects this exposed, none of them fixed here

1. **`set:world_scale=` aborts the driver** with `0xC0000409` (fail-fast). Every other override in
   the table is accepted. `world_scale` has its own `scale=` argument and a separate
   `decimal_scale` path through the JSON request, so the `set:` channel silently accepts a name it
   cannot handle and then dies. Bisected one override at a time to isolate it.

2. **`support_reach` cannot be expressed through Core's own contract.** Recipe 3 resolves
   17938.89 at this seed; `Core/genesis.cpp` `override_bounds()` caps it at **10000**. Reaches are
   absolute metres authored for the 11.15 km reference world and must grow with the world, so any
   world wider than roughly 6x reference resolves a `support_reach` the native JSON API rejects.
   The driver's `set:` channel does not consult the bounds, which is why the tests can now pass it
   — that inconsistency is itself the second half of this defect.

3. **`Core/genesis.cpp` `world_shape_overrides` omits `wavelength`.** Stated outright in
   `Sim/icarus_sim/terrain_scale.py:8-10`: *"What is added here is the piece `world_shape_overrides`
   omits -- `wavelength` -- without which surface detail silently vanishes as the world grows."*
   So even a caller using Core's own shaping helper gets a world whose surface noise does not scale.

## What remains red — RE-MEASURED 2026-09-20, and the old diagnosis below was wrong

### The hidden-schools diagnosis is struck

The section this replaces said the magic family was **hidden-schools** work, on the grounds that
Python's `SCHOOLS` is twelve and `Core/magic.cpp` `school_names()` is eight. **That is wrong and is
withdrawn.** The ley networks are eight on both sides: `blood`, `void`, `rot` and `eldritch` are
declared with `occurrence` `0.0` and generation never raises them, `terrain_ecology.NETWORKS` is the
eight known schools, and an eight-school Core now matches the reference bit for bit on every
stage-nine layer. The school count was never the divergence, and reasoning about the count instead
of measuring it is how that account survived two sessions — the same failure this card's own handoff
already names.

### The actual root cause was one line, and it is fixed

`Core/magic.cpp` assigned the authored school width straight through. The reference scales it by the
world's own circumference (`Sim/icarus_sim/terrain_leyline_history.py:101` computes
`width_scale = result['effective_config']['globe_radius']/REFERENCE_RADIUS_M`), so at seed 42 the
reference resolves 1973.28 m where Core held a flat 110 m — a 110 m Gaussian against a
kilometres-wide raster cell, which is why every ley field, instability field and categorical zone
collapsed at once rather than drifting.

Proved by controlled rebuild, twice, at two rasters: at size 33 the stock binary showed up to
0.739894 absolute error and 1089 of 1089 mismatched cells on `magic_density`; at size 17 a second
agent independently measured 28 of 55 stage-nine blocks mismatched. Patched, both runs report
**0 of 55 blocks mismatched, worst difference 0** on every cell, magic and non-magic alike. The
reference radius must stay the decimal literal `1774.4123532462844`: `10000.*0.17744123532462844` is
one ulp lower and the categorical layers are compared exactly.

Two harness gaps landed with it: `cityplans` was never passed `residents=1`, so Core planned cities
with no population, and `culture_link_cost` — the third of the three keys
`Sim/icarus_sim/terrain_world.py:263-264` reach-scales, beside `settlement_spacing` and
`support_reach` — was neither in `SHAPE_KEYS` nor accepted by Core's override chain, so the culture
union-find regrouped and every culture id hashed differently.

### And one of the eight ERRORs was never a root cause at all

Every one was `RecursionError` inside `difflib._fancy_replace`, raised while unittest rendered the
diff for a 1089-element `assertEqual`. Measured standalone on this interpreter rather than inferred:
two 1089-element float lists take about **seven minutes** to reach a 1000-frame `RecursionError`
through `difflib._fancy_helper`. So the assertion found a real divergence, spent minutes on it, and
then crashed explaining it — the layer name gone, the mismatch count gone, and a difflib stack trace
printed under the heading ERROR. It was read as a distinct failure family needing its own
investigation and cost a review cycle. `tests/test_native_world.py` now routes all four whole-layer
comparisons through `assertCellsIdentical`, which compares with exactly the predicate `assertEqual`
uses and reports the count and the first six differing cells. The suite's own wall clock halved,
from 653 s to 344 s, because that rendering was a measurable share of the run.

`tests/test_native_world.py` also gained `test_resolved_ley_networks_match_the_reference` and
`Core/tests/world_driver.cpp` a `networks` operation, so the width is now pinned as one number
instead of being inferred from fifty-five grids.

### Measured residual

`python -m unittest -v tests.test_native_world`, one process, whole module. The **68 failures and
6 errors** baseline was measured by the investigating session on the tree before any of this
landed, and is quoted rather than re-run, because the tree has moved underneath it since. Measured
here, in two runs of the whole module: **14 tests, 13 failures, 1 error** after the three fixes and
the first harness pass, then **15 tests, 19 failures, 0 errors** after the remaining defects below
were fixed and a new regression test added. Wall clock fell from 653 s to 278 s, because rendering
those diffs was a measurable share of the run.

The count went up because the second run caught a defect in the regression test added in that same
run: `test_resolved_ley_networks_match_the_reference` compared a freshly generated network's node
count against the oracle's, and the oracle is a *finished* world whose age transitions have appended
a key point per ruin — six schools, `8 != 26` and so on. The three resolved parameters it exists to
pin, `width_m`, `strength` and `instability`, passed for all eight schools. The node-count assertion
is removed with the reason recorded beside it, and the corrected test is green. **So the honest
standing figure is 13 failures and 0 errors**, of which two are the peer contamination below —
eleven parity failures, projected by subtraction from a measured 19 rather than measured directly,
because the third whole-module run was not affordable in this session.

Those two are not parity defects at all: `test_asset_registry_binds_every_catalogue_identity`
and `test_native_registry_loader_resolves_and_diagnoses` fail on `asset_list_sha256`, because a peer
lane edited `Sim/fantasy_world_generator/asset_list.py` after
`Contracts/catalogues/unreal-asset-registry-v1.json` was last generated. Regenerating the registry
closes both; no C++ is implicated.

### Two of the residuals turned out to be defects, and both are fixed

**`protected_route_node`, `390` against `454`, with `defence_score` matching to the last bit.** The
reference's `route_neighbors` is a dict, so it iterates in insertion order; `Core/humans.cpp` held a
`std::map`, which iterates in ascending key order. `strategic` keeps the first node to reach a value
with a strict `>`, so wherever two route nodes tie on defence value the two sides recorded different
ones — the same fortress on the same ground, watching a different road. Core now keeps a
`route_order` vector beside the map and walks that, appending in the reference's own
`setdefault(i)`-then-`setdefault(j)` order. The failure is gone.

**A fifth large-list `assertEqual`**, in the finished-world comparison, which was the whole of the
remaining ERROR. Converted, and it immediately paid: what it had been hiding is
**`dominant_magic`, 33 of 1089 cells, native `-1` where the reference names a school** — the first
cells being 331, 369, 397, 402, 423 and 424. `-1` is "no school leads by the required margin", so
natively the potency is flatter. `biome` in the same finished world is exact. This is now a named,
countable, cell-addressed failure instead of a difflib stack trace, and it is the most diagnosable
thing left; the hypothesis to test first is that `Core/ages.cpp` appends fewer ley key points than
the reference does, since the reference's finished `weave` network carries 26 nodes against the 8 it
was generated with.

### And one classification was simply wrong

The plan this lane inherited described six of the hamlet failures as `access_cost` differing by one
to three ulp. **`access_cost` is exact at every hamlet.** The driver now emits each hamlet's access
path and the suite compares it, and every path matches too — which matters, because `access_cost` is
a Dijkstra total whose additions run strictly along the settled path, so an identical path forces an
identical double. The failing fields, now named in the assertion messages rather than guessed at,
are **five `delivered_food`** (hamlets 8, 23, 28, 49 and 73 — `119.4796596384166` against `...59`)
and **three `irrigation_benefit`** (hamlets 17, 48 and 56 — `2.5324759650446893e-12` against
`2.5324763987255583e-12`). Eight hamlets, not six, and not the field the plan named.

That reads as one defect, not two. `irrigation_benefit` is `food[i]-natural[i]`, a single
subtraction of two nearly equal numbers, so a last-bit difference in either operand becomes a 1.7e-7
relative difference in a 1e-12 result — the large relative gaps are cancellation, not a separate
divergence. `delivered_food` accumulates `100*area*food[i]*delivery*...` over a hamlet's cells with
plain `+=` on both sides, and `delivery` is exact because `access_cost` is. So both families point
at a last-ulp difference in `food[i]`, compared with no tolerance at all after being accumulated or
differenced. **Classification: (d) float, in a continuous input the parity contract does give a
tolerance to, surfaced through fields compared exactly.** Not established: which term of
`farming_potential` or `biome_food_multiplier` carries it.

### What is still red, and what kind of thing each one is

- **Five `delivered_food` and three `irrigation_benefit`** — (d) float, as above. Paths and
  `access_cost` proven identical.
- **One `dominant_magic`**, 33 of 1089 cells in the finished world only — (a) a real divergence,
  bounded to the age transitions because stage nine is exact.
- **One `lunar_sensitivity`**, 0.00273 against a 1.0005e-06 tolerance, in the finished world only —
  (a) a real divergence, and very likely the same one: `Core/astrology.cpp` restates
  `Sim/icarus_sim/terrain_astrology.py:254` term for term and sums the same eight instability
  layers, so if the aged networks differ, both layers differ together.
- **One war `pressure`**, `0.8019473845702728` against `...73` — (d) float, about one ulp.

Nothing in terrain, hydrology, climate, tectonics, magic at stage nine, city layout, per-people
fields, founded cities, roads, fortresses, ports or nest placement fails any more.
`Core/nests.cpp`'s new `danger_ramp` port, written by an agent that could not compile it, compiles
clean under `/W3 /WX`, matches `Sim/icarus_sim/terrain_nests.py:139-167` term for term, reads the
same effective radius, and places every nest bit-identically.

`Core/profiles.cpp`'s new `require(profile.creature_class!="monster" || !profile.biome_weights.empty())`
was confirmed by loading rather than by reading: the regenerated catalogue holds 680 nest profiles,
369 of them monsters and all 369 carrying `biome_weights`, so the guard is live rather than vacuous,
and the three new string keys `likeness`, `likeness_traits` and `likeness_secondary` are ignored by
the named-`field()` nest loader rather than throwing.

## Dependencies and unresolved decisions

- **Open, and it is a product question rather than a test question:** should a bare native call
  with no overrides produce the same world as a bare Python call? Today it does not, and the
  native core is the Unreal generate API. The harness now compensates; a consumer would not.
  Either `Core/config.hpp`'s defaults should resolve recipe 3's shape, or the API should require a
  shape and refuse to invent one. **The harness fix does not answer this and must not be read as
  answering it.**
- The user has said the native port is being redone for the Unreal import. Everything above should
  be weighed against that before anyone invests in porting hidden schools into the current core.

## Acceptance and evidence

Measured directly rather than inferred, with the driver built once and reused:

- Native driven with the oracle's shape at seed 42 size 17: `base`, `continental`, `height`,
  `structure`, `surface`, `boundary_distance`, `noise`, `plates`, `tpi`, `temperature`, `moisture`
  all **289/289 exact, maxdiff 0**.
- `Core/legacy.cpp` compiles clean in isolation, so the `villain_school` change is not implicated.
- The full 42-unit driver builds successfully; the `'vswhere.exe' is not recognized` line is
  benign noise from `vcvars64.bat`, which calls `vswhere` by bare name with the Installer
  directory off PATH. `INCLUDE`, `LIB` and `VSCMD_VER` all resolve correctly afterwards.

## Adversarial review and limitations

The convergence proof was run at **size 17**, not the suite's parity size of 33, because the
question was what *kind* of difference this is. The suite runs at 33 and the terrain layers there
now agree except `lunar_sensitivity`, which corroborates it at the parity size.

This card claims the core's terrain generation is correct. It does **not** claim the core is
correct: the magic and settlement residuals are real and unexplained by anything here.

And the harness fix makes a test pass by giving the code under test more information than it had.
That is legitimate here — the suite's stated job is comparing two implementations of the same
world, and it was not doing that — but it is exactly the move that hides a defect when the
information should have come from the implementation itself. Hence the open question above, which
is the part a reviewer should push on.

## Handoff

Found while holding the verification baton, after three sessions had characterised this suite
without measuring it. The general lesson is cheap to state: the pattern of *which* tests fail
carried the diagnosis, and every session including this one initially reasoned about the count
instead.
