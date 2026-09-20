"""The documentation gate must fail for the right reason, not merely pass.

A structural checker that reports green because it looked at nothing is worse than no
checker: it reads as coverage. Every test here injects one defect and asserts both the
exit code and the error code, then restores the tree.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / 'tools' / 'docs_check.py'
CONFORMANCE = ROOT / 'docs' / 'conformance'


def run_check():
    result = subprocess.run([sys.executable, str(CHECK)], cwd=str(ROOT),
                            capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


class Restores(unittest.TestCase):
    """Injects a defect, asserts it is caught, and puts the tree back."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.saved = {}
        self.created = []

    def tearDown(self):
        for path, data in self.saved.items():
            path.write_bytes(data)
        for path in self.created:
            if path.exists():
                path.unlink()
        shutil.rmtree(self.temp, ignore_errors=True)

    def save(self, path):
        self.saved[path] = path.read_bytes()

    def write_new(self, path, text):
        self.created.append(path)
        path.write_text(text, encoding='utf-8')

    def assertCaught(self, code):
        status, output = run_check()
        self.assertEqual(status, 1, 'expected a failure, got:\n' + output)
        self.assertIn(code, output, 'expected %s in:\n%s' % (code, output))


class DocsCheckBaseline(unittest.TestCase):
    def test_the_tree_passes(self):
        """If this fails, every other test in this file proves nothing."""
        status, output = run_check()
        self.assertEqual(status, 0, output)
        self.assertIn('Documentation checks passed', output)


class DocsCheckCatchesDefects(Restores):
    def test_an_unclaimed_module_fails(self):
        self.write_new(ROOT / 'Sim' / 'icarus_sim' / 'zz_probe_module.py',
                       '"""Probe."""\n')
        self.assertCaught('COVERAGE')

    def test_a_stale_version_marker_fails(self):
        self.write_new(CONFORMANCE / '_probe.md',
                       '---\nconformance: 1\nrecord: _probe\n---\n\n'
                       '# Probe\n\n<!-- conformance:version magic=3 -->\n')
        self.assertCaught('VERSION')

    def test_a_marker_for_an_unknown_binding_fails(self):
        self.write_new(CONFORMANCE / '_probe.md',
                       '---\nconformance: 1\nrecord: _probe\n---\n\n'
                       '# Probe\n\n<!-- conformance:version nope=1 -->\n')
        self.assertCaught('VERSION')

    def test_a_broken_link_fails(self):
        self.write_new(CONFORMANCE / '_probe.md',
                       '---\nconformance: 1\nrecord: _probe\n---\n\n'
                       '# Probe\n\n[gone](./absent.md)\n')
        self.assertCaught('LINK')

    def test_a_python3_invocation_fails(self):
        self.write_new(CONFORMANCE / '_probe.md',
                       '---\nconformance: 1\nrecord: _probe\n---\n\n'
                       '# Probe\n\nRun python3 tools/validate_repo.py.\n')
        self.assertCaught('COMMAND')

    def test_claiming_a_module_that_does_not_exist_fails(self):
        self.write_new(CONFORMANCE / '_probe.md',
                       '---\nconformance: 1\nrecord: _probe\nmodules:\n'
                       '  - Sim/icarus_sim/absent.py\n---\n\n# Probe\n')
        self.assertCaught('CLAIM')

    def test_two_records_claiming_one_module_fails(self):
        for stem in ('_probe', '_probe2'):
            self.write_new(CONFORMANCE / (stem + '.md'),
                           '---\nconformance: 1\nrecord: %s\nmodules:\n'
                           '  - Sim/icarus_sim/terrain_water.py\n---\n\n# Probe\n' % stem)
        self.assertCaught('COVERAGE-DOUBLE')

    def test_an_allowlist_entry_for_a_claimed_module_fails(self):
        self.write_new(CONFORMANCE / '_probe.md',
                       '---\nconformance: 1\nrecord: _probe\nmodules:\n'
                       '  - Sim/icarus_sim/terrain_water.py\n---\n\n# Probe\n')
        self.assertCaught('COVERAGE-STALE')

    def test_a_cross_file_version_shadow_fails(self):
        """terrain_magic writes magic=1; terrain_leyline_history overwrites it with 4.

        The shadow is in a different file from the declared site, so a scan confined to
        the binding's own file would never see it.
        """
        path = CONFORMANCE / 'version-bindings.json'
        self.save(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        for binding in data['bindings']:
            binding.pop('shadowed_by', None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n',
                        encoding='utf-8')
        self.assertCaught('VERSION-AMBIGUOUS')

    def test_a_dangling_provenance_decision_fails(self):
        path = ROOT / 'provenance' / 'extraction-manifest.json'
        self.save(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        for entry in data['files']:
            if entry.get('revisions'):
                entry['revisions'][0]['decision'] = 'docs/decisions/999-absent.md'
                break
        path.write_bytes(
            (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
        self.assertCaught('PROV-DECISION')

    def test_an_undecodable_document_fails(self):
        path = CONFORMANCE / '_probe.md'
        self.created.append(path)
        path.write_bytes(b'---\nconformance: 1\nrecord: _probe\n---\n\n# Probe \x96 dash\n')
        self.assertCaught('ENCODING')

    def test_a_duplicate_decision_number_fails(self):
        existing = sorted((ROOT / 'docs' / 'decisions').glob('0*.md'))[0]
        clone = existing.parent / (existing.name.split('-')[0] + '-probe-duplicate.md')
        self.write_new(clone, '# Probe duplicate\n')
        self.assertCaught('NUMBERING')


if __name__ == '__main__':
    unittest.main()
