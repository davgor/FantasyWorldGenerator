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
)
# Historical or imported evidence: read but never repaired. Frozen must be a subset of
# what is provenance-pinned or of board/done, so nothing current can hide in here.
FROZEN_GLOBS = (
    'docs/terrain-math-lab.md',
    'docs/catalogue/world-assets/*.md',
    'board/done/*.md',
    'provenance/source-reviews/*.md',
)

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
    out = []
    for p in sorted(ROOT.rglob('*.md')):
        parts = p.relative_to(ROOT).parts
        if '.git' in parts or 'node_modules' in parts or '.venv' in parts:
            continue
        out.append(p)
    return out


def read_text(path, findings):
    """Read a document, reporting an unreadable one rather than raising."""
    try:
        return path.read_bytes().decode('utf-8')
    except UnicodeDecodeError as exc:
        findings.append(Finding(
            HARD, 'ENCODING', rel(path),
            'is not valid UTF-8 (%s at byte %d); a reader that assumes UTF-8 crashes on it'
            % (exc.reason, exc.start)))
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
        except UnicodeDecodeError:
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


def check_provenance_decisions(findings):
    p = ROOT / 'provenance' / 'extraction-manifest.json'
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


def front_matter(path, findings):
    """A deliberately small key: value and - item subset. No PyYAML."""
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
    data, key = {}, None
    for i, line in enumerate(text[3:end].splitlines(), 2):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.startswith((' ', '\t')):
            item = line.strip()
            if item.startswith('- ') and key:
                data.setdefault(key, []).append(item[2:].strip())
            continue
        if ':' not in line:
            findings.append(Finding(
                HARD, 'CLAIM-SYNTAX', '%s:%d' % (rel(path), i),
                'front matter line is neither "key: value" nor "  - item": %r' % line))
            continue
        key, _, value = line.partition(':')
        key, value = key.strip(), value.strip()
        data[key] = value if value else []
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
                cwd=str(ROOT), stderr=subprocess.DEVNULL).decode('utf-8')
            base = {u['module'] for u in json.loads(blob).get('uncovered', [])}
            grew = sorted(uncovered - base)
            if grew:
                findings.append(Finding(
                    HARD, 'COVERAGE-RATCHET', 'docs/conformance/coverage.json',
                    'uncovered grew by %d: %s' % (len(grew), ', '.join(grew))))
        except (subprocess.CalledProcessError, ValueError):
            print('COVERAGE-RATCHET skipped (no merge base at %s)' % ratchet_base)
    return uncovered


# --------------------------------------------------------------------------- versions

def _int_of(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return node.value
    return None


def _dict_key(node, key):
    if not isinstance(node, ast.Dict):
        return None
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return _int_of(v)
    return None


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
        if not found:
            return None, []
        # The declared site wins; any other site emitting a different value is a shadow.
        line = spec.get('line')
        chosen = None
        for ln, v in found:
            if line is None or ln == line:
                chosen = v
                break
        if chosen is None:
            chosen = found[-1][1]
        shadows = [(ln, v) for ln, v in found if v != chosen]
        return chosen, shadows
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
        except UnicodeDecodeError:
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


# --------------------------------------------------------------------------- reporting

def run(args):
    findings = []
    docs = [p for p in all_markdown() if matches(p, ACTIVE_GLOBS) or matches(p, FROZEN_GLOBS)]

    check_documents(findings, docs)
    check_citations(findings, docs)
    check_index(findings)
    check_numbering(findings)
    check_provenance_decisions(findings)
    uncovered = check_coverage(findings, args.ratchet_base)
    check_versions(findings, docs)

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
