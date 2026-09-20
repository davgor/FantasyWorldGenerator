"""Event logs, situations, bonds and mantles: derived from deeds, never invented, never planned.

The log is the whole of what a person has been through, one entry per recorded event in
age order, each pointing at the event id. The situation is one sentence about where they
stand now. That is all an orchestrator gets; what they do next is its call, on the fly.
"""
from .history import cause_phrase, civilization_name, short_name

CLASS_WORD = {'small': 'small city', 'medium': 'city', 'capital': 'capital'}


def _entry(deed, text):
    return {'age': deed['age'], 'event_kind': deed['event_kind'], 'event_id': deed['event_id'], 'role': deed['role'], 'text': text}


def person_log(world, person, ruins_by_uid):
    entries = []
    lost = person.get('lost')
    for deed in person['deeds']:
        if deed['event_kind'] == 'hamlet':
            entries.append(_entry(deed, f"Speaks for {person['site_name']}, which feeds {person['home']['name']}"
                                        f"{'; the ' + person['nest_name'].lower() + ' hunts its fields' if person.get('nest_name') else ''}."))
        elif deed['event_kind'] == 'fortress':
            entries.append(_entry(deed, f"Commands {person['site_name']}, on the road to {person['home']['name']}."))
        elif deed['event_kind'] == 'port':
            entries.append(_entry(deed, f"Runs {person['site_name']}; every hull bound for {person['home']['name']} pays its due."))
        elif deed['event_kind'] == 'shrine':
            entries.append(_entry(deed, f"{'Leads' if person['role'] == 'heresiarch' else 'Tends'} {person['site_name']}."))
        elif person['role'] == 'pretender' and deed['event_kind'] == 'ruin':
            entries.append(_entry(deed, f"{lost['name']}, {CLASS_WORD.get(lost['city_class'], 'city')} of the "
                                        f"{civilization_name(world, person['civilization_id'])}, was destroyed by "
                                        f"{cause_phrase(ruins_by_uid[lost['uid']])}; its heir survived."))
        elif person['role'] == 'pretender' and deed['role'] == 'victim':
            entries.append(_entry(deed, f"Lost the {deed['kind']} war that ended {lost['name']}."))
        elif person['role'] == 'pretender':
            entries.append(_entry(deed, f"{lost['name']} won a {deed['kind']} war."))
        elif person['role'] == 'warlord':
            entries.append(_entry(deed, f"Led {person['victor_name']} to victory over {deed['defeated_name']} in a "
                                        f"{deed['kind']} war; {deed['defeated_name']} is a ruin."))
        elif person['role'] == 'magister':
            entries.append(_entry(deed, f"{lost['name']} destroyed itself in a magical experiment; the master of its college "
                                        f"walked out of the ash, and a {person['school']} key point burns where the city stood."))
        elif person['role'] == 'domain_holder':
            entries.append(_entry(deed, f"Took up the {person['school']} key point left where {lost['name']} fell to {cause_phrase(ruins_by_uid[lost['uid']])}."))
        elif person['role'] == 'sovereign':
            entries.append(_entry(deed, f"{person['home']['name']} {'won' if deed['role'] == 'credited' else 'lost'} a {deed['kind']} war."))
        elif person['role'] == 'champion' and deed['event_kind'] == 'nest':
            entries.append(_entry(deed, f"Holds the line for {person['home']['name']} against the {person['nest_name'].lower()}."))
        elif person['role'] == 'champion':
            entries.append(_entry(deed, f"Stood for {lost['name']} against the {person['nest_name'].lower()}, and the city fell anyway."))
        elif person['role'] in ('prophet', 'heresiarch', 'exile', 'founder'):
            reason = deed.get('reason', '').replace('_', ' ')
            entries.append(_entry(deed, f"Led the {reason} that founded {person['claim']['target_name'] if person['role'] in ('exile', 'founder') else 'a new city'}."))
    entries.sort(key=lambda e: (e['age'], e['event_id']))
    return entries


def person_situation(world, person, camps_by_uid):
    presence = person.get('presence') or {}
    site = presence.get('site_kind')
    situation = presence.get('situation')
    lost = person.get('lost')
    if person['role'] == 'reeve':
        selectable = person.get('features') or person.get('selectable') or ()
        trouble = 'the granary is short' if 'hamlet:starving' in selectable else 'the harvest is in'
        return f"Reeve of {person['site_name']}; {trouble}" + (f", and the {person['nest_name'].lower()} is close." if person.get('nest_name') else '.')
    if person['role'] == 'castellan':
        return f"Holds {person['site_name']} for {person['home']['name']}."
    if person['role'] == 'harbourmaster':
        return f"Keeps the ledger of {person['site_name']}."
    if person['role'] == 'keeper':
        return f"Tends {person['site_name']}" + (f" and shelters at {person['home']['name']}." if person.get('home') else '; no city of the old people stands near.')
    if person['role'] == 'heresiarch' and site == 'shrine':
        return f"Preaches from {person['site_name']}" + (f" toward {person['claim']['target_name']}." if person['claim']['verb'] == 'convert' else '.')
    if person['role'] == 'pretender':
        if site == 'camp':
            return f"Leads {camps_by_uid[presence['uid']]['name']}; still claims {lost['name']}."
        if person.get('home'):
            return f"Sheltered at {person['home']['name']}; still claims {lost['name']}."
        return (f"No city of the {civilization_name(world, person['civilization_id'])} survives to shelter the heir; "
                f"the claim on {lost['name']} passed into legend.")
    if person['role'] == 'warlord':
        if person.get('victor_fell'):
            return f"{person['victor_name']} itself fell in a later age; the victor is remembered, not seated."
        return f"Holds {person['victor_name']}."
    if person['role'] == 'magister':
        if site == 'camp':
            camp = camps_by_uid[presence['uid']]['name']
            return f"Held captive at {camp}." if situation == 'captive' else f"Hiding at {camp}, unrecognised."
        if site == 'city':
            return f"A refugee at {person['home']['name']}; the college is ash, the {person['school']} key point is not."
        if site == 'college':
            return f"Heads the college near {short_name(person['home']['name'])}."
        return f"Gone; the last master of {lost['name']} is a name in the ash."
    if person['role'] == 'domain_holder':
        if site == 'ruin':
            return f"Wards the {person['school']} key point in the ruins of {short_name(lost['name'])}."
        return f"The {person['school']} key point at {short_name(lost['name'])} has no keeper now."
    if person['role'] == 'sovereign':
        return f"Sits the throne of {person['claim']['target_name']} at {person['home']['name']}."
    if person['role'] == 'council':
        return f"Holds the {person.get('seat', 'council').replace('_', ' ')} seat at {person['home']['name']}."
    if person['role'] == 'champion':
        if site == 'city':
            return f"Champion of the Order at {person['home']['name']}; the {person['nest_name'].lower()} is still out there."
        if site == 'camp':
            return f"{'Held captive at' if situation == 'captive' else 'Hiding at'} {camps_by_uid[presence['uid']]['name']}; the Order is a remnant."
        if person.get('home'):
            return f"A refugee at {person['home']['name']}; the Order of {short_name(lost['name'])} is a remnant."
        return f"The Order of {short_name(lost['name'])} is a remnant; its champion is a name."
    if person['role'] in ('prophet', 'heresiarch'):
        return f"Preaches at {person['home']['name']}." if person.get('home') else "The schism outlived its prophet."
    if person['role'] in ('exile', 'founder'):
        return f"Leads {person['home']['name']}." if person.get('home') else "The founding outlived its leader."
    return ''


def dread_log(dread):
    return [_entry(d, f"Destroyed {d['city_name']}.") for d in sorted(dread['deeds'], key=lambda d: (d['age'], d['event_id']))]


def dread_situation(dread):
    if dread['status'] == 'living':
        return f"The lair still stands; the {dread['species']} has not been driven out."
    return f"The lair is gone, but the name of the {dread['species']} is not."


def bonds(people, dreads):
    """Edges from shared deeds: heir and the warlord who took the city, heir and beast, keeper and heir of one ruin."""
    edges = []
    pretenders = {p['lost']['uid']: p for p in people if p['role'] == 'pretender'}
    for person in people:
        if person['role'] == 'warlord':
            for defeat in person['defeated']:
                heir = pretenders.get(defeat['uid'])
                if heir:
                    edges.append({'a': heir['uid'], 'b': person['uid'], 'kind': 'rival', 'from_event': defeat['war_id']})
        elif person['role'] in ('domain_holder', 'magister') and person.get('lost'):
            heir = pretenders.get(person['lost']['uid'])
            if heir:
                kind = 'rival' if person['role'] == 'domain_holder' else 'kin'
                edges.append({'a': heir['uid'], 'b': person['uid'], 'kind': kind, 'from_event': person['lost']['ruin_id']})
    for dread in dreads:
        for destroyed in dread['destroyed']:
            heir = pretenders.get(destroyed['uid'])
            if heir:
                edges.append({'a': heir['uid'], 'b': dread['uid'], 'kind': 'rival', 'from_event': 'ruin-' + destroyed['uid']})
    warlords_by_city = {p.get('victor_uid'): p for p in people if p['role'] == 'warlord'}
    sovereigns_by_realm = {p['realm_uid']: p for p in people if p['role'] == 'sovereign'}
    for person in people:
        home_uid = (person.get('home') or {}).get('uid')
        if person['role'] == 'champion' and home_uid in warlords_by_city:
            edges.append({'a': person['uid'], 'b': warlords_by_city[home_uid]['uid'], 'kind': 'betrayed', 'from_event': warlords_by_city[home_uid]['deeds'][0]['event_id']})
        if person['role'] == 'council' and person.get('realm_uid') in sovereigns_by_realm:
            edges.append({'a': person['uid'], 'b': sovereigns_by_realm[person['realm_uid']]['uid'], 'kind': 'ally', 'from_event': home_uid})
        if 'mentor:successor' in person.get('selectable', ()):
            pupil = min((q for q in people if q['status'] == 'living' and q is not person and q['civilization_id'] == person['civilization_id'] and q['born_age'] > person['born_age']),
                        key=lambda q: (q['born_age'], q['uid']), default=None)
            if pupil:
                edges.append({'a': person['uid'], 'b': pupil['uid'], 'kind': 'mentor', 'from_event': person['deeds'][0]['event_id'] if person['deeds'] else person['uid']})
    return edges


def mantles(people):
    return [{'claim': person['claim'], 'predecessor_uid': person['uid'], 'civilization_id': person['civilization_id'],
             'vacant_since_age': person['born_age']}
            for person in people if person['status'] == 'legend' and person['claim']['verb'] in ('retake', 'hold')]
