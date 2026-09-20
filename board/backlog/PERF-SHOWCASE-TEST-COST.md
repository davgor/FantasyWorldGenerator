# PERF-SHOWCASE-TEST-COST — one test method generates six worlds, and the guard that would stop it runs last

Owner: none. State: backlog, unowned. Found by the code red team auditing `233182e`
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

**2. Shrink the reproducibility input.** One world at a smaller size proves the exporter is
deterministic just as well as three at 65, while the published bundle stays at 65. **State the
cost plainly if this is chosen:** the test would stop asserting that the *published*
configuration is reproducible, which is a weaker claim than the one it makes today.

**3. Compare digests, not bytes.** `tests/test_showcase.py:24` compares two dicts of file
contents. Comparing SHA-256 hex strings instead drops the test process's own peak to nothing and
weakens no assertion — the test already computes a SHA-256 of each payload at
`tests/test_showcase.py:39`. This is free and should land regardless of the other two.

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
  [PERF-CITY-COUNT-TRACKS-RASTER](PERF-CITY-COUNT-TRACKS-RASTER.md) supplies a mechanism, but
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

## Not owned

Pre-existing. Interrupting this test is what produced
[PERF-SUITE-RUNNER-ORPHANS-CHILD](PERF-SUITE-RUNNER-ORPHANS-CHILD.md); the two findings were
observed together and are separate cards because the orphaning is not specific to the showcase.

## Handoff

Converted from M5 of [233182e-code-red-team](../../docs/reviews/233182e-code-red-team.md). The
six-generation structure, the three-times-per-CI-run cost, the guard-runs-last shape and the five
recorded runs were established here; the three headline figures were relayed.
