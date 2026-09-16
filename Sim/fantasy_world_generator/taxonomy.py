"""Versioned terrain identity lookup; independent of generator implementation."""
from __future__ import annotations

import json
from importlib.resources import files


def taxonomy_document() -> dict:
    """Return a caller-owned copy of the packaged canonical taxonomy."""
    return json.loads(files(__package__).joinpath('terrain_taxonomy.json').read_text(encoding='utf-8'))


def resolve_terrain_identity(request: dict) -> dict:
    """Resolve a strict v1/recipe-3 request or raise ValueError without coercion."""
    required = {'taxonomy_version', 'recipe_version', 'natural_biome_id', 'magic_school'}
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError('terrain identity request must contain exactly: ' + ', '.join(sorted(required)))
    for key in ('taxonomy_version', 'recipe_version', 'natural_biome_id'):
        if type(request[key]) is not int:
            raise ValueError(key + ' must be an integer (not a boolean, float or string)')
    document = taxonomy_document()
    if request['taxonomy_version'] != document['taxonomy_version']:
        raise ValueError('unsupported taxonomy_version')
    if request['recipe_version'] != document['recipe_version']:
        raise ValueError('unsupported recipe_version; regenerate retired worlds')
    natural_id = request['natural_biome_id']
    cores = {row['id']: row['core'] for row in document['natural_biomes']}
    if natural_id not in cores:
        raise ValueError('unknown or retired natural_biome_id')
    school = request['magic_school']
    if school is not None and (not isinstance(school, str) or school not in document['schools']):
        raise ValueError('unknown magic_school; aliases are not supported')
    core = cores[natural_id]
    variant = None if school is None else core + '.' + school
    return {
        'natural_biome_id': natural_id,
        'core': core,
        'magic_school': school,
        'variant_id': variant,
        'asset_id': f'terrain.biome.{natural_id:03d}' if variant is None else 'terrain.mutation.' + variant,
    }
