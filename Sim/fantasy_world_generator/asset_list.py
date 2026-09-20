"""Compile every asset identity reachable from supported generator states."""

from __future__ import annotations

from collections import Counter
import hashlib
from importlib.resources import files
import json
from typing import Any

from icarus_sim.terrain_biome_catalogue import natural_catalogue, biome_catalogue


SCHEMA = "fantasy-world-generator.asset-list"
SCHEMA_VERSION = 2


def _load(package: str, name: str) -> Any:
    return json.loads(files(package).joinpath(name).read_text(encoding="utf-8"))


def _terrain_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": biome["asset_id"],
            "kind": "terrain_surface",
            "name": biome["name"],
            "source": "simulation.biomes",
            "status": "supported",
            "selectors": {"biome_ids": [biome["id"]]},
            "metadata": {"display_color_rgb": biome["color"]},
        }
        for biome in natural_catalogue()
    ]



def _history_assets() -> list[dict[str, Any]]:
    from icarus_sim.terrain_history import biome_catalogue
    result = [{
        'id': biome['asset_id'], 'kind': 'terrain_surface', 'name': biome['name'],
        'source': 'simulation.biome_mutations', 'status': 'supported',
        'selectors': {'core_biome_id': biome['core_biome_id'], 'core': biome['core'], 'magic_school': biome['magic_school']},
        'metadata': {'display_color_rgb': biome['color'], 'group': biome['group'], 'recipe_version': 3},
    } for biome in biome_catalogue()]
    result.append({'id': 'marker.city_ruins', 'kind': 'marker', 'name': 'City ruins',
                   'source': 'simulation.history', 'status': 'supported',
                   'selectors': {'settlement_role': 'ruins'},
                   'metadata': {'source_culture': 'carried by each generated ruin', 'recipe_version': 3}})
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
    from icarus_sim.terrain_profiles import civilization_ids
    from icarus_sim.civilization_registry import building_pack_data
    known=set(civilization_ids())
    references: dict[str, dict[str, Any]] = {}
    for pack in building_pack_data()["packs"]:
        pack_people=set(pack['criteria'].get('population_profiles',known)) & known
        for option in pack["building_options"]:
            option_people=option.get('profiles',option.get('count',{}).get('profiles'))
            people=pack_people & (set(option_people) if option_people else known)
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
                    {"pack_id": pack["id"], "option_id": option["id"], "weight": choice["weight"],
                     "civilization_ids": sorted(people)}
                )
    for row in references.values():
        row["metadata"]["references"].sort(key=lambda item: (item["pack_id"], item["option_id"], item["weight"]))
    return list(references.values())


def _production_assets() -> list[dict[str, Any]]:
    result = []
    catalogue = _load(__package__, "world_asset_requirements.json")
    if catalogue.get("schema_version") != 2:
        raise ValueError("Production catalogue requires schema 2")
    natural_ids = {b["id"] for b in natural_catalogue()}
    variant_ids = {b["id"] for b in biome_catalogue()}
    for item in catalogue["assets"]:
        for field, allowed, kind in (("biome_ids", natural_ids, int), ("biome_variant_ids", variant_ids, str)):
            if field in item and (not isinstance(item[field], list) or any(type(v) is not kind or v not in allowed for v in item[field])):
                raise ValueError("Invalid production biome selector: " + item["id"] + "." + field)
        metadata = {key: value for key, value in item.items() if key not in {"id", "name", "kind", "status", "biome_ids", "biome_variant_ids", "people", "settlement_role"}}
        selectors = {
            key: item[key]
            for key in ("biome_ids", "biome_variant_ids", "people", "settlement_role")
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


def _city_planner_assets():
    from icarus_sim.civilization_registry import section
    rows=[s for key, library in section('structure_blocks').items() if key != 'castle'
          for block in library['blocks'] for s in block['structures']]
    rows+=list(section('housing_profiles').values())
    return [{'id':s['id'],'kind':'building','name':s['name'],'source':'simulation.city_planner',
             'status':'schematic','selectors':{'building_id':s['id']},
             'metadata':{'dimensions_m':s['dimensions_m'],'plot_m':s['plot_m'],
                         'rendering':'Labeled rectangle; production art remains unassigned'}} for s in rows]


def _castle_planner_assets():
    from icarus_sim.civilization_registry import section
    library=section('structure_blocks')['castle']
    rows=[s for block in library['blocks'] for s in block['structures']]
    return [{'id':s['id'],'kind':'building','name':s['name'],'source':'simulation.castle_planner',
             'status':'schematic','selectors':{'building_id':s['id']},
             'metadata':{'dimensions_m':s['dimensions_m'],'plot_m':s['plot_m'],
                         'rendering':'Fortification module or bailey shell; production art remains unassigned'}} for s in rows]


def _key_location_assets() -> list[dict[str, Any]]:
    """One marker per key-location archetype.

    The catalogue has no cave, tomb, waystone or standing-stone mesh, so these are markers
    with production art unassigned rather than claims of supported geometry. They are listed
    because the exhaustive list describes every potential final state, and a generated world
    can reference any of these the moment the archetype places.
    """
    from key_locations.catalogue import load

    document = load()
    rows = []
    for archetype in document["archetypes"]:
        family = document["families"][archetype["family"]]
        rows.append({
            "id": f"marker.key_location.{archetype['id']}",
            "kind": "marker",
            "name": archetype["name"],
            "source": "simulation.key_locations",
            "status": "schematic",
            "selectors": {"key_location_kind": archetype["id"]},
            "metadata": {
                "family": archetype["family"],
                "tier": archetype["tier"],
                "domain": archetype["domain"],
                "display_color_rgb": family["color"],
                "glyph": family["glyph"],
                "interior": bool(archetype.get("interior")),
                "rendering": "Map marker; production art remains unassigned.",
                "catalogue_revision": document["revision"],
                "recipe_version": 3,
            },
        })
    return rows


def _key_location_part_assets() -> list[dict[str, Any]]:
    """One identity per exterior kit part.

    These are the things that actually stand on the ground at a location, so unlike the
    per-archetype markers they carry real footprints and dimensions. Still schematic: the
    metres are sized for legibility and no production art is assigned.
    """
    from key_locations.exteriors import load

    document = load()
    return [{
        "id": part["id"],
        "kind": "building" if part["kind"] == "structure" else "marker",
        "name": part["name"],
        "source": "simulation.key_location_exteriors",
        "status": "schematic",
        "selectors": {"part_id": part["id"]},
        "metadata": {
            "part_kind": part["kind"],
            "dimensions_m": part["dimensions_m"],
            "plot_m": part["plot_m"],
            "rendering": "Labeled footprint; production art remains unassigned.",
            "catalogue_revision": document["revision"],
            "recipe_version": 3,
        },
    } for part in document["parts"]]


def compile_asset_list() -> dict[str, Any]:
    """Return a deterministic, normalized potential-state asset catalogue."""
    assets = (_terrain_assets() + _creature_assets() + _building_assets() + _production_assets()
              + _history_assets() + _city_planner_assets() + _castle_planner_assets()
              + _key_location_assets() + _key_location_part_assets())
    assets.sort(key=lambda item: item["id"])
    ids = [item["id"] for item in assets]
    if len(ids) != len(set(ids)):
        duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
        raise ValueError(f"duplicate normalized asset IDs: {duplicates}")
    canonical = json.dumps(assets, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "recipe_version": 3,
        "scope": "All assets reachable from potential recipe 3 generator states; not a single generated world.",
        "content_sha256": hashlib.sha256(canonical).hexdigest(),
        "summary": {
            "total": len(assets),
            "by_kind": dict(sorted(Counter(item["kind"] for item in assets).items())),
            "by_source": dict(sorted(Counter(item["source"] for item in assets).items())),
        },
        "assets": assets,
    }
