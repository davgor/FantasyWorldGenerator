"""Hero generator: the larger-than-life cast a finished world's history precipitates.

Called once when the world generator finishes, with the world and its story so far, as
plain JSON. It reads ruins, wars, cities, nests, ley networks, colleges, cultures, and
the diaspora record and writes nothing back. Its output is the `heroes` block: people,
dreads, realms, orgs, camps, relics, quest hooks, bonds, mantles, and the roll ledger.
Each person is a named handle on an event the world already recorded, with a derived
alignment, an archetype whose persona an agent can play from, one or more faces, and an
event log of what they have been through. Nothing is planned for them: the log, the
situation, the faces and the hooks are the data an orchestrator improvises from.

Not every event precipitates a person. Each candidate rolls once against the wells policy
and the roll is exported whether it precipitated or not.

Determinism: every draw comes from ``child_seed(world seed, 'hero-...' + uid)``, so the same
world and the same policy revisions give the same cast byte for byte. Isolation: the
generator core imports only :func:`attach`; a raising revision yields a failed block, not a
crashed world.
"""
import os

from . import archetypes as archetype_rules
from . import fame as fame_rules
from . import features as feature_rules
from .alignment import derive_dread, derive_person, intensify
from .faces import build as build_faces
from .facts import bonds, dread_log, dread_situation, mantles, person_log, person_situation
from .history import cities, final_age, nests, radius, ruins, world_seed
from .hooks import quest_hooks
from .naming import dread_name, person_name
from .persona import compose
from .policy import load_all, revisions
from .realms import build_realms, realm_by_city
from .seeds import rng
from .sites import camps as build_camps
from .sites import place, relics as build_relics
from .wells import cities as cities_well
from .wells import countryside as countryside_well
from .wells import guilds as guilds_well
from .wells import magic as magic_well
from .wells import ports as ports_well
from .wells import ruins as ruins_well
from .wells import shrines as shrines_well

VERSION = 1
ENV_SWITCH = 'FANTASY_WORLD_HEROES'
COMPANION_JOIN = {'captive': 'rescued', 'hidden': 'found', 'refugee': 'hired'}
METHOD = ('Walk the finished history through seven wells. Hamlets: a reeve who speaks for the farmstead that starves or loses '
          'its herds. Fortresses: a castellan who holds the road. Ports: a harbourmaster with a trade seat. Shrines: a keeper '
          'at a shrine, a heresiarch at a cult. Ruins: a ruin may leave an heir, a war a remembered victor, a '
          'beast kill a named Dread. Magic: a key point a warden, a self-destroyed college a surviving master, a living '
          'college a head. Cities: a realm a sovereign (and a founding capital a dynasty), every city a council by class, '
          'a diaspora its prophet, exile or founder. Guilds: every guild hall under threat an Order with a champion, '
          'every beast-taken city a remnant with a champion who failed. Each candidate rolls once against the wells '
          'policy and the roll is recorded. Ruins may be squatted as camps and always leave a relic; the dispossessed '
          'are placed at camps or as refugees. Cross-cutting features (tainted ground, outranked sovereigns, living '
          'successors, refounded peoples, tyrant realms) are computed once the cast is known. Fame is deed magnitude '
          'times stake reach; alignment is derived from civilization bias and deeds before an archetype is chosen from '
          'the cards whose preconditions the person\'s own record satisfies, seated people first so a Tyrant can make '
          'Rebels; the persona is the alignment-neutral card coloured by the two axis overlays, once per face. Claims '
          'compile into quest hooks typed against ruins, cities, nests, relics, colleges and ley nodes; a public face '
          'states a different purpose than the effect. Each person carries an event log and a present situation, not a plan.')
LIMITS = ('An artistic reading of the exported history, not a demographic claim. Council seats are a policy table by '
          'city class, not the placed rosters. Claims and hooks are exported intent; nothing here acts, fights, changes '
          'a node, or scripts what a person will do next.')


def enabled():
    return os.environ.get(ENV_SWITCH, '1') != '0'


def attach(world):
    """The one call the generator makes. Never raises; a failure is a reported block."""
    if not enabled():
        return None
    try:
        return generate(world)
    except Exception as exc:  # noqa: BLE001 - the whole point is to report, not to crash the world
        return {'version': VERSION, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}


def generate(world, policies=None):
    """The cast for a finished world. `policies` overrides the packaged policy documents (tests, explorers)."""
    _validate(world)
    seed = world_seed(world)
    policies = policies or load_all()
    wells = policies['wells']
    cards = policies['archetypes']['cards']
    overlays = policies['axis_overlays']
    realms = build_realms(world)
    by_realm = realm_by_city(realms)
    people, dreads, rolls = ruins_well.candidates(world, by_realm, seed, wells)
    for found, found_rolls in (magic_well.candidates(world, by_realm, seed, wells),):
        people += found
        rolls += found_rolls
    city_people, city_rolls, orgs = cities_well.candidates(world, realms, by_realm, seed, wells)
    guild_people, guild_rolls, guild_orgs = guilds_well.candidates(world, by_realm, seed, wells, radius(world))
    people += city_people + guild_people
    rolls += city_rolls + guild_rolls
    orgs += guild_orgs
    for well in (countryside_well, ports_well, shrines_well):
        found, found_rolls = well.candidates(world, by_realm, seed, wells)
        people += found
        rolls += found_rolls
    camp_list, camp_rolls = build_camps(world, seed, wells)
    rolls += camp_rolls
    place(world, people, camp_list, seed, wells)
    camps_by_uid = {c['uid']: c for c in camp_list}
    cities_by_uid = {c['uid']: c for c in cities(world)}
    realms_by_uid = {r['uid']: r for r in realms}
    nests_by_id = {n['id']: n for n in nests(world)}
    ruins_by_uid = {r['uid']: r for r in ruins(world)}
    people.sort(key=lambda p: (p['born_age'], p['uid']))
    for person in people:
        person['fame'] = fame_rules.fame(fame_rules.person_magnitude(person),
                                         fame_rules.person_reach(person, cities_by_uid, realms_by_uid))
        person['tier'] = fame_rules.tier(person['fame'])
        _fame_features(person)
        person['anchor_direction'] = _anchor(person, cities_by_uid, ruins_by_uid, camps_by_uid)
    _predecessors(people)
    feature_rules.apply(world, people, wells)
    seated = [p for p in people if p['role'] in feature_rules.SEATED]
    for person in seated:
        _finish_person(world, person, policies, cards, overlays, seed, ruins_by_uid, camps_by_uid)
    feature_rules.mark_rebels(people, feature_rules.tyrant_realms(seated))
    for person in people:
        if person.get('archetype') is None:
            _finish_person(world, person, policies, cards, overlays, seed, ruins_by_uid, camps_by_uid)
    for dread in dreads:
        dread['fame'] = fame_rules.fame(fame_rules.dread_magnitude(dread), fame_rules.dread_reach(dread, nests_by_id))
        dread['tier'] = fame_rules.tier(dread['fame'])
        _fame_features(dread)
        _finish_dread(dread, policies, cards, overlays, seed)
    relic_list = build_relics(world)
    hooks = quest_hooks(world, people, {r['resting_at']: r for r in relic_list}, wells)
    for person in people:
        person.pop('anchor_direction', None)
        person.pop('dispossessed', None)
    edges = bonds(people, dreads)
    for person in people:
        mine = [e for e in edges if person['uid'] in (e['a'], e['b'])]
        other = lambda e: e['b'] if e['a'] == person['uid'] else e['a']
        person['rivals'] = sorted({other(e) for e in mine if e['kind'] in ('rival', 'betrayed')})
        person['kin'] = sorted({other(e) for e in mine if e['kind'] == 'kin'})
        person['allies'] = sorted({other(e) for e in mine if e['kind'] in ('ally', 'mentor')})
    orgs = [o for o in orgs if o['members']]
    return {'version': VERSION, 'status': 'ok', 'policy_revision': revisions(policies), 'final_age': final_age(world),
            'summary': {'living': sum(p['status'] == 'living' for p in people),
                        'legends': sum(p['status'] == 'legend' for p in people),
                        'dreads': len(dreads), 'realms': len(realms), 'orgs': len(orgs), 'camps': len(camp_list),
                        'hooks': len(hooks), 'candidates': len(rolls), 'precipitated': sum(r['precipitated'] for r in rolls)},
            'people': people, 'orgs': orgs, 'realms': realms, 'dreads': dreads, 'camps': camp_list, 'quest_hooks': hooks,
            'bonds': edges, 'relics': relic_list, 'mantles': mantles(people), 'rolls': rolls, 'method': METHOD, 'limits': LIMITS}


def _validate(world):
    if not isinstance(world, dict) or type(world.get('config', {}).get('seed')) is not int:
        raise ValueError('hero generation needs a finished world with an integer config.seed')
    if not isinstance(world.get('history', {}).get('ages'), list):
        raise ValueError('hero generation needs history.ages; generate a recipe-3 world to phase 16')
    for key in ('ruins', 'settlements', 'civilizations', 'humans', 'beast_nests'):
        if key not in world:
            raise ValueError(f'hero generation needs the {key} block')


def _anchor(person, cities_by_uid, ruins_by_uid, camps_by_uid):
    """Where the person stands, as a globe direction, for nearest-node lookups."""
    presence = person.get('presence') or {}
    source = {'city': cities_by_uid, 'ruin': ruins_by_uid, 'camp': camps_by_uid}.get(presence.get('site_kind'), {}).get(presence.get('uid'))
    if source is None and person.get('lost'):
        source = ruins_by_uid.get(person['lost']['uid'])
    if source is None and person.get('home'):
        source = cities_by_uid.get(person['home']['uid'])
    return list(source['direction']) if source else None


def _fame_features(record):
    if record['tier'] in ('renowned', 'legendary'):
        record['features'].add('fame:renowned')
    if record['tier'] == 'legendary':
        record['features'].add('fame:legendary')


def _predecessors(people):
    """A living heir inherits when a legend of their own people left the same kind of claim open."""
    legends = [p for p in people if p['status'] == 'legend' and p['claim']['verb'] == 'retake']
    for person in people:
        if person['status'] != 'living':
            continue
        earlier = [l for l in legends if l['civilization_id'] == person['civilization_id'] and l['born_age'] < person['born_age']]
        if earlier:
            person['features'].add('legend:predecessor')
            person['predecessor_uid'] = min(earlier, key=lambda l: (-l['fame'], l['uid']))['uid']


def _finish_person(world, person, policies, cards, overlays, seed, ruins_by_uid, camps_by_uid):
    draw = rng(seed, 'hero-archetype-' + person['uid'])
    alignment = derive_person(person, policies['alignment'], seed)
    card = archetype_rules.choose(cards, person['features'], alignment, draw)
    if card is None:
        raise ValueError(f'no archetype precondition holds for {person["uid"]}: {sorted(person["features"])}')
    alignment = intensify(alignment, card['intensity'], draw)
    alignment['drift'] = card['drift']
    name, epithet = person_name(policies['names'], person, seed)
    person.update({'name': name, 'epithet': epithet, 'display_name': f'{name} {epithet}', 'archetype': card['id'],
                   'archetype_name': card['name'], 'alignment': alignment})
    faces = build_faces(card, person, alignment, overlays, policies['names'], seed)
    situation = (person.get('presence') or {}).get('situation')
    person.update({'persona': next(f['persona'] for f in faces if f['label'] not in ('public', 'unleashed', 'second') or len(faces) == 1),
                   'faces': faces, 'log': person_log(world, person, ruins_by_uid),
                   'situation': person_situation(world, person, camps_by_uid),
                   'companion': {'eligible': person['status'] == 'living' and situation in COMPANION_JOIN,
                                 'join_condition': COMPANION_JOIN.get(situation) if person['status'] == 'living' else None,
                                 'offered_from_face': faces[0]['label'] if situation in COMPANION_JOIN else None},
                   'org_uid': None, 'seed': rng(seed, 'hero-seed-' + person['uid']).getrandbits(32)})
    for key in ('predecessor_uid', 'school', 'node_id', 'seat', 'nest_id', 'site_name'):
        person.setdefault(key, None)
    person['selectable'] = sorted(person.pop('features'))


def _finish_dread(dread, policies, cards, overlays, seed):
    draw = rng(seed, 'hero-archetype-' + dread['uid'])
    alignment = derive_dread(dread, policies['alignment'], seed)
    card = archetype_rules.choose(cards, dread['features'], alignment, draw)
    if card is not None:
        alignment = intensify(alignment, card['intensity'], draw)
        alignment['drift'] = card['drift']
    epithet = dread_name(policies['names'], dread, seed)
    dread.update({'name': epithet, 'display_name': f"{dread['species']}, {epithet}",
                  'archetype': card['id'] if card else None,
                  'archetype_name': card['name'] if card else None, 'alignment': alignment,
                  'persona': compose(card, overlays, alignment) if card else None,
                  'log': dread_log(dread), 'situation': dread_situation(dread),
                  'seed': rng(seed, 'hero-seed-' + dread['uid']).getrandbits(32)})
    dread['selectable'] = sorted(dread.pop('features'))


def summary_lines(block):
    """Short human lines for logs and the lab status: one per living person, plus counts."""
    if block.get('status') != 'ok':
        return [f"heroes failed: {block.get('error')}"]
    s = block['summary']
    lines = [f"{s['precipitated']} of {s['candidates']} candidates precipitated · {s['living']} living · {s['legends']} legends · "
             f"{s['dreads']} dreads · {s['orgs']} orgs · {s['camps']} camps · {s['hooks']} hooks · {s['realms']} realms"]
    for person in block['people']:
        if person['status'] == 'living':
            where = person['home']['name'] if person.get('home') else person['presence']['uid']
            lines.append(f"{person['display_name']} — {person['archetype_name']}, {person['alignment']['label']}, at {where}")
    return lines
