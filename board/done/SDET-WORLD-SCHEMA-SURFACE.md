# SDET-WORLD-SCHEMA-SURFACE — the published world contract describes ten of forty-eight blocks

Owner: none. State: **CLOSED. All four tests pass.** Ready to move to `board/done/`; left in
`backlog/` only because `board/README.md:31` links it here and that file belongs to another
lane this wave.
Evidence: `tests/test_world_schema_surface.py` — 4 tests, 4 pass, 0.009 s, no world generated.
`tests/test_world_schema_conformance.py` — 13 tests, 12 pass, 1 skip, 80.4 s, still green
against the tightened contract.

## What landed

`Contracts/schemas/world-output.schema.json`:

- `required` grew from 6 keys to 16 — the ten sections
  `test_world_schema_conformance.test_generated_world_exercises_every_versioned_section`
  already insists a generated world carries. The same list is now pinned a third time as
  `VERSIONED_SECTIONS` in `tools/validate_repo.py`, so the contract, the suite and the
  determinism gate fail together instead of disagreeing.
- The 37 undeclared `STATE_KEYS` blocks are declared, each with its JSON type and a one-line
  description; the nine with a schema of their own point at it, and `villains` and `humans`
  carry a pointer to the card that owns their outstanding defect.
- A root `description` states plainly that `required` describes a **completed** (phase 16)
  world and that a `--phase`-gated document is deliberately not described by this contract,
  and that `additionalProperties: true` is a decision rather than an oversight.

**The types were measured, not designed.** One world at the artifacts configuration
(`generate_request({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}})`, 76.3 s)
was generated and every top-level block's type recorded from it. Writing the stubs by reading
the emitters risks a stub the product violates.

**Two numbers in this card are now stale and are corrected here rather than rewritten below,
so the arithmetic that produced them stays auditable.** `STATE_KEYS` is **47**, not 48, and
the undeclared count was **37**, not 38: wave 1 removed `pending_ley_edits` (see
`board/done/SDET-LEY-QUEUE-NO-APPLIER.md`). The gap the card describes is unaffected.

Companion to `PRODUCT-BLOCK-REGISTRY` and `PRODUCT-CONFORMANCE-PROOF-UNCHECKED`, which argue
this in prose. This is the executable half.

## The defect

`tests/test_world_schema_conformance.py:34` validates a generated world against
`world-output.schema.json` and passes, which reads as "the published contract matches the
product". It does not establish that, because passing is close to unconditional.

The schema has `additionalProperties: true`, declares 17 properties and requires 6. Three of
the six are constants; of the other three, `config` and `layers` declare no required keys at
all and `recipe` requires four sub-keys that may be empty objects. So this document conforms:

```
{"schema": "fantasy-world-generator.world", "schema_version": 2, "generator_version": 16,
 "config": {}, "layers": {},
 "recipe": {"version": 3, "seed": 0, "resolved": {}, "provenance": {}}}
```

**No terrain grid, no settlements, no people, no plans.** It is a conforming world.

And `STATE_KEYS` carries 48 blocks across an age boundary of which the contract declares 10.
**38 arrive unannounced and unvalidated** through the open root, including `heroes`, `npcs`,
`nomads`, `key_locations`, `villains`, `story_web`, `magic`, `humans`, `ruins`, `roads`,
`water`, `climate`, `threat_assessments` and `encounters`.

`STATE_KEYS` is used as the denominator on purpose: it is the simulation's own answer to what
a block is, and it is maintained by whoever adds one, so the test tracks the product instead
of a list copied into a test that goes stale.

### The sharpest form is an internal contradiction, not a coverage count

`test_world_schema_conformance.test_generated_world_exercises_every_versioned_section`
asserts a real world carries ten named sections — `terrain`, `settlements`, `civilizations`,
`city_plans`, `hamlet_plans`, `castle_plans`, `world_scene`, `astrology`, `lunar_almanac`,
`religion`. **The published contract requires none of them.** The requirement was written
into a test instead of into the contract, so the consumer who reads the contract never sees
it. That test's own docstring concedes the point: *"A conformance pass is only meaningful if
the sections are actually present."*

Two documents in the same repository disagree about what a world is, and both are green.

### And the one world it is validated against is the degenerate corner

`test_world_schema_conformance` builds seed 42 at size 17 — "small enough to stay quick,
large enough to populate every planner section". It is not large enough for the terrain.
**This table is a property of the generator, not of a seed, a preset or a planet.** Octave
admission keeps octave `k` when `wavelength / 2^k >= 2 * step`, and on the recipe path both
terms carry the radius — `wavelength = radius*1.6/sqrt(plate_count)`
(`terrain_recipes.py:23`), `step = 2*pi*radius/(size-1)`. The radius cancels:

```
wavelength / step  =  1.6 * (size - 1) / (2 * pi * sqrt(plate_count))
```

So admission depends only on grid size and plate count, and `plate_count` is drawn from
`9..15`. Evaluated over every combination of that range with the small, medium and large
radii — 28 configurations — there is **exactly one** resulting table:

Values below are `resolved_octaves`' own `cell_step_m`, the **equatorial step**
`2*pi*radius/(size-1)` that the admission filter compares against, at `globe_radius`
10000.0 m. That is not the same quantity as a cell's edge length on an equal-area grid
(`2*radius*sqrt(pi)/size`); both are legitimate and mixing them produces wrong ratios, so
the filter's own is the one quoted here.

| size | octaves kept | equatorial step |
|---|---|---|
| 17 | **0 of 5** | 3927.0 m |
| 33 | 1 of 5 | 1963.5 m |
| 65 | 2 of 5 | 981.7 m |
| 129 | 3 of 5 | 490.9 m |
| 257 | 4 of 5 | 245.4 m |
| 513 | 5 of 5 | 122.7 m |
| 1025 | 5 of 5 | 61.4 m |

**The reference world every test in this repository validates against has no surface noise
at all** — zero of five octaves survive the Nyquist filter. And because the radius cancels,
that is not a fact about seed 42 or about the small preset: **no world this generator can
produce resolves any surface noise at size 17, and none resolves all five below 513.** A
contract validated only at 17 has been validated against the least featured world the
generator is capable of, which is a second reason the pass at
`test_world_schema_conformance.py:34` reads as more than it is: not only does the schema ask
for almost nothing, the single document it is asked about is the emptiest one available.

Four sessions derived this table independently — from `terrain_scale`, from
`default_config`, from world files on disk, and from the raw formula — and agreed. The
algebra above is why they could not have disagreed, which is worth more than the agreement:
four matching results from one invariant are one result, not four.

Note for whoever plans the widened runs: **513 is where the noise story completes.** All
five octaves already resolve there, so 1025 buys a finer cell step and no additional
octave. Whatever justifies 1025 over 513, it is not surface noise.

**A comment to qualify, now reconciled.** `terrain_world.py:271-278` cites "this planet's
14,702 m wavelength" as the basis for the fifth octave admitting at 513. That figure is
correct — it is the **large** radius at `plate_count` 12 — while the recipe-3 small world
derives 4824.2 m. Neither is wrong; the comment is under-specified, because it says "this
planet" without saying which, and a reader on a small world who recomputes other sizes from
14,702 m gets crossovers their generator will not produce. Given the cancellation above the
comment does not need a wavelength at all: the crossover is the same for every planet, and
citing one planet's figure invites exactly the arithmetic that makes it look wrong.

## Proposed mechanism

**Not proposed.** The range runs from closing the root and declaring every block, to
declaring nothing and saying plainly that the schema is an envelope check rather than a
contract. Either is defensible; the current state is the one that is not, because it reads as
the first and behaves as the second. `PRODUCT-BLOCK-REGISTRY` argues the shape; this card
only fixes the acceptance bar.

## Dependencies and unresolved decisions

- Whether every block should be *required* or merely *declared* is undecided, and the two
  failing tests are deliberately split along that line so the decision can be taken once and
  applied to each separately.
- Declaring 38 blocks means writing 38 shapes, several of which have no canonical
  documentation yet. `villains` has no schema at all — see `VILLAINS-NO-SCHEMA.md`.
- Phase-gated blocks are absent from a low-phase world by design, so "required" cannot mean
  unconditionally required without a phase discriminator. Nobody has decided how that is
  expressed.

## Sources consulted

- `Contracts/schemas/world-output.schema.json` — `additionalProperties: true`, 17 properties, 6 required.
- `tests/test_world_schema_conformance.py:34` — the pass that reads as coverage.
- `Sim/icarus_sim/terrain_history.py:406` — `STATE_KEYS`, the 47-block denominator.
- `Sim/icarus_sim/terrain_scale.py:91-104` — the octave admission filter, computed not read.
- `board/backlog/PRODUCT-BLOCK-REGISTRY.md` — the prose argument.

## Files and assets in scope

`Contracts/schemas/world-output.schema.json`, `tests/test_world_schema_conformance.py`,
`docs/unreal-integration.md`, `docs/publishing.md`.

## Acceptance and evidence

`tests/test_world_schema_surface.py` passes unmodified:

1. a document with only the required keys and no content is rejected;
2. the schema requires the sections the conformance suite asserts are present;
3. every block in `STATE_KEYS` is at least declared.

The control must keep passing: the validator rejects a retired `schema_version` and a
document missing a required key. Without it, all three failures are indistinguishable from a
validator that never objects to anything.

## Documentation impact

`docs/unreal-integration.md` points consumers at this schema. If the resolution is "envelope
check, not contract", that document must say so in the same change, because its audience is
generating import code from it.

## Adversarial review and limitations

- **Not established:** that any of the 38 undeclared blocks would *fail* validation against a
  schema that described them. The claim is that the contract does not describe them, not that
  the product disagrees with a description that does not exist. Do not cite it as the latter.
- `STATE_KEYS` is a reasonable denominator and not an authoritative one. It is what the sim
  carries across an age, which is not identical to what a consumer is handed — `build_stages`
  is dropped by the CLI, for instance. The count would move slightly under a different
  definition; the gap would not.
- **Three of these tests passed on first run and were wrong.** `schema_subset.errors` is a
  generator, so `assertTrue(errors(...))` is true whether or not it would yield anything —
  and the positive control passed too, because it called `errors()` the same way. A control
  only guards against failure modes it does not share. Anyone hand-running a validation here
  must materialise the generator; `validate()` is safe because it consumes it.

## Handoff

The lead came from the product red-team session, whose original form — "17 properties, 6
required, passes on a world missing 38 blocks" — was corrected on one point before filing:
`recipe` requires four sub-keys of its own, so a bare six-key stub is rejected and a reviewer
trying that one-liner would have got a green and stopped reading. The corrected minimal
document is above. That session has recorded the correction in its own cards.
