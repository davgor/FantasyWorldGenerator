"""Packaged policy documents: post labels with their verbs, and the interim naming tables.

Policies are data so the roster can be re-tagged or re-capped without touching code. Each
file carries its own ``revision``; the combined revisions travel with every block so a
consumer can tell a policy edit from a world change.

`posts.json` holds a snapshot of the building staffing rosters copied out of
`Sim/icarus_sim/buildings.json`, because this package must not import the generator. That
snapshot can drift when the registry is edited, so `test_npc_roster` re-reads the registry
and fails on any difference. The lint below is the cheaper half of that guard: it checks the
document is internally coherent without needing the registry present.
"""
from importlib.resources import files
import json

POLICY_FILES = ('posts', 'names')
SITE_KINDS = ('city', 'hamlet', 'fortress')
CLASS_CAPS = ('capital', 'medium', 'small')
NAME_TABLE_FIELDS = ('onsets', 'medials', 'nuclei', 'codas', 'third_syllable_chance')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate policy key {key!r}')
        result[key] = value
    return result


def _reject(token):
    raise ValueError(f'non-finite policy number {token}')


def load(name):
    if name not in POLICY_FILES:
        raise ValueError(f'unknown policy {name!r}')
    text = files('npc_roster.policies').joinpath(name + '.json').read_text(encoding='utf-8')
    document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject)
    if type(document.get('revision')) is not int or document['revision'] < 1:
        raise ValueError(f'policy {name} needs a positive integer revision')
    return document


def load_all():
    policies = {name: load(name) for name in POLICY_FILES}
    lint_posts(policies['posts'])
    lint_names(policies['names'])
    return policies


def revisions(policies):
    return {name: policies[name]['revision'] for name in POLICY_FILES}


def lint_posts(document):
    verbs = document.get('verbs')
    if not isinstance(verbs, list) or not verbs or len(set(verbs)) != len(verbs):
        raise ValueError('posts policy needs a non-empty list of distinct verbs')
    known = set(verbs)
    for role, tagged in document['role_verbs'].items():
        if not isinstance(tagged, list) or len(set(tagged)) != len(tagged):
            raise ValueError(f'role {role} needs a list of distinct verbs')
        unknown = sorted(set(tagged) - known)
        if unknown:
            raise ValueError(f'role {role} offers verbs outside the canonical list: {unknown}')
    buildings = document['buildings']
    if not buildings:
        raise ValueError('posts policy lists no staffed buildings')
    for building, roles in buildings.items():
        if not roles:
            raise ValueError(f'{building} is listed with no roles; omit it instead')
        seen = set()
        for row in roles:
            if len(row) != 2 or not isinstance(row[0], str) or type(row[1]) is not int or row[1] < 0:
                raise ValueError(f'{building} has a malformed role row {row!r}')
            if row[0] in seen:
                raise ValueError(f'{building} repeats role {row[0]!r}')
            seen.add(row[0])
        if not any(target for _, target in roles):
            raise ValueError(f'{building} has no post with a positive target; omit it instead')
    missing = sorted(set(document['giver_rank']) - set(buildings))
    if missing:
        raise ValueError(f'giver_rank names buildings with no roster: {missing}')
    if len(set(document['giver_rank'])) != len(document['giver_rank']):
        raise ValueError('giver_rank repeats a building')
    caps = document['caps']
    for key in CLASS_CAPS + SITE_KINDS[1:]:
        if type(caps.get(key)) is not int or caps[key] < 0:
            raise ValueError(f'caps needs a non-negative integer for {key}')


def lint_names(document):
    """The names policy is now a record of a completed handover, not a table of syllables.

    It is kept rather than deleted so that `policy_revision` still reports which naming
    contract a roster was built against: a consumer reading an old export needs to be able to
    tell an interim-table roster from a genome one, and a missing key cannot say that.

    The check that matters is the last one. If race tables ever reappear here, something has
    reintroduced the parent-race model that gave four peoples human names, and it should fail
    at load rather than quietly out-name the genome.
    """
    supersede = document.get('supersede')
    if not isinstance(supersede, dict) or not supersede.get('package'):
        raise ValueError('names policy must record which package supersedes it')
    if supersede.get('status') != 'complete':
        raise ValueError('names policy records a handover that never completed')
    if 'races' in document:
        raise ValueError('names policy carries race tables again; the genome supersedes them')


def _retired_name_table_lint(document):
    """Retained unreachable for one revision so the removed rules are readable in review."""
    races = document.get('races')
    if not races or 'human' not in races:
        raise ValueError('names policy needs race tables including a human fallback')
    for race, table in races.items():
        for field in NAME_TABLE_FIELDS:
            if field not in table:
                raise ValueError(f'name table {race} lacks {field}')
        for field in ('onsets', 'medials', 'nuclei', 'codas'):
            if not table[field]:
                raise ValueError(f'name table {race} has an empty {field}')
        chance = table['third_syllable_chance']
        if not isinstance(chance, (int, float)) or not 0 <= chance <= 1:
            raise ValueError(f'name table {race} has an out-of-range third_syllable_chance')
