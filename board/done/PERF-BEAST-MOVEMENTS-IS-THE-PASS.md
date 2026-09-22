# PERF-BEAST-MOVEMENTS-IS-THE-PASS — the largest pass in a generation, 10× cheaper at identical bytes

Owner: none. State: **done**. Raised by [docs/performance.md](../../docs/performance.md),
which had named `add_beast_movements` the successor to `add_world_society` — *"both the
largest pass and the only superlinear one left"*, 21 % of a size-128 run and a projected
46 % of a size-257 one. Delivered 2026-09-21.

> **The block this pass writes did not move.** `beast_movements` was captured before and
> after at sizes 17, 33, 65 and 128 and compares **byte for byte with every float printed
> by `repr`** — same groups, same camps, same leg node paths, same `host_uid`s, same
> `routed`/`stranded`/`solitary` counts. No seed changes, no schema or version moves, no
> world needs regenerating. This is a cost change and nothing else.

## What it cost

Timed around the pass alone on a baked phase-16 world, old implementation against new in
one process so the two see the same box and the same minute. Seed 42, recipe 3, Windows 11
/ 24-core / 31.4 GB / CPython 3.12.10.

| Size | Groups | Before | After | Factor |
|---:|---:|---:|---:|---:|
| 17 | 756 | 0.025 s | **0.009 s** | 2.7× |
| 33 | 2 760 | 0.400 s | **0.077 s** | 5.2× |
| 65 | 6 262 | 4.623 s | **0.617 s** | 7.5× |
| 128 | 11 184 | 34.792 s | **3.248 s** | **10.7×** |

Exponent against cells: **1.79 → 1.47.**

In situ, from four full `tools/stage_profile.py` generations on the same tree, which is the
measurement [docs/performance.md](../../docs/performance.md) carries:

| | 13:38 run | 16:08 run |
|---|---:|---:|
| `add_beast_movements` at 128 | 38.68 s | **3.60 s** (−90.7 %) |
| Its exponent | 1.62 | **1.10** |
| Its rank among passes | 1st of 8, 21.0 % | **8th, 2.6 %** |
| Whole run at 128 | 184.6 s | **137.0 s** (−25.8 %) |
| Peak resident at 128 | 2 823 MB | **1 069 MB** (−62 %) |
| Projected size-257 cost of the pass | ~366 s | **~17–25 s** |

**This is the cleanest single-variable pair in that document.** `terrain_beast_movement.py`
is the only file in the measured digest that changed between the two runs, confirmed by
modification time as well as by the digest, and at size 65 every unchanged pass moved by
less than a percent.

### The memory was not the target and is the larger finding

Resident sampled during the call, on a baked world:

| Size | Peak above entry, before | After |
|---:|---:|---:|
| 65 | 216 MB | **48 MB** |
| 128 | **2 208 MB** | **158 MB** |

The old form cached a full-width `distances` and `parent` list for every start node it
searched from — about 9 000 of them at size 128, 16 004 entries each — and dropped none
until the function returned. That was the 1 723 MB transient inside stage 16 that
`docs/performance.md` had recorded and attributed to "the planners and the satellite
packages". It was this.

## What was actually wrong

Four costs, none of which grew with the number of *routes* and all of which grew with the
world. Measured, at size 65, by instrumenting the old code rather than by reading it:
`builder.follower` was 3.09 s of a 6.20 s instrumented run and `terrain_nests.distance` was
called **3 902 893 times**.

1. **The host scan was quadratic in the block.** A follower takes the nearest host in reach,
   biased by kind, and by the time followers are built nearly every other group in this
   block is a host. Every follower was compared against every host: 2 494 × ~1 565 great
   circle distances at size 65, each an `acos` over a compensated dot product.
   **Now** the hosts are sorted by latitude and walked outwards from the follower's own
   latitude, nearest side first, stopping on whichever of two floors it meets first — the
   reach, and the best mark already found divided by the smallest bias the role can apply.
   The same mathematics `terrain_nests.nearest_settled` already uses.

2. **An unbounded Dijkstra per group, over a cost function evaluated per edge.** Every
   builder searched the whole land component and every relaxation called the `travel_cost`
   closure, whose answer cannot change because the graph and the ground are fixed for the
   pass. **Now** the graph is priced once — one call per directed edge — and the search
   stops at the reach its caller will read. Exact, because edge costs here are strictly
   positive.

3. **A scan of every cell in the world to find the two hundred a search reached.**
   `_within` ran over all 16 004 cells after each search to recover a set the search
   already knew. **Now** the search reports what it settled, sorted ascending because
   `_irruption` sums forage over it and float addition is not associative.

4. **One route built per group, where a route depends only on the cell.** Nothing any
   builder reads varies between two species standing on one cell of one movement class —
   a follower additionally reads its role. **Now** the circuit is built once per key and
   worn by everyone who shares it, and each traced leg is cached by its pair of endpoints.
   11 184 groups at size 128 resolve to 9 236 searches rather than one search per camp per
   group.

## Why it is bit-exact

Each of the four is an ordering or bookkeeping change and none of them touches a float:

- **Bounded search.** Edge costs are strictly positive — `travel_cost` refuses `d <= 0` and
  its forage term never falls below 0.75 — so every prefix of a path costing `limit` or
  less also costs `limit` or less, and a node inside the bound keeps the distance and the
  parent the unbounded search gave it.
- **Target early-exit**, used for leg traces: every node on the path to the target has a
  *strictly* smaller distance than the target, so all of them are settled with final
  parents by the time it is popped.
- **The host walk.** The winner is the unique minimum of `(span * bias, uid)`, which does
  not depend on the order candidates arrive in, and the walk's floors are conservative:
  the angle between two directions is at least the difference of their latitudes.
- **Hoisted fields and inlined `clamp`.** Same values, same defaults, same order of
  operations. `clamp` *is* `max(0., min(1., v))`.

The claim is not that these arguments are sound; it is that the block compares
`repr`-exact at four sizes, which is what would catch it if one of them were not.

## Coverage

`Sim/tests/test_beast_movements.py` gains `BoundedSearchTests` and `HostWalkTests`: the
bounded search against `terrain_settlements.shortest_paths` for both the settled set and
every parent inside it, the target trace against the unbounded trace, and every follower's
recorded host against a flat scan over every host.

**Both were run against deliberately broken code before being believed.** Perturbing the
host walk's slack to −1e-7 rad moves **23 followers** onto a different host at size 33 and
the test goes red — which is also the measured justification for the slack existing.
Breaking the search four ways — reach × 0.9, reach × 0.5, never clearing the parent array
between calls, inverting the first-touch test — turns the set and parent assertions red in
all four cases, and the stale-array case puts 16 of 24 traced routes on a different path.

**The first shape of `BoundedSearchTests` was empty and the control is what found it.** It
sampled the 24 lowest start-node indices at size 17; node 0 is the north pole and the cells
around it on that world are all isolated, so every search settled exactly one cell — itself
— and passed against anything that returns its own start. Every perturbation above also
passed. The class now samples start nodes of groups that routed, builds its world at size
33 where the same sample settles 13 cells rather than 2.0, and carries
`test_searches_here_are_not_trivial` so that a future world cannot quietly empty it again.
The cost is one size-33 generation, about 35 s, shared between the two classes.

## Evidence

- `Sim/tests/test_beast_movements.py`: 8 tests, 48 s, green.
- Full Sim suite: 1 082 tests, **3 failures, all pre-existing and carded** —
  [NPC-TOMBSTONES](../backlog/NPC-TOMBSTONES.md) (two deliberate defect pins) and
  [WAR-RUIN-CHARGES-GROUND-NO-SCHOOL-HELD](../backlog/WAR-RUIN-CHARGES-GROUND-NO-SCHOOL-HELD.md)
  (one). None is in or downstream of this pass.
- `python tools/docs_check.py`: passed, 235 documents, 14 pre-existing warnings.
- `python tools/verify_provenance.py`: **already failing before this change** on
  `terrain_erosion.py`, `terrain_settlements.py` and `terrain_society.py`, which carry
  another session's uncommitted work. `terrain_beast_movement.py` is not a manifest
  destination, so this change needs no provenance revision.
- Profile reports `Artifacts/stage-profile-{17,33,65,128}-c5.{json,md}`, digest
  `e9922f7ee1c6754b`.

## Limitations

- **The in-situ exponent of 1.10 is loosely fitted.** It runs through a size-17 figure of
  0.05 s, at the edge of what `stage_profile` resolves. The isolated harness's 1.47 against
  the old code's 1.79 is the better-resolved pair and the more conservative claim. Both say
  the shape improved; neither is a measurement at 257.
- **Nothing at size 257 or 513 has been run.** The projections are projections. What the
  memory result changes is that a 257 run is now worth attempting rather than worth fearing.
- **The remaining cost is close to the floor for this algorithm.** The pass does one
  bounded search per distinct start node and examines the cells inside a reach that is
  absolute metres, so the work is groups × reach-area and grows superlinearly by
  construction. Beating that means changing what a route means, not how it is computed.
- **`_searcher` returns scratch arrays** — they hold until the next call and no longer.
  Every caller in the module respects that, and the docstring says so in as many words, but
  it is a real hazard for whoever edits next: the negative control above drove a stale
  parent array into a cycle and `terrain_society.trace` walked it to 13.8 GB before it was
  killed.
- **The strand rate is untouched and still uncarded here.** A third of these groups never
  travel; see [CONTENT-BEAST-MOVEMENTS-STRANDED](../backlog/CONTENT-BEAST-MOVEMENTS-STRANDED.md),
  whose numbers this change does not move by a single group.
