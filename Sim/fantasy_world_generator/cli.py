"""Command-line publishing interface for worlds and capability catalogues."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Optional

from .asset_list import compile_asset_list
from .capabilities import capabilities_document
from icarus_sim.terrain_world import generate_request


def _write_json(path: Path, value: Any, indent: Optional[int] = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    separators = (",", ":") if indent is None else None
    path.write_text(json.dumps(value, ensure_ascii=False, indent=indent, separators=separators, allow_nan=False) + "\n",
                    encoding="utf-8")


def _without_timings(value: Any) -> Any:
    """Drop wall-clock measurements so an exported world is byte-reproducible.

    Timings are a profiling aid, not part of the interchange contract, and they
    are the only reason two runs of the same seed differed. terrain_patch emits a
    scalar while every other producer emits a map, so both shapes are removed.
    """
    if isinstance(value, dict):
        return {key: _without_timings(item) for key, item in value.items() if key != "timing_ms"}
    if isinstance(value, list):
        return [_without_timings(item) for item in value]
    return value


def world_document(request: dict[str, Any], build_stages: bool = False, timings: bool = False) -> dict[str, Any]:
    """Assemble the published world document.

    `build_stages` holds sixteen cumulative snapshots for the browser lab's stage
    inspector. They are roughly two thirds of the payload and no consumer of the
    exported document reads them, so they are opt-in here.
    """
    result = generate_request(request)
    if not build_stages:
        result.pop("build_stages", None)
    document = {
        "schema": "fantasy-world-generator.world",
        "schema_version": 2,
        **result,
        # The sim owns this: it is the generation-algorithm version the age API and
        # the published schema pin, not the package version in __init__.
        "generator_version": result["generator_version"],
    }
    return document if timings else _without_timings(document)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="fantasy-world", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Generate an Unreal-consumable world JSON document")
    generate.add_argument("--request", type=Path, help="JSON request with seed, recipe_version, and overrides")
    generate.add_argument("--seed", type=int)
    generate.add_argument("--size", type=int, help="Convenience override for grid size")
    generate.add_argument("--phase", type=int, help="Convenience override for generation phase")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--include-build-stages", action="store_true",
                          help="Embed the browser lab's sixteen cumulative stage snapshots (roughly triples the file)")
    generate.add_argument("--include-timings", action="store_true",
                          help="Keep wall-clock timing_ms values; the output is then not byte-reproducible")
    generate.add_argument("--pretty", action="store_true",
                          help="Indent the document for reading; interchange output is compact by default")

    assets = commands.add_parser("asset-list", help="Compile the exhaustive potential-state asset list")
    assets.add_argument("--output", type=Path, required=True)
    capabilities = commands.add_parser("capabilities", help="Export supported reference contracts and coordinate conventions")
    capabilities.add_argument("--version", type=int, default=1, help="Capability descriptor version (default: 1)")
    capabilities.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "capabilities":
            _write_json(args.output, capabilities_document(args.version))
            return 0
        if args.command == "asset-list":
            _write_json(args.output, compile_asset_list())
            return 0
        if args.request:
            if args.seed is not None or args.size is not None or args.phase is not None:
                raise ValueError("--request cannot be combined with seed/size/phase convenience options")
            request = json.loads(args.request.read_text(encoding="utf-8"))
        else:
            overrides = {key: value for key, value in {"size": args.size, "phase": args.phase}.items() if value is not None}
            request = {"recipe_version": 3, "seed": 42 if args.seed is None else args.seed, "overrides": overrides}
        # Fail on an unwritable destination before spending a full generation on it.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.touch()
        document = world_document(request, build_stages=args.include_build_stages, timings=args.include_timings)
        _write_json(args.output, document, indent=2 if args.pretty else None)
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser().error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
