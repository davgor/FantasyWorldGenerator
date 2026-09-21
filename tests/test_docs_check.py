"""The documentation gate must fail for the right reason, not merely pass.

A structural checker that reports green because it looked at nothing is worse than no
checker: it reads as coverage. Every test here injects one defect and asserts the error
code, then restores the tree.

**Where a negative fixture lives matters.** Four other sessions run this gate while this
suite runs, and a deliberately broken record parked in `docs/conformance/` is
indistinguishable from a real one for as long as it is there: it has already been reported
twice as somebody else's failure. Tests that exercise a record-level check therefore build
their probe under `.conformance-probe/`, a dot-directory `all_markdown` skips, and call the
check in process. Only the checks whose subject is the real tree -- the glob lists, the
whole-run report -- touch the tree, and those take milliseconds rather than a subprocess.
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

sys.path.insert(0, str(ROOT / 'tools'))
import docs_check  # noqa: E402
sys.path.pop(0)


def run_check():
    result = subprocess.run([sys.executable, str(CHECK)], cwd=str(ROOT),
                            capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


CREATES = (
    ROOT / '.conformance-probe',
    ROOT / 'board' / '_probe_folder',
    CONFORMANCE / '_probe.md',
    CONFORMANCE / '_probe2.md',
    ROOT / 'Sim' / 'icarus_sim' / 'zz_probe_module.py',
)


def setUpModule():
    """Sweep anything a previous run died holding.

    `tearDown` does not fire when the process is killed, and a fixture stranded in
    `docs/conformance/` is indistinguishable from a real broken record: one sat there for
    twenty minutes tonight failing the gate in two different ways, and was reported twice
    as somebody else's defect. Everything this suite can create is named here and removed
    before the first test, so an interrupted run costs the next run and nobody else.
    """
    for path in CREATES:
        shutil.rmtree(path, ignore_errors=True) if path.is_dir() else None
        if path.is_file():
            path.unlink()
    for path in (ROOT / 'docs' / 'decisions').glob('*-probe-duplicate.md'):
        path.unlink()


class Restores(unittest.TestCase):
    """Creates a defect, asserts it is caught, and removes what it created.

    **It only ever creates files; it never rewrites a committed one.** Restoring a shared
    file from bytes captured a second earlier silently reverts whatever another session
    wrote in between, and five sessions run this suite concurrently. The checks whose
    fixture used to be a real committed file are in `DocsCheckNeverRewritesAContendedFile`
    and build their own instead. There is deliberately no `save()` helper here to reach
    for.
    """

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.created = []

    def tearDown(self):
        for path in self.created:
            if path.exists():
                path.unlink()
        shutil.rmtree(self.temp, ignore_errors=True)

    def write_new(self, path, text):
        self.created.append(path)
        path.write_text(text, encoding='utf-8')

    def assertCaught(self, code, fragment=None):
        """A specific error code, and optionally the sentence it must carry.

        The exit status is deliberately NOT the load-bearing assertion. The tree can
        already be red for an unrelated reason, and a status-only check would then pass
        before the check under test exists at all -- an unexpected green is a test
        defect, not a finished feature.
        """
        status, output = run_check()
        self.assertIn(code, output, 'expected %s in:\n%s' % (code, output))
        if fragment is not None:
            self.assertIn(fragment, output, 'expected %r in:\n%s' % (fragment, output))
        self.assertEqual(status, 1, 'expected a failure, got:\n' + output)


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

    def test_a_duplicate_decision_number_fails(self):
        existing = sorted((ROOT / 'docs' / 'decisions').glob('0*.md'))[0]
        clone = existing.parent / (existing.name.split('-')[0] + '-probe-duplicate.md')
        self.write_new(clone, '# Probe duplicate\n')
        self.assertCaught('NUMBERING')


def record(**fields):
    """A conformance record with the given front matter, rendered the way records are."""
    lines = ['---', 'conformance: 1']
    for key, value in fields.items():
        if isinstance(value, str):
            lines.append('%s: %s' % (key, value))
        else:
            lines.append('%s:' % key)
            lines.extend(value)
    lines += ['---', '', '# Probe', '']
    return '\n'.join(lines)


class InProcess(unittest.TestCase):
    """Builds its fixtures where the gate does not walk, and calls the check directly.

    `docs_check.CONFORMANCE` is redirected at a dot-directory under the repository root:
    inside the root so `rel()` still resolves, hidden so a concurrent `docs_check.py` run
    in another session cannot see it even mid-test. Nothing is written into
    `docs/conformance/` and no shared file is rewritten and restored.
    """

    PROBE = ROOT / '.conformance-probe'

    def setUp(self):
        shutil.rmtree(self.PROBE, ignore_errors=True)
        self.PROBE.mkdir(parents=True, exist_ok=True)
        self.saved_conformance = docs_check.CONFORMANCE
        docs_check.CONFORMANCE = self.PROBE
        docs_check._FRONT_MATTER.clear()

    def tearDown(self):
        docs_check.CONFORMANCE = self.saved_conformance
        docs_check._FRONT_MATTER.clear()
        shutil.rmtree(self.PROBE, ignore_errors=True)

    def probe_doc(self, text, name='_probe.md'):
        path = self.PROBE / name
        path.write_text(text, encoding='utf-8')
        return path

    def mirror_conformance(self):
        """Copy the real conformance folder into the probe, so a fixture added beside it
        behaves exactly as it would in place -- against the real ledger and the real
        records -- without a byte being written to the folder the gate reads."""
        for src in self.saved_conformance.iterdir():
            if src.is_file():
                shutil.copy2(src, self.PROBE / src.name)

    def claims(self, text, versions=None):
        """Findings from check_claims over one probe record."""
        self.probe_doc(text)
        findings = []
        docs_check.check_claims(findings, versions if versions is not None else {'nomads': 1})
        return findings

    def assertFinding(self, findings, code, fragment, severity='error'):
        """Matched against the finding as the report prints it, `where` included."""
        hits = [f for f in findings if f.code == code and fragment in str(f)]
        self.assertTrue(hits, 'expected a %s finding containing %r, got: %s'
                        % (code, fragment, [str(f) for f in findings]))
        self.assertEqual(hits[0].severity, severity)
        return hits[0]


class DocsCheckReadsTheRestOfTheRecord(InProcess):
    """The eight front-matter keys that were parsed for syntax and never read again.

    A conformance record is the only artifact in the repository that makes a
    present-tense capability claim to a consumer. Before these checks existed, the only
    machine-enforced property of one was which modules it claimed: `proof:` could name a
    file that was never written, `emits[].schema` a schema that was deleted, `versions:`
    any integer at all, and `tier:` any word.
    """

    def test_a_proof_path_that_does_not_exist_fails(self):
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            proof=['  - path: Sim/tests/test_absent_probe.py',
                   '    establishes: nothing, because it does not exist']))
        self.assertFinding(findings, 'CLAIM-PROOF', 'Sim/tests/test_absent_probe.py')

    def test_a_proof_path_no_suite_runs_fails(self):
        """Existence is not exercise. A record may only cite a file the suite discovers."""
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            proof=['  - path: tools/docs_check.py',
                   '    establishes: nothing; no unittest discovery pattern reaches it']))
        self.assertFinding(findings, 'CLAIM-PROOF', 'no test suite discovers')

    def test_a_proof_entry_with_no_establishes_fails(self):
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            proof=['  - path: tests/test_docs_check.py']))
        self.assertFinding(findings, 'CLAIM-PROOF', 'establishes')

    def test_an_emitted_schema_that_does_not_exist_fails(self):
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            emits=['  - path: probe', '    schema: Contracts/schemas/absent.schema.json']))
        self.assertFinding(findings, 'CLAIM-EMITS', 'Contracts/schemas/absent.schema.json')

    def test_a_record_asserting_the_wrong_version_fails(self):
        """`versions:` looked enforced and was not: version checking ran only off the
        markers in prose, so a record's own list could assert any integer it liked."""
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            versions=['  - id: nomads', '    assert: 9']))
        self.assertFinding(findings, 'CLAIM-VERSION', 'asserts nomads=9')

    def test_a_record_asserting_an_unknown_binding_fails(self):
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            versions=['  - id: no-such-binding', '    assert: 1']))
        self.assertFinding(findings, 'CLAIM-VERSION', 'no-such-binding')

    def test_a_tier_outside_the_vocabulary_fails(self):
        findings = self.claims(record(
            record='_probe', tier='BATTLE-TESTED', summary='Probe.'))
        self.assertFinding(findings, 'CLAIM-TIER', 'BATTLE-TESTED')

    def test_a_record_whose_name_is_not_its_filename_fails(self):
        findings = self.claims(record(
            record='something-else', tier='DECLARED', summary='Probe.'))
        self.assertFinding(findings, 'CLAIM-RECORD', 'something-else')

    def test_a_record_with_no_summary_fails(self):
        findings = self.claims(record(record='_probe', tier='DECLARED'))
        self.assertFinding(findings, 'CLAIM-SUMMARY', 'makes none is a heading')

    def test_a_dangling_ticket_warns_rather_than_failing(self):
        """Tickets move between backlog/, in-progress/, done/ and retired/ constantly.
        A hard failure would punish the move, so this one is soft on purpose."""
        findings = self.claims(record(
            record='_probe', tier='DECLARED', summary='Probe.',
            tickets=['  - board/backlog/ABSENT-PROBE-CARD.md']))
        self.assertFinding(findings, 'CLAIM-REF', 'ABSENT-PROBE-CARD.md',
                           severity=docs_check.WARN)

    def test_a_record_that_states_everything_correctly_is_silent(self):
        """The control. Every check above has to be capable of passing, or a record that
        fires all of them proves only that the parser crashes."""
        findings = self.claims(record(
            record='_probe', tier='EXERCISED', summary='Probe.',
            modules='[]',
            emits=['  - path: probe', '    schema: none'],
            versions=['  - id: nomads', '    assert: 1'],
            proof=['  - path: tests/test_docs_check.py',
                   '    establishes: that each claim check fires and that this one does not'],
            tickets='[]', decisions='[]'))
        self.assertEqual([str(f) for f in findings], [])


class DocsCheckKnowsWhatItDidNotRead(InProcess):
    """A checker that cannot see a folder cannot fail on it.

    `board/retired/` was created on 2026-09-21 and added to neither glob list. Four cards
    moved into it, six sibling-relative links inside them died, and the run stayed green
    because the folder was not being scanned at all. The only visible symptom was the
    document count falling from 208 to 204, which was rationalised rather than
    investigated, and it was caught by a separate repo-wide link sweep rather than here.
    """

    def test_a_document_no_glob_examines_fails(self):
        """The one check whose subject is the real tree, so the probe has to be in it.

        In process and for milliseconds rather than through a two-second subprocess: this
        is the only fixture of this suite's that another session could see, and it is a
        card-shaped file under board/ rather than a broken conformance record.
        """
        folder = ROOT / 'board' / '_probe_folder'
        folder.mkdir(parents=True, exist_ok=True)
        try:
            (folder / 'card.md').write_text('# Probe card\n', encoding='utf-8')
            findings = []
            docs_check.check_document_globs(findings)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        self.assertFinding(findings, 'GLOB-UNCLAIMED', 'no glob in docs_check')
        self.assertTrue(any(f.where == 'board/_probe_folder/card.md' for f in findings),
                        'the finding must name the document: %s'
                        % [str(f) for f in findings])

    def test_a_probe_in_a_dot_directory_is_invisible_to_the_gate(self):
        """The property the rest of this suite depends on.

        `setUp` has already written nothing here; this asserts the rule that makes the
        redirect safe -- a document under a dot-directory is not in the gate's universe,
        so a probe record cannot be mistaken for a real one by a concurrent run.
        """
        (self.PROBE / 'visible_if_this_breaks.md').write_text('# Probe\n', encoding='utf-8')
        names = [docs_check.rel(p) for p in docs_check.all_markdown()]
        self.assertNotIn('.conformance-probe/visible_if_this_breaks.md', names)
        findings = []
        docs_check.check_document_globs(findings)
        self.assertEqual([str(f) for f in findings if f.severity == 'error'], [])

    def test_the_run_reports_what_it_did_not_examine(self):
        _, output = run_check()
        self.assertIn('not examined', output,
                      'a gate that does not say what it skipped reads as coverage:\n' + output)

    def test_a_glob_matching_nothing_warns(self):
        """The other direction: a folder that moved leaves a glob pointing at nothing,
        and the documents it used to cover become invisible without any finding.
        """
        saved = docs_check.FROZEN_GLOBS
        docs_check.FROZEN_GLOBS = saved + ('board/moved-away/*.md',)
        try:
            findings = []
            docs_check.check_document_globs(findings)
        finally:
            docs_check.FROZEN_GLOBS = saved
        self.assertFinding(findings, 'GLOB-EMPTY', 'board/moved-away/*.md',
                           severity=docs_check.WARN)


class DocsCheckCatchesDefectsInADocument(InProcess):
    """The document-level checks, over a probe document rather than a probe record.

    These used to write `docs/conformance/_probe.md` and delete it afterwards. It is the
    filename the gate reported twice tonight as a real broken record, because an
    interrupted run left one behind. Nothing here writes into `docs/conformance/`.
    """

    def test_a_stale_version_marker_fails(self):
        self.mirror_conformance()
        path = self.probe_doc('# Probe\n\n<!-- conformance:version magic=3 -->\n')
        findings = []
        docs_check.check_versions(findings, [path])
        self.assertFinding(findings, 'VERSION', 'marker says magic=3 but the code emits 4')

    def test_a_marker_for_an_unknown_binding_fails(self):
        self.mirror_conformance()
        path = self.probe_doc('# Probe\n\n<!-- conformance:version nope=1 -->\n')
        findings = []
        docs_check.check_versions(findings, [path])
        self.assertFinding(findings, 'VERSION', "unknown binding 'nope'")

    def test_a_marker_shown_as_an_example_is_not_a_claim(self):
        """The control. `_template.md` documents the syntax in a fence and must not be
        read as asserting a version, or the gate cannot describe itself."""
        self.mirror_conformance()
        path = self.probe_doc('# Probe\n\n```\n<!-- conformance:version nope=1 -->\n```\n'
                              'and inline `<!-- conformance:version nope=1 -->`.\n')
        findings = []
        docs_check.check_versions(findings, [path])
        self.assertEqual([str(f) for f in findings], [])

    def test_a_broken_link_fails(self):
        path = self.probe_doc('# Probe\n\n[gone](./absent.md)\n')
        findings = []
        docs_check.check_documents(findings, [path])
        self.assertFinding(findings, 'LINK', 'link target does not exist: ./absent.md')

    def test_a_python3_invocation_fails(self):
        path = self.probe_doc('# Probe\n\nRun python3 tools/validate_repo.py.\n')
        findings = []
        docs_check.check_documents(findings, [path])
        self.assertFinding(findings, 'COMMAND', 'Microsoft Store alias stub')


class DocsCheckCatchesDefectsInTheCoverageLedger(InProcess):
    """The coverage checks, against a mirror of the real folder.

    The ledger and every real record are copied into the probe directory, so the probe
    record sits among them exactly as it would in place, and `python_modules()` still
    walks the real `Sim/`. What is not real is the folder being written to.
    """

    def claim(self, stem, module):
        self.probe_doc('---\nconformance: 1\nrecord: %s\ntier: DECLARED\n'
                       'summary: Probe.\nmodules:\n  - %s\n---\n\n# Probe\n'
                       % (stem, module), stem + '.md')

    def coverage(self):
        findings = []
        docs_check.check_coverage(findings)
        return findings

    def test_claiming_a_module_that_does_not_exist_fails(self):
        self.mirror_conformance()
        self.claim('_probe', 'Sim/icarus_sim/absent.py')
        self.assertFinding(self.coverage(), 'CLAIM',
                           'claimed module does not exist: Sim/icarus_sim/absent.py')

    def test_two_records_claiming_one_module_fails(self):
        self.mirror_conformance()
        self.claim('_probe', 'Sim/icarus_sim/terrain_water.py')
        self.claim('_probe2', 'Sim/icarus_sim/terrain_water.py')
        self.assertFinding(self.coverage(), 'COVERAGE-DOUBLE',
                           'exactly one record owns a module')

    def test_an_allowlist_entry_for_a_claimed_module_fails(self):
        self.mirror_conformance()
        self.claim('_probe', 'Sim/icarus_sim/terrain_water.py')
        self.assertFinding(self.coverage(), 'COVERAGE-STALE',
                           'Sim/icarus_sim/terrain_water.py')

    def test_the_mirrored_ledger_is_clean_without_a_probe(self):
        """The control, and the one that makes the three above mean something: the mirror
        reproduces a green ledger, so each finding is caused by the probe record and not
        by the mirroring."""
        self.mirror_conformance()
        self.assertEqual([str(f) for f in self.coverage()], [])


class DocsCheckNeverRewritesAContendedFile(InProcess):
    """Three checks whose fixtures used to be the real committed files.

    Each of these rewrote a shared file and restored it in `tearDown` from bytes captured
    at `setUp`. That is a read-then-write across an arbitrarily long window: any session
    writing the same file inside it has its edit silently reverted, with no error and no
    diff to notice. `version-bindings.json` and `provenance/extraction-manifest.json` are
    the two most contended files in the repository and the manifest has already been
    corrupted once by two sessions racing on it. Filed as M4 in
    `docs/reviews/233182e-code-red-team.md`, and its root-cause reading is right: the gap
    was a missing seam, not a careless test.

    The fixtures are now the probe directory's own, so an interrupted run strands nothing
    the gate can see, and no committed file is written at all.
    """

    def test_a_cross_file_version_shadow_fails(self):
        """terrain_magic writes magic=1; terrain_leyline_history overwrites it with 4.

        The shadow is in a different file from the declared site, so a scan confined to
        the binding's own file would never see it. The real modules are still the subject
        -- `scan_emitters` walks the real `Sim/` — only the binding is the probe's.
        """
        (self.PROBE / 'version-bindings.json').write_text(json.dumps({
            'schema': 1,
            'bindings': [{
                'id': 'magic', 'label': 'magic schema',
                'code': {'kind': 'emitted-key',
                         'file': 'Sim/icarus_sim/terrain_leyline_history.py',
                         'block': 'magic', 'key': 'version'},
            }]}), encoding='utf-8')
        findings = []
        docs_check.check_versions(findings, [])
        self.assertFinding(findings, 'VERSION-AMBIGUOUS', 'terrain_magic.py')

    def test_a_dangling_provenance_decision_fails(self):
        manifest = self.PROBE / 'extraction-manifest.json'
        manifest.write_text(json.dumps({
            'schema_version': 1,
            'files': [{'destination': 'Sim/icarus_sim/terrain_water.py',
                       'revisions': [{'decision': 'docs/decisions/999-absent.md'}]}],
        }), encoding='utf-8')
        findings = []
        docs_check.check_provenance_decisions(findings, manifest)
        self.assertFinding(findings, 'PROV-DECISION', 'docs/decisions/999-absent.md')

    def test_the_real_manifest_cites_only_decisions_that_exist(self):
        """The control, and the reason the check is worth having: run against the real
        manifest, read-only, so a green here is a statement about the tree rather than
        about the fixture."""
        findings = []
        docs_check.check_provenance_decisions(findings)
        self.assertEqual([str(f) for f in findings], [])

    def test_an_undecodable_document_fails(self):
        path = self.PROBE / 'undecodable.md'
        path.write_bytes(b'---\nconformance: 1\nrecord: probe\n---\n\n# Probe \x96 dash\n')
        findings = []
        docs_check.check_documents(findings, [path])
        self.assertFinding(findings, 'ENCODING', 'not valid UTF-8')

    def test_a_document_that_vanishes_mid_run_warns_instead_of_crashing(self):
        """Four other sessions move cards between board folders while this gate runs, and
        a file listed a moment ago can be gone by the time it is read. That killed a run
        tonight with a FileNotFoundError traceback, which reports nothing at all."""
        path = self.PROBE / 'gone.md'
        path.write_text('# Gone\n', encoding='utf-8')
        path.unlink()
        findings = []
        docs_check.check_documents(findings, [path])
        self.assertFinding(findings, 'VANISHED', 'disappeared between being listed',
                           severity=docs_check.WARN)


class DocsCheckBindsAPublishedBoundToItsGuard(InProcess):
    """PRODUCT-PARAMETER-PROVENANCE: a bound and its enforcement are two statements of
    one fact, four hundred lines apart in one module. They agreed because somebody
    checked, which is the footing the Python/native grid pair was on before it drifted.

    Entirely inside the probe directory: the bindings file the checker reads is the probe's
    own, and the module both sides resolve against is a probe module. Appending a binding
    to the real `version-bindings.json` and restoring it would lose whatever another
    session wrote to it in between, and that file is shared on purpose.
    """

    SOURCE = ('"""Probe: a bounds table and a guard that restate one number."""\n'
              'def registry():\n'
              "    bounds={'size':(3,1025)}\n"
              '    return bounds\n'
              'def guard(raw):\n'
              "    if raw['size']>%d:raise over_capacity('size',raw['size'],%d,'grid')\n")

    def bindings(self, guard_value):
        (self.PROBE / 'zz_probe_bounds.py').write_text(
            self.SOURCE % (guard_value, guard_value), encoding='utf-8')
        module = '.conformance-probe/zz_probe_bounds.py'
        (self.PROBE / 'version-bindings.json').write_text(json.dumps({
            'schema': 1,
            'bindings': [{
                'id': 'zz-probe-bound',
                'label': 'probe bound',
                'code': {'kind': 'tuple-bound', 'file': module,
                         'name': 'bounds', 'key': 'size', 'index': 1},
                'mirror': {'kind': 'call-arg', 'file': module,
                           'call': 'over_capacity', 'arg': 2, 'select': {'0': 'size'}},
            }]}), encoding='utf-8')
        findings = []
        actual = docs_check.check_versions(findings, [])
        return findings, actual

    def test_a_bounds_table_that_disagrees_with_its_guard_fails(self):
        findings, _ = self.bindings(2049)
        self.assertFinding(findings, 'VERSION-MIRROR', 'zz-probe-bound')

    def test_a_bounds_table_that_agrees_with_its_guard_is_silent(self):
        """The control. A mirror that cannot pass reports a disagreement it invented."""
        findings, actual = self.bindings(1025)
        self.assertEqual([str(f) for f in findings], [])
        self.assertEqual(actual['zz-probe-bound'], 1025)

    def test_the_live_grid_ceiling_resolves_the_same_from_both_statements(self):
        """The real binding, against the real module: the registry's bounds table and the
        guard four hundred lines below it both resolve 1025 today."""
        data = json.loads(
            (CONFORMANCE / 'version-bindings.json').read_text(encoding='utf-8'))
        binding = next(b for b in data['bindings'] if b['id'] == 'grid-size-max')
        findings = []
        table, _ = docs_check.resolve_code(binding['code'], findings, 'test')
        guard, _ = docs_check.resolve_code(binding['mirror'], findings, 'test')
        self.assertEqual([str(f) for f in findings], [])
        self.assertIsNotNone(table, 'the bounds table resolved no integer')
        self.assertEqual(table, guard,
                         'the published grid bound and the guard that enforces it '
                         'disagree: table %s, guard %s' % (table, guard))


if __name__ == '__main__':
    unittest.main()
