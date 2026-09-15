"""Compile every asset identity reachable from supported generator states."""

from __future__ import annotations

from collections import Counter
import hashlib
from importlib.resources import files
import json
from typing import Any

from icarus_sim.terrain_biomes import BIOMES


SCHEMA = "fantasy-world-generator.asset-list"
SCHEMA_VERSION = 1
COLD_BIOMES = [
    ("Boreal forest", [56, 104, 95]),
    ("Cold tundra", [152, 164, 136]),
    ("Persistent land ice", [223, 240, 245]),
]


def _load(package: str, name: str) -> Any:
    return json.loads(files(package).joinpath(name).read_text(encoding="utf-8"))


def _terrain_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": f"terrain.biome.{index:03d}",
            "kind": "terrain_surface",
            "name": name,
            "source": "simulation.biomes",
            "status": "supported",
            "selectors": {"biome_ids": [index]},
            "metadata": {"display_color_rgb": color},
        }
        for index, (name, color) in enumerate(BIOMES + COLD_BIOMES)
    ]



def _history_assets() -> list[dict[str, Any]]:
    from icarus_sim.terrain_history import biome_catalogue
    result = [{
        'id': biome['asset_id'], 'kind': 'terrain_surface', 'name': biome['name'],
        'source': 'simulation.biome_mutations', 'status': 'supported',
        'selectors': {'core_biome_id': biome['core_biome_id'], 'core': biome['core'], 'magic_school': biome['magic_school']},
        'metadata': {'display_color_rgb': biome['color'], 'group': biome['group'], 'recipe_version': 2},
    } for biome in biome_catalogue()]
    result.append({'id': 'marker.city_ruins', 'kind': 'marker', 'name': 'City ruins',
                   'source': 'simulation.history', 'status': 'supported',
                   'selectors': {'settlement_role': 'ruins'},
                   'metadata': {'source_culture': 'carried by each generated ruin', 'recipe_version': 2}})
    return result

def _creature_assets() -> list[dict[str, Any]]:
    result = []
    for profile in _load("icarus_sim", "terrain_nest_profiles.json")["profiles"]:
        metadata = {key: value for key, value in profile.items() if key not in {"id", "name"}}
        result.append(
            {
                "id": "creature." + profile["id"],
                "kind": "creature",
                "name": profile["name"],
                "source": "simulation.creature_profiles",
                "status": "supported",
                "selectors": {
                    "species_id": profile["id"],
                    "medium": profile["medium"],
                    "family": profile["family"],
                },
                "metadata": metadata,
            }
        )
    return result


def _building_assets() -> list[dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}
    for pack in _load("icarus_sim", "terrain_city_building_packs.json")["packs"]:
        for option in pack["building_options"]:
            for choice in option["asset_choices"]:
                asset_id = choice["asset_id"]
                row = references.setdefault(
                    asset_id,
                    {
                        "id": "building." + asset_id,
                        "kind": "building",
                        "name": asset_id.replace("_", " ").title(),
                        "source": "simulation.building_packs",
                        "status": "supported",
                        "selectors": {"asset_id": asset_id},
                        "metadata": {"references": []},
                    },
                )
                row["metadata"]["references"].append(
                    {"pack_id": pack["id"], "option_id": option["id"], "weight": choice["weight"]}
                )
    for row in references.values():
        row["metadata"]["references"].sort(key=lambda item: (item["pack_id"], item["option_id"], item["weight"]))
    return list(references.values())


def _production_assets() -> list[dict[str, Any]]:
    result = []
    for item in _load(__package__, "world_asset_requirements.json")["assets"]:
        metadata = {key: value for key, value in item.items() if key not in {"id", "name", "kind", "status", "biome_ids", "people", "settlement_role"}}
        selectors = {
            key: item[key]
            for key in ("biome_ids", "people", "settlement_role")
            if item.get(key) is not None
        }
        result.append(
            {
                "id": "production." + item["id"].lower(),
                "kind": item["kind"],
                "name": item["name"],
                "source": "production.world_asset_catalogue",
                "status": item["status"],
                "selectors": selectors,
                "metadata": metadata,
            }
        )
    return result


def compile_asset_list() -> dict[str, Any]:
    """Return a deterministic, normalized potential-state asset catalogue."""
    assets = _terrain_assets() + _creature_assets() + _building_assets() + _production_assets() + _history_assets()
    assets.sort(key=lambda item: item["id"])
    ids = [item["id"] for item in assets]
    if len(ids) != len(set(ids)):
        duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
        raise ValueError(f"duplicate normalized asset IDs: {duplicates}")
    canonical = json.dumps(assets, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "scope": "All assets reachable from supported potential generator states; not a single generated world.",
        "content_sha256": hashlib.sha256(canonical).hexdigest(),
        "summary": {
            "total": len(assets),
            "by_kind": dict(sorted(Counter(item["kind"] for item in assets).items())),
            "by_source": dict(sorted(Counter(item["source"] for item in assets).items())),
        },
        "assets": assets,
    }
