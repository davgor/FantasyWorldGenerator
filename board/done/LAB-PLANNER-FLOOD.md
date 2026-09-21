# LAB-PLANNER-FLOOD — A regional proxy was refusing two thirds of the cities

Status: done. Owner/session: local lab session, 2026-09-21.

## The defect

Three planners shared one line. The hamlet planner's read:

```python
code = 1 if v['water'] else 2 if v['slope']>25 else 0                 # hamlet_planner.py
code = 1 if v['water'] else 2 if v['slope']>25 or v['flood']>.65 ...  # city_planner, castle_planner
```

with this comment above the hamlet one, already in the tree: *"Coarse flood_risk is a
regional layer, not a local inundation mask; coasts would otherwise be empty."*

`flood_risk` is emitted as 0 or 1 — 958 cells at 0.0 and 131 at 1.0 in a seed-42 size-33
world, nothing between. A city footprint is 640–800 m; one regional cell at that size is
3125 m. So the whole footprint reads a single sample, and on a 1.0 cell every cell of it
became code 2, `valid` emptied, no shape was eligible and the plan came back
`No suitable shape · unbuildable`. The failing sites were on ground of 0.6°–20°, well
inside the 25° limit — slope was never the reason.

The natural experiment was already in the repo: same terrain, same sampler, one clause
different.

| planner | clause present | unbuildable, seed 42 size 33 |
|---|---|---|
| hamlet | no | 0 of 116 |
| city | yes | 23 of 35 |
| castle | yes | 34 of 56 |

`Core/cityplanner.cpp:850` and `Core/castleplanner.cpp:985` carry the same rule and still
do. Under [027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md) that
divergence is not a defect and not tracked; the native port is a full rewrite at the end
of the project.

## The fix

The sampler returned one `flood` field that meant two incompatible things — a local river
mask when a routed centerline was near, the regional proxy otherwise — and a caller could
not tell which it had. It now returns two:

- `channel`: 1 inside the reserved 24 m river channel and 28 m setback, measured in local
  metres. This still blocks, in all three planners.
- `flood_risk`: the regional proxy, carried for information and read by no rule.

Dropping the ambiguous key rather than leaving it meant every consumer had to be found,
which is how the second defect surfaced (below). `planner_version` moves in Python only:
city 6→7, castle 1→2, hamlet 2→3. Nothing was changed in `Core/`; see Limitations.

**A second defect, found by the rename.** `hamlet_planner` imports `city_planner._sampler`,
so the rename broke it — seven errors. The break was worth having: its cell mask had
excluded the regional proxy since version 1, but the gate deciding whether a plot reaches
a street still required `flood <= .65` at `hamlet_planner.py:160`. On a flood_risk=1 cell
the mask admitted the ground and the gate then refused every plot standing on it. Both
now read `channel`.

## The co-siting defect, fixed with it

28 of 56 fortresses in the same world shared their exact node with a hamlet, so a keep
drew on top of a house and two settlements occupied one place. Not mislabelling: `kind` is
correct on every record.

`terrain_humans` places hamlets and forts against a shared `occupied` list and a
great-circle `separated()` test, and honours it. Coastal harbours are raised later, by
`terrain_society`, against its own set — `{cities} | {hamlets}`, with the forts left out.
One line, in Python only. Rural report 8→9, and
`terrain_history.validate_age_world` moves with it, so a world carrying the old placement
is refused rather than advanced.

It went unseen because `test_hinterland_invariants_and_stage_isolation` already asserts
exactly this uniqueness — at phase 9, which is before the pass that breaks it.

## Evidence

Seed 42, before and after, both sizes:

| | 16 × 16 before | 16 × 16 after | 32 × 32 before | 32 × 32 after |
|---|---|---|---|---|
| unbuildable cities | 3 of 12 | **0 of 12** | 23 of 35 | **0 of 35** |
| unbuildable castles | — | **0 of 17** | 34 of 56 | **0 of 56** |
| forts sharing a hamlet node | 12 of 17 | **0** | 28 of 56 | **0** |

The three cities reported from the lab all build now: Korweg (Age 2), medium, market grid,
92 plots; Andonael, medium, ceremonial clusters, 16 plots; Linmor (Age 1), small,
courtyard lanes, 47 plots.

- `Sim/tests/test_city_planner.py`, `test_castle_planner.py`: a saturated regional
  `flood_risk` with no river must not disqualify the site. Both fail on the old rule.
- `test_routed_river_reserves_corridor_instead_of_entire_world_cell` still passes, which
  is what shows the setback was preserved rather than relaxed along with the proxy.
- `Sim/tests/test_terrain_humans.py`: the phase-9 uniqueness invariant, asserted at phase
  16 where the harbour pass has run.
- 84 tests across the four planner and roster suites pass.
- The committed sample was rebuilt against the fix and re-verified from the served page.

## Limitations

- **This change touches no C++, and that is deliberate.** This session first wrote the fix
  into `Core/cityplanner.cpp`, `castleplanner.cpp`, `hamletplanner.cpp` and `society.cpp`
  before reading [027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md),
  whose point 3 forbids speculative C++ and whose point 2 says Core's divergence from
  Python is not a defect and not tracked. Reverting was briefly impossible: a HARD
  `VERSION-MIRROR` binding tied each planner's Python constant to `Core/*.hpp
  planner_version`, so a revert failed `docs_check` — a gate that was, in one stroke,
  treating native divergence as a defect, tracking it, and holding a change on it, which is
  the three things 027 point 2 says it is not. The three clauses were removed as 027
  follow-through by the session doing that work, and the mirrors were then reverted
  wholesale. Core sits at planner 6 / 1 / 2 against Python's 7 / 2 / 3 and will be rewritten
  whole when the port is scoped. No compiler exists on this machine either way.
- Worlds built by the older planners carry the refusals and the co-sited harbours and must
  be regenerated; age advancement now refuses a rural report below 9.
- `flood_risk` itself is still a binary layer published as "relative 0–1". Nothing here
  changes that, and no card owns it.
- The hamlet count in the sample falls from 116 to 98: harbours that used to be founded on
  a fortress node now have to find other ground or go unplaced. Whether a refused harbour
  should retry further along the coast is a product question this does not answer.
