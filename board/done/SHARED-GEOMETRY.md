# SHARED-GEOMETRY — one sphere-grid module instead of four pinned copies

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** `child_seed` is copied in all four of `hero_generator`, `story_web`, `npc_roster`, `key_locations`; `node_index` additionally in `key_locations`. Exactly as carded.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: reader-packages sweep, 2026-09-21. State: **DONE.**

## Delivered 2026-09-21

`Sim/world_geometry/` now holds one implementation of every primitive, and every reader
imports it. Claimed by `docs/conformance/world-geometry.md` (new record, tier `EXERCISED`).

**The card's count of pinned copies was wrong, and wrong in both directions. Re-derived, not
quoted:**

| Primitive | Definitions found in Python, before |
|---|---|
| `child_seed` | **5** — the generator plus a copy in each of the four readers, not four |
| `node_index`, `cell`, `node_count`, `cell_area_m2`, `cell_of_direction`, `offset`, `normalise`, `slerp`, `great_circle_m` | **1 each** — `key_locations/core/grid.py` only. The generator computes the layout inline inside `terrain_erosion.sphere_grid` and never names these functions. |
| `direction` | **2** — `icarus_sim/terrain_globe.py` and `key_locations/core/grid.py`. (`castle_planner` and `city_planner` each define a local `direction_at`; neither is this function.) |

So "four copies of the sphere-grid primitives" over-counts the geometry and under-counts the
seed helper. The consolidation is real either way, but the number in the ticket was not.

A **fifth** great-circle distance was found and deliberately **not** consolidated:
`hero_generator/history.py:57` `separation` writes the dot product as
`sum(x * y for x, y in zip(...))`, which begins at integer `0`, where `grid.great_circle_m`
writes the three products out. The two agree on every ordinary input and disagree on the sign
of a zero dot product, because `0 + -0.0` is `0.0`. Replacing it would be exactly the
arithmetic "simplification" that moves a world, so it stays and is recorded in the new record's
`## Does not establish`.

### Decisions made on the owner's behalf — reverse these if you disagree

1. **`icarus_sim` stays the oracle. The generator was not touched.** *Rejected: the generator
   adopting `world_geometry`.* Adoption gives one definition instead of two and is the cleaner
   end state, but it edits the generator to serve its consumers, several of the modules it
   would touch are provenance-pinned, and it weakens the pin itself: a test comparing an
   imported function to the module it was imported from asserts `f is f`. Keeping two
   definitions keeps a real comparison, and that comparison is the test that fails if they
   drift. The conservative option, per the sweep's standing instruction.
2. **The package lives at `Sim/world_geometry/`, a top-level sibling of the readers**, not
   inside any one of them and not under `icarus_sim`. Anything under `icarus_sim` would make
   every reader's "never mentions `icarus_sim`" assertion false by construction; anything
   inside one reader would make the other three depend on it. `pyproject.toml`'s
   `packages.find` include list gains `world_geometry*`; there is no package data.
   *Native module mapping:* there is none to update. No file in the tree maps Python modules to
   `Core/` stems, the three `cxx-constexpr` version bindings were removed on 2026-09-21 as
   follow-through on decision 027, and `Core/` mirrors this arithmetic in its own copies. A
   shared Python module does not reduce the native surface by one line, and under 027 it is not
   meant to. No C++ was written.
3. **The reader-side modules are re-export shims, not deletions.** `hero_generator/seeds.py`,
   `story_web/seeds.py`, `npc_roster/seeds.py`, `key_locations/seeds.py` and
   `key_locations/core/grid.py` keep their import paths and hold no arithmetic. This was forced
   as well as preferred: `Sim/tests/test_npc_roster.py` does
   `from npc_roster.seeds import child_seed` and belongs to another workstream, so that path
   had to survive. Keeping the shims also leaves `coverage.json` untouched — no module
   appeared or vanished from the `uncovered` allowlist.

### Acceptance, item by item

- *One implementation of each primitive, imported by every reader package.* Done, and asserted
  by **identity** rather than equality:
  `test_world_geometry.py::SharedImplementation` uses `assertIs`, because four equal copies
  pass an equality test on the day someone re-forks them.
- *Exactly one test pinning it to the generator, at several raster sizes.* One new pin,
  `Sim/tests/test_world_geometry.py::Pins`, at sizes **5, 9, 17, 33 and 65** (the old
  `key_locations` pin covered 9, 17, 33). The three redundant per-package pins in
  `test_hero_generator.py`, `test_story_web.py` and `test_key_locations.py` were removed.
  **One redundant pin survives and could not be removed:**
  `test_npc_roster.py::PackageTests::test_seed_helper_matches_the_generator`. That file is
  fenced to a live naming session. It passes — it now compares the shared implementation to the
  generator by a second route — so the count is 2, not 1, until that fence lifts. Deleting it
  is a two-line follow-up for whoever owns that file next.
- *Every reader still passes its "never mentions `icarus_sim`" assertion.* Yes, unchanged, and
  `test_world_geometry.py::Isolation` now re-checks all four packages in one place plus asserts
  that `world_geometry` itself imports nothing but `math`, `hashlib` and `random`. That
  assertion reads the imports out of the **parse tree** rather than matching substrings, so a
  word in a docstring is not mistaken for a dependency and an aliased import is not missed.
- *No seed-42 output moves.* Verified by byte comparison, not by argument. Every function body
  was moved verbatim — the move was scripted with an asserted anchor and the transplanted text
  was diffed against the original, both `True` — and nine SHA-256 digests taken over the four
  reader packages' full output plus a 500 KB sample of the geometry itself
  (`node_index`/`cell`/`direction`/`cell_area_m2` for every cell at sizes 5, 9, 17, 33, 65, and
  `great_circle_m`/`slerp`/`offset`/`cell_of_direction`/`normalise` samples, plus `child_seed`
  over 96 master/domain/variation combinations through all four packages) are **identical before
  and after**. The four packages' own fixture tests
  (`hero-generator-v1.json`, `story-web-v1.json`, `npc-roster-v1.json`) also still pass.

### Files changed

New: `Sim/world_geometry/{__init__,grid,seeds}.py`, `Sim/tests/test_world_geometry.py`,
`docs/conformance/world-geometry.md`.
Shims: `Sim/{hero_generator,story_web,npc_roster,key_locations}/seeds.py`,
`Sim/key_locations/core/grid.py`.
Tests: `Sim/tests/test_{hero_generator,story_web,key_locations}.py` (redundant pins removed;
`test_key_locations.py` keeps a new assertion that its own import paths resolve to the shared
implementation).
Docs: `docs/key-locations.md`, `docs/hero-generator.md`, `docs/story-web.md`,
`docs/conformance/actor-scale-writes.md` (one sentence that said
`hero_generator/seeds.py` duplicates `child_seed`, which is no longer true).
Build: `pyproject.toml`.

**Not done, and it is not mine to do:** `docs/npc-roster.md:254` still says the helper "is a
byte-for-byte copy of the generator's and a test pins them together". That file is fenced to
the naming session. The sentence is now false in its first half and true in its second. It
needs the same edit the other three canonical documents got.

## Requested behavior

Four reader packages now carry their own copies of the same sphere-grid primitives, each
pinned against `icarus_sim` by its own test. One shared pure-geometry module that every reader
imports would be better than four copies that agree only because four separate tests say so.

## Why the copies exist, which is a real reason and not an accident

Reader packages — `hero_generator`, `story_web`, `npc_roster`, `key_locations` — read a
finished world's JSON and never import the generator. That isolation is deliberate and
test-asserted: it is what lets a saved `world.json` serve as well as a live result, and what
keeps a package from quietly depending on generator internals.

`child_seed` was the first thing copied under that rule. `key_locations` then needed more,
because unlike a consumer that only reads *placed* records it has to *choose* ground, and
choosing means addressing cells the world never occupied — which requires `sphere_grid`'s
exact node layout, not just the `node`/`x`/`z` stamped on existing records. So it copied
`node_index`, `cell`, `direction` and `cell_area_m2` as well, and pinned all four against
`sphere_grid`/`terrain_globe` at sizes 9, 17 and 33.

The pins work. They are also the whole problem: four copies that are correct *because* four
tests independently say so, rather than because there is one of them.

## Proposed mechanism

A small pure-geometry package — no filesystem, no network, no engine, no generator import —
holding the sphere-grid node layout, direction, cell area, great-circle distance, slerp and
`child_seed`. Every reader package imports it; `icarus_sim` either imports it too or stays
pinned against it by a single test rather than four.

Open questions the owner has to settle, not the raiser:

- Does `icarus_sim` adopt it, or does it stay the oracle with one pin pointing at it? Adoption
  is cleaner and touches the generator, which is the expensive half.
- Where does it live so that `pyproject.toml`, the native port's module mapping and the
  "package never mentions `icarus_sim`" tests all stay coherent.
- `Core/` mirrors these functions too. A shared Python module does not by itself reduce the
  native surface, and pretending otherwise would be the wrong claim to make in the ticket.

## Dependencies and unresolved decisions

- **Unowned.** Raised by KEY-LOCATIONS, which judged it larger than its own ticket and needing
  a deliberate owner rather than a drive-by. The coordinator agreed and escalated it; it was
  not assigned, so it is recorded here rather than dropped.
- Nothing is broken today. This is debt with a working mitigation, not a defect — which is
  exactly why it will keep not happening unless someone picks it up on purpose.

## Files and assets in scope

`Sim/hero_generator/seeds.py`, `Sim/story_web/seeds.py`, `Sim/npc_roster/seeds.py`,
`Sim/key_locations/seeds.py`, `Sim/key_locations/core/grid.py`, the four pin tests that hold
them to `icarus_sim`, `pyproject.toml`, and whatever new package the owner chooses.

## Acceptance and evidence

- One implementation of each primitive, imported by every reader package.
- Exactly one test pinning it to the generator's behaviour, at several raster sizes, instead of
  one per package.
- Every reader package still passes its "never mentions `icarus_sim`" assertion.
- No seed-42 output moves: this is a refactor, and any change in a generated world means the
  copies were not identical after all, which would itself be the finding.
