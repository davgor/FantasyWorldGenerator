# 029 — A core-emitted block carries its own schema

## Status

Accepted for `villains`, 2026-09-21, and delivered with it. **Proposed for the other four
core blocks named below**, which are not this session's to schedule: `describe, do not
design` requires someone who knows what the emitter can produce, and that is the block's
owner. `PRODUCT-BLOCK-REGISTRY` is waiting on this answer and should read it as the rule,
not as four completed schemas.

## Context

`VILLAINS-NO-SCHEMA.md` reported an absence and asked a policy question underneath it: do
the core's own blocks get schemas, or are they meant to live under
`world-output.schema.json`'s open root by design? The card was right that `villains` is the
case that forces it, because it is the one block with no contract that two published
contracts already derive records from.

Measured against the tree on 2026-09-21, not quoted from the card, which is stale in two
places:

- `Contracts/schemas/` holds 25 files. Every top-level block written by a separate reader
  package has one — `hero-generator`, `story-web`, `npc-roster`, `key-locations`,
  `key-location-plans`, `nomads`, `beast-movements`, `encounters` — and each is validated
  against real output by `tests/test_world_schema_conformance.py`.
- `world-output.schema.json` now declares **all 49** `STATE_KEYS` blocks, not seventeen of
  them. The card's "thirty-eight undeclared" no longer reproduces.
- **Declaring is not describing, and that is the finding that survives.** The root is still
  `additionalProperties: true`, and the declarations are of wildly uneven depth:
  `settlements` is described five levels down, `religion` one level, and `villains`,
  `threat_assessments`, `wildlife`, `magic` and `ruins` are `{"type": "object"}` with a
  sentence of prose. A block declared as a bare object validates whatever it contains. The
  absence the card reported is real; the shape of it moved.

So the honest statement of the gap is not "six blocks are undeclared" but "five core blocks
are declared to a depth that asserts nothing": `threat_assessments`, `wildlife`, `magic`,
`ruins` and, until this decision, `villains`. `religion` and `astrology` are declared one
and two levels deep, which is more than nothing and less than a contract. `heritage` is
emitted by a package rather than by the core and is not a `STATE_KEYS` block at all.

## Decision

**A core-emitted top-level block gets its own schema in `Contracts/schemas/`, validated
against a generated world by `tests/test_world_schema_conformance.py`, when either of these
is true:**

1. another published contract derives records from it, or
2. a consumer outside the generator reads it.

`world-output.schema.json` keeps its open root and its per-block declarations. It is the
index of what a world contains and the place a version constant is pinned; it is not where
a block is described. A block's own file is.

**Two subsidiary rules, because the villains case exposed both.**

- **An emitted block closes its containers.** Nothing *sends* a generated block: the
  generator is its only writer, so the failure it has to catch is not a consumer supplying
  something unexpected but the emitter growing a field no contract mentions — exactly what
  an open container cannot catch. `npc-roster`'s `summary` declared six counters against
  eight emitted with a green suite. A **request** schema is the opposite case and keeps its
  containers open where it already does.
- **Describe, do not design.** The key sets in `villains.schema.json` were read off a
  generated world advanced far enough to produce a fall, not off the source and not off an
  opinion about what the block ought to hold. A schema that tightens a shape is a behaviour
  change made by whoever is least equipped to make it.

## What this does not decide

It does not schedule `threat_assessments`, `wildlife`, `magic` or `ruins`. Each needs its
own owner to enumerate what its emitter can produce, and each will surface its own version
question on the way. The rule above says they qualify; it does not say when.

It does not touch `religion` or `astrology` beyond noting they are partly described. Bringing
them to the bar is the same work at a lower cost.

## Consequences

- `villains` is contracted at version 2 and validated in both directions, so a field the
  generator grows and nobody describes now fails a test.
- Any future core block that two other contracts derive from is a schema, not a paragraph.
- The counter-argument the card raised — that freezing an unsettled shape into a published
  contract is its own cost — is answered by the version integer rather than by silence. The
  `villains` shape moved the same day it was contracted, from 1 to 2, and the contract moved
  with it. That is the mechanism working, not an argument against having one.
