"""Advance a live world by an arbitrary span of elapsed time. Glue over `terrain_time_schedule`.

Stateless JSON API v1, in the shape the other runtime mutators already use: a world goes
in, a new world comes out, the caller persists it. There were seven such mutators and no
clock between them (`advance_age_request`, `corruption_request`, `cleanse_request`,
`visitation_request`, `nomad_request`, `lunar_request`, `patch_request`); this is that
clock, and `world_clock` is the authoritative now they can all read.

Which steps run is decided by `terrain_time_schedule`, which is pure and holds the
determinism argument. This module executes them, in the order that module returns, and
owns everything that touches a world: validation, the quest lifecycle, ley drift, the
route into an age advance, and the operation record.

**Failure is all-or-nothing.** Every pass runs against a private copy and the caller's
object is never touched; a raise leaves no half-advanced world anywhere. That guarantee is
nearly free in a world-in/world-out shape and expensive to retrofit once anything mutates
in place, so it is taken here rather than later.

**What this is not allowed to touch.** Terrain, water, climate, tectonics, biomes,
civilizations, settlements, roads, city/hamlet/castle plans and the ley *geometry* are
read-only below the age band: a tick moves the living layer over ground that does not
move. Only an age advance rebuilds ground, and this module reaches that by calling
`advance_age_request`, never by reimplementing it.
"""
import copy
import json
import random
from dataclasses import replace
from importlib import import_module
from time import perf_counter

from .terrain_errors import (SCHEMA as ERROR_SCHEMA, SCHEMA_VERSION as ERROR_SCHEMA_VERSION,
                             cross_field, invalid_choice, missing_block, over_capacity,
                             refused_by_world, retired_version, unknown_field,
                             unsupported_api, wrong_type)
from .terrain_leyline_history import edit_network
from .terrain_tectonics import child_seed
from .terrain_astrology import tide
from . import terrain_time_schedule as schedule

TIME_API_VERSION = 1
CLOCK_VERSION = 1
QUESTS_VERSION = 1

# An offer does not stand forever. The window is drawn once per quest from the step that
# created it, so it is a function of simulated time like everything else here, and a
# quest created at the same day by two differently chunked calls draws the same window.
OFFER_MIN_DAYS = 180.
OFFER_MAX_DAYS = 1080.

# Ley intensities drift 0.65..1.35 across one age transition (`terrain_history`). A year
# step must compose to that same band over an age rather than applying an age-sized shock
# a hundred times, so the per-year bounds are the age bounds taken to the power of one
# over the age's length in years.
LEY_AGE_LOW, LEY_AGE_HIGH = .65, 1.35
LEY_YEAR_LOW = LEY_AGE_LOW ** (1. / schedule.AGE_YEARS)
LEY_YEAR_HIGH = LEY_AGE_HIGH ** (1. / schedule.AGE_YEARS)

# Recorded generation cost, stated with its basis because a cost figure is description and
# not invariant: 11 s / 30 MB at size 129 and 42 s / 116 MB at size 257, seed 42, on the
# development machine. Cost scales with cell count, which is the square of the grid.
COST_BASIS_SIZE = 129.
COST_BASIS_SECONDS = 11.
COST_BASIS_MB = 30.

# `advance_age_request` accepts 1..10 steps per call, so a longer run is chunked.
MAX_AGE_STEPS = 10
# And a run has to end. Each age rebuilds every derived layer, so an unbounded span
# is an unbounded loop: five thousand years is fifty ages, a million years is ten
# thousand. Refused with the estimate attached rather than silently attempted.
MAX_AGES_PER_REQUEST = 50

# Every cadence maps to a pass with the same `(result, cfg)` signature, except the three
# this module implements itself because no pass exists for them.
CADENCE_PASSES = {
    'encounters': ('terrain_encounters', 'add_encounters'),
    'beast_movements': ('terrain_beast_movement', 'add_beast_movements'),
    'nomad_routes': ('terrain_nomad_routes', 'add_nomad_routes'),
    'nomads': ('terrain_nomads', 'add_nomads'),
    'nomad_effects': ('terrain_nomad_effects', 'apply_nomad_effects'),
    'seasonal_food': ('terrain_seasons', 'add_seasonal_food'),
}

# Passes that write into the ley networks themselves, so the derived field is stale after
# they run. `apply_nomad_effects` deepens every cult's circuit node through `edit_network`.
LEY_WRITING_PASSES = frozenset({'nomad_effects'})


def validate_time_world(world):
    """Check that a world can tick, and return its `Config`.

    Deliberately not `validate_age_world`. That answers a different question -- whether a
    world can advance an *age* -- and carries contract requirements a tick does not need,
    including its own grid ceiling. A world that cannot turn an age can still move its
    encounters and its quests, so the tick refuses only what it genuinely cannot do, and
    the age band asks the real gate rather than restating it (see `age_gate`).
    """
    from .terrain_lab import Config
    if not isinstance(world, dict):
        raise wrong_type('world', world,
                         {'type': 'object', 'description': 'a generated recipe 3 world document'})
    try:
        cfg = Config(**world['config'])
        if cfg.world_recipe != 3 or cfg.phase < 13:
            raise missing_block('config', 'Time advance requires a recipe 3 world generated through '
                                'creatures (phase 13); this world is recipe %s at phase %s.'
                                % (cfg.world_recipe, cfg.phase))
        if world['terrain']['version'] != 6 or world['generator_version'] != 16 or world['recipe']['version'] != 3:
            raise retired_version('world.generator_version', world.get('generator_version'), (16,))
        astrology = world.get('astrology')
        if not isinstance(astrology, dict) or astrology.get('version') != 1:
            raise missing_block('astrology', 'This world predates the moon contract and carries no sky '
                                'to advance; regenerate it with recipe_version 3.')
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise wrong_type('world', type(exc).__name__,
                         {'type': 'object',
                          'description': 'a complete recipe 3 world; ' + str(exc)}) from exc
    return cfg


def clock(world):
    """This world's `world_clock`, derived once for a world generated before it existed.

    A world with no clock is read at its founding year, which is the same day the age
    lottery already samples (`docs/astrology.md`), so adopting a clock does not move a
    world's position in time.
    """
    existing = world.get('world_clock')
    if isinstance(existing, dict) and existing.get('version') == CLOCK_VERSION:
        return dict(existing)
    from .terrain_astrology import reported_year
    year, source = reported_year(world)
    return {'version': CLOCK_VERSION, 'day': float(year) * schedule.DAYS_PER_YEAR,
            'age': len((world.get('history') or {}).get('ages') or []),
            'epoch_day': 0., 'derived_from': source}


def _timing(result):
    """Make `timing_ms` present before any pass writes into it.

    A world persisted by the CLI has it stripped, because timings are the only reason two
    runs of one seed differ and the interchange document is meant to be byte-reproducible
    (`cli.py:30`). Several passes then write `result['timing_ms'][...]` unguarded, so a
    persisted world raises `KeyError` before doing any work. This is a local mitigation so
    the tick works on the document a real consumer actually has; the general fix is
    `board/backlog/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md`, which must audit every writer
    rather than the one that happens to be reached first.
    """
    timing = result.setdefault('timing_ms', {})
    timing.setdefault('total', 0.)
    return timing


def _dedupe_warnings(result):
    """Keep `warnings` a set of statements rather than a tally of how often a pass ran.

    `add_seasonal_food` ends with `result['warnings'].append(...)`, so it is not quite the
    wholesale replacement the rest of its body is: every run leaves another copy of the
    same sentence. Run once at generation that is invisible; run on a cadence it turns a
    list of limitations into a counter, and it would differ between two chunkings of one
    span purely by how many calls were made.

    Order is preserved, and only exact repeats are dropped -- a warning this tick did not
    produce is never removed.
    """
    warnings = result.get('warnings')
    if not isinstance(warnings, list):
        return
    seen, out = set(), []
    for warning in warnings:
        key = json.dumps(warning, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(warning)
    result['warnings'] = out


def _apply_surge(result, day):
    """Recompute the lunar surge at `day`. Closed form, no state, no draw.

    The same two lines `refresh_astrology` applies, against the clock's day rather than
    the reported year, and using the same `tide` primitive so the two cannot disagree.
    A hidden school takes no surge and keeps no `surged_strength`; that asymmetry is the
    twelve-school contract and is not an oversight here.
    """
    magic = result.get('magic')
    astrology = result.get('astrology')
    if not isinstance(magic, dict) or not isinstance(astrology, dict):
        return
    factors = tide(astrology['moon'], day)
    for name, net in (magic.get('networks') or {}).items():
        if name in factors:
            net['surged_strength'] = net['strength'] * factors[name]
    magic['lunar_surge'] = {'day': day, 'factors': dict(factors),
                            'formula': 'surged_strength = strength * tide_school(day)'}


def _ley_drift(result, cfg, index):
    """One year of ley intensity drift, keyed on the absolute year index.

    The age transition's own drift is unchanged and still owns the age boundary. This is
    the same random walk at a year's granularity, composing to the same band across an
    age, so a world advanced by a hundred year-steps and one advanced by an age arrive at
    comparable intensities without either pretending to be the other.
    """
    if not cfg.magic_enabled:
        return False
    networks = (result.get('magic') or {}).get('networks') or {}
    moved = False
    for name, net in networks.items():
        rng = random.Random(child_seed(cfg.seed, 'time-ley-' + name, index))
        for item in net['nodes'] + net['edges']:
            item['intensity'] = min(4., item['intensity'] * rng.uniform(LEY_YEAR_LOW, LEY_YEAR_HIGH))
            moved = True
    return moved


def _villain_outlook(result, cfg):
    """Refresh the standing villain outlook without advancing the cast.

    A villain rises, holds or falls at an age boundary and nowhere else: `advance` reads
    the threat assessment an age inherited, so raising one mid-tick would let a villain be
    raised by its own damage. The outlook is a reading of present ground and is safe to
    refresh; the cast is not.
    """
    if 'villains' not in result:
        return
    from .terrain_villains import outlook
    from .terrain_world import options
    o = options(cfg)
    result['villains']['outlook'] = outlook(result, cfg, float(o.get('villain_rise', 0.)),
                                            float(o.get('villain_density', 3.)))


# ---------------------------------------------------------------- quests

def _giver_index(result):
    """`uid -> (record, block)` for everyone who can hold a quest open."""
    index = {}
    for key, block, listing in (('heroes', 'heroes', 'people'), ('heroes', 'dreads', 'dreads'),
                                ('npcs', 'npcs', 'people')):
        container = result.get(key)
        if not isinstance(container, dict) or container.get('status') != 'ok':
            continue
        for record in container.get(listing) or []:
            uid = record.get('uid')
            if uid is not None and uid not in index:
                index[uid] = (record, block)
    return index


def _target_present(result, effect):
    """Whether the thing a hook points at is still in the world.

    Only the kinds with an id set this module can resolve are tested. An unresolvable
    kind reads as present: a quest wrongly left open is a smaller lie than a quest
    silently reaped because this module did not recognise its target.
    """
    kind = effect.get('kind')
    uid = effect.get('uid')
    if kind == 'city':
        return any(site.get('uid') == uid for site in result.get('settlements', {}).get('sites', []))
    if kind == 'nest':
        nest_id = effect.get('nest_id', uid)
        return any(site.get('id') == nest_id for site in result.get('beast_nests', {}).get('sites', []))
    return True


def _quest_step(result, cfg, day, index, liveness_of, givers):
    """Open what the world now offers, and close what it no longer does.

    The world decides whether an offer still *stands*. It never decides whether a player
    succeeded: that arrives as a resolution from the game, because an outcome the world
    invented would be an outcome the player did not play.
    """
    heroes = result.get('heroes')
    hooks = (heroes or {}).get('quest_hooks') or [] if isinstance(heroes, dict) and heroes.get('status') == 'ok' else []
    block = result.setdefault('quests', {'version': QUESTS_VERSION, 'quests': [], 'log': []})
    block['version'] = QUESTS_VERSION
    tracked = {quest['quest_id']: quest for quest in block['quests']}
    by_hook = {hook['hook_id']: hook for hook in hooks}
    rng = random.Random(child_seed(cfg.seed, 'time-quests', index))
    # Walk the union: a hook the world no longer offers still has a quest to close. Walking
    # hooks alone left an open quest for every hook that vanished -- and an age transition
    # regenerates `heroes` wholesale, so that was roughly the whole board, immortal and
    # growing, every age.
    for hook_id in list(by_hook) + [q for q in tracked if q not in by_hook]:
        hook = by_hook.get(hook_id)
        quest = tracked.get(hook_id)
        if hook is None:
            if quest and quest['state'] in ('offered', 'taken'):
                quest['state'] = 'expired'
                quest['closed_day'] = day
                quest['closed_reason'] = 'hook_gone'
                block['log'].append({'day': day, 'quest_id': quest['quest_id'], 'event': 'hook_gone'})
            continue
        if quest is None:
            quest = {'quest_id': hook['hook_id'], 'giver_uid': hook['giver_uid'],
                     # The contract's anchor and verb, from fields the hook already
                     # carries. Difficulty is the quest generator's to emit and is not
                     # invented here.
                     # `target` is uid-or-node_id only, so a nest hook -- which carries
                     # `nest_id` -- anchored to null and named nothing at all.
                     'anchor': (hook.get('target') or (hook.get('actual_effect') or {}).get('nest_id')),
                     'verb': (hook.get('actual_effect') or {}).get('action'),
                     'stated_purpose': hook.get('stated_purpose'), 'unwitting': hook.get('unwitting', False),
                     'state': 'offered', 'offered_day': day,
                     'expires_day': day + rng.uniform(OFFER_MIN_DAYS, OFFER_MAX_DAYS),
                     'closed_day': None, 'closed_reason': None}
            tracked[quest['quest_id']] = quest
            block['quests'].append(quest)
        if quest['state'] not in ('offered', 'taken'):
            continue
        entry = givers.get(quest['giver_uid'])
        reason = None
        if entry is None or liveness_of(*entry) == 'gone':
            reason = 'giver_gone'
        elif not _target_present(result, hook.get('actual_effect') or {}):
            reason = 'target_gone'
        elif quest['state'] == 'offered' and day > quest['expires_day']:
            reason = 'expired'
        if reason:
            quest['state'] = 'expired'
            quest['closed_day'] = day
            quest['closed_reason'] = reason
            block['log'].append({'day': day, 'quest_id': quest['quest_id'], 'event': reason})
    block['quests'].sort(key=lambda quest: quest['quest_id'])
    return block


def _apply_resolutions(result, cfg, day, resolutions):
    """Record what the game says the player did, and apply what the hook already declares.

    A completed hook whose declared effect is a ley change applies it, because the hook
    states the school and the delta itself. Every other kind is recorded and nothing
    else: inventing a world consequence the hook does not declare would be this module
    deciding play.
    """
    block = result.get('quests')
    if not resolutions:
        return False
    if not isinstance(block, dict):
        raise missing_block('quests', 'This world carries no quests to resolve. Advance it by at '
                            'least one day first, which is what opens them.')
    by_id = {quest['quest_id']: quest for quest in block['quests']}
    hooks = {hook['hook_id']: hook for hook in ((result.get('heroes') or {}).get('quest_hooks') or [])}
    moved = False
    for item in resolutions:
        if not isinstance(item, dict):
            raise wrong_type('resolutions[]', item,
                             {'type': 'object',
                              'description': 'an object with quest_id and outcome'})
        extra = sorted(set(item) - {'quest_id', 'outcome'})
        if extra:
            raise unknown_field(extra[0], ('quest_id', 'outcome'), noun='resolution field')
        if item.get('outcome') not in ('completed', 'failed', 'abandoned'):
            raise invalid_choice('outcome', item.get('outcome'),
                                 {'choices': ['completed', 'failed', 'abandoned']})
        quest = by_id.get(item.get('quest_id'))
        if quest is None:
            raise unknown_field(str(item.get('quest_id')), sorted(by_id), noun='quest')
        if quest['state'] in ('completed', 'failed', 'abandoned', 'expired'):
            # Refused by the world, not malformed: the id was real and the caller is
            # simply late. The alternatives are the quests still open to resolve.
            raise refused_by_world('quest_id', quest['quest_id'],
                                   'Quest %s is already %s and cannot be resolved again.'
                                   % (quest['quest_id'], quest['state']),
                                   alternatives=[q['quest_id'] for q in block['quests']
                                                 if q['state'] in ('offered', 'taken')])
        quest['state'] = item['outcome']
        quest['closed_day'] = day
        quest['closed_reason'] = 'resolved'
        block['log'].append({'day': day, 'quest_id': quest['quest_id'], 'event': item['outcome']})
        effect = (hooks.get(quest['quest_id']) or {}).get('actual_effect') or {}
        if item['outcome'] == 'completed' and cfg.magic_enabled and 'school' in effect and 'intensity_delta' in effect:
            networks = result.get('magic', {}).get('networks') or {}
            net = networks.get(effect['school'])
            node_id = effect.get('node_id')
            if net is not None and node_id is not None:
                current = next((node['intensity'] for node in net['nodes'] if node['id'] == node_id), None)
                if current is not None:
                    target = min(4., max(0., current + float(effect['intensity_delta'])))
                    networks[effect['school']] = edit_network(net, node_id=node_id, intensity=target)
                    block['log'].append({'day': day, 'quest_id': quest['quest_id'], 'event': 'ley_applied',
                                         'school': effect['school'], 'node_id': node_id, 'intensity': target})
                    moved = True
    return moved


# ---------------------------------------------------------------- the age band

def cost_estimate(world, ages):
    """What an age advance would cost, before the caller commits to paying it.

    A caller asking for five thousand years has no idea whether that is a second or an
    hour, and the honest answer is a range with its basis attached. `measured` says
    whether this world has actually been advanced before: if it has, its own recorded
    cost is used, and if it has not, this is an extrapolation from *generation* cost,
    which is a different pass. Nobody has measured an age advance at size 513.
    """
    size = float(world['config']['size'])
    recorded = (world.get('timing_ms') or {}).get('age_advance_total')
    if recorded:
        # `age_advance_total` is the wall time of a whole call, and a call may have carried
        # up to ten ages. Dividing by the ages that call actually advanced is what makes it
        # a per-age figure; reading it raw reported a ten-age run as the cost of one.
        previous = [op for op in ((world.get('history') or {}).get('operations') or [])
                    if op.get('steps') or op.get('ages')]
        last = previous[-1] if previous else {}
        carried = max(1, int(last.get('ages') or last.get('steps') or 1))
        per_age = float(recorded) / 1000. / carried
        basis = ("this world's own recorded age_advance_total over the %d age(s) that call advanced"
                 % carried)
        measured = True
    else:
        per_age = COST_BASIS_SECONDS * (size / COST_BASIS_SIZE) ** 2
        basis = ('extrapolated from generation cost (11 s at size 129, 42 s at size 257, seed 42) '
                 'by cell count; an age advance itself has never been timed at any size')
        measured = False
    return {'ages': ages, 'per_age_seconds': round(per_age, 3),
            'total_seconds': round(per_age * ages, 3),
            'peak_mb': round(COST_BASIS_MB * (size / COST_BASIS_SIZE) ** 2, 1),
            'basis': basis, 'measured': measured}


def age_gate(world):
    """Why this world cannot advance an age, or `None` if it can.

    **Reported rather than raised, and that is deliberate.** A caller that asked for five
    thousand years deserves the estimate *and* the reason together; an exception would
    throw away the more useful half of the answer.

    But it carries the failure envelope's own document, so a caller branches on the same
    `code`, `field`, `received`, `expected` and `retry` fields it would get from a raised
    refusal, and can tell this apart from a malformed argument without reading prose. The
    shape is `refused_by_world`: the request was well formed and the world is the
    constraint. A caller that could not tell those apart would keep correcting a value
    that was never wrong -- here, by shortening a span that was perfectly legal.
    """
    from .terrain_history import validate_age_world
    try:
        validate_age_world(world)
    except ValueError as exc:
        # Whatever the age boundary refuses, reported in its own words. This used to
        # hard-code `size > 257` and name `validate_age_world` as the source -- a ceiling
        # that had already been raised to 1025, in a check that never contained the number.
        # A caller debugging it would have found nothing at the named location, and the
        # whole 258..1025 band was refused a span it would have advanced happily. Asking
        # the real predicate is the only version of this that cannot go stale again.
        # `validate_age_world` still wraps some refusals as a bare ValueError, so the
        # envelope is built here rather than assumed. A caller must get the same shape
        # whichever way the age boundary chose to complain.
        document = exc.document() if hasattr(exc, 'document') else {
            'schema': ERROR_SCHEMA, 'schema_version': ERROR_SCHEMA_VERSION,
            'code': 'INVALID_INPUT', 'message': str(exc), 'field': 'world',
            'received': None, 'expected': {'refused_by': 'world state'},
            'suggestion': {'kind': 'none'}, 'retry': False}
        document['gate'] = 'terrain_history.validate_age_world'
        return document
    return None


def _advance_ages(world, ages, moon_day):
    """Chain `advance_age_request` in chunks, because it accepts at most ten steps a call."""
    from .terrain_history import advance_age_request
    current = world
    done = 0
    while done < ages:
        steps = min(MAX_AGE_STEPS, ages - done)
        body = {'api_version': 1, 'world': current, 'steps': steps}
        if moon_day is not None:
            body['moon_day'] = moon_day
        current = advance_age_request(body)
        done += steps
    return current


def _instant(world, now, days, started):
    """A span shorter than a day: move the clock, resample the sky, copy nothing else.

    Only `magic` and `history` are rewritten, so only those are copied, and only as deeply
    as this writes into them. Everything else in the returned document is the caller's own
    object, shared rather than duplicated.
    """
    end_day = now['day'] + days
    result = dict(world)
    magic = world.get('magic')
    if isinstance(magic, dict):
        networks = {name: dict(net) for name, net in (magic.get('networks') or {}).items()}
        result['magic'] = {**magic, 'networks': networks}
    _apply_surge(result, end_day)
    after = dict(now)
    after['day'] = end_day
    after['age'] = len((world.get('history') or {}).get('ages') or [])
    result['world_clock'] = after
    history = dict(world.get('history') or {})
    history['operations'] = list(history.get('operations') or []) + [
        {'api_version': TIME_API_VERSION, 'kind': 'time', 'band': schedule.band(days),
         'elapsed_days': days, 'from_day': now['day'], 'to_day': end_day, 'steps': 0,
         'leyline_edits': [], 'resolutions': []}]
    history['replay'] = ('Persist this returned world for subsequent calls. Config reproduces genesis; '
                         'operation history records subsequent advances, player leyline edits and quest resolutions.')
    if days > 0:
        # A span that crosses nothing still moves the clock, and that is all it does. A game
        # asking what time it is every frame would otherwise append an operation per frame
        # and copy the whole log to do it -- an unbounded record of nothing happening, in
        # the one band built to be free.
        result['history'] = history
    plan = schedule.plan(now['day'], days)
    plan.update(api_version=TIME_API_VERSION, committed=True, leyline_edits=0, resolutions=0,
                leylines_evaluated=False)
    result['time_advance'] = plan
    result['time_api_version'] = TIME_API_VERSION
    result['timing_ms'] = {**(world.get('timing_ms') or {}),
                           'time_advance_total': (perf_counter() - started) * 1000}
    return result


# ---------------------------------------------------------------- the API

def advance_time_request(body):
    """Stateless JSON API v1: advance a supplied world by an elapsed span.

    Same input => same output, and the same span cut differently produces the same bytes.
    Persist the returned world to advance again; `Config` reproduces genesis, and
    `history.operations` records every advance since.
    """
    allowed = {'api_version', 'world', 'elapsed', 'leyline_edits', 'resolutions', 'commit', 'moon_day'}
    if not isinstance(body, dict):
        raise wrong_type('body', body, {'type': 'object', 'description': 'a request object'})
    if set(body) - allowed:
        raise unknown_field(sorted(set(body) - allowed)[0], sorted(allowed), noun='request field')
    if type(body.get('api_version')) is not int or body['api_version'] != TIME_API_VERSION:
        raise unsupported_api('api_version', body.get('api_version'), (TIME_API_VERSION,))
    days = schedule.elapsed_days(body.get('elapsed'))
    moon_day = body.get('moon_day')
    if moon_day is not None and (type(moon_day) is not int or moon_day < 0):
        raise wrong_type('moon_day', moon_day,
                         {'type': 'integer', 'min': 0,
                          'description': 'a whole day at or after founding year 0'})
    edits = body.get('leyline_edits', [])
    if not isinstance(edits, list):
        raise wrong_type('leyline_edits', edits,
                         {'type': 'array', 'description': 'a list of ley edits'})
    if len(edits) > 128:
        raise over_capacity('leyline_edits', len(edits), 128, 'edits per request')
    resolutions = body.get('resolutions', [])
    if not isinstance(resolutions, list):
        raise wrong_type('resolutions', resolutions,
                         {'type': 'array', 'description': 'a list of quest resolutions'})
    if len(resolutions) > 1024:
        raise over_capacity('resolutions', len(resolutions), 1024, 'resolutions per request')
    commit = body.get('commit', False)
    if type(commit) is not bool:
        raise wrong_type('commit', commit,
                         {'type': 'boolean',
                          'description': 'whether to actually advance the age band'})

    world = body.get('world')
    cfg = validate_time_world(world)
    if edits and not cfg.magic_enabled:
        raise refused_by_world('leyline_edits', len(edits),
                               'This world was generated with magic disabled, so it has no ley '
                               'networks to edit.')

    started = perf_counter()
    now = clock(world)
    which = schedule.band(days)

    # The age band answers before anything is copied: it either delegates wholesale or
    # reports why it cannot.
    if which == schedule.AGE:
        ages = schedule.ages_for(days)
        if ages > MAX_AGES_PER_REQUEST:
            # Without this a span of a million years loops ten thousand age advances, each
            # rebuilding every derived layer. The estimate is still returned, so a caller
            # learns the size of what it asked for rather than only that it was refused.
            refusal = over_capacity('elapsed', ages, MAX_AGES_PER_REQUEST, 'ages per request')
            document = refusal.document()
            document['cost_estimate'] = cost_estimate(world, ages)
            out = copy.deepcopy(world)
            out['world_clock'] = now
            out['time_advance'] = {'api_version': TIME_API_VERSION, 'band': schedule.AGE,
                                   'elapsed_days': days, 'from_day': now['day'], 'ages': ages,
                                   'committed': False, 'blocked': document,
                                   'note': 'Ask for fewer ages, or send several requests.'}
            return out
        estimate = cost_estimate(world, ages)
        blocked = age_gate(world)
        report = {'api_version': TIME_API_VERSION, 'band': schedule.AGE, 'elapsed_days': days,
                  'from_day': now['day'], 'ages': ages, 'cost_estimate': estimate,
                  'committed': False, 'note': 'A span of one age or longer is an age advancement, not a tick.'}
        if blocked:
            report['blocked'] = blocked
            out = copy.deepcopy(world)
            out['world_clock'] = now
            out['time_advance'] = report
            return out
        if not commit:
            report['note'] = ('Estimate only. Send commit: true to advance ' + str(ages)
                              + ' age(s), or ask for a shorter span to tick instead.')
            out = copy.deepcopy(world)
            out['world_clock'] = now
            out['time_advance'] = report
            return out
        advanced = _advance_ages(world, ages, moon_day)
        age_days = ages * schedule.AGE_DAYS
        clock_after = clock(advanced)
        clock_after['day'] = now['day'] + age_days
        clock_after['age'] = len(advanced['history']['ages'])
        advanced['world_clock'] = clock_after
        advanced['history'].setdefault('operations', []).append(
            {'api_version': TIME_API_VERSION, 'kind': 'time', 'band': schedule.AGE,
             'elapsed_days': age_days, 'ages': ages, 'from_day': now['day'],
             'to_day': clock_after['day']})
        remainder = days - age_days
        if remainder > 0 or edits or resolutions:
            # The span is ages *plus* a remainder, and the remainder is a tick. Dropping it
            # made `advance(150y)` differ from `advance(100y)` then `advance(50y)` -- a
            # counterexample to the invariant that needed no band table to produce -- and
            # left the operation log claiming an elapsed the clock never moved. Edits and
            # resolutions ride the same request rather than being validated and discarded.
            advanced = advance_time_request({
                'api_version': TIME_API_VERSION, 'world': advanced,
                'elapsed': {'days': remainder}, 'leyline_edits': edits,
                'resolutions': resolutions})
            report['remainder'] = advanced['time_advance']
        else:
            _apply_surge(advanced, clock_after['day'])
        report['committed'] = True
        report['elapsed_days'] = days
        report['age_days'] = age_days
        report['to_day'] = now['day'] + days
        report['age'] = clock_after['age']
        advanced['time_advance'] = report
        return advanced

    # The instant band writes four keys and runs nothing seeded, so it copies four keys.
    # A full deep copy costs the better part of two seconds on a size-33 world and grows
    # with the square of the grid; a game asking what time it is every frame cannot pay
    # that, and paying it to change a clock and twelve floats would make the band's whole
    # point -- that a moment is cheap because nothing can happen in it -- a fiction.
    #
    # Structural sharing is safe here in the one direction that matters: nothing below is
    # mutated in place, so the caller's world is unchanged. The returned document does
    # share its unwritten blocks with the caller's, the way `advance_age_request` already
    # shares `build_stages` entries for the same reason.
    executed = schedule.steps(now['day'], days)
    if not executed and not edits and not resolutions:
        # Keyed on "this span crosses nothing", not on "this span is short". The old test
        # was `band == INSTANT`, which let a sub-day call carrying a resolution fall through
        # to the full path and move the ley field -- the opposite of what the band promised.
        return _instant(world, now, days, started)

    # Every other span runs against a private copy. The caller's object is never touched,
    # and a raise anywhere leaves no half-advanced world behind.
    result = copy.deepcopy({k: v for k, v in world.items() if k != 'build_stages'})
    if 'build_stages' in world:
        result['build_stages'] = list(world['build_stages'])
    _timing(result)

    for edit in edits:
        if not isinstance(edit, dict):
            raise wrong_type('leyline_edits[]', edit,
                             {'type': 'object', 'description': 'a ley edit'})
        fields = ('school', 'node_id', 'line_id', 'intensity', 'new_node')
        extra = sorted(set(edit) - set(fields))
        if extra:
            raise unknown_field(extra[0], fields, noun='edit field')
        if 'new_node' in edit and 'intensity' in edit:
            raise cross_field('An edit that creates a node carries its intensity inside '
                              'new_node, not beside it.', ('new_node', 'intensity'))
        networks = result.get('magic', {}).get('networks') or {}
        if edit.get('school') not in networks:
            raise invalid_choice('school', edit.get('school'), {'choices': sorted(networks)})
        school = edit['school']
        networks[school] = edit_network(networks[school], **{k: v for k, v in edit.items() if k != 'school'})

    from .terrain_liveness import liveness
    ley_touched = bool(edits)
    # A tick never changes who exists -- the cast moves at an age boundary and nowhere
    # else -- so the index is built once rather than on each of a long span's daily
    # quest steps.
    givers = _giver_index(result)
    # Resolutions describe what the player did *before* this span, so they are applied
    # before it runs. Applying them at the end meant the world could expire a quest during
    # the very span the player spent completing it, and then refuse the completion.
    if resolutions:
        if 'quests' not in result:
            _quest_step(result, cfg, now['day'], 0, liveness, givers)
        if _apply_resolutions(result, cfg, now['day'], resolutions):
            ley_touched = True
    day = now['day']
    for day, name, index in executed:
        if name == 'quests':
            _quest_step(result, cfg, day, index, liveness, givers)
        elif name == 'ley_drift':
            # Only claim the field moved if it did. `_ley_drift` returns early on a world
            # with magic disabled, and setting the flag anyway sent a magicless world into
            # `evaluate_networks`, which indexes `result['magic']` and died on a bare
            # KeyError rather than any refusal this boundary knows how to make.
            ley_touched = _ley_drift(result, cfg, index) or ley_touched
        elif name == 'villain_outlook':
            _villain_outlook(result, cfg)
        else:
            module, func = CADENCE_PASSES[name]
            # A pass is a deterministic function of the world and the seed, so a
            # time-derived seed is what makes it move at all. Keyed on the absolute step
            # index, never on the call, so chunking cannot change which world it draws.
            stepped = replace(cfg, seed=child_seed(cfg.seed, 'time-' + name, index))
            getattr(import_module('.' + module, __package__), func)(result, stepped)
            _dedupe_warnings(result)
            if name in LEY_WRITING_PASSES:
                ley_touched = True

    end_day = now['day'] + days

    if ley_touched:
        # The expensive globe pass, at most once per request and only when the base field
        # actually moved. The surge below is a closed form and is free either way.
        from .terrain_leyline_history import evaluate_networks
        evaluate_networks(result, cfg)
    _apply_surge(result, end_day)

    after = dict(now)
    after['day'] = end_day
    after['age'] = len((result.get('history') or {}).get('ages') or [])
    result['world_clock'] = after

    plan = schedule.plan(now['day'], days)
    plan.update(api_version=TIME_API_VERSION, committed=True,
                leyline_edits=len(edits), resolutions=len(resolutions),
                leylines_evaluated=ley_touched)
    result['time_advance'] = plan
    result['time_api_version'] = TIME_API_VERSION
    history = result.setdefault('history', {})
    history.setdefault('operations', []).append(
        {'api_version': TIME_API_VERSION, 'kind': 'time', 'band': which, 'elapsed_days': days,
         'from_day': now['day'], 'to_day': end_day, 'steps': len(executed),
         'leyline_edits': copy.deepcopy(edits), 'resolutions': copy.deepcopy(resolutions)})
    history['replay'] = ('Persist this returned world for subsequent calls. Config reproduces genesis; '
                         'operation history records subsequent advances, player leyline edits and quest resolutions.')
    _timing(result)['time_advance_total'] = (perf_counter() - started) * 1000
    return result
