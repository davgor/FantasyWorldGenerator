# PERF-SHOWCASE-TEST-COST — one test method generates six worlds, and the guard that would stop it runs last

Owner: none. State: **backlog — two of three fixes landed; the falsification RAN on 2026-09-21 and this is a breakage card, not a cost card.** The exporter cannot produce a publishable bundle at all: `crossroads.html` is 313.0 MB against a 100 MB hard limit. See [The falsification ran 2026-09-21](#the-falsification-ran-2026-09-21--it-is-a-breakage-card-not-a-cost-card) at the end — it supersedes the header below and the 41,806,542-byte figure in this card. What remains is a product decision (shrink the grid, or stop embedding `build_stages`), not a performance fix.

> **Swept 2026-09-21 at `4778a3e`.** Fix **3** (compare digests, not bytes) and fix **1** (move
> the size guard inside the generation loop) are both landed, with tests that failed first and
> that cost no world generation to run. Fix **2** (shrink the reproducibility input) was
> **rejected and deliberately not stacked** on fix 1 — it is the only one of the three that gives
> up a stated guarantee. **Superseded 2026-09-21: the falsification has since finished** — see the > final section. It stayed open at the time because the run did not finish,
> twice, so whether this is a cost card or a breakage card is still formally undecided. See
> [Falsification](#falsification).

Found by the code red team auditing `233182e`
([review](../../docs/reviews/233182e-code-red-team.md), M5) and held off the board while that
lens's filing hold stood; filed 2026-09-20 once the user lifted it. A constraint rather than a
defect, with one open question that would make it a defect — see Falsification.

## Observed behavior

`tests/test_showcase.py` holds a single test method,
`test_bundle_is_fresh_reproducible_and_traceable`. Inside it:

- `tests/test_showcase.py:19` loops over two output names and runs the exporter once per pass.
- `tools/export_showcase.py:11-15` declares three worlds in `WORLDS`, and the generation loop at
  `tools/export_showcase.py:50` builds each one at size 65.

**Six size-65 world generations, inside one test method.**

The bundle is then held in memory three times over, and none of it is necessary:

- The child accumulates every page before writing anything. Nothing reaches disk until
  `tools/export_showcase.py:90-92`, after all three worlds exist.
- The test reads both bundles fully into memory at `tests/test_showcase.py:23`.
- And compares the raw bytes at `tests/test_showcase.py:24`, so both complete copies must be
  resident at once.

Relayed from the code lens and not reproduced here: bundle **338,680,135 bytes**, exporter child
peak **2,258 MB and still climbing**, **over twenty-five minutes** inside the method.

## What the tree can still prove without paying that cost

The exporter prints its own byte count per world at `tools/export_showcase.py:66`, and five
recorded runs under `Artifacts/` still carry those lines. The most recent of them,
`Artifacts/debug-repo-rerun.log` of 2026-09-16, passed:

```
crossroads   41,806,542
frost        49,430,830
islands      51,683,423
             -----------
three pages 142,920,795 bytes
```

Five recorded `repo-tests` logs bound the cost of the **whole stage** on 2026-09-15/16, both
exporter passes included: 273.988 s, 283.566 s, 299.944 s, 307.284 s and 462.264 s. Those are
hard upper bounds on what this test cost then. If the twenty-five-minute figure holds, one test
method now costs more than three times what the entire stage cost four days earlier.

**Those recorded runs predate the size guard, which is why none of them warns.** `islands` at
51.68 MB is above the exporter's 50 MB advisory and no advisory line was printed; the traceback
in `Artifacts/debug-repo-final.log` also puts the module entry point at line 83 of a file where
`main` now sits at `tools/export_showcase.py:96`. Quote those byte counts as the baseline the
cost has moved away from, not as a current measurement.

## The guard runs last, and it has already fired that way once

`tools/export_showcase.py:71-78` refuses any page at or above 100 MB and warns at or above
50 MB. It is a **second loop**, entered only after the generation loop has finished. So the
cheapest possible failure — a world too large to publish — is discoverable only once every world
has been generated, and `parser.error` at `tools/export_showcase.py:73` is reached with the full
cost already paid.

That shape is on record. `Artifacts/debug-repo-final.log` shows `crossroads` and `frost` printed,
then the third world raising `ValueError: sky_occurrence outside allowed range` inside
`generate_request`, then the test failing on the child's exit status. Two worlds' cost bought a
failure the third world's arguments would have shown in milliseconds.

## Why it matters

**CI pays the exporter three times per run, not once.** `.github/workflows/publish.yml:26` puts
`repo-tests` in the validate matrix; that stage is `tools/validate_repo.py:84` discovering
`tests/`, which contains this file — two exporter invocations. `.github/workflows/publish.yml:53`
runs the exporter a third time in the `build` job. Nine size-65 generations per CI run, against
two thirty-minute job budgets at `.github/workflows/publish.yml:22` and `:40`.

**The bundle is permanent history elsewhere.** `docs/publishing.md:7` records that showcase
bundles embed a whole world per page and are committed to the portfolio repository on every
`main` merge. That is the reason the size guard exists at all, and the reason an unnoticed growth
is expensive rather than merely slow.

**The invariant is worth keeping; its input size is what nobody chose.** The test asserts that
two exporter runs produce identical bytes. That is a real guarantee. Nothing about it requires
three worlds, and nothing about it requires size 65.

## Proposed fix

Three changes. The third is unconditional; the first two are alternatives and should not be
stacked without deciding what coverage is being given up.

**1. Move the guard inside the generation loop.** Check each world's size as it is produced
rather than in the second pass at `tools/export_showcase.py:71-78`. A short move that saves two
thirds of a doomed run and makes the refusal arrive at the world that caused it.

> **LANDED 2026-09-21, and it is the one of the two alternatives that was chosen.** The guard is
> now a `page_size_verdict(megabytes)` returning `'refuse'`, `'warn'` or `'ok'`, called inside
> the generation loop immediately after each page's bytes exist. The second pass over
> `manifest['worlds']` is gone. The bounds are unchanged — refuse at 100 MB, warn at 50 — and
> they are now named constants rather than literals repeated between the check and its message.
>
> **Fix 2 was rejected, and the two were explicitly not stacked**, which this card asks for. Fix
> 1 changes only *when* the refusal arrives and gives up no coverage. Fix 2 gives up a stated
> guarantee: the test would stop asserting that the **published** configuration is reproducible,
> which is a weaker claim than the one it makes today. With fix 1 and fix 3 both landed, the
> remaining cost is the six generations themselves, and paying for them buys a real guarantee
> about the artifact that actually ships. That is the conservative reading and the owner can
> reverse it by taking fix 2 as well — at which point the cost recorded in this card is what it
> would be trading for.
>
> Two tests, both cheap enough to run without generating a world, and both failing first: the
> boundary test (`AttributeError: module ... has no attribute 'page_size_verdict'`) and a
> structural test that the guard is called from inside the loop over `WORLDS`
> (`AssertionError: 'page_size_verdict' not found in {'print', 'generate_request',
> 'omit_timings', 'dict', 'len'}`). The second is the one that matters: it is what stops the
> guard drifting back out into a second pass, and it is checked by AST rather than by provoking
> an oversized world, because provoking one costs exactly what this card is about.

**2. Shrink the reproducibility input.** One world at a smaller size proves the exporter is
deterministic just as well as three at 65, while the published bundle stays at 65. **State the
cost plainly if this is chosen:** the test would stop asserting that the *published*
configuration is reproducible, which is a weaker claim than the one it makes today.

**3. Compare digests, not bytes.** `tests/test_showcase.py:24` compares two dicts of file
contents. Comparing SHA-256 hex strings instead drops the test process's own peak to nothing and
weakens no assertion — the test already computes a SHA-256 of each payload at
`tests/test_showcase.py:39`. This is free and should land regardless of the other two.

> **LANDED 2026-09-21.** `bundle_digests(directory)` in `tests/test_showcase.py` returns
> `{filename: sha256hex}`, reading each file in 1 MiB blocks so no payload is ever resident, and
> the comparison is now between two dicts of digests. The assertions that follow it needed the
> payloads, so they re-read them **from disk one page at a time** instead of from a dict holding
> all five: the first bundle is still sitting in the temporary directory, and holding it in
> memory to re-read it was never necessary.
>
> Peak in the test process for the comparison goes from two complete bundles held at once to one
> 1 MiB block. Nothing is weakened: a single changed byte, a missing file and an extra file are
> each pinned by a test, and the chunked digest is pinned equal to a whole-file
> `hashlib.sha256`, so a block-boundary bug cannot hide.
>
> Those three checks live in a new `BundleDigestTests` class that generates **no worlds**, which
> is the point — the property that the comparison is sound is now provable without paying the
> six generations that `ShowcaseTests` costs. Before the change they failed with
> `NameError: name 'bundle_digests' is not defined`.

## Acceptance and evidence

The exporter still refuses to publish an oversized page, the reproducibility assertion still
fails on a nondeterministic exporter, and one `repo-tests` stage completes inside the CI budget
with the three per-world byte counts recorded in the run log. A profile that separates world
generation from rendering would make the fix targetable; nobody has taken one.

## Does not establish

- **The three headline numbers.** 338,680,135 bytes, 2,258 MB and twenty-five minutes are all
  relayed from the code lens's review. None was reproduced here, because reproducing them costs
  exactly what this card is about.
- **Where the cost is.** The exporter both generates a world and renders it to HTML, one line
  apart, and nothing here separates them. PERF-ADD-NESTS-DOMINATES profiled generation at size
  17; nobody has profiled the renderer at any size.
- **That size 65 is the driver.** It is the obvious suspect and
  [PERF-CITY-COUNT-TRACKS-RASTER](../backlog/PERF-CITY-COUNT-TRACKS-RASTER.md) supplies a mechanism, but
  this card measured neither, and an extrapolation from a neighbouring card is not a measurement.
- **That the test is red today.** See below. It is currently unknown, and that is the point.

## Falsification

`tests/test_showcase.py:34` asserts the bundle is five files — three world pages, an index and a
manifest, of which the last two are small. Read as three pages, 338,680,135 bytes puts the mean
page near 113 MB, **above the 100 MB refusal**, which would mean the exporter is refusing and
this test is red today. Read as the six pages the two passes produce — both bundles live in one
temporary directory — the mean is 56.4 MB, under the refusal, over the advisory, and an 18%
growth on the 47.6 MB mean recorded on 2026-09-16. The second reading is arithmetically
comfortable and the first is not, but neither was measured and this card does not settle it.

One run of the exporter into a temporary directory, reading the three byte counts it prints,
decides it — and decides whether this is a cost card or a breakage card. If every page is under
100 MB, the "currently red" reading is dead and this stays a cost card. If any page is over, the
fix is urgent and the first proposal above is the one to land.

> **Attempted twice on 2026-09-21 and NOT SETTLED. This is the one item of this card the sweep
> could not close, and it is stated here rather than in a footnote.**
>
> The experiment run was the per-world half of the exporter — same recipe, same overrides, same
> `report(world, live=False)`, releasing each page before the next — which is half the test's
> cost because it skips the second pass the determinism check needs. It still did not finish.
>
> - **Attempt 1** was abandoned after ~25 minutes when it became clear it had imported
>   `terrain_settlements` before another session added a constant `city_planner` needs, so it was
>   going to die at `fill_cities` after paying for a world. Killed by PID.
> - **Attempt 2** ran the phase-16 import chain up front to fail fast, and was still inside its
>   **first** size-65 world after 385 CPU-seconds on a machine at 100% with 42 python processes.
>
> **A provenance trap worth recording, because it would have made the answer wrong rather than
> late.** Attempt 2 started at 02:12 and `terrain_nests.py` was restructured at 02:14, which
> changed generated content substantially — the same world carries 411 monster lairs after the
> change against 256 before. Page size follows content, so attempt 2's byte counts would have
> described a generator that no longer exists, and would have *understated* current pages.
> Byte counts are immune to contention; they are not immune to the tree moving underneath them.
>
> **What is still known, and it is not nothing.** Five recorded runs put pages at 37.7-51.7 MB,
> and the arithmetic in this section already favours the six-page reading (mean 56.4 MB, under
> the refusal) over the three-page one (113 MB, over it). Reaching 100 MB from ~50 needs a
> doubling, and the nest change is a fraction of a page. **The cost reading remains much the more
> likely and it is still not measured.** Whoever picks this up needs one quiet machine and about
> ten minutes — and should re-read the digest of `terrain_nests.py` before and after, because
> this is the second card tonight whose numbers moved because that file did.

## Not owned

Pre-existing. Interrupting this test is what produced
[PERF-SUITE-RUNNER-ORPHANS-CHILD](../done/PERF-SUITE-RUNNER-ORPHANS-CHILD.md); the two findings were
observed together and are separate cards because the orphaning is not specific to the showcase.

## Handoff

Converted from M5 of [233182e-code-red-team](../../docs/reviews/233182e-code-red-team.md). The
six-generation structure, the three-times-per-CI-run cost, the guard-runs-last shape and the five
recorded runs were established here; the three headline figures were relayed.

## The falsification ran 2026-09-21 — it is a BREAKAGE card, not a cost card

The card says its falsification run "decides whether this is a cost card or a breakage card".
It has now run, and the answer is breakage: **`export_showcase.py` cannot produce a publishable
bundle at all.**

    $ PYTHONPATH=Sim python tools/export_showcase.py --source . --output <tmp> --allow-dirty
    crossroads 312965123 bytes
    export_showcase.py: error: crossroads.html is 313.0 MB; GitHub rejects files at 100 MB.
    exit 2

**313 MB against a 100 MB hard limit, on the first page generated.** The exporter refuses and
stops, which is the size guard working — fix 1 moved it inside the generation loop, so it now
fails on page one instead of after generating every world. That is the whole benefit of fix 1,
demonstrated: the old shape did all the work first and refused afterwards.

**This is not new tonight, and the card already half-knew it.** The guard and its 100 MB bound
are byte-identical to HEAD — `git diff tools/export_showcase.py` shows only the guard's *position*
moved, nothing about what is embedded. The card's own investigation recorded a reading of "a page
near 113 MB, **above the 100 MB refusal**, which would mean the exporter is refusing", and could
not decide between that and a 56.4 MB mean. The first reading was right.

**The 41,806,542-byte `crossroads` figure in this card is superseded** and should not be requoted.
The grid is `size: 65` (`export_showcase.py:74`, unchanged), so a page carries a size-65 world
with `build_stages` — and `build_stages` is roughly two thirds of a world document.

**What this means for the card's three fixes.** Fix 3 (SHA-256 digests) and fix 1 (guard inside
the loop) have landed and are correct. Neither makes the bundle publishable, because the
deliverable was never reachable: no arrangement of digests or guard placement gets a 313 MB page
under 100 MB. The remaining question is the one the guard's own error message asks — **reduce the
showcase grid size, or stop embedding `build_stages` in the bundle** — and that is a product
decision about what the showcase is for, not a performance fix.

`tests/test_showcase.py::test_bundle_is_fresh_reproducible_and_traceable` errors for this reason
and will keep erroring until that decision is taken. It is not a flaky test and not a regression
from the 2026-09-21 sweep.
