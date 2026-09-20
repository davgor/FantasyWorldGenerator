"""Story web: the arcs every living hero could walk, compiled from the cast and the world.

Called once after the hero generator attaches its block, with the finished world as plain
JSON. It reads `heroes` (people, dreads, bonds, relics, camps, mantles, realms) and a few
exported world facts (threat assessments, rural food balance, the lunar almanac, ley node
intensity) and writes only `story_web`. It never imports `icarus_sim` or `hero_generator`.

For each living person and Dread it evaluates every trope's entry predicate, weights the
eligible spokes by the deterministic equation in `policies/weights.json`, offers the
heaviest as the hero's resting hook, arms the rest, binds the offered trope's three acts to
real names, and lists the threads each act can exit along, with the one condition each
needs and any cut the archetype's constraints impose. Heroes no trope admits are reported
with the nearest misses. Nothing is rolled; the same world and policy revisions give the
same web byte for byte.
"""
import copy
import os

from .bind import fill, slots_for
from .facts import WorldFacts, person_facts
from .policy import load_all, revisions
from .predicates import eligible, missing
from .seeds import rng
from .threads import constraints_for, threads_from
from .weights import angle_degrees, weight

VERSION = 1
ENV_SWITCH = 'FANTASY_WORLD_STORY_WEB'
METHOD = ('For every living person and Dread: derive facts from the exported record (features, role, status, claim verb, '
          'bond kinds, tier, archetype, presence, faces) and the world (war pressure and threat on the home city, rural '
          'food deficit, lunar surges, node intensity at a held key point, living rivals, resting relics, squatted ruins, '
          'open mantles, seated tyrants). Every trope whose entry predicate holds is a spoke; weight = boosts × '
          'alignment fit × archetype fit × claim fit. The heaviest spoke is the offered hook, ties broken on trope id; '
          'the rest are armed. The offered trope\'s three acts are bound to the hero\'s own names and each act lists '
          'the threads it can exit along with one typed condition and any archetype cut. No draw decides an assignment; '
          'the seed only staggers initiative deadlines.')
LIMITS = ('A compiled offer, not a running story: nothing here advances an act, applies a delta, resolves an abandonment '
          'or writes to the cast. Completion and abandonment predicates are exported for a later walker. World facts are '
          'coarse (a surge anywhere counts for everyone; reach is the home city). Tropes whose entry names features no '
          'well computes yet are listed in the ledger as unreachable rather than hidden.')


def enabled():
    return os.environ.get(ENV_SWITCH, '1') != '0'


def attach(world):
    """The one call the generator makes. Never raises; a failure is a reported block."""
    if not enabled():
        return None
    try:
        return generate(world)
    except Exception as exc:  # noqa: BLE001 - report, never crash the world
        return {'version': VERSION, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}


def generate(world, policies=None):
    """The story web for a finished world that already carries a `heroes` block."""
    heroes = _validate(world)
    policies = policies or load_all()
    tropes = policies['tropes']['tropes']
    weights = policies['weights']
    seed = int(world['config']['seed'])
    world_facts = WorldFacts(world, heroes, weights)
    bonds = heroes.get('bonds') or []
    cast = [p for p in (heroes.get('people') or []) + (heroes.get('dreads') or []) if p.get('status') == 'living']
    cast.sort(key=lambda p: p['uid'])
    webs, unwoven, histogram = [], [], {}
    for hero in cast:
        facts = person_facts(hero, bonds, heroes.get('final_age')) | world_facts.for_hero(hero)
        kind = 'dread' if hero['role'] == 'dread' else 'person'
        spokes, considered = [], []
        for trope in tropes:
            if kind not in trope['cast']:
                continue
            if eligible(trope['requires'], facts):
                value, breakdown = weight(trope, facts, hero, weights)
                spokes.append({'trope_id': trope['id'], 'name': trope['name'], 'weight': value, 'breakdown': breakdown,
                               'angle': angle_degrees(trope['pull']['law'], trope['pull']['good'])})
            else:
                considered.append({'trope_id': trope['id'], 'missing': missing(trope['requires'], facts)})
        considered.sort(key=lambda c: (len(c['missing']), c['trope_id']))
        if not spokes:
            unwoven.append({'uid': hero['uid'], 'display_name': hero.get('display_name'), 'archetype': hero.get('archetype'),
                            'facts': sorted(facts), 'nearest': considered[:3]})
            continue
        spokes.sort(key=lambda s: (-s['weight'], s['trope_id']))
        offered = spokes[0]
        trope = next(t for t in tropes if t['id'] == offered['trope_id'])
        slots = slots_for(hero, heroes)
        threads = threads_from(trope, tropes, facts, hero, policies)
        acts = []
        for index, act in enumerate(trope['acts']):
            acts.append({'id': act['id'], 'title': act['title'], 'ring': index + 1,
                         'prompt': fill(act['prompt'], slots),
                         'completion': copy.deepcopy(act['completion']),
                         'abandonment': {**copy.deepcopy(act['abandonment']), 'implicit': ['protagonist_dead', 'target_gone']},
                         'options': [{'id': o['id'], 'text': fill(o['text'], slots), 'delta': dict(o['delta']), 'effect': o['effect']}
                                     for o in act['options']]})
        initiative = weights['initiative_days'] + rng(seed, 'web-initiative-' + hero['uid']).randrange(0, 30)
        histogram[offered['trope_id']] = histogram.get(offered['trope_id'], 0) + 1
        webs.append({'uid': hero['uid'], 'display_name': hero.get('display_name'), 'role': hero['role'],
                     'archetype': hero.get('archetype'), 'alignment': {'law': hero['alignment']['law'], 'good': hero['alignment']['good'],
                                                                        'code': hero['alignment']['code'],
                                                                        'angle': angle_degrees(hero['alignment']['law'], hero['alignment']['good'])},
                     'claim': (hero.get('claim') or {}).get('verb') or 'none',
                     'facts': sorted(facts), 'constraints': constraints_for(hero, policies['constraints']),
                     'spokes': spokes, 'offered': offered['trope_id'],
                     'rest': {'hook': {'trope_id': trope['id'], 'act_id': trope['acts'][0]['id'], 'prompt': acts[0]['prompt'],
                                       'expires_day': initiative},
                              'armed': [{'trope_id': s['trope_id'], 'weight': s['weight']} for s in spokes[1:]],
                              'initiative_day': initiative},
                     'acts': acts, 'threads': threads, 'considered': considered, 'examples': list(trope['examples'])})
    reachable = {t['id'] for t in tropes if _reachable(t)}
    return {'version': VERSION, 'status': 'ok', 'policy_revision': revisions(policies),
            'heroes_revision': heroes.get('policy_revision'),
            'summary': {'woven': len(webs), 'unwoven': len(unwoven), 'tropes': len(tropes),
                        'reachable_tropes': len(reachable), 'offered': dict(sorted(histogram.items())),
                        'mean_spokes': round(sum(len(w['spokes']) for w in webs) / len(webs), 3) if webs else 0.},
            'webs': webs, 'unwoven': unwoven,
            'tropes': [{'id': t['id'], 'name': t['name'], 'pull': dict(t['pull']), 'cast': list(t['cast']),
                        'angle': angle_degrees(t['pull']['law'], t['pull']['good'])} for t in tropes],
            'unreachable_tropes': sorted(t['id'] for t in tropes if t['id'] not in reachable),
            'method': METHOD, 'limits': LIMITS}


# Features the archetype catalogue reserves but no well or cross-cutting pass computes yet
# (checked against Sim/hero_generator on 2026-09-19: the cities well emits role:schemer, stakes:2,
# routes:2, realm:cold_conflicts_2 and the diaspora roles prophet, heresiarch, exile and founder).
NEVER_COMPUTED = frozenset({'dread:person_shaped', 'ally:lost', 'deeds:two_schools'})


def _reachable(trope):
    """A trope whose every conjunction needs a feature nothing computes is documented but cannot fire."""
    return any(all(t.startswith('archetype:') or t.lstrip('!') not in NEVER_COMPUTED for t in conjunction)
               for conjunction in trope['requires'])


def _validate(world):
    if not isinstance(world, dict) or type((world.get('config') or {}).get('seed')) is not int:
        raise ValueError('story web needs a finished world with an integer config.seed')
    heroes = world.get('heroes')
    if not isinstance(heroes, dict):
        raise ValueError('story web needs the heroes block; run the hero generator first')
    if heroes.get('status') != 'ok':
        raise ValueError(f"heroes block is not ok: {heroes.get('error')}")
    for key in ('people', 'dreads', 'bonds', 'realms'):
        if key not in heroes:
            raise ValueError(f'heroes block lacks {key}')
    return heroes


def summary_lines(block):
    """Short human lines for logs and the lab status."""
    if block.get('status') != 'ok':
        return [f"story web failed: {block.get('error')}"]
    s = block['summary']
    lines = [f"{s['woven']} woven · {s['unwoven']} unwoven · {s['reachable_tropes']} of {s['tropes']} tropes reachable · "
             f"mean spokes {s['mean_spokes']}"]
    for web in block['webs']:
        lines.append(f"{web['display_name']} — {web['archetype']}, {web['alignment']['code']} → {web['offered']} "
                     f"({len(web['spokes'])} spokes)")
    return lines
