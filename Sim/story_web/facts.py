"""Facts: the plain, typed truths a trope precondition can test about a person and their world.

A fact is `namespace:value`. Person facts come from the exported hero record (its
selection features, role, status, claim verb, bond kinds, tier, archetype, presence,
faces). World facts come from the exported world (war pressure and threat on the home
city, food deficit at its rural core, lunar surges, node intensity at a held key point) and
from the rest of the cast (living rivals, open mantles, resting relics, squatted ruins,
a tyrant on the realm's seat). Nothing here is rolled and nothing is written back.
"""

# The selection features the hero generator can export (mirrors hero_generator.archetypes.FEATURES;
# copied rather than imported so this package reads only the block).
HERO_FEATURES = frozenset({
    'role:pretender', 'role:warlord', 'role:dread', 'role:champion', 'role:sovereign', 'role:magister',
    'role:domain_holder', 'role:schemer', 'role:council', 'role:prophet', 'role:heresiarch', 'role:exile',
    'role:founder', 'role:camp_leader',
    'role:reeve', 'role:castellan', 'role:harbourmaster', 'role:keeper',
    'hamlet:farming', 'hamlet:resource', 'hamlet:starving', 'hamlet:threatened', 'fortress:pressed', 'port:terminal',
    'shrine:ruin', 'shrine:cult',
    'home:fell', 'stake:lost', 'heir:small', 'heir:medium', 'heir:capital', 'sides:both', 'civ:lost_many',
    'dread:living', 'realm:contested', 'war:civil_victor', 'war:regional_victor', 'war:international_victor',
    'home:fell_later', 'dread:long_lived', 'dread:ages_2', 'legend:predecessor',
    'seat:magistrate', 'seat:commander', 'seat:chaplain', 'seat:market_steward', 'seat:mage', 'seat:librarian',
    'dynasty:founding', 'sovereign:advised',
    'seat:college', 'college:destroyed', 'keypoint:ruin_born', 'school:dark', 'stake:none', 'seat:none',
    'fame:renowned', 'fame:legendary',
    'dread:person_shaped', 'order:member', 'order:remnant', 'order:against_dark',
    # `villain:prior_age` has nothing to do with `icarus_sim.terrain_villains`. That module owns
    # the word in the world model -- a field with a continuous tier, a reach in metres, a seat and
    # held ley nodes, published in the `villains` block under its own schema. This is a fact about
    # an ordinary person: a pretender whose people founded a city again after they were born.
    # `weights.json` additionally lists it as gainable, so a runtime can add it to somebody, which
    # a super villain's tier is not. Reading it as evidence that a super villain stood here in a
    # prior age is the wrong join; `villains.fallen` answers that and this does not.
    'deed:credited_not_actual', 'deed:dark_nest', 'villain:prior_age', 'stake:regained',
    'ley:tainted_home', 'rival:spared', 'realm:cold_conflicts_2', 'realm:tyrant', 'stakes:2', 'seat:trade',
    'routes:2', 'mentor:successor', 'heir:unclaimed', 'council:outranks_sovereign',
    'dread:failed_against', 'defence:failed', 'warden:post', 'ally:lost', 'deeds:two_civilizations', 'deeds:two_schools',
})

CLAIM_VERBS = ('hold', 'retake', 'avenge', 'exploit', 'convert', 'protect', 'unify', 'kill', 'expose', 'overthrow', 'none')
BOND_KINDS = ('rival', 'ally', 'kin', 'mentor', 'debt', 'betrayed')
TIERS = ('notable', 'renowned', 'legendary')
SITUATIONS = ('court', 'command', 'council', 'throne', 'guildhall', 'pulpit', 'hall', 'lair', 'leader', 'refugee',
              'teaching', 'warding', 'captive', 'hidden', 'reeve', 'garrison', 'quay', 'altar', 'cult')
WORLD_FACTS = frozenset({
    'world:war_pressure', 'world:war_recent', 'world:enemy_living', 'world:war_risk', 'world:war_hunger', 'world:famine',
    'world:threatened', 'world:food_deficit', 'world:surge', 'world:hollow_night',
    'world:node_intense', 'world:rival_living', 'world:rival_dread', 'world:relic_resting', 'world:camp_at_lost',
    'world:mantle_open', 'world:other_realm', 'world:dread_living', 'world:realm_has_sovereign', 'world:realm_tyrant',
})
DERIVED_FACTS = frozenset(
    {'status:living', 'status:legend', 'home:set', 'home:none', 'lost:set', 'faces:two', 'companion:eligible',
     'war:veteran', 'war:victor_recent', 'war:defeated_recent'}
    | {'claim:' + v for v in CLAIM_VERBS} | {'bond:' + k for k in BOND_KINDS} | {'tier:' + t for t in TIERS}
    | {'presence:' + s for s in SITUATIONS}
)
FACTS = HERO_FEATURES | WORLD_FACTS | DERIVED_FACTS


def known_fact(token):
    """A precondition token is known when it is a listed fact or an archetype reference."""
    return token in FACTS or (token.startswith('archetype:') and len(token) > len('archetype:'))


def _rows(value):
    """The dict rows of a list-valued export field; anything else reads as empty."""
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _number(value):
    try:
        return float(value or 0.)
    except (TypeError, ValueError):
        return 0.


class WorldFacts:
    """World-side lookups computed once per compile, then asked per hero."""

    def __init__(self, world, heroes, weights):
        # Every read below skips a malformed row rather than failing the block: a bad row costs one fact.
        sites = _rows((world.get('settlements') or {}).get('sites'))
        self.uid_by_site_id = {s['id']: s['uid'] for s in sites if 'id' in s and 'uid' in s}
        self.threat = {c['city_uid']: c for c in _rows((world.get('threat_assessments') or {}).get('cities')) if 'city_uid' in c}
        self.deficit = {}
        for core in _rows((world.get('humans') or {}).get('cores')):
            uid = self.uid_by_site_id.get(core.get('site_id'))
            if uid is not None:
                self.deficit[uid] = _number(core.get('food_deficit'))
        # A famine is a year the city cannot feed itself, read from the seasonal food model, not the
        # structural deficit diagnostic (which marks nearly every city that lacks farms).
        self.famine_threshold = weights.get('famine_coverage', .5)
        self.coverage = {}
        for row in _rows((world.get('seasonal_food') or {}).get('cities')):
            uid = self.uid_by_site_id.get(row.get('site_id'))
            if uid is not None:
                self.coverage[uid] = _number(row.get('food_coverage'))
        events = _rows((world.get('lunar_almanac') or {}).get('events'))
        self.surge = any(e.get('kind') == 'surge' for e in events)
        self.hollow = any(e.get('kind') == 'hollow_night' for e in events)
        self.node_intensity = {}
        networks = (world.get('magic') or {}).get('networks')
        for net in (networks.values() if isinstance(networks, dict) else []):
            for node in _rows((net or {}).get('nodes') if isinstance(net, dict) else None):
                if 'id' in node:
                    self.node_intensity[node['id']] = _number(node.get('intensity'))
        self.node_threshold = weights['node_intense_threshold']
        people = _rows(heroes.get('people'))
        dreads = _rows(heroes.get('dreads'))
        self.living = {p['uid'] for p in people + dreads if p.get('status') == 'living' and 'uid' in p}
        self.dread_uids = {d['uid'] for d in dreads if 'uid' in d}
        self.dread_living = any(d.get('status') == 'living' for d in dreads)
        self.resting_relics = {r['resting_at'] for r in _rows(heroes.get('relics')) if r.get('holder_uid') is None and 'resting_at' in r}
        self.camp_ruins = {c['ruin_uid'] for c in _rows(heroes.get('camps')) if 'ruin_uid' in c}
        self.mantles = {}
        for m in _rows(heroes.get('mantles')):
            if 'civilization_id' in m and 'predecessor_uid' in m:
                self.mantles.setdefault(m['civilization_id'], set()).add(m['predecessor_uid'])
        self.realm_count = len(_rows(heroes.get('realms')))
        self.sovereign_civs = {p.get('civilization_id') for p in people if p.get('status') == 'living' and p.get('role') == 'sovereign'}
        self.tyrant_civs = {p.get('civilization_id') for p in people
                            if p.get('status') == 'living' and p.get('role') in ('sovereign', 'warlord') and p.get('archetype') == 'tyrant'}

    def for_hero(self, hero):
        facts = set()
        home = (hero.get('home') or {}).get('uid')
        if home is not None:
            report = self.threat.get(home) or {}
            if _number(report.get('war_pressure')) > 0.:
                facts.add('world:war_pressure')
            if _number(report.get('wars_recent')) > 0:
                facts.add('world:war_recent')
            if report.get('enemy_living'):
                facts.add('world:enemy_living')
            if _number(report.get('war_risk')) > 0.:
                facts.add('world:war_risk')
            if _number(report.get('war_hunger')) > 0.:
                facts.add('world:war_hunger')
            if _number(report.get('regional_threat')) >= .5:
                facts.add('world:threatened')
            if self.deficit.get(home, 0.) > 0.:
                facts.add('world:food_deficit')
            if home in self.coverage and self.coverage[home] < self.famine_threshold:
                facts.add('world:famine')
        if self.surge:
            facts.add('world:surge')
        if self.hollow:
            facts.add('world:hollow_night')
        node = hero.get('node_id')
        if node and self.node_intensity.get(node, 0.) >= self.node_threshold:
            facts.add('world:node_intense')
        rivals = set(hero.get('rivals') or [])
        if rivals & self.living:
            facts.add('world:rival_living')
        if rivals & self.dread_uids & self.living:
            facts.add('world:rival_dread')
        lost = (hero.get('lost') or {}).get('uid')
        if lost is not None:
            if lost in self.resting_relics:
                facts.add('world:relic_resting')
            if lost in self.camp_ruins:
                facts.add('world:camp_at_lost')
        civ = hero.get('civilization_id')
        if self.mantles.get(civ, set()) - {hero['uid']}:
            facts.add('world:mantle_open')
        if self.realm_count >= 2:
            facts.add('world:other_realm')
        if self.dread_living:
            facts.add('world:dread_living')
        if civ in self.sovereign_civs:
            facts.add('world:realm_has_sovereign')
        if civ in self.tyrant_civs:
            facts.add('world:realm_tyrant')
        return facts


def person_facts(hero, bonds, final_age=None):
    """Facts read from one exported person or dread, without the world."""
    facts = set(hero.get('selectable') or [])
    for deed in _rows(hero.get('deeds')):
        if deed.get('event_kind') != 'war':
            continue
        facts.add('war:veteran')
        if final_age is not None and deed.get('age') == final_age:
            facts.add('war:victor_recent' if deed.get('role') == 'credited' else 'war:defeated_recent')
    facts.add('role:' + hero['role'])
    facts.add('status:' + hero['status'])
    if hero.get('tier') in TIERS:
        facts.add('tier:' + hero['tier'])
    if hero.get('archetype'):
        facts.add('archetype:' + hero['archetype'])
    claim = hero.get('claim') or {}
    facts.add('claim:' + (claim.get('verb') or 'none'))
    for edge in _rows(bonds):
        if hero['uid'] in (edge.get('a'), edge.get('b')) and edge.get('kind') in BOND_KINDS:
            facts.add('bond:' + edge['kind'])
    facts.add('home:set' if hero.get('home') else 'home:none')
    if hero.get('lost'):
        facts.add('lost:set')
    situation = (hero.get('presence') or {}).get('situation')
    if situation in SITUATIONS:
        facts.add('presence:' + situation)
    if len(hero.get('faces') or []) > 1:
        facts.add('faces:two')
    if (hero.get('companion') or {}).get('eligible'):
        facts.add('companion:eligible')
    return facts
