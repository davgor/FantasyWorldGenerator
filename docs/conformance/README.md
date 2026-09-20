# Conformance records

This folder is the present-tense breakdown of what this product does. One record per
capability, each stating what it produces, how it is entered, what it emits, at what
version, and what proves it.

`board/` is the change log — how the product got here. A conformance record says what is
true now. A sentence that only makes sense as history belongs in a ticket, not here.
Records carry no dates except their own, no "previously", no "now that".

A word of warning about the name: `Core/README.md` has a `## Conformance` section and
`tests/test_world_schema_conformance.py` uses the word too, both meaning numeric parity
between the Python reference and the C++ port. That is a narrower sense and it keeps its
own home. Here the word means the product conforming to its own description.

## Scope

Every module under `Sim/` is claimed by exactly one record. The 46 `Core/` stems are not
covered yet: the native port is being redone for the Unreal import and these records are
its acceptance spec, so native records are written against the new port rather than the
current one. They are parked in `coverage.json` against
[UNREAL-IMPORT-CONFORMANCE](../../board/backlog/UNREAL-IMPORT-CONFORMANCE.md) so the gap is a
declared debt with a ticket rather than a silent omission.

## What a record contains

Front matter carries the machine-checked claims. It is parsed with a deliberately small
`key: value` and `  - item` subset — no PyYAML, because this package declares no
dependencies and a documentation gate must not add the first one.

```
---
conformance: 1
record: nomads                 # equals the filename stem
tier: EXERCISED                # the record's floor, not its ceiling
summary: one present-tense sentence
modules:                       # the coverage claim; exactly one record owns a module
  - Sim/icarus_sim/terrain_nomads.py
emits:
  - path: nomads
    schema: Contracts/schemas/nomads.schema.json
versions:
  - id: nomads
    assert: 1
proof:
  - path: Sim/tests/test_terrain_nomads.py
    establishes: gate eligibility, weighted draw, route construction, stage gating
decisions: []
tickets: []
---
```

The body uses the same headings in the same order in every record, so heading position
carries no information and you navigate by filename. This is deliberate: the repository
already has a document whose headings are ordered by when the work happened, where
heading navigation actively misleads.

1. `## What it produces`
2. `## Entry points`
3. `## Inputs it reads`
4. `## Artifacts it writes`
5. `## Where it runs`
6. `## Versions asserted`
7. `## Proven by`
8. `## Why it works this way`
9. `## Does not establish`

Heading 9 is not optional. It is the house convention already carried by the evidence
table in `PLAN.md` and the adversarial-review section every board ticket must have.

## Evidence tiers

A record's tier is the floor of what it claims, not the ceiling. Anything above
`DECLARED` must cite `file::test_name`, and the checker resolves the citation.

| Tier | May assert | Established by |
|---|---|---|
| `DECLARED` | The symbol exists with this signature; its own comments say it does X | Reading source |
| `REACHABLE` | A caller exists and a named build compiles and links it | A call-site trace and a build target |
| `EXERCISED` | A named test runs this code and asserts on its output | Reading the test |
| `PARITY` | Output matches a reference field by field at a stated seed and tolerance | The parity suite |

**Writing a record never promotes a tier.** A tier moves when a test lands, and that
test is a ticket, not documentation work. Without this rule the folder becomes a place
where claims get laundered: the most confident, best-reasoned prose in this repository
sits in headers describing code no test has ever executed.

## Widening a record you do not own

There is a fourth case, and it is the one people get wrong. If your change means a block
another record owns can now change at a time it could not before — a new writer, a new
trigger, a new failure mode — **that record needs the edit, in your change**, even
though no version moved, none of its modules changed, and nothing it says became
literally false.

It needs the edit because `## Where it runs` and `## Artifacts it writes` are claims
about *when a thing is stable*, and a consumer reads them that way. A block written once
at stage sixteen is a block a consumer may read and cache. The same block re-rolled by a
later call is not, and nothing in the old record warns them.

This is the two-writer problem arriving by the front door. The `magic` block already has
two functions that each replace it wholesale, and that went unnoticed until a check
compared the sites. Do not add a second writer to someone else's block silently: say so
in their record, and if a version integer is involved, decide which site is
authoritative rather than suppressing the warning.

## Binding invariants versus current description

Records are binding on other work, not merely descriptive. Two categories, marked
differently because they behave differently under change:

- **Invariant.** Determinism, replay identity, draw and iteration order, byte
  reproducibility, id stability across ages. Changing one of these is a contract change
  and needs its own decision. An optimisation may not quietly break one because the
  mathematics looks equivalent — float addition is not associative, and one reordered
  summation propagates into a different city set against a zero-tolerance comparison.
- **Description.** What a stage costs, how many of a thing a seed produces, current
  counts. These are expected to change. A cost figure must state the seed, the world
  size and what it ran on, because a number without those three cannot be compared to
  the next one.

If you believe an invariant is wrong rather than inconvenient, say so and change it
deliberately. Do not route around it.

## Coverage and the allowlist

`coverage.json` was seeded once, on 2026-09-19, from the tree at that moment, and is
never re-seeded. A module created after that day appears in none of its lists, so the
first check that sees it fails. The `uncovered` list may shrink and may not grow; every
entry names a ticket that must exist.

`exempt` is a different thing and permanent: a closed vocabulary of `generated`,
`test-support`, `re-export` and `vendored-reference`, each with a required note. There
is no `other`, so "this one is awkward" cannot be expressed.

Note that five `__init__.py` files hold real implementation — roughly a thousand lines
and forty public functions across the leaf packages. They are in the universe and must
be claimed. Only genuinely empty package markers are exempt.

## Version markers

A documented version integer is written as a marker and never as bare prose:

```
Twelve leylines in three groups <!-- conformance:version magic=4 -->
```

`version-bindings.json` binds each id to the code that emits it. The checker never
scrapes prose, because several historical sentences in the canonical documents cite old
versions correctly and no regex can tell those from stale ones.

An `emitted-key` binding is scanned for across every module under `Sim/`, not just its
own file. This exists for a real case: `terrain_magic.py` writes `magic` version 1 early
and `terrain_leyline_history.py` later overwrites the whole block with version 4. A scan
confined to the declared file would never see the disagreement.

## Working in a shared tree

Other sessions edit this repository at the same time. Two techniques are rules here, not
folklore, because both have already gone wrong:

- **Compute a provenance `previous_destination_sha256` by reverting your own edit in
  memory, never by reading disk.** Hashing the file off disk captures other sessions'
  concurrent edits and silently claims them under your reason.
- **Pinned-file hashes are taken over worktree bytes, so line endings are part of the
  hash.** `docs/terrain-math-lab.md` is CRLF; `Sim/README.md` and
  `docs/terrain-world-layers.md` are LF. Patch pinned files at byte level rather than
  with a tool that may normalise, and check `git check-attr text` reports `unset`.

Before editing a shared file, capture its hash and modification time and re-check both
immediately before writing. If it has changed twice, it is under active construction:
note it and move on.

## What a green check does not prove

`tools/docs_check.py` establishes that documents are readable, that their links resolve,
that every module is claimed exactly once, and that every version marker matches the
code. It establishes nothing about whether a record is true. A record can pass every
check here and describe behaviour the product no longer has.

It is a structural gate. Do not cite it as documentation review.
