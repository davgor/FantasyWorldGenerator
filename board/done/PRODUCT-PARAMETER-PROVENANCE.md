# PRODUCT-PARAMETER-PROVENANCE — a published bound says what it is, never which producer said it or when it changed

> **CLOSED 2026-09-21, by option 2 rather than option 1. The owner should read the next
> paragraph and reverse this if they disagree.**
>
> **Chosen: bind the registry's bound to a version, and bind the guard to it as a mirror.**
> `docs/conformance/version-bindings.json` gains `grid-size-max`, whose `code` side reads
> `bounds['size'][1]` out of the registry table by AST and whose `mirror` side reads the
> integer argument the guard passes to `over_capacity('size', …, 1025, 'grid')`. Two new
> resolver kinds carry it, `tuple-bound` and `call-arg`, and the existing `VERSION-MIRROR`
> finding reports them when they disagree. `docs/conformance/world-parameters.md` states
> the bound as a marker, so a published integer now moves when the ceiling moves.
>
> **Rejected: option 1, deriving the guard from the registry.** It is the better fix — one
> statement of the fact instead of two agreeing ones — and it is one line. It was not taken
> because `Sim/icarus_sim/terrain_world.py` is provenance-pinned: editing it needs a
> revision row in `provenance/extraction-manifest.json`, a file this lane is forbidden to
> touch and which has already been corrupted once by two sessions racing on it. Editing the
> module without the row turns `verify_provenance` red for every concurrent session. The
> conservative option was taken and the better one is named here so it can still be done:
> **`raw['size'] > registry(version)['size']['max']`, twice on two adjacent lines.** Option
> 2 does not become redundant when option 1 lands — the mirror simply resolves the same
> statement twice and stays green.
>
> **Option 3, stamping the producer, is not done and is not started.** The card says it is
> worth doing only if multiple producer paths become real, and they have not. That half of
> the title — "never which producer said it" — is therefore still true and is the honest
> residue of this close. `recipe.provenance` distinguishes override, preset, bias and
> default, and nothing else.
>
> Premise re-tested by running it rather than reading the card, as the card asked: the
> bounds table is at `terrain_world.py:266` and the guard at `:458` (the card said 457-458;
> lines have moved), there is exactly one of each in the module, and both resolve to 1025.

Owner: none. State: **closed**. Filed 2026-09-21 as the surviving non-native half of
[PRODUCT-CAPABILITY-RANGE-DIVERGENCE](../done/PRODUCT-CAPABILITY-RANGE-DIVERGENCE.md), which
closed when the grid range stopped diverging and the native port was deferred
([027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md)). That card asked
explicitly that this not be lost with it.

## Requested behavior

A consumer reading a bound out of a world document can tell which producer path published it and
whether it has moved since the document it is holding was written. Today it can tell neither.

## The defect

Every generated world carries a parameter registry: `registry(version)` is published as
`recipe.parameters` at `Sim/icarus_sim/terrain_world.py:463`, and its `bounds` table at
`Sim/icarus_sim/terrain_world.py:266` is where `size` is declared as `(3, 1025)`. The guard that
actually rejects an out-of-range world is a separate statement of the same number at
`Sim/icarus_sim/terrain_world.py:457-458`.

Two things follow, and neither is about C++:

1. **No version binds the range.** `docs/conformance/version-bindings.json` carries bindings for
   emitted blocks and native constants, and none for the grid range. The ceiling moved from 257 to
   1025 in `21df9aa` and `4713f9a` and no published integer changed to say so, so two world
   documents generated either side of that change are indistinguishable on the point.
2. **The bound and its enforcement are two statements of one fact.** `bounds` advertises the range
   and the guard enforces it, four hundred lines apart in the same module. They agree today because
   somebody checked, which is the same footing the Python/native pair was on before it drifted.

The grid ceiling is the instance that was caught. Nothing about the shape is specific to `size` —
the next parameter to move will diverge the same way, silently, and a consumer still has no way to
ask which producer published a bound it is holding.

## Proposed mechanism

Not decided; three options, cheapest first.

- **Derive the guard from the registry.** The guard reads `bounds['size']` rather than restating
  `1025`. This is the pattern `tools/validate_repo.py`'s `rejection_fixtures()` already uses — it
  reads the bound from `registry(3)` rather than restating it, precisely so the check cannot be
  satisfied by moving a number. One statement of the fact, and option 2 becomes a much smaller job.
- **Bind the registry to a version.** A `conformance:version` marker for the parameter registry,
  bumped when any bound moves, bound in `version-bindings.json` like every other emitted key.
- **Stamp the producer.** `recipe.parameters` carries which entry point resolved it. This is the
  most useful to a consumer and the most invasive; it is worth doing only if the read surface
  ([PRODUCT-READ-SURFACE](../done/PRODUCT-READ-SURFACE.md)) makes multiple producer paths real.

Options 1 and 2 are independent and either is worth doing alone.

## Dependencies and unresolved decisions

None blocking. Deliberately **not** blocked on the native port: the whole point of splitting this
out of its parent card is that nothing here needs a `Core/` consumer to exist.

Sequence it near [PRODUCT-BLOCK-REGISTRY](PRODUCT-BLOCK-REGISTRY.md), which asks the same kind of
question one level up — what a world document declares about itself — and near
[PRODUCT-CONFORMANCE-PROOF-UNCHECKED](PRODUCT-CONFORMANCE-PROOF-UNCHECKED.md), which is about the
conformance records these bindings live in.

## Sources consulted

`Sim/icarus_sim/terrain_world.py`, `docs/conformance/version-bindings.json`,
`tools/validate_repo.py`, `board/done/PRODUCT-CAPABILITY-RANGE-DIVERGENCE.md`,
`board/done/PRINCIPAL-GRID-BOUND-PARITY.md`.

## Files and assets in scope

`Sim/icarus_sim/terrain_world.py`, `docs/conformance/version-bindings.json`, and whichever
conformance record claims the recipe module.

## Acceptance and evidence

A bound is stated once and enforced from that statement, demonstrated by changing the registry in
memory and showing the guard's behavior follows it — a guard that has not been shown to move with
the bound has not been shown to read it. If option 2 is taken, `tools/docs_check.py` resolves the
new binding and reports a mismatch when the bound moves without the version.

## Documentation impact

`docs/conformance/version-bindings.json` gains a binding; the conformance record owning the recipe
module states the parameter registry's version.

## Adversarial review and limitations

**This card is a shape, not a measured defect.** The one instance that actually bit — the grid
ceiling — is closed and correct today, verified by running the tests. Nothing is currently
diverging. A reader deciding priority should weigh it as prevention, and the honest argument for
doing it now is `PRODUCT-CONFORMANCE-PROOF-UNCHECKED`'s: it is cheapest while almost nothing
depends on the registry.

The `size` numbers above were read on 2026-09-21 and line numbers in `terrain_world.py` have moved
repeatedly; check them rather than quoting them.
