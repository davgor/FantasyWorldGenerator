# CORRUPTION-LEGACY-BASIS — a corrupted city's ruin claimed the region chose a hidden school

Owner: none. State: **CLOSED 2026-09-21 — verified in a generated world.** Found by the
bug-hunt session reading `terrain_corruption.py`; SUPER-VILLAINS, which wrote it, has closed.

## Requested behavior

A city unmade by a walking hidden god leaves a key point in that god's school, and the ruin's
`legacy.basis` says where the school came from. `source` means the destroyer chose it, `region`
means the local dominant magic did, `culture` means the ruined people's own school did.

## The defect

`terrain_corruption.corrupt()` built the legacy like this:

```python
legacy = ruin_legacy(city, cause, potencies, villain_school=god['school'])
legacy['school'] = god['school']
```

`cause` is `rot_plague` or `void_unmade`. Neither matches any branch in
`terrain_ruins.source_school`: `villain_school` is read **only** under
`cause.startswith('villain')`. So the argument did nothing, the call fell through to the
region's dominant school (or the culture's), and `basis` was set to `region` or `culture` on
the way. The next line then overwrote `school` with the god's and left `basis` untouched.

Every ruin a walking god ever made therefore carried a **hidden** school under a `region`
basis — an assertion that the region's dominant magic is rot or void. A region can never hold
one: hidden-school occurrence is locked to zero in the option registry, and this API is the
only thing in the codebase that ever puts a node in one
(`terrain_leyline_history.HIDDEN_SCHOOLS`). The document asserted something the generator
forbids.

`basis` has no code consumer today, which is why nothing caught it and why the blast radius is
bounded: `school` and `intensity` were both correct, so no world moved. It is wrong data in the
Unreal interchange artifact, not a wrong world.

## Why the suite was green

There was no coverage of this path at all. `Sim/tests/test_corruption.py` never mentioned
`legacy` or `basis` before this card. Proving anything about those four lines in place required
a generated villain world, a hidden god that happened to act at the chosen encounter count, and
that god's school to be one of the two that end a city rather than farm or take it — three
conditions, only the first of which a test could set.

## What was done

`corruption_legacy(city, cause, potencies, school)` is lifted out of `corrupt()` as a pure
function, stating the school and `basis: 'source'` explicitly and asking `ruin_legacy` only for
the class intensity that is genuinely its business. `corrupt()` calls it; the stale
`from .terrain_ruins import ruin_legacy` inside `corrupt` is gone with the call that needed it.

Three tests in `Sim/tests/test_corruption.CorruptionLegacyTests`, 36 ms, no world:

- the god is the source for both causes, over a region holding `umbral` at .9;
- intensity still follows city class, so nothing else was absorbed into the helper;
- **the regression proof** — `ruin_legacy(city, 'void_unmade', potencies(umbral=.9),
  villain_school='void')` returns a school that is *not* void, with `basis == 'region'`. That
  assertion fails on the old code path and is the defect stated as an executable fact.

Ran locally: 3 tests, OK. Nothing else was run; verification is centralised elsewhere tonight.

## Files and assets in scope

`Sim/icarus_sim/terrain_corruption.py`, `Sim/tests/test_corruption.py`. No schema change: the
`legacy` object is not declared anywhere in `Contracts/schemas/` — see `VILLAINS-NO-SCHEMA.md`,
which is the reason this could not have been caught by conformance either.

## Acceptance and evidence

`Sim/tests/test_corruption.py` passes whole, and a corruption ruin in a generated world carries
`legacy.basis == 'source'` with `legacy.school` equal to the acting god's school.

### The second half, run 2026-09-21

**It took a constructed world to reach, and the reason is worth recording, because it is
why this path had no coverage in the first place.** Which god acts is
`watching(world, encounters)[0]`, ranked by an interest read from the world and never
rolled. `interest('aberrant')` is `min(1., (aberrant + undead nests) / 24.)`, and a
seed-42 size-17 world carries 26 of them — so it saturates at 1.0, `god_shape_beneath`
wins every ranking, and its school is **eldritch**, which *takes* a city rather than
ending one and therefore leaves no ruin at all. Seeds 1, 5, 7, 42, 99 and 2024 all rank
eldritch or blood first; six age advances on seed 42 push `decay` to 0.879 and still lose
to a saturated 1.0; `nest_density` does not move the count and `nest_fantasy: 0.35` moved
it the wrong way.

The knob that works is `nest_fantasy: 0.0` — "zero leaves only animals" — which empties
the nest list and takes `aberrant` to 0. Two age advances then put `decay` at 0.625 above
`living` at 0.506, and `god_glad_mother` (rot) acts:

```
generate seed 42, recipe 3, size 17, phase 13, villain_rise 1.0, nest_fantasy 0.0
advance_age_request x2        cities 9, ruins 15
corruption_request encounters 60
  ACTED god_glad_mother school rot | ruins 6
  {"cause": "rot_plague", "id": "ruin-surface-city-0-95-human_large_island",
   "legacy": {"basis": "source", "intensity": 3.5, "school": "rot"}, "new_node_school": "rot"}
  ... and five more, every one basis 'source', school 'rot'
```

Six of six ruins carry `legacy.basis == 'source'` and `legacy.school` equal to the acting
god's school. **The claim is verified.** Before the fix these would have read `region` or
`culture` over a hidden school, which is the assertion the generator forbids.

### A second defect found while verifying it — NOT fixed here

The key point does not survive the call. `corrupt()` adds one node per ruin, id
`<ruin id>-key`, into the god's network, and then calls `rebuild_tail`. In the returned
world the rot network holds **four nodes — the corrupted cluster — and none of the six key
points.** The ruin *records* are correct, so this is again wrong data in the interchange
artifact rather than a wrong world, and it is the opposite end of the same seam: this card
fixed the ruin's description of a key point that is not there.

It is deliberately not fixed here. The card in front of me is about `legacy.basis`, the
mechanism is inside `rebuild_tail` — which an age transition and a visitation also run —
and touching it moves ley intensities and therefore worlds. Handed to the orchestrator as
a new finding; the reproduction above is the whole of it, and the saved world is
`scratchpad/work/rot_corrupted.json`.

## Documentation impact

`docs/corruption.md` describes the four failure modes but does not state what a rot or void ruin
records. If it gains a record-shape section, `basis: source` belongs in it. No existing sentence
is now false, so this is an addition rather than a correction.

## Adversarial review and limitations

The fix asserts the god is the source. The alternative reading — that a god's smite should carry
`DIVINE_INTENSITY` like a summoned visitation does, rather than the city-class intensity it gets
now — is **not** settled by this card and was deliberately left alone: changing intensity moves
leyline key-point strength and therefore the world. Whoever owns the corruption model should
decide it. The card changes only the field that was self-contradictory.

Second limitation: `corruption_legacy` now states `basis` rather than deriving it, so a future
cause that *does* match a `source_school` branch would be overridden here silently. Both current
causes are literals in `_failure_mode` a few lines above, so this is visible rather than hidden,
but it is a constraint the next editor inherits.

## Handoff

Found while tracing `VILLAIN-SCHOOL-DRIFT`'s `source_school` signature across its five callers.
The two defects are the same shape from opposite ends: one implementation dropped a parameter,
another passed one that the branch it needed was never going to read. Neither is catchable by a
seed-42 comparison, because both live on inputs the reference world does not produce.
