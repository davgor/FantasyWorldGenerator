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


# --- The stock: which of those names a people actually uses, and how often ----------------
#
# `person_name` says what a tongue can build. It does not say what a people calls its
# children, and drawing uniformly from the first answers the second badly. A heartland
# genome composes 88 names; drawn uniformly each lands on about one person in ninety, so
# nobody is common and - the part that costs more - nobody is unusual either. A rare name
# cannot mark a foreigner, an old family or an affectation when no name is rare.
#
# Real naming is far more concentrated than that. In the English poll tax returns of the
# late fourteenth century one man in three was a John and the five commonest names covered
# about four fifths of all men, with a long tail of forms borne by one person each. These
# shares are those figures rounded. They are tabulated rather than fitted because the
# measured curve is steeper at the head than any single Zipf exponent reproduces: an
# exponent steep enough to put one name at 35% still leaves the top five short of 79%.
HEAD_SHARES = (0.35, 0.17, 0.12, 0.09, 0.06)

# What the ranks below the head divide the remaining 0.21 by. A plain 1/r.
ZIPF_EXPONENT = 1.0

# How often a name comes from outside the common stock. Small on purpose: this is the tail
# that makes rarity mean something, not a second stock.
RARE_SHARE = 0.025


def _rare_patterns(lexicon):
    """The ordered role pairs the authored templates leave unspent.

    A rare name is still two meaning-bearing roots joined. It has to be: the phonotactic
    path coins `Wopagup` and `Yoroochaat`, which is the reason the dithematic path exists,
    and a tail built from it would read as generator noise exactly where a reader is meant
    to notice the name. What makes these rare is the *pairing*. A `site`-initial form or a
    craft before a terrain is legal in the tongue and simply not what this people usually
    calls a child.

    Both authored sets are removed. Pairs already spent on personal names are what common
    means, so they cannot also be rare; pairs spent on settlements would make a person read
    as a town, which is the collision `person_name` documents itself as avoiding.
    """
    roles = sorted(lexicon['slot_roles'])
    spent = {tuple(template['pattern']) for template in lexicon['personal_templates']}
    spent |= {tuple(template['pattern']) for template in lexicon['settlement_templates']}
    return [(first, second) for first in roles for second in roles
            if first != second and (first, second) not in spent]


def _enumerate(resolved, lexicon, patterns):
    """`{name: (gloss, weight, slots)}` for every slot pair those patterns admit here.

    Composition collides: two different root pairs can join to one string once the seam
    rules have had their say, so the table is keyed on the finished name. The first reading
    wins and the highest weight wins, because a name a common template can reach is a common
    name however else it can also be reached.
    """
    roots = resolved['genome']['lexicon']
    roles = lexicon['slot_roles']
    forms = resolved['genome'].get('forbidden_forms', ())
    found = {}
    for pattern, weight in patterns:
        heads = sorted(slot for slot in roles[pattern[0]] if slot in roots)
        tails = sorted(slot for slot in roles[pattern[1]] if slot in roots)
        for first in heads:
            for second in tails:
                if first == second:
                    continue  # `_pick_elements` discards a repeated slot; so does this.
                name = _compose(resolved, (first, second))
                if not _acceptable(name, forms):
                    continue
                previous = found.get(name)
                if previous is None:
                    found[name] = (f'{first}-{second}', weight, (first, second))
                elif weight > previous[1]:
                    found[name] = (previous[0], weight, previous[2])
    return found


def _ordered(found):
    """Rank order before the head is spread: authored weight, then length, then spelling.

    Rank has to be a property of the culture rather than of a seed - `Eldsel` is a common
    heartland name in every world the way John was common in every English county - and this
    package carries no seed logic by design, which rules out permuting the order with one.

    Template weight is authored and already says which shapes a people reaches for. Length
    breaks its ties, because the names that wear into everyday use are the short ones, and
    the spelling breaks what is left, so the order is total and the stock is reproducible.
    """
    return sorted(found.items(), key=lambda entry: (-entry[1][1], len(entry[0]), entry[0]))


# How many of the commonest names are held apart from each other. The head carries about
# four fifths of a people, so these are the names a reader meets over and over.
HEAD_SPREAD = 5


def _ranked(found):
    """Commonest first, with the head spread across the space rather than bunched in it.

    Ranking on length alone put the whole heartland head on one root: `Eldsel`, `Frosel`,
    `Nersel`, `Versel`, and the elves on `-naur` four times over. That is worse than the
    uniform draw it replaces. Four fifths of a people would share not just a few names but a
    few *sounds*, and a reader meeting them in succession hears a stutter rather than a
    culture. Real stocks do not behave that way: John, William, Thomas, Richard and Robert
    have nothing in common, because a name that cannot be told from the last one is a name
    that stops being used.

    So the head is filled greedily from rank order, skipping any name that reuses a root
    already standing in it. What is skipped is not discarded - it falls to the body of the
    stock, in its own rank order - and if the space is too small to fill the head with
    distinct roots, the rank order stands unaltered rather than the head running short.
    """
    ordered = _ordered(found)
    head, body, spent = [], [], set()
    for name, (gloss, _weight, slots) in ordered:
        if len(head) < HEAD_SPREAD and not spent.intersection(slots):
            spent.update(slots)
            head.append((name, gloss))
        else:
            body.append((name, gloss))
    if len(head) < min(HEAD_SPREAD, len(ordered)):
        return [(name, value[0]) for name, value in ordered]
    return head + body


def _thresholds(count):
    """Cumulative draw thresholds over `count` ranks: the tabulated head, then 1/r.

    Normalised at the end so a stock smaller than the head table still sums to one rather
    than silently dropping its last ranks below the last threshold.
    """
    if count <= 0:
        return ()
    shares = list(HEAD_SHARES[:count])
    rest = count - len(shares)
    if rest > 0:
        remainder = 1.0 - sum(shares)
        harmonic = sum(1.0 / rank ** ZIPF_EXPONENT for rank in range(1, rest + 1))
        shares += [remainder / rank ** ZIPF_EXPONENT / harmonic for rank in range(1, rest + 1)]
    total = sum(shares)
    running, cumulative = 0.0, []
    for share in shares:
        running += share / total
        cumulative.append(running)
    return tuple(cumulative)


def name_stock(resolved, lexicon):
    """Every name this people uses, ranked, with the thresholds that say how often.

    Pure and seedless, so one people yields one stock in every world. It enumerates the
    whole reachable space, which is cheap but not free - build it once per civilization and
    hand it to `stock_name` for each person rather than per name.
    """
    common = _ranked(_enumerate(resolved, lexicon,
                                [(template['pattern'], template['weight'])
                                 for template in lexicon['personal_templates']]))
    rare = _ranked(_enumerate(resolved, lexicon,
                              [(pattern, 1) for pattern in _rare_patterns(lexicon)]))
    spoken = {name for name, _ in common}
    # A rare pairing that composes to a name the common stock already holds is not rare.
    rare = [entry for entry in rare if entry[0] not in spoken]
    return {'common': common, 'rare': rare, 'thresholds': _thresholds(len(common))}


def stock_name(stock, draw):
    """One `(name, gloss)` under the people's own concentration, or None if the stock is empty.

    Two draws whatever the outcome, so the stream a caller sees does not depend on which
    branch was taken and adding the rare tail cannot desynchronise a replay from itself.

    An empty stock means a family whose roots reach none of the personal templates, which is
    an authoring failure rather than a naming one; the caller falls back and it stays visible.
    """
    roll, cut = draw.random(), draw.random()
    common, rare = stock['common'], stock['rare']
    if not common:
        # No common stock means no personal template this family's roots can fill. The rare
        # pairings may still compose, but promoting them would make the tail the whole tongue
        # and hide the authoring fault behind names that look fine. Refuse the whole stock.
        return None
    if rare and roll < RARE_SHARE:
        return rare[min(int(cut * len(rare)), len(rare) - 1)]
    for index, threshold in enumerate(stock['thresholds']):
        if cut < threshold:
            return common[index]
    return common[-1]
