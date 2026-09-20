"""Deterministic names: a given name from the people's own language, an epithet from the deeds.

The given name now comes from the heritage genome, keyed on `civilization_id` rather than on
the parent race. That distinction is the whole point: keyed on the parent race, a desert human
and a cold human drew from one table, and the four peoples with no table of their own -
tidekin, gnome, hill_dwarf, frosthold_dwarf - fell through to the human one without comment.

`given_name` and the `races` tables that fed it are gone. They were kept only while
`Sim/npc_roster/naming.py` still drew from the same parent-race model; that package now calls
the genome too, so the last reader is gone and the tables with it.

Epithets stay English on purpose. They are what the player reads about a hero, and
`Torsunn the Unyielding` is the intended effect.
"""
from .history import short_name
from .seeds import rng


def heritage_name(person, draw):
    """A given name in the person's own tongue.

    `race_id` on a hero record is the *parent* race, so it selects the language family and
    nothing finer; `civilization_id` selects the language. Both are already stamped on every
    record by the wells, so this is a lookup rather than a new requirement.

    A record missing `civilization_id` raises instead of falling back. The silent fallback
    this replaces is the defect - it gave four peoples human names for as long as they have
    existed, and a loud failure is the only way that does not happen again.
    """
    import heritage
    civilization_id = person.get('civilization_id')
    if not civilization_id:
        raise ValueError(f"person {person.get('uid')!r} has no civilization_id to name it from")
    resolved = heritage.resolve(civilization_id, person.get('race_id') or 'human')
    return heritage.person_name(resolved, heritage.lexicon(), draw)


def _fill(template, context):
    """Substitute placeholders; a capitalised token asks for a capitalised value.

    `{school}` renders "the fire focus", `{School}` renders "the Fire Stone". Without the
    second form a school name filled mid-title reads as a typo - `Keeper of the fire Stone` -
    and capitalising in the data instead would break the places the lowercase form is right.

    Only the first letter is raised: `str.capitalize` would lower the rest and turn a seat
    like `Court Mage` into `Court mage`.
    """
    for key, value in context.items():
        template = template.replace('{' + key + '}', value)
        template = template.replace('{' + key[:1].upper() + key[1:] + '}', value[:1].upper() + value[1:])
    return template


def person_name(policy, person, seed):
    draw = rng(seed, 'hero-name-' + person['uid'])
    name = heritage_name(person, draw)
    context = {'lost': short_name(person['lost']['name']) if person.get('lost') else '',
               'home': short_name(person['home']['name']) if person.get('home') else '',
               'victor': short_name(person['victor_name']) if person.get('victor_name') else '',
               'defeated': short_name(person['defeated'][0]['name']) if person.get('defeated') else '',
               'school': person.get('school') or 'weave',
               'site': (person.get('site_name') or '').replace('the ', '', 1),
               'seat': {'magistrate': 'Magistrate', 'commander': 'Commander', 'chaplain': 'Chaplain', 'market_steward': 'Steward',
                        'mage': 'Court Mage', 'librarian': 'Archivist'}.get(person.get('seat'), 'Councillor')}
    epithets = policy['epithets'][person['role']]
    if person['status'] == 'legend' and 'legend' in policy['epithets']:
        epithets = epithets + policy['epithets']['legend']
    usable = [e for e in epithets if all(context.get(key) for key in _placeholders(e))] or epithets
    epithet = _fill(draw.choice(usable), context)
    return name, epithet


def _placeholders(template):
    """Context keys a template needs, case-folded so `{School}` still finds `school`.

    Without the fold, a capitalised token resolves to no context value, the template is judged
    unusable and is quietly dropped from the draw - the epithet would not render wrong, it
    would never be chosen.
    """
    return [part.split('}')[0].lower() for part in template.split('{')[1:]]


def dread_name(policy, dread, seed):
    draw = rng(seed, 'hero-name-' + dread['uid'])
    context = {'city': short_name(dread['destroyed'][0]['name']), 'species': dread['species']}
    return _fill(draw.choice(policy['epithets']['dread']), context)

