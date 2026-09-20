# SDET-PRODUCER-CALL-GRAPH — the measured call graph, and the timing that could not be taken

Owner: none. State: **call graph measured and recorded; the timing half is unrun and item 4
remains open.** Evidence is the graph below, taken by instrumenting the producers and running
one generation. Reproduce in fifteen lines — see Acceptance.

Two things are recorded here because neither existed on disk: the producer call graph, which
corrects a published profile split, and the negative result that no clean timing could be
taken on 2026-09-20 because the machine was saturated continuously.

## The call graph

Seed 42, size 17, phase 16, `villain_rise 1.0`, recipe 3. Nesting recorded from a stack of
instrumented frames, so "ran inside" is observed rather than inferred from line numbers.

```
producer                                runs   nested inside
terrain_history.city_fate                 13   13 x age_transition
terrain_nests.add_nests                   10   5 x terrain_area.apply_world_scale
                                               2 x age_transition
                                               2 x age_transition > rebuild_tail
                                               1 x (top)
terrain_area.apply_world_scale             5   5 x (top)
terrain_history.civilization               5   3 x (top)
                                               2 x age_transition > rebuild_tail
terrain_history.add_biome_variants         4   2 x age_transition > rebuild_tail
                                               1 x (top), 1 x age_transition
terrain_history.refresh_environment        3   2 x age_transition > rebuild_tail, 1 x (top)
terrain_history.evaluate_networks          3   2 x age_transition > rebuild_tail
                                               1 x age_transition
terrain_history.age_transition             2   2 x (top)
terrain_villains.advance                   2   2 x age_transition
terrain_wars.resolve_wars                  2   2 x age_transition
terrain_history.rebuild_tail               2   2 x age_transition
terrain_villains.build                     2   2 x age_transition
city_planner.fill_cities                   1   1 x (top)
hamlet_planner.fill_hamlets                1   1 x (top)
castle_planner.fill_castles                1   1 x (top)
terrain_nomads.add_nomads                  1   1 x (top)
terrain_nomad_routes.add_nomad_routes      1   1 x (top)
terrain_beast_movement.add_beast_movements 1   1 x (top)
terrain_encounters.add_encounters          1   1 x (top)
terrain_nomad_effects.apply_nomad_effects  1   1 x (top)
```

## What it changes

**`age_transition` is a scheduler, not a producer.** Its two runs contain `city_fate` x13,
`add_nests` x4, `add_biome_variants` x3, `evaluate_networks` x3, `refresh_environment` x2,
`resolve_wars` x2, `villains.advance` x2, `villains.build` x2, `civilization` x2 and
`rebuild_tail` x2. A profiler that suppresses nested calls charges all of that to it.
Publishing its share beside `fill_cities` as a peer describes it as something it is not.

**`city_fate` is the most-executed producer in the generation and is in no producer set.**
Thirteen runs, every one inside `age_transition`.

**`terrain_area.apply_world_scale` is a producer whose name says otherwise.** Five runs,
accounting for **five of the ten `add_nests` executions**. It raises humans, colleges,
seasonal food, world society and nests inside a function named for rescaling coordinates.
This is why `add_nests` was twice miscounted by grepping `terrain_history`: the largest
source of its executions is in a different file, behind a name that does not suggest it.

**`add_nests` executes ten times, not three.** Three call sites in `terrain_history` plus one
in `terrain_area`, and two of the `terrain_history` sites run twice because `age_transition`
runs twice.

**`fill_cities` is the one published share that survives, and is now verified rather than
assumed.** Exactly one execution, at top level, with no instrumented producer nested inside
it, so its exclusive time equals its inclusive time.

## The negative result

**No clean timing was taken on 2026-09-20 and none could be.** A phase-16 cost ladder at
sizes 33, 65 and 129 was started at 01:14:12, killed within minutes when the process table
showed two `validate_repo` stages running and a second world generation starting 24 seconds
after the ladder did. A watcher then polled the process table from 01:15:22 for a window of
two consecutive clear samples and **recorded zero clear samples in roughly twenty minutes**
before the sweep was wound down. The machine was saturated continuously for that period.

That is a fact about how this run was conducted rather than about the code, and it is
recorded so the absence is not mistaken for something nobody tried. Wall-clock and
peak-memory figures for phase-16 generation at any size above 17 do not exist.

## Method: what a saturated machine does and does not prevent

The graph above was taken **during** that saturation, and is unaffected. The distinction that
made it possible is worth keeping:

- **Corrupted by contention:** wall clock, peak resident memory, per-producer time shares.
  These must queue for a quiet machine.
- **Immune to contention:** call counts, call graphs and nesting, content digests, byte
  comparisons, schema surveys. These never need to queue.

Three generations of structural evidence were produced through a saturated hour on that
basis, while the timing half never ran. Treating "the machine is busy" as blocking all
measurement is what had been costing the time.

**An instrument must report its own blind spots.** The first pass of this graph failed to
instrument two producers — `civilization` was sought in `terrain_civilizations` when it is
defined in `terrain_history:270`, and the `terrain_area` producer was sought under a guessed
name. Both were caught only because the script prints what it could not instrument alongside
what never executed. A survey that silently skips what it cannot resolve reports full
coverage every time, which is the same defect as a profiler suppressing nested calls and as
`assertIn` matching a prefix.

## Dependencies and unresolved decisions

- The costs belong to perf, whose corrected profiler supplies them. This card supplies the
  structure. Neither is complete alone: a share without the graph attributes nested work to
  the wrong producer, and the graph without costs says nothing about where time goes.
- Whether `apply_world_scale` should be renamed, or its generation work moved out of it, is
  an architecture question this card does not decide.

## Sources consulted

- `Sim/icarus_sim/terrain_history.py:270` — `civilization`, defined here rather than in `terrain_civilizations`.
- `Sim/icarus_sim/terrain_history.py:288` — `rebuild_tail`, which `age_transition` calls.
- `Sim/icarus_sim/terrain_history.py:318` — `age_transition`.
- `Sim/icarus_sim/terrain_area.py:84` — the `add_nests` call inside `apply_world_scale`.

## Files and assets in scope

None. This card records evidence and changes no behaviour. Acting on it means adding
`city_fate` and `apply_world_scale` to whatever producer set a profile reports, which is
perf's to do.

## Acceptance and evidence

No test accompanies this card: it records a measurement, and a test asserting the current
call graph would pin the implementation rather than a contract. The graph is reproducible in
about fifteen lines and should be re-taken rather than trusted:

```python
counts, stack = collections.Counter(), []
def instrument(module_name, attr):
    module = importlib.import_module(module_name)      # AttributeError here is a finding:
    original = getattr(module, attr)                   # report it, never skip it
    label = f'{module_name.rsplit(".", 1)[-1]}.{attr}'
    def wrapper(*a, **k):
        counts[(label, ' > '.join(stack) or '(top)')] += 1
        stack.append(label)
        try: return original(*a, **k)
        finally: stack.pop()
    setattr(module, attr, wrapper)
```

Every producer is imported inside a function body in `terrain_history`, so the name resolves
from its source module at call time and patching the module attribute intercepts it. That is
load-bearing: a producer bound by a module-level import elsewhere would not be caught, which
is why zero-execution results are reported rather than assumed to mean uncalled.

## Documentation impact

None until a corrected split is published. When one is, whatever document carries it should
name `city_fate` and `apply_world_scale` and should not describe `age_transition` as a
producer.

## Adversarial review and limitations

- **The graph is for one configuration** — seed 42, size 17, phase 16, `villain_rise 1.0`.
  Counts that depend on content will differ elsewhere: `city_fate` runs once per surviving
  city per age, so its 13 is a property of this world, not a constant. The *nesting* is
  structural and will not change with seed or size.
- **Not established:** any cost. Nothing here says where time goes; it says which producer's
  ledger a cost would be charged to. Do not quote it as a profile.
- **Not established:** that these are all the producers. The list instrumented was chosen by
  hand from the ones under discussion, so a producer nobody named is still missing —
  `apply_world_scale` was exactly that until this run, and it was found only because a call
  count disagreed with a grep.
- `villain_rise 1.0` is not the default. It was set so the villain paths execute; at the
  default of zero, `villains.advance` and `villains.build` would not appear.

## Handoff

Taken by the red-team SDET session during a saturated machine, after perf retracted a profile
split and two sessions in succession miscounted `add_nests` from the same file. The
coordinator asked for the graph to reach disk because it existed only in a message.
