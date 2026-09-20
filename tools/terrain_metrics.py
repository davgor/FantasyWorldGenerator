"""Report elevation and relief statistics for generated worlds.

Glue only: argument parsing, generation, and formatting. Every measurement lives in
`icarus_sim.terrain_metrics`, which is pure and testable without running this.

  python tools/terrain_metrics.py --size 129
  python tools/terrain_metrics.py --sweep orogeny=1,3,6 --seeds 8
  python tools/terrain_metrics.py --size 65 --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Sim'))

from icarus_sim.terrain_world import default_config          # noqa: E402
from icarus_sim.terrain_lab import generate                  # noqa: E402
from icarus_sim.terrain_metrics import elevation_metrics     # noqa: E402


# (label, path into the metrics document, format spec). The columns worth watching
# when a terrain knob moves; everything else stays in --json.
COLUMNS = (('land%', ('land', 'land_fraction'), '.3f'),
           ('p90/p50', ('land', 'land_p90_over_p50'), '.3f'),
           ('land_max', ('land', 'land_max_m'), '.1f'),
           ('relief', ('land', 'total_relief_m'), '.1f'),
           ('craton', ('tectonics', 'craton_land_fraction'), '.3f'),
           ('ranges', ('ranges', 'range_systems'), 'd'),
           ('slope_p90', ('slope', 'p90_deg'), '.1f'),
           ('oct', ('noise', 'resolved_octaves'), 'd'))


def dig(document, path):
    for key in path:
        if not isinstance(document, dict) or key not in document:
            return None
        document = document[key]
    return document


def cell(value, spec):
    if value is None:
        return '-'
    return format(value, spec) if spec != 'd' else str(value)


def parse_sweep(raw):
    """'orogeny=1,3,6' -> ('orogeny', [1.0, 3.0, 6.0]), ints kept as ints."""
    if '=' not in raw:
        raise argparse.ArgumentTypeError(f'expected field=v1,v2,..., got {raw!r}')
    field, values = raw.split('=', 1)
    parsed = []
    for token in values.split(','):
        token = token.strip()
        parsed.append(int(token) if token.lstrip('-').isdigit() else float(token))
    return field.strip(), parsed


def measure(seed, size, phase, overrides):
    cfg = replace(default_config(3), seed=seed, size=size, phase=phase, **overrides)
    return elevation_metrics(generate(cfg))


def spread(samples):
    """median and interquartile range; the shape a default should be chosen against."""
    clean = [v for v in samples if v is not None]
    if not clean:
        return None, None, None
    if len(clean) < 4:
        return statistics.median(clean), min(clean), max(clean)
    quartiles = statistics.quantiles(clean, n=4)
    return statistics.median(clean), quartiles[0], quartiles[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--seeds', type=int, default=1,
                        help='measure this many consecutive seeds and report median [IQR]')
    parser.add_argument('--size', type=int, default=129)
    parser.add_argument('--phase', type=int, default=8)
    parser.add_argument('--sweep', type=parse_sweep, action='append', default=[],
                        help='field=v1,v2,... repeatable; one row per value')
    parser.add_argument('--json', action='store_true', help='raw metrics document')
    args = parser.parse_args(argv)

    seeds = [args.seed+i for i in range(max(1, args.seeds))]
    cases = [({}, 'baseline')]
    for field, values in args.sweep:
        cases = [(dict(overrides, **{field: value}), f'{field}={value:g}'
                  if isinstance(value, float) else f'{field}={value}')
                 for overrides, _ in cases for value in values]

    if args.json:
        document = {'seed': args.seed, 'size': args.size, 'phase': args.phase,
                    'cases': [{'label': label, 'overrides': overrides,
                               'metrics': measure(args.seed, args.size, args.phase, overrides)}
                              for overrides, label in cases]}
        print(json.dumps(document, indent=2, default=str))
        return 0

    width = max(len(label) for _, label in cases)+2
    print(f'seed {args.seed}'+(f'..{seeds[-1]}' if len(seeds) > 1 else '')
          + f'  size {args.size}  phase {args.phase}'
          + ('   (median [p25-p75] across seeds)' if len(seeds) > 1 else ''))
    header = f'{"case":<{width}}'+''.join(f'{name:>11}' for name, _, _ in COLUMNS)
    print(header)
    print('-'*len(header))
    for overrides, label in cases:
        columns = {name: [] for name, _, _ in COLUMNS}
        failure = None
        for seed in seeds:
            try:
                metrics = measure(seed, args.size, args.phase, overrides)
            except Exception as error:                       # unconstructible config is a result
                failure = str(error).split('\n')[0][:60]
                break
            for name, path, _ in COLUMNS:
                columns[name].append(dig(metrics, path))
        if failure:
            print(f'{label:<{width}} !! {failure}')
            continue
        row = f'{label:<{width}}'
        for name, _, spec in COLUMNS:
            median, low, high = spread(columns[name])
            row += f'{cell(median, spec):>11}'
        print(row)
        if len(seeds) > 1:
            detail = f'{"":<{width}}'
            for name, _, spec in COLUMNS:
                _, low, high = spread(columns[name])
                detail += f'{("["+cell(low, spec)+"-"+cell(high, spec)+"]") if low is not None else "-":>11}'
            print(detail)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
