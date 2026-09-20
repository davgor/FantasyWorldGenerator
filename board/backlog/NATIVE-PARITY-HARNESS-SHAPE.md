# NATIVE-PARITY-HARNESS-SHAPE — the native suite compared two different worlds

Owner: none. State: **harness fixed in the working tree; residual port gaps carded below.**
Found and fixed by the bug-hunt session holding the verification baton.

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

## What remains red, and it is genuine port lag

With the harness fixed, the terrain comparison collapses to a single layer. The residual is
concentrated and diagnosable:

- `test_native_world_reproduces_the_reference_world_for_one_seed` — **`lunar_sensitivity` only.**
- `test_stage_nine_magic_and_environment_match_the_reference` — `instability_*` failing and
  `zone_*` erroring. This is the **hidden-schools** work: Python's `SCHOOLS` is twelve (eight known
  plus four hidden), `Core/magic.cpp` `school_names()` is eight. `Core/settlements.cpp:217` already
  carries a comment about hidden-school indices arriving from a corrupted world, so the boundary
  was known and the layer set was not carried across.
- `test_city_layout_plans_match_the_reference`,
  `test_hinterlands_ports_and_nests_match_the_reference`,
  `test_per_people_fields_budget_and_founded_cities_match_the_reference` — settlement-level.

Measured after the fix: **five failing tests, fifteen failing subtests**, and the implicated
layers are a closed set —

```
dominant_magic   instability_{air,earth,fire,infernal,radiant}
lunar_sensitivity
zone_{demonic,draconic,enchanted,haunted_sands,witch_huts}
```

Every one of those is magic, except `lunar_sensitivity`. Nothing in terrain, hydrology, climate,
tectonics or the shared surface function fails any more.

These are Python moving away from a static C++ side over days, exactly as suspected — but they are
two identifiable subsystems plus a settlement tail, not ninety independent divergences, and the
terrain foundation underneath them is provably sound.

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
