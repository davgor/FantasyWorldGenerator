# SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE - a replacement pass that appends

## Observed behavior

`terrain_seasons.add_seasonal_food` replaces `result['seasonal_food']` wholesale. Every
line of it reads as a pure recomputation from settlements, roads, layers and profiles —
and then the last line before its timing is:

```python
result['warnings'].append(result['seasonal_food']['limits'])
```

`warnings` is a world-level list shared by every pass. So the function is a wholesale
replacement in its own block and an **accumulator** in someone else's, and nothing about
its shape says so.

Run once at generation this is invisible: one run, one warning. Run on a cadence — which
is what `terrain_time` now does, at one call per season — and the list becomes a tally of
how many times the pass ran rather than a statement of what the world's limits are.

## Why it matters beyond the tick

It made the **same elapsed span produce different worlds depending on how it was cut**. One
call of a year appended one warning; four calls of ninety days appended four. That is a
determinism failure in a capability whose central guarantee is that chunking cannot reach
the result, and it had nothing to do with any RNG.

It was found by `test_a_year_in_four_seasons_is_a_year` in `Sim/tests/test_time_advance.py`
— by a byte comparison, not by reading the code. Nobody reviewing `add_seasonal_food` would
look at that line twice.

## Current state

Mitigated at the consumer, not fixed at the source. `terrain_time._dedupe_warnings` runs
after every coalesced pass, preserving order and dropping only exact repeats, so the tick
is correct. `add_seasonal_food` is unchanged and still appends on every call.

## Why this is a card and not just a fix

The shape will catch the next person. Any pass that is "a wholesale replacement" in every
line but one, where the one writes to a structure it does not own, is invisible to review
and invisible to a single-run test. Two questions worth answering once rather than per
caller:

1. **Is `warnings` append-only by contract, or is it a set of statements?** If the second,
   the dedupe belongs in whatever owns `warnings`, not in each consumer that might run a
   pass twice. If the first, then no pass that writes to it may be run on a cadence without
   the caller knowing, and that is worth stating where `warnings` is defined.
2. **Which other passes append rather than replace?** Answered, 2026-09-20 — there are
   **seven**, and `add_seasonal_food` is only the one the tick happens to run:

   | Pass | Site | Reached by a cadence today? |
   |---|---|---|
   | `add_seasonal_food` | `terrain_seasons.py:113` | **yes**, `terrain_time` season cadence |
   | `add_terrain_labels` | `terrain_biomes.py:99` | via the age band's `refresh_environment` |
   | `add_climate` | `terrain_climate.py:89` | via the age band |
   | `add_water` | `terrain_water.py:74` | no |
   | `add_magic` | `terrain_magic.py:87` | no — and it is dead code, see `MAGIC-ADD-MAGIC-DEAD-WRITER.md` |
   | `generate_history` | `terrain_history.py:588` | no |
   | `fill_cities` / `fill_hamlets` | `city_planner.py:138`, `hamlet_planner.py:135` | via the age band, and guarded by a resolution test so they do not always fire |

   The age-band entries matter: `advance_age_request` runs `refresh_environment` on every
   call, so a world advanced ten ages carries ten copies of the biome and climate method
   strings. That is pre-existing and unrelated to the tick, and it is the same defect.

## Proposed fix

Decide (1), then either move the dedupe to the owner of `warnings` and delete the
consumer-side mitigation, or document `warnings` as append-only and make every cadence-run
pass responsible for its own idempotence. Either way, answer (2) in the same change — a fix
at the one site the tick reaches leaves the next one armed, which is the same mistake
`TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md` warns about for `timing_ms`.

## Not owned

Pre-existing. Found 2026-09-20 while building `TIME-ADVANCE`; not introduced by it. Raised
by the controls-and-tooling session as worth a card of its own, and they are right.
