# VILLAINS-NO-SCHEMA — two published contracts depend on a block that has no contract

Owner: none. State: open, unowned. Found by the bug-hunt session auditing `Contracts/schemas/`
against what the generator actually emits.

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

`Contracts/schemas/` (full listing), `Contracts/schemas/world-output.schema.json` (root
`additionalProperties: true`, seventeen declared properties), `Sim/icarus_sim/terrain_history.py`
`STATE_KEYS`, `Sim/icarus_sim/terrain_villains.py:140-202,318-344`,
`Sim/key_locations/core/world.py:92-103`, `Sim/icarus_sim/terrain_nomads.py:191-195,276-278`,
`docs/super-villains.md:1`, `tests/test_world_schema_conformance.py`.

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
