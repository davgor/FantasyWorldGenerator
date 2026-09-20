# TIME-LIVENESS - one predicate for "is this person still here"

Owner: local. State: **delivered** 2026-09-20 as `Sim/icarus_sim/terrain_liveness.py`.
Split out of `TIME-ADVANCE.md` and deliberately held until the fall pair landed, so the
villain arm was written against the real export rather than a predicted one.

## Observed behavior

Four packages answer "is this person still here" in four different vocabularies, and no
caller can ask the question once.

| Block | Field | Still here | Gone |
|---|---|---|---|
| `heroes.people[]` | `status` | `living` | `legend` |
| `npcs.people[]` | `status` | `alive` | `dead` |
| `villains.people[]` | `status` | `living` | `fallen` |
| `villains.fallen[]` | - | n/a, the list is the record | n/a |

Counts in `Sim/` as of 2026-09-20: 61 `'living'`, 20 `'legend'`, 15 `'fallen'`, 6
`'alive'`, 4 `'dead'`. (`'departed'` at `terrain_corruption.py:417` is a god-visitation
report flag, not a person's liveness, and is out of scope.)

Two traps a naive adapter walks into:

- **`status` means two different things in one block.** `hero_generator` sets a
  block-level `status` of `'failed'` or `'ok'` and reads a *person-level* `status` of
  `'living'` or `'legend'` from the same key name at a different depth. A predicate that matches on the string alone will read a failed block
  as a living person. This repository already has `tier` meaning four things; this is the
  same shape.
- **Absent means living.** `terrain_villains.is_standing` reads a missing status as
  `'living'` on purpose - a record written before the fall was recorded described someone
  who stood. Any unified predicate must preserve that, or every pre-fall-pair world
  becomes a world of ghosts.

## Why the tick forces the issue

A single advance-time call can cross many ages. It asks "is this one still here" across
all four blocks, constantly, and today it cannot do so with one predicate. Every consumer
that means "who stands right now" has to say so itself - `is_standing`'s own docstring
says the list stopped answering that question by construction the moment the fallen began
staying in it.

## Proposed mechanism

A read-only adapter. One predicate over the four shapes, no vocabulary migration, no
change to any published contract.

- `liveness(record) -> 'present' | 'gone'`, dispatching on the block the record came from
  rather than sniffing its fields, so the `'failed'`/`'ok'` collision cannot be hit.
- Absent status resolves to `present`, matching `is_standing`.
- Existing per-package predicates stay and keep working. `is_standing` remains the
  villain-side authority and the adapter delegates to it rather than reimplementing it -
  two implementations of one rule is the bug this card exists to prevent, and writing a
  second one would be committing it.
- No writes. Nothing in this card changes what any block contains.

## Dependencies and unresolved decisions

- **The fall pair has landed**, so the villain arm can now be written against the real
  export rather than a predicted one: `villains.people` retains the fallen with
  `status: 'fallen'` and a `fell_age`, `villains.fallen[]` holds durable marks, and
  `is_standing` is the filter. This card was deliberately held
  until that shape existed - an adapter written on 2026-09-19 would have encoded "villains
  are always living", which was true by construction then and is false now.
- Whether `key_locations` can consume the adapter at all: it is a leaf package and cannot
  import the sim. The fall pair's answer was to stamp `holder_status` and `influence` onto
  the claim itself so a consumer needs no join. The adapter must not undo that by becoming
  a required import - it is a convenience for sim-side and orchestrator-side callers, and
  leaf packages keep reading stamped fields.

## Files and assets in scope

New module, claimed by the `TIME-ADVANCE` conformance record or its own. No edits to
`hero_generator`, `npc_roster` or `terrain_villains`.

## Acceptance and evidence

- A test that every one of the four shapes resolves correctly, including a record with no
  `status` key and a hero *block* carrying `status: 'ok'`.
- A test that the adapter and `is_standing` never disagree on a villain record.
- No behavior change anywhere: the same worlds serialise to the same bytes before and
  after.

## Delivered

`Sim/icarus_sim/terrain_liveness.py`: `liveness(record, block)`, `is_present`, `present`
and `census`. Dispatch is on the block name, never on the record's shape, and a record
carrying `people`, `quest_hooks` or `policy_revision` raises rather than being answered -
that is the block/person `status` collision caught loudly instead of silently. The villain
arm delegates to `terrain_villains.is_standing` rather than restating it. Absent status
resolves to present. Nothing writes; no vocabulary was migrated.

Covered by the `LivenessTests` class in `Sim/tests/test_time_advance.py`: seven tests,
including every vocabulary, the absent-status case per block, both block-shaped inputs, an
unknown block, and an agreement check against `is_standing`.

## Handoff

Delivered. One thing deliberately not done: `key_locations` still reads the stamped
`holder_status` and `influence` off the claim rather than importing this, because it is a
leaf package and the fall pair stamped those fields precisely so it would not need a join.
