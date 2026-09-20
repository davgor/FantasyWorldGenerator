# TIME-PERSISTED-WORLD-CANNOT-ADVANCE - a world is either reproducible or advanceable, never both

## Observed behavior

`advance_age_request` on a world written by the CLI raises `KeyError: 'timing_ms'` before it
does any work. The same call on the same seed succeeds if the world was written with
`--include-timings`:

```
default (timings stripped)   timing_ms present=False -> KeyError: 'timing_ms'
--include-timings            timing_ms present=True  -> ADVANCED OK
```

Both halves are doing exactly what they were built to do.

`cli.py:30` strips `timing_ms` on purpose, and its docstring says why: *"Timings are a
profiling aid, not part of the interchange contract, and they are the only reason two runs of
the same seed differed."* `--include-timings` is documented as making the output **not**
byte-reproducible. So the default is the reproducible document, and reproducibility is the
guarantee `validate_repo` exists to enforce.

`terrain_biomes.py:100` then writes into `result['timing_ms']` unguarded, reached through
`advance_age_request` -> `refresh_environment` -> `add_terrain_labels`.

`terrain_history.py:755` instructs the caller to do precisely what breaks: *"Persist this
returned world for subsequent calls."*

## Why it matters

This is **not an unguarded write**, and framing it that way invites a one-line `setdefault`
that hides the real question. It is two individually correct requirements that are jointly
unsatisfiable: the interchange document must be byte-reproducible, and the interchange
document must be advanceable. Today you must pick one.

The seam has no test because every existing test advances an **in-memory** world that still
carries the key. Nothing exercises persist-then-advance, which is the documented workflow and
the only one a real consumer would use.

This is the third defect traced to the determinism guarantee interacting badly with something
else, after the size-17 reference world that resolves zero octaves and the ceiling sentinels
that turned rejection tests into legal work. The guarantee is right; its blast radius is not
being tracked.

## Current state

Unfixed. Reproduced on seed 42 size 17 phase 13, both directions, against `biomes.json` at
the data-ized catalogue.

## Proposed fix

Decide the contract first, because the two fixes are not the same size:

- **If a persisted world is not meant to carry timing** — which is what `cli.py:30` already
  asserts — then *every* writer into `timing_ms` must tolerate its absence, not just
  `terrain_biomes.py:100`. Audit all producers; a single `setdefault` at the one site that
  happens to be reached first leaves the next one armed.
- **If a persisted world is meant to carry timing**, then it must carry a reproducible form of
  it (zeros, or omitted keys rather than omitted map), and `--include-timings` becomes a
  profiling flag rather than a correctness flag.

Either way this needs a test over the real seam: generate through the CLI, read the file back,
advance. An in-memory advance cannot catch it and never will.

Sequence with [TIME-ADVANCE](TIME-ADVANCE.md), which assumes this round trip works.

## Not owned

Pre-existing. Found while verifying the hidden-school route during the biome catalogue
data-ization, 2026-09-20; not introduced by it.
