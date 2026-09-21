"""Turn the three plan blocks into stable site rows and the posts standing in them.

Everything here is a pure read of the exported world JSON.

Identity is the whole difficulty. This block is re-derived after every age advance, and all
three planners rebuild their plans each time, so anything ordinal renames people:

* city uids are genuinely stable (``surface-city-<age>-<node>-<profile>``, carried across
  rebuilds by the settlement builder), so they are used unchanged;
* ``hamlet-0`` and ``fortress-0`` are ordinals that renumber every age, and ``plot-7`` is an
  ordinal inside a plan that is itself rebuilt, so neither can carry identity.

So the non-city sites are anchored positionally on their node, the way `terrain_villains`
anchors villains to ley nodes for exactly this reason. Nodes are unique within a kind, but a
hamlet and a fortress can share one, so the kind is part of the key. The ordinal plan ids are
kept on the row as convenience fields and are documented as never being identity.

The keys spell the anchor out -- ``hamlet-node-1062``, not ``hamlet-1062`` -- because two keys
that read alike and mean different things is how a consumer joins the wrong rows without an
error. A reader who sees ``-node-`` cannot mistake which space the number lives in.

The cast package used to be the counter-example: it built ``hero-castellan-fortress-36`` on the
*ordinal* id, so its ``presence.uid`` and this block's site ``uid`` named the same fortress in
two number spaces that could not be joined. It no longer does.
``hero_generator.wells.countryside.anchor`` now writes this same spelling, so a cast presence at
a hamlet or a fortress **is** a site uid here, and ``places()`` below is no longer the only
bridge between them. ``places()`` stays: the cast also stands at ports, ruins, shrines, camps
and nests whose ids belong to other blocks and are not keyed this way.

For the same reason nothing here reads ``culture_id``: those ids rehash every age. The stable
handle for a people is ``civilization_id``.
"""

CITY_CLASSES = ('capital', 'medium', 'small')


def _plot_order(plot):
    """`plot-10` must not sort before `plot-2`: order on the number, then the raw id."""
    raw = str(plot.get('id') or '')
    tail = raw.rsplit('-', 1)[-1]
    return (int(tail) if tail.isdigit() else len(raw) + 10 ** 9, raw)


def _plan_rows(world, block, key):
    """A plan list, tolerating the block being absent or invalidated by an identity change."""
    section = world.get(block)
    if not isinstance(section, dict):
        return []
    rows = section.get(key)
    return rows if isinstance(rows, list) else []


def _entities(world):
    return {entity['id']: entity for entity in (world.get('civilizations') or {}).get('entities', [])}


def _parent_race(entities, civilization_id):
    """The language family, or None. Never guesses `human`: a wrong parent is a wrong tongue."""
    entity = entities.get(civilization_id)
    return (entity or {}).get('parent_race_id')


def collect(world):
    """Every site that has staffed posts, with the posts it holds.

    Returns `(rows, notes)` where a row is a site plus its ordered `posts`, and notes counts
    what could not be resolved so the block can report it instead of guessing.
    """
    entities = _entities(world)
    ordered = (world.get('settlements') or {}).get('sites', [])
    settlements = {str(s.get('uid', s.get('id'))): s for s in ordered}
    # `core_id` on a hamlet or fortress is a POSITION in settlements.sites, not a uid: the
    # small-site builder stores `owner[i]`, and the hamlet planner dereferences it by index.
    by_index = {index: site for index, site in enumerate(ordered)}
    humans = world.get('humans') or {}
    fortress_nodes = {str(f['id']): f for f in humans.get('fortresses', []) if 'node' in f}
    # Every counter starts at zero and is always exported. A monitoring counter that appears
    # only once it is non-zero cannot be told apart from one that was never computed, which
    # makes it useless on exactly the day it would have earned its keep.
    notes = {'unresolved_parent_race': 0, 'unanchored_sites': 0, 'roster_mismatches': 0,
             'duplicate_site_keys': 0, 'important_capped_out': 0, 'cast_outside_a_planned_site': 0,
             'cast_located_by_presence': 0, 'cast_presence_unresolved': 0}
    rows = []

    for plan in _plan_rows(world, 'city_plans', 'cities'):
        uid = plan.get('city_uid')
        if not uid:
            notes['unanchored_sites'] += 1
            continue
        site = settlements.get(str(uid), {})
        civilization_id = plan.get('civilization_id') or site.get('civilization_id')
        rows.append({'uid': str(uid), 'kind': 'city', 'name': plan.get('name') or str(uid),
                     'civilization_id': civilization_id,
                     'parent_race_id': site.get('parent_race_id') or _parent_race(entities, civilization_id),
                     'city_class': plan.get('city_class') if plan.get('city_class') in CITY_CLASSES else None,
                     'plan_id': str(uid), 'node': site.get('node'),
                     'x': plan.get('x', site.get('x')), 'z': plan.get('z', site.get('z')),
                     'plan_status': plan.get('status'), 'plots': plan.get('plots') or []})

    for plan in _plan_rows(world, 'hamlet_plans', 'hamlets'):
        node = plan.get('node')
        if node is None:
            notes['unanchored_sites'] += 1
            continue
        civilization_id = plan.get('civilization_id')
        core = settlements.get(str(plan.get('core_city_uid'))) or by_index.get(plan.get('core_id')) or {}
        rows.append({'uid': f'hamlet-node-{node}', 'kind': 'hamlet',
                     'name': _hamlet_name(plan, core),
                     'civilization_id': civilization_id,
                     'parent_race_id': core.get('parent_race_id') or _parent_race(entities, civilization_id),
                     'city_class': None, 'plan_id': str(plan.get('hamlet_id') or ''), 'node': node,
                     'x': plan.get('x'), 'z': plan.get('z'),
                     'core_uid': plan.get('core_city_uid'), 'role': plan.get('role'),
                     'plan_status': plan.get('status'), 'plots': plan.get('plots') or []})

    for plan in _plan_rows(world, 'castle_plans', 'castles'):
        fortress = fortress_nodes.get(str(plan.get('fortress_id')))
        if fortress is None:
            notes['unanchored_sites'] += 1
            continue
        civilization_id = fortress.get('population_profile')
        core = by_index.get(fortress.get('core_id')) or {}
        rows.append({'uid': f"fortress-node-{fortress['node']}", 'kind': 'fortress',
                     'name': _fortress_name(core),
                     'civilization_id': civilization_id,
                     'parent_race_id': core.get('parent_race_id') or _parent_race(entities, civilization_id),
                     'city_class': None, 'plan_id': str(plan.get('fortress_id') or ''),
                     'node': fortress['node'], 'x': plan.get('x'), 'z': plan.get('z'),
                     'plan_status': plan.get('status'), 'plots': plan.get('plots') or []})

    rows.sort(key=lambda row: row['uid'])
    seen = set()
    unique = []
    for row in rows:
        if row['uid'] in seen:
            notes['duplicate_site_keys'] += 1
            continue
        seen.add(row['uid'])
        unique.append(row)
        if not row['parent_race_id']:
            notes['unresolved_parent_race'] += 1
    _disambiguate(unique)
    return unique, notes


def _disambiguate(rows):
    """Two farmsteads below the same city would otherwise share a name.

    The uids already differ, so nothing joins wrongly -- but a quest giver whose location
    reads exactly like another's is useless to a reader, and a person cannot be sent to "the
    fortress above Dunlin" when there are two. The node is what actually separates them, so
    it is what the name says.
    """
    counts = {}
    for row in rows:
        counts[row['name']] = counts.get(row['name'], 0) + 1
    for row in rows:
        if counts[row['name']] > 1 and row['node'] is not None:
            row['name'] = f"{row['name']} ({row['node']})"


def _short_name(core):
    """`Bargdorn (Age 2)` reads as `Bargdorn` inside a small site's name.

    The `(Age N)` split is live. The ` City` strip beside it is not:
    `heritage.settlement_name` replaced the round-robin that appended it, so on a
    generated world that replace is the identity. It still fires on the synthetic world in
    `tests/test_npc_roster.py` and on `Fixtures/npc-roster-v1.json`, which name their
    cities in the retired convention, so removing it renames the derived sites there.
    Tracked on board/backlog/CONTENT-CITY-SUFFIX-DEAD-READERS.md.
    """
    name = (core.get('name') or '').replace(' City', '')
    return name.split(' (Age ', 1)[0].strip()


PLACE_SOURCES = (('settlements', 'sites'), ('humans', 'hamlets'), ('humans', 'fortresses'),
                 ('fisheries', 'ports'), ('religion', 'sites'), ('heroes', 'camps'),
                 ('magic', 'colleges'), ('beast_nests', 'sites'))


def places(world):
    """Every exported record that names a place, indexed by its own id, with its node.

    The cast stands at fortresses, hamlets, ports, ruins, shrines and camps whose ids belong to
    those blocks, not to this one. Hamlets and fortresses now agree -- the cast writes
    `fortress-node-1062` for the fortress this package keys `fortress-node-1062` -- but a port,
    a ruin, a shrine, a camp, a college and a nest are still named in their own block's id
    space, and a consumer holding only the roster block cannot resolve those at all.

    So the coordinates are resolved here, where the whole world is in hand, and carried on the
    record. That is the point: a person posted to a remote fortress otherwise falls back to
    their home city, which is a real place and the wrong one, and a confidently wrong location
    is worse than no location for anything measuring travel.
    """
    index = {}
    for block, key in PLACE_SOURCES:
        for row in ((world.get(block) or {}).get(key) or []):
            if not isinstance(row, dict) or row.get('node') is None:
                continue
            uid = row.get('uid') if row.get('uid') is not None else row.get('id')
            if uid is None:
                continue
            index.setdefault(str(uid), {'node': row['node'], 'x': row.get('x'), 'z': row.get('z')})
    for ruin in (world.get('ruins') or []):
        if isinstance(ruin, dict) and ruin.get('node') is not None and ruin.get('id'):
            index.setdefault(str(ruin['id']), {'node': ruin['node'], 'x': ruin.get('x'), 'z': ruin.get('z')})
    return index


def locate(index, uid):
    """A presence uid to its node. Ruin presences name the city the ruin used to be, so the
    canonical `ruin-<city uid>` is tried as well before giving up."""
    if not uid:
        return None
    return index.get(str(uid)) or index.get(f'ruin-{uid}')


def _hamlet_name(plan, core):
    """`the farmstead below Alder`, the phrasing the cast already uses for the small sites."""
    word = 'harbour' if (plan.get('kind') == 'coastal' or 'harbor' in (plan.get('role') or '')) else 'farmstead'
    home = _short_name(core)
    return f'the {word} below {home}' if home else f"the {word} at node {plan.get('node')}"


def _fortress_name(core):
    home = _short_name(core)
    return f'the fortress above {home}' if home else 'the fortress'


def posts_in(row, buildings, notes):
    """Ordered posts standing in one site, senior first within each building.

    The plot exports `workers` as a count, not a breakdown, so the roster is expanded from the
    policy snapshot of the registry. When a size-block staffing override makes the two
    disagree, the plot's own count wins -- it is what the planner actually budgeted and housed
    -- and the difference is counted rather than hidden: a longer roster is truncated, a
    shorter one continues under its last role.
    """
    ordinals = {}
    posts = []
    for plot in sorted(row['plots'], key=_plot_order):
        building_id = plot.get('building_id')
        workers = plot.get('workers') or 0
        if not building_id or workers <= 0:
            continue
        roles = buildings.get(building_id)
        if not roles:
            continue
        expanded = [role for role, target in roles for _ in range(target)]
        if len(expanded) != workers:
            notes['roster_mismatches'] += 1
            if len(expanded) > workers:
                expanded = expanded[:workers]
            else:
                expanded += [expanded[-1]] * (workers - len(expanded))
        for index, role in enumerate(expanded):
            ordinal = ordinals.get(building_id, 0)
            ordinals[building_id] = ordinal + 1
            posts.append({'building_id': building_id, 'role': role, 'ordinal': ordinal,
                          'plot_id': str(plot.get('id') or ''), 'senior': index == 0 and ordinal == 0})
    return posts
