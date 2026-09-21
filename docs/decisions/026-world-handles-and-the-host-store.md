# 026 — A world is named by its content, and the host owns the store

On 2026-09-21 the owner ruled where a live world lives. The generator does not hold one.
It hands a world to a host — Unreal or Electron, whichever gets built — and the host
stores it and asks for the next version. A handle names one immutable version, the store
is durable, and it collects by age and count.

This record is the contract that makes those three sentences implementable by two
different hosts without them drifting apart.

## Why a name is needed at all

A world is not a value a caller can pass around. Measured on this generator, seed 42 at
size 17 phase 16 — the smallest world anyone generates: 52.9 MB as generated, of which
29.7 MB is `build_stages`; 23.2 MB in the transfer form; 5.1 MB gzipped. Generating it
takes about 90 seconds. Larger worlds are larger: an implementation-time sample recorded
30 MB of diagnostic JSON at 129² and 116 MB at 257², and those figures predate several
blocks.

The consumer that matters is a local model packaged inside the game, and its context is
finite. It cannot hold a world, and it cannot be handed one back after every call. So the
world stays with the host and the caller works by name.

The tempting alternative is to make the name a recipe — a `Config` plus the operation log,
replayed on demand. It does not work, for two reasons that are both facts about this
repository rather than opinions. Replay costs about 90 seconds for the smallest world
and more for every larger one, which is not an interactive budget. And nothing can replay: every mutating API appends to
`history.operations`, eight of them do, and no code anywhere reads that log back. It is
evidence, not a reconstruction source.

## Decision

**A handle is the content address of a version.** `w_` followed by the first sixteen hex
digits of sha256 over the transfer bytes. Whoever holds the bytes can compute it; nobody
has to allocate, register or agree on an id.

**The transfer form is the canonical form.** One serialisation, used both to hand a world
over and to name it: JSON with sorted keys, no whitespace, UTF-8, non-ASCII unescaped, NaN
and Infinity refused. `build_stages` comes off at the top level and `timing_ms` comes off
at every depth.

That the two forms are the same form is the load-bearing choice. A host that digests what
it received and a generator that digests what it sent agree by construction, so a host
that only *stores* worlds needs no float-formatting parity with Python at all. Only a host
that *generates* natively has to reproduce these bytes, and that is the existing
native-parity problem rather than a new one.

**Dropping the two keys is what makes the name a function of the world rather than of the
run.** `timing_ms` is wall clock and is the only reason two runs of one seed ever differed,
which is why `cli._without_timings` already exists; the handle rule imports it rather than
restating it. `build_stages` is sixteen cumulative snapshots the browser lab inspects, no
consumer reads, and 56% of the bytes. A world generated for profiling and the same world
generated for a game are the same world and get the same name.

**A version is immutable and a mutation produces a child.** The parent stays valid. This is
not a new guarantee: every request API is already pure — world in, new world out — and
`consumer_orchestrator.py` asserts that a call never touches the caller's world. A store
built on mutable slots would throw that away at the boundary and hand back the aliasing the
API was written to avoid. Undo and branching are then free rather than features.

**A host returns an envelope, never a world.** `Contracts/schemas/operation-envelope.schema.json`:
the new handle, its parent, the paths that changed, the `history.operations` entry, and the
producing API's own report where it writes one. Kilobytes, whatever the world weighs.

**The store is the host's, and `icarus_sim` never learns what a handle is.** Every request
function allow-lists its body keys and refuses an unknown one by name, so a `world_id`
field would be rejected by construction. The glue resolves a handle to a document and calls
the existing function unchanged. The arrow that must not reverse — `icarus_sim` importing
nothing from `fantasy_world_generator` — is unaffected, because the handle rule lives on
the far side of it.

**A handle outlives the generator that minted it, so a store refuses a stale one.** A
version whose `generator_version` no longer matches the running generator is refused with
`retired_version`, which already says the right thing — regenerate rather than migrate —
and carries `retry=False`, so a controller stops resending instead of hunting for a value
that would work. This is decision 023 arriving at the store: worlds are disposable until
the first player-facing release, and a durable store is exactly where that bites.

**Collection is by age and count, and a root is kept longest.** A store may evict; it may
not evict silently. A handle that named a version the store has collected is refused as
gone, distinctly from a handle that never existed, because the remedy differs: one is
regenerate, the other is a bug in the caller.

**Reads produce no version.** `moon` and `patch` answer with their own document and mint no
handle. Nine verbs mint one: eight transforms, plus the generate that roots a lineage.
`depart` is one of the eight and has no route of its own, being `summon` with
`depart: true`.

## What this does not decide

- **Which process is the host.** Deliberately open. The contract is written so that Unreal
  and Electron can each satisfy it, and so that a world stored by one is named the same by
  the other.
- **The read surface.** At the time of this ruling a caller that could name a world still
  could not ask what was in it without receiving all of it, and that was named here as the
  next package and the critical path. That package is now built: five bounded reads over a
  world that already exists -- `blocks`, `near`, `place`, `person` and `quests` -- each
  taking a world document exactly as the mutators do, and each minting no version, which
  is this ruling's own rule rather than an exception to it. See
  [the read surface](../conformance/read-surface.md). What stays undecided here is the
  host half: resolving a handle into the document a read is handed is still the store's
  job, and the generator still has never heard of a handle.
- **Anything about MCP.** An MCP server is a client of a host that satisfies this contract.
  It cannot be built before one exists.

## Consequences worth stating plainly

**The two candidate hosts are not interchangeable today.** `Core/` implements generate and
advance-age. The other seven world verbs, and heroes, quests and NPCs, are Python only —
quests by the owner's own ruling. An Unreal host satisfying this contract would store
worlds and offer two of the eleven operations; an Electron host offers all eleven.

**A native host can already format floats Python's way, but not in JSON.** `python_repr` in
`Core/castlegeometry.cpp` and `py_repr` in `Core/cityshapes.cpp` are two independent
implementations of CPython's float repr, and they agree: shortest round-trip digits, with
scientific notation when the decimal point position is at or below -4 or above 16. What is
missing is the JSON layer — the value type in `Core/json.hpp` has no floating-point case at
all, so the native canonical writer cannot serialise a world document today. A port should
reuse one of the two repr implementations rather than write a third.

**A version costs about 5 MB, so collection is a requirement rather than housekeeping.**
Dropping `build_stages` and gzipping takes the smallest world anyone generates from 52.9 MB
to 5.1 MB — a tenfold saving, and still 507 MB for a hundred-version session. A store that
skips either rule is holding 5.3 GB for the same session and will conclude that immutable
versioning is unaffordable, which is the wrong conclusion reached from correct arithmetic
on the wrong bytes. A store that applies both still has to collect, and that is why the
eviction rule is part of this contract rather than left to whoever implements it.

This figure is worth re-measuring rather than citing. An artifact generated six days before
this record was written is 7.8 MB for nominally the same world, because the generator has
gained blocks since; the number above will drift the same way.

## Evidence

`Fixtures/world-handle-v1.json` is the cross-host parity fixture: nine documents with their
transfer bytes written out in full and their handles, two rejections, and one real
generated world. An implementation checks its serialisation before its digest, because two
implementations that agree on a digest while disagreeing on the bytes agree by luck.
Regenerate it with `tools/build_world_handle_fixture.py`.

Proven by `tests/test_world_handle.py`; see `docs/conformance/world-handles.md`.
