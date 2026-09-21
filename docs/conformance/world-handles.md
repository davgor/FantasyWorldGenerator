---
conformance: 1
record: world-handles
tier: EXERCISED
summary: Names one immutable version of a world by the sha256 of the bytes it is handed over as, and reports one operation as an envelope of names rather than as a world.
modules:
  - Sim/fantasy_world_generator/world_handle.py
emits:
  - path: (not a world block)
    schema: Contracts/schemas/operation-envelope.schema.json
versions:
  - id: store-contract
    assert: 1
proof:
  - path: tests/test_world_handle.py
    establishes: the pinned transfer bytes and handles of nine parity cases, that NaN and Infinity are refused, that key order and profiling residue do not change a name, that a real generated world still has its pinned handle, that a stale world is refused in the shared refusal vocabulary, and that every envelope a version verb produces validates against its schema
decisions:
  - docs/decisions/026-world-handles-and-the-host-store.md
  - docs/decisions/023-world-compatibility-policy.md
tickets: []
---

# Conformance: world-handles

## What it produces

A name for one immutable version of a world, and the envelope a host returns after acting
on one. The name is `w_` followed by the first sixteen hex digits of sha256 over the
transfer bytes <!-- conformance:version store-contract=1 -->. The envelope carries the new
name, its parent, the paths that changed, the operations record, and the producing API's
own report where it writes one — and never the world, which is the point.

Nothing here holds state. The store belongs to the host, which is Unreal or Electron,
whichever gets built. This module says only what a version is called, which bytes that
name is taken over, and what one operation reports.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `handle(document)` | `world_handle` | the version's name |
| `transfer_bytes(document)` | `world_handle` | the exact bytes to hand a host, and the bytes the name is taken over |
| `transfer_document(document)` | `world_handle` | the same content as an object, for a caller that will serialise it itself |
| `is_handle(value)` | `world_handle` | whether a value is shaped like a handle; says nothing about a world existing |
| `check_generator(document, running)` | `world_handle` | nothing, or `RequestError` refusing a world this generator will not read |
| `changed_paths(before, after)` | `world_handle` | dotted paths, to two levels, that differ |
| `last_operation(document)` | `world_handle` | the final `history.operations` entry |
| `envelope(operation, after, before)` | `world_handle` | the operation envelope |
| `OPERATIONS` | `world_handle` | every verb, and whether it roots a lineage, produces a version, or only reads |

## Inputs it reads

A world document, and nothing else. No layer, block or catalogue is required to exist: a
handle is defined over any JSON-safe object, which is what lets the parity fixture pin the
rule with nine documents that are not worlds. `check_generator` reads `generator_version`
and `last_operation` reads `history.operations`; both tolerate absence, and `envelope` is
total over any document a producer returns.

## Artifacts it writes

No world block. The envelope is a return value against
`Contracts/schemas/operation-envelope.schema.json`, closed with `additionalProperties:
false`.

**Invariant: the transfer form and the canonical form are one form.** Sorted keys, no
whitespace, UTF-8, non-ASCII unescaped, NaN and Infinity refused. A host that digests what
it received and a generator that digests what it sent agree by construction; the moment
these diverge, cross-host parity becomes a float-formatting negotiation instead of an
identity.

**Invariant: `build_stages` comes off at the top level only.** It is lab payload there and
content anywhere else. A recursive strip would silently rename any world whose blocks
happen to carry the key.

**Invariant: `timing_ms` comes off at every depth, by importing `cli._without_timings`
rather than restating it.** Two implementations of one rule is how the transfer form starts
drifting from the export form, and the export form's byte-reproducibility is the guarantee
the whole content address rests on.

**Invariant: a handle is a function of the world, not of the run.** The same request
generated with `build_stages` and `timings` and without them produces the same handle.

**Invariant: `changed` is computed in the transfer form too.** Two versions are the same
version when their transfer bytes match, so a path that cannot differ between two distinct
versions is not a change. Comparing the documents as handed in puts `timing_ms` — the one
key the handle is defined to ignore — into the account of every call that carries timings.

The load-bearing detail that reads as incidental: the digest is taken over a *rendering*,
so every float formatting convention is part of the identity. A whole float keeps its
trailing `.0`, negative zero keeps its sign, notation turns scientific when the decimal
point position is at or below -4 or above 16, and an exponent carries a sign and at least
two digits. `Fixtures/world-handle-v1.json` pins all four, because an implementation that
gets the shortest-round-trip digits right and the layout wrong produces a different name
for the same world and no other test would say so.

## Where it runs

Outside `icarus_sim`, on the glue side of the boundary, called by whatever hands a world to
a host. It is not reached during generation and no producer imports it. Every request
function allow-lists its body keys, so a handle cannot be passed into one even by mistake:
the glue resolves a handle to a document and calls the request function unchanged.

## Versions asserted

The store contract is version 1 <!-- conformance:version store-contract=1 -->. It covers
the handle rule, the transfer form and the envelope together, because a change to any one
of them changes what a stored version is called or how it is reported, and a host cannot
adopt them separately.

## Proven by

`tests/test_world_handle.py` — 34 tests. The fixture cases assert bytes before digests, so
a failure says which serialisation is wrong rather than only that two hashes differ. The
schema tests include a control that damages three different constraints, because three
passing validations establish nothing unless something can fail.

## Why it works this way

**Content addressing rather than allocated ids**, because an exported world is already
byte-reproducible — `cli._without_timings` exists precisely so that two runs of one seed
agree — and a reproducible document has a true name rather than a bookkeeping one. Dedupe
is then free, and a call that changed nothing is detectable by comparing names instead of
by trusting a report that says so.

**Sixteen hex digits**, because the collision budget is a session's worth of versions, not
a content-addressed filesystem's.

**Immutable versions rather than a mutable slot**, because the request APIs are already
pure and the scripted consumers assert it. A slot would reintroduce aliasing at the
boundary and lose undo and branching, and the arithmetic that makes slots look necessary is
arithmetic on the wrong bytes: dropping `build_stages` and gzipping takes a measured
size-17 phase-16 version from 52.9 MB to 5.1 MB, which is a tenfold saving and still
5 MB a call.

**An envelope built around `history.operations` rather than around the per-API report**,
because the report is the thing that is missing. Four of the eight version-producing APIs
stamp no report block — age, visitation, departure and nomad — and all eight append an
operations entry. Keying the envelope to the report would have left half the verbs saying
that something happened without saying what.

**`retired_version` for a stale world**, because it already carries the right message and
`retry=False`. A store is durable and a generator is not, so this is the one refusal a
long-lived store will emit routinely.

## Does not establish

- **Nothing about a store.** No code here stores, evicts, or resolves a handle back to a
  world. Decision 026 states what a host must guarantee; no host exists, so none of it is
  exercised. The eviction rule in particular — collect by age and count, keep a root
  longest, refuse a collected handle distinctly from an unknown one — is specified and
  unimplemented.
- **Nothing about cross-host parity in practice.** The fixture is what a second
  implementation would be checked against, and there is no second implementation. The
  native JSON layer cannot even represent a world document: the value type in
  `Core/json.hpp` has no floating-point case. Two independent CPython float-repr ports
  already exist in `Core/castlegeometry.cpp` and `Core/cityshapes.cpp` and agree with the
  fixture's thresholds, which is evidence that the rule is portable, not that it has been
  ported.
- **Nothing about collisions.** Sixteen hex digits is asserted as a choice, not as a
  bound; no test generates enough versions to say anything empirical about it.
- **Nothing about large worlds.** Every test runs against synthetic documents or a size-17
  phase-4 world. The cost of digesting a 116 MB size-257 document is unmeasured, and
  `transfer_bytes` materialises the whole rendering in memory before hashing it.
- **`changed_paths` is a two-level summary, not a diff, and for some verbs it is a
  firehose.** It says a block differs, not how, and at two levels a change deep inside one
  list is reported as the list having changed. Measured on one age advance of a seed-42
  size-17 phase-16 world: 189 paths, because an age transition rebuilds nearly everything.
  For that verb `changed` establishes little beyond the fact that the world moved; for a
  founding or a cleanse it is the account.
- **That any verb's report is accurate.** The envelope carries what a producer stamped,
  verbatim. Whether that block describes what actually happened is the producing package's
  claim, not this one's.
