"""Run from repository root: python tools/terrain_lab.py --serve."""
import argparse
from dataclasses import fields, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import platform
import statistics
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Sim'))
from icarus_sim.terrain_lab import Config, generate
from icarus_sim.terrain_seed import manual_seed, prompt_seed
from icarus_sim.terrain_patch import patch_request

# The world the served page opens on, built by tools/build_sample_world.py. Reading it
# costs a file read; generating its equivalent costs minutes, which is why page load no
# longer does that.
SAMPLE = ROOT / 'Fixtures' / 'sample-world-v1.json'


def report(result, live=False, sample=False):
    return report_document(json.dumps(result, allow_nan=False), live, sample)


def report_document(payload, live=False, sample=False):
    """Assemble the browser document around an already-serialised world.

    Takes the JSON text rather than the object so a served sample is encoded once at
    startup instead of on every request; the template and scripts are still read per
    call, so editing them is visible on reload.
    """
    template = Path(__file__).with_name('terrain_lab.html').read_text(encoding='utf-8')
    extension=Path(__file__).with_name('terrain_world.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('city_view_3d.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('city_view.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('world_debug.js').read_text(encoding='utf-8')
    # The flags are substituted before the payload: a world document cannot contain these
    # markers, but replacing in the other order would make that a question rather than a
    # fact about the template.
    shell = template.replace('__LIVE__', json.dumps(live)).replace('__SAMPLE__', json.dumps(sample))
    return shell.replace('__DATA__', payload)+'\n<script>\n'+extension+'\n</script>'


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


def serve(cfg, port, sample_json=None):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path not in ('/seed/manual', '/seed/prompt', '/patch', '/world/generate', '/world/advance-age', '/world/advance-time', '/world/summon', '/world/moon', '/world/corrupt', '/world/cleanse', '/world/nomad', '/world/found-settlement', '/world/blocks', '/world/near', '/world/place', '/world/person', '/world/quests', '/world/quest', '/world/person-state'):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                limit=256*1024*1024 if self.path in ('/world/advance-age', '/world/advance-time', '/world/summon', '/world/moon', '/world/corrupt', '/world/cleanse', '/world/nomad', '/world/found-settlement', '/world/blocks', '/world/near', '/world/place', '/world/person', '/world/quests', '/world/quest', '/world/person-state') else 65536
                if not 0 < length <= limit:
                    raise ValueError(f'JSON body must be 1..{limit} bytes')
                body = json.loads(self.rfile.read(length))
                if self.path == '/world/generate':
                    from icarus_sim.terrain_world import generate_request
                    result=generate_request(body)
                elif self.path == '/world/advance-age':
                    from icarus_sim.terrain_history import advance_age_request
                    result=advance_age_request(body)
                elif self.path == '/world/advance-time':
                    # The clock the other mutators assume: advance a live world by an
                    # elapsed span. Stateless like advance-age; a span of an age or more
                    # is answered with an estimate rather than a tick.
                    from icarus_sim.terrain_time import advance_time_request
                    result=advance_time_request(body)
                elif self.path == '/world/summon':
                    # The orchestrator summons a god (or sends a walking one home); stateless like advance-age.
                    from icarus_sim.terrain_visitation import visitation_request
                    result=visitation_request(body)
                elif self.path == '/world/moon':
                    # The sky and the surge at any day or hour, for an orchestrator driving a clock.
                    from icarus_sim.terrain_astrology import lunar_request
                    result=lunar_request(body)
                elif self.path == '/world/found-settlement':
                    # The player picks the ground; the world supplies the metadata.
                    from icarus_sim.terrain_settlement_api import found_settlement_request
                    result=found_settlement_request(body)
                elif self.path == '/world/corrupt':
                    # The hidden gods act only when something is watching: the caller passes
                    # its own cross-playthrough `encounters` count and the world decides.
                    from icarus_sim.terrain_corruption import corruption_request
                    result=corruption_request(body)
                elif self.path == '/world/cleanse':
                    from icarus_sim.terrain_corruption import cleanse_request
                    result=cleanse_request(body)
                elif self.path == '/world/nomad':
                    # Raise one band at a node. The villain-to-nomad seam calls this, and
                    # until now could only do so from inside Python.
                    from icarus_sim.terrain_nomad_api import nomad_request
                    result=nomad_request(body)
                elif self.path in ('/world/blocks', '/world/near', '/world/place', '/world/person', '/world/quests'):
                    # The bounded read surface: ask a question about a world instead of
                    # receiving all of it. Each read takes a whole world in, so these belong
                    # in the large-body bucket above rather than the 65536 one, and each
                    # answers with its own document. No read mints a version, mutates or
                    # regenerates -- see docs/conformance/read-surface.md.
                    from icarus_sim.terrain_read import READS
                    result=READS[self.path[len('/world/'):]](body)
                elif self.path == '/world/quest':
                    # The actor-scale writes a playing session makes: what its party
                    # did with an offer. Note this is not /world/quests, which reads
                    # the board. See docs/conformance/actor-scale-writes.md.
                    from icarus_sim.terrain_quest_api import quest_request
                    result=quest_request(body)
                elif self.path == '/world/person-state':
                    # Whether a person is still in the world, in one published
                    # vocabulary, translated at the boundary into whichever of the
                    # four the record's own block uses.
                    from icarus_sim.terrain_person_api import person_state_request
                    result=person_state_request(body)
                elif self.path == '/patch':
                    result=patch_request(body)
                else:
                    key = 'seed' if self.path == '/seed/manual' else 'prompt'
                    if not isinstance(body,dict) or set(body) != {key}:
                        raise ValueError(f'JSON body must contain only {key}')
                    result = manual_seed(body[key]) if key == 'seed' else prompt_seed(body[key])
                payload = json.dumps(result,allow_nan=False).encode()
            except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
                # A RequestError carries the field, the value and the bound; anything else
                # only has its text. Both answer 400, so a caller branches on the body.
                document = exc.document() if hasattr(exc, 'document') else {'error':str(exc)}
                payload = json.dumps(document).encode()
                self.send_response(400)
            else:
                self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_HEAD(self):
            """Answer a liveness probe without building the document it asks about.

            Preview harnesses and uptime checks send HEAD; the base handler has no
            do_HEAD, so they got 501 and read the lab as broken. Producing the real
            body to discard it would cost a whole page, so this reports reachability
            and omits Content-Length rather than claiming a size it did not measure.
            """
            if urlparse(self.path).path not in ('/', '/generate'):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()

        def do_GET(self):
            route = urlparse(self.path)
            try:
                if route.path not in ('/', '/generate'):
                    self.send_error(404)
                    return
                if route.path == '/':
                    # The sample is the page. Generating one here is what made opening the
                    # lab a wait; Run simulation is where a new world is paid for now.
                    payload = (report_document(sample_json, live=True, sample=True)
                               if sample_json is not None
                               else report(generate(cfg), live=True)).encode()
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
    source = f'prebuilt sample, {len(sample_json)/1e6:.1f} MB' if sample_json is not None else 'generated per page load'
    print(f'Terrain lab: http://127.0.0.1:{port} ({source}; Ctrl+C to stop)', flush=True)
    # Threaded, because one request now moves a hundred and sixty megabytes. On the
    # single-threaded server a page load held the only worker for seconds and every
    # other client -- a second tab, the preview pane's health check, a curl -- sat in
    # the accept backlog behind it looking like a hang.
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


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
    parser.add_argument('--sample', type=Path, default=SAMPLE,
                        help='Prebuilt world served at / (build it with tools/build_sample_world.py)')
    parser.add_argument('--fresh', action='store_true',
                        help='Generate from these settings on every page load instead of serving the sample')
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
    # Serving the sample makes the CLI terrain settings irrelevant to the page, so the
    # static snapshot export is skipped with it: writing a report nobody asked for was
    # only ever a side effect of having generated one anyway.
    sample_json = None
    if args.serve and not args.fresh:
        if not args.sample.is_file():
            parser.error(f'{args.sample} is missing. Build it with '
                         'python tools/build_sample_world.py, or pass --fresh to generate '
                         'from these settings on every page load.')
        sample_json = args.sample.read_text(encoding='utf-8')
        try:
            json.loads(sample_json)
        except ValueError as exc:
            parser.error(f'{args.sample} is not readable as JSON: {exc}')
        # Terrain settings on the command line used to be what the page showed. They now
        # reach only /generate, and a silently ignored --phase is exactly the kind of thing
        # someone spends twenty minutes disbelieving.
        ignored = sorted({argument.lstrip('-').split('=')[0] for argument in sys.argv[1:]
                          if argument.startswith('--')} & {f.name for f in fields(Config)})
        if ignored:
            print(f'Note: {", ".join(ignored)} do not change the served page, which is the '
                  f'prebuilt sample in {args.sample}. They still apply to /generate; pass '
                  '--fresh to generate the page from them instead.', flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    if sample_json is None:
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
        serve(cfg, args.port, sample_json)


if __name__ == '__main__':
    main()
