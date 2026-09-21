# VILLAINS-NO-SCHEMA — two published contracts depend on a block that has no contract

Owner: villains session. State: **closed 2026-09-21.** The headline defect did not
reproduce — the schema had already been published by another lane — but the card's own
acceptance had not been met and is delivered here. See "What was actually there" and
"Delivered" at the foot. The policy question the card raises underneath the defect is
answered in [decision 029](../../docs/decisions/029-core-emitted-blocks-carry-their-own-schema.md),
which `PRODUCT-BLOCK-REGISTRY` is waiting on.

Found by the bug-hunt session auditing `Contracts/schemas/` against what the generator
actually emits.

## The defect

`Contracts/schemas/` holds fourteen schemas. Every top-level block written by a separate reader
package has one — `hero-generator`, `story-web`, `npc-roster`, `key-locations`,
`key-location-plans`, `nomads`, `beast-movements`, `encounters` — and each is validated against
real output by a test.

`villains` has none. It is emitted by the core, it carries `version: 1`, it is in `STATE_KEYS`,
`docs/super-villains.md` opens with the words "villains schema 1" — and there is no schema file
anywhere that describes it.

**It is not alone, and that changes what this card is asking for.** The conformance session
independently confirmed the same absence for `religion`, `astrology`, `threat_assessments`,
`wildlife` and `heritage`. Six core-emitted blocks have no contract between them, so the real
question is a policy one — do the core's own blocks get schemas, or do they live under
`world-output.schema.json`'s open root by design? — and `villains` is the case that forces it,
because it is the only one of the six with published contracts already depending on it.

It is not covered by `world-output.schema.json` either. That document declares seventeen
top-level properties and sets `additionalProperties: true` at the root, so an emitted block it
has never heard of validates silently. Thirty-eight of the forty-eight `STATE_KEYS` blocks are
undeclared there; most of those have their own schema, which is the intended arrangement.
`villains` is the one that has neither.

## Why it matters more than the count suggests

Two published schemas already reference villain-derived fields:

- `Contracts/schemas/key-locations.schema.json`
- `Contracts/schemas/nomads.schema.json`

So the repository publishes contracts for data **derived from** a block whose own shape is
unspecified. A consumer can validate the derived records and has nothing to validate the source
against. `key_locations.core.world.villain_holdings` reads `people[].direction` and
`people[].claims[]`; `terrain_nomads` reads `people[].claims[]`, `people[].school` and
`people[].tier`. None of those field names is written down as a contract anywhere.

`tier` is the sharpest case. It is a **float**, and `reach_m = tier × REACH_SPACINGS_PER_TIER ×
spacing` makes it a physical quantity in metres once multiplied — not a rank. `terrain_nomads.py:277`
reads it as `strength = max(1., float(...))`, a multiplier. `key_locations` reads villain
proximity into a `threat`. The word `tier` already means four different things across this
codebase (see the coordinator's collision list), and this is the one instance of it that no
schema pins.

## Proposed mechanism

Author `Contracts/schemas/villains.schema.json` describing the block as it is emitted today —
`version`, `people[]`, `tiers{}`, `outlook{}`, `works[]` — and validate a generated villain world
against it, the way `tests/test_world_schema_conformance.py` validates the other blocks. Units go
in the descriptions: `tier` is a dimensionless continuous band whose product with
`REACH_SPACINGS_PER_TIER × settlement_spacing` is metres, and `reach_m` is metres.

Two constraints on whoever writes it:

- **Describe, do not design.** The block's author is gone; a schema that tightens the shape is a
  behavior change made by the person least equipped to make it. Anything the emitter can produce
  must validate, including the fields this card argues about elsewhere.
- Decide `additionalProperties` deliberately per container rather than by habit. An open container
  is what let `npc-roster`'s `summary` declare six counters against eight emitted with a green
  suite; a closed one on a block still under design fails the moment someone adds a field. State
  the reason in the schema's description either way.

Sequence this **before** `VILLAIN-FALL-UNRECORDED.md`, whose option 2 adds a key to this block.

## Dependencies and unresolved decisions

- `Contracts/` is the conformance session's neighbourhood; this card should be routed there rather
  than picked up unilaterally. It is written as a gap report, not as a licence to edit schemas.
- Open: whether `villains` should be schema'd at all, or whether the core's own blocks are meant
  to live under `world-output.schema.json`'s open root by policy. If that is the policy it is
  undocumented, and `docs/super-villains.md` calling itself a schema contradicts it.

## Sources consulted

One citation per line, re-anchored to the tree on 2026-09-21, so a stale anchor names the
claim it broke rather than its neighbours. The counts in the body above are the ones this
was found at and no longer reproduce; see "What was actually there" below.

- `Contracts/schemas/` — full listing, 25 files.
- `Contracts/schemas/world-output.schema.json` — the open root and the per-block declarations.
- `Sim/icarus_sim/terrain_history.py:409` — `STATE_KEYS`.
- `Sim/icarus_sim/terrain_villains.py:295-429` — `advance`, which writes the block.
- `Sim/icarus_sim/terrain_villains.py:645-696` — `claim_settlements`, which writes `claims`.
- `Sim/key_locations/core/world.py:92-103` — `villain_holdings`, one of the two consumers.
- `Sim/icarus_sim/terrain_nomads.py:191-195` — the cultist gate, the other consumer.
- `docs/super-villains.md` — which called itself the schema and now points at one.
- `tests/test_world_schema_conformance.py` — where the block is now validated.

## Files and assets in scope

New `Contracts/schemas/villains.schema.json`; `tests/test_world_schema_conformance.py`;
`docs/super-villains.md` gains the pointer.

## Acceptance and evidence

A generated world with `villain_rise` above zero validates against the new schema, and the
conformance suite fails if a field is emitted that the schema does not describe — in **both**
directions, which is the property the open-container exposure currently denies.

## Documentation impact

`docs/README.md` indexes the contracts; the new schema belongs in `Contracts/README.md` beside the
others. `docs/super-villains.md` should point at the real schema rather than being one.

## Adversarial review and limitations

This card reports an absence, which is cheap to state and easy to overvalue. The block is not
broken for lack of a schema — it has tests, and its two consumers work. What it lacks is the
failure mode the other eight blocks have: a change to the emitter that a consumer's contract does
not expect cannot fail here, because there is nothing to fail against.

Counter-argument worth weighing before acting: the `villains` shape may still be genuinely
unsettled, and freezing an unsettled shape into a published contract is its own cost. If so, the
honest output is a recorded decision saying "not yet, because —", not a schema. Either resolves
this card; silence does not.

## Handoff

Found by enumerating every object container in `Contracts/schemas/` that accepts undeclared keys
(116 open, 22 closed) and then diffing declared top-level properties against `STATE_KEYS`. The
container enumeration itself is the coordinator's open-container audit item and is being handed to
the conformance session separately — it needs one generated world to complete the
emitted-versus-declared half, which this session did not run.

## What was actually there — villains session, 2026-09-21

The premise was re-tested by running it rather than by re-reading the card. **Two of its
three measurements no longer reproduce.**

1. **`Contracts/schemas/villains.schema.json` already existed, and was committed.** It is
   not in `git status`, so it was landed and committed by another lane before this session
   opened the card. The headline — "there is no schema file anywhere that describes it" —
   is false against this tree.
2. **`world-output.schema.json` declares all 49 `STATE_KEYS` blocks, not seventeen.** The
   card's "thirty-eight of the forty-eight are undeclared" is stale; another lane widened
   the root from 17 declared properties to 56.
3. **The finding that survives is a different one, and it is sharper.** Declaring is not
   describing. The root is still `additionalProperties: true`, and the per-block
   declarations are of wildly uneven depth: `settlements` five levels down, `religion` one,
   and `villains`, `threat_assessments`, `wildlife`, `magic` and `ruins` are
   `{"type": "object"}` with a sentence of prose. A block declared as a bare object
   validates whatever it happens to contain.

**And the card's own acceptance had not been met by the lane that wrote the schema.** The
acceptance is two-directional: a generated world validates against it, *and* the suite
fails if a field is emitted that the schema does not describe. Measured before this work:

- nothing anywhere validated a world against `villains.schema.json` — `grep -rn "villains"
  tests/test_world_schema_conformance.py` returned nothing;
- neither `Contracts/README.md` nor `docs/README.md` mentioned it;
- `world-output.schema.json`'s `villains` description still read "This block has NO schema
  of its own ... see board/backlog/VILLAINS-NO-SCHEMA.md", pointing at this card;
- every object container in it was open, so the reverse direction — the property the
  acceptance actually names — did not exist.

## Delivered

**Three tests in `tests/test_world_schema_conformance.py`**, all of which failed before the
work and pass after:

- `test_generated_world_carries_a_valid_villains_block` — a generated world's block against
  the contract, plus the joins the two derived contracts make.
- `test_the_villains_schema_describes_a_fallen_reign_as_well_as_a_standing_one` — the half a
  default world never reaches: `status: 'fallen'`, `fell_age`, the `villains.fallen` mark
  and a claim carrying its holder's fall. Driven directly, in milliseconds, at the declared
  default `villain_hold` rather than at the `hold=99.` the unit tests use as an instrument.
- `test_the_villains_schema_fails_in_the_direction_an_open_container_cannot` — guard the
  guard: an undeclared `menace` on a person and an undeclared `dread` on an outlook row must
  both be reported.

**The schema moved to version 2** in the same change, because the emitter did — see
`SDET-VILLAIN-FALL-UNREACHABLE` and `VILLAIN-CLAIM-FROZEN`. Every container in it is now
closed and every key sets was read off a generated world advanced far enough to produce a
fall, not off the source: `$defs` for the claim, log entry and well, so the roster record
and the durable mark describe the same shapes rather than two drifting copies.

**Closed containers are a deliberate departure** from the rest of `Contracts/`, and the
reason is stated in the schema's own description: nothing *sends* this block, so the failure
it has to catch is not a consumer supplying something unexpected but the emitter growing a
field no contract mentions — exactly what an open container cannot catch, and exactly what
let `npc-roster`'s `summary` declare six counters against eight emitted with a green suite.

**Pointers**: `Contracts/README.md` gains a Villains v2 paragraph, `docs/README.md` points
at the schema, `world-output.schema.json`'s description no longer claims the block has no
contract, and `docs/super-villains.md` — which opened with the words "villains schema 1" —
now opens by saying the schema is the contract and this page is not.

### The policy answer, which another agent is waiting on

[029 A core-emitted block carries its own schema](../../docs/decisions/029-core-emitted-blocks-carry-their-own-schema.md).
A core-emitted top-level block gets its own schema, validated against a generated world in
both directions, when another published contract derives records from it or a consumer
outside the generator reads it. `world-output.schema.json` keeps its open root: it is the
index of what a world contains and where a version constant is pinned, not where a block is
described. Emitted blocks close their containers; request schemas do not.

**What 029 does not do is schedule the other four.** `threat_assessments`, `wildlife`,
`magic` and `ruins` qualify under the rule and each needs its own owner, because "describe,
do not design" requires someone who knows what that emitter can produce. `religion` and
`astrology` are partly described already. `heritage` is emitted by a package, not by the
core, and is not a `STATE_KEYS` block at all.

### The counter-argument, answered

The card's own adversarial section warns that freezing an unsettled shape into a published
contract is its own cost. That is answered by the version integer rather than by silence:
the `villains` shape moved the same day it was contracted, 1 to 2, and the contract moved
with it. That is the mechanism working.

### Ablation — the contract checked against its own removal

A validation test is green from birth and can never be watched to flip, so each was re-run
with the thing it checks taken away:

| Ablation | Result |
|---|---|
| every `additionalProperties: false` stripped from the schema (10 containers) | `test_the_villains_schema_fails_in_the_direction_an_open_container_cannot` goes **red** |
| `terrain_villains.VERSION` bumped to 3 with the schema left at 2 | `test_the_villains_schema_describes_a_fallen_reign_as_well_as_a_standing_one` goes **red** on `/version: expected 2, found 3` |

`test_generated_world_carries_a_valid_villains_block` builds a world in `setUpClass`, so
ablating it costs a four-minute generation per variant. **The same two ablations were applied
offline instead**, to the real `villains` block saved from the six-age run through
`terrain_history`, through the same `schema_subset.errors` the test calls: the real block is
green against the published schema, red at version 3, red when an undescribed `menace`,
`dread` and `curse` are added — and **green again once the containers are reopened**, which
is the ablation that matters and the property the card asked for. That last line is the whole
reverse direction in one measurement.

**One harness bug found by doing this, and it is the failure mode the exercise exists to
catch.** The version ablation first reported the test as *passing*. `VERSION = 2` and
`VERSION = 3` are the same number of bytes, and the rewrite landed in the same second as the
restore before it, so CPython's `(mtime, size)` check called the cached `.pyc` current and
the unablated module ran. An ablation that silently did nothing would have been reported as
evidence the test was sound. The harness now clears `__pycache__` before every run.

### Two failures in this module that are NOT this card's

`tests/test_world_schema_conformance.py` is not fully green on this tree, and the two
failures were isolated rather than assumed: re-run in a copy of the tree with
`terrain_villains.py` reverted to `HEAD`, **both still fail**, so neither is this work's.

- `test_generated_world_carries_a_valid_heroes_block_only_from_stage_sixteen` —
  `'fortress-node-190' not found in {'fortress-3', ...}`. A fortress id is node-keyed on one
  side of the join and an ordinal on the other; that is `SDET-SITE-ID-ORDINALS`, in flight.
- `test_generated_world_carries_valid_travelling_groups_only_from_stage_sixteen` — a
  beast-movements count divergence (`683 != 756`), and in the reverted copy a
  `route_status: 'solitary' is not one of ['routed', 'stranded']` schema error instead. In
  flight in the movements lane.

All three villains tests pass in the same module against a real generated world.
