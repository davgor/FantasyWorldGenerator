"""Regenerate the Pages showcase from FantasyWorldGenerator (Python 3.12)."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import subprocess
import sys

REPOSITORY = 'https://github.com/davgor/FantasyWorldGenerator'
WORLDS = [
    ('crossroads', 'The Crossroads', 42, {}, 'Magical networks, competing habitats, settlements and beast lairs.'),
    ('frost', 'The Frostbound Reach', 73, {'temperature_offset': -12, 'seasonality': 1.4, 'mountain_abundance': 1.8}, 'Cold climates, snow and ice across mountain and coastal refuges.'),
    ('islands', 'The Shattered Coast', 108, {'archipelago_count': 10, 'archipelago_occurrence': 1., 'sky_occurrence': 1., 'sky_clusters': 5}, 'Ocean archipelagos, floating islands and coastal communities.'),
]


def omit_timings(value):
    """Keep the renderer's timing map, without nondeterministic wall-clock values."""
    if isinstance(value, dict):
        return {key: ({} if key == 'timing_ms' else omit_timings(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [omit_timings(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'Artifacts/showcase')
    args = parser.parse_args()
    source = args.source.resolve()
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
        parser.error('Source checkout must be clean so the published revision identifies the generated code.')
    sys.path.insert(0, str(source / 'tools'))
    import terrain_lab
    from icarus_sim.terrain_world import generate_request

    manifest = {'format': 2, 'source_repository': REPOSITORY, 'source_revision': revision,
                'timings': 'omitted', 'source_files': {}, 'worlds': []}
    for folder in [source / 'Sim/icarus_sim', source / 'tools']:
        for path in sorted(folder.rglob('*')):
            if path.suffix in ('.py', '.json', '.js', '.html'):
                manifest['source_files'][path.relative_to(source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    payloads = {}
    for slug, title, seed, overrides, description in WORLDS:
        world = omit_timings(generate_request({'recipe_version': 2, 'seed': seed, 'overrides': {'size': 65, **overrides}}))
        html = terrain_lab.report(world, live=False)
        html += '''<style>
        #world-mode,#world-generate,#world-advance-age,#world-params,#local-lab,.local-lab{display:none!important}
        .layout{display:block}aside{margin-bottom:20px}body{padding:16px}select{max-width:100%}
        </style><script>
        document.getElementById('world-status').textContent='Seed '+data.config.seed+' · Saved world showcase. Explore layers and lairs; generation runs in GitHub Actions. Timings omitted.';
        document.getElementById('world-status').parentElement.querySelector('h2').textContent='Saved world';
        </script>'''
        filename = slug + '.html'
        payloads[filename] = html.encode('utf-8')
        manifest['worlds'].append(dict(id=slug, title=title, description=description, file=filename,
                                      seed=seed, recipe=world['recipe'], bytes=len(payloads[filename]),
                                      sha256=hashlib.sha256(payloads[filename]).hexdigest()))
        print(slug, len(payloads[filename]), 'bytes', flush=True)
    template = Path(__file__).with_name('mathlab-showcase.html').read_text(encoding='utf-8')
    options = ''.join(f'<option value="{w[0]}">{escape(w[1])}</option>' for w in WORLDS)
    descriptions = json.dumps({w[0]: f'{w[4]} Seed {w[2]}.' for w in WORLDS})
    largest = max(w['bytes'] for w in manifest['worlds']) / 1_000_000
    index = (template.replace('__OPTIONS__', options).replace('__DESCRIPTIONS__', descriptions)
             .replace('__REVISION__', revision).replace('__SIZE__', f'{largest:.1f}'))
    payloads['index.html'] = index.encode('utf-8')
    payloads['manifest.json'] = (json.dumps(manifest, indent=2, allow_nan=False) + '\n').encode('utf-8')
    # Generate everything before replacing any existing sample; failures cannot publish partial worlds.
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, payload in payloads.items():
        (args.output / filename).write_bytes(payload)


if __name__ == '__main__':
    main()
