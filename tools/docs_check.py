"""Read-only documentation routing and structural checks; no semantic approval.

What a green run establishes: every document is readable, its links resolve, every
Python module is claimed by exactly one conformance record, and every documented
version integer matches the code that emits it.

What it does not establish: that any record is true. A record can pass every check
here and describe behavior the product no longer has. This is a structural gate, not
documentation review, and it must not be cited as one.

Every correspondence is checked in both directions. A one-directional check reads as
coverage while missing the other half: verifying each index entry resolves says nothing
about documents the index omits, and verifying a block validates against its schema says
nothing about fields the schema never declared.

Standard library only, Python 3.9 compatible. The package declares no dependencies and
this gate must not add the first one.
"""
import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFORMANCE = ROOT / 'docs' / 'conformance'

# Documents that must satisfy the active checks.
ACTIVE_GLOBS = (
    'README.md', 'AGENTS.md', 'PLAN.md',
    'docs/*.md', 'docs/conformance/*.md', 'docs/decisions/*.md',
    'Contracts/*.md', 'Core/README.md', 'Sim/README.md', 'provenance/README.md',
    'board/README.md', 'board/backlog/*.md', 'board/in-progress/*.md',
    # Two folders that no glob named until 2026-09-21, and so were read by nothing: the
    # card template every new card is copied from, and the plugin README that links five
    # documents across two folders with `../../` paths -- the exact shape that dies when
    # a card is moved.
    'board/templates/*.md', 'Unreal/FantasyWorldGenerator/README.md',
    # Retired cards are not worked, but they are still linked from live documents and
    # still link back into them, and a card that changes folder takes its sibling links
    # with it. Freezing them instead would suppress the link check, which is the one
    # check that catches exactly that move -- it missed six dead links on 2026-09-21.
    'board/retired/*.md',
)
# Historical or imported evidence: read but never repaired. Frozen must be a subset of
# what is provenance-pinned or of board/done, so nothing current can hide in here.
FROZEN_GLOBS = (
    'docs/terrain-math-lab.md',
    'docs/catalogue/world-assets/*.md',
    'board/done/*.md',
    'provenance/source-reviews/*.md',
)
# Markdown this gate deliberately does not read, each with the reason. Every document in
# the repository must match one of the three lists, so a new folder fails loudly instead
# of being silently skipped, and every run prints what this list cost.
UNCHECKED_GLOBS = {
    'Artifacts/*.md': 'generated profile reports, rewritten wholesale by '
                      'tools/stage_profile.py; no prose in them is hand-authored',
}

# The closed vocabulary for a record's `tier`. These are the four tiers declared in
# docs/conformance/README.md's evidence table, restated here because the table was the
# only statement of them and nothing read it: `tier` is the word a reader is most likely
# to trust and it was self-assigned. Keep the two in step -- a fifth tier invented in a
# record now fails here, and a fifth tier added to the table has to be added here too.
TIERS = {
    'DECLARED': 'the symbol exists with this signature; its own comments say it does X',
    'REACHABLE': 'a caller exists and a named build compiles and links it',
    'EXERCISED': 'a named test runs this code and asserts on its output',
    'PARITY': 'output matches a reference field by field at a stated seed and tolerance',
}

# Where a proof file has to live to be run at all. These mirror the three unittest
# discoveries in tools/validate_repo.py (`sim-tests`, `repo-tests`, `consumers`); a
# record may not cite a file no suite reaches.
PROOF_PATTERNS = ('Sim/tests/test_*.py', 'tests/test_*.py', 'tests/consumer_*.py')


# Values a record may write where a path is expected, to say plainly that there is none.
# Anything else in those fields is read as a path and must resolve.
def disclaimed(value):
    return not value or value.lower() == 'none' or value.startswith('(')

FENCE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE = re.compile(r'`[^`]*`')
MD_LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
VERSION_MARKER = re.compile(r'<!--\s*conformance:version\s+([A-Za-z0-9_.-]+)=(\d+)\s*-->')
CXX_CONST = r'^\s*(?:constexpr|const)\s+[A-Za-z_:<>\s\d]*\b{name}\s*=\s*(\d+)\s*;'
DECISION_NUM = re.compile(r'^(\d+)-')

HARD = 'error'
WARN = 'warning'


class Finding:
    def __init__(self, severity, code, where, message):
        self.severity = severity
        self.code = code
        self.where = where
        self.message = message

    def __str__(self):
        return '%s: %s %s' % (self.where, self.code, self.message)


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def matches(path, globs):
    p = path if isinstance(path, str) else rel(path)
    return any(fnmatch.fnmatchcase(p, g) for g in globs)


def all_markdown():
    """Every document in the tree. Hidden directories are not documentation.

    `.git`, `.venv` and `node_modules` were named one at a time; the rule behind them is
    that a dot-directory holds machinery rather than prose. Stating it as the rule also
    gives this repository's negative tests somewhere to build a deliberately broken
    record: a probe record parked in `docs/conformance/` is indistinguishable from a real
    one for as long as it exists, and another session standing at a closeout run sees it
    as a failure that is theirs to chase.
    """
    out = []
    for p in sorted(ROOT.rglob('*.md')):
        parts = p.relative_to(ROOT).parts
        if 'node_modules' in parts or any(x.startswith('.') for x in parts):
            continue
        out.append(p)
    return out


def read_text(path, findings):
    """Read a document, reporting an unreadable one rather than raising.

    A document can also disappear between being listed and being read, because four other
    sessions move cards between board folders while this runs. That is not a defect in the
    tree and it is not the reader's to fail on, but a gate that dies with a traceback
    halfway through has reported nothing at all -- so it is a warning and the run
    continues.
    """
    try:
        return path.read_bytes().decode('utf-8')
    except UnicodeDecodeError as exc:
        findings.append(Finding(
            HARD, 'ENCODING', rel(path),
            'is not valid UTF-8 (%s at byte %d); a reader that assumes UTF-8 crashes on it'
            % (exc.reason, exc.start)))
        return None
    except OSError:
        findings.append(Finding(
            WARN, 'VANISHED', rel(path),
            'disappeared between being listed and being read; another session most '
            'likely moved it mid-run, and nothing in this run examined it'))
        return None


def strip_code(text):
    """Blank out fenced blocks and inline code so examples are not read as claims."""
    lines = text.splitlines()
    out, fence = [], None
    for line in lines:
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            out.append('')
            continue
        if fence is not None:
            out.append('')
            if line.strip().startswith(fence):
                fence = None
            continue
        out.append(INLINE_CODE.sub('``', line))
    return out


def slug(heading):
    s = heading.strip().lstrip('#').strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)
    return re.sub(r'[\s_]+', '-', s).strip('-')


def headings(text):
    return {slug(l) for l in text.splitlines() if l.startswith('#')}


# --------------------------------------------------------------------------- documents

def check_documents(findings, docs):
    """ENCODING, LINK and COMMAND over the active document set."""
    texts = {}
    for p in docs:
        t = read_text(p, findings)
        if t is not None:
            texts[p] = t

    for p, text in texts.items():
        name = rel(p)
        if matches(name, FROZEN_GLOBS):
            continue
        lines = strip_code(text)
        for i, line in enumerate(lines, 1):
            for target in MD_LINK.findall(line):
                if re.match(r'^(https?:|mailto:|#)', target):
                    continue
                frag = None
                if '#' in target:
                    target, frag = target.split('#', 1)
                if not target:
                    continue
                dest = (p.parent / target).resolve()
                if not dest.exists():
                    findings.append(Finding(
                        HARD, 'LINK', '%s:%d' % (name, i),
                        'link target does not exist: %s' % target))
                    continue
                if frag and dest.suffix == '.md':
                    body = texts.get(dest)
                    if body is None and dest.exists():
                        body = read_text(dest, findings)
                    if body and slug(frag) not in headings(body):
                        findings.append(Finding(
                            HARD, 'LINK', '%s:%d' % (name, i),
                            'anchor not found in %s: #%s' % (target, frag)))
            if 'python3' in line:
                findings.append(Finding(
                    HARD, 'COMMAND', '%s:%d' % (name, i),
                    'python3 is a Microsoft Store alias stub on the development machine '
                    'and has never launched; use python'))


CITATION = re.compile(r'`?([A-Za-z0-9_./-]+\.(?:py|cpp|hpp|js|json|html))`?:(\d+)(?:-(\d+))?')
IDENT = re.compile(r'`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`')


def check_citations(findings, docs):
    """A `file.py:NNN` citation should point at a line that still holds what it claims.

    Two directions are cheap and both matter: the line must exist, and when the
    sentence names a backticked identifier that identifier should appear near the line.
    Line numbers drift silently as code moves above them, and a citation that is off by
    forty lines reads as authoritative while sending a reader to unrelated code.

    Warn-only: the identifier heuristic has real false positives, and a check that
    blocks a merge on a judgement call gets switched off.
    """
    cache = {}
    for p in docs:
        name = rel(p)
        if matches(name, FROZEN_GLOBS):
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            # Undecodable is reported by check_documents; gone is another session moving
            # a card mid-run. Neither is this check's to die on.
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for target, start, end in CITATION.findall(line):
                dest = ROOT / target
                if not dest.is_file():
                    continue  # covered by REF; a missing file is not a line problem
                if dest not in cache:
                    try:
                        cache[dest] = dest.read_text(encoding='utf-8', errors='replace').splitlines()
                    except OSError:
                        cache[dest] = []
                body = cache[dest]
                lo, hi = int(start), int(end or start)
                if hi > len(body):
                    findings.append(Finding(
                        WARN, 'CITE', '%s:%d' % (name, i),
                        '%s:%s is past the end of the file (%d lines)'
                        % (target, start, len(body))))
                    continue
                # An identifier that is part of the cited path is not a claim about the
                # line: `story_web/__init__.py:66` never names story_web at line 66.
                idents = [x for x in IDENT.findall(line)
                          if not x.endswith(('.py', '.cpp', '.hpp', '.js', '.json'))
                          and x.split('.')[-1] not in target]
                if not idents:
                    continue
                window = '\n'.join(body[max(0, lo - 4):hi + 3])
                if not any(x.split('.')[-1] in window for x in idents):
                    findings.append(Finding(
                        WARN, 'CITE', '%s:%d' % (name, i),
                        'cites %s:%s but none of %s appears within three lines of it'
                        % (target, start, ', '.join(repr(x) for x in idents[:3]))))


def check_index(findings):
    """Both directions: every index entry resolves, and every document is indexed.

    The second direction is the one that rots. docs/README.md linked two of eleven
    decision records and nothing failed, because a hand-written index has no failure
    signal for what it omits.
    """
    index = ROOT / 'docs' / 'README.md'
    if not index.is_file():
        return
    text = index.read_text(encoding='utf-8')
    linked = set()
    for line in strip_code(text):
        for target in MD_LINK.findall(line):
            if re.match(r'^(https?:|mailto:|#)', target):
                continue
            dest = (index.parent / target.split('#')[0]).resolve()
            if dest.exists():
                linked.add(dest)
    for p in sorted((ROOT / 'docs').glob('*.md')):
        if p.name == 'README.md' or p.resolve() in linked:
            continue
        findings.append(Finding(
            WARN, 'INDEX', 'docs/README.md',
            'does not link %s; a document the map omits is a document nobody finds'
            % rel(p)))
    missing = [rel(p) for p in sorted((ROOT / 'docs' / 'decisions').glob('*.md'))
               if p.name != 'README.md' and p.resolve() not in linked]
    if missing:
        findings.append(Finding(
            WARN, 'INDEX', 'docs/README.md',
            'does not link %d of the decision records: %s'
            % (len(missing), ', '.join(Path(m).name for m in missing))))


def check_numbering(findings):
    seen = {}
    d = ROOT / 'docs' / 'decisions'
    if not d.is_dir():
        return
    for p in sorted(d.glob('*.md')):
        m = DECISION_NUM.match(p.name)
        if not m:
            continue
        seen.setdefault(m.group(1), []).append(p.name)
    for num, names in sorted(seen.items()):
        if len(names) > 1:
            findings.append(Finding(
                HARD, 'NUMBERING', 'docs/decisions',
                'decision number %s is used by %s; a citation of "decision %s" is ambiguous'
                % (num, ' and '.join(names), num)))


def check_provenance_decisions(findings, manifest=None):
    """Every revision row cites a decision document that exists.

    `manifest` exists so a negative test can hand this a fixture of its own. The
    extraction manifest is the most contended file in the repository -- it has already
    been corrupted once by two sessions racing on it -- and a test that rewrites the real
    one and restores it from bytes captured a second earlier silently reverts whatever
    another session wrote inside that window, with no error and no diff to notice.
    """
    p = manifest or (ROOT / 'provenance' / 'extraction-manifest.json')
    if not p.is_file():
        return
    data = json.loads(p.read_text(encoding='utf-8'))
    for entry in data.get('files', []):
        for rev in entry.get('revisions', []):
            target = rev.get('decision')
            if target and not (ROOT / target).exists():
                findings.append(Finding(
                    HARD, 'PROV-DECISION', 'provenance/extraction-manifest.json',
                    'revision for %s cites a decision document that does not exist: %s'
                    % (entry.get('destination'), target)))


# --------------------------------------------------------------------------- coverage

def python_modules():
    out = set()
    for p in (ROOT / 'Sim').rglob('*.py'):
        parts = p.relative_to(ROOT).parts
        if 'tests' in parts or '__pycache__' in parts:
            continue
        out.add(p.relative_to(ROOT).as_posix())
    return out


def core_stems():
    return {('Core/' + p.stem) for p in (ROOT / 'Core').iterdir()
            if p.is_file() and p.suffix in ('.cpp', '.hpp')}


def records():
    """Every conformance record and its parsed front matter."""
    out = {}
    if not CONFORMANCE.is_dir():
        return out
    for p in sorted(CONFORMANCE.glob('*.md')):
        if p.name in ('README.md', 'INDEX.md', 'COVERAGE.md', 'VERSIONS.md', '_template.md'):
            continue
        out[rel(p)] = p
    return out


_FRONT_MATTER = {}


def front_matter(path, findings):
    """A deliberately small key: value, - item and nested - key: value subset. No PyYAML.

    The nested form is the one that matters and it used to be dropped on the floor. A
    continuation line under a list item -- the `schema:` under `- path:`, the `assert:`
    under `- id:`, the `establishes:` under `- path:` -- is indented and does not begin
    with `- `, so the old parser skipped it silently. Five of the nine keys could not be
    read at all, which is a harder version of not reading them.

    An item whose body is `key: value` becomes a dict and swallows the indented
    `key: value` lines beneath it; an item without a colon stays the plain string that
    `modules:`, `tickets:` and `decisions:` are made of. Parsed once per path: two
    checks read the same record and a second parse would report every syntax defect
    twice.
    """
    if path in _FRONT_MATTER:
        return _FRONT_MATTER[path]
    _FRONT_MATTER[path] = {}
    text = read_text(path, findings)
    if text is None:
        return {}
    if not text.startswith('---'):
        findings.append(Finding(
            HARD, 'CLAIM-SYNTAX', rel(path), 'record has no front matter block'))
        return {}
    end = text.find('\n---', 3)
    if end < 0:
        findings.append(Finding(
            HARD, 'CLAIM-SYNTAX', rel(path), 'front matter block is not closed'))
        return {}
    data, key, item = {}, None, None
    for i, line in enumerate(text[3:end].splitlines(), 2):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.startswith((' ', '\t')):
            stripped = line.strip()
            if stripped.startswith('- ') and key:
                body = stripped[2:].strip()
                if ':' in body:
                    field, _, value = body.partition(':')
                    item = {field.strip(): value.strip()}
                    data.setdefault(key, []).append(item)
                else:
                    item = None
                    data.setdefault(key, []).append(body)
            elif isinstance(item, dict) and ':' in stripped:
                field, _, value = stripped.partition(':')
                item[field.strip()] = value.strip()
            continue
        if ':' not in line:
            findings.append(Finding(
                HARD, 'CLAIM-SYNTAX', '%s:%d' % (rel(path), i),
                'front matter line is neither "key: value" nor "  - item": %r' % line))
            continue
        key, _, value = line.partition(':')
        key, value = key.strip(), value.strip()
        item = None
        # `key: []` is an empty list written inline. Left as the string it looks like,
        # iterating it yields '[' and ']' and a claim check reports two missing files
        # named after brackets.
        data[key] = [] if value in ('', '[]') else value
    _FRONT_MATTER[path] = data
    return data


def check_coverage(findings, ratchet_base=None):
    cov_path = CONFORMANCE / 'coverage.json'
    if not cov_path.is_file():
        findings.append(Finding(
            HARD, 'COVERAGE', 'docs/conformance/coverage.json', 'claim ledger is missing'))
        return
    cov = json.loads(cov_path.read_text(encoding='utf-8'))
    if cov.get('schema') != 1:
        findings.append(Finding(
            HARD, 'COVERAGE', 'docs/conformance/coverage.json', 'unsupported ledger schema'))
        return

    universe = python_modules()
    allowed_reasons = {'generated', 'test-support', 're-export', 'vendored-reference'}
    exempt = set()
    for e in cov.get('exempt', []):
        exempt.add(e['module'])
        if e.get('reason') not in allowed_reasons:
            findings.append(Finding(
                HARD, 'COVERAGE-EXEMPT-REASON', 'docs/conformance/coverage.json',
                '%s uses reason %r; allowed: %s'
                % (e['module'], e.get('reason'), ', '.join(sorted(allowed_reasons)))))
        if not e.get('note'):
            findings.append(Finding(
                HARD, 'COVERAGE-EXEMPT-REASON', 'docs/conformance/coverage.json',
                '%s is exempt without a note saying why' % e['module']))

    uncovered = set()
    for u in cov.get('uncovered', []):
        uncovered.add(u['module'])
        ticket = u.get('ticket')
        if not ticket or not (ROOT / ticket).exists():
            findings.append(Finding(
                HARD, 'COVERAGE-TICKET', 'docs/conformance/coverage.json',
                'uncovered entry %s names a ticket that does not exist: %s'
                % (u['module'], ticket)))

    claimed, owner = set(), {}
    for name, path in records().items():
        fm = front_matter(path, findings)
        for module in fm.get('modules', []):
            if module in owner:
                findings.append(Finding(
                    HARD, 'COVERAGE-DOUBLE', module,
                    'claimed by both %s and %s; exactly one record owns a module'
                    % (owner[module], name)))
                continue
            owner[module] = name
            claimed.add(module)
            if module.startswith('Core/'):
                if module not in core_stems():
                    findings.append(Finding(
                        HARD, 'CLAIM', name, 'claimed Core stem does not exist: %s' % module))
            elif not (ROOT / module).exists():
                findings.append(Finding(
                    HARD, 'CLAIM', name, 'claimed module does not exist: %s' % module))

    # Both directions. Modules nobody claims, and ledger entries nothing needs.
    for module in sorted(universe - claimed - exempt - uncovered):
        findings.append(Finding(
            HARD, 'COVERAGE', module, 'no conformance record claims this module'))
    for module in sorted((uncovered & (claimed | exempt))):
        findings.append(Finding(
            HARD, 'COVERAGE-STALE', 'docs/conformance/coverage.json',
            '%s is in the uncovered allowlist but is now claimed or exempt; delete the entry'
            % module))
    for module in sorted(uncovered - universe - core_stems()):
        findings.append(Finding(
            HARD, 'COVERAGE-GONE', 'docs/conformance/coverage.json',
            '%s is in the uncovered allowlist but no longer exists' % module))

    if ratchet_base:
        try:
            blob = subprocess.check_output(
                ['git', 'show', '%s:docs/conformance/coverage.json' % ratchet_base],
                cwd=str(ROOT), stderr=subprocess.DEVNULL, timeout=60).decode('utf-8')
            base = {u['module'] for u in json.loads(blob).get('uncovered', [])}
            grew = sorted(uncovered - base)
            if grew:
                findings.append(Finding(
                    HARD, 'COVERAGE-RATCHET', 'docs/conformance/coverage.json',
                    'uncovered grew by %d: %s' % (len(grew), ', '.join(grew))))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            print('COVERAGE-RATCHET skipped (no merge base at %s)' % ratchet_base)
    return uncovered


# --------------------------------------------------------------------------- versions

def _int_of(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return node.value
    return None


def _dict_value(node, key):
    """The AST node a dict literal holds under a constant key, not its integer."""
    if not isinstance(node, ast.Dict):
        return None
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


def _dict_key(node, key):
    return _int_of(_dict_value(node, key))


def _choose(found, spec):
    """The declared site wins; any other site holding a different integer is a shadow."""
    if not found:
        return None, []
    line = spec.get('line')
    chosen = None
    for ln, v in found:
        if line is None or ln == line:
            chosen = v
            break
    if chosen is None:
        chosen = found[-1][1]
    return chosen, [(ln, v) for ln, v in found if v != chosen]


def resolve_code(spec, findings, where):
    """Return (value, [shadow sites]) for one binding's code side."""
    kind = spec.get('kind')
    path = ROOT / spec['file']
    if not path.is_file():
        findings.append(Finding(HARD, 'VERSION-CODE', where,
                                'binding names a file that does not exist: %s' % spec['file']))
        return None, []
    if kind == 'cxx-constexpr':
        pat = re.compile(CXX_CONST.format(name=re.escape(spec['name'])), re.M)
        m = pat.search(path.read_text(encoding='utf-8'))
        return (int(m.group(1)) if m else None), []

    tree = ast.parse(path.read_text(encoding='utf-8'))
    if kind == 'constant':
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else [])
            for t in targets:
                if isinstance(t, ast.Name) and t.id == spec['name']:
                    return _int_of(node.value), []
        return None, []

    if kind in ('emitted-key', 'returned-key'):
        found = []
        for node in ast.walk(tree):
            if kind == 'emitted-key' and isinstance(node, ast.Assign):
                for t in node.targets:
                    if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                            and t.slice.value == spec['block']):
                        v = _dict_key(node.value, spec.get('key', 'version'))
                        if v is not None:
                            found.append((node.lineno, v))
            if kind == 'returned-key' and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == spec.get('function'):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return):
                        v = _dict_key(sub.value, spec.get('key', 'version'))
                        if v is not None:
                            found.append((sub.lineno, v))
        return _choose(found, spec)

    if kind == 'tuple-bound':
        # A bound published as a tuple in a table -- bounds={'size':(3,1025)}. Read out
        # of the table rather than restated, so the binding cannot be satisfied by
        # editing a number here: only by moving the published bound itself.
        found = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if not (isinstance(t, ast.Name) and t.id == spec['name']):
                    continue
                entry = _dict_value(node.value, spec['key'])
                index = spec.get('index', 1)
                if isinstance(entry, (ast.Tuple, ast.List)) and len(entry.elts) > index:
                    v = _int_of(entry.elts[index])
                    if v is not None:
                        found.append((node.lineno, v))
        return _choose(found, spec)

    if kind == 'call-arg':
        # The enforcement half of a published bound: over_capacity('size',v,1025,'grid').
        # A bound and the guard that enforces it are two statements of one fact, and in
        # terrain_world.py they sit four hundred lines apart. They agree because somebody
        # checked, which is the footing the Python and native grid ceilings were on
        # before they drifted. `select` pins which call is meant, by a constant argument.
        found = []
        select = {int(i): want for i, want in spec.get('select', {}).items()}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
            if name != spec['call'] or len(node.args) <= spec['arg']:
                continue
            if any(len(node.args) <= i or not isinstance(node.args[i], ast.Constant)
                   or node.args[i].value != want for i, want in select.items()):
                continue
            v = _int_of(node.args[spec['arg']])
            if v is not None:
                found.append((node.lineno, v))
        return _choose(found, spec)

    findings.append(Finding(HARD, 'VERSION-CODE', where, 'unknown resolver kind %r' % kind))
    return None, []


_TREES = {}


def module_tree(mod):
    """Parse once. Six emitted-key bindings across 124 modules is 744 parses otherwise."""
    if mod not in _TREES:
        try:
            _TREES[mod] = ast.parse((ROOT / mod).read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            _TREES[mod] = None
    return _TREES[mod]


def scan_emitters(block, key):
    """Every site in Sim/ that assigns result[<block>] = {... <key>: int ...}.

    Repo-wide on purpose. The trap this exists for is cross-file: terrain_magic.py
    emits magic version 1 and terrain_leyline_history.py later overwrites the same
    block with 4. A scan confined to the declared file would never see it.
    """
    sites = []
    for mod in sorted(python_modules()):
        tree = module_tree(mod)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                        and t.slice.value == block):
                    v = _dict_key(node.value, key)
                    if v is not None:
                        sites.append((mod, node.lineno, v))
    return sites


def check_versions(findings, docs):
    path = CONFORMANCE / 'version-bindings.json'
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1:
        findings.append(Finding(HARD, 'VERSION', rel(path), 'unsupported bindings schema'))
        return

    actual, shadowed = {}, {}
    for b in data.get('bindings', []):
        where = 'docs/conformance/version-bindings.json'
        value, shadows = resolve_code(b['code'], findings, where)
        if value is None:
            findings.append(Finding(
                HARD, 'VERSION-CODE', where,
                'binding %r resolves to no integer in %s' % (b['id'], b['code']['file'])))
            continue
        actual[b['id']] = value
        allowed = set(b.get('shadowed_by', []))
        if b['code'].get('kind') == 'emitted-key':
            declared_line = b['code'].get('line')
            for mod, ln, v in scan_emitters(b['code']['block'], b['code'].get('key', 'version')):
                if v == value:
                    continue
                if mod == b['code']['file'] and ln == declared_line:
                    continue
                if mod in allowed:
                    continue
                findings.append(Finding(
                    HARD, 'VERSION-AMBIGUOUS', '%s:%d' % (mod, ln),
                    'binding %r is also emitted here as %d while the declared site '
                    '(%s) emits %d; declare the authoritative site or make them agree'
                    % (b['id'], v, b['code']['file'], value)))
        else:
            for ln, v in shadows:
                findings.append(Finding(
                    HARD, 'VERSION-AMBIGUOUS', '%s:%d' % (b['code']['file'], ln),
                    'binding %r is also emitted here as %d while the declared site emits %d; '
                    'declare the authoritative site or make them agree' % (b['id'], v, value)))
        if 'mirror' in b:
            mv, _ = resolve_code(b['mirror'], findings, where)
            if mv is not None and mv != value:
                findings.append(Finding(
                    HARD, 'VERSION-MIRROR', b['mirror']['file'],
                    'binding %r is %d in %s but %d here'
                    % (b['id'], value, b['code']['file'], mv)))
        shadowed[b['id']] = b

    marked = set()
    for p in docs:
        name = rel(p)
        if matches(name, FROZEN_GLOBS):
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            # Undecodable is reported by check_documents; gone is another session moving
            # a card mid-run. Neither is this check's to die on.
            continue
        # A marker shown as an example in a fence or in backticks is documentation of
        # the syntax, not a claim about this product.
        for i, line in enumerate(strip_code(text), 1):
            for bid, stated in VERSION_MARKER.findall(line):
                marked.add(bid)
                if bid not in shadowed:
                    findings.append(Finding(
                        HARD, 'VERSION', '%s:%d' % (name, i),
                        'marker names unknown binding %r' % bid))
                elif int(stated) != actual.get(bid):
                    findings.append(Finding(
                        HARD, 'VERSION', '%s:%d' % (name, i),
                        'marker says %s=%s but the code emits %s'
                        % (bid, stated, actual.get(bid))))
    return actual


# ----------------------------------------------------------------------------- claims

def check_claims(findings, versions):
    """The rest of the record: the eight front-matter keys nothing read.

    `modules:` was the only key this gate consulted, so every other claim a record made
    to its reader was decoration. `proof:` could name a file that was never written,
    `emits[].schema` a schema that had been deleted, `versions:` any integer at all --
    version checking runs off version-bindings.json and never consulted a record's own
    list -- and `tier:`, the one word a reader is most likely to trust, any word.

    What a green run of this establishes, stated so it is not read as more: the cited
    files exist, each proof path is a file one of the three suites discovers, each
    asserted version equals the integer the code emits, and `tier` is a declared word.
    It does not establish that a proof test passes, or that it establishes what
    `establishes:` says it does. Existence is not exercise.
    """
    for name, path in records().items():
        fm = front_matter(path, findings)
        if not fm:
            continue
        stem = Path(name).stem

        if fm.get('conformance') != '1':
            findings.append(Finding(
                HARD, 'CLAIM-SCHEMA', name,
                'record schema is %r; this gate reads schema 1' % fm.get('conformance')))
        if fm.get('record') != stem:
            findings.append(Finding(
                HARD, 'CLAIM-RECORD', name,
                'names itself %r but its file is %s.md; a record cited by name has to be '
                'findable by it' % (fm.get('record'), stem)))
        tier = fm.get('tier')
        if tier not in TIERS:
            findings.append(Finding(
                HARD, 'CLAIM-TIER', name,
                'tier %r is not a declared tier; the vocabulary is %s'
                % (tier, ', '.join('%s (%s)' % (k, v) for k, v in sorted(TIERS.items())))))
        if not isinstance(fm.get('summary'), str) or not fm.get('summary'):
            findings.append(Finding(
                HARD, 'CLAIM-SUMMARY', name,
                'has no summary; the record is the present-tense claim and a record that '
                'makes none is a heading'))

        for i, entry in enumerate(fm.get('emits') or []):
            if not isinstance(entry, dict) or 'schema' not in entry:
                findings.append(Finding(
                    HARD, 'CLAIM-EMITS', name,
                    'emits[%d] declares no schema: line; write `schema: none` to say '
                    'there is no schema rather than leaving it unsaid' % i))
                continue
            schema = entry['schema']
            if not disclaimed(schema) and not (ROOT / schema).exists():
                findings.append(Finding(
                    HARD, 'CLAIM-EMITS', name,
                    'emits[%d] names a schema that does not exist: %s' % (i, schema)))

        for i, entry in enumerate(fm.get('proof') or []):
            if not isinstance(entry, dict) or 'path' not in entry:
                findings.append(Finding(
                    HARD, 'CLAIM-PROOF', name, 'proof[%d] declares no path: line' % i))
                continue
            target = entry['path']
            if not entry.get('establishes'):
                findings.append(Finding(
                    HARD, 'CLAIM-PROOF', name,
                    'proof[%d] (%s) has no establishes: line; a proof citation that does '
                    'not say what it proves is a filename' % (i, target)))
            if disclaimed(target):
                continue
            if not (ROOT / target).exists():
                findings.append(Finding(
                    HARD, 'CLAIM-PROOF', name,
                    'proof[%d] names a file that does not exist: %s' % (i, target)))
            elif not matches(target, PROOF_PATTERNS):
                findings.append(Finding(
                    HARD, 'CLAIM-PROOF', name,
                    'proof[%d] names %s, which no test suite discovers; the suites run '
                    '%s' % (i, target, ', '.join(PROOF_PATTERNS))))

        for i, entry in enumerate(fm.get('versions') or []):
            if not isinstance(entry, dict) or 'id' not in entry or 'assert' not in entry:
                findings.append(Finding(
                    HARD, 'CLAIM-VERSION', name,
                    'versions[%d] is not an `- id:` with an `assert:` beneath it' % i))
                continue
            bid, stated = entry['id'], entry['assert']
            if bid not in versions:
                findings.append(Finding(
                    HARD, 'CLAIM-VERSION', name,
                    'versions[%d] asserts %s=%s, and no binding in '
                    'docs/conformance/version-bindings.json is named %s'
                    % (i, bid, stated, bid)))
            elif not stated.isdigit() or int(stated) != versions[bid]:
                findings.append(Finding(
                    HARD, 'CLAIM-VERSION', name,
                    'asserts %s=%s but the code emits %s' % (bid, stated, versions[bid])))

        # Tickets and decisions drift legitimately -- a card moves between backlog/,
        # in-progress/, done/ and retired/ and takes every citation of it along. A hard
        # failure would punish the move, so this half is soft.
        for field in ('tickets', 'decisions'):
            for target in fm.get(field) or []:
                if isinstance(target, str) and not (ROOT / target).exists():
                    findings.append(Finding(
                        WARN, 'CLAIM-REF', name,
                        '%s names %s, which does not exist; the card most likely moved'
                        % (field, target)))


def check_document_globs(findings):
    """Every document is claimed by a glob list, and every glob list claims a document.

    A checker that cannot see a folder cannot fail on it. `board/retired/` was created on
    2026-09-21 and named in neither list. Four cards moved into it, six sibling-relative
    links inside them died, and the run stayed green because the folder was never
    scanned. The only symptom was the document count falling from 208 to 204, which was
    rationalised rather than investigated, and the dead links were caught by a separate
    repo-wide sweep rather than here.

    Coverage is the property a gate cannot check about itself by passing. Both
    directions, because a new folder and a folder that moved away are different failures:
    a document matching no glob is unexamined, and a glob matching no document is a
    folder that has gone somewhere this list has not followed.
    """
    names = [rel(p) for p in all_markdown()]
    unchecked = {}
    for name in names:
        if matches(name, ACTIVE_GLOBS) or matches(name, FROZEN_GLOBS):
            continue
        hit = next((g for g in UNCHECKED_GLOBS if fnmatch.fnmatchcase(name, g)), None)
        if hit:
            unchecked.setdefault(hit, []).append(name)
            continue
        findings.append(Finding(
            HARD, 'GLOB-UNCLAIMED', name,
            'is examined by no glob in docs_check: add it to ACTIVE_GLOBS, to '
            'FROZEN_GLOBS if it is imported evidence, or to UNCHECKED_GLOBS with the '
            'reason. A checker that cannot see a folder cannot fail on it.'))
    for glob in tuple(ACTIVE_GLOBS) + tuple(FROZEN_GLOBS) + tuple(UNCHECKED_GLOBS):
        if not any(fnmatch.fnmatchcase(n, glob) for n in names):
            findings.append(Finding(
                WARN, 'GLOB-EMPTY', 'tools/docs_check.py',
                'glob %r matches no document; a folder that moved leaves its glob behind '
                'and takes its documents out of this gate without a finding' % glob))
    return unchecked


# --------------------------------------------------------------------------- reporting

def run(args):
    findings = []
    docs = [p for p in all_markdown() if matches(p, ACTIVE_GLOBS) or matches(p, FROZEN_GLOBS)]

    unchecked = check_document_globs(findings)
    check_documents(findings, docs)
    check_citations(findings, docs)
    check_index(findings)
    check_numbering(findings)
    check_provenance_decisions(findings)
    uncovered = check_coverage(findings, args.ratchet_base)
    check_claims(findings, check_versions(findings, docs))

    if args.list_uncovered:
        for m in sorted(uncovered or []):
            print(m)
        return 0

    errors = [f for f in findings if f.severity == HARD]
    warnings = [f for f in findings if f.severity == WARN]
    for f in sorted(errors, key=lambda f: (f.code, f.where)):
        print(f)
    for f in sorted(warnings, key=lambda f: (f.code, f.where)):
        print('%s  [warning]' % f)

    # What was NOT read, on every run and before the verdict. A green line that reports
    # only what it looked at reads as coverage of everything; the folder this gate could
    # not see is exactly the one that rotted.
    frozen = [p for p in docs if matches(p, FROZEN_GLOBS)]
    skipped = sum(len(v) for v in unchecked.values())
    print('%d document(s) not examined%s' % (
        skipped, (': ' + '; '.join('%s (%d) -- %s' % (g, len(v), UNCHECKED_GLOBS[g])
                                   for g, v in sorted(unchecked.items()))) if skipped else '.'))
    print('%d frozen document(s) read but not link-, citation- or version-checked.'
          % len(frozen))

    if errors:
        print('%d documentation error(s).' % len(errors))
        return 1
    print('Documentation checks passed: %d documents, %d modules claimed or declared.'
          % (len(docs), len(python_modules())))
    if warnings:
        print('%d warning(s), not blocking.' % len(warnings))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ratchet-base', help='git ref to compare the uncovered allowlist against')
    parser.add_argument('--list-uncovered', action='store_true',
                        help='print the modules no record claims yet')
    return run(parser.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
