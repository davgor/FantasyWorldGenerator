"""Names for places, in the idiom the rest of the tree already uses for sites.

The generator names cities by round-robin over twelve nature words plus the literal string
" City", and every ruin, realm and quest hook inherits those strings. That is a real gap and
worth its own ticket, but it is not this one's to fix, so key locations do what
``hero_generator`` does for sites: descriptor templates filled from world facts — "the
farmstead below Alder", "the shrine of The Red Field at Fern". A place named for what it is
and what it is near reads better than a syllable-generated proper noun attached to nothing,
and it stays honest about how much this world actually knows.

Pure: no filesystem, no network, no engine, no generator imports.
"""

ADJECTIVES = ('old', 'drowned', 'broken', 'quiet', 'hollow', 'grey', 'low', 'far', 'bitter',
              'long', 'black', 'dry', 'cold', 'deep', 'lost', 'crooked', 'silent', 'thin',
              'red', 'high', 'sunken', 'blind', 'empty', 'pale')
FALLBACK_NEAR = 'the waste'
SUFFIX = ' City'


def short_name(name):
    """``'Fern City'`` becomes ``'Fern'``; anything else is left alone."""
    if not name:
        return None
    return name[:-len(SUFFIX)] if name.endswith(SUFFIX) else name


def nearest(records, point, distance_of):
    """The record closest to ``point``, or ``None``. Ties break on name for replay stability."""
    best, best_distance = None, None
    for record in records:
        if not record.get('direction'):
            continue
        gap = distance_of(point, tuple(record['direction']))
        key = (gap, str(record.get('name') or record.get('id') or ''))
        if best_distance is None or key < best_distance:
            best, best_distance = record, key
    return best


def fill(template, context, draw):
    """Substitute the placeholders a template may use, leaving nothing unresolved."""
    text = template
    replacements = {
        '{near}': context.get('near') or FALLBACK_NEAR,
        '{culture}': context.get('culture') or 'the old people',
        '{school}': context.get('school') or 'unquiet',
        '{god}': context.get('god') or 'the nameless',
        '{adj}': ADJECTIVES[draw.randrange(len(ADJECTIVES))],
        '{ordinal}': context.get('ordinal') or 'lone',
    }
    for token, value in replacements.items():
        text = text.replace(token, str(value))
    return text


def name_for(archetype, context, draw):
    templates = archetype['names']
    # A chain member is named by its place in the chain when the archetype offers that, so a
    # run of waystones counts itself out instead of reading as eleven unrelated stones.
    numbered = [t for t in templates if '{ordinal}' in t]
    if context.get('ordinal') and numbered:
        templates = numbered
    chosen = templates[draw.randrange(len(templates))]
    usable = [t for t in templates if '{near}' not in t]
    if '{near}' in chosen and not context.get('near') and usable:
        chosen = usable[draw.randrange(len(usable))]
    return fill(chosen, context, draw)


ARTICLE = 'the '
# Disjoint from ADJECTIVES on purpose: an overlap silently shrinks the variant pool, which
# only shows up as a duplicate name once a world is crowded enough to exhaust it.
QUALIFIERS = ('upper', 'lower', 'nether', 'outer', 'inner', 'further')


def _without_article(text):
    return text[len(ARTICLE):] if text.startswith(ARTICLE) else text


def unique_name(archetype, context, draw, used, attempts=6):
    """A name no other location in this world already carries.

    Templates collide constantly - three silver mines near the same city all want to be
    "the deeps under Bracken" - and a duplicate name makes two different places
    indistinguishable to anything that refers to them by name. Ids stay the real key, but a
    name that cannot tell two locations apart is a name that has failed at its one job.

    Tries the archetype's own templates first, then qualifies with an adjective, then with a
    position word. Only if all of those collide does it accept a duplicate, which needs the
    same archetype near the same neighbour more times than the vocabulary can distinguish.
    """
    for _ in range(attempts):
        candidate = name_for(archetype, context, draw)
        if candidate not in used:
            used.add(candidate)
            return candidate
    base = _without_article(name_for(archetype, context, draw))
    order = list(ADJECTIVES)
    draw.shuffle(order)
    for prefix in order:
        if base.startswith(prefix + ' '):
            continue
        candidate = f'{ARTICLE}{prefix} {base}'
        if candidate not in used:
            used.add(candidate)
            return candidate
    for qualifier in QUALIFIERS:
        for adjective in order:
            for prefix in (qualifier, f'{qualifier} {adjective}'):
                if base.startswith(prefix.split()[-1] + ' '):
                    continue
                candidate = f'{ARTICLE}{prefix} {base}'
                if candidate not in used:
                    used.add(candidate)
                    return candidate
    used.add(ARTICLE + base)
    return ARTICLE + base
