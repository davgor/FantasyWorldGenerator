"""Opt-in wall-clock and resident-memory profile of one generation run.

Why this exists as its own module rather than as timings written by each pass: the
generator already writes about two dozen `timing_ms` scalars, and they answer the wrong
question. They are a flat bag keyed by subsystem, several of them are *cumulative across
every call in the run*, and none of them says which of the sixteen stages the cost landed
in. A flat bag cannot tell you that stage 5 pays for stages 1-4 again, or that one pass
ran eleven times. This module records the run as a tree: stage -> step -> nested step,
with call counts, self time and total time kept apart.

Three properties it is built to have.

- **Free when off.** Nothing here runs, and no wrapper is installed, unless a caller opens
  `profile_run()`. `begin`/`mark`/`end` are three attribute reads and a `None` test on the
  ordinary path, which is what `terrain_history.generate_history` pays to carry the hooks.
- **Content-neutral.** Every wrapper is a pass-through: same arguments, same return value,
  same exceptions, same order. It cannot move a seed or a float, so a profiled world is
  byte-identical to an unprofiled one once `timing_ms` is stripped, and `tests/
  test_stage_profile.py` pins that equality rather than asserting it here in a comment.
- **Honest about its blind spots.** The step table is a fixed list of named targets. A
  target that no longer exists is reported in `missing_targets` rather than skipped
  quietly, because a step that silently stops being measured reads exactly like a step
  that got fast.

The one thing it deliberately does not do is wrap per-cell functions (`layout_point`,
`perlin3`, `direction`). At size 128 those are called tens of millions of times and the
wrapper would cost more than the body, so they are left inside their caller's self time.
Read a large self time on a physical pass as "the per-cell loops", not as unexplained.
"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from contextlib import contextmanager
from time import perf_counter

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a reporting nicety, never a dependency
    psutil = None


# Named pipeline steps, as (module, attribute) inside the `icarus_sim` package or a
# sibling top-level package. Order here is documentation only; wrapping is by name.
#
# The list is coarse on purpose: one entry per pass a person could plausibly go and
# optimise, and nothing that runs per cell. Anything not named here stays in the self
# time of whichever named step called it.
STEP_TARGETS = (
    # Stages 1-5: the physical base, rebuilt from scratch once per stage.
    ('icarus_sim.terrain_lab', 'generate_base'),
    ('icarus_sim.terrain_tectonics', 'generate_tectonics'),
    ('icarus_sim.terrain_tectonics', 'make_plates'),
    ('icarus_sim.terrain_erosion', 'erode'),
    ('icarus_sim.terrain_ecology', 'shape_islands'),
    ('icarus_sim.terrain_area', 'apply_world_scale'),
    ('icarus_sim.terrain_globe', 'measure_globe'),
    ('icarus_sim.terrain_water', 'add_water'),
    # Stages 6-7: the second tectonic epoch and the relic cut.
    ('icarus_sim.terrain_history', 'tectonic_transition'),
    ('icarus_sim.terrain_history', 'carve_relics'),
    ('icarus_sim.terrain_history', 'measure_surface'),
    # Stage 8: climate, labels, ecology, ground detail.
    ('icarus_sim.terrain_climate', 'add_climate'),
    ('icarus_sim.terrain_biomes', 'add_terrain_labels'),
    ('icarus_sim.terrain_ecology', 'add_environment'),
    ('icarus_sim.terrain_detail', 'attach_detail'),
    # Stage 9: leylines and the sky.
    ('icarus_sim.terrain_leyline_history', 'generate_networks'),
    ('icarus_sim.terrain_leyline_history', 'evaluate_networks'),
    ('icarus_sim.terrain_astrology', 'add_astrology'),
    ('icarus_sim.terrain_astrology', 'refresh_astrology'),
    ('icarus_sim.terrain_history', 'refresh_environment'),
    ('icarus_sim.terrain_history', 'add_biome_variants'),
    # Stages 10-12: civilization, in three passes over the same body.
    ('icarus_sim.terrain_history', 'civilization'),
    ('icarus_sim.terrain_settlements', 'add_settlements'),
    ('icarus_sim.terrain_humans', 'add_humans'),
    ('icarus_sim.terrain_magic', 'add_colleges'),
    ('icarus_sim.terrain_seasons', 'add_seasonal_food'),
    ('icarus_sim.terrain_society', 'add_world_society'),
    # Stage 13: creatures, threat, religion.
    ('icarus_sim.terrain_nests', 'add_nests'),
    ('icarus_sim.terrain_history', 'add_threat_assessments'),
    ('icarus_sim.terrain_religion', 'add_religion'),
    # Stages 14-15: the two age transitions.
    ('icarus_sim.terrain_history', 'age_transition'),
    # Runs once per surviving city per age, between the two `add_nests` calls, and reads
    # the nest field the first one wrote. It is the reason that pair is two calls and not
    # one, so the profile names it.
    ('icarus_sim.terrain_history', 'city_fate'),
    ('icarus_sim.terrain_history', 'rebuild_tail'),
    ('icarus_sim.terrain_villains', 'promote'),
    ('icarus_sim.terrain_villains', 'build'),
    # Stage 16: the planners and the four satellite packages.
    ('icarus_sim.city_planner', 'fill_cities'),
    ('icarus_sim.hamlet_planner', 'fill_hamlets'),
    ('icarus_sim.castle_planner', 'fill_castles'),
    ('icarus_sim.terrain_nomads', 'add_nomads'),
    ('icarus_sim.terrain_nomad_routes', 'add_nomad_routes'),
    ('icarus_sim.terrain_beast_movement', 'add_beast_movements'),
    ('icarus_sim.terrain_encounters', 'add_encounters'),
    ('icarus_sim.terrain_nomad_effects', 'apply_nomad_effects'),
    ('icarus_sim.terrain_history', '_attach_heroes'),
    ('icarus_sim.terrain_history', '_attach_story_web'),
    ('icarus_sim.terrain_history', '_attach_npcs'),
    ('icarus_sim.terrain_history', '_attach_key_locations'),
    ('icarus_sim.terrain_history', '_attach_key_location_plans'),
    # Closeout.
    ('icarus_sim.world_debug', 'build_debug'),
)

PROFILE_VERSION = 1

_ACTIVE = None


def active():
    """The open `Run`, or None. The hooks in `generate_history` test this and return."""
    return _ACTIVE


def _rss_mb():
    if psutil is None:
        return None
    info = psutil.Process().memory_info()
    return round(info.rss / 1048576., 1)


def _peak_mb():
    if psutil is None:
        return None
    info = psutil.Process().memory_info()
    # `peak_wset` is Windows-only; on POSIX the high-water mark is not in memory_info at
    # all, so the report carries a null rather than a number meaning something else.
    peak = getattr(info, 'peak_wset', None)
    return None if peak is None else round(peak / 1048576., 1)


class Run:
    """One profiled generation. Holds the stage table and the step tree."""

    def __init__(self, progress=None):
        # A 128-cell run is hours long. Without a line per stage the only two states a
        # watcher can distinguish are "running" and "finished", and a stage that has
        # hung looks exactly like a stage that is slow.
        self.progress = progress
        self.started = perf_counter()
        self.stages = []
        self.missing_targets = []
        self.steps = {}           # (stage, label) -> record
        self._stack = []          # open steps: [label, start, children_total]
        self._stage = None
        self._timing_seen = {}
        self._patched = []
        self.subject = subject_digest()

    # ---------------------------------------------------------------- stages

    def begin(self, number, title):
        self._stage = {'stage': number, 'title': title,
                       'body_ms': 0., 'capture_ms': 0., 'wall_ms': 0.,
                       'rss_mb': None, 'rss_delta_mb': None, 'peak_rss_mb': None,
                       'snapshot_layers': 0, 'snapshot_state_keys': 0,
                       'layers_after': 0, 'subsystem_ms': {}}
        self._stage_started = perf_counter()
        self._stage_rss = _rss_mb()
        self._marked = None

    def mark(self):
        """Split the stage: everything before this is body, everything after is capture."""
        if self._stage is not None:
            self._marked = perf_counter()

    def end(self, result, snapshots=None):
        stage = self._stage
        if stage is None:
            return
        now = perf_counter()
        stage['wall_ms'] = (now - self._stage_started) * 1000.
        split = self._marked if self._marked is not None else now
        stage['body_ms'] = (split - self._stage_started) * 1000.
        stage['capture_ms'] = (now - split) * 1000.
        rss = _rss_mb()
        stage['rss_mb'] = rss
        stage['peak_rss_mb'] = _peak_mb()
        if rss is not None and self._stage_rss is not None:
            stage['rss_delta_mb'] = round(rss - self._stage_rss, 1)
        layers = (result or {}).get('layers') or {}
        stage['layers_after'] = len(layers)
        if snapshots:
            entry = snapshots[-1]
            stage['snapshot_layers'] = len(entry.get('layers') or {})
            stage['snapshot_state_keys'] = len(entry.get('state') or {})
        stage['subsystem_ms'] = self._subsystem_delta(result)
        self.stages.append(stage)
        self._stage = None
        if self.progress is not None:
            self.progress(stage, self)

    def _subsystem_delta(self, result):
        """How much each pre-existing flat `timing_ms` scalar moved during this stage.

        Those scalars are a mixture: some are overwritten by their pass each call, some
        are accumulated. A delta is therefore not always "the cost inside this stage" --
        an overwritten key reports its last call only. They are carried because they name
        costs the step table does not reach into, and they are labelled `subsystem_ms`
        rather than anything implying a decomposition of `wall_ms`.
        """
        delta = {}
        timing = (result or {}).get('timing_ms') or {}
        for key, value in timing.items():
            if not isinstance(value, (int, float)):
                continue
            previous = self._timing_seen.get(key)
            if previous is None or abs(value - previous) > 1e-9:
                delta[key] = round(float(value), 3) if previous is None else round(float(value) - previous, 3)
            self._timing_seen[key] = float(value)
        delta.pop('total', None)
        return delta

    # ---------------------------------------------------------------- steps

    @contextmanager
    def step(self, label):
        stage = self._stage['stage'] if self._stage else 0
        started = perf_counter()
        self._stack.append([label, started, 0.])
        try:
            yield
        finally:
            _, _, children = self._stack.pop()
            total = (perf_counter() - started) * 1000.
            if self._stack:
                self._stack[-1][2] += total
            key = (stage, label)
            record = self.steps.get(key)
            if record is None:
                record = self.steps[key] = {'stage': stage, 'label': label, 'calls': 0,
                                            'total_ms': 0., 'self_ms': 0., 'max_ms': 0.}
            record['calls'] += 1
            record['total_ms'] += total
            record['self_ms'] += total - children
            record['max_ms'] = max(record['max_ms'], total)

    # ---------------------------------------------------------------- wrapping

    def install(self):
        for module_name, attribute in STEP_TARGETS:
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                self.missing_targets.append(module_name + '.' + attribute + ' (module)')
                continue
            original = getattr(module, attribute, None)
            if original is None or not callable(original):
                self.missing_targets.append(module_name + '.' + attribute)
                continue
            self._patched.append((module, attribute, original))
            setattr(module, attribute, self._wrap(module_name, attribute, original))

    def _wrap(self, module_name, attribute, original):
        label = module_name.split('.')[-1] + '.' + attribute
        run = self

        def wrapped(*args, **kwargs):
            with run.step(label):
                return original(*args, **kwargs)

        wrapped.__name__ = getattr(original, '__name__', attribute)
        wrapped.__doc__ = getattr(original, '__doc__', None)
        wrapped.__wrapped__ = original
        return wrapped

    def remove(self):
        for module, attribute, original in reversed(self._patched):
            setattr(module, attribute, original)
        self._patched = []

    # ---------------------------------------------------------------- report

    def report(self, label=''):
        total = sum(s['wall_ms'] for s in self.stages)
        steps = sorted(self.steps.values(), key=lambda r: (r['stage'], -r['self_ms']))
        for record in steps:
            for key in ('total_ms', 'self_ms', 'max_ms'):
                record[key] = round(record[key], 3)
        for stage in self.stages:
            # Round the whole and the body, then take the capture as the remainder. Rounding
            # all three independently leaves body + capture off wall by up to a millisecond,
            # and a split that does not close is a split a reader cannot trust.
            stage['wall_ms'] = round(stage['wall_ms'], 3)
            stage['body_ms'] = round(stage['body_ms'], 3)
            stage['capture_ms'] = round(stage['wall_ms'] - stage['body_ms'], 3)
            stage['share'] = round(stage['wall_ms'] / total, 4) if total else 0.
        return {'version': PROFILE_VERSION, 'label': label, 'subject': self.subject,
                'wall_ms': round((perf_counter() - self.started) * 1000., 3),
                'stage_wall_ms': round(total, 3),
                'peak_rss_mb': _peak_mb(), 'rss_mb': _rss_mb(),
                'psutil': psutil is not None,
                'stages': self.stages, 'steps': steps,
                'missing_targets': self.missing_targets}


def subject_digest():
    """Which tree these numbers describe: a digest per measured module, and one overall.

    A cost figure names its seed, its size and its machine. It also has to name the code,
    and that is the one a shared tree makes easy to get wrong: a report taken at 01:45
    against a module somebody rewrote at 02:18 reads exactly like a report of the new
    module, and the only thing that distinguishes them is a hash nobody recorded. So the
    report records one, per module in STEP_TARGETS, at the moment the run opens.
    """
    # Repo-relative, so a digest key is the same string `coverage.json`, the conformance
    # records and a `git diff` use. A key relative to Sim/ would name the same file in a
    # spelling nothing else in this repository uses.
    root = Path(__file__).resolve().parents[2]
    digests = {}
    for module_name, _ in STEP_TARGETS:
        relative = 'Sim/' + module_name.replace('.', '/') + '.py'
        path = root / relative
        if not path.is_file():
            continue
        digests[relative] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    combined = hashlib.sha256(
        ''.join(k + digests[k] for k in sorted(digests)).encode('utf-8')).hexdigest()[:16]
    return {'modules': digests, 'combined': combined}


@contextmanager
def profile_run(progress=None):
    """Profile every generation that runs inside this block. Not reentrant, not threaded.

    `progress` is called with (stage_record, run) as each stage closes.
    """
    global _ACTIVE
    if _ACTIVE is not None:
        raise RuntimeError('a generation profile is already open; they do not nest')
    run = Run(progress)
    _ACTIVE = run
    run.install()
    try:
        yield run
    finally:
        run.remove()
        _ACTIVE = None


# ------------------------------------------------------------------ hooks
# Called unconditionally from `terrain_history.generate_history`. When no profile is open
# these are a global read and a `None` test, which is the whole cost of carrying them.

def begin(number, title):
    if _ACTIVE is not None:
        _ACTIVE.begin(number, title)


def mark():
    if _ACTIVE is not None:
        _ACTIVE.mark()


def end(result, snapshots=None):
    if _ACTIVE is not None:
        _ACTIVE.end(result, snapshots)
