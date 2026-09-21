# PRODUCT-BLOCK-REGISTRY — the world contract lists no blocks, so nothing can be missing

> **RE-MEASURED 2026-09-21 — the gap widened.** This card counts 48 published blocks with 30 lacking an
> envelope declaration or schema. The current sample publishes **58 container blocks**, of which 7 have a
> same-named schema. Same-name matching is a heuristic and not this card's predicate, so treat 7 as a
> floor rather than the figure — but recount before quoting 48/30. [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

Owner: contracts-and-vocabulary sweep. State: **closed 2026-09-21.** Delivered as
`Contracts/blocks.json` plus `tests/test_block_registry.py` and two tests in
`tests/test_world_schema_conformance.py`. **The headline counts no longer reproduce and the
finding that survives is a different, sharper one** — see "What was actually there" at the
foot. Found by the product red team auditing `233182e` for what a
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

---

## What was actually there — contracts-and-vocabulary sweep, 2026-09-21

The premise was re-measured by generating a world and diffing it, which is what this card's own
adversarial section says whoever picked it up should do before quoting the number. **Three of its
four counts are stale, and the fourth is gone.**

| The card says | Measured 2026-09-21 |
|---|---|
| `STATE_KEYS` holds 48 blocks | **49** |
| the envelope declares 10 of them | **all 49**, plus 7 envelope keys — 56 declared properties |
| `required` is six | **sixteen**, and it now includes the ten sections `test_generated_world_exercises_every_versioned_section` asserts |
| 30 neither declared nor schema'd | **zero** are undeclared *from `STATE_KEYS`* |

Another lane widened the envelope from 17 declared properties to 56 and moved `required` from 6 to
16, which also closed `SDET-WORLD-SCHEMA-SURFACE` — all four of its tests pass on this tree.

**The finding that survives is the one `VILLAINS-NO-SCHEMA` reached independently: declaring is
not describing, and there is a second gap the card never counted.**

- **Nine keys a world emits are declared by nothing at all.** `build_stages`, `effective_config`,
  `effective_tpi_radius_m`, `phases`, `physical_scale`, `resolved_octaves`, `spacing_m`,
  `topology`, `warnings`. They are not in `STATE_KEYS`, so the card's `STATE_KEYS`-based diff
  could not see them, and they reach a consumer unannounced because the root is
  `additionalProperties: true`.
- **Nine blocks have a contract of their own**; the rest are declared as bare objects with a
  sentence of prose, at wildly uneven depth. A block declared `{"type": "object"}` validates
  whatever it happens to contain.
- **Same-name matching is a heuristic and undercounts.** The header's floor of 7 is the
  same-named schemas; `heroes` resolves to `hero-generator.schema.json` and `npcs` to
  `npc-roster.schema.json`, which makes it 9.

### The unresolved question this card raised, settled

*Is `STATE_KEYS` membership the right definition of "published"?* **No, and it is not close.**
`STATE_KEYS` is the tuple `terrain_history` carries across an age boundary; `materialize_stage`
builds each stage from the keys *not* in it. A reference world carries **63 top-level keys**: 47
of the 49 `STATE_KEYS` blocks, plus 16 envelope and derived keys. Two `STATE_KEYS` blocks —
`quests` and `world_clock` — are declared, are legal, and are **absent from every freshly
generated world**, because the clock writes them and generation does not. A registry built on
`STATE_KEYS` alone would have been wrong in both directions at once.

The registry is therefore keyed on *what a world document carries*, with `state_key` kept as a
measured column rather than as the definition.

### Measurement

Seed 42, size 17, recipe 3, generator 16, `build_stages=True` — the same call
`tests/test_world_schema_conformance.setUpClass` makes. **Independently cross-checked against
`Fixtures/sample-world-v1.json`** (seed 42, size 33) by streaming its top-level keys rather than
parsing 162 MB: identical key set, identical nine undeclared, identical two absent. The key set
does not move with size, which is what makes a size-17 world a fair reference for it.

## Delivered

### `Contracts/blocks.json`, schema 1, 65 rows

One row per top-level key, carrying `schema` **or** `reason_if_unspecified` — exactly one of the
two, enforced — plus `version_binding`, `owner`, `optional`, `env_gate`, and four measured
columns: `state_key`, `declared_in_envelope`, `required_by_envelope`, `in_reference_world`.

`reason_if_unspecified` is the point of the exercise rather than an escape hatch, and it carries
real information rather than boilerplate. The four blocks
[029](../../docs/decisions/029-core-emitted-blocks-carry-their-own-schema.md) says qualify for a
schema and deliberately does not schedule — `threat_assessments`, `wildlife`, `magic`, `ruins` —
each say so and say who derives from them. The nine undeclared keys each say what they are and
that nothing declares them. The rest state 029's rule and that they do not meet it. That fact
about the product now lives in a file a consumer reads instead of in a card.

Two columns the card's example row asked for are **not** here, and the reason is stated in the
file:

- `present_from_stage` — it would be 65 integers that nothing measured. Every one would have to
  be right on the day it was typed and would then rot silently. `in_reference_world` is measured
  and answers the question the two-way test actually needs.
- `optional` is kept, and is flagged in the file as the **one authored column**: it is a claim
  about worlds that were not built, so no test can derive it. The world-direction test below is
  what keeps it honest.

### The tests, in both directions, because a registry without them is bureaucracy

`tests/test_block_registry.py` — 9 tests, no world, 0.4 s. Every derivable column re-derived:
`STATE_KEYS` in both directions, the envelope's `properties` and `required` in both directions,
every named `version_binding` resolving in `docs/conformance/version-bindings.json`, every
`schema` path existing, every owner **writing** the key it is credited with, and the
contradiction guard that a key the envelope requires is never marked optional.

`tests/test_world_schema_conformance.py` — two tests on the world that class already builds, so
they cost no extra generation:

- `test_every_block_this_world_carries_is_in_the_block_registry` — emitted but unregistered;
- `test_every_block_the_registry_does_not_call_optional_is_present` — registered but absent.

### Ablation — every test watched to flip

The whole module is green, so each check was re-run with the thing it checks taken away.

| Ablation | Result |
|---|---|
| the `settlements` row deleted | `test_every_state_key_has_a_row...` **red**, names `settlements` |
| `topology.state_key` flipped to true | same test **red** — the column is checked in both directions |
| `wildlife.reason_if_unspecified` replaced with a placeholder | `test_every_row_names_a_contract...` **red** |
| `villains.schema` pointed at a file that does not exist | same test **red** |
| `nomads.version_binding` set to a binding id nothing declares | `test_every_named_version_binding_exists` **red** |
| `terrain.declared_in_envelope` flipped to false | `test_the_envelope_columns...` **red**, and the undeclared-keys test with it |
| `terrain.optional` flipped to true | `test_a_key_the_envelope_requires_is_never_marked_optional` **red** |
| `water.owner` repointed at `terrain_astrology.py` | **GREEN — and that is a defect this exercise caught.** See below |
| the `settlements` row deleted, against a generated world | `test_every_block_this_world_carries_is_in_the_block_registry` **red**, naming `settlements` |
| `quests.optional` flipped to false, against a generated world | `test_every_block_the_registry_does_not_call_optional_is_present` **red**, naming `quests` |

**The owner check passed its own ablation, which means it was testing the fixture.** The first
version asked whether the owner module *contains the string*. `Sim/icarus_sim/terrain_astrology.py`
contains that block's name — as an element of `HEMISPHERES`. A near-miss match silently answered
a different question, and only the ablation showed it. The check now parses the module and
requires the key to appear as something that **writes**: a subscript assignment target, a dict
literal key, a `dict(...)` keyword argument, or the first argument of `setdefault`, which is the
only way `terrain_villains` writes its block. Re-ablated: **red**.

The two world-dependent ablations were run against the real test methods with `setUpClass`
called once, so they ablate the tests rather than a re-implementation of their assertions. The
registry file was restored from captured bytes and the restore verified before the run finished.

### Suite result

`python -m unittest tests.test_world_schema_conformance` — **18 tests, OK**, 70 s, including
both new tests. Note for the closeout: the two failures `VILLAINS-NO-SCHEMA` reported in this
module (the fortress-id join and the beast-movements count) are **fixed** on this tree by their
own lanes. `python -m unittest tests.test_block_registry` — 9 tests, OK.

### Files

`Contracts/blocks.json` (new); `tests/test_block_registry.py` (new); two tests added to
`tests/test_world_schema_conformance.py`; `Contracts/README.md` and `docs/README.md` gain the
pointer.

**`Contracts/schemas/world-output.schema.json` was NOT touched**, and no version was bumped.
Four cards edit that file and three other agents wrote to it tonight; nothing here needs it,
because the registry sits beside the envelope rather than inside it. Closing the open root is
still explicitly not proposed — it is a compatibility decision with its own cost and belongs to
whoever owns `Contracts/`. The registry makes the nine undeclared keys *visible*; it does not
make them invalid.

### Conformance record

None changed. This card adds a data file and two test modules and changes no module under
`Sim/`, so no record's `modules:` front matter covers anything that moved, and
`tools/docs_check.py` claims Python modules rather than contracts. A reworded record would be
worse than none.

### Scope honesty, restated because it still holds

This does not make any block correct. It makes absence detectable, and it gives the four
unscheduled schemas somewhere to be recorded other than a decision document's last paragraph.
Those are different goods and only the second pair is claimed.

**The half a registry cannot reach:** the read surface already reports, per world at runtime,
every top-level key with a `registered` flag meaning "in `STATE_KEYS`". That is an inventory of
what a world happens to carry. It has no schema, owner or reason column and cannot say what a
world *should* carry, which is why it is the registry's natural consumer rather than a
substitute for it.
