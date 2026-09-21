"""Quest hooks: a living person's claim, compiled into typed effects on things the world has.

A hook says what the giver asks for (`stated_purpose`) and what doing it actually does
(`actual_effect`, typed against a ruin, city, nest, relic or leyline node). For a person
with one face the two agree. For a person with a public face the stated purpose comes
from that face and `unwitting` is true: the player is handed the wrong reason for a real
effect. Which nodes are touched is read from the world; nothing is scripted beyond that.

**The quest contract: anchor, verb, difficulty.** A hook names an anchor, says what the
player does to it, and says how hard it is on the creature-tier rubric. It never names a
reward. The generator emits no loot, no XP and no treasure table; `difficulty` is the one
number a consuming game prices, and pricing it is that game's job, not this one's.

- ``verb`` is drawn from :data:`VERBS`, the same closed vocabulary `npc_roster` tags its
  posts with, so a hero-given hook and a post-given offer are the same kind of thing to a
  consumer. A ley effect carries no `action` of its own, so its verb comes from the sign
  of its `intensity_delta` through the `quests.ley_verb` policy.
- ``difficulty`` is an integer 1..5 and is derived, never invented -- see
  :func:`difficulty`.
- ``target_node`` is the terrain node the player stands on to do it, and
  ``unsited_reason`` says why there is none when there is none. A bare ley node is a
  direction and an intensity with no footprint anywhere in the world, so it is reported as
  unsited rather than given an invented position. A ley *key point*, whose id is a ruin's
  id plus `-key`, stands at that ruin and is sited there: that join already exists in
  `_node_name` and is read rather than guessed.
"""
import math

from .history import separation, short_name
from .wells.countryside import anchor as small_site_key

#: The one verb vocabulary, identical to `npc_roster/policies/posts.json` `verbs`.
#: `hero_generator` may not import a sibling package, so the list is declared in both
#: places and `Sim/tests/test_hero_generator.py::QuestContractTests` is what keeps the two
#: copies one list. It is a closed contract rather than a tuning table, which is why it is
#: code and not policy: a new verb needs a new hook branch to emit it.
VERBS = ('reclaim', 'recover', 'defend', 'slay', 'trade', 'tend', 'convert', 'supply',
         'cleanse', 'investigate')

#: Why a hook has no `target_node`. A published vocabulary: a consumer branches on it to
#: decide whether to draw a marker, and two reasons that read the same to a player are
#: still two reasons here.
#:
#: `ley_node_has_no_site` is the honest one -- `magic.networks.<school>.nodes[]` carries a
#: direction and an intensity and nothing a player can stand in front of. The other two
#: say the world moved out from under the hook, which is a world change and not a defect.
UNSITED_REASONS = ('ley_node_has_no_site', 'target_not_found', 'target_has_no_node')

#: The rubric reaches 5 only through what stands at the target, never through the ground
#: around it, so a long walk past a lair can never turn an errand into a campaign threat.
PRESSURE_EXEMPT = ('nest',)


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


def _small_sites(records, kind):
    """Hamlets and fortresses under both the ordinal id and the positional node key.

    Both are in use at once and a hook may name either, so a lookup that knows only one of
    them answers `target_not_found` for a site standing right there. The ordinal is written
    first and the node key second, so a collision between the two spellings resolves to the
    node key, which is the one that survives an age.
    """
    table = {}
    for record in records or []:
        if 'id' in record:
            table[record['id']] = record
    for record in records or []:
        table[small_site_key(record, kind)] = record
    return table


def _index(world, relics_by_ruin):
    """Every lookup the contract fields need, built once per world.

    No two blocks name their key the same way, so each row states the exact field it joins
    on rather than trusting a shared convention: `ruins` by `uid` (its `id` is the
    `ruin-`-prefixed form the ley key points use), settlements by `uid`, ports, shrines and
    colleges by `id`, and hamlets and fortresses by both spellings of theirs.
    """
    ruins = world.get('ruins') or []
    return {
        'ruins_by_uid': {r['uid']: r for r in ruins if 'uid' in r},
        'ruins_by_id': {r['id']: r for r in ruins if 'id' in r},
        'city': {c['uid']: c for c in (world.get('settlements') or {}).get('sites') or [] if 'uid' in c},
        'hamlet': _small_sites((world.get('humans') or {}).get('hamlets'), 'hamlet'),
        'fortress': _small_sites((world.get('humans') or {}).get('fortresses'), 'fortress'),
        'port': {p['id']: p for p in (world.get('fisheries') or {}).get('ports') or [] if 'id' in p},
        'shrine': {s['id']: s for s in (world.get('religion') or {}).get('sites') or [] if 'id' in s},
        'college': {c['id']: c for c in (world.get('magic') or {}).get('colleges') or [] if 'id' in c},
        'nest': {n['id']: n for n in (world.get('beast_nests') or {}).get('sites') or [] if 'id' in n},
        'ruin_of_relic': {relic['uid']: ruin_uid for ruin_uid, relic in sorted(relics_by_ruin.items())},
        'intensity': {node['id']: float(node.get('intensity') or 0.)
                      for _, network in sorted(((world.get('magic') or {}).get('networks') or {}).items())
                      for node in network.get('nodes') or []},
    }


def _target(effect, index):
    """`(record, node, unsited_reason)` for what a hook points at.

    `record` is the placed thing whose `x`/`z` the pressure term measures from, which is
    not always the thing named: a shrine carries a node and no grid position, so its ruin
    answers for it, and a ley key point *is* its ruin.

    A hamlet or fortress is looked up under **both** spellings its id has, because the two
    key spaces are live at once: `humans.hamlets[].id` is an ordinal that renumbers every
    age, and `wells/countryside.anchor` mints the positional `hamlet-node-<n>` a person's
    claim is keyed on. That function is imported rather than its spelling copied, so this
    lookup follows it wherever it goes; restating the format here is how the two would
    drift apart and every countryside hook would quietly read `target_not_found`.
    """
    kind = effect.get('kind')
    if kind == 'ley_node':
        node_id = effect.get('node_id') or ''
        ruin = index['ruins_by_id'].get(node_id[:-4]) if node_id.endswith('-key') else None
        if ruin is None:
            return None, None, 'ley_node_has_no_site'
        return ruin, ruin.get('node'), None
    if kind == 'relic':
        record = index['ruins_by_uid'].get(index['ruin_of_relic'].get(effect.get('uid')))
    elif kind == 'ruin':
        record = index['ruins_by_uid'].get(effect.get('uid'))
    elif kind == 'nest':
        record = index['nest'].get(effect.get('nest_id') or effect.get('uid'))
    else:
        record = (index.get(kind) or {}).get(effect.get('uid'))
    if record is None:
        return None, None, 'target_not_found'
    node = record.get('node')
    if node is None:
        return record, None, 'target_has_no_node'
    if 'x' not in record and kind == 'shrine':
        # `religion.sites` carries a node and no grid position; the ruin it was born of
        # carries both, and is the same ground.
        return index['ruins_by_id'].get(record.get('ruin_id')), node, None
    return record, node, None


def _pressure(record, nests, spacing, rules):
    """The danger the world already records around the target's ground.

    The highest tier among the nests whose own declared `range_m` reaches it, weighted and
    capped. Measured in grid metres (`spacing_m` per node), the same measure
    `wells/countryside.py` uses to decide whether a hamlet is threatened -- never on the
    render and never on the globe, so the two passes cannot disagree.

    Nothing reaching it is 0.0, which is a statement about the ground rather than a
    missing value: quiet country is the common case and it should read as quiet.
    """
    if record is None or 'x' not in record or 'z' not in record:
        return 0.
    worst = 0
    for nest in nests:
        if 'x' not in nest or 'z' not in nest:
            continue
        reach = float(nest.get('range_m') or 0.)
        if reach <= 0.:
            continue
        if math.hypot(record['x'] - nest['x'], record['z'] - nest['z']) * spacing <= reach:
            worst = max(worst, int(nest.get('tier') or 0))
    return min(float(rules['pressure_cap']), float(rules['pressure_per_tier']) * worst)


def difficulty(effect, record, index, nests, spacing, rules):
    """How hard the thing is, on the creature-tier rubric, derived and never invented.

        difficulty = clamp(1, 5, floor(opposition + pressure + 0.5))

    **Opposition is what stands at the target**, and it is the only term that can reach 5
    on its own. A lair answers with its own `tier`, which *is* the rubric -- 1 harmless, 2
    can hurt you, 3 kills the careless, 4 kills the prepared, 5 a campaign threat. A ley
    node answers with its own intensity. Everything else takes a floor by what the place
    is: ground somebody holds, or an errand.

    **Pressure is the danger recorded around it**, bounded, and never applied to a nest
    target: its tier is already the whole answer and its own `range_m` would otherwise
    count it a second time.

    The banding is `floor(x + 0.5)` rather than `round`, because CPython rounds halves to
    even and a rubric that sends 2.5 down and 3.5 up reads as arbitrary to anyone checking
    it by hand.
    """
    kind = effect.get('kind')
    if kind == 'nest':
        opposition = float((record or {}).get('tier') or rules['difficulty_min'])
    elif kind == 'ley_node':
        intensity = index['intensity'].get(effect.get('node_id'), 0.)
        opposition = float(rules['ley_floor']) + float(rules['ley_intensity_weight']) * intensity
    else:
        opposition = float(rules['opposition'].get(kind, rules['difficulty_min']))
    pressure = 0. if kind in PRESSURE_EXEMPT else _pressure(record, nests, spacing, rules)
    banded = int(math.floor(opposition + pressure + .5))
    return max(int(rules['difficulty_min']), min(int(rules['difficulty_max']), banded))


def _verb(effect, rules):
    """The hook's verb, from the one vocabulary.

    Every effect but a ley change already carries its `action`, drawn from that vocabulary
    when the branch below wrote it. A ley change carries a school and a delta instead, so
    its verb is the sign of the delta: deepening a node is tending it, thinning one is
    cleansing it, and `cleanse` is the same word `cleanse_request` uses for the same act.
    """
    action = effect.get('action')
    if action is not None:
        return action
    if effect.get('kind') != 'ley_node':
        return None
    key = 'strengthen' if float(effect.get('intensity_delta') or 0.) >= 0. else 'weaken'
    return rules['ley_verb'][key]


def quest_hooks(world, people, relics_by_ruin, policy):
    ruins_by_id = {r['id']: r for r in world.get('ruins', [])}
    delta = policy['magic']['hook_intensity_delta']
    rules = policy['quests']
    index = _index(world, relics_by_ruin)
    nests = [n for n in (world.get('beast_nests') or {}).get('sites') or []]
    spacing = float(world.get('spacing_m') or 1000.)
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
        for index_of, (stated, effect, unwitting) in enumerate(out):
            record, node, unsited = _target(effect, index)
            verb = _verb(effect, rules)
            if verb not in VERBS:
                raise ValueError(f'quest hook verb {verb!r} is outside the vocabulary')
            hooks.append({'hook_id': f"hook-{person['uid']}-{index_of}", 'giver_uid': person['uid'], 'offered_from_face': face,
                          'stated_purpose': stated, 'actual_effect': effect, 'unwitting': unwitting,
                          # A nest effect names `nest_id`, so reading `uid` or `node_id`
                          # alone left every slay hook pointing at nothing.
                          'target': effect.get('uid') or effect.get('node_id') or effect.get('nest_id'),
                          'verb': verb,
                          'difficulty': difficulty(effect, record, index, nests, spacing, rules),
                          'target_node': node, 'unsited_reason': unsited})
    return hooks
