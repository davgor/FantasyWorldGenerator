"""Integration checks for the static bundle; FWG_SOURCE selects the source checkout."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FWG_SOURCE', ROOT))


class ShowcaseTests(unittest.TestCase):
    def test_bundle_is_fresh_reproducible_and_traceable(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundles = []
            for name in ('first', 'second'):
                output = Path(temporary) / name
                subprocess.run([sys.executable, str(ROOT / 'tools/export_showcase.py'),
                                '--source', str(SOURCE), '--output', str(output)], check=True)
                bundles.append({p.name: p.read_bytes() for p in output.iterdir()})
            self.assertEqual(bundles[0], bundles[1])
            manifest = json.loads(bundles[0]['manifest.json'])
            self.assertEqual(manifest['format'], 2)
            self.assertEqual(manifest['source_repository'], 'https://github.com/davgor/FantasyWorldGenerator')
            revision = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
            self.assertEqual(manifest['source_revision'], revision)
            self.assertEqual([w['seed'] for w in manifest['worlds']], [42, 73, 108])
            self.assertEqual(len(bundles[0]), 5)
            index = bundles[0]['index.html'].decode()
            self.assertIn('https://github.com/davgor/FantasyWorldGenerator', index)
            for world in manifest['worlds']:
                payload = bundles[0][world['file']]
                self.assertEqual(hashlib.sha256(payload).hexdigest(), world['sha256'])
                self.assertEqual(len(payload), world['bytes'])
                self.assertIn(world['title'], index)
                html = payload.decode()
                self.assertTrue('constlive=false' in html.replace(' ', ''), 'snapshot must disable live generation')
                self.assertIn('Saved world showcase', html)
                self.assertIn('timing_ms', html)
                self.assertNotIn(str(SOURCE.resolve()), html)
                self.assertEqual(world['recipe']['overrides']['size'], 65)
            for relative, digest in manifest['source_files'].items():
                self.assertEqual(hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
