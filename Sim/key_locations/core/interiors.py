"""Interior chamber graphs for tier-2 complexes.

This is a **graph, not geometry**. Chambers have a depth, a role, a rough size and a list of
what they connect to; they have no metre position, no walls and no contents. Laying a real
interior out in metres is what the settlement planners do for cities, and an interior planner
for these belongs in its own phase — claiming otherwise here would be a misleading
integration claim, which is exactly the thing reviewers are asked to flag.

What the graph *is* good for: knowing that a mine goes four levels down and a barrow does
not, that the flooded sump is between you and the vault, and that this warren has three ways
in while that tower has one. A text client can narrate from it directly; a 3D client can lay
it out later without re-deciding the structure.

Pure: no filesystem, no network, no engine, no generator imports.
"""

PLAN_NOTES = {
    'linear': 'One way in, one way on; depth is the only axis.',
    'branching': 'A spine with workings off it, the way anything dug for profit grows.',
    'radial': 'Built around a centre, with everything else facing it.',
    'warren': 'Dug without a plan over a long time; loops back on itself.',
    'vault': 'Shallow and wide: a few large rooms rather than a descent.',
}
ROLES = {
    'subterranean': ('gallery', 'sump', 'squeeze', 'chimney', 'grotto', 'rubble fall'),
    'extractive': ('gallery', 'stope', 'winze', 'pump house', 'spoil chamber', 'tool store'),
    'fortification': ('gatehouse', 'guardroom', 'barracks', 'cistern', 'undercroft', 'armoury'),
    'funerary': ('antechamber', 'burial cell', 'ossuary', 'offering niche', 'sealing stone', 'grave shaft'),
    'sacred': ('narthex', 'nave', 'crypt', 'cell', 'reliquary', 'cloister walk'),
    'arcane': ('workroom', 'binding floor', 'library', 'observation cell', 'ward ring', 'sink'),
    'lair': ('approach', 'nest floor', 'bone midden', 'hoard', 'bolt hole', 'roost'),
    'drowned': ('flooded hall', 'air pocket', 'silted room', 'collapsed stair', 'anchorage'),
    'wonder': ('approach', 'inner space', 'hollow', 'vantage'),
    'curiosity': ('entry room', 'main room', 'back room', 'store', 'stair'),
    'wayside': ('yard', 'common room', 'stable', 'cellar'),
}
FALLBACK_ROLES = ('chamber', 'passage', 'side room', 'stair')
ENTRANCE_KINDS = {'subterranean': 'mouth', 'extractive': 'shaft', 'funerary': 'sealed door',
                  'drowned': 'breach', 'lair': 'mouth'}
DEFAULT_ENTRANCE = 'door'
FLOODED_STATES = ('drowned',)
COLLAPSE_STATES = ('ruined', 'buried')
METHOD = ('Chamber graph only: depth, role, rough size and connections. Plans differ in how chambers attach '
          '- linear chains, branching spines, radial hubs, looping warrens, shallow vaults. State decides how '
          'much of it is flooded or fallen in.')


def _roles(family):
    return ROLES.get(family, FALLBACK_ROLES)


def _connect(plan, index, draw):
    """Which earlier chamber this one hangs off. Index 0 is the entrance chamber."""
    if index == 0:
        return []
    if plan == 'linear':
        return [index - 1]
    if plan == 'radial':
        return [0] if index > 1 else [0]
    if plan == 'vault':
        return [0] if index <= 2 else [draw.randint(0, index - 1)]
    if plan == 'branching':
        return [index - 1] if draw.random() < .6 else [draw.randint(0, index - 1)]
    return [draw.randint(max(0, index - 3), index - 1)]


def build(archetype, state, draw):
    """The interior for one tier-2 site, or ``None`` when the archetype declares none."""
    spec = archetype.get('interior')
    if not spec:
        return None
    plan = spec['plan']
    family = archetype['family']
    levels = draw.randint(spec['levels'][0], spec['levels'][1])
    count = draw.randint(spec['chambers'][0], spec['chambers'][1])
    roles = _roles(family)
    flooded_bias = .55 if state in FLOODED_STATES else .08
    collapse_bias = .3 if state in COLLAPSE_STATES else .05
    chambers = []
    for index in range(count):
        connects = _connect(plan, index, draw)
        depth = 0 if index == 0 else min(levels - 1, chambers[connects[0]]['depth'] + (1 if draw.random() < .45 else 0))
        chambers.append({
            'id': f'chamber-{index}',
            'depth': depth,
            'role': roles[draw.randrange(len(roles))] if index else 'entrance chamber',
            'size_m': [round(3. + draw.random() * 9., 1), round(3. + draw.random() * 9., 1)],
            'connects': [f'chamber-{c}' for c in connects],
            'flooded': draw.random() < flooded_bias * (1 + depth * .3),
            'collapsed': index > 0 and draw.random() < collapse_bias,
        })
    if plan == 'warren':
        for chamber in chambers[2:]:
            if draw.random() < .3:
                other = draw.randrange(len(chambers))
                link = f'chamber-{other}'
                if link != chamber['id'] and link not in chamber['connects']:
                    chamber['connects'].append(link)
    entrance_kind = ENTRANCE_KINDS.get(family, DEFAULT_ENTRANCE)
    entrances = [{'id': 'entrance-0', 'chamber': 'chamber-0', 'kind': entrance_kind,
                  'hidden': state in ('buried', 'sealed')}]
    extra = 1 if plan in ('warren', 'branching') and draw.random() < .45 else 0
    for index in range(extra):
        target = chambers[draw.randrange(len(chambers))]
        entrances.append({'id': f'entrance-{index + 1}', 'chamber': target['id'],
                          'kind': 'collapse' if target['collapsed'] else entrance_kind,
                          'hidden': True})
    return {'version': 1, 'plan': plan, 'plan_note': PLAN_NOTES[plan], 'levels': levels,
            'chambers': chambers, 'entrances': entrances, 'method': METHOD,
            'limits': 'A graph, not a layout. No metre positions, no contents, no encounters.'}
