---
conformance: 1
record: world-geometry
tier: EXERCISED
summary: Holds one implementation of the sphere-grid node layout, cell direction, cell area, great-circle distance, bearing offset, spherical interpolation and child-seed derivation, imported by every package that reads a finished world and pinned to the generator by a single test.
modules:
  - Sim/world_geometry/__init__.py
  - Sim/world_geometry/grid.py
  - Sim/world_geometry/seeds.py
emits: []
versions: []
proof:
  - path: Sim/tests/test_world_geometry.py
    establishes: that all four reader packages hold the same function objects rather than equal ones, that the node layout, cell inverse, direction and cell area equal the generator's at five raster sizes, that the child seed equals the generator's across seventy-two master/domain/variation combinations, that great-circle distance and interpolation stay on the unit sphere, that a bearing offset walks the distance it was given, that the package imports nothing but math, hashlib and random, and that no reader package imports the generator
decisions: []
tickets:
  - board/done/SHARED-GEOMETRY.md
---

# Conformance: world geometry

## What it produces

Nothing in a world document. This package is arithmetic: given a raster size it returns node
ids, cell coordinates, unit direction vectors, cell areas in square metres, distances along a
great circle, interpolated points between two directions and the position reached by walking a
bearing; given a master seed and a domain string it returns the derived child seed and a
seeded `random.Random`.

It is the single implementation of primitives that four packages previously each carried a
copy of.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `node_count(n)` | `world_geometry.grid` | How many nodes a size-`n` raster has: two poles plus a row-major body with the seam column dropped. |
| `node_index(x, z, n)` | `world_geometry.grid` | The node id the generator gives cell `(x, z)`. Poles collapse to one node each; `x` wraps at the seam. |
| `cell(node, n)` | `world_geometry.grid` | The `(x, z)` a node id addresses — the inverse of `node_index`. |
| `direction(x, z, n)` | `world_geometry.grid` | The unit vector of a cell, equal to `icarus_sim.terrain_globe.direction`. |
| `cell_area_m2(z, n, radius)` | `world_geometry.grid` | The surface area of one cell's latitude-band slice, as `sphere_grid` computes it. Pole rows carry the whole band. |
| `cell_of_direction(v, n)` | `world_geometry.grid` | The nearest cell to an arbitrary direction, for reading layers under something that does not sit on a node. |
| `great_circle_m(a, b, radius)` | `world_geometry.grid` | Surface distance between two unit directions, with the dot product clamped against float overshoot. |
| `offset(origin, bearing, distance_m, radius)` | `world_geometry.grid` | The direction reached by walking `distance_m` from `origin` along a great circle, `bearing` in radians clockwise from local north. |
| `slerp(a, b, t)` | `world_geometry.grid` | Great-circle interpolation, falling back to the nearer endpoint when the two directions coincide. |
| `normalise(v)` | `world_geometry.grid` | A unit vector, returning `(0., 1., 0.)` for a zero-length input rather than dividing by zero. |
| `child_seed(master, domain, variation=0)` | `world_geometry.seeds` | The generator's own derived seed: the first four bytes of `sha256('tectonics-v1:<master>:<domain>:<variation>')`, big-endian. |
| `rng(master, domain, variation=0)` | `world_geometry.seeds` | `random.Random(child_seed(...))`. |

Every name is also re-exported from the package root, and from each reader's existing import
path: `hero_generator.seeds`, `story_web.seeds`, `npc_roster.seeds`, `key_locations.seeds` and
`key_locations.core.grid` are re-export modules with no arithmetic of their own.

## Inputs it reads

Nothing. No world document, no block, no layer, no config, no catalogue, no file. Every
function takes its arguments and returns a value. The whole package imports `math`, `hashlib`
and `random` and nothing else, which is what lets a reader package depend on it without
breaking the rule that a reader never imports the generator.

## Artifacts it writes

None. It writes no key into any world and no file anywhere.

**Invariant: this is the generator's arithmetic, in the generator's order.** These functions
are not a re-derivation of the sphere grid; they are the expressions `icarus_sim`
evaluates, transcribed. Float addition is not associative, so a rewritten sum here is a
different world even where the algebra is equivalent — different node heights, therefore
different city sites, against a byte-compare gate. Two places this looks like an accident and
is not:

- `direction` computes `math.cos(lat) * math.cos(lon)` and `math.cos(lat) * math.sin(lon)` as
  two products rather than hoisting `math.cos(lat)`; keep the expression.
- `cell_area_m2` multiplies the band area by `n - 1` on the two pole rows, because the pole
  node stands for the entire cap row. A "simplification" that treats a pole like any other
  cell shrinks it by a factor of `n - 1`.

**Invariant: the child-seed domain prefix is part of the replay contract.** The literal
`tectonics-v1:` is not a namespace that can be tidied. Changing it renames every random stream
in every package at once, in the generator and in all four readers, and every saved world
stops replaying.

## Where it runs

Wherever a reader package needs it: `hero_generator`, `story_web`, `npc_roster` and
`key_locations` all import it at module import time. It is not part of a generation stage, has
no attach site and no gate, and holds no state, so the call order does not affect its results.

`icarus_sim` does **not** import it. The generator keeps its own definitions and remains the
oracle this package is pinned against; see `## Why it works this way`.

## Versions asserted

None. This package emits no block and no version integer, so it has no marker and needs no
binding in `version-bindings.json`. Its contract is behavioural equality with the generator,
which the pin below asserts directly rather than through a number.

## Proven by

`Sim/tests/test_world_geometry.py`, in about a tenth of a second, with no world generated.

- `::SharedImplementation::test_every_reader_package_shares_one_seed_helper` and
  `::SharedImplementation::test_the_grid_primitives_have_one_implementation` — identity, not
  equality. `assertIs` is the whole point: four equal copies pass an equality test on the day
  someone re-forks them, and fail this one.
- `::Pins::test_seed_helper_matches_the_generator` — the derived seed equals
  `icarus_sim.terrain_tectonics.child_seed` over four masters, six domains including the empty
  string, and three variations.
- `::Pins::test_grid_geometry_matches_the_generator` — at sizes 5, 9, 17, 33 and 65, node
  count, node id, the cell inverse, direction and cell area all equal what
  `icarus_sim.terrain_erosion.sphere_grid` and `icarus_sim.terrain_globe.direction` produce,
  for every node in the raster.
- `::Pins::test_great_circle_and_slerp_stay_on_the_sphere` and
  `::Pins::test_offset_walks_the_distance_it_was_given` — the interpolation and the walk stay
  on the unit sphere and land at the distance asked for.
- `::Isolation::test_the_package_is_arithmetic_and_nothing_else` — the imports are read out of
  the parse tree, not matched as substrings, and the set outside `math`, `hashlib`, `random`
  and the package itself is empty.
- `::Isolation::test_the_readers_still_never_reach_into_the_generator` — every `.py` file
  under all four reader packages, line by line.

## Why it works this way

A reader package reads a finished world's JSON and never imports the generator. That isolation
is deliberate and test-asserted: it is what lets a saved `world.json` serve as well as a live
result, and what keeps a package from depending on generator internals.

The rule was satisfied for a long time by copying. `child_seed` was copied into all four
readers; `key_locations` additionally copied the node layout, because unlike a consumer that
reads only *placed* records it has to *choose* ground, and choosing means addressing cells the
world never occupied. Each copy was pinned by its own test, so four implementations agreed
because four tests said so rather than because there was one of them.

The rule never required the copies. It required that no reader import the generator, and a
package that imports nothing but `math`, `hashlib` and `random` satisfies that as well as a
copy does — better, because the isolation is now asserted about one file instead of five.

**`icarus_sim` stays the oracle and imports nothing from here.** That is the conservative half
of the choice and it is deliberate. Making the generator import this package would give one
definition instead of two, but it would edit the generator to serve its consumers, and several
of the modules that would change are provenance-pinned. A pin that compares two independent
expressions is also a stronger statement than one that compares a function to itself: if the
generator imported this module, `test_grid_geometry_matches_the_generator` would assert
`f is f` and prove nothing. The cost of keeping two definitions is that the generator can still
drift from the readers — and that is exactly what this test fails on.

The reader-side modules are re-export shims rather than deletions so that every existing import
path keeps working, including `from npc_roster.seeds import child_seed` in a test module owned
by another workstream.

## Does not establish

- **That the two definitions can never diverge.** The pin compares them at five raster sizes
  and seventy-two seed combinations, not over the whole legal range. A divergence that appears
  only at size 129, or only for a domain string no test uses, would pass.
- **That the primitives are correct.** Every assertion here is equality with the generator. If
  `icarus_sim`'s cell area is wrong, this package is wrong in exactly the same way and every
  test still passes. The generator is the oracle, not a proof.
- **Anything about `Core/`.** The native tree mirrors these functions in its own copies. A
  shared Python module does not reduce the native surface by one line, and under
  [027](../decisions/027-native-port-deferred-to-a-full-redo.md) it is not meant to.
- **That exactly one test pins the primitives.** This is the only pin that matters, but
  `Sim/tests/test_npc_roster.py` still carries a per-package `child_seed` pin of its own. It
  passes — it now compares the shared implementation to the generator, by a second route — and
  it is redundant. It stays because that file belongs to another workstream.
- **That every geometry primitive in the repository is here.** Three were found and
  deliberately left alone. `hero_generator.history.separation` is a fifth great-circle
  distance, and it is **not** the same expression: it sums the dot product with
  `sum(x * y for ...)`, which begins at integer `0`, where `great_circle_m` writes the three
  products out. The two agree on every ordinary input and disagree on the sign of a zero dot
  product, because `0 + -0.0` is `0.0`. Replacing it would be exactly the arithmetic
  "simplification" this record warns against, so it stays. `hero_generator.wells.countryside`
  measures a planar `math.hypot` on grid coordinates, which is a different quantity, not a copy
  of this one. `icarus_sim.castle_planner` and `icarus_sim.city_planner` each define a local
  `direction_at`. None of the three is touched or pinned here.
