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
covered, and will not be until the native port is scoped again. Under
[027 The native port is deferred to a full redo](../decisions/027-native-port-deferred-to-a-full-redo.md)
the port happens at the end of the project as a full rewrite, so a record written against the
current `Core/` would describe a tree that is not the one that gets ported. They stay in
`coverage.json`'s `uncovered` allowlist as a **deliberate permanent exclusion**, not as a debt
with a ticket: the ticket that used to own it,
[UNREAL-IMPORT-CONFORMANCE](../../board/retired/UNREAL-IMPORT-CONFORMANCE.md), is retired. These
Python records remain the acceptance spec for whoever scopes the port.

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
`DECLARED` must cite the file that establishes it, under `proof:`.

This table is the closed vocabulary, and `tools/docs_check.py` reads it: a `tier` that is
not one of these four words is a hard failure naming the word. The four are restated in
`TIERS` in the checker, so a fifth tier has to be added in both places or it is refused.
What the checker resolves is the `proof[].path` — that the file exists and that it is a
file one of the three suites discovers. It does not resolve a `::test_name`, does not run
the test, and does not read what `establishes:` says. Existence is not exercise.

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

A record may also state the integer in its own front matter, under `versions:`, and that
list is checked against the same binding. It used to be checked against nothing: version
enforcement ran only off the markers in prose, so a record's own `versions:` could assert
any integer it liked and stay green.

A binding is not only for a schema version. A published **bound** takes one too, and a
bound usually has a second statement of itself in the guard that enforces it — the grid
ceiling is declared in the registry's `bounds` table and restated four hundred lines below
by the call that refuses an oversized world. The `tuple-bound` and `call-arg` resolvers
read each side independently and a `mirror` reports them when they disagree, so one fact
written twice cannot drift the way the Python and native grid ceilings did. Deriving the
guard from the table is still better than checking two statements agree; where that has
not been done, the binding says so.

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
that every module is claimed exactly once, that every version marker matches the code,
and — since 2026-09-21 — that the rest of a record's front matter resolves: every
`emits[].schema` and `proof[].path` is a file that exists, every proof path is a file one
of the three suites discovers, every `versions[].assert` equals the integer the code
emits, and `tier` is one of the four declared words.

It establishes nothing about whether a record is true. A record can pass every check here
and describe behaviour the product no longer has. In particular it does not run a proof
test, does not check that the test passes, and does not read what `establishes:` claims.
**Existence is not exercise.**

### And it says what it did not read

Every run prints the documents it did not examine and the frozen documents it read but
did not link-, citation- or version-check, because the failure this gate is most prone to
is not a wrong answer but an unasked question. `board/retired/` was created on 2026-09-21
and named in neither glob list: four cards moved into it, six sibling-relative links
inside them died, and the run stayed green because the folder was never scanned. The only
symptom was the document count falling from 208 to 204, and that was rationalised rather
than investigated. **A checker that cannot see a folder cannot fail on it.**

Every markdown file in the repository now has to match `ACTIVE_GLOBS`, `FROZEN_GLOBS` or
`UNCHECKED_GLOBS`, and the last of those carries a written reason per glob and is printed
on every run. A new folder fails loudly instead of passing silently. The other direction
is checked too: a glob that matches no document warns, because a folder that moved leaves
its glob behind and takes its documents out of the gate without a finding.

Note which list `board/retired/` went into. Freezing it would have suppressed exactly the
link check that catches a card changing folder, because a frozen document hits a
`continue` inside the link check — so the class of rot that was missed would have become
permanently invisible instead of merely invisible once.

It is a structural gate. Do not cite it as documentation review.
