"""Quest hooks: a living person's claim, compiled into typed effects on things the world has.

A hook says what the giver asks for (`stated_purpose`) and what doing it actually does
(`actual_effect`, typed against a ruin, city, nest, relic or leyline node). For a person
with one face the two agree. For a person with a public face the stated purpose comes
from that face and `unwitting` is true: the player is handed the wrong reason for a real
effect. Which nodes are touched is read from the world; nothing is scripted beyond that.
"""
from .history import separation, short_name


def _node_name(node_id, school, ruins_by_id):
    if node_id.endswith('-key'):
        ruin = ruins_by_id.get(node_id[:-4])
        if ruin:
            return f"the {school} key point at {short_name(ruin['name'])}"
    return f"the {school} node {node_id}"


def _nearest_opposing(world, person, school, policy):
    opposite = policy['magic']['opposites'].get(school)
    networks = (world.get('magic') or {}).get('networks') or {}
    anchor = person.get('anchor_direction')
    if not opposite or opposite not in networks or anchor is None:
        return None, None
    best = None
    for node in networks[opposite].get('nodes', []):
        key = (separation({'direction': anchor}, node, 1.), node['id'])
        if best is None or key < best[0]:
            best = (key, node)
    return (opposite, best[1]) if best else (None, None)


def quest_hooks(world, people, relics_by_ruin, policy):
    ruins_by_id = {r['id']: r for r in world.get('ruins', [])}
    delta = policy['magic']['hook_intensity_delta']
    hooks = []
    for person in people:
        if person['status'] != 'living':
            continue
        covert = len(person['faces']) > 1 and person['faces'][0]['label'] == 'public'
        face = 'public' if covert else person['faces'][0]['label']
        claim = person['claim']
        out = []
        if claim['verb'] == 'retake':
            out.append(('Help me take back ' + claim['target_name'] + '.', {'kind': 'ruin', 'uid': claim['target_uid'], 'action': 'reclaim'}, False))
            relic = relics_by_ruin.get(claim['target_uid'])
            if relic:
                out.append((f"Recover {relic['name']} from the ruins.", {'kind': 'relic', 'uid': relic['uid'], 'action': 'recover'}, False))
        elif claim['verb'] == 'hold' and person['role'] == 'warlord':
            out.append(('Stand with ' + claim['target_name'] + ' when they come for it.', {'kind': 'city', 'uid': claim['target_uid'], 'action': 'defend'}, False))
        elif person.get('node_id') and claim['verb'] in ('hold', 'exploit'):
            school = person['school']
            own = {'kind': 'ley_node', 'node_id': person['node_id'], 'school': school, 'intensity_delta': delta}
            honest = f"Strengthen {_node_name(person['node_id'], school, ruins_by_id)}."
            cover = f"Restore the old shrine at {short_name(person['lost']['name']) if person.get('lost') else claim['target_name']}; the land around it is sick."
            out.append((cover if covert else honest, own, covert))
            opposite, node = _nearest_opposing(world, person, school, policy)
            if node:
                weaken = {'kind': 'ley_node', 'node_id': node['id'], 'school': opposite, 'intensity_delta': -delta}
                honest = f"Weaken {_node_name(node['id'], opposite, ruins_by_id)}; it chokes the {school}."
                cover = f"Cleanse {_node_name(node['id'], opposite, ruins_by_id)}; something there is poisoning the valley."
                out.append((cover if covert else honest, weaken, covert))
        elif person['role'] == 'reeve':
            out.append((f"See {claim['target_name']} through the season.", {'kind': 'hamlet', 'uid': claim['target_uid'], 'action': 'defend'}, False))
            if person.get('nest_id'):
                out.append((f"Drive the {person['nest_name'].lower()} from our fields.", {'kind': 'nest', 'nest_id': person['nest_id'], 'action': 'slay'}, False))
        elif person['role'] == 'castellan':
            out.append((f"Hold {claim['target_name']} with me.", {'kind': 'fortress', 'uid': claim['target_uid'], 'action': 'defend'}, False))
        elif person['role'] == 'harbourmaster':
            out.append((f"Keep the sea lanes to {claim['target_name']} open.", {'kind': 'port', 'uid': claim['target_uid'], 'action': 'trade'}, False))
        elif person['role'] == 'keeper':
            out.append((f"Bring an offering to {claim['target_name']}.", {'kind': 'shrine', 'uid': claim['target_uid'], 'action': 'tend'}, False))
        elif person['role'] == 'sovereign':
            out.append(('Stand with ' + person['home']['name'] + ' when they come for it.', {'kind': 'city', 'uid': person['home']['uid'], 'action': 'defend'}, False))
        elif person['role'] == 'council' and person.get('seat') == 'market_steward':
            out.append((f"Keep the roads to {person['home']['name']} open; the granary is my ledger.", {'kind': 'city', 'uid': person['home']['uid'], 'action': 'trade'}, False))
        elif person['role'] == 'council' and person.get('seat') == 'commander':
            out.append((f"Walk the walls of {person['home']['name']} with me.", {'kind': 'city', 'uid': person['home']['uid'], 'action': 'defend'}, False))
        elif person['role'] == 'champion' and person.get('nest_id'):
            out.append((f"Help me end {claim['target_name']}.", {'kind': 'nest', 'nest_id': person['nest_id'], 'action': 'slay'}, False))
        elif person['role'] in ('heresiarch', 'prophet') and claim['verb'] == 'convert':
            out.append((f"Carry the word to {claim['target_name']}.", {'kind': 'city', 'uid': claim['target_uid'], 'action': 'convert'}, False))
        elif person['role'] in ('exile', 'founder', 'prophet'):
            out.append((f"Keep {claim['target_name']} standing.", {'kind': 'city', 'uid': claim['target_uid'], 'action': 'defend'}, False))
        elif person['role'] == 'magister' and person.get('college'):
            out.append((f"Bring the college near {short_name(person['home']['name'])} what it asks for.", {'kind': 'college', 'uid': person['college']['id'], 'action': 'supply'}, False))
        for index, (stated, effect, unwitting) in enumerate(out):
            hooks.append({'hook_id': f"hook-{person['uid']}-{index}", 'giver_uid': person['uid'], 'offered_from_face': face,
                          'stated_purpose': stated, 'actual_effect': effect, 'unwitting': unwitting,
                          'target': effect.get('uid') or effect.get('node_id')})
    return hooks
