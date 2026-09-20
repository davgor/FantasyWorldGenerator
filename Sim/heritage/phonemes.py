"""The closed phoneme alphabet and the articulatory gates that open or shut parts of it.

This is code rather than data because it is a physical constraint, not a taste: a people
with blunt dentition cannot make an interdental fricative, and no amount of authoring
should let one. `terrain_leyline_history` sets the precedent of declaring an enum here and
nowhere else so a caller cannot guess a name into it.

Tokens are ASCII digraphs, not IPA. The repository hashes bytes and disables text
normalisation for every provenance destination; a table full of multi-byte glyphs would
put that contract under avoidable strain for no expressive gain.
"""

CONSONANTS = ('p', 'b', 't', 'd', 'k', 'g', 'q',
              'm', 'n', 'ng',
              'f', 'v', 'th', 'dh', 's', 'z', 'sh', 'zh', 'kh', 'gh', 'h',
              'ts', 'ch',
              'l', 'lh', 'r', 'w', 'y')

VOWELS = ('a', 'e', 'i', 'o', 'u',
          'aa', 'ee', 'ii', 'oo', 'uu',
          'ae', 'ao', 'ia', 'io', 'ua')

ALPHABET = frozenset(CONSONANTS + VOWELS)

# A base every tongue starts from before its soma opens or shuts anything.
CORE_CONSONANTS = ('p', 'b', 't', 'd', 'k', 'g', 'm', 'n', 'ng', 's', 'h', 'l', 'r')
CORE_VOWELS = ('a', 'e', 'i', 'o', 'u')

# What each soma axis value adds and removes. A phoneme removed by any gate stays
# removed: the forbidden set is a union, so one impossibility is not argued away by
# another axis that would have permitted it.
GATES = {
    'dentition': {
        'blunt':            {'drop': ('th', 'dh')},
        'even':             {'add': ('th', 'f', 'v')},
        'prominent_canine': {'add': ('f', 'v'), 'drop': ('dh',)},
        'tusked':           {'drop': ('f', 'v', 'th', 'dh')},
    },
    'vocal_tract': {
        'narrow':         {'add': ('ts', 'ch', 'sh', 'y'), 'drop': ('q', 'kh', 'gh')},
        'even':           {'add': ('f', 'v', 'w', 'y')},
        'broad':          {'add': ('kh', 'gh', 'w')},
        'resonant_chest': {'add': ('q', 'kh', 'gh', 'r'), 'drop': ('y',)},
    },
    'hearing_band': {
        # A tongue shaped for low frequencies sheds the contrasts its listeners
        # cannot separate; one sibilant survives to carry the whole series.
        'low_weighted':  {'drop': ('sh', 'zh', 'ts', 'ch', 'z')},
        'flat':          {'add': ('z',)},
        'high_weighted': {'add': ('s', 'z', 'sh', 'ts', 'ch')},
        'wide':          {'add': ('s', 'z', 'sh', 'ts', 'ch', 'zh')},
    },
    'body_scale': {
        'small':    {'add': ('ii',)},
        'compact':  {},
        'mid':      {},
        'tall':     {'add': ('ae', 'ee')},
        'towering': {'add': ('ao', 'uu')},
    },
    'breath_capacity': {
        'short':     {},
        'steady':    {},
        'deep':      {'add': ('aa',)},
        'sustained': {'add': ('aa', 'ee', 'oo', 'ia', 'io', 'ua')},
    },
}

GATED_AXES = tuple(GATES)


def inventory(traits):
    """Resolve a trait record to (consonants, vowels, forbidden).

    Additions accumulate and removals win, so `forbidden` lists every phoneme some gate
    ruled out and the two sets never overlap. Order follows ALPHABET rather than the
    order gates happened to fire, because this table is hashed into the heritage identity.
    """
    kept, banned = set(CORE_CONSONANTS) | set(CORE_VOWELS), set()
    for axis in GATED_AXES:
        rule = GATES[axis].get(traits[axis], {})
        kept.update(rule.get('add', ()))
        banned.update(rule.get('drop', ()))
    kept -= banned
    unknown = (kept | banned) - ALPHABET
    if unknown:
        raise ValueError('articulatory gate produced phonemes outside the alphabet: '
                         + ', '.join(sorted(unknown)))
    consonants = tuple(p for p in CONSONANTS if p in kept)
    vowels = tuple(p for p in VOWELS if p in kept)
    forbidden = tuple(p for p in CONSONANTS + VOWELS if p in banned)
    return consonants, vowels, forbidden
