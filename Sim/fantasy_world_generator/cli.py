"""Command-line publishing interface for worlds and capability catalogues."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Optional

from . import __version__
from .asset_list import compile_asset_list
from .capabilities import capabilities_document
from icarus_sim.terrain_world import generate_request


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def world_document(request: dict[str, Any]) -> dict[str, Any]:
    result = generate_request(request)
    return {
        "schema": "fantasy-world-generator.world",
        "schema_version": 2,
        "generator_version": __version__,
        **result,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="fantasy-world", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Generate an Unreal-consumable world JSON document")
    generate.add_argument("--request", type=Path, help="JSON request with seed, recipe_version, and overrides")
    generate.add_argument("--seed", type=int)
    generate.add_argument("--size", type=int, help="Convenience override for grid size")
    generate.add_argument("--phase", type=int, help="Convenience override for generation phase")
    generate.add_argument("--output", type=Path, required=True)

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
        _write_json(args.output, world_document(request))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser().error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
