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
import math
import random
from dataclasses import replace
from importlib import import_module
from time import perf_counter

from .terrain_errors import (CLAMP, SCHEMA as ERROR_SCHEMA, SCHEMA_VERSION as ERROR_SCHEMA_VERSION,
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

# Why a quest closed. This is a published vocabulary -- `closed_reason` in
# `Contracts/schemas/read-quests.schema.json` is constrained to exactly these plus `null`
# -- and a consumer branches on it to tell a player what happened, so two reasons that
# read the same to a player are still two reasons here.
#
# `hook_gone` and `age_turned` are the pair that is easiest to collapse and must not be.
# `hook_gone` says *this hook* left `heroes.quest_hooks` while the world around it stood.
# `age_turned` says the world moved on: five thousand years passed, the cast was
# regenerated, and everyone who could have offered or populated the quest is gone. A
# consumer that cannot tell those apart cannot tell a player whether their quest went away
# or their age did.
#
# `abandoned` is written by `terrain_quest_actions`, not here; it is in the vocabulary
# because the vocabulary is the block's, not this module's.
AGE_TURNED = 'age_turned'
CLOSED_REASONS = ('expired', 'giver_gone', 'target_gone', 'hook_gone', AGE_TURNED,
                  'resolved', 'abandoned')

# Ley intensities drift 0.65..1.35 across one age transition (`terrain_history`). A year
# step must compose to that same band over an age rather than applying an age-sized shock
# once per year, so the per-year bounds are the age bounds taken to the power of one over
# the age's length in years.
#
# **The exponent is derived from `AGE_YEARS` and must never be written as a literal.** The
# two numbers are one contract: the pair that composes correctly over a century composes to
# `0.65 ** 50` -- about 2e-10 -- over the five thousand years an age now lasts, which is the
# magic layer draining to zero through ordinary ticking, silently, with every individual
# step inside its stated bounds. `LeyDriftCompositionTests` in `Sim/tests/test_time_advance.py`
# is the guard, and it is a guard against a future edit rather than against this line.
LEY_AGE_LOW, LEY_AGE_HIGH = .65, 1.35
LEY_YEAR_LOW = LEY_AGE_LOW ** (1. / schedule.AGE_YEARS)
LEY_YEAR_HIGH = LEY_AGE_HIGH ** (1. / schedule.AGE_YEARS)

# Recorded cost of **one age advance**, stated with its basis because a cost figure is
# description and not invariant.
#
# It used to be recorded *generation* cost -- 11 s / 30 MB at size 129 -- extrapolated by
# cell count to price a different pass entirely, and both halves had gone stale. The MB
# figure was the worse of the two: 30 MB at size 129 scales down to **0.5 MB at size 17**,
# where generation alone now peaks at 378 MB. Wrong by nearly three orders of magnitude,
# in the direction that tells a caller an expensive call is free.
#
# Measured 2026-09-21, seed 42, recipe 3, through phase 16, on the development machine
# with five other sessions sharing it, so **wall clock is an upper bound**: 34.3 s, 37.6 s
# and 39.4 s in three runs for one age at size 17, and 181.8 s at size 33.
#
# The seconds basis is the *larger* of the two points on purpose. An age advance grows
# faster than cell count between them -- 4.7x the time for 3.8x the cells -- so
# extrapolating from size 17 under-reports size 33 by a fifth, while extrapolating from 33
# over-reports 17 by about the same. A cost guard should err toward warning.
AGE_BASIS_SIZE = 33.
AGE_BASIS_SECONDS = 181.8
# **Memory has its own reference size, and that is deliberate rather than untidy.** The
# only memory figure available here is peak working set, and the machine was trimming
# working sets under load from the other sessions: the size-33 reading came back *smaller*
# per cell than the size-17 one, which is the instrument and not the world. So the
# size-17 reading is used -- 566 MB peak across a generation and one age advance, against
# 378 MB for the generation alone -- and it is a **lower** bound. Pretending both
# quantities share one reference would state a precision neither has.
AGE_BASIS_MB_SIZE = 17.
AGE_BASIS_MB = 566.

# What a tick costs, measured on the same worlds in the same runs. Two terms because the
# cost has two shapes, and a single-term model gets whichever one it omits badly wrong:
#
# - a fixed cost per call, which is the private deep copy every non-instant span makes.
#   It scales with the world and not with the span.
# - a marginal cost per cadence step, which scales with the span.
#
# Measured at size 17 (seed 42, phase 16): 18,057 steps in 1.15 s, 72,207 in 2.05 s,
# 361,007 in 6.15 s and 1,804,646 in 26.81 s -- a straight line, 14.2 us a step over a
# 1.0 s copy. The copy itself is 51 MB resident with `build_stages` shared rather than
# copied, as the code does it; a step tuple in the schedule's list is 132 bytes, measured
# over a century's 36,107 of them.
#
# **Both terms are scaled by cell count**, which the second point justifies rather than
# assumes: at size 33 the same spans took 4.30 s, 6.47 s, 19.26 s and 79.90 s, so the copy
# grew 3.2x and the per-step cost 3.0x for 3.8x the cells. Scaling both quadratically
# therefore over-reports size 33 by about a fifth, which is the safe direction for a
# figure a caller uses to decide whether to pay.
#
# **Steps are a proxy for cost and not cost** -- a coalesced pass runs once per call
# however many crossings it had, while the daily quest sweep runs every day -- so two
# spans with equal counts can differ, and an estimate built on this says so.
TICK_BASIS_SIZE = 17.
TICK_BASIS_COPY_SECONDS = 1.
TICK_BASIS_STEP_SECONDS = .0000142
TICK_BASIS_COPY_MB = 51.
TICK_BASIS_STEP_BYTES = 132.

# `advance_age_request` accepts 1..10 steps per call, so a longer run is chunked.
MAX_AGE_STEPS = 10
# And a run has to end. Each age rebuilds every derived layer, so an unbounded span
# is an unbounded loop: a million years is two hundred ages. Refused with the estimate
# attached rather than silently attempted.
#
# The number is unchanged by decision 028 and its meaning is not: fifty ages was five
# thousand years and is now two hundred and fifty thousand. Decision 028 leaves whether
# that is still the right ceiling open, and this change does not answer it either: it is
# kept beside `MAX_TICK_STEPS` rather than replaced by it, because a work ceiling and an
# ages ceiling refuse different things -- one prices a tick, the other bounds a loop of
# whole-world rebuilds this module does not execute itself.
MAX_AGES_PER_REQUEST = 50

# The most work one request executes as a tick before it is **reported** rather than
# attempted. Steps, because a step is what costs; years are what a caller asks in, and
# both are reported.
#
# This guard exists because the one the module had was on the wrong axis. `cost_estimate`,
# `age_gate` and the ages-per-request cap were all reached only when `band(days) == AGE`,
# so a span below that boundary was executed however long it was -- and decision 028 moved
# that boundary from a century to five thousand years, putting a fifty-fold cost increase
# on the unguarded side of it. A caller could ask for 4,999 years, get 1.8 million cadence
# steps, and reach none of the machinery built to say what that would cost.
#
# **An absolute count, and never a share of an age.** Writing it as a fraction of
# `AGE_DAYS` would re-couple the guard to the band boundary, which is the defect itself:
# how much work a machine can afford does not change when the calendar is redefined.
# `WorkCeilingTests.test_the_ceiling_is_an_absolute_count_and_not_a_share_of_an_age` is
# that assertion.
#
# 200,000 steps is about 554 years measured from day zero: roughly 3.8 s and 25 MB of
# transient step tuples at size 17, against a *measured* 26.8 s and 230 MB of them for the
# 4,999-year span the band permits. It is an order of magnitude above any span a game
# drives -- a century is 36,107 steps -- and an order of magnitude below the band's own
# maximum, so what it catches is a caller that did not know what it was asking for rather
# than a caller playing the game.
#
# **It does not scale with the world, and the estimate beside it does.** A step costs
# about three times as much on a size-33 world as on a size-17 one, so the same permitted
# span is 14 s there and would be far worse on a large grid. A ceiling read out of the
# cost model instead would move every time somebody re-measured -- the same request
# refused on Monday and run on Tuesday, with no constant edited -- which is worse than a
# ceiling that is honest about being one number. `tick_cost_estimate` carries the
# size-dependent figure, and the record says so.
#
# **It advises; it does not forbid.** `commit: true` proceeds, exactly as it does for the
# age band, so nothing a caller could do before is now impossible.
MAX_TICK_STEPS = 200000

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
    # hooks alone left an open quest for every hook that vanished, immortal and growing.
    # `hook_gone` is this hook leaving `heroes.quest_hooks` while the world around it stands
    # -- a resolved hook, a player edit, a caller trimming the block. An age turn is *not*
    # reaped here and never was reliably: `_turn_age_board` closes that board under its own
    # reason before the new age's first tick reaches this function.
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
                     # Both fallbacks are for a world generated before `heroes` version 2,
                     # which is the version that made the hook answer for itself. A
                     # pre-2 `target` is uid-or-node_id only, so a nest hook -- which
                     # carries `nest_id` -- anchored to null and named nothing at all;
                     # and a pre-2 ley hook had no `action` on its effect, so its verb
                     # read as null however the board was queried.
                     'anchor': (hook.get('target') or (hook.get('actual_effect') or {}).get('nest_id')),
                     'verb': (hook.get('verb') or (hook.get('actual_effect') or {}).get('action')),
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


def _turn_age_board(result, cfg, day):
    """Retire the quest board at an age turn and rebuild it from the new age's hooks.

    A quest does not cross an age. Five thousand years pass, `heroes` is regenerated
    wholesale, and the people who offered and populate an offer are gone, so every quest
    still open closes -- under `age_turned`, which is its own reason: the world moved on,
    rather than one hook having vanished from under it.

    **It does not depend on the id disappearing, and that is the whole point.** That is how
    reaping used to happen, and it was only mostly true. The regenerated cast re-mints
    positional uids -- `hero-reeve-hamlet-node-<n>`, `hero-sovereign-<city uid>` -- as the same
    string, so `by_hook.get(hook_id)` found a *different* hook wearing the old id and the
    quest carried on: the old age's `anchor`, `verb` and `stated_purpose`, the new age's
    target check, and a `giver_uid` naming someone who no longer exists. Measured 2026-09-21
    with all 49 open quests taken and one age advanced: 39 closed, **10 survived** as that
    chimera.

    **The previous age's rows are retired with it rather than kept beside the new ones**, for
    the same reason rather than for tidiness: a retained closed row whose id the new cast
    re-mints could not be told apart from the offer that id now names, and which rows
    survived would again be decided by an accident of uid minting. `quests.log` keeps every
    closure with its day and its reason, so why a quest ended outlives the board it stood on.

    Only a world that already carries a board gets one back. The quest lifecycle begins when
    a world is first ticked -- `POST /world/quests` refuses a world that has never been
    advanced, because no quests and no quest lifecycle are different facts -- and an age turn
    continues a lifecycle rather than starting one.
    """
    block = result.get('quests')
    if not isinstance(block, dict):
        return
    log = block.setdefault('log', [])
    for quest in block.get('quests') or []:
        if quest.get('state') in ('offered', 'taken'):
            quest['state'] = 'expired'
            quest['closed_day'] = day
            quest['closed_reason'] = AGE_TURNED
            log.append({'day': day, 'quest_id': quest.get('quest_id'), 'event': AGE_TURNED})
    block['quests'] = []
    from .terrain_liveness import liveness
    # Keyed on the day the age turned, like every other step in this module: the quests
    # cadence has a period of one day, so the absolute index of the sweep at `day` is
    # `floor(day)`. The next tick's window is half-open at the start and begins at
    # `floor(day) + 1`, so nothing is drawn twice and no offer opened here depends on how
    # the span that reached this age was cut.
    _quest_step(result, cfg, day, int(math.floor(day)), liveness, _giver_index(result))


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
    hour, and the honest answer is a figure with its basis attached. `measured` says
    whether **this world** has actually been advanced before: if it has, its own recorded
    cost is used, and if it has not, this extrapolates from a reference advance timed on a
    different world.

    The fallback used to extrapolate from *generation* cost, which is a different pass,
    and from constants recorded at size 129 that had gone stale in both halves. An age
    advance has now been timed directly, at sizes 17 and 33, so the fallback prices the
    operation it claims to price -- and it moved the size-17 answer from 0.19 s and 0.5 MB
    to 48 s and 566 MB, against a measured 34-39 s. It is still an extrapolation by cell
    count, still unmeasured above size 33, and the seconds and the megabytes take
    *different* reference sizes because only the seconds could be measured cleanly at
    both; `peak_mb_precision` says what the memory figure is worth.
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
        per_age = AGE_BASIS_SECONDS * (size / AGE_BASIS_SIZE) ** 2
        basis = ('extrapolated by cell count from age advances timed directly on 2026-09-21 '
                 '(34.3-39.4 s at size 17 and 181.8 s at size 33, seed 42 through phase 16, '
                 'on a contended development machine, so upper bounds); the seconds take '
                 'size 33 as the reference because the cost grows faster than cell count '
                 'between the two, and nothing has been timed above size 33')
        measured = False
    return {'ages': ages, 'per_age_seconds': round(per_age, 3),
            'total_seconds': round(per_age * ages, 3),
            'peak_mb': round(AGE_BASIS_MB * (size / AGE_BASIS_MB_SIZE) ** 2, 1),
            'peak_mb_precision': ('566 MB peak working set measured at size 17, '
                                  'extrapolated by cell count. The measurement is a lower '
                                  'bound, because the machine was trimming working sets '
                                  'under load; the extrapolation is an over-estimate of '
                                  'unknown size, because the two measured world documents '
                                  'grew 3.0x for 3.8x the cells rather than in step with '
                                  'them. Nothing above size 33 has been measured at all, '
                                  'and no age advance above size 33 has been run'),
            'basis': basis, 'measured': measured}


def tick_cost_estimate(world, days, steps):
    """What a tick would cost, before the caller commits to paying it.

    The age band's estimate has a sibling here because the work ceiling refuses on the
    tick path and a refusal without a price is half an answer. Unlike the age band's, this
    one is exact about *what* would run: `schedule.work` counts the crossings a span
    contains, so the step count is a fact and not a projection. Only the seconds and the
    megabytes are projected.

    Two terms, because the cost has two shapes. The private deep copy is paid once per
    call and scales with the world; the per-step cost is paid per crossing and does not.
    A single-term model gets whichever term it omits badly wrong, which is the mistake the
    age band's own basis constants made for a year.

    **Steps are a proxy for cost and not cost.** `add_encounters` coalesces to one run per
    call while the daily quest sweep runs every day, so two spans with equal step counts
    can differ by orders of magnitude, and `precision` says so rather than letting a
    rounded number imply otherwise.
    """
    size = float((world.get('config') or {}).get('size') or TICK_BASIS_SIZE)
    scale = (size / TICK_BASIS_SIZE) ** 2
    copy_seconds = TICK_BASIS_COPY_SECONDS * scale
    return {'steps': steps, 'elapsed_days': days,
            'elapsed_years': round(days / schedule.DAYS_PER_YEAR, 3),
            'total_seconds': round(copy_seconds + steps * TICK_BASIS_STEP_SECONDS * scale, 3),
            'copy_seconds': round(copy_seconds, 3),
            'per_step_seconds': TICK_BASIS_STEP_SECONDS * scale,
            'peak_mb': round(TICK_BASIS_COPY_MB * scale
                             + steps * TICK_BASIS_STEP_BYTES / 1048576., 1),
            'basis': ('measured 2026-09-21 on seed 42 through phase 16, on a contended '
                      'development machine: at size 17, 72,207 steps in 2.05 s and '
                      '1,804,646 in 26.81 s, so 14.2 us a step over a 1.0 s copy; at '
                      'size 33 the same spans took 6.47 s and 79.90 s, so both terms are '
                      'scaled by cell count, which over-reports size 33 by about a fifth'),
            'precision': ('order of magnitude; steps are a proxy for cost, because a '
                          'coalesced pass runs once per call however many crossings it '
                          'had while the daily quest sweep runs every day'),
            'measured': True}


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
                          'description': 'whether to pay a cost this boundary reported first'})

    world = body.get('world')
    cfg = validate_time_world(world)
    if edits and not cfg.magic_enabled:
        raise refused_by_world('leyline_edits', len(edits),
                               'This world was generated with magic disabled, so it has no ley '
                               'networks to edit.')

    started = perf_counter()
    now = clock(world)
    which = schedule.band(days)

    # What this request would execute **as a tick**, priced before anything is copied.
    #
    # Only the remainder after whole ages, because the ages themselves are delegated to
    # `advance_age_request` and are not ticked here; pricing them as cadence steps would
    # refuse every age advance for work it never does. Asked before the age branch rather
    # than inside it, so a span of ages *plus* an unaffordable remainder is reported
    # whole instead of advancing its ages and then baulking -- failure at this boundary is
    # all-or-nothing and a partial answer would be the one thing this module promises not
    # to produce.
    #
    # `schedule.work` counts crossings and allocates nothing, which is the point of its
    # existing: the span this guard is for is 1.8 million step tuples, and a guard that
    # had to build the list to price it would have paid the cost it exists to report.
    tick_days = days - schedule.ages_for(days) * schedule.AGE_DAYS if which == schedule.AGE else days
    tick_from = now['day'] + (days - tick_days)
    tick_steps = schedule.work(tick_from, tick_days)
    if tick_steps > MAX_TICK_STEPS and not commit:
        # Reported, not raised, and `commit` proceeds -- the age gate's shape, extended
        # down the bands it never reached. A caller that asked for a millennium deserves
        # the estimate and the reason together; an exception throws away the more useful
        # half, and a guard that quietly ran *less* than it was asked for would be the
        # band-selects-cadences data loss `terrain_time_schedule` documents at length.
        refusal = over_capacity('elapsed', tick_steps, MAX_TICK_STEPS, 'cadence steps per request')
        document = refusal.document()
        # `over_capacity` suggests clamping the field to the limit, which here would tell
        # a caller to send `elapsed` as a step count -- a unit this API does not accept.
        # The span that would fit, in days, is the value that actually works.
        #
        # Measured from the caller's *own* clock rather than from `tick_from`, so that
        # sending this value straight back is guaranteed to be accepted. A suggestion
        # computed from the day the ages would have ended is a suggestion about a request
        # the caller cannot make, and off by a step or two besides -- half-open windows
        # start where they start.
        fits = schedule.longest_span(now['day'], MAX_TICK_STEPS)
        document['suggestion'] = {'kind': CLAMP, 'value': {'days': fits},
                                  'note': 'the longest span from this world_clock that '
                                          'runs at most %d steps' % MAX_TICK_STEPS}
        document['cost_estimate'] = tick_cost_estimate(world, tick_days, tick_steps)
        out = copy.deepcopy(world)
        out['world_clock'] = now
        out['time_advance'] = {
            'api_version': TIME_API_VERSION, 'band': which, 'elapsed_days': days,
            'from_day': now['day'], 'to_day': now['day'] + days, 'steps': tick_steps,
            'ages': schedule.ages_for(days) if which == schedule.AGE else 0,
            'committed': False, 'blocked': document,
            'note': ('Estimate only. Send commit: true to run it anyway, or ask for at '
                     'most %g day(s).' % fits)}
        return out

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
        # The age turned, so the board does. Every quest still open closes as `age_turned`
        # and the board is rebuilt from the cast this age raised -- before the remainder
        # ticks, because the remainder is time spent in the new age.
        _turn_age_board(advanced, cfg, clock_after['day'])
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
