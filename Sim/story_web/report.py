"""Calibration report: does the deterministic assignment match what the log says about each person?

The report lists every woven hero with the facts that admitted their spokes, the weight
table, and the offered hook, then flags the cases a reviewer should look at:

- `generic`: a generic seat spoke (The Court, The Reign) won although a spoke that names
  the hero's archetype in `fits` was eligible.
- `unfit`: the offered spoke does not name the hero's archetype although some eligible spoke does.
- `claim`: the offered spoke does not accept the hero's claim verb although some eligible spoke does.
- `close`: the runner-up is within `margin` of the winner, so the assignment is fragile.
- `unwoven`: no spoke admitted the hero.

Nothing here changes the block; it reads it.
"""
GENERIC = ('the_court', 'the_reign')


def flags(block, tropes_by_id, margin=0.1):
    out = []
    for web in block['webs']:
        offered = tropes_by_id[web['offered']]
        spokes = web['spokes']
        fitting = [s for s in spokes if web['archetype'] in tropes_by_id[s['trope_id']]['fits']]
        claiming = [s for s in spokes if web['claim'] in tropes_by_id[s['trope_id']]['claims']]
        reasons = []
        if web['offered'] in GENERIC and fitting and fitting[0]['trope_id'] != web['offered']:
            reasons.append(f"generic: {web['offered']} beat fitting {fitting[0]['trope_id']} ({fitting[0]['weight']} vs {spokes[0]['weight']})")
        if fitting and web['archetype'] not in offered['fits']:
            reasons.append(f"unfit: {web['archetype']} not in {web['offered']}.fits; fitting {fitting[0]['trope_id']}={fitting[0]['weight']}")
        if claiming and web['claim'] not in offered['claims'] and web['claim'] != 'none':
            reasons.append(f"claim: {web['claim']} not accepted by {web['offered']}; {claiming[0]['trope_id']} would")
        if len(spokes) > 1 and spokes[0]['weight'] > 0 and (spokes[0]['weight'] - spokes[1]['weight']) / spokes[0]['weight'] < margin:
            reasons.append(f"close: {spokes[0]['trope_id']}={spokes[0]['weight']} vs {spokes[1]['trope_id']}={spokes[1]['weight']}")
        for reason in reasons:
            out.append((web['uid'], web['display_name'], reason))
    for u in block['unwoven']:
        out.append((u['uid'], u['display_name'], 'unwoven: nearest ' + ', '.join(f"{n['trope_id']} missing {n['missing']}" for n in u['nearest'])))
    return out


def lines(block, tropes_by_id, heroes=None, verbose=True):
    people = {p['uid']: p for p in ((heroes or {}).get('people') or []) + ((heroes or {}).get('dreads') or [])}
    out = []
    s = block['summary']
    out.append(f"woven {s['woven']} · unwoven {s['unwoven']} · reachable {s['reachable_tropes']}/{s['tropes']} · mean spokes {s['mean_spokes']}")
    out.append('offered: ' + ', '.join(f'{k}={v}' for k, v in s['offered'].items()))
    for web in block['webs']:
        out.append('')
        out.append(f"{web['display_name']} [{web['uid']}] {web['role']} · {web['archetype']} · {web['alignment']['code']} "
                   f"({web['alignment']['law']:+.2f}/{web['alignment']['good']:+.2f}) · claim {web['claim']} → {web['offered']}")
        person = people.get(web['uid'])
        if person and verbose:
            for entry in person.get('log') or []:
                out.append(f"    log: Age {entry['age']} {entry['event_kind']} {entry['role']}: {entry['text']}")
            out.append(f"    now: {person.get('situation')}")
        out.append('    spokes: ' + ', '.join(f"{sp['trope_id']}={sp['weight']}" for sp in web['spokes']))
        if verbose:
            top = web['spokes'][0]['breakdown']
            out.append(f"    winner: boosts {top['boosts']} {top['boosted_by']} × fit {top['alignment_fit']} × archetype {top['archetype_fit']} × claim {top['claim_fit']}")
            out.append(f"    hook: {web['rest']['hook']['prompt'] or '(silent, world-driven)'}")
    flagged = flags(block, tropes_by_id)
    review = [f for f in flagged if f[2].startswith(('close', 'unwoven'))]
    tilt = [f for f in flagged if f not in review]
    out.append('')
    out.append(f'review ({len(review)}): fragile or empty assignments')
    for uid, name, reason in review:
        out.append(f'  {name} [{uid}]: {reason}')
    out.append(f'tilt ({len(tilt)}): history beat the archetype or claim; by design unless the log disagrees')
    for uid, name, reason in tilt:
        out.append(f'  {name} [{uid}]: {reason}')
    return out
