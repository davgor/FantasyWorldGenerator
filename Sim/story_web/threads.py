"""Threads: where a hero can step at an act exit, with the one typed condition each step needs.

For every other trope the compiler looks at every entry conjunction and keeps the cheapest
way in. A thread is `open` when the trope is eligible now and its pull agrees with the
hero's alignment (non-negative dot product); `alignment` when it is eligible but pulls
against the hero, so the walker takes it only if the alignment moved that way during the
act; `claim` when only a different claim verb is missing; `feature` when one or two
runtime-gainable facts would make it eligible. The thread's weight is the trope's weight
*after* the condition holds (the changed verb or the gained facts applied), so the order
reflects where the hero would land. A thread is `cut` when the archetype's constraints
forbid the change it needs. Threads are ranked open first, then by weight, and capped.
Only an `open` way in is checked against the pull: a `claim` or `feature` thread already
names the one change it needs, and the walker re-evaluates alignment when it arrives.
"""
from .predicates import holds
from .weights import weight

RANK = {'open': 0, 'alignment': 1, 'claim': 2, 'feature': 3}


def constraints_for(hero, constraints):
    return constraints['archetypes'].get(hero.get('archetype') or '', constraints['default'])


def opposes(pull, alignment):
    """The axis on which the trope pulls hardest against the hero, or None when the pull agrees."""
    contributions = {axis: pull[axis] * alignment[axis] for axis in ('good', 'law')}
    if sum(contributions.values()) >= 0.:
        return None
    axis = min(('good', 'law'), key=lambda a: (contributions[a], a))
    return axis, 'up' if pull[axis] > 0 else 'down'


def _way_in(conjunction, facts, gainable):
    """The condition under which this conjunction would hold, and the facts it would leave."""
    gaps = [t for t in conjunction if not holds(t, facts)]
    if not gaps:
        return {'kind': 'open'}, facts
    verbs = [g[len('claim:'):] for g in gaps if g.startswith('claim:')]
    others = [g for g in gaps if not g.startswith('claim:')]
    if len(verbs) == 1 and not others:
        after = {f for f in facts if not f.startswith('claim:')} | {'claim:' + verbs[0]}
        return {'kind': 'claim', 'verb': verbs[0]}, after
    if not verbs and 1 <= len(others) <= 2 and all(not g.startswith('!') and g in gainable for g in others):
        return {'kind': 'feature', 'facts': others}, facts | set(others)
    return None, None


def threads_from(offered, tropes, facts, hero, policies):
    weights = policies['weights']
    rules = constraints_for(hero, policies['constraints'])
    gainable = set(weights['gainable_features'])
    kind = 'dread' if hero['role'] == 'dread' else 'person'
    out = []
    for trope in tropes:
        if trope['id'] == offered['id'] or kind not in trope['cast']:
            continue
        best = None
        for conjunction in trope['requires']:
            condition, after = _way_in(conjunction, facts, gainable)
            if condition is None:
                continue
            key = (RANK[condition['kind']], len(condition.get('facts', [])))
            if best is None or key < best[0]:
                best = (key, condition, after)
        if best is None:
            continue
        _, condition, after = best
        hero_after = hero
        if condition['kind'] == 'claim':
            hero_after = dict(hero, claim=dict(hero.get('claim') or {}, verb=condition['verb']))
        thread = {'to': trope['id'], 'weight': weight(trope, after, hero_after, weights)[0], 'condition': condition, 'cut': None}
        if condition['kind'] == 'open':
            opposed = opposes(trope['pull'], hero['alignment'])
            if opposed is not None:
                thread['condition'] = {'kind': 'alignment', 'axis': opposed[0], 'toward': opposed[1]}
                if rules['drift_locked']:
                    thread['cut'] = 'drift locked by archetype'
        elif condition['kind'] == 'claim':
            if rules['claim_locked']:
                thread['cut'] = 'claim locked by archetype'
            elif rules['allowed_verbs'] is not None and condition['verb'] not in rules['allowed_verbs']:
                thread['cut'] = f"claim verb {condition['verb']} not allowed by archetype"
        out.append(thread)
    out.sort(key=lambda t: (RANK[t['condition']['kind']], -t['weight'], t['to']))
    return out[:weights['max_threads_per_act']]
