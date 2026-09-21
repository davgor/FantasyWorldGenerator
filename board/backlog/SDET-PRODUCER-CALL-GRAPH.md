# SDET-PRODUCER-CALL-GRAPH — the measured call graph, and the timing that could not be taken

Owner: none. State: **call graph measured and recorded; the timing half is STILL unrun and item 4
remains open.** Evidence is the graph below, taken by instrumenting the producers and running
one generation. Reproduce in fifteen lines — see Acceptance.

> **Swept again 2026-09-21, later the same day. The producer set is now complete, the graph has
> been re-taken with the binding-site patch this card's Acceptance demands, and one of this
> card's own published rows was wrong. Details in
> [Second sweep 2026-09-21 — the corrected graph](#second-sweep-2026-09-21--the-corrected-graph)
> at the foot. Only the cost ladder is left.**
>
> | remaining item | status |
> |---|---|
> | add `apply_world_scale` to the producer set | **already there** — `Sim/icarus_sim/terrain_profile.py:59`, committed, not a pending edit (it was line 57 before `city_fate` was added above it) |
> | add `city_fate` to the producer set | **DONE by the fence owner** — `Sim/icarus_sim/terrain_profile.py:94`, with a comment saying it runs between the two `add_nests` calls and reads the field the first one wrote |
> | phase-16 cost ladder at sizes 33 / 65 / 129 | **STILL NOT RUN** — third consecutive day; the machine has carried five sessions and up to 44 Python processes. This is the only thing left in this card. |
> | `evaluate_networks` runs **4** times, not this card's 3 | **card corrected below** — the 3 and the re-take's 1 are each half of it |

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

> **Do not copy the fifteen lines above as they stand.** They patch one module, and nine of the
> producers here are bound in two or three. Both a definition-site patch and a binding-site
> patch undercount, in opposite directions — `evaluate_networks` comes back 1 from one and 3
> from the other against a true 4. Replace **every** attribute across every loaded module that
> `is` the original function object; see
> [the corrected graph](#second-sweep-2026-09-21--the-corrected-graph).

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

## Sweep 2026-09-21

Worked at `4778a3e`. **Nothing in this card was closed.** What changed is that the three
remaining items are now individually accounted for rather than described as one timing half —
and the graph was re-taken, because `AGE_YEARS` moved from `100.` to `5000.` today and this
card's own adversarial review predicts which of its numbers that should move.

### The graph, re-taken at AGE_YEARS = 5000

Same configuration as the original: seed 42, size 17, phase 16, `villain_rise 1.0`, recipe 3.
Counts only; no timing was taken and the machine was saturated throughout.

**The nesting is unchanged, exactly as this card predicted it would be.** `add_nests` is still
ten executions split 5 / 2 / 2 / 1 across `apply_world_scale`, `age_transition`,
`age_transition > rebuild_tail` and top level. `apply_world_scale` is still 5, `civilization` 5,
`add_biome_variants` 4, `refresh_environment` 3, and `age_transition`, `rebuild_tail`,
`resolve_wars`, `villains.advance` and `villains.build` are all still 2. `fill_cities`,
`fill_hamlets`, `fill_castles` and the five satellite packages are still one apiece at top level.

**One count moved: `city_fate` is now 14, not 13.** Still every one of them inside
`age_transition`. This is the card's own prediction coming true — "`city_fate` runs once per
surviving city per age, so its 13 is a property of this world, not a constant" — and the thing
that changed the world is `AGE_YEARS`. It is not a regression and nothing needs fixing; it is a
reminder that this row is content, not structure.

**One producer this card does not list showed up at ten executions:**
`terrain_settlements.add_settlements`, nested 5 x `apply_world_scale`, 3 x `civilization` and
2 x `age_transition > rebuild_tail > civilization`. That matches the ten executions
[PERF-ADD-NESTS-DOMINATES](../done/PERF-ADD-NESTS-DOMINATES.md) already charges it, and it is a second
example of this card's "not established: that these are all the producers".

### The instrument was wrong about one row, and says so

**`evaluate_networks` came back as 1 x (top), against this card's 3. The card is right and the
re-take is wrong.** `terrain_history.py:11` binds the name at **module level** —
`from .terrain_leyline_history import ... evaluate_networks ...` — so the three call sites in
`terrain_history` (`:303`, `:398`, `:832`) resolve against `terrain_history`'s own global and
patching `terrain_leyline_history.evaluate_networks` never sees them. The original run patched
`terrain_history.evaluate_networks`, which is the binding site rather than the definition site,
and got the right answer.

This is the exact failure mode this card's Acceptance section warns about, reproduced by
accident: "a producer bound by a module-level import elsewhere would not be caught". **Patch
where the name is bound, not where the function is defined**, and the two differ for precisely
those producers that are NOT imported inside a function body. Every other producer here is, which
is why the rest of the graph reproduced.

**`apply_world_scale` is already in the producer set**, at `Sim/icarus_sim/terrain_profile.py:57`,
and `git diff HEAD` on that file is empty — so it is committed, not somebody's pending edit. The
handoff instruction to "add `city_fate` and `apply_world_scale`" was half stale. **`city_fate` is
genuinely absent**, confirmed by grep over the whole `PRODUCERS` tuple.

**Adding it is blocked by a fence.** The producer set lives in `Sim/icarus_sim/terrain_profile.py`,
which is fenced to the perf session for the duration. Per the sweep rules a card that needs a
fenced file stops and reports rather than working around it. This is a one-line edit —
`('icarus_sim.terrain_history', 'city_fate'),` beside the other `terrain_history` entries — and
it belongs to whoever holds that file.

**The cost ladder is blocked by the machine, which is the same blocker this card already
documents.** Checked repeatedly through the sweep: 36-38 `python.exe` processes, `LoadPercentage`
at 100, two of them past 2,500 CPU-seconds. Two other sessions had live work — an `--stage
artifacts` run in its size-513 pair and a `unittest discover` past forty minutes. **No wall-clock
or peak-memory figure was published for this card, for the same reason as on 2026-09-20.** The
negative result below stands, now for a second consecutive day.

One thing worth adding to the negative result: **this sweep did take timings, and threw none of
them away, because they were never load-bearing.** The showcase falsification and the `add_nests`
interior profile were both run on the saturated machine deliberately — their headline results are
byte counts and call counts, which the method note below classes as immune. Every duration
printed beside them is labelled an upper bound in the script that prints it. The lesson the card
draws — that "the machine is busy" blocks a specific list of measurements and not measurement
itself — held up a second time.

**Item 4 was not decided, and deliberately so.** Whether `apply_world_scale` should be renamed or
have its generation work moved out is named in this card as an architecture question it does not
decide, and the sweep brief repeated that it was not this card's to decide either. It is still
open. Note the practical consequence while it stays open: a reader of `terrain_profile.py` sees
`apply_world_scale` listed among the producers with no indication that it raises humans, colleges,
seasonal food, world society and nests, so the profiler is now correct and the name still misleads.

## Second sweep 2026-09-21 — the corrected graph

Same day, later. The producer set is complete and the graph has been re-taken a third time,
this time with the instrument the Acceptance section above specifies and neither previous run
used. Counts and nesting only; **no timing was taken, deliberately — see
[the ladder](#the-ladder-is-still-the-only-thing-left) at the foot of this section.**

### The producer set is complete

`city_fate` is in it, at `Sim/icarus_sim/terrain_profile.py:94`, put there by the session the
file is fenced to, with a comment saying it runs between the two `add_nests` calls and reads the
nest field the first one wrote. `apply_world_scale` was already there. **Nothing in this card
asks for an edit to `terrain_profile.py` any more.**

That comment matters beyond bookkeeping, because it answers the question a reader of the profile
would ask next: the second `add_nests` of each age-transition pair is **not** redundant.
`city_fate` reads `beast_nests` between the two and feeds it to `fantasy_nest_threats`, which
decides whether a city dies. Removing the second call would change which cities survive.

### Patch the binding site AND the definition site — they are different sets, and each alone undercounts

The 2026-09-21 re-take reported `evaluate_networks` as 1 against this card's 3, diagnosed it as
patching the definition site instead of the binding site, and concluded the card was right.
**Neither was right. It runs 4 times.**

- `Sim/icarus_sim/terrain_history.py:11` binds the name at module level, so the three call sites
  in that file — `:303`, `:398`, `:832` — resolve against `terrain_history`'s own global. Three
  of them exist; three executions were observed in this run, one directly under `age_transition`
  and two under `age_transition > rebuild_tail`. Patching `terrain_leyline_history` alone sees
  none of these. That is the re-take's 1.
- `Sim/icarus_sim/terrain_leyline_history.py:132` is a fourth call to `evaluate_networks`, the
  last statement of `generate_networks`, in its own module and against its own global. Patching
  `terrain_history` alone sees none of *this* one. That is the call this card's published 3 is
  missing.

3 + 1 = 4, and **the two wrong answers are each exactly half of the right one.** "Patch the
binding site, not the definition site" is not the rule; it is one half of the rule. The instrument
used here does not choose: for each producer it walks every loaded module and rebinds **every**
attribute that is the same function object, so the definition site and all re-bindings become one
wrapper and a call through any of them counts once.

Nine of the producers instrumented hold more than one binding, which is the size of the blind
spot a single-site patch carries:

```
terrain_astrology.add_astrology        terrain_astrology, terrain_history
terrain_astrology.refresh_astrology    terrain_astrology, terrain_history
terrain_encounters.add_encounters      terrain_encounters, terrain_nomad_api
terrain_globe.measure_globe            terrain_globe, terrain_tectonics
leyline_history.evaluate_networks      terrain_leyline_history, terrain_history
leyline_history.generate_networks      terrain_leyline_history, terrain_history
nomad_effects.apply_nomad_effects      terrain_nomad_effects, terrain_nomad_api
nomad_routes.add_nomad_routes          terrain_nomad_routes, terrain_nomad_api
terrain_religion.add_religion          terrain_religion, terrain_corruption, terrain_visitation
```

A related hazard that did **not** bite here, recorded so nobody relies on the wrong reason:
`Sim/icarus_sim/terrain_history.py:335` imports `advance` under the alias `advance_villains`, and
`promote` and `build` are aliased the same way. Those three are still caught, because the import
is inside a function body and so resolves from the wrapped module at call time. **The alias is
harmless today and stops being harmless the moment one of those imports is hoisted to module
level** — which is exactly what happened to `evaluate_networks`. A survey that identifies
producers by grepping for their names in `terrain_history` would miss all three regardless.

### The graph, re-taken at AGE_YEARS = 5000 over the whole producer set

Seed 42, size 17, phase 16, `villain_rise 1.0`, recipe 3, generator 16, through the pinned
recipe-3 request rather than a hand-built `Config` — a hand-built one leaves `globe_radius` at
the 10 km design default and generates a different, tiny world. **`NEVER EXECUTED: none` and
`COULD NOT INSTRUMENT: none`**, over this card's list and `terrain_profile.STEP_TARGETS` together.

```
producer                                runs   nested inside
terrain_history.city_fate                 14   14 x age_transition
terrain_nests.add_nests                   10   5 x generate_base > apply_world_scale
                                               2 x age_transition
                                               2 x age_transition > rebuild_tail
                                               1 x (top)
terrain_settlements.add_settlements       10   5 x generate_base > apply_world_scale
                                               3 x civilization
                                               2 x age_transition > rebuild_tail > civilization
terrain_biomes.add_terrain_labels          9   5 x generate_base > apply_world_scale
                                               2 x age_transition > rebuild_tail > refresh_environment
                                               1 x (top), 1 x refresh_environment
terrain_humans.add_humans                  8   5 x generate_base > apply_world_scale
                                               2 x age_transition > rebuild_tail > civilization
                                               1 x civilization
terrain_magic.add_colleges                 8   same three places as add_humans
terrain_seasons.add_seasonal_food          8   same three places as add_humans
terrain_society.add_world_society          8   same three places as add_humans
terrain_water.add_water                    7   5 x generate_base > apply_world_scale
                                               1 x carve_relics, 1 x tectonic_transition
terrain_astrology.refresh_astrology        6   3 x civilization
                                               2 x age_transition > rebuild_tail > civilization
                                               1 x add_astrology
terrain_climate.add_climate                6   5 x generate_base > apply_world_scale, 1 x (top)
terrain_globe.measure_globe                6   4 x generate_base > generate_tectonics
                                               1 x carve_relics > measure_surface
                                               1 x tectonic_transition > measure_surface
terrain_area.apply_world_scale             5   5 x generate_base
terrain_history.civilization               5   3 x (top)
                                               2 x age_transition > rebuild_tail
terrain_lab.generate_base                  5   5 x (top)
terrain_tectonics.generate_tectonics       5   5 x generate_base
terrain_tectonics.make_plates              5   5 x generate_base > generate_tectonics
terrain_ecology.add_environment            4   2 x age_transition > rebuild_tail > refresh_environment
                                               1 x (top), 1 x refresh_environment
terrain_ecology.shape_islands              4   4 x generate_base > generate_tectonics
terrain_history.add_biome_variants         4   2 x age_transition > rebuild_tail
                                               1 x (top), 1 x age_transition
terrain_leyline_history.evaluate_networks  4   2 x age_transition > rebuild_tail
                                               1 x age_transition
                                               1 x generate_networks
terrain_history.add_threat_assessments     3   2 x age_transition > rebuild_tail, 1 x (top)
terrain_history.refresh_environment        3   2 x age_transition > rebuild_tail, 1 x (top)
terrain_religion.add_religion              3   2 x age_transition > rebuild_tail, 1 x (top)
terrain_erosion.erode                      2   2 x generate_base > generate_tectonics
terrain_history.age_transition             2   2 x (top)
terrain_history.measure_surface            2   1 x carve_relics, 1 x tectonic_transition
terrain_history.rebuild_tail               2   2 x age_transition
terrain_villains.advance                   2   2 x age_transition
terrain_villains.build                     2   2 x age_transition
terrain_wars.resolve_wars                  2   2 x age_transition
terrain_villains.promote                   1   1 x age_transition
```

One apiece at top level: `fill_cities`, `fill_hamlets`, `fill_castles`, `add_astrology`,
`attach_detail`, `carve_relics`, `tectonic_transition`, `generate_networks`, `add_nomads`,
`add_nomad_routes`, `add_beast_movements`, `add_encounters`, `apply_nomad_effects`,
`_attach_heroes`, `_attach_story_web`, `_attach_npcs`, `_attach_key_locations`,
`_attach_key_location_plans`, `build_debug`.

### What moved against this card's published graph

- **`city_fate` is 14, not 13.** Every one inside `age_transition`, as before. `AGE_YEARS` moved
  from `100.` to `5000.` today, and this card predicted this row would move: "`city_fate` runs
  once per surviving city per age, so its 13 is a property of this world, not a constant."
- **`evaluate_networks` is 4, not 3.** This card was wrong; so was the re-take. See above.
- **`apply_world_scale` is 5 x `generate_base`, not 5 x (top).** Same count; the nesting is one
  level deeper than published, and it was published as top-level only because `generate_base`
  was never instrumented. Every `(top)` row in the original graph is suspect for the same reason,
  which is what "not established: that these are all the producers" was warning about.
- **`terrain_villains.promote` runs once, inside `age_transition`, and is in the producer set
  while `advance` — which runs twice — is not.** Whether the profile should name `advance` too
  is perf's call, not this card's; it is recorded here because the graph is what would tell them.
- Everything else reproduced exactly: `add_nests` 10 split 5/2/2/1, `civilization` 5,
  `add_biome_variants` 4, `refresh_environment` 3, `age_transition`, `rebuild_tail`,
  `resolve_wars`, `villains.advance` and `villains.build` all 2, the planners and satellites one
  apiece, and `add_settlements` 10 as the previous re-take found.

### The ladder is still the only thing left

**No wall-clock or peak-memory figure was taken, for a third consecutive day, and this time it
was a decision rather than an obstruction.** The machine has carried five concurrent sessions
tonight and up to 44 Python processes; anything measured would be an upper bound wearing the
costume of a measurement. Two generations were run for this sweep and both printed a duration
labelled UPPER BOUND in the script that printed it, and neither is quoted anywhere as evidence.

That is the same split this card already documents. Call counts, call graphs, nesting and
coverage are immune to contention, so the whole of the section above was taken on a saturated
machine and is sound. **Wall clock, peak resident memory and per-producer time shares must queue
for a quiet one.** The phase-16 cost ladder at sizes 33 / 65 / 129 is the entire remaining
content of this card.

What is known about cost comes from perf's ledger, not from here, and is repeated only so that
whoever runs the ladder knows what it has to resolve: `add_nests` is 41% of a size-128 run at
505.5 s across five calls, and the second call of each age-transition pair is somewhere between
191 s and 210 s. **That band cannot be narrowed from the existing profile**, because the profile
records per-stage totals and a maximum rather than call order.

## Handoff

Taken by the red-team SDET session during a saturated machine, after perf retracted a profile
split and two sessions in succession miscounted `add_nests` from the same file. The
coordinator asked for the graph to reach disk because it existed only in a message.

Re-taken 2026-09-21 by the backlog sweep with an object-identity instrument, which closed the
producer-set items and corrected one of this card's own rows. The card stays in `backlog/` for
the cost ladder and for item 4.
