# LAB-SAMPLE — The lab opens on a committed world, and a run is timed

Status: done. Owner/session: local lab session, 2026-09-21.

## What changed

The lab generated a world on every page load, so opening `http://127.0.0.1:8765` gave
you either a flat ground-only baseline or a multi-minute wait. `/` now serves
`Fixtures/sample-world-v1.json`, a committed recipe-3 world, and generates nothing.
Building a world became an explicit act with a clock on it: **Run simulation** replaces
**Generate random world**, ticks a live elapsed counter while it waits, and on completion
reports the whole run — request, transfer and redraw — not the server's share of it.

- `tools/build_sample_world.py` writes the sample. It is a thin pin over
  `python -m fantasy_world_generator generate`, not a second serialiser, so the lab reads
  the same document an Unreal consumer does. `--check` rebuilds into a temporary file and
  compares, and runs in `validate_repo.py --stage artifacts`.
- `tools/terrain_lab.py` gains `--sample PATH` and `--fresh`. Serving a sample skips the
  startup generation and the static snapshot export. CLI terrain settings no longer reach
  the page, so the server prints which ones it is ignoring rather than letting a dead
  `--phase` pass for a bug.
- `tools/smoke_lab.py` covers both answers to `/`, because they fail differently: a
  missing fixture is a startup error, and `--fresh` is the only path that still proves
  `generate` runs under the server.
- Map icons: the ruin pin was a size-16 glyph with a 22 px halo, a white cross-out and a
  bold `RUIN` label on a map whose other markers are 2.5–5 px. It is now a warm-grey
  broken wall at size 6 with no halo and no label. The atlas fortress was a thin outlined
  triangle, one small pale mark beside a filled hamlet dot; it is now the slate
  crenellated keep the globe view already used, so the two views share one vocabulary.

## Two findings this forced

**The sample does NOT need to carry its timings, though this session first believed it
did.** `cli.py` strips `timing_ms` for byte-reproducibility and `terrain_biomes.py:100`
writes into that map unguarded, so `Advance age` on a stripped world looked certain to
raise `KeyError: 'timing_ms'` — [TIME-PERSISTED-WORLD-CANNOT-ADVANCE](TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md).
The sample was built with `--include-timings` on that basis and `--check` was weakened to
compare modulo timings. Both were wrong. The derivation was sound and answered a different
question than the card asks: it establishes that a producer would raise if reached with a
stripped world, not that any path reaches one. `terrain_history.adopt_world` sits between
the two and guards `timing_ms` at that single boundary rather than at the 32 producer
sites across 18 modules. Measured on a stripped seed-42 size-17 world: `advance_age_request`
advanced it 2→3 in 57 s, and `advance_time_request` accepted 7 days, 400 days and 9000
years. Of the lab's seven POST mutators, five adopt by construction, advance-age adopts and
is measured, and advance-time bypasses `adopt_world` yet passes anyway. The sample is now
built stripped and `--check` is an exact byte comparison again.

**A world without `build_stages` breaks the lab.** Served as a sample it throws two
uncaught `TypeError`s and renders an empty stage bar. That closed off the cheapest way to
shrink the file (64.6 MB instead of 147.4 MB at the same resolution, measured before the
planner fix) and is the reason the
sample carries snapshots that no exported-document consumer reads.

## Cost, measured

One desktop, seed 42, stage snapshots included. Both numbers are wall clock for
`build_sample_world.py`, and the size is the committed file.

| size | cells | build | file | cities / hamlets / fortresses / ruins |
|---|---|---|---|---|
| 17 | 16 × 16 | 80 s | 52.9 MB | 12 / 24 / 17 / 10 |
| 33 | 32 × 32 | 225 s | 162.1 MB | 35 / 98 / 56 / 38 |

(The size-33 row is the pinned sample as committed: timings stripped, remeasured after
LAB-PLANNER-FLOOD. It builds more than it used to, so it is larger than the 147.4 MB the same
request cost while two thirds of its cities were being refused.)

33 is pinned: a dozen cities on a whole globe is too sparse to read. An earlier session
figure claiming size 33 "did not finish in 35 minutes" was measured against a contended
box and is wrong; it is 4.3 minutes. Neither size resolves more than 1 of the 5 noise
octaves — 513 is the first that admits all five — so no committable sample has much
surface detail, and `Run simulation` at a higher resolution is how you see it.

## Evidence

- `tools/build_sample_world.py --check`: passes against the committed file, byte for
  byte. This is the first check in the repository asserting that `build_stages` is
  byte-reproducible; `compare_worlds` omits the sixteen snapshots.
- The server is `ThreadingHTTPServer` and answers `HEAD`. Single-threaded, one page load
  held the only worker while every other client -- a second tab, the pane's health check --
  queued behind it, which at 162 MB read as a hang: a `GET /` that had not returned after
  300 s now completes in 0.76 s, and a `HEAD /` that answered 501 now answers 200 in 0.22 s.
- `tools/smoke_lab.py`: passes; sample document and `--fresh` document both carry the
  expected marker.
- `tools/validate_repo.py --stage checks`: passes, 210 documents, 10 non-blocking
  warnings, none of them from this change.
- Browser, against the served fixture: page opens on the sample with no console errors,
  reporting 32 × 32 cells and 35 / 98 / 56 / 38 sites, all sixteen stages and
  `timing_ms` present. At the size-17 pin, **Run simulation** reported `Simulation
  complete in 109.1 s · 108.7 s generating and transferring, 0.4 s drawing` and
  **Advance age** off the sample reached age 3, which is what proves the timings
  decision above.
- Icons verified by sampling atlas pixels at known ruin and fortress coordinates rather
  than by eye: `#8a8177` ruin fill and `#c7c6d1` keep fill paint where they should.

## Documentation impact

`docs/terrain-math-lab.md` gains a section stating what `/` serves, what a run costs and
how to rebuild the sample; `docs/terrain-world-layers.md` and `README.md` correct their
launch claims, since `--phase` no longer limits what the page shows. No `Sim/` module
changed, so no conformance record moved.

## Limitations

- 162 MB of JSON in the tree, and git will store each rebuild whole. Rebuilds should be
  rare — only a recipe or generator change makes the sample stale — but nothing enforces
  that.
- The lab page is ~190,000 px tall at this resolution. It loads and paints, but the
  desktop browser pane dropped the tab once on first load and recovered on reopen.
- `validate_repo --stage artifacts` is about four minutes longer.
