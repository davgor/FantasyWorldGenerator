# PERF-SUITE-RUNNER-ORPHANS-CHILD — stopping a suite kills the wrapper and leaves the work running

Owner: none. State: backlog, unowned. Found by the code red team auditing `233182e`
([review](../../docs/reviews/233182e-code-red-team.md), M5) and held off the board while that
lens's filing hold stood; filed 2026-09-20 once the user lifted it. A constraint rather than a
defect: no output is wrong, and the cost is paid by whoever shares the machine.

## Observed behavior

Stopping a background task killed the wrapper and left the real work running, twice, on two
different runners:

```
export_showcase.py                     2,258 MB   survived the stop
unittest discover -s Sim/tests           894 MB   survived the stop
```

Those two figures are relayed from the code lens, not re-measured here. The mechanism below is
measured, and it is structural.

**One `--stage repo-tests` is three processes deep.** `python tools/validate_repo.py --stage
repo-tests` spawns at `tools/validate_repo.py:26`, which starts `python -m unittest discover -s
tests` at `tools/validate_repo.py:84`, inside which `tests/test_showcase.py:21` spawns the
showcase exporter. Killing the outermost PID leaves two live descendants, each holding a world
in memory.

**Nothing in that chain cleans up, and one file in the repository shows it could.** A census of
every `subprocess` spawn site under `tools/` and `tests/`, taken by walking the AST of each
module and counting calls to `subprocess.run`, `Popen`, `check_output`, `check_call` and `call`:

| | count |
|---|---|
| spawn sites | 38 |
| across files | 19 |
| sites passing a `timeout=` | 21 |
| files that terminate a child they started | **1** |

The one is `tools/smoke_lab.py`. It wraps its lab server in `try`/`finally` and calls
`terminate`, then `wait` with a five-second bound, then `kill` — `tools/smoke_lab.py:50-56`.
Every other site has no `finally` and no exception handling of any kind, including
`tools/validate_repo.py:26`, which is the parent of every local and CI suite run.

**A `timeout=` is not protection against this.** A timeout is enforced by the parent, and the
parent is what died. Twenty-one of the thirty-eight sites bound a *hung* child; none of them
bounds an *orphaned* one.

**A survivor is also anonymous.** `tools/validate_repo.py:25` prints the command line it is
about to run and not the PID it got back, so a python process found alive an hour later cannot
be matched to the run that started it.

## Why it matters

This is how a machine ends up saturated by runs everyone believes they already stopped, which is
the state the code lens found this one in: six concurrent python processes generating worlds,
three of them the same sim-tests suite from three different sessions.

The second-order cost is worse than the first. A contended machine does not merely run slowly —
it produces timings and peak-memory figures that cannot be assigned to a cause, and the sweep
that found this spent real effort on numbers it then had to withdraw for exactly that reason.

Killing by executable name is not a workaround. On a shared tree the process list is full of
other sessions' work, and killing the wrong `python.exe` destroys a peer's run silently, with
nothing left to show it happened.

## Current state

Unfixed. The census above was taken at `7d94bf5`.

## Proposed fix

Two halves, because they answer different failure modes and only one of them is solvable.

**1. An interruption the parent can see.** Ctrl-C and a `KeyboardInterrupt` both reach
`tools/validate_repo.py`. Give its `run` helper at `tools/validate_repo.py:24` the shape
`tools/smoke_lab.py:50-56` already uses: `Popen`, then `try`/`finally`, `terminate`, a bounded
`wait`, then `kill`. That pattern is already in the tree and already reviewed.

**2. A hard kill the parent cannot intercept.** This cannot be handled, so make the survivor
identifiable instead: print the child's PID beside the command line that
`tools/validate_repo.py:25` already prints. A survivor is then matched by PID to a specific run,
which is what makes it safe to kill on a shared machine.

**Do not apply this to all thirty-eight sites.** One of them is the parent of every suite run;
the rest are leaves that are short-lived or already bounded. A sweep across all of them is a
much larger diff with no more coverage.

## Acceptance and evidence

An honest test is harder here than the fix. Asserting that a killed process is dead requires
killing one, and on a shared machine that is the exact hazard being fixed. Two cheap assertions
are available and neither needs a kill:

1. The suite runner names a child PID in its own output.
2. A census test: every `subprocess` spawn under `tools/` either passes a timeout or terminates
   its child in a `finally`. That pins today's 38 sites and single cleaner so the gap cannot
   grow silently, and it would have reported this the day it was written. Pin the number by
   re-running the AST census, not a grep — a grep over the same directories counts comments and
   strings and will not reproduce 38.

The measurement that actually closes the card is a stop with a follow-up process list: after
interrupting `--stage repo-tests`, no python process holding a world survives.

## Does not establish

- **The 2,258 MB and 894 MB figures.** Both are relayed from the code lens's review, not
  reproduced. Reproducing the first means paying the cost recorded in
  [PERF-SHOWCASE-TEST-COST](PERF-SHOWCASE-TEST-COST.md). What is established here is the
  three-deep tree, the census and the absence of cleanup.
- **That the two survivors were one process tree** — the review reads that way and they were
  not. `unittest discover -s Sim/tests` is the sim-tests stage, `tools/validate_repo.py:80`; the
  showcase exporter descends from the repo-tests stage at `tools/validate_repo.py:84`. Two stops
  on two different stages, which makes the finding wider than the review states rather than
  narrower: it is not a property of the showcase.
- **That CI leaks processes.** A hosted runner is torn down with the job. CI pays a timeout, not
  a ghost. The cost here is local and shared-machine only.
- **That anything was lost.** No corrupted output has been traced to a survivor. The claim is
  contention and confusion, not damage.

## Falsification

If `subprocess` children on this platform are already reaped when the parent is hard-killed,
this card is wrong and the fix is unnecessary. One interrupted `--stage repo-tests` followed by
a process list settles it in under a minute. The code lens's two survivors are the evidence
against that, and they are the part this card did not re-run.

## Handoff

Converted from M5 of [233182e-code-red-team](../../docs/reviews/233182e-code-red-team.md). The
census, the three-deep tree and the two-stages correction were established here; the memory
figures were not.
