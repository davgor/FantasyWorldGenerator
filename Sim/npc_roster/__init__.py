"""NPC roster: the ordinary working population a finished world already implies, made addressable.

Every placed building in `city_plans`, `hamlet_plans` and `castle_plans` carries a staffing
roster, so the world has always known how many people it employs -- `docs/civilizations.md`
says outright that "each post assumes a different NPC" and that none is created. This package
creates them: one thin record per staffed post, plus the cast folded in, so a quest generator
has one list to ask "who here is worth talking to, and are they still alive".

It is a separate consumer package in the same mould as `hero_generator` and `story_web`:
called once with the finished world as plain JSON, it reads the three plan blocks, the
settlement and civilization reports and `heroes`, and writes only `npcs`. It never imports
`icarus_sim`, so a saved `world.json` serves it as well as a live result, and no generation
stage, seed or recipe moves on its account.

Two fields carry the whole point. `important` is the earmark -- the people worth naming, kept
to a bounded few per site so a consumer can scan them rather than walk the roster. `status` is
`alive` or `dead`, so a quest is never offered by a corpse. Everything else is the minimum
needed to say who someone is and where they stand.

What this package deliberately does not hold: traits, which are per-race constants owned by
`heritage` and joined through `civilization_id`; anything a quest decides; and any runtime
state. The block is birth state and is never mutated -- `validate_repo` generates a world
twice and byte-compares, so a mutating block would fail the build.
"""
import os

from .naming import name_for, name_with_gloss, reset_cache
from .policy import load_all, revisions
from .seeds import rng
from .sites import collect, locate, places, posts_in

VERSION = 1
ENV_SWITCH = 'FANTASY_WORLD_NPCS'
# Cast uids already begin `hero-` or `dread-`, so one prefix is enough to say whose namespace
# a roster uid belongs to without reading `npc-hero-hero-castellan-...`.
HERO_UID_PREFIX = 'npc-'
METHOD = ('Walk the three plan blocks. Every placed plot with a positive worker count expands into that many '
          'posts, senior first, using the policy snapshot of the building registry; the plot\'s own count wins '
          'when a civilization overrides the roster. Each post becomes one person, named from a seeded draw and '
          'keyed npc-<site>-<building>-<ordinal>, where the site is the stable city uid for a city and the node '
          'for a hamlet or fortress, because the ordinal plan ids renumber on every age advance. Every hero and '
          'Dread is folded in as a record cross-linked by hero_uid, alive while the cast calls them living. The '
          'earmark is authored, not rolled: every hero, plus the senior post of the highest-ranked giver '
          'buildings a site has, capped per site so the important subset stays bounded.')
LIMITS = ('An index of posts, not a simulation of people: nobody here works, moves, ages or dies of anything. '
          'status is birth state -- alive for every staffed post, dead only for a hero the cast has passed into '
          'legend -- and a runtime is expected to copy the block into its own save and flip it there; nothing '
          'writes back. Names are an interim parent-race syllable draw, so nine of the twelve cultures read as '
          'their parent until the heritage language genome replaces them. A site anchored on its node reuses the '
          'key if that hamlet is abandoned and another is later founded on the same node, which points a quest '
          'at the right place with the wrong history; that is the residue of anchoring positionally, and it is '
          'much smaller than the annual renumbering it replaces. Posts are drawn from the registry roster, so '
          'they are the jobs a building needs filled, not a census: dependents, children and the unemployed are '
          'not here, and neither is anyone in a ruin, camp, college or nest.')


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
    """The roster for a finished world whose cities, hamlets and castles have been planned."""
    seed = _validate(world)
    policies = policies or load_all()
    posts_policy = policies['posts']
    rows, notes = collect(world)
    rank = {building: index for index, building in enumerate(posts_policy['giver_rank'])}
    caps = posts_policy['caps']
    verbed = _verbed(posts_policy)

    sites, people = [], []
    for row in rows:
        posts = posts_in(row, posts_policy['buildings'], notes)
        important = _earmark(posts, rank, caps, row, notes, verbed)
        for post in posts:
            uid = f"npc-{row['uid']}-{_short(post['building_id'])}-{post['ordinal']}"
            people.append({'uid': uid,
                           'name': (name_for(row['civilization_id'], row['parent_race_id'],
                                             rng(seed, 'npc-name-' + uid))
                                    if row['parent_race_id'] else None),
                           'site_uid': row['uid'], 'site_kind': row['kind'], 'post': post['role'],
                           'building_id': post['building_id'], 'plot_id': post['plot_id'],
                           'status': 'alive', 'important': uid in important})
        sites.append({'uid': row['uid'], 'kind': row['kind'], 'name': row['name'],
                      'civilization_id': row['civilization_id'], 'parent_race_id': row['parent_race_id'],
                      'city_class': row['city_class'], 'plan_id': row['plan_id'], 'node': row['node'],
                      'x': row['x'], 'z': row['z'], 'plan_status': row.get('plan_status'),
                      'posts': len(posts)})

    people.extend(_cast(world, {row['uid']: row['kind'] for row in rows}, notes))
    people.sort(key=lambda person: (person['site_uid'] or '~', person['building_id'] or '~', person['uid']))
    alive = sum(person['status'] == 'alive' for person in people)
    important = sum(person['important'] for person in people)
    linked = sum('hero_uid' in person for person in people)
    return {'version': VERSION, 'status': 'ok', 'policy_revision': revisions(policies),
            'registry': _registry(world),
            'summary': {'total': len(people), 'alive': alive, 'dead': len(people) - alive,
                        'important': important, 'important_fraction': round(important / len(people), 4) if people else 0.,
                        'sites': len(sites), 'heroes_linked': linked, **notes},
            'sites': sites, 'people': people,
            # Copied, not aliased: the policy document is cached and shared, so exporting its
            # own lists would let a consumer mutating the block corrupt every later roster.
            'post_verbs': {role: list(verbs) for role, verbs in sorted(posts_policy['role_verbs'].items())},
            'verbs': list(posts_policy['verbs']),
            'method': METHOD, 'limits': LIMITS}


def _registry(world):
    """The building registry this roster's post labels were resolved against.

    The labels come from a snapshot of `buildings.json` carried in the policy, because this
    package must not import the generator. A per-civilization size-block `staffing` override
    replaces the library roster for that entry alone, and no override exists today -- so the
    snapshot is correct now and could silently mislabel one civilization's posts later. Naming
    the world's own registry identity beside the snapshot's is what makes that visible: when
    the two revisions differ, the labels were resolved against a registry this policy has not
    been re-linted for. The block reports it rather than failing, because the registry revision
    moves for reasons that have nothing to do with staffing.
    """
    identity = (world.get('civilizations') or {}).get('registry') or {}
    return {'world_revision': identity.get('revision'), 'world_sha256': identity.get('sha256'),
            'labels_from': 'npc_roster.policies.posts'}


def _short(building_id):
    """`building.smithy` reads as `smithy` in a uid; the prefix is constant and costs 12,000 copies."""
    return building_id.split('.', 1)[-1]


def _earmark(posts, rank, caps, row, notes, verbed):
    """The bounded important subset for one site: senior posts of its best-ranked giver buildings.

    The cap is per site and authored, so the important set cannot drift upward when a
    civilization's preset grows a building -- the consumer scans this subset instead of walking
    the roster, so its boundedness is a contract. Heroes are earmarked separately and are never
    subject to this cap; a cap that could silently demote a hero would be the bug.
    """
    cap = caps.get(row['city_class']) if row['kind'] == 'city' else caps.get(row['kind'])
    if not cap:
        return set()
    candidates = [post for post in posts if post['senior'] and post['building_id'] in rank
                  and post['role'] in verbed]
    candidates.sort(key=lambda post: (rank[post['building_id']], post['building_id']))
    notes['important_capped_out'] += max(0, len(candidates) - cap)
    return {f"npc-{row['uid']}-{_short(post['building_id'])}-{post['ordinal']}" for post in candidates[:cap]}


def _cast(world, site_kinds, notes):
    """Heroes and Dreads as roster records, so one list answers who can give a quest.

    They keep their own uids in `heroes`; these are separate records that cross-link, because
    the cast package owns its namespace and nothing here should bend it.

    A hero is not a staffed post, and three things follow that the schema has to allow rather
    than pretend away. `presence` may be absent entirely -- every legend, and the living but
    dispossessed -- so `site_uid` is null for them. A presence may stand somewhere this block
    has no row for: a camp, ruin, college, port, shrine or nest. And `post` is the person's
    role, not a job in a building, so `building_id` is null. `presence_kind` carries the cast's
    own word for where they are, so a consumer can resolve it against the block that owns it
    instead of inferring a kind from a uid that this package never minted.
    """
    heroes = world.get('heroes')
    if not isinstance(heroes, dict) or heroes.get('status') != 'ok':
        return []
    index = places(world)
    records = []
    for person in (heroes.get('people') or []) + (heroes.get('dreads') or []):
        uid = person.get('uid')
        if not uid:
            continue
        presence = person.get('presence') or {}
        home = (person.get('home') or {}).get('uid')
        site_uid = next((c for c in (home, presence.get('uid')) if c in site_kinds), None)
        if site_uid is None:
            notes['cast_outside_a_planned_site'] += 1
        record = {'uid': HERO_UID_PREFIX + str(uid),
                  'name': person.get('display_name') or person.get('name') or str(uid),
                  'site_uid': site_uid, 'site_kind': site_kinds.get(site_uid),
                  'post': person.get('role') or 'hero', 'building_id': None, 'plot_id': '',
                  'status': 'alive' if person.get('status') == 'living' else 'dead',
                  'important': True, 'hero_uid': str(uid),
                  'presence_kind': presence.get('site_kind'), 'presence_uid': presence.get('uid')}
        # Where they actually stand, whenever that is not the site they were filed under. A
        # castellan filed at their home city because their fortress keys differently is a real
        # place and the wrong one; anything measuring travel needs the node, not the fallback.
        if presence.get('uid') and presence.get('uid') != site_uid:
            where = locate(index, presence['uid'])
            if where:
                record['presence_node'] = where['node']
                if where['x'] is not None:
                    record['presence_x'], record['presence_z'] = where['x'], where['z']
                notes['cast_located_by_presence'] += 1
            else:
                notes['cast_presence_unresolved'] += 1
        records.append(record)
    return records


def _validate(world):
    if not isinstance(world, dict) or type((world.get('config') or {}).get('seed')) is not int:
        raise ValueError('the npc roster needs a finished world with an integer config.seed')
    if not any(isinstance(world.get(block), dict) for block in ('city_plans', 'hamlet_plans', 'castle_plans')):
        raise ValueError('the npc roster needs at least one planned block; run the planners first')
    return int(world['config']['seed'])


def summary_lines(block):
    """Short human lines for logs and the lab status."""
    if block.get('status') != 'ok':
        return [f"npc roster failed: {block.get('error')}"]
    s = block['summary']
    lines = [f"{s['total']} people across {s['sites']} sites · {s['alive']} alive · {s['dead']} dead · "
             f"{s['important']} important ({s['important_fraction']:.1%}) · {s['heroes_linked']} linked to the cast"]
    for note, count in sorted(s.items()):
        if note.endswith(('mismatches', 'sites', 'keys', 'race', 'site')) and isinstance(count, int) and count:
            lines.append(f"  {note.replace('_', ' ')}: {count}")
    return lines


def _verbed(posts_policy):
    """Roles the policy gives a verb: a role with none can hold a post but never be a giver.

    Resolved once per generate from the policy actually in use, rather than cached at import.
    An import-time cache that swallowed a broken policy would leave every role unverbed and
    earmark nobody, which looks like a quiet world rather than a failure.
    """
    return {role for role, verbs in posts_policy['role_verbs'].items() if verbs}
