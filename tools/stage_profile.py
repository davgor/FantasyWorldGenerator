"""Measure one generation run stage by stage and write the outline.

    python tools/stage_profile.py --size 128 --seed 42

Writes a JSON record and prints a Markdown outline: every one of the sixteen stages with
its wall time, share of the run, cumulative share and resident memory, then the named
steps inside each stage with call counts and self time.

What the numbers are
--------------------
`wall_ms` per stage is measured around the stage body plus the snapshot capture, and the
two are reported apart, because the capture is the generator's own bookkeeping rather than
world building and a reader should be able to price it separately.

`self_ms` on a step is its total time minus the time of the named steps it called. A pass
with a large self time and no children spent it in its own per-cell loops. Steps are named
from a fixed list in `icarus_sim.terrain_profile`; anything unnamed lands in the self time
of its caller, so a stage's step rows do not add up to its `wall_ms` and are not meant to.

`calls` matters as much as the time. Several passes run once per stage for three stages
and again inside each age transition, so an 11-call row is eleven whole executions of that
pass, not one slow one.

Cost
----
This is a full generation, and generation is superlinear in grid size. Measured on one
desktop at seed 42, phase 16: size 17 is about 80 s, size 33 about 260 s. Budget an hour
or more at size 128 and several gigabytes of resident memory: the sixteen stage snapshots
hold a copy of every layer that changed, and they are not optional -- `generate_history`
builds them whether or not anyone exports them.

Nothing here is a gate. It measures; it does not pass or fail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

DEFAULT_OUTPUT = ROOT / "Artifacts" / "stage-profile"


def machine():
    """What the numbers were taken on. A cost figure without this is not a measurement."""
    record = {"python": platform.python_version(), "platform": platform.platform(),
              "processor": platform.processor() or platform.machine()}
    try:
        import psutil
        record["cores"] = psutil.cpu_count(logical=False)
        record["threads"] = psutil.cpu_count(logical=True)
        record["ram_gb"] = round(psutil.virtual_memory().total / 1073741824., 1)
        # A run sharing the box with something else is a different measurement. Record
        # what the box was doing rather than leaving the reader to wonder.
        record["load_percent_at_start"] = psutil.cpu_percent(interval=1.0)
    except ImportError:
        record["cores"] = record["threads"] = record["ram_gb"] = None
    return record


def run(seed, size, phase, progress_path=None):
    from icarus_sim.terrain_world import generate_request
    from icarus_sim import terrain_profile

    request = {"recipe_version": 3, "seed": seed, "overrides": {"size": size, "phase": phase}}
    started = time.perf_counter()

    def announce(stage, profile):
        """One line and one JSON rewrite per stage, so a multi-hour run is watchable.

        The partial file matters as much as the line: a run that is killed at stage 14 --
        for memory, for the box being wanted back -- should still leave the thirteen
        stages it did measure, rather than nothing.
        """
        print("  stage %2d/%d  %-24s %9.1f s  RSS %s MB  (elapsed %.1f s)"
              % (stage["stage"], phase, stage["title"], stage["wall_ms"] / 1000.,
                 stage["rss_mb"], time.perf_counter() - started), flush=True)
        if progress_path is not None:
            partial = {"partial": True, "completed_stages": len(profile.stages),
                       "phase": phase, "request": request,
                       "elapsed_s": round(time.perf_counter() - started, 1),
                       "stages": profile.stages,
                       "steps": sorted(profile.steps.values(), key=lambda r: (r["stage"], -r["self_ms"]))}
            progress_path.write_text(json.dumps(partial, indent=2, default=str) + chr(10), encoding="utf-8")

    with terrain_profile.profile_run(progress=announce) as profile:
        world = generate_request(request)
    elapsed = time.perf_counter() - started
    report = profile.report(label="seed %d, size %d, phase %d" % (seed, size, phase))
    report["request"] = request
    report["total_s"] = round(elapsed, 3)
    report["machine"] = machine()
    report["counts"] = counts(world)
    return report, world


def counts(world):
    """A few content counts, so a stage's cost can be read against what it produced.

    Blocks disagree about what they call their collection -- `sites`, `plans`, `people`,
    `locations`, `bands`, `entries` -- and a wrong guess reports a real population as
    `None`, which reads like "this pass produced nothing". So rather than naming the key
    per block, take the longest list anywhere one level inside it and say which key that
    was. An approximate label beats a confident null.
    """
    BLOCKS = ('settlements', 'city_plans', 'hamlet_plans', 'castle_plans', 'roads',
              'beast_nests', 'key_locations', 'key_location_plans', 'npcs', 'heroes',
              'story_web', 'nomads', 'beast_movements', 'encounters', 'ruins',
              'villains', 'threat_assessments', 'build_stages')
    record = {'cells': world['config']['size'] ** 2,
              'resolved_octaves': world.get('resolved_octaves'),
              'layers': len(world.get('layers') or {})}
    for name in BLOCKS:
        block = world.get(name)
        if isinstance(block, list):
            record[name] = len(block)
        elif isinstance(block, dict):
            best = max(((len(v), k) for k, v in block.items() if isinstance(v, list)),
                       default=(None, None))
            record[name] = best[0] if best[1] is None else '%d (%s)' % best
        else:
            record[name] = None
    return record


def _bar(share, width=28):
    filled = int(round(share * width))
    return "#" * filled + "." * (width - filled)


def outline(report):
    lines = []
    total = report["stage_wall_ms"] or 1.
    lines.append("# Stage profile - %s" % report["label"])
    lines.append("")
    machine_record = report["machine"]
    lines.append("Total %.1f s, stages %.1f s, peak RSS %s MB. %s cores / %s threads, %s GB RAM, "
                 "Python %s, CPU %s%% busy at start."
                 % (report["total_s"], total / 1000., report["peak_rss_mb"],
                    machine_record.get("cores"), machine_record.get("threads"),
                    machine_record.get("ram_gb"), machine_record["python"],
                    machine_record.get("load_percent_at_start")))
    lines.append("")
    lines.append("Subject: measured-code digest `%s` over %d modules. A later report with a "
                 "different digest measured different code."
                 % (report["subject"]["combined"], len(report["subject"]["modules"])))
    lines.append("")
    lines.append("| # | Stage | Body s | Capture s | Total s | Share | Cum | RSS MB | dRSS | Layers |")
    lines.append("|---|-------|-------:|----------:|--------:|------:|----:|-------:|-----:|-------:|")
    cumulative = 0.
    for stage in report["stages"]:
        cumulative += stage["wall_ms"]
        lines.append("| %d | %s | %.1f | %.1f | %.1f | %.1f%% | %.1f%% | %s | %+.0f | %d |"
                     % (stage["stage"], stage["title"], stage["body_ms"] / 1000.,
                        stage["capture_ms"] / 1000., stage["wall_ms"] / 1000.,
                        100. * stage["wall_ms"] / total, 100. * cumulative / total,
                        stage["rss_mb"], stage["rss_delta_mb"] or 0., stage["layers_after"]))
    lines.append("")
    lines.append("## Where the time goes")
    lines.append("")
    for stage in sorted(report["stages"], key=lambda s: -s["wall_ms"]):
        share = stage["wall_ms"] / total
        lines.append("    %-2d %-26s %8.1f s  %5.1f%%  %s"
                     % (stage["stage"], stage["title"][:26], stage["wall_ms"] / 1000.,
                        100. * share, _bar(share)))
    lines.append("")
    lines.append("## Named steps, by self time")
    lines.append("")
    lines.append("| Step | Stages | Calls | Self s | Total s | Slowest call s |")
    lines.append("|------|--------|------:|-------:|--------:|---------------:|")
    merged = {}
    for record in report["steps"]:
        entry = merged.setdefault(record["label"], {"stages": set(), "calls": 0,
                                                    "self_ms": 0., "total_ms": 0., "max_ms": 0.})
        entry["stages"].add(record["stage"])
        entry["calls"] += record["calls"]
        entry["self_ms"] += record["self_ms"]
        entry["total_ms"] += record["total_ms"]
        entry["max_ms"] = max(entry["max_ms"], record["max_ms"])
    for label, entry in sorted(merged.items(), key=lambda item: -item[1]["self_ms"]):
        stages = ",".join(str(s) for s in sorted(entry["stages"]))
        lines.append("| %s | %s | %d | %.1f | %.1f | %.1f |"
                     % (label, stages, entry["calls"], entry["self_ms"] / 1000.,
                        entry["total_ms"] / 1000., entry["max_ms"] / 1000.))
    lines.append("")
    lines.append("## Step detail, stage by stage")
    lines.append("")
    lines.append("Self time only, worst first, and only steps above 0.05 s. A stage with no rows")
    lines.append("spent its time in code no target names.")
    by_stage = {}
    for record in report["steps"]:
        by_stage.setdefault(record["stage"], []).append(record)
    for stage in report["stages"]:
        rows = sorted(by_stage.get(stage["stage"], []), key=lambda r: -r["self_ms"])
        lines.append("")
        lines.append("**%d. %s** - %.1f s" % (stage["stage"], stage["title"], stage["wall_ms"] / 1000.))
        for record in rows:
            if record["self_ms"] < 50.:
                continue
            lines.append("    %-46s %8.2f s self  %8.2f s total  x%d"
                         % (record["label"], record["self_ms"] / 1000.,
                            record["total_ms"] / 1000., record["calls"]))
        subsystem = {k: v for k, v in (stage["subsystem_ms"] or {}).items() if abs(v) >= 50.}
        for key, value in sorted(subsystem.items(), key=lambda item: -item[1]):
            lines.append("    %-46s %8.2f s  (timing_ms delta)" % (key, value / 1000.))
    # Steps recorded outside any stage: the closeout work generate_history does after the
    # loop. Stage 0 is not a stage, and calling it one in the table would be a lie.
    closeout = sorted(by_stage.get(0, []), key=lambda r: -r["self_ms"])
    if closeout:
        lines.append("")
        lines.append("**After the loop** (closeout, outside every stage)")
        for record in closeout:
            lines.append("    %-46s %8.2f s self  x%d"
                         % (record["label"], record["self_ms"] / 1000., record["calls"]))
    if report["missing_targets"]:
        lines.append("")
        lines.append("**Unmeasured targets** (named in `terrain_profile.STEP_TARGETS` but not found, "
                     "so their cost is hidden inside a caller): "
                     + ", ".join(report["missing_targets"]))
    lines.append("")
    lines.append("## What the world came out as")
    lines.append("")
    for key, value in report["counts"].items():
        lines.append("    %-18s %s" % (key, value))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=128, help="Grid cells along one edge (default: 128)")
    parser.add_argument("--phase", type=int, default=16, help="How far through the sixteen stages to run")
    parser.add_argument("--output", type=Path, default=None,
                        help="Base path for the .json and .md outputs "
                             "(default: Artifacts/stage-profile-<size>)")
    arguments = parser.parse_args(argv)

    base = arguments.output or Path(str(DEFAULT_OUTPUT) + "-%d" % arguments.size)
    base.parent.mkdir(parents=True, exist_ok=True)
    print("Generating: seed %d, size %d (%d cells), phase %d. This is a full generation."
          % (arguments.seed, arguments.size, arguments.size ** 2, arguments.phase), flush=True)
    report, _ = run(arguments.seed, arguments.size, arguments.phase,
                    progress_path=base.with_suffix(".progress.json"))
    text = outline(report)
    base.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    base.with_suffix(".md").write_text(text, encoding="utf-8")
    print(text)
    print("Wrote %s and %s" % (base.with_suffix(".json").name, base.with_suffix(".md").name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
