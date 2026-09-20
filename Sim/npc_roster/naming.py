"""The one place a name is made, so replacing the name-maker was a one-function change.

It has now been replaced. Names come from the heritage language genome, keyed on
`civilization_id`, so each of the twelve cultures draws from its own tongue:

    name_for(civilization_id, parent_race_id, draw) -> str

That is the signature this module committed to while the interim tables stood, and the
signature it still has. Nothing else in the package moved.

What the swap fixed. The interim tables were keyed by *parent race*, so nine of the twelve
cultures read as their parent and four peoples — tidekin, gnome, hill_dwarf, frosthold_dwarf —
had no table at all and silently fell through to the human one. They had human names for as
long as they have existed. `parent_race_id` is still passed because it selects the language
*family*; `civilization_id` selects the language.

There is no fallback. A record without a civilization id raises, because the silent fallback is
precisely the defect being removed here, and a loud failure is the only thing that stops it
coming back.
"""
import heritage

_LEXICON = None


def _shared_lexicon():
    """Load the lexicon once. It is immutable and reading it per name is pure overhead."""
    global _LEXICON
    if _LEXICON is None:
        _LEXICON = heritage.lexicon()
    return _LEXICON


def name_for(civilization_id, parent_race_id, draw):
    """A given name for one person, in that people's own language."""
    if not civilization_id:
        raise ValueError('a person needs a civilization_id to be named from')
    resolved = heritage.resolve(civilization_id, parent_race_id)
    return heritage.person_name(resolved, _shared_lexicon(), draw)


def name_with_gloss(civilization_id, parent_race_id, draw):
    """The same name plus what it means, for anything that wants to show its working."""
    if not civilization_id:
        raise ValueError('a person needs a civilization_id to be named from')
    resolved = heritage.resolve(civilization_id, parent_race_id)
    return heritage.person_name_with_gloss(resolved, _shared_lexicon(), draw)
