"""Run from repository root: python tools/terrain_lab.py --serve."""
import argparse
from dataclasses import fields, replace
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import platform
import statistics
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Sim'))
from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_seed import manual_seed, prompt_seed
from icarus_sim.terrain_patch import patch_request


def report(result, live=False):
    template = Path(__file__).with_name('terrain_lab.html').read_text(encoding='utf-8')
    extension=Path(__file__).with_name('terrain_world.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('city_view_3d.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('city_view.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('world_debug.js').read_text(encoding='utf-8')
    return template.replace('__DATA__', json.dumps(result, allow_nan=False)).replace('__LIVE__', json.dumps(live))+'\n<script>\n'+extension+'\n</script>'


def benchmark(cfg, repeats):
    results = []
    for size in (65, 129, 257):
        config = replace(cfg, size=size)
        generate(config)  # unmeasured warm-up
        timings = [generate(config)['timing_ms'] for _ in range(repeats)]
        results.append({'size':size, 'cells':size*size,
                        'median_ms':{k:statistics.median(t[k] for t in timings) for k in timings[0]},
                        'total_min_ms':min(t['total'] for t in timings),
                        'total_max_ms':max(t['total'] for t in timings)})
    return {'python':sys.version, 'platform':platform.platform(), 'repeats':repeats,
            'config':vars(cfg), 'results':results,
            'scope':'CPU wall times only; excludes HTML/JSON encoding, disk I/O and browser rendering. Resolution can change resolved octave count.'}


def serve(cfg, port):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path not in ('/seed/manual', '/seed/prompt', '/patch', '/world/generate', '/world/advance-age', '/world/summon', '/world/moon'):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                limit=256*1024*1024 if self.path in ('/world/advance-age', '/world/summon', '/world/moon') else 65536
                if not 0 < length <= limit:
                    raise ValueError(f'JSON body must be 1..{limit} bytes')
                body = json.loads(self.rfile.read(length))
                if self.path == '/world/generate':
                    from icarus_sim.terrain_world import generate_request
                    result=generate_request(body)
                elif self.path == '/world/advance-age':
                    from icarus_sim.terrain_history import advance_age_request
                    result=advance_age_request(body)
                elif self.path == '/world/summon':
                    # The orchestrator summons a god (or sends a walking one home); stateless like advance-age.
                    from icarus_sim.terrain_visitation import visitation_request
                    result=visitation_request(body)
                elif self.path == '/world/moon':
                    # The sky and the surge at any day or hour, for an orchestrator driving a clock.
                    from icarus_sim.terrain_astrology import lunar_request
                    result=lunar_request(body)
                elif self.path == '/patch':
                    result=patch_request(body)
                else:
                    key = 'seed' if self.path == '/seed/manual' else 'prompt'
                    if not isinstance(body,dict) or set(body) != {key}:
                        raise ValueError(f'JSON body must contain only {key}')
                    result = manual_seed(body[key]) if key == 'seed' else prompt_seed(body[key])
                payload = json.dumps(result,allow_nan=False).encode()
            except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
                payload = json.dumps({'error':str(exc)}).encode()
                self.send_response(400)
            else:
                self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            route = urlparse(self.path)
            try:
                if route.path not in ('/', '/generate'):
                    self.send_error(404)
                    return
                if route.path == '/':
                    payload = report(generate(cfg), live=True).encode()
                    kind = 'text/html; charset=utf-8'
                else:
                    values = parse_qs(route.query, strict_parsing=True)
                    types = {f.name:f.type for f in fields(Config)}
                    if set(values)-set(types) or any(len(v)!=1 for v in values.values()):
                        raise ValueError('Unknown or repeated parameter')
                    changed = replace(cfg, **{k:types[k](v[0]) for k,v in values.items()})
                    if changed.size > 257:
                        raise ValueError('Interactive size is limited to 257; use CLI for larger grids')
                    payload = json.dumps(generate(changed), allow_nan=False).encode()
                    kind = 'application/json'
            except (ValueError, OverflowError) as exc:
                self.send_error(400, str(exc))
                return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)
    print(f'Terrain lab: http://127.0.0.1:{port} (Ctrl+C to stop)', flush=True)
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    from icarus_sim.terrain_world import default_config
    defaults=default_config(3)
    for f in fields(Config):
        parser.add_argument('--'+f.name, type=f.type, default=getattr(defaults,f.name))
    parser.add_argument('--output', type=Path, default=Path('Artifacts/terrain-lab'))
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--prompt', help='Hash text to a seed; overrides --seed without interpreting terrain intent')
    args = parser.parse_args()
    if args.world_recipe != 3 and not any(a=="--phase" or a.startswith("--phase=") for a in sys.argv[1:]):
        args.phase=9
    try:
        if args.prompt is not None:
            args.seed = prompt_seed(args.prompt)['seed']
        cfg = Config(**{f.name:getattr(args,f.name) for f in fields(Config)})
        if not 1 <= args.repeats <= 20:
            raise ValueError('repeats must be 1..20')
        if args.serve and cfg.size > 257:
            raise ValueError('Interactive size is limited to 257')
    except ValueError as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True, exist_ok=True)
    result = generate(cfg)
    result['seed_source'] = prompt_seed(args.prompt) if args.prompt is not None else manual_seed(cfg.seed)
    (args.output/'terrain.json').write_text(json.dumps(result, allow_nan=False), encoding='utf-8')
    (args.output/'index.html').write_text(report(result), encoding='utf-8')
    print(json.dumps({'report':str((args.output/'index.html').resolve()), 'timing_ms':result['timing_ms']}), flush=True)
    if args.benchmark:
        data = benchmark(cfg, args.repeats)
        (args.output/'benchmark.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(json.dumps(data, indent=2), flush=True)
    if args.serve:
        serve(cfg, args.port)


if __name__ == '__main__':
    main()
