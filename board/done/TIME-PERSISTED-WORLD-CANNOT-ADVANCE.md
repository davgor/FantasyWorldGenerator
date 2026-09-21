# TIME-PERSISTED-WORLD-CANNOT-ADVANCE - a world is either reproducible or advanceable, never both

> **CLOSED 2026-09-21. The claim does not reproduce on any route. Delivered as the
> Resolution below describes; this re-test is the verification that section asked for.**
>
> An earlier 2026-09-21 re-test marked this CONFIRMED on the grounds that
> `terrain_biomes.py:100` is unchanged and still writes into `timing_ms` unguarded. That is
> true and it is not the predicate. The guard is at `terrain_history.adopt_world`, which
> every stateless request API takes a caller's world through, so the producer being
> unguarded is the design rather than the defect — there are **32 such writes across 18
> modules** and guarding them one by one is what the Resolution deliberately did not do.
> Reading the producer answers a different question than calling the route, which is the
> near-miss this repository keeps finding.
>
> **What was actually run, 2026-09-21.** Two worlds exported through
> `fantasy_world_generator.cli generate` *without* `--include-timings` (seed 42, size 17,
> recipe 3, `humans` 9, generator 16) — one at phase 13, one at phase 16 — each asserted to
> carry no `timing_ms` key before any call. Then **every `POST /world/*` route in
> `tools/terrain_lab.py`**, sixteen of them, driven against those documents:
>
> ```
> /world/moon              OK      /world/quest            OK
> /world/advance-age       OK      /world/person-state     OK
> /world/advance-time 2d   OK      /world/blocks           OK
> /world/advance-time 3y   OK      /world/near             OK
> /world/summon            OK      /world/place            OK
> /world/corrupt           OK      /world/person           OK
> /world/cleanse           OK      /world/quests           OK
> /world/nomad             OK      /world/found-settlement OK
> ```
>
> No `KeyError: 'timing_ms'` anywhere, at either phase. `/world/cleanse` was driven against
> the output of `/world/corrupt` re-stripped through `cli._without_timings`, so the
> corrupted world it read was persisted-shaped too. `/world/moon`, `/world/advance-time`,
> `/world/quest`, `/world/person-state` and the five reads do **not** go through
> `adopt_world` and were the routes most likely to hold a residual; `terrain_time` carries
> its own `_timing` because it makes its own private copy, and the rest never write timing.
>
> **There is no CLI advance path to bypass.** `cli.py` exposes exactly four subcommands —
> `generate`, `asset-list`, `capabilities`, `controls` — so the persisted-world re-entry
> this card names has no command-line route at all.
>
> **Residual: none for this card.** It does not close
> `SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE`, which is the same shape on a different key and
> is a separate lane. Nothing in this verification touched `Fixtures/sample-world-v1.json`.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


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

## Resolution

**Delivered 2026-09-20.** The contract question the card insisted on answering first is
answered the way `cli.py` already asserted it: a persisted world does not carry timing, so
every writer must tolerate its absence.

It is not a `setdefault` at the first site reached, which this card rightly warns against --
there are roughly thirty unguarded writes across seventeen files and fixing one arms the
next. The guard goes where a persisted world *enters* instead. `terrain_history.adopt_world`
is the one seam every stateless request API now takes a caller's world through: deep copy,
`build_stages` shared rather than copied, `timing_ms` guaranteed. By the time any producer
runs the key exists, so all thirty are disarmed by one guarantee, and a request API written
later inherits it rather than having to remember.

Evidence, against a world generated through the CLI and read back off disk (seed 42, size
17, 62 blocks, no `timing_ms`): `lunar_request`, `advance_age_request`, `visitation_request`,
`corruption_request` and `nomad_request` all succeed. `cleanse_request` refuses correctly,
because that world carries no corruption to cleanse, and says so by name.

Covered by `tests/consumer_orchestrator.py::PersistBoundaryTests`, which generates, persists,
reads back and acts -- and asserts first that the persisted world really lacks `timing_ms`,
without which the rest of the class proves nothing.

**What this does not close:** the seven passes that append to `warnings` rather than
replacing it, found by the time-advance session and filed as
`SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE`. Four of them are reached by `advance_age_request`
on every call, so a world advanced ten ages already carries ten copies of the biome and
climate method strings. Same shape as this defect, different key, still open.

## Current state

**Closed 2026-09-21**, verified across every route rather than the one that was convenient;
see the verification at the top. Originally reported as Reproduced on seed 42 size 17 phase
13, both directions, against `biomes.json` at the data-ized catalogue.

`docs/conformance/time-advance.md` states the contract this closes under *Does not
establish*: the guard belongs at the boundary a persisted world re-enters through, the 32
producers are deliberately left alone, and the verification above is named there.

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

Sequence with [TIME-ADVANCE](../done/TIME-ADVANCE.md), which assumes this round trip works.

## Not owned

Pre-existing. Found while verifying the hidden-school route during the biome catalogue
data-ization, 2026-09-20; not introduced by it.
