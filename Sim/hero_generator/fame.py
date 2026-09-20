"""Fame: deed magnitude times stake reach, from numbers the world already carries.

A capital lost to an international war is a bigger wound than a hamlet-sized town lost to
a civil quarrel, and a person seated in a capital of a large realm reaches further than a
dispossessed heir with no seat. Both factors come from exported fields, so raising the
class of the fallen city or the tier of the beast must raise the fame; a test holds that.
"""
CLASS_WEIGHT = {'small': 1., 'medium': 2., 'capital': 3.}
SITE_WEIGHT = {'hamlet': .5, 'fortress': 1., 'port': 1., 'shrine': .5}  # a countryside seat is a smaller deed than a city
WAR_WEIGHT = {'civil': 1., 'regional': 2., 'international': 3.}
LEGEND_REACH = .5
SEAT_WEIGHT = {'magistrate': 1.5, 'commander': 1.5, 'market_steward': 1.2, 'chaplain': 1., 'mage': 1., 'librarian': .8}
# A capital heir with a capital seat lands near 19; a victor who took a capital in an
# international war near 38. Legendary is reserved for the latter kind of deed.
TIERS = ((24., 'legendary'), (8., 'renowned'), (0., 'notable'))


def class_weight(city_class):
    return CLASS_WEIGHT.get(city_class, 1.)


def person_magnitude(person):
    total = 0.
    for deed in person['deeds']:
        if deed['event_kind'] == 'ruin' and deed['role'] == 'heir':
            total += class_weight(person['lost']['city_class'])
        elif deed['event_kind'] == 'ruin' and deed['role'] in ('actual', 'keeper', 'credited'):
            total += (1. if deed['role'] == 'actual' else .5) * class_weight(person['lost']['city_class'])
        elif deed['event_kind'] == 'war' and deed['role'] == 'credited':
            total += WAR_WEIGHT.get(deed.get('kind'), 1.) * class_weight(deed.get('defeated_class', 'small'))
        elif deed['event_kind'] == 'war':
            total += .5 * WAR_WEIGHT.get(deed.get('kind'), 1.)
        elif deed['event_kind'] == 'nest':
            total += .6 * deed.get('tier', 1)
        elif deed['event_kind'] == 'founding':
            total += 1.5
        elif deed['event_kind'] in SITE_WEIGHT:
            total += SITE_WEIGHT[deed['event_kind']]
    if person['role'] == 'sovereign':
        total += class_weight((person.get('home') or {}).get('city_class', 'capital'))
    elif person['role'] == 'council':
        total += SEAT_WEIGHT.get(person.get('seat'), 1.)
    return total


def person_reach(person, cities_by_uid, realms_by_uid):
    if not person.get('home'):
        return LEGEND_REACH
    home = cities_by_uid.get(person['home']['uid'], {})
    realm = realms_by_uid.get(person.get('realm_uid'))
    return class_weight(home.get('city_class', 'small')) + .25 * (len(realm['city_uids']) if realm else 1)


def dread_magnitude(dread):
    return sum(.6 * dread['nest_tier'] * class_weight(d.get('city_class', 'small')) for d in dread['deeds'])


def dread_reach(dread, nests_by_id):
    nest = nests_by_id.get(dread['nest_id'])
    return min(3., nest.get('range_m', 1000.) / 1000.) if nest else LEGEND_REACH


def fame(magnitude, reach):
    return round(magnitude * (1. + reach), 3)


def tier(value):
    return next(name for floor, name in TIERS if value >= floor)
