---
conformance: 1
record: stage-profile
tier: EXERCISED
summary: Records one generation run as a tree of sixteen stages and named steps, with wall time, call counts, self time and resident memory, without changing the world it measures or writing anything into it.
modules:
  - Sim/icarus_sim/terrain_profile.py
emits: []
versions:
  - id: stage-profile
    assert: 1
proof:
  - path: Sim/tests/test_stage_profile.py
    establishes: that a profiled world equals an unprofiled one once timings are stripped, that every stage is recorded once in order and splits exactly into body plus capture, that every named step target resolves, that self time never exceeds total time, that wrappers are removed on success and on failure, that profiles refuse to nest, that the report digests and names every module it measured, and that nothing is written into the world document
decisions: []
tickets: []
---

# Conformance: stage profile

## What it produces

A measurement of one generation, as a tree rather than a flat bag. The top level is the
sixteen stages `terrain_history.STAGES` names, each carrying its wall time split into the
stage body and the snapshot capture, resident memory at the stage boundary and the change
across it, how many layers the world holds afterwards, how large that stage's snapshot
delta was, and how far each pre-existing `timing_ms` scalar moved while it ran. Under that
sits a step table: one row per named pass per stage, with call count, total time, self time
(total minus the named steps it called) and the slowest single call.

The report is returned to whoever opened the profile. It is not part of the world document
and is not part of the interchange contract.

## Entry points

| Symbol | Where | What a caller gets |
|---|---|---|
| `profile_run(progress=None)` | `terrain_profile` | A context manager. Wraps every named target for the duration, yields a `Run`, restores every wrapper on the way out including on an exception. `progress` is called with `(stage_record, run)` as each stage closes. |
| `Run.report(label='')` | `terrain_profile` | The finished record: stages, steps, peak resident memory, and `missing_targets`. |
| `begin` / `mark` / `end` | `terrain_profile` | The three hooks `generate_history` calls unconditionally. With no profile open each is a global read and a `None` test. |
| `STEP_TARGETS` | `terrain_profile` | The fixed `(module, attribute)` list of named passes. Everything not in it lands in the self time of its caller. |
| `subject_digest()` | `terrain_profile` | A sha256 prefix per measured module plus one combined digest, taken when the run opens and carried in the report as `subject`. Two reports with different digests measured different code. |
| `tools/stage_profile.py` | `tools/` | The runner: generates at a seed and size, writes the JSON record and a Markdown outline, and prints a line per stage as it goes. |

## Inputs it reads

Nothing in the world. It reads the clock, `psutil` for resident memory when it is
installed, and the modules named in `STEP_TARGETS` so it can wrap them. It takes
`result['timing_ms']` and `result['layers']` at each stage boundary to compute deltas, and
the last entry of `generate_history`'s snapshot list to size the capture — all reads, never
writes.

`psutil` is optional. Without it every memory field is `None` rather than zero, because a
zero there would read as "this stage allocated nothing".

## Artifacts it writes

None into the world. This is the load-bearing property of the whole module: the report is
returned to the caller and `generate_history` stores no part of it, so an exported document
is byte-identical whether or not a profile was open. That is stronger than relying on
`cli._without_timings` to strip it, and it is what
`test_stage_profile.py::test_the_profile_is_not_written_into_the_world` and
`::test_a_profiled_world_equals_an_unprofiled_one` pin together.

**Invariant: wrapping is content-neutral.** Every wrapper passes its arguments through
unchanged, returns the callee's value unchanged, and propagates exceptions unchanged. It
adds no call to any random stream and reorders nothing, so a profiled run draws the same
world as an unprofiled one. An optimisation of this module that caches, batches, reorders
or skips a call breaks that, and the equality test is the thing that would catch it.

`tools/stage_profile.py` writes two files outside the world: `<base>.json` and `<base>.md`,
plus a `<base>.progress.json` rewritten as each stage closes so a run killed partway still
leaves the stages it did measure.

## Where it runs

Only inside a `profile_run()` block. `generate_history` carries three unconditional hook
calls in its stage loop — `begin` before the stage body, `mark` between the body and
`capture(stage)`, `end` after it — and all three return immediately when no profile is
open. No pass is wrapped, and no measurement is taken, outside such a block.

It is not reentrant and not thread-safe: one module-level pointer holds the open run, a
second `profile_run()` raises rather than interleaving two step stacks, and two generations
inside one block are recorded as one run.

## Versions asserted

Profile record version 1 <!-- conformance:version stage-profile=1 -->, carried as
`version` in `Run.report()`.

## Proven by

`Sim/tests/test_stage_profile.py`, at seed 42, size 5, phase 16 — a whole sixteen-stage
generation in about a second, because these assertions are about the shape of the
measurement and not the cost of a world.

- `::test_a_profiled_world_equals_an_unprofiled_one` — the same world, timings stripped.
- `::test_every_stage_is_recorded_once_in_order` — sixteen stages, in order, titled from
  `STAGES`, each splitting exactly into body plus capture.
- `::test_every_named_target_exists` — `missing_targets` is empty.
- `::test_self_time_never_exceeds_total_time` — nesting is subtracted once, never twice.
- `::test_wrappers_are_removed_when_the_block_closes` and
  `::test_a_failed_run_still_restores_the_wrappers` — no wrapper outlives its profile.
- `::test_profiles_refuse_to_nest`.
- `::test_the_report_names_the_code_it_measured` — every measured module is digested and
  named repo-relative.
- `::test_the_profile_is_not_written_into_the_world`.

## Why it works this way

The generator already wrote about two dozen `timing_ms` scalars and they answer a
different question. They are keyed by subsystem rather than by stage, several are
accumulated across every call in the run while others are overwritten by their last call,
and none of them says how many times a pass ran. A flat bag of that shape cannot show that
stages 1 to 5 each rebuild the physical base from scratch, or that one pass executes five
times across the run. Those are the two facts that decide where optimisation effort goes,
so the record had to be a tree with call counts in it.

Wrapping module attributes rather than editing thirty call sites is deliberate. The passes
are imported inside function bodies (`from .terrain_settlements import add_settlements`
inside `civilization`), so the name is resolved against the module at call time and a
patched attribute is picked up without touching the caller. That keeps the instrumentation
in one file that can be read and audited as a unit, instead of scattering timing code
through the simulation where it would have to be maintained by everyone.

The target list is fixed and coarse rather than automatic. Automatic wrapping of every
public function would swallow `layout_point`, `perlin3` and `direction`, which run tens of
millions of times at size 128 — the wrapper would cost more than the body and the report
would measure itself. The price of a fixed list is that it can go stale, which is why a
target that does not resolve is reported in `missing_targets` and asserted empty by a test:
a step that quietly stops being measured looks exactly like a step that got fast.

The report digests the code it measured because this repository is worked on by several
sessions at once. A run finished at 01:45 and two of the modules it measured were rewritten
by 02:18, and nothing in the report distinguished it from a run of the new code: the seed,
the size and the machine were all still correct, and all three are what a cost figure is
conventionally asked to state. The fourth thing is the code, and on a shared tree it is the
one that moves without anybody's report noticing. `docs/performance.md` carries a paragraph
about exactly that incident, because the run predates the digest.

`subsystem_ms` carries the old flat scalars per stage anyway, deltas rather than absolutes,
because they name costs inside passes the step list does not reach into. They are labelled
as what they are and not presented as a decomposition of `wall_ms`, because for an
overwritten key a delta is not the cost of the stage.

## Does not establish

- **That the digest means the measurement is current.** It means the report says which
  code it ran against. Comparing it to the tree is the reader's job and nothing does it
  automatically; a stale report with an honest digest is still stale.
- **Nothing about cost.** No test here asserts that a stage takes any particular time, and
  none should: a timing assertion on a shared desktop is a flake generator. Every cost
  figure in `docs/performance.md` is a description with its seed, size and machine
  attached, not a gate.
- **That `wall_ms` decomposes into the step rows.** It does not, and it is not meant to.
  Unnamed work stays in the self time of its caller, and work in no named step at all is
  in the stage total and in no row.
- **That the profiled run costs the same as an unprofiled one.** The wrappers are cheap
  relative to the passes they wrap, and `psutil` is sampled sixteen times, but nothing
  measures the overhead. The numbers are the cost of a *profiled* generation.
- **Anything under concurrency.** One module-level pointer, one step stack. Two threads
  generating inside one block would interleave into nonsense, and nothing prevents that or
  detects it.
- **That `subsystem_ms` deltas are per-stage costs.** For a key its pass overwrites each
  call, the delta is the difference between two last-call values, which is not a cost at
  all. They are carried as a pointer to look at, not as an accounting.
- **Anything on POSIX.** `peak_rss_mb` reads `psutil`'s `peak_wset`, which exists only on
  Windows; elsewhere the field is `None` and the high-water mark is simply not recorded.
  The measurements published here were taken on Windows.
