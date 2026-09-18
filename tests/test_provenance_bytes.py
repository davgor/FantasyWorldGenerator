"""Provenance hashes must be checkable on every platform.

verify_provenance.py hashes working-tree bytes. Under `* text=auto` a Windows
checkout rewrites LF-committed files to CRLF, so 35 destinations failed there
while passing in Linux CI — the check was effectively unrunnable on the primary
development machine. Marking every pinned destination `-text` keeps the working
tree byte-identical to the committed content everywhere; this test keeps that
list complete as the manifest grows.
"""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / 'provenance/extraction-manifest.json').read_text(encoding='utf-8'))


class ProvenanceByteTests(unittest.TestCase):
    def test_every_pinned_destination_is_excluded_from_eol_normalization(self):
        if shutil.which('git') is None:
            self.skipTest('git is required to resolve .gitattributes')
        destinations = [row['destination'] for row in manifest()['files']]
        result = subprocess.run(['git', 'check-attr', 'text', '--', *destinations],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        unprotected = []
        for line in result.stdout.splitlines():
            destination, _, value = line.rpartition(': text: ')
            if value.strip() != 'unset':
                unprotected.append(destination)
        self.assertEqual(unprotected, [],
                         'add these provenance destinations to .gitattributes as "-text": '
                         + ', '.join(unprotected))

    def test_working_tree_matches_every_recorded_destination_hash(self):
        """The same assertion verify_provenance.py makes, reported all at once."""
        drifted = []
        for row in manifest()['files']:
            path = ROOT / row['destination']
            self.assertTrue(path.is_file(), f'missing extracted file: {row["destination"]}')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != row['destination_sha256']:
                drifted.append(row['destination'])
        self.assertEqual(drifted, [],
                         'these files changed without a provenance revision: ' + ', '.join(drifted))

    def test_catalogue_mirrors_normalize_like_their_pinned_original(self):
        """A mirror left on text=auto diverges from its pinned source by line endings alone."""
        if shutil.which('git') is None:
            self.skipTest('git is required to resolve .gitattributes')
        mirrors = ['Sim/fantasy_world_generator/world_asset_requirements.json',
                   'docs/catalogue/world-assets/manifest.json']
        canonical = (ROOT / 'Contracts/catalogues/world-assets.json').read_bytes()
        result = subprocess.run(['git', 'check-attr', 'text', '--', *mirrors],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        for line in result.stdout.splitlines():
            mirror, _, value = line.rpartition(': text: ')
            self.assertEqual(value.strip(), 'unset',
                             f'{mirror} mirrors a provenance-pinned file and must be "-text"')
        for mirror in mirrors:
            self.assertEqual((ROOT / mirror).read_bytes(), canonical,
                             f'{mirror} is not byte-identical to the canonical catalogue')

    def test_exact_extractions_still_match_their_source_hash(self):
        mismatched = [row['destination'] for row in manifest()['files']
                      if row['status'] == 'exact' and row['destination_sha256'] != row['source_sha256']]
        self.assertEqual(mismatched, [],
                         'an "exact" row must equal its source; mark it "modified" with a revision '
                         'instead: ' + ', '.join(mismatched))


if __name__ == '__main__':
    unittest.main()
