"""Build the prebuilt world the local lab shows on page load.

The lab used to generate a world every time someone opened http://127.0.0.1:8765,
which meant the page was either a flat ground-only baseline or a several-minute
wait before anything appeared. The sample closes that: one pinned world is built
here, committed, and served as-is, so opening the lab is a file read. Running a
new simulation is then an explicit act with a visible clock, not the cost of
looking.

The sample is not a new export format. It is exactly what
`python -m fantasy_world_generator generate` writes, so the lab reads the same
document an Unreal consumer does and no second serialiser exists to drift. Two of
that command's flags are forced here:

- `--include-build-stages`, because the lab's stage inspector reads them. They
  are roughly two thirds of the file.
- timings stay stripped, the exporter's own default, so the committed bytes are
  reproducible and `--check` can be an exact byte comparison.

An earlier version of this file forced `--include-timings`, on the belief that a
stripped world could not be advanced -- `terrain_biomes.py` writes into `timing_ms`
unguarded, so `Advance age` looked certain to raise `KeyError: 'timing_ms'`. That
was derived from board/backlog/TIME-PERSISTED-WORLD-CANNOT-ADVANCE and never
tested, and it is false: `terrain_history.adopt_world` guards the seam every
stateless request API takes a caller's world through, `timing_ms` included,
deliberately at that one boundary rather than at the 32 producer sites. Measured
on a stripped seed-42 size-17 world: `advance_age_request` advances it, and
`advance_time_request` accepts all three elapsed bands. Do not reintroduce the
flag without a failing case.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

DESTINATION = ROOT / "Fixtures" / "sample-world-v1.json"

# The pinned request. Seed 42 is the seed the determinism gates and the conformance
# fixtures already use, so a sample that disagrees with them is a visible disagreement
# rather than two unrelated worlds.
#
# The size is the rung of the lab's ladder (17/33/65/129) the sample sits on, and it is
# the only knob here with a price. Measured on this generator, seed 42, one desktop, with
# the stage snapshots the lab's inspector needs:
#
#   size 17  ->  16 x 16 cells,   80 s,   52.9 MB,  12 cities,  24 hamlets, 10 ruins
#   size 33  ->  32 x 32 cells,  304 s,  162.3 MB,  35 cities,  98 hamlets, 38 ruins
#
# 33, because at 16 x 16 the world is too sparse to read: a dozen cities on a whole globe.
# The cost is a 162 MB file in the tree and a `--check` that takes five minutes, which is
# why that gate runs in `--stage artifacts` beside the other multi-minute generations and
# not in `checks`.
#
# Stated so nobody re-measures it in surprise: 33 still resolves only 1 of the 5 noise
# octaves, so the terrain has little surface detail either way. Octave admission needs
# step <= wavelength/2^k and 513 is the first size that admits all five -- far past
# anything committable. Run simulation at a higher resolution to see that.
SEED = 42
SIZE = 33


def build(destination: Path) -> float:
    """Write the pinned world to `destination`; return the seconds it took."""
    from fantasy_world_generator.cli import main as generate

    started = time.perf_counter()
    code = generate(["generate", "--seed", str(SEED), "--size", str(SIZE),
                     "--include-build-stages", "--output", str(destination)])
    if code != 0:
        raise ValueError(f"the pinned sample request was refused (exit {code}); "
                         "the recipe no longer accepts it")
    return time.perf_counter() - started


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="rebuild into a temporary file and fail when the committed "
                             "sample differs by a single byte. This is a full world "
                             "generation, so it costs what building one costs.")
    arguments = parser.parse_args(argv)

    if arguments.check:
        if not DESTINATION.is_file():
            print(f"{DESTINATION.relative_to(ROOT)} is missing; run "
                  "python tools/build_sample_world.py", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / DESTINATION.name
            elapsed = build(candidate)
            if candidate.read_bytes() != DESTINATION.read_bytes():
                print(f"{DESTINATION.relative_to(ROOT)} is stale: a rebuild of seed {SEED} "
                      f"at size {SIZE} produced different bytes. Run "
                      "python tools/build_sample_world.py", file=sys.stderr)
                return 1
        print(f"Lab sample current: seed {SEED}, size {SIZE}, "
              f"{DESTINATION.stat().st_size / 1e6:.1f} MB, rebuilt in {elapsed:.1f} s.")
        return 0

    elapsed = build(DESTINATION)
    print(f"Wrote {DESTINATION.relative_to(ROOT)}: seed {SEED}, size {SIZE}, "
          f"{DESTINATION.stat().st_size / 1e6:.1f} MB in {elapsed:.1f} s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
