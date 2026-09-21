# PERF-SUITE-RUNNER-ORPHANS-CHILD — stopping a suite kills the wrapper and leaves the work running

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** `tools/validate_repo.py:26` and `tests/test_showcase.py:21-22` both `subprocess.run(..., check=True)` with zero `terminate`/`kill` between them. **`tools/smoke_lab.py` is this card's good example, not a defect site** — its teardown moved to `:65-70`, so the docs_check CITE warning on `:50` is a moved line, not a stale claim.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).

> **DELIVERED 2026-09-21 at `4778a3e`. The card's diagnosis was right and BOTH halves of its
> proposed fix were wrong, in opposite directions.** Measured, not reasoned:
>
> * **Fix 1 was already being done, by the standard library.** CPython's `subprocess.run`
>   wraps `communicate` in a bare `except:` that calls `process.kill()`, so a `KeyboardInterrupt`
>   at the old `subprocess.run(..., check=True)` already reaped the direct child.
> * **And fix 1 would not have worked anyway, because it stops at the direct child.** A probe
>   mirroring `validate_repo` → `unittest discover` → exporter was interrupted with exactly the
>   `terminate` → bounded `wait` → `kill` sequence this card proposes. The middle process died;
>   **the grandchild kept running.** Twice. That grandchild is the 2,258 MB survivor in
>   *Observed behavior*, so the card's own headline evidence is the case its fix does not cover.
> * **`sys.executable` on this machine is a ~5 MB shim** that spawns the real
>   `Python312/python.exe`. `Popen` hands back the launcher's PID, so any check on the handle's
>   `poll()` answers a question about the launcher rather than about the process holding a world.
>
> What shipped is therefore tree termination, not child termination. See **Delivered**.

Owner: none. State: **done**. Found by the code red team auditing `233182e`
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
repo-tests` spawns at `tools/validate_repo.py:43`, which starts `python -m unittest discover -s
tests` at `tools/validate_repo.py:272`, inside which `tests/test_showcase.py:27` spawns the
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
`terminate`, then `wait` with a five-second bound, then `kill` — `tools/smoke_lab.py:65-70`.
Every other site has no `finally` and no exception handling of any kind, including
`tools/validate_repo.py:43`, which is the parent of every local and CI suite run.

**Re-taken at `4778a3e`, before this card's change:** 39 spawn sites across 20 files, 21
passing a `timeout=`, one file terminating a child. One site and one file more than the
`7d94bf5` census above; the two figures that matter — 21 bounded, 1 cleaner — did not move.

**And after it:** 41 sites across 21 files, **32** bounded, **two** files terminating a child.
The site count rose because `reap` spawns `taskkill`, which is itself a bounded spawn site.

**A `timeout=` is not protection against this.** A timeout is enforced by the parent, and the
parent is what died. Twenty-one of the thirty-eight sites bound a *hung* child; none of them
bounds an *orphaned* one.

**A survivor is also anonymous.** `tools/validate_repo.py:44` prints the command line it is
about to run and not the PID it got back, so a python process found alive an hour later cannot
be matched to the run that started it. This half is the one the standard library cannot supply:
`subprocess.run` returns a `CompletedProcess`, which carries no PID at all, so printing one
forces the `Popen` rewrite whether or not the cleanup was already there.

## The reproduction, which this card was missing

Run 2026-09-21 on Windows 11, CPython 3.12.10. Structural, so contention does not affect it —
and the machine was busy at the time. Three processes, mirroring
`validate_repo` → `unittest discover` → exporter. Each level dials back to a listening socket
and sleeps, so liveness is read from a socket the process itself holds rather than from a PID.
Then the top handle gets `terminate` → bounded `wait` → `kill`, which is exactly *Proposed fix*
1 below:

```
top handle (the shim)      PID 11288
  L2-suite    real worker  PID 3768    -> DEAD
  L3-worker   real worker  PID 30712   -> STILL RUNNING
```

Two facts fall out, and each defeats a different instrument:

**`sys.executable` is a shim.** It is a ~5 MB `AI/comfy-tools/Scripts/python.exe` that spawns
the real `AppData/.../Python312/python.exe`. `Popen` returned PID 26960 while the code ran in
41264. So `process.poll()` reports on a launcher, and a 5 MB entry in the process list sitting
next to a 949 MB one is one logical child, not two. Terminating the shim *does* take its own
worker with it — checked twice — so the shim is not itself the leak.

**The leak is one level further down.** A worker's own children are not reaped, because the
worker is hard-killed and never runs its own cleanup. That is the case in *Observed behavior*:
the exporter descends from the repo-tests stage through `unittest discover`, two levels below
the handle anyone holds. **No amount of cleanup written into the middle level can fix this**,
which is why the delivered change walks the tree instead.

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

**Fixed at `4778a3e`, though not by either of the two halves proposed below.** The `7d94bf5`
census in the table above is superseded by the two re-takes recorded beside it. See **Delivered**.

## Proposed fix

Two halves, because they answer different failure modes and only one of them is solvable.

**1. An interruption the parent can see.** Ctrl-C and a `KeyboardInterrupt` both reach
`tools/validate_repo.py`. Give its `run` helper at `tools/validate_repo.py:24` the shape
`tools/smoke_lab.py:65-70` already uses: `Popen`, then `try`/`finally`, `terminate`, a bounded
`wait`, then `kill`. That pattern is already in the tree and already reviewed.

> **Both already true and insufficient, which took a measurement to see.** `subprocess.run`
> contains `except:  # Including KeyboardInterrupt` followed by `process.kill()` (CPython
> 3.12.10), so the direct child was already being reaped. And the direct child is not the
> problem: a three-deep probe interrupted with this exact sequence left the grandchild
> running, twice (PIDs 29572 and 30712, each confirmed alive from the CIM process list and
> then cleaned up by PID). The reason is structural and not fixable by writing cleanup at
> every level — level 2 is *hard-killed*, so it never runs Python again and never gets to
> clean up level 3. Only a parent that walks the tree can close this.

**2. A hard kill the parent cannot intercept.** This cannot be handled, so make the survivor
identifiable instead: print the child's PID beside the command line that
`tools/validate_repo.py:44` already prints. A survivor is then matched by PID to a specific run,
which is what makes it safe to kill on a shared machine.

> **This is the half that was real, and it is what the delivered change is for.** It is also
> the half that matches the observed behaviour: the two survivors were produced by *stopping a
> background task*, which is a `TerminateProcess` the parent never sees, not a Ctrl-C.

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

> **Built, with one correction the card could not have anticipated.** The predicate has to
> follow delegation. `run` ends `finally: reap(process)` and every terminate lives in `reap`, so
> a check looking for a literal `.terminate()` inside the `finally` reported the better shape as
> a regression. The shipped predicate resolves a `finally` that calls a module-level function
> which itself stops a process. **The raw site count is deliberately not pinned to an integer**:
> the ratchet is the count of UNPROTECTED sites, held at zero, and pinning 41 as well would turn
> any unrelated tool gaining a `git rev-parse` into a red suite for a reason nobody can act on.

The measurement that actually closes the card is a stop with a follow-up process list: after
interrupting `--stage repo-tests`, no python process holding a world survives.

## Does not establish

- **The 2,258 MB and 894 MB figures.** Both are relayed from the code lens's review, not
  reproduced. Reproducing the first means paying the cost recorded in
  [PERF-SHOWCASE-TEST-COST](../backlog/PERF-SHOWCASE-TEST-COST.md). What is established here is the
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

**Run 2026-09-21. It did not falsify the card, and it falsified the fix.**

The soft case — a real `KeyboardInterrupt` raised inside a real `Popen.wait` — came back green
against the **unmodified** tree: the direct child was already dead, because the cleanup lives
inside `subprocess.run` rather than inside this repository. So "nothing in that chain cleans up"
is true of the source and false of the running program. The census counts source, which is why
it could not see this, and why the census alone was never sufficient evidence for fix 1.

Then the same experiment at the depth the card actually describes, three processes rather than
two, with the card's own proposed sequence: **middle dead, grandchild still running.** Twice.
That is the finding. The fix had to change shape, from terminating a child to terminating a tree.

Two measurement traps were hit and are worth recording, because both produced a green that meant
nothing:

- **The first version of this test killed the child in its own `finally` and then asserted the
  child was dead.** It passed on its own doing. Reading a subject's state *before* the cleanup
  that touches it is the whole discipline here.
- **`poll()` on the handle is the wrong instrument on this machine**, because the handle names a
  shim. Liveness in the shipped test is read from a socket the process itself holds, so it
  reports on whichever process is really there — no PID, no process list, no platform branch.

## Delivered

Landed at `4778a3e` on 2026-09-21.

- `tools/validate_repo.py` — `run` holds a `Popen`, prints `+ [pid N] <command>`, waits in a
  `try` and calls the new `reap` in a `finally`, then re-raises `CalledProcessError` on a
  non-zero exit so `check=True`'s contract is unchanged. `reap` kills the **tree**: on Windows
  `taskkill /F /T /PID`, by PID and never by image name, and it runs *before* the handle dies
  because once the intermediate process is gone its descendants are re-parented and no longer
  reachable from that PID. The comment pinning `VERSIONED_SECTIONS` below `run` now points at
  this card's `board/done/` path.
- Five leaf sites given a `timeout=`, which is the whole of what they needed: they are
  `git rev-parse`, `git status`, `git show`, `xcrun` and `<compiler> --version`.
  `tools/build_extraction_manifest.py`, `tools/docs_check.py` (whose `except` gained
  `TimeoutExpired`, so a wedged `git` still degrades to "ratchet skipped"),
  `tools/export_showcase.py` x2, `tools/qualify_native.py` x2.
- `tests/test_showcase.py` — the exporter spawn bounded at 3600 s and the two `git` calls at
  120 s and 60 s. The exporter bound is deliberately far above its measured cost: five sessions
  share this machine and a tight bound converts contention into a red suite.
- `tests/test_tool_subprocess_census.py` — new. Three assertions: the AST census invariant over
  `tools/` plus `tests/test_showcase.py`; the runner naming a PID; and the three-deep
  interrupt, which asserts the **grandchild** is dead. **That third test was checked against the
  pre-fix shape and fails there**, with "the GRANDCHILD (pid 18072) was still running after the
  suite runner was interrupted" — so it measures the fix rather than restating it.

**A decision made on the owner's behalf, flag it:** tree termination is implemented for
**Windows only**, and the grandchild test skips elsewhere. The POSIX equivalent is
`start_new_session=True` plus `killpg`, which detaches the child from the terminal's signal
group — a trade this machine cannot test. The conservative reading is that POSIX keeps today's
behaviour rather than gaining an untested signal change, and it is defensible on this card's own
grounds: it states CI "pays a timeout, not a ghost", and the shim that makes the handle useless
is a Windows-local fact. **The POSIX grandchild case is therefore still open.** Reverse this by
adding the session flag and widening the `skipUnless`.

**Not done, deliberately:** the thirty-one sites outside that scope, per this card's own "do not
apply this to all thirty-eight sites". The census test's scope constant names the two entries it
covers, so widening it is a one-line decision rather than a rediscovery.

**Not done, could not be:** the measurement this card says actually closes it — "a stop with a
follow-up process list" — was not run against a real `--stage repo-tests`. That needs an
interrupted live stage on a machine four other sessions are working on, which is the hazard the
card exists to describe. The three-deep probe is a faithful model of the chain, not the chain.

## Handoff

Converted from M5 of [233182e-code-red-team](../../docs/reviews/233182e-code-red-team.md). The
census, the three-deep tree and the two-stages correction were established here; the memory
figures were not.
