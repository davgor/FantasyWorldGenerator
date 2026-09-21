# HERITAGE-NATIVE-MIRRORS — what the native port owes the heritage layer

> **RETIRED 2026-09-21 by owner ruling. Not done, and not to be worked as written.**
> The native `Core/` port is deferred wholesale to the end of the project and will be a full
> rewrite against functionality that does not exist yet, so this card describes porting,
> mirroring or measuring a tree that is not the tree that will be ported. It is kept for its
> scoping notes and measurements only. **It is not a hold on anything** and must not be cited
> as a blocker or as evidence that a capability is incomplete.
> See [027 The native port is deferred to a full redo](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md).
>
> This card was already explicit that nothing in it was built and that the Python side is the complete reference oracle. It was a checklist for a port that will now be scoped fresh.


Owner: none. State: queued for the native port phase. **Do not start before it.**

The user has sequenced the native port as a separate later phase, after all Python work is
codified, because the UE module build takes hours. Writing these mirrors early puts unverifiable
C++ in the tree months before anything compiles it.

## Requested behavior

When the native port phase starts, whoever runs it should find one list of everything heritage
needs mirrored in `Core/`, with the Python reference for each, rather than reconstructing it
from scattered notes. This card is that list. **Nothing here is built** — the Python side is
the reference oracle and is complete; the C++ is deliberately deferred.

## The general rule for this layer

Heritage derivation never ships. Authoring, linting, sound changes and name assembly stay in
Python, exactly as `docs/decisions/020-authoring-catalogues-ship-as-data.md` prescribes for the
civilization registry. What the native side reads is the **resolved** result, already exported:
`Contracts/catalogues/native-catalogues-v1.json` carries a top-level `heritage` block with all
twelve peoples' traits, culture, genome and provenance.

Two facts that make this cheap, both verified at source:

- **A new top-level catalogue key is invisible to an existing binary.** `Catalogues::parse`
  (`Core/profiles.cpp:218-230`) reads the document only through named `catalogue::field()`
  lookups; it never iterates top-level keys and has no strict-schema pass. The `heritage` block
  has already shipped on that basis and needs no C++ change to be tolerated.
- **But a string key inside `profiles` is fatal.** `Core/profiles.cpp:256` is
  `profile.traits.emplace(key, catalogue::number(trait.second))` as its *default branch*. Do not
  put categorical heritage data inside a profile record; read it from the `heritage` block.

## The mirrors, in the order they should be taken

### 1. `Core/legacy.cpp` — culture magic schools

**Python reference:** `Sim/icarus_sim/terrain_ruins.py::culture_schools()`.

`Core/legacy.cpp:12-18` holds a literal twelve-row `culture_school()` table. Python no longer
does — it resolves from heritage. Replace the literal with a read of
`catalogues.heritage(<civ_id>).traits.magic_school`, which means `ruin_legacy` gains a
`const Catalogues&` (changing `Core/legacy.hpp:17`) and both call sites in `Core/ages.cpp`
(`:148`, `:207`) pass it.

**Zero behaviour change expected.** The twelve resolved values are identical to the retired
constant and are pinned literally in `tests/test_heritage_registry_binding.py`. Until this
lands, `NativeCultureSchoolTests` in that file reads `legacy.cpp` **as text** and asserts the
literal still agrees; it skips itself automatically once the literal is gone.

### 2. `Core/scene.cpp` — settlement names

**Python reference:** `Sim/icarus_sim/terrain_settlements.py::_settlement_names()`.

`Core/scene.cpp:87-90` holds the 24-word English list and `:110` applies
`city_names[index % count] + " City"`. Python has replaced both. **This is currently divergent
and is the one place where the reference and the port disagree on world content** — see the
consequences section.

The native side must not re-implement name assembly. The intended mechanism is that
`export_catalogues.py` writes a per-civilization pool of already-assembled names with their
glosses, and `scene.cpp` swaps its `const char* const[]` for a catalogue lookup, keeping its
index arithmetic. That keeps every sound change, seam rule and forbidden-form check in Python.

What must match exactly if names are instead generated natively:
- the seed domain `f'city-name-{node}-{x}-{z}-{profile}'` with `child_seed`'s third parameter
  used for collision redraws, bounded at 8;
- naming performed in **node order**, not founding order, so collision resolution is canonical;
- the seam rules in `Sim/heritage/naming.py::_join` — degemination, hiatus repair, and the
  spurious-digraph break that turns `ulk`+`hakn` into `ulhakn`.

### 3. `Core/settlements.cpp`, `Core/founding.cpp`, `Core/humans.cpp` — only if geometry wiring happens

**Python reference:** none yet. These are listed for completeness, not as work.

No trait currently feeds placement, population or founding. If `HERITAGE-GEOMETRY` is ever
accepted, each Python change needs its mirror here in the same change, and
`tests/test_native_world.py:186` compares founded cities with **no tolerance** — see that card
for why this is the expensive one.

## Consequences of the current state

`Core/scene.cpp` still names cities from the 24-word list while Python names them from each
people's language. **The native parity test will disagree on city names until mirror 2 lands.**
That is a known, sequenced consequence of the native port being a later phase, not an accident;
the Python side is the reference and is correct.

Mirror 1 has no such divergence — the values are identical — but the C++ table is now a copy of
something with no upstream, so it can only drift.

## Sources consulted

`Core/profiles.cpp:218-230,246-262`, `Core/legacy.cpp:12-45`, `Core/legacy.hpp:17`,
`Core/ages.cpp:148,207`, `Core/scene.cpp:87-90,110`, `tools/export_catalogues.py`,
`docs/decisions/020-authoring-catalogues-ship-as-data.md`,
`docs/decisions/021-heritage-chain.md`.

## Acceptance and evidence

Each mirror compared against the Python oracle in `tests/test_native_world.py`, following the
existing pattern that a catalogue "parsing successfully is not evidence that the two
implementations agree". Mirror 1 additionally has a zero-delta assertion available: the schools
must not move.

## Handoff

Written while completing heritage Phases A–D. The Python side of every item above is finished
and is the reference; nothing here is blocked on design, only on the port phase starting.
Related: `board/backlog/VILLAIN-SCHOOL-DRIFT.md`, which is a pre-existing divergence in the
same `Core/legacy.cpp` file and should be fixed in the same visit as mirror 1.
