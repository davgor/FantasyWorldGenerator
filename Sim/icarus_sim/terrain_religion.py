"""Pantheon: gods that may exist, a cosmology the world chooses, faiths the peoples keep.

Everything here is narrative provenance resolved deterministically from world state.
A god is manifest, sleeping or absent; it changes nothing in the world unless the
orchestrator summons it through terrain_visitation. The catalogue ships as data
(pantheon.json, decision 020); this module only interprets it.
"""
import copy
import hashlib
import json
import random
from pathlib import Path
from .terrain_tectonics import child_seed
from .terrain_leyline_history import KNOWN_SCHOOLS
from .civilization_registry import entity_rules
from .terrain_profiles import civilization_ids

VERSION = 1
PRIMORDIAL = ('fire', 'water', 'earth', 'air')
SURGE_BIRTH = 1.3
_CATALOGUE = None


def catalogue():
    global _CATALOGUE
    if _CATALOGUE is None:
        _CATALOGUE = json.loads((Path(__file__).with_name('pantheon.json')).read_text(encoding='utf-8'))
    return _CATALOGUE


_HIDDEN = None


def hidden_catalogue():
    """The four the known pantheon does not speak of.

    Their own file, with its own identity, so catalogue_identity() never moves: hashing
    them into pantheon.json would retire every saved world each time one was touched.
    """
    global _HIDDEN
    if _HIDDEN is None:
        _HIDDEN = json.loads((Path(__file__).with_name('hidden_pantheon.json')).read_text(encoding='utf-8'))
    return _HIDDEN


def hidden_gods_by_id():
    return {god['id']: god for god in hidden_catalogue()['gods']}


def hidden_records(previous=None):
    """Hidden gods as exported: absent until something reveals one.

    Exported rather than withheld on purpose. Nothing in a generated world points at them,
    no faith names one and no rule can raise one; keeping them out of sight is the game's
    job, not the generator's.
    """
    prior = {g['id']: g for g in (previous or {}).get('gods', []) if g.get('family') == 'outside'}
    out = []
    for god in hidden_catalogue()['gods']:
        was = prior.get(god['id'], {})
        status = was.get('status', 'absent')
        out.append({'id': god['id'], 'name': god['name'], 'family': 'outside', 'status': status,
                    'aspect': was.get('aspect'), 'aspect_name': was.get('aspect_name'),
                    'domains': list(god['domains']), 'schools': [god['school']],
                    'rule': dict(god['exists']), 'evidence': was.get('evidence'), 'saint_of': None})
    return out


def catalogue_identity():
    doc = catalogue()
    canonical = json.dumps(doc, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    return {'schema_version': doc['schema_version'], 'revision': doc['revision'], 'sha256': hashlib.sha256(canonical).hexdigest()}


def gods_by_id():
    return {god['id']: god for god in catalogue()['gods']}


def lint_catalogue():
    """Raise on a catalogue that could not be resolved; used by tests and the identity pin."""
    doc = catalogue()
    ids = [god['id'] for god in doc['gods']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate god id')
    known = set(ids)
    schools = {god['exists']['school'] for god in doc['gods'] if god['family'] == 'school'}
    if schools != set(KNOWN_SCHOOLS):
        raise ValueError('School gods must cover every school exactly once')
    for god in doc['gods']:
        _check_rule(god['exists'])
        for key in ('allies', 'rivals'):
            if set(god.get(key, [])) - known:
                raise ValueError(f'{god["id"]} names an unknown god in {key}')
        if 'folds_into' in god and god['folds_into'] not in known:
            raise ValueError(f'{god["id"]} folds into an unknown god')
        if not god.get('school_affinity') or any(s not in KNOWN_SCHOOLS and s != 'moon' for s in god['school_affinity']):
            raise ValueError(f'{god["id"]} needs school affinities')
        if 'sovereign' not in god['aspects']:
            raise ValueError(f'{god["id"]} needs a sovereign aspect')
    for cosmology in doc['cosmologies']:
        _check_rule(cosmology['requires'])
        if set(cosmology.get('high', [])) - known:
            raise ValueError(f'{cosmology["id"]} names an unknown high god')
    if set(doc['affinities']) != set(civilization_ids()):
        raise ValueError('Affinities must cover every civilization')
    for civilization, table in doc['affinities'].items():
        for key in ('strong', 'mild', 'aversion'):
            if set(table.get(key, [])) - known:
                raise ValueError(f'{civilization} affinity names an unknown god')
    if set(doc['fear_gods'].values()) - known or set(doc['wild_push_families']) - known:
        raise ValueError('Fear or aspect tables name an unknown god')
    return True


RULE_KINDS = {'always', 'magic_enabled', 'magic_disabled', 'school', 'race', 'civilization_city', 'ocean_share',
              'sky', 'dragon', 'nest_family', 'ruins', 'diaspora', 'any', 'all', 'primordial_count', 'gods', 'races'}


def _check_rule(rule):
    if rule['kind'] not in RULE_KINDS:
        raise ValueError('Unknown existence rule ' + rule['kind'])
    for inner in rule.get('rules', []):
        _check_rule(inner)


def world_facts(world, cfg=None):
    """The inputs existence rules read, taken from what the generator already exports."""
    magic = world.get('magic', {})
    networks = magic.get('networks', {})
    schools = {school: bool(networks.get(school, {}).get('nodes')) for school in KNOWN_SCHOOLS}
    settlements = world.get('settlements', {})
    sites = settlements.get('sites', [])
    founding = settlements.get('founding', {}) or {}
    ruins = world.get('ruins', [])
    ids = set(civilization_ids())
    ever = set(founding.get('used_civilizations', [])) | {s['population_profile'] for s in sites} | \
        {r['population_profile'] for r in ruins if r.get('population_profile') in ids}
    races = sorted({entity_rules(c)['parent_race_id'] for c in ever if c in ids})
    water = world.get('water', {})
    ocean = water.get('ocean_km2', 0.)
    total = ocean + water.get('lake_km2', 0.) + water.get('dry_km2', 0.)
    fantasy = [n for n in world.get('beast_nests', {}).get('sites', []) if not n.get('real', True)]
    families = sorted({n.get('family') for n in fantasy if n.get('family')})
    dragons = sum(1 for n in fantasy if n.get('family') == 'draconic' or 'dragon' in n.get('name', '').lower())
    diaspora = sum(1 for s in sites if s.get('diaspora')) + \
        sum(1 for e in founding.get('events', []) if e.get('status') == 'diaspora_founded')
    wars = sum(len(age.get('wars', [])) for age in world.get('history', {}).get('ages', []))
    if cfg is not None:
        from .terrain_world import options
        lunar = options(cfg)['lunar_influence']
    else:
        lunar = world.get('recipe', {}).get('resolved', {}).get('lunar_influence', 0.)
    return {'schools': schools, 'primordial_count': sum(schools[s] for s in PRIMORDIAL),
            'races': races, 'civilizations_with_cities': sorted({s['population_profile'] for s in sites}),
            'ocean_share': ocean / total if total else 0., 'sky': len(world.get('sky', {}).get('settlements', [])),
            'families': families, 'dragons': dragons, 'ruins': len(ruins), 'diaspora': diaspora, 'wars': wars,
            'magic_enabled': bool(magic.get('enabled', any(schools.values()))), 'lunar_influence': lunar}


def rule_holds(rule, facts, manifest=frozenset()):
    kind = rule['kind']
    if kind == 'always':
        return True
    if kind == 'magic_enabled':
        return facts['magic_enabled']
    if kind == 'magic_disabled':
        return not facts['magic_enabled']
    if kind == 'school':
        return facts['schools'][rule['school']]
    if kind == 'race':
        return rule['race'] in facts['races']
    if kind == 'races':
        return len(facts['races']) >= rule['min']
    if kind == 'civilization_city':
        return any(c in facts['civilizations_with_cities'] for c in rule['ids'])
    if kind == 'ocean_share':
        return facts['ocean_share'] >= rule['min']
    if kind == 'sky':
        return facts['sky'] > 0
    if kind == 'dragon':
        return facts['dragons'] > 0
    if kind == 'nest_family':
        return any(f in facts['families'] for f in rule['families'])
    if kind == 'ruins':
        return facts['ruins'] >= rule['min']
    if kind == 'diaspora':
        return facts['diaspora'] > 0
    if kind == 'primordial_count':
        return facts['primordial_count'] >= rule['min']
    if kind == 'gods':
        ids = rule['ids']
        return all(i in manifest for i in ids) if rule.get('all', True) else any(i in manifest for i in ids)
    if kind == 'any':
        return any(rule_holds(r, facts, manifest) for r in rule['rules'])
    if kind == 'all':
        return all(rule_holds(r, facts, manifest) for r in rule['rules'])
    raise ValueError('Unknown existence rule ' + kind)


def aspect_of(god, world, facts):
    """Sovereign below the intensity/instability midpoint, Wild above; the moon follows its lean."""
    doc = catalogue()
    if 'wild' not in god['aspects']:
        return 'sovereign', {}
    if god['family'] == 'school':
        net = world.get('magic', {}).get('networks', {}).get(god['exists']['school'], {})
        items = net.get('nodes', []) + net.get('edges', [])
        mean = sum(i['intensity'] for i in items) / len(items) if items else 0.
        score = mean * (1 + net.get('instability', 0.))
        push = doc['nest_aspect_push'] if any(f in facts['families'] for f in doc['wild_push_families'].get(god['id'], [])) else 0.
        evidence = {'mean_intensity': mean, 'instability': net.get('instability', 0.), 'nest_push': push,
                    'midpoint': doc['aspect_midpoint']}
        return ('wild' if score + push > doc['aspect_midpoint'] else 'sovereign'), evidence
    if god['id'] == 'god_turning_moon':
        months = world.get('lunar_almanac', {}).get('months', [])
        lean = sum(m['nod_degrees'] for m in months) / len(months) if months else 0.
        return ('sovereign' if lean >= 0 else 'wild'), {'mean_nod_degrees': lean,
                                                        'leaning': 'still' if lean >= 0 else 'restless'}
    return 'sovereign', {}


def resolve_gods(world, facts, previous=None):
    before = {g['id']: g for g in (previous or {}).get('gods', [])}
    gods = []
    for god in catalogue()['gods']:
        holds = rule_holds(god['exists'], facts)
        prior = before.get(god['id'])
        if prior and prior['status'] == 'walking':
            status = 'walking'
        elif holds:
            status = 'manifest'
        elif prior and prior['status'] in ('manifest', 'sleeping', 'walking'):
            status = 'sleeping'
        else:
            status = 'absent'
        if status in ('manifest', 'walking'):
            aspect, evidence = aspect_of(god, world, facts)
        elif status == 'sleeping':
            aspect, evidence = prior['aspect'], {'last_seen': prior.get('evidence', {})}
        else:
            aspect, evidence = None, {}
        record = {'id': god['id'], 'name': god['name'], 'family': god['family'], 'status': status,
                  'aspect': aspect, 'aspect_name': god['aspects'].get(aspect) if aspect else None,
                  'domains': list(god['domains']), 'schools': list(god['school_affinity']),
                  'rule': god['exists'], 'evidence': evidence}
        if prior and prior['status'] == 'walking' and prior.get('avatar'):
            record['avatar'] = copy.deepcopy(prior['avatar'])
        gods.append(record)
    return gods


def _draw(rng, weighted):
    """One seeded pick from (item, weight) pairs with positive weights, in list order."""
    total = sum(w for _, w in weighted)
    target = rng.random() * total
    for item, weight in weighted:
        target -= weight
        if target <= 0:
            return item
    return weighted[-1][0]


def choose_cosmology(facts, manifest, seed):
    doc = catalogue()
    eligible = []
    for cosmology in doc['cosmologies']:
        if not rule_holds(cosmology['requires'], facts, manifest):
            continue
        spec = cosmology['weight']
        value = facts.get(spec.get('fact', ''), 0.)
        if isinstance(value, (list, tuple, set)):
            value = len(value)
        weight = spec.get('base', 0.) + spec.get('per', 0.) * value
        if weight > 0:
            eligible.append((cosmology, weight))
    if not eligible:
        eligible = [(next(c for c in doc['cosmologies'] if c['id'] == 'cos_mosaic'), 1.)]
    rng = random.Random(child_seed(seed, 'pantheon-v1'))
    chosen = _draw(rng, eligible)
    return {'id': chosen['id'], 'name': chosen['name'], 'high': [g for g in chosen.get('high', []) if g in manifest],
            'arrangement': chosen['arrangement'],
            'eligible': [{'id': c['id'], 'weight': w} for c, w in eligible]}


def mean_potency(world, cities):
    layers = world.get('layers', {})
    result = {}
    for school in KNOWN_SCHOOLS:
        grid = layers.get('ley_' + school)
        values = [grid[c['z']][c['x']] for c in cities] if grid else []
        result[school] = sum(values) / len(values) if values else 0.
    return result


def choose_faiths(world, facts, gods, cosmology, seed, conversions=None):
    doc = catalogue()
    conversions = conversions or {}
    weights = doc['affinity_weights']
    by_id = {g['id']: g for g in gods}
    manifest = [g for g in gods if g['status'] in ('manifest', 'walking')]
    sites = world.get('settlements', {}).get('sites', [])
    nests = world.get('beast_nests', {}).get('sites', [])
    radius = world.get('effective_config', {}).get('globe_radius', 1.)
    founding = world.get('settlements', {}).get('founding', {}) or {}
    almanac = world.get('lunar_almanac', {})
    faiths = {}
    for civilization in facts['civilizations_with_cities']:
        cities = [s for s in sites if s['population_profile'] == civilization]
        race = entity_rules(civilization)['parent_race_id']
        potency = mean_potency(world, cities)
        table = doc['affinities'].get(civilization, {})
        ancestor = next((g for g in manifest if g['family'] == 'ancestor' and by_id[g['id']] and
                         gods_by_id()[g['id']].get('race') == race), None)
        rng = random.Random(child_seed(seed, 'faith-v1-' + civilization))
        weighted = []
        for god in manifest:
            if ancestor and god['id'] == ancestor['id']:
                continue
            weight = 0.
            for key in ('strong', 'mild', 'aversion'):
                if god['id'] in table.get(key, []):
                    weight += weights[key]
            if god['id'] in cosmology['high']:
                weight += weights['high']
            if god['family'] == 'civic':
                weight += weights['civic_base']
            weight += sum(potency.get(s, 0.) for s in god['schools'] if s in potency)
            if weight > 0:
                weighted.append((god['id'], weight))
        patron = ancestor['id'] if ancestor else (_draw(rng, weighted) if weighted else None)
        conversion = conversions.get(civilization)
        if conversion and by_id.get(conversion['god_id'], {}).get('status') in ('manifest', 'walking'):
            # A god that walked among this people is its patron until it stops existing.
            if ancestor and ancestor['id'] != conversion['god_id']:
                weighted.append((ancestor['id'], weights['strong']))
            patron = conversion['god_id']
        chosen = [patron] if patron else []
        pool = [(g, w) for g, w in weighted if g != patron]
        while pool and len(chosen) < 4:
            pick = _draw(rng, pool)
            chosen.append(pick)
            pool = [(g, w) for g, w in pool if g != pick]
        names = {}
        for god_id in chosen:
            record = gods_by_id()[god_id]
            names[god_id] = record.get('epithets', {}).get(civilization) or by_id[god_id]['aspect_name'] or record['name']
        fear = []
        from .terrain_history import fantasy_nest_threats
        for city in cities:
            for threat in fantasy_nest_threats(city, nests, radius):
                god_id = doc['fear_gods'].get(threat.get('family')) or (doc['fear_gods']['draconic'] if threat['kind'] == 'dragon' else None)
                if god_id and by_id.get(god_id, {}).get('status') in ('manifest', 'walking') and \
                        not any(f['god_id'] == god_id and f['city_uid'] == city.get('uid') for f in fear):
                    fear.append({'god_id': god_id, 'city_uid': city.get('uid'), 'nest_id': threat['nest_id'], 'mode': 'fear'})
        sects = []
        if patron:
            rivals = [r for r in gods_by_id()[patron].get('rivals', []) if r in by_id and by_id[r]['status'] in ('manifest', 'walking')]
            rival = rivals[0] if rivals else (chosen[1] if len(chosen) > 1 else None)
            for event in founding.get('events', []):
                if event.get('status') == 'diaspora_founded' and event.get('diaspora_reason') == 'religious_schism' \
                        and event.get('population_profile') == civilization and rival:
                    sects.append({'node': event['node'], 'founding_year': event.get('founding_year'), 'patron': rival,
                                  'rival': patron, 'epithet': names.get(rival, by_id[rival]['name']) + ' of the Schism'})
        faiths[civilization] = {'parent_race_id': race, 'patron': patron, 'gods': chosen, 'names': names,
                               'conversion': conversion,
                               'fear': sorted(fear, key=lambda f: (f['city_uid'] or '', f['god_id'])),
                               'sects': sects, 'feasts': feasts(chosen, by_id, almanac),
                               'weights': {g: round(w, 6) for g, w in weighted}}
    return faiths


def feasts(chosen, by_id, almanac):
    events = almanac.get('events', [])
    surges = {}
    for god_id in chosen:
        god = gods_by_id()[god_id]
        if god['family'] == 'school':
            school = god['exists']['school']
            days = [e['day'] for e in events if e['kind'] == 'surge' and e['school'] == school]
            if days:
                surges[god_id] = days
    full = [e['day'] for e in events if e['kind'] == 'full_moon'] if 'god_turning_moon' in chosen else []
    hollow = [e['day'] for e in events if e['kind'] == 'hollow_night']
    vigil = any(by_id[g]['aspect'] == 'wild' and g in ('god_umbral', 'god_infernal') for g in chosen[:1])
    return {'surges': surges, 'full_moons': full, 'hollow_nights': {'days': hollow, 'kept_as': 'vigil' if vigil else 'dread'}}


def resolve_sites(world, gods, previous=None):
    by_id = {g['id']: g for g in gods}
    ages = world.get('history', {}).get('ages', [])
    sites = []
    for ruin in world.get('ruins', []):
        cause = ruin.get('cause', '')
        if cause == 'self_magic' and by_id.get('god_weave', {}).get('status') != 'absent':
            age = next((a for a in ages if a['age'] == ruin.get('destroyed_age')), None)
            surge = age.get('moon', {}).get('tide', {}).get('weave') if age else None
            sites.append({'id': 'cult-' + ruin['id'], 'kind': 'cult', 'god_id': 'god_weave', 'ruin_id': ruin['id'],
                          'node': ruin['node'], 'born_under_surge': bool(surge is not None and surge >= SURGE_BIRTH),
                          'weave_tide': surge})
        elif cause.startswith('war_'):
            sites.append({'id': 'shrine-' + ruin['id'], 'kind': 'shrine', 'god_id': 'god_red_field', 'ruin_id': ruin['id'],
                          'node': ruin['node']})
    for site in (previous or {}).get('sites', []):
        if site.get('kind') in ('theophany', 'pilgrimage'):
            sites.append(copy.deepcopy(site))
    return sorted(sites, key=lambda s: s['id'])


def add_religion(result, cfg=None, seed=None):
    """Resolve gods, cosmology, faiths and sites from the current world. Narrative only."""
    previous = result.get('religion')
    seed = result['config']['seed'] if seed is None and 'config' in result else (seed if seed is not None else 0)
    facts = world_facts(result, cfg)
    gods = resolve_gods(result, facts, previous)
    manifest = frozenset(g['id'] for g in gods if g['status'] in ('manifest', 'walking'))
    cosmology = choose_cosmology(facts, manifest, seed)
    doc = catalogue()
    fold_free = cosmology['id'] in doc['fold_free_cosmologies']
    for god in gods:
        target = gods_by_id()[god['id']].get('folds_into')
        god['saint_of'] = target if (target and target in manifest and not fold_free and god['status'] != 'absent') else None
    conversions = {c: f['conversion'] for c, f in (previous or {}).get('faiths', {}).items() if f.get('conversion')}
    faiths = choose_faiths(result, facts, gods, cosmology, seed, conversions)
    result['religion'] = {
        'version': VERSION, 'catalogue': catalogue_identity(), 'facts': facts, 'cosmology': cosmology,
        'gods': gods + hidden_records(previous),
        'faiths': faiths, 'sites': resolve_sites(result, gods, previous),
        'visitations': copy.deepcopy((previous or {}).get('visitations', [])),
        # Carried forward like visitations: resolving religion rebuilds this block, and a
        # corruption record outliving its rebuild is the whole point of a persistent node.
        'corruptions': copy.deepcopy((previous or {}).get('corruptions', [])),
        'method': 'Every god has an independent existence rule read from exported world state; a god that stops '
                  'qualifying sleeps with its last aspect. One cosmology is drawn from the eligible templates by fit '
                  'weight. Each civilization with a live city takes its ancestor god as patron and draws up to three '
                  'more by affinity, cosmology rank and the leyline potency under its cities. Feasts follow the almanac.',
        'limits': 'Gods are narrative provenance only: no terrain, food, threat or influence effect until the '
                  'orchestrator summons one through the visitation API. Names and epithets are authored English.'}
    return result
