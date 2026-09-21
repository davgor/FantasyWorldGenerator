"""Archetype selection: preconditions filter, alignment priors and features weight, the seed picks.

A card is eligible when any one of its `requires` conjunctions is a subset of the person's
features. Features the current wells cannot compute are simply absent, so cards that need
them are never chosen until the well that supplies them exists. Nothing is clamped by
alignment: a prior only changes frequency.
"""

# Every feature a card may name. Wells set a subset; the rest are reserved for later wells,
# so a card that needs one is documented but unreachable until that well exists.
FEATURES = frozenset({
    # roles
    'role:pretender', 'role:warlord', 'role:dread', 'role:champion', 'role:sovereign', 'role:magister',
    'role:domain_holder', 'role:schemer', 'role:council', 'role:prophet', 'role:heresiarch', 'role:exile',
    'role:founder', 'role:camp_leader',
    # countryside, ports and shrines wells
    'role:reeve', 'role:castellan', 'role:harbourmaster', 'role:keeper',
    'hamlet:farming', 'hamlet:resource', 'hamlet:starving', 'hamlet:threatened', 'fortress:pressed', 'port:terminal',
    'shrine:ruin', 'shrine:cult',
    # ruins well
    'home:fell', 'stake:lost', 'heir:small', 'heir:medium', 'heir:capital', 'sides:both', 'civ:lost_many',
    'dread:living', 'realm:contested', 'war:civil_victor', 'war:regional_victor', 'war:international_victor',
    'home:fell_later', 'dread:long_lived', 'dread:ages_2', 'legend:predecessor',
    # cities and guilds wells
    'seat:magistrate', 'seat:commander', 'seat:chaplain', 'seat:market_steward', 'seat:mage', 'seat:librarian',
    'dynasty:founding', 'sovereign:advised',
    # magic well and placement
    'seat:college', 'role:camp_leader', 'college:destroyed', 'keypoint:ruin_born', 'school:dark', 'stake:none', 'seat:none',
    # fame
    'fame:renowned', 'fame:legendary',
    # reserved for later wells
    'dread:person_shaped', 'order:member', 'order:remnant', 'order:against_dark', 'keypoint:ruin_born',
    # `villain:prior_age` is a dispossessed claimant, NOT a super villain -- `terrain_villains`
    # owns that word in the world model and the two share no field. The full disclaimer is at
    # `features.py`, where the token is set.
    'deed:credited_not_actual', 'deed:dark_nest', 'villain:prior_age', 'stake:regained', 'stake:none',
    'ley:tainted_home', 'rival:spared', 'realm:cold_conflicts_2', 'realm:tyrant', 'stakes:2', 'seat:trade',
    'seat:none', 'routes:2', 'mentor:successor', 'heir:unclaimed', 'council:outranks_sovereign',
    'sovereign:advised', 'college:destroyed', 'dread:failed_against', 'defence:failed', 'warden:post',
    'school:dark', 'ally:lost', 'deeds:two_civilizations', 'deeds:two_schools',
})


def eligible(card, features):
    return any(all(feature in features for feature in conjunction) for conjunction in card['requires'])


def weight(card, features, alignment):
    value = 1.
    for feature, factor in card['boosts'].items():
        if feature in features:
            value *= factor
    match = card['prior']['law'] * alignment['law'] + card['prior']['good'] * alignment['good']
    return value * max(.25, 1. + .75 * match)


def choose(cards, features, alignment, draw):
    """Seeded weighted choice in catalogue order; None when no card's precondition holds."""
    options = [(card, weight(card, features, alignment)) for card in cards if eligible(card, features)]
    total = sum(w for _, w in options)
    if total <= 0:
        return None
    selector = draw.random() * total
    for card, w in options:
        selector -= w
        if selector <= 0:
            return card
    return options[-1][0]
