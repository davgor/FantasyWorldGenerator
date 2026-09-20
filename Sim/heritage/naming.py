"""Names built under a genome: morphemic for places, phonotactic for people.

A settlement name is assembled from meaningful roots and carries its gloss, so a player can
be told that Khasdum is the stone-hall. A personal name is drawn syllable by syllable under
the tongue's actual template, which is what makes a form like `Caelioaes` unconstructible
rather than merely unlikely - the old generator appended a bare second nucleus and produced
vowel-on-vowel by design.

The gloss is returned beside the name but costs nothing to ignore: callers that only want a
string, such as a roster naming several thousand posts, never build one.
"""

_VOWEL_LETTERS = frozenset('aeiou')


def _is_vowel(token):
    return bool(token) and token[0] in _VOWEL_LETTERS


def _join(first, second, genome):
    """Smooth a compound seam under the tongue's own rules."""
    if not first:
        return second
    if not second:
        return first
    hiatus = genome['phonotactics']['hiatus']
    geminates = genome['phonotactics']['geminates']
    if first[-1] == second[0]:
        # A doubled letter across a seam is a geminate; tongues that lack them simplify.
        return first + second[1:] if not geminates else first + second
    if _is_vowel(first[-1]) and _is_vowel(second[0]) and hiatus == 'forbidden':
        return first[:-1] + second
    # A seam can spell a digraph its two halves never contained: `ulk` + `hakn` reads as
    # `ul-khakn`, inventing a `kh` neither root has and mis-teaching the reader where the
    # compound breaks. Drop the first root's final consonant rather than let the seam lie.
    from .derive import DIGRAPHS
    if first[-1] + second[0] in DIGRAPHS and len(first) > 2:
        return first[:-1] + second
    return first + second


REDRAW_LIMIT = 8


def _acceptable(word, forms):
    """Reject a form that reads as an English word nobody meant to ship.

    Not fastidiousness: a prototype of this design generated `Person` for a cold human from
    `per` + `son`, and `Mordor` for a hill dwarf from `copper` + `gate`. Innocent roots
    collide into loaded words, and a generated world produces far more names than anyone
    reviews. The check is a substring match because the compound, not the root, is where
    the accident happens.
    """
    lowered = word.lower()
    return not any(bad in lowered for bad in forms)


def _weighted(templates, draw):
    total = sum(t['weight'] for t in templates)
    cut, running = draw.random() * total, 0.0
    for template in templates:
        running += template['weight']
        if cut < running:
            return template
    return templates[-1]


def settlement_name(resolved, lexicon, draw, terrain_slot=None):
    """Return (name, gloss). `terrain_slot` lets a name echo the ground it stands on."""
    roots = resolved['genome']['lexicon']
    roles = lexicon['slot_roles']
    for _ in range(REDRAW_LIMIT):
        template = _weighted(lexicon['settlement_templates'], draw)
        chosen = []
        for index, role in enumerate(template['pattern']):
            options = [slot for slot in roles[role] if slot in roots]
            if not options:
                options = sorted(roots)
            if index == 0 and role == 'terrain' and terrain_slot in options:
                slot = terrain_slot
            else:
                slot = draw.choice(sorted(options))
            chosen.append(slot)
        word = ''
        for slot in chosen:
            word = _join(word, roots[slot], resolved['genome'])
        if _acceptable(word, resolved['genome'].get('forbidden_forms', ())):
            return word.capitalize(), '-'.join(chosen)
    # Bounded, so naming always terminates. Reaching here means the lexicon is small
    # enough that the filter cannot be satisfied, which is an authoring problem.
    return word.capitalize(), '-'.join(chosen)


def _nucleus(genome, draw):
    """Simple vowels carry most syllables; complex nuclei are a seasoning, not a staple.

    Drawing uniformly from the whole vowel set gave elvish `Paemuayuan` - every nucleus a
    diphthong, which no tongue does. The complex share is raised only where the genome says
    the speakers hold vowels: contrastive length, or a habit of hiatus.
    """
    vowels = genome['inventory']['vowels']
    simple = [v for v in vowels if len(v) == 1] or list(vowels)
    complex_ = [v for v in vowels if len(v) > 1]
    share = 0.15
    if genome['phonotactics']['vowel_length'] == 'contrastive':
        share = 0.3
    if genome['phonotactics']['hiatus'] == 'preferred':
        share = 0.4
    if complex_ and draw.random() < share:
        return draw.choice(complex_)
    return draw.choice(simple)


def _syllable(genome, draw, allow_onset_cluster, coda_mode):
    """coda_mode is 'none', 'optional' or 'required'."""
    phonotactics = genome['phonotactics']
    consonants = genome['inventory']['consonants']
    rate = genome['rates']['cluster']
    onsets = phonotactics['onset_clusters']
    codas = phonotactics['coda_clusters']
    if allow_onset_cluster and onsets and draw.random() < rate:
        part = draw.choice(onsets)
    else:
        part = draw.choice(genome['inventory'].get('onsets') or consonants)
    part += _nucleus(genome, draw)
    if coda_mode == 'none':
        return part
    if coda_mode == 'optional' and draw.random() >= 0.55:
        return part
    if codas and draw.random() < rate:
        return part + draw.choice(codas)
    return part + draw.choice([c for c in consonants if len(c) <= 2])


def person_name(resolved, lexicon=None, draw=None):
    """A personal name, dithematic when a lexicon is supplied and phonotactic otherwise.

    Real names are built from two meaning-bearing elements - Thor-bjorn, Gal-adriel,
    Ead-weard - and the difference shows: drawing syllables under the phonotactics alone
    produced pronounceable noise like `Gregaa` and `Penaatang`. Composing a quality with a
    craft or a terrain gives `Ulkbor` and `Narrik`, which read as names and gloss like the
    place names do.

    The element pairs deliberately avoid `terrain + site`, which is what a settlement is,
    so a person and a town do not come out looking like the same kind of word.

    `lexicon` is optional so the phonotactic path stays reachable for a caller that has a
    genome but no lexicon to hand; `person_name(resolved, draw)` still works.
    """
    if draw is None:
        lexicon, draw = None, lexicon
    forms = resolved['genome'].get('forbidden_forms', ())
    for _ in range(REDRAW_LIMIT):
        candidate = (_draw_dithematic(resolved, lexicon, draw) if lexicon
                     else _draw_person(resolved, draw))
        if candidate and _acceptable(candidate, forms):
            return candidate
    return candidate or _draw_person(resolved, draw)


def person_name_with_gloss(resolved, lexicon, draw):
    """As `person_name`, plus the English reading of its two elements."""
    slots = _pick_elements(resolved, lexicon, draw)
    if not slots:
        return _draw_person(resolved, draw), ''
    return _compose(resolved, slots), '-'.join(slots)


def _pick_elements(resolved, lexicon, draw):
    roots = resolved['genome']['lexicon']
    roles = lexicon['slot_roles']
    template = _weighted(lexicon['personal_templates'], draw)
    slots = []
    for role in template['pattern']:
        options = [slot for slot in roles[role] if slot in roots]
        if not options:
            return []
        slots.append(draw.choice(sorted(options)))
    return slots if len(set(slots)) == len(slots) else []


def _compose(resolved, slots):
    roots = resolved['genome']['lexicon']
    word = ''
    for slot in slots:
        word = _join(word, roots[slot], resolved['genome'])
    return word.capitalize()


def _draw_dithematic(resolved, lexicon, draw):
    slots = _pick_elements(resolved, lexicon, draw)
    return _compose(resolved, slots) if slots else ''


def _draw_person(resolved, draw):
    genome = resolved['genome']
    shape = genome['prosody']['word_shape']
    count = {'monosyllabic_heavy': 1, 'disyllabic': 2, 'trisyllabic_flowing': 2}[shape]
    if draw.random() < genome['rates']['third_syllable']:
        count += 1
    onset_cluster = genome['phonotactics']['max_onset_cluster'] > 1
    closes = genome['phonotactics']['max_coda_cluster'] > 0
    word = ''
    for index in range(count):
        last = index == count - 1
        # Only the final syllable closes, so a medial coda never meets the next onset and
        # builds a cluster the tongue does not permit. A one-syllable name must close, or
        # a heavy monosyllabic tongue produces bare `Na`.
        if not last or not closes:
            mode = 'none'
        elif count == 1 or shape == 'monosyllabic_heavy':
            mode = 'required'
        else:
            mode = 'optional'
        word = _join(word, _syllable(genome, draw, onset_cluster and index == 0, mode), genome)
    return _shift(word, genome).capitalize()


def _shift(word, genome):
    """Run the branch's own sound changes over a coined word.

    A sound change is a property of the tongue, not of the inherited vocabulary: a speaker
    who cannot say `th` cannot say it in a new name either. Applying the chain here is what
    keeps two siblings that share a soma from generating the same names.
    """
    from .derive import apply_sound_changes
    return apply_sound_changes(word, genome.get('sound_changes', ()))


def realm_name(resolved, capital_name):
    """A realm named for its seat, in the seat's own tongue.

    `Bargdorn` plus the dwarven realm morpheme gives `Bargdornrik`; the elven `doren` and
    the human `mark` do the same work. The join runs through the tongue's own seam rules,
    so whether a doubled letter survives is the tongue's decision and not this function's:
    `Bor` + `rik` is `Borik` in gnomish and hill-dwarvish, which have no geminates, and
    `Borrik` in dwarvish and frostholder, whose stone-hall and wind-scoured acoustics do.

    Returns an empty string when the culture has no realm morpheme, which lets a caller
    keep its English form rather than invent one.
    """
    root = resolved['genome']['lexicon'].get('realm')
    if not root or not capital_name:
        return ''
    return _join(capital_name.lower(), root, resolved['genome']).capitalize()


def name_table(resolved):
    """Adapter to the shape `hero_generator.naming.given_name` already consumes.

    A compatibility bridge, not the destination: the old function still appends a bare
    nucleus for its third syllable, so the tables below keep onsets consonant-initial and
    codas closed to limit the damage until that call site moves to `person_name`.
    """
    genome = resolved['genome']
    consonants, vowels = genome['inventory']['consonants'], genome['inventory']['vowels']
    onsets = [c + v for c in consonants[:12] for v in vowels[:3]]
    codas = [c for c in consonants if len(c) <= 2]
    if genome['phonotactics']['hiatus'] == 'preferred':
        codas = codas + ['', '']
    return {'onsets': sorted(set(onsets)), 'nuclei': list(vowels), 'codas': sorted(set(codas)),
            'third_syllable_chance': genome['rates']['third_syllable']}
