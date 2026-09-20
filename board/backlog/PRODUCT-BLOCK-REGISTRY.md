# PRODUCT-BLOCK-REGISTRY — the world contract lists no blocks, so nothing can be missing

Owner: none. State: open, unowned. Found by the product red team auditing `233182e` for what a
consumer receives versus what the contracts declare.

## Requested behavior

One machine-readable registry of every top-level block the generator publishes, naming for each:
its schema (or an explicit recorded reason it has none), its version binding, its owning package,
and the stage from which it is present. `tests/test_world_schema_conformance.py` fails when the
generator emits a block the registry does not list, and when the registry lists a block a
reference world does not carry.

## The defect

`Sim/icarus_sim/terrain_history.py:398` publishes **48** top-level blocks.

| | count |
|---|---|
| top-level blocks in `STATE_KEYS` | 48 |
| declared in `Contracts/schemas/world-output.schema.json` | 10 |
| carrying a schema file of their own | 8 |
| **neither declared nor schema'd** | **30** |

The envelope declares seventeen properties, `required` is six, and the root is
`additionalProperties: true`. Of those six only `recipe` has required contents of its own —
`version`, `seed`, `resolved`, `provenance` — while `config` and `layers` declare no required keys,
so `{}` satisfies both. The minimal conforming world is therefore:

```json
{"schema": "fantasy-world-generator.world", "schema_version": 2, "generator_version": 16,
 "config": {}, "layers": {}, "recipe": {"version": 3, "seed": 0, "resolved": {}, "provenance": {}}}
```

**No terrain grid, no settlements, no people, no plans — and it conforms.**
`tests/test_world_schema_conformance.py:34` validates a generated world against exactly that
document. The suite then validates the eight reader-package blocks individually. That is real
coverage and it is the whole of it.

**The contradiction is sharper than the coverage gap.**
`test_generated_world_exercises_every_versioned_section` asserts that a real world carries ten named
sections — `terrain`, `settlements`, `civilizations`, `city_plans`, `hamlet_plans`, `castle_plans`,
`world_scene`, `astrology`, `lunar_almanac`, `religion`. The published contract requires none of
them, and its docstring concedes the reason: *"A conformance pass is only meaningful if the sections
are actually present."* The requirement was written into the test instead of into the contract, so
the consumer who reads the contract never sees it.

The consequence for a consumer is not that a block is wrong. It is that **absence is
unrepresentable**. A downstream reader cannot distinguish a block that was never built, a block
that failed and reported `status: failed`, a block gated off by an environment variable, and a
block whose emitter broke this morning. All four validate.

The checker's own author wrote the general form at `tools/docs_check.py:11-15`: "verifying a block
validates against its schema says nothing about fields the schema never declared." The gate knows.
The contract has not caught up.

## Correction to an existing card

`board/backlog/VILLAINS-NO-SCHEMA.md` states that of the thirty-eight blocks undeclared by the
envelope, "most of those have their own schema, which is the intended arrangement." **Eight of
thirty-eight do.** That card's own opening paragraph enumerates exactly those eight and describes
them correctly as the blocks written by a separate reader package; the error is the generalisation
from eight to most. Its conclusion stands and its policy question is the right one — it is a
thirty-block question rather than a six-block one, which is the reason to answer it with a registry
instead of one schema at a time.

## Proposed mechanism

`Contracts/blocks.json`, schema 1, one row per published block:

```json
{"key": "nomads", "schema": "Contracts/schemas/nomads.schema.json",
 "version_binding": "nomads", "owner": "Sim/icarus_sim/terrain_nomads.py",
 "present_from_stage": 16, "optional": true, "reason_if_unspecified": null}
```

`reason_if_unspecified` is the honest escape hatch and the point of the exercise: a block may
legitimately have no schema while its shape is unsettled, and `VILLAINS-NO-SCHEMA` argues
persuasively that freezing an unsettled shape is its own cost. The registry does not force a schema.
It forces the absence to be **stated once, in one place, with a reason**, instead of being
discoverable only by diffing a constant against a directory listing.

Then extend `test_generated_world_satisfies_the_published_world_schema` in both directions:
emitted-but-unregistered fails, registered-and-required-but-absent fails.

Explicitly **not** proposed: closing `additionalProperties` on the envelope root. That is a
compatibility decision with its own cost and it belongs to whoever owns `Contracts/`.

## Dependencies and unresolved decisions

- Routes to whoever owns `Contracts/` — the conformance session's neighbourhood. This card is a gap
  report, not a licence to edit schemas.
- Depends on the open-container policy question in `VILLAINS-NO-SCHEMA`; sequence that card's
  ruling first or take both together, since the registry's `reason_if_unspecified` column is where
  that ruling would be recorded.
- Unresolved: whether `STATE_KEYS` membership is the right definition of "published". It is the
  stage-snapshot list, and `materialize_stage` builds output from keys *not* in it
  (`terrain_history.py:476`), so the two concepts are related but not identical. Whoever takes this
  should settle that first — it may move the 48.

## Sources consulted

`Sim/icarus_sim/terrain_history.py:398,476`; `Contracts/schemas/world-output.schema.json`
(root `additionalProperties: true`, `required` six, seventeen declared properties);
`Contracts/schemas/` full listing (fourteen files, eight matching a `STATE_KEYS` block);
`tests/test_world_schema_conformance.py:34-263`; `tools/docs_check.py:11-15`;
`board/backlog/VILLAINS-NO-SCHEMA.md`.

## Files and assets in scope

New `Contracts/blocks.json` and its schema; `tests/test_world_schema_conformance.py`;
`Contracts/README.md` gains the pointer.

## Acceptance and evidence

A reference world validates against the registry in both directions. Deleting a block from a
generated world in a fixture makes the suite fail and names the block. Adding a new key to
`STATE_KEYS` without a registry row makes the suite fail.

## Documentation impact

`Contracts/README.md` indexes it. `docs/README.md` points at it as the answer to "what does a world
contain", which is currently answerable only by reading a Python constant.

## Adversarial review and limitations

**This card counts emitters, not a generated document.** The minimal-conforming-world claim above
was validated directly and holds. The 48 / 10 / 8 / 30 counts were not: they come from reading
`STATE_KEYS`, the envelope's declared properties and the schema directory, because no world was
generated — the performance session has size 17 at 70 s and 18.6 MB for 289 cells against recorded
11 s / 30 MB at 16,641 cells, cost has stopped tracking the raster, and verification is centralised
while that resolves. If a block in `STATE_KEYS` is never actually emitted at stage 16, the 30 is too
high. One generated world diffed against the envelope closes that, and whoever picks this up should
run it before quoting the number.

**An earlier draft of this card was wrong in the other direction** and said a bare six-key stub
conforms. It does not; `recipe`'s four required keys reject it. That claim came from reading the
`required` list rather than validating a document, and the SDET red team caught it. Corrected above.
The general lesson is the one this card is about: **a `required` list is not a contract until
something validates against it.**

**The counter-argument worth weighing:** a registry is a second place to forget to update, and a
stale registry is worse than none because it reads as authoritative. That is only survivable if the
suite fails on drift in both directions, which is why the two-way test is the deliverable and the
JSON file is just where it keeps its list. A registry without the failing test is bureaucracy.

**Scope honesty:** this does not make any block correct. It makes absence detectable. Those are
different goods and only the second one is claimed.

## Handoff

Found by extracting `STATE_KEYS` with `ast`, diffing it against `world-output.schema.json`'s
declared properties and against the filenames in `Contracts/schemas/`, then reading what
`tests/test_world_schema_conformance.py` actually validates. Full reasoning in
`docs/reviews/233182e-product-red-team.md`, Finding 1 — note that document's own placement warning.
