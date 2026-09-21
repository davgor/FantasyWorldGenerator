# ML-03f — Finish the building transposition and make the plugin a carryable artifact

> **RETIRED 2026-09-21 by owner ruling. Not done, and not to be worked as written.**
> The native `Core/` port is deferred wholesale to the end of the project and will be a full
> rewrite against functionality that does not exist yet, so this card describes porting,
> mirroring or measuring a tree that is not the tree that will be ported. It is kept for its
> scoping notes and measurements only. **It is not a hold on anything** and must not be cited
> as a blocker or as evidence that a capability is incomplete.
> See [027 The native port is deferred to a full redo](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md).
>
> Scope was finishing the building transposition, making the plugin folder a hermetic carryable artifact, and the tectonic wavelength that never scales with the world. **The wavelength finding is not native and does not die with this card** — one octave of five survives at the 60 km cook and none at 200 km. It belongs with `SCALE-METRE-CONSTANTS-COLLAPSE`, which is still open in `backlog/`.


## Requested behavior

ML-03e proved a packaged Win64 loop. This slice closes what that loop still gets
wrong, now that the city geometry is ported and the plugin is meant to outlive any one
game.

Two goals, in priority order.

**1. A game must see the buildings the generator actually makes.** The reference has
always emitted dimensioned, rotated, ground-anchored footprints; Core now emits them
too, bit-exactly. Nothing draws them yet. Unreal still places 10x10x14 m boxes at
reserved grid nodes, which are not a reported dimension and never were.

**2. The plugin folder must be the whole generator.** The owner's stated use: build a
game from a known-good generator state, keep that state pinned in the game, and when a
game is abandoned carry the generator into the next one. That makes the installed
folder — not this repository — the unit of delivery. It must be hermetic, versioned
and verifiable without the producer tree on the machine.

## Proposed mechanism

### Finish the wiring (started, incomplete, uncommitted)

`Core/scene.hpp` declares `SceneBuilding`, `WorldScene::buildings`,
`WorldScene::buildings_status` and `plan_settlement_buildings`. An agent was killed
mid-task on 2026-09-18, so this is **declared but unproven**: Core compiles and the 14
native parity tests pass, but nobody has verified the call site is wired or that
`scene.buildings` is ever populated. Verify that first, before building on it.

Then: expose `GetSceneBuildings` on the subsystem (the contract is drafted in the
modified `FantasyWorldGeneratorTypes.h`), and draw them in the consumer at true scale,
instanced by resolved mesh, seated with `TraceDrawnSurface` rather than the height
sample — at 513 rows the two disagree by up to 12.46 m between vertices, which buries
or floats a 5 m house.

### City glyphs at altitude

Settled by the owner, do not relitigate. At the overview pose one pixel is 45 m, so a
true-scale house is ~0.2 px — as is today's placeholder box, which means **the
overview capture currently contains no buildings at all**. Draw one clearly symbolic
glyph per settlement when far, real buildings when near, and never let a glyph read as
a building. Pick the threshold from the arithmetic, not by eye.

### Make the plugin hermetic and self-identifying

Largely done in `tools/package_plugin.py` (uncommitted): the four catalogues the
planners read at runtime (`civilizations.json`, `buildings.json`, `city_shapes.json`,
`castles.json`) now stage into `Data/`, and `plugin-manifest.json` installs inside the
plugin folder carrying a `generator_identity` digest over all 97 files. Remaining:

- **Remove the escape hatch.** `FantasyWorldGeneratorSubsystem.cpp` still falls back to
  `<plugin>/../../Sim/icarus_sim`, a path that exists only in this checkout. Make a
  missing staged catalogue a loud diagnostic, never a silent success. The original bug
  was invisible precisely because the fallback worked here.
- **Guard it with a test.** Nothing checks that a catalogue read at runtime is staged.
  That absence is why the defect existed. A packaging test must fail when a path the
  compiled rules open is not in the archive.
- **Document the carry-over.** How to install into a new game, how to read the pinned
  identity, and the guarantee it buys: two folders sharing a `generator_identity`
  produce identical worlds from identical seeds.

### Tectonic wavelength never scales with the world (defect, measured)

`Core/genesis.cpp:148-167` `world_shape_overrides` emplaces `globe_radius`,
`tectonic_relief`, `amplitude` and `orogeny` but **never `wavelength`**, which stays at
the 4300 m default however large the world is. The Nyquist filter at
`terrain_tectonics.py:177-178` then drops octaves. It reads `cfg.globe_radius`, the
**design** radius, because `terrain_area.apply_world_scale` multiplies down to physical
only after `generate_tectonics` has already resolved the frequency list.

Measured on the real code path, recipe-3 defaults, wavelength 4300, octaves 5:

| circumference | design radius | n=193 | n=513 |
|---|---|---|---|
| 11 km | 9,866 | 3/5 | 5/5 |
| 60 km | 53,817 | **1/5** | 2/5 |
| 200 km | 179,389 | **0/5** | 0/5 |
| 1000 km | 896,945 | **0/5** | 0/5 |

So the shipped 60 km cook resolves **one octave of five**, and at or above roughly
150 km the noise layer is identically zero with only a soft warning at
`terrain_tectonics.py:211`. The surface detail visible in current captures is coming
from `terrain_detail.py`'s close-up bands, not from tectonics: the regional raster is
smoother than intended in every world shipped so far.

The dormant recipe formula at `terrain_recipes.py:23`,
`wavelength = radius*1.6/sqrt(plate_count)`, holds a **constant** octave count at every
circumference — 3/5 at n=193, 5/5 at n=513, the same at 11 km and at 1000 km. The
argument for it is scale-invariant detail, not more octaves. Credit: found by the
Tectonic-plates session, whose magnitudes were confirmed after an initial disagreement
traced to design-versus-physical radius.

**Coordinate before touching this.** A concurrent workstream owns
`terrain_tectonics.py` and is taking worlds to 1000 km, where the default is 0/5 and
the fix is mandatory rather than cosmetic.

### Scale slice parity debt: the two sides now generate different planets

Added 2026-09-18 by the Tectonic-plates session, which caused this. The wavelength
defect above is one item in a larger Python change that has already landed and that
**breaks native parity outright**, not within a tolerance.

**What landed on the Python side** (`generate_request`, not `Config` defaults):

- `world_size` presets moved from design-radius multipliers (11/22/33 km circumference)
  to **200 / 400 / 600 km**, with `DEFAULT_RELIEF_M` 1667 and `DEFAULT_OROGENY` 10.
- New authored inputs `circumference_km` and `relief_m` derive `globe_radius`,
  `tectonic_relief`, `amplitude`, `wavelength` and `orogeny` through the new pure module
  `Sim/icarus_sim/terrain_scale.py`. This includes the wavelength fix above.
- `settlement_spacing`, `support_reach` and `culture_link_cost` now derive from
  circumference; their upper bounds rose from 10 km to 100 km.
- Ley school widths scale by `physical_radius / 1774.4123532462844` in
  `terrain_leyline_history.generate_networks`.
- Grid ceiling raised 257 -> 1025.

**Why parity fails badly.** `tests/test_native_world.py:122-125` builds its oracle by
calling `generate_request(...)` — it is a live oracle, and `Fixtures/native-world-v1.json`
is only the numeric contract. `generate_request` is exactly where the new world shape
lives, so the Python side is now a 200 km world while `Core/` still builds an 11 km one
from its own `WorldConfig`. Expect the **identity layers** (plate, water, biome,
landform, land) to mismatch outright. That is the signature of a different planet, and no
tolerance change touches it.

**Containment, which is better than it first looks.** The presets live in the request
builder, *not* in `Config.__post_init__` defaults. Anything constructing a `Config`
directly — most of `Sim/tests/` — still gets the old 11 km world. Only the CLI, the lab
request path and this parity oracle see the new one.

**The port, concretely:**

- `Core/genesis.cpp` `world_shape_overrides` — add
  `wavelength = radius*1.6/sqrt(plate_count)` (the item above).
- Core config path — the 200/400/600 km presets, `DEFAULT_RELIEF_M` 1667,
  `DEFAULT_OROGENY` 10, and the derivation order in `terrain_world.generate_request`.
- Core — scale `settlement_spacing`, `support_reach`, `culture_link_cost` by
  `circumference / 11149.557` (the reference circumference), clamped at 100 km.
- `Core/magic.cpp` — scale school widths by `physical_radius / 1774.4123532462844`.
- `Core/tests/world_driver.cpp` — must be handed the same circumference the Python side
  derives, or the kernels agreeing changes nothing.

**Two measured traps the port will hit.**

1. `terrain_recipes.derive_population` looks like it scales spacing and reach with land
   area. It does not run: it early-returns on `if not cfg.auto_parameters`, and
   `Config.__post_init__` **forbids** `auto_parameters` with `world_recipe=3`. It is dead
   code on the only live recipe. Do not port it as the source of truth; the derivation
   lives in `generate_request`.
2. Every reach is absolute metres tuned for the 11 km world, and each one fails
   **silently** by covering less than one cell rather than by raising. Measured at
   200 km before the fix: `support_reach` 1000 m was 0.16 of one cell, giving **222
   cities, zero hamlets and zero fortresses**, and a size-33 world took 9m31s instead of
   4s. Ley widths at 110 m took magical cells from **1003 to 8**. Verify a port by
   counting hamlets, fortresses and magical cells, never by reading the kernel.

Still unscaled on both sides, deliberately: `nest_settlement_clearance` (250 m),
`sea_reach` (6000), `air_reach` (4500), `fishing_reach` (700), `sky_radius` (180).

**Consumer note.** `tools/terrain_world.js:34` still sets the `globe_radius` input from
`10000*{small:1,medium:2,large:3}` when `world_size` changes. That mapping is dead — the
radius is now derived from circumference — so the field displays a value the generator
will not use. Cosmetic only (the value is not added to `explicit`), but misleading.

### Port hygiene, deferred on purpose during the port

Each was flagged by the agent that created it rather than hidden, and each was left
alone because refactoring verified code mid-port is the wrong order:

- `smooth_closed_ring` and `path_turn_degrees` exist twice — exported from
  `Core/cityfortifications.hpp` and duplicated as statics in `Core/castlegeometry.cpp`.
  Both verified; unify and re-run both suites.
- **Two implementations of Python's `round(x, n)`**: `fortification_round_digits`
  (snprintf) and a `python_round` inside `castlegeometry.cpp` that replicates CPython's
  digit algorithm. Both pass their oracles. This belongs in `Core/globe.hpp` beside
  `Sum`, `python_hypot` and `python_mod` as one shared primitive.
- `Core/README.md` lists ported modules and names none of the ten added here.
- `Core/cityplanner.cpp:802-805` hardcodes `neighbour_half` as an if/else chain that
  throws on an unknown `city_class`. It will throw the moment a new settlement tier
  appears — a hard coupling point with the tier workstream.

### Windows CI for the CRT class of bug

MSVC's static CRT `pow()` differs from `ucrtbase.dll`'s — which is what CPython calls —
by one ulp on a small fraction of inputs, and `perlin3` evaluates `pow(f, 3.0)` three
times per sample. `tests/native_cxx.py` passed no CRT flag and so defaulted to the
non-matching one; its parity tests stayed green only because
`Fixtures/native-world-v1.json` compares continuous fields with a tolerance that
absorbs a 13th-digit drift. Fixed by adding `/MD` (uncommitted).

The trap is that **Linux CI can never catch this**: there CPython and g++ share glibc,
so they agree automatically. Green CI does not prove Windows parity. If Windows is the
shipping platform, a Windows job is needed — it does not need the engine, only a
compiler and the existing oracle harnesses.

## Dependencies and unresolved decisions

- Depends on the ten bit-exact Core ports landed 2026-09-18. Their oracle harnesses
  live in the session scratchpad, not in the repository: **decide whether they become
  committed tests**. They are the regression net for every future generator change and
  currently survive only as loose files.
- Blocked-ish on the terrain/scale/tier workstream for `terrain_tectonics.py`,
  `city_planner.py`, `city_fortifications.py`, `hamlet_planner.py` and
  `civilizations.json`. That workstream's scale slice has now landed in Python and its
  C++ parity debt is logged **in this card** (see "Scale slice parity debt"), by the
  owner's decision on 2026-09-18, rather than in a card of its own. The tier and
  verticality slices are still to come and will add to it.
- Open: whether the cook moves to a self-hosted Windows runner. Everything except the
  cook already runs in existing CI; the cook needs a licensed ~100 GB engine install.
- Open: `plugin_version` is hand-maintained (now 0.3.0) while `generator_identity` is
  computed. Decide which is authoritative for a game pinning a generator.

## Sources consulted

- `Core/scene.hpp`, `Core/genesis.cpp`, `Core/cityplanner.cpp`, `Core/citygeometry.cpp`
- `Sim/icarus_sim/terrain_tectonics.py`, `terrain_area.py`, `terrain_recipes.py`
- `tools/package_plugin.py`, `tests/native_cxx.py`, `.github/workflows/publish.yml`
- `Artifacts/unreal/packaged-run.json`, and the 2026-09-18 packaged captures
- Cross-session findings from the Tectonic-plates session (wavelength, `city_blocks`
  fourth use at `Core/settlementpresets.cpp:934`, duplicated detail height at
  `Core/cityplanner.cpp:214` and `Core/world.cpp:256`, and
  `Core/history.cpp:38-93` fusing the stage-6/7 transition without emitting
  `second_uplift`, `second_convergence`, `second_divergence`, `moved_plates` or
  `pre_tectonic_height`). Only the wavelength finding was independently verified here;
  the rest are unconfirmed leads.

## Files and assets in scope

`Core/scene.{hpp,cpp}`, `Core/genesis.cpp`, `Core/globe.{hpp,cpp}`,
`Core/castlegeometry.cpp`, `Core/cityfortifications.{hpp,cpp}`, `Core/README.md`,
`Core/tests/world_driver.cpp`, the plugin subsystem and types headers,
`tools/package_plugin.py`, `tests/native_cxx.py`, `.github/workflows/publish.yml`,
`docs/unreal-integration.md`, and in the consumer
`Source/UnrealWorldGen/FWGWorldMaterializer.{h,cpp}`.

## Acceptance and evidence

1. A packaged Win64 run reports `scene_buildings=` with a city/hamlet/castle split, and
   the count matches what the Python reference emits for that seed.
2. A near-ground capture shows real buildings at authored size beside the 1.8 m scale
   figure — the 4x4x2 m well and the 8x10x6 m worker house readable as such.
3. An overview capture shows one glyph per settlement, and the glyph is visibly not a
   building.
4. The plugin installs into a project on a machine with no copy of this repository and
   produces buildings. This is the test the original defect would have failed.
5. A packaging test fails when a runtime-read catalogue is unstaged.
6. `generator_identity` is readable at runtime and two installs sharing it produce
   identical worlds from identical seeds.
7. Octave counts hold constant across circumference after the wavelength fix, with the
   table above regenerated as evidence.
8. `python tools/validate_repo.py` green, and every ported module's oracle still
   prints ALL EXACT.

## Documentation impact

`docs/unreal-integration.md` gains the scene-building API and the glyph rule.
`board/backlog/ML-03e.md` packaged-evidence section is refreshed with building counts.
A new carry-over section documents installing and pinning the plugin in a game.
`Core/README.md` lists the ten added modules.

## Adversarial review and limitations

- The 2026-09-18 evidence stands on suites, not on eyes: buildings have never been seen
  drawn at true scale in an engine. Counts matching is necessary, not sufficient.
- `scene.buildings` is declared and unproven. Do not assume the last hop works.
- The bit-exact ports are exact against the CPython they were measured against, on this
  machine, with `/MD`. A different interpreter build or libm may move `pow`-dependent
  values within the documented tolerance.
- The wavelength fix changes every generated world. It is a deliberate break and needs
  fixtures regenerated, not a compatibility shim.
- An adversary pass found five real divergences in `city_planner` that its own author's
  21-case suite missed, including a process-killing integer divide. Assume the same is
  true of any module verified only by the agent that wrote it.

## Handoff

Finish line: a game project that contains only the plugin folder generates a world with
its own buildings, reports which generator version produced it, and needs nothing from
this repository to do so.
