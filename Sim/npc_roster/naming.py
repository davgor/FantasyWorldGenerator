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

Names now come off that genome's **stock** rather than straight off its generator. A roster is
where the difference shows: a size-65 world carries some thirteen thousand people, and drawing
each one uniformly from the 88 names a heartland tongue can build made every name equally
ordinary - no name common enough to be met twice and none rare enough to be worth remarking.
`heritage.name_stock` ranks the space once per people and `heritage.stock_name` draws under a
concentration taken from the historical record, with a small tail of forms outside the common
stock. What that leaves undone is the byname: at this concentration the commonest heartland
name lands on hundreds of people in one world, and telling them apart is the job of a
patronymic, a trade or a home town, none of which this module writes yet.
"""
import heritage

_LEXICON = None
_STOCKS = {}


def _shared_lexicon():
    """Load the lexicon once. It is immutable and reading it per name is pure overhead."""
    global _LEXICON
    if _LEXICON is None:
        _LEXICON = heritage.lexicon()
    return _LEXICON


def _stock_for(civilization_id, parent_race_id):
    """`(resolved, stock)` for one people, built once.

    Building a stock enumerates the whole reachable name space. That is cheap for one people
    and ruinous thirteen thousand times, and the result is seedless, so it caches on the pair
    that determines it and nothing else.
    """
    if not civilization_id:
        raise ValueError('a person needs a civilization_id to be named from')
    key = (civilization_id, parent_race_id)
    if key not in _STOCKS:
        resolved = heritage.resolve(civilization_id, parent_race_id)
        _STOCKS[key] = (resolved, heritage.name_stock(resolved, _shared_lexicon()))
    return _STOCKS[key]


def reset_cache():
    """Drop the memoised lexicon and stocks, for a test that edits the policies underneath."""
    global _LEXICON
    _LEXICON = None
    _STOCKS.clear()


def name_with_gloss(civilization_id, parent_race_id, draw):
    """A name plus what it means, for anything that wants to show its working."""
    resolved, stock = _stock_for(civilization_id, parent_race_id)
    drawn = heritage.stock_name(stock, draw)
    if drawn is None:
        # No template this people's roots can fill, which is an authoring fault in the
        # lexicon rather than a naming one. Coin rather than return nothing, and let the
        # heritage linter be what reports it.
        return heritage.person_name_with_gloss(resolved, _shared_lexicon(), draw)
    return drawn


def name_for(civilization_id, parent_race_id, draw):
    """A given name for one person, in that people's own language."""
    return name_with_gloss(civilization_id, parent_race_id, draw)[0]
