"""Integration checks for the static bundle; FWG_SOURCE selects the source checkout."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FWG_SOURCE', ROOT))
BLOCK = 1 << 20


def bundle_digests(directory):
    """`{filename: sha256hex}` for one bundle, without a payload ever being resident.

    The comparison this backs used to be `{p.name: p.read_bytes()}` over BOTH bundles,
    held simultaneously so they could be compared -- six size-65 pages, every byte of
    them in this process, to answer one yes/no question. A digest answers the same
    question and weakens nothing: the test already hashes each payload against the
    manifest a few lines below, so SHA-256 was already the standard of proof here.

    Read in blocks rather than whole, or the peak comes back one file at a time instead
    of all at once, which is a smaller version of the same problem.
    """
    digests = {}
    for path in sorted(directory.iterdir()):
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(BLOCK), b''):
                digest.update(block)
        digests[path.name] = digest.hexdigest()
    return digests


class BundleDigestTests(unittest.TestCase):
    """The bundle comparison itself. Cheap on purpose: no world is generated here.

    `ShowcaseTests` below costs six size-65 world generations, so the property that the
    comparison is sound must be provable without paying that, or it never gets checked.
    """

    def _write(self, directory, files):
        directory.mkdir(parents=True, exist_ok=True)
        for name, payload in files.items():
            (directory / name).write_bytes(payload)
        return directory

    def test_digest_matches_a_whole_file_hash(self):
        """Chunked reading must not change the answer, or the comparison is not a digest."""
        with tempfile.TemporaryDirectory() as temporary:
            # Larger than the read block, and not a multiple of it, so a boundary bug shows.
            payload = bytes(range(256)) * 9000 + b'tail'
            folder = self._write(Path(temporary) / 'b', {'page.html': payload})
            self.assertEqual(bundle_digests(folder),
                             {'page.html': hashlib.sha256(payload).hexdigest()})

    def test_identical_bundles_compare_equal_and_one_changed_byte_does_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            body = b'<html>' + b'x' * 5000
            first = self._write(Path(temporary) / 'first',
                                {'a.html': body, 'manifest.json': b'{}'})
            second = self._write(Path(temporary) / 'second',
                                 {'a.html': body, 'manifest.json': b'{}'})
            self.assertEqual(bundle_digests(first), bundle_digests(second))

            (second / 'a.html').write_bytes(body[:-1] + b'y')
            self.assertNotEqual(bundle_digests(first), bundle_digests(second),
                                'a single changed byte must still fail the comparison, '
                                'or switching from bytes to digests weakened the test')

    def test_a_missing_or_extra_file_is_caught(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = self._write(Path(temporary) / 'first', {'a.html': b'a', 'b.html': b'b'})
            second = self._write(Path(temporary) / 'second', {'a.html': b'a'})
            self.assertNotEqual(bundle_digests(first), bundle_digests(second))


class ExporterGuardTests(unittest.TestCase):
    """The size guard, and WHEN it runs. No world is generated here either.

    GitHub warns at 50 MB per file and refuses at 100, and every `main` merge commits these
    bundles into the portfolio repository, so the guard is the reason an unnoticed growth is
    expensive rather than merely slow. What it could not do was arrive in time: it was a
    second loop over the finished manifest, so the cheapest possible failure -- a world too
    large to publish -- cost three size-65 generations before anyone heard about it.
    """

    def _exporter(self):
        spec = importlib.util.spec_from_file_location(
            'fwg_export_showcase_under_test', ROOT / 'tools' / 'export_showcase.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_verdict_boundaries(self):
        verdict = self._exporter().page_size_verdict
        # The bounds are GitHub's, and both are inclusive in the code this replaces.
        self.assertEqual(verdict(100.0), 'refuse')
        self.assertEqual(verdict(150.0), 'refuse')
        self.assertEqual(verdict(99.9), 'warn')
        self.assertEqual(verdict(50.0), 'warn')
        self.assertEqual(verdict(49.9), 'ok')
        self.assertEqual(verdict(0.0), 'ok')

    def test_the_guard_runs_inside_the_generation_loop(self):
        """A guard in a second pass cannot save the runs it is meant to prevent.

        Checked structurally rather than by generating an oversized world, because
        provoking one costs exactly what this card is about. What must be true is that
        the refusal is reachable from inside the loop over `WORLDS`, so world two is
        never generated once world one is known to be unpublishable.
        """
        source = (ROOT / 'tools' / 'export_showcase.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        loops = [node for node in ast.walk(tree)
                 if isinstance(node, ast.For)
                 and any(isinstance(n, ast.Name) and n.id == 'WORLDS'
                         for n in ast.walk(node.iter))]
        self.assertEqual(len(loops), 1,
                         'expected exactly one loop over WORLDS in the exporter; found '
                         '%d, so this check no longer knows which one to inspect'
                         % len(loops))
        called = {n.func.id for n in ast.walk(loops[0])
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn('page_size_verdict', called,
                      'the generation loop does not consult the size guard, so an '
                      'oversized page is still discovered only after every world has '
                      'been generated -- which is the whole finding of '
                      'board/done/PERF-SHOWCASE-TEST-COST.md')


class ShowcaseTests(unittest.TestCase):
    def test_bundle_is_fresh_reproducible_and_traceable(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundles = []
            for name in ('first', 'second'):
                output = Path(temporary) / name
                # Bounded. This child generates three size-65 worlds and peaks in the
                # gigabytes, so an exporter that wedges is the most expensive hang in the
                # suite -- and `subprocess.run` reaps it on a Ctrl-C but not on a hang.
                # The bound is deliberately far above the measured cost rather than close
                # to it: five sessions share this machine and a tight bound turns
                # contention into a red test. See board/done/PERF-SHOWCASE-TEST-COST.md.
                subprocess.run([sys.executable, str(ROOT / 'tools/export_showcase.py'),
                                '--source', str(SOURCE), '--output', str(output), '--allow-dirty'],
                               check=True, timeout=3600)
                bundles.append(bundle_digests(output))
            self.assertEqual(bundles[0], bundles[1],
                             'two exporter runs did not produce identical bundles, so '
                             'the showcase is not reproducible; the differing filenames '
                             'are the keys whose digests disagree above')
            # Everything below reads one file at a time from the first bundle, which is
            # still on disk. Holding the whole bundle to re-read it is what this card is
            # about; `bundles[0]` is now five digests, not five payloads.
            first = Path(temporary) / 'first'
            manifest = json.loads((first / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['format'], 3)
            dirty=bool(subprocess.check_output(['git','-C',str(SOURCE),'status','--porcelain'],text=True,timeout=120).strip())
            self.assertEqual(manifest['source_dirty'],dirty)
            self.assertEqual(manifest['publication_ready'],not dirty)
            self.assertEqual(manifest['source_repository'], 'https://github.com/davgor/FantasyWorldGenerator')
            revision = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True, timeout=60).strip()
            self.assertEqual(manifest['source_revision'], revision)
            self.assertEqual([w['seed'] for w in manifest['worlds']], [42, 73, 108])
            self.assertEqual(len(bundles[0]), 5)
            index = (first / 'index.html').read_text(encoding='utf-8')
            self.assertIn('https://github.com/davgor/FantasyWorldGenerator', index)
            for world in manifest['worlds']:
                # One page resident at a time, released before the next is read.
                payload = (first / world['file']).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), world['sha256'])
                self.assertEqual(len(payload), world['bytes'])
                self.assertIn(world['title'], index)
                html = payload.decode()
                self.assertTrue('constlive=false' in html.replace(' ', ''), 'snapshot must disable live generation')
                self.assertIn('Saved world showcase', html)
                if dirty:self.assertIn('Uncommitted local preview',html)
                self.assertIn('timing_ms', html)
                self.assertNotIn(str(SOURCE.resolve()), html)
                self.assertEqual(world['recipe']['overrides']['size'], 65)
                self.assertEqual(world['recipe']['version'], 3)
            for relative, digest in manifest['source_files'].items():
                self.assertEqual(hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
