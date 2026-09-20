# SHARED-GEOMETRY — one sphere-grid module instead of four pinned copies

Owner: none. State: backlog, unowned. Raised by KEY-LOCATIONS; escalated and not taken.

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
