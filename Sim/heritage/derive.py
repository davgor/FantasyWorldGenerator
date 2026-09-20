"""Resolve a people: race base, subrace delta, derived culture, derived genome, overrides.

The chain is deliberately one direction with no feedback. Traits are authored, culture is a
pure function of traits, the genome is a pure function of culture and traits, and each
derived layer may then be patched by a sparse override. Nothing downstream writes back, so
`resolve` is a pure function of two strings and the packaged document.

Unlike the civilization registry this does not hot-reload. Packaged resources carry no stat
to key a cache on, and the tables are immutable at runtime; `reset_cache` exists for tests.
"""
import copy
import hashlib
import json
from functools import lru_cache

from . import phonemes, policy


def merge_traits(base, delta, label='people'):
    """Shallow, key-by-key. An axis has no internal structure, so there is nothing to merge."""
    merged = dict(base)
    for axis, value in delta.items():
        if axis not in base:
            raise ValueError(f'{label} names an unknown axis {axis!r}')
        if base[axis] == value:
            raise ValueError(f'{label} overrides axis {axis!r} with its inherited value')
        merged[axis] = value
    return merged


def _apply_rule(rule, traits):
    if 'copy' in rule:
        return traits[rule['copy']]
    if 'craft' in rule:
        return traits['craft_focus'][rule['craft']]
    return rule['map'][traits[rule['from']]]


def derive_culture(traits, rules):
    return {block: {key: _apply_rule(rule, traits) for key, rule in keys.items()}
            for block, keys in rules['culture'].items()}


def _template_shape(template):
    """(C)(C)V(C) is two onsets and one coda; (C)V(C)(C) is the reverse. N counts as a coda."""
    head, _, tail = template.partition('V')
    return head.count('(C)'), tail.count('(C)') + tail.count('(N)')


def _clusters(consonants, onset_max, coda_max):
    """Plausible clusters from what the inventory actually holds, in alphabet order.

    Onsets and codas are built separately because they are not interchangeable: a sequence
    that opens a syllable rarely closes one. The shapes here are the cross-linguistically
    common ones - stop plus liquid, and s plus voiceless stop, in front; sonorant plus
    voiceless stop, and homorganic nasal plus stop, behind. Letting any fricative lead
    produced onsets like `kht`, and pairing any nasal with any stop produced codas like
    `nb`; both are the kind of form a real tongue would have levelled long ago.
    """
    stops = [c for c in ('p', 'b', 't', 'd', 'k', 'g', 'q') if c in consonants]
    voiceless = [c for c in ('p', 't', 'k') if c in consonants]
    liquids = [c for c in ('l', 'lh', 'r') if c in consonants]
    nasals = [c for c in ('m', 'n', 'ng') if c in consonants]
    onset, coda = [], []
    if onset_max > 1:
        # `tl` and `dl` are the two stop-liquid pairs most tongues refuse.
        onset += [a + b for a in stops for b in liquids
                  if not (a in ('t', 'd') and b in ('l', 'lh'))]
        if 's' in consonants:
            onset += ['s' + b for b in voiceless]
    if coda_max > 1:
        coda += [a + b for a in liquids for b in voiceless]
        if 's' in consonants:
            coda += [a + 's' for a in liquids]
        # Nasal plus stop only where the two share a place of articulation. Pairing any
        # nasal with any stop produced `Pimd` and `Wongd`; homorganic pairing is the rule
        # real tongues keep, and it is why `mp`, `nt` and `ngk` are the surviving shapes.
        # `ng` takes only the voiceless member: ng + g renders as the unreadable `ngg`.
        for nasal, stops_here in (('m', ('p', 'b')), ('n', ('t', 'd')), ('ng', ('k',))):
            if nasal in consonants:
                coda += [nasal + b for b in stops_here if b in consonants]
    return tuple(sorted(set(onset))), tuple(sorted(set(coda)))


DIGRAPHS = frozenset(t for t in phonemes.CONSONANTS + phonemes.VOWELS if len(t) > 1)


def apply_sound_changes(word, changes):
    """Rewrite a word, treating multi-letter phonemes as atomic.

    A naive `str.replace` reads the `s` inside `sh` as an `s`, so the rainforest rule
    s -> sh turned `mush` into `mushh`. Scanning left to right and consuming a digraph
    whole makes a rule apply to the phoneme it names and to nothing else. Each rule runs
    as one non-overlapping pass, and rules run in order, so they may feed each other.
    """
    for old, new in changes:
        out, index = [], 0
        while index < len(word):
            pair = word[index:index + 2]
            if pair in DIGRAPHS and old != pair:
                out.append(pair)
                index += 2
                continue
            if word.startswith(old, index):
                out.append(new)
                index += len(old)
                continue
            out.append(word[index])
            index += 1
        word = ''.join(out)
    return word


def branch_lexicon(lexicon, family, branch):
    """Family roots rewritten by the branch's ordered sound changes, then its own coinages.

    Innovations are added after the changes rather than before: a word the branch invented
    was not present when the sound shift ran, which is why gnomish keeps `spril` intact.
    """
    entry = lexicon['families'][family]
    spec = entry['branches'].get(branch, {'sound_changes': [], 'add_roots': {}})
    roots = {}
    for slot, root in entry['roots'].items():
        if slot in spec.get('drop_roots', ()):
            continue
        roots[slot] = apply_sound_changes(root, spec['sound_changes'])
    roots.update(spec.get('add_roots', {}))
    return roots


def _family_for(lexicon, parent_race_id):
    for name, entry in lexicon['families'].items():
        if entry['parent_race'] == parent_race_id:
            return name, entry
    raise ValueError(f'no lexicon family for parent race {parent_race_id!r}')


def derive_genome(culture, traits, rules, lexicon, parent_race_id, branch):
    family, entry = _family_for(lexicon, parent_race_id)
    consonants, vowels, forbidden = phonemes.inventory(traits)
    derived = {block: {key: _apply_rule(rule, traits) for key, rule in keys.items()}
               for block, keys in rules['genome'].items()}
    onset_max, coda_max = _template_shape(derived['phonotactics']['syllable'])
    onset_clusters, coda_clusters = _clusters(consonants, onset_max, coda_max)
    derived['phonotactics'].update({
        'max_onset_cluster': onset_max,
        'max_coda_cluster': coda_max,
        'onset_clusters': list(onset_clusters),
        'coda_clusters': list(coda_clusters),
        'allowed_clusters': sorted(set(onset_clusters) | set(coda_clusters)),
    })
    derived['morphology'].update({
        'word_order': entry['word_order'],
        'affixing': entry['affixing'],
        'patronymic': {'given_plus_father': 'patronymic', 'given_plus_clan': 'clan_name',
                       'given_plus_house': 'house_name', 'given_plus_cohort': 'cohort_name',
                       'given_plus_vessel': 'vessel_name',
                       'given_plus_workshop': 'workshop_name'}[
                           culture['household']['naming_pattern']],
    })
    derived['orthography']['digraphs'] = [c for c in consonants if len(c) > 1]
    spec = entry['branches'].get(branch, {'sound_changes': []})
    return {
        'family': family,
        'branch': branch,
        'inventory': {'consonants': list(consonants), 'vowels': list(vowels),
                      'forbidden': list(forbidden),
                      # `ng` is a fine coda and a poor word onset in most tongues; without
                      # this, dwarven produced names like `Ngukhuls`.
                      'onsets': [c for c in consonants if c != 'ng']},
        # Carried so coined words undergo the same shifts the inherited roots did. Without
        # it two siblings with the same soma generate identical personal names - which is
        # exactly what human_large_island and human_rainforest did before this line.
        'sound_changes': [list(change) for change in spec['sound_changes']],
        'forbidden_forms': list(lexicon.get('forbidden_forms', ())),
        'lexicon': branch_lexicon(lexicon, family, branch),
        **derived,
    }


def _patch_inventory(derived, patch):
    add, drop = tuple(patch.get('add', ())), tuple(patch.get('drop', ()))
    overlap = sorted(set(add) & set(drop))
    if overlap:
        raise ValueError(f'override both adds and drops phoneme {overlap[0]!r}')
    for token in add + drop:
        if token not in phonemes.ALPHABET:
            raise ValueError(f'override names phoneme {token!r} outside the alphabet')
    for token in drop:
        if token not in derived:
            raise ValueError(f'override drops phoneme {token!r} the derivation never produced')
    for token in add:
        if token in derived:
            raise ValueError(f'override adds phoneme {token!r} the derivation already produced')
    kept = (set(derived) | set(add)) - set(drop)
    order = phonemes.CONSONANTS + phonemes.VOWELS
    return [p for p in order if p in kept]


def apply_overrides(derived, patch, label):
    """Depth two and no deeper, so the merge rule stays statable in one sentence."""
    result = copy.deepcopy(derived)
    touched = []
    for block, keys in patch.items():
        if block not in result:
            raise ValueError(f'override for {label} touches unknown block {block!r}')
        for key, value in keys.items():
            if key not in result[block]:
                raise ValueError(f'override for {label} touches unknown key {block}.{key}')
            current = result[block][key]
            if isinstance(value, dict):
                result[block][key] = _patch_inventory(current, value)
            else:
                if current == value:
                    raise ValueError(f'override for {label} restates the derived value '
                                     f'at {block}.{key}')
                result[block][key] = value
            touched.append(f'{block}.{key}')
    return result, touched


@lru_cache(maxsize=1)
def _document():
    return policy.load_all()


@lru_cache(maxsize=1)
def lexicon():
    """The shared root tables and name templates, loaded once.

    A caller needs this alongside a resolved people to build a morphemic name. It is the
    same document for every people, so it is fetched separately rather than copied into
    each resolution.
    """
    return _document()['lexicon']


@lru_cache(maxsize=64)
def _resolve(civ_id, parent_race_id):
    policies = _document()
    traits_doc = policies['traits']
    if parent_race_id not in traits_doc['races']:
        raise ValueError(f'unknown parent race {parent_race_id!r}')
    base = traits_doc['races'][parent_race_id]
    # An unlisted civilization resolves to its parent base. That is the property that lets a
    # new people arrive with a plausible culture and language already attached, and it is
    # what keeps a registry test that injects a synthetic entity working.
    delta = traits_doc['peoples'].get(civ_id, {})
    traits = merge_traits(base, delta, f'people {civ_id!r}')
    culture = derive_culture(traits, policies['derivation'])
    culture, culture_touched = apply_overrides(
        culture, policies['overrides'].get('culture', {}).get(civ_id, {}), civ_id)
    genome = derive_genome(culture, traits, policies['derivation'], policies['lexicon'],
                           parent_race_id, civ_id)
    genome, genome_touched = apply_overrides(
        genome, policies['overrides'].get('genome', {}).get(civ_id, {}), civ_id)
    return {
        'id': civ_id,
        'parent_race_id': parent_race_id,
        'traits': traits,
        'culture': culture,
        'genome': genome,
        'provenance': {
            'revisions': policy.revisions(policies),
            'overridden': [f'culture.{p}' for p in culture_touched]
                          + [f'genome.{p}' for p in genome_touched],
        },
    }


def resolve(civ_id, parent_race_id):
    """Resolve one people. The two arguments are not treated alike.

    An unknown `civ_id` resolves to its parent base, so a people that heritage has never
    heard of still arrives with a complete culture and tongue. An unknown or missing
    `parent_race_id` raises: it selects the language *family*, so guessing one yields a
    name in the wrong language rather than an approximate one, and that silent guess is
    the defect this package exists to remove.

    A caller that cannot supply a parent race should leave the name empty and say so,
    rather than substituting a default.
    """
    return copy.deepcopy(_resolve(civ_id, parent_race_id))


def revisions():
    return policy.revisions(_document())


def heritage_identity(pairs):
    """Hash the resolved peoples, not the source bytes.

    A derivation edit that changes no output then invalidates nothing, while a one-character
    override that does change an output is caught. `pairs` is an iterable of
    (civilization_id, parent_race_id) so this package stays a leaf.
    """
    resolved = {cid: _resolve(cid, parent) for cid, parent in sorted(pairs)}
    blob = json.dumps(resolved, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return {'revision': revisions(),
            'sha256': hashlib.sha256(blob.encode('utf-8')).hexdigest()}


def reset_cache():
    _resolve.cache_clear()
    lexicon.cache_clear()
    _document.cache_clear()
