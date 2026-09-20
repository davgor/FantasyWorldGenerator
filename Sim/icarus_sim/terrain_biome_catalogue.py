"""Natural surfaces and explicit natural-core / magic-school states.

The identities themselves live in the sibling `biomes.json`; this module is the logic that
reads them. Position in that file is a contract, for the reason `biome_catalogue` gives, so
the registry stores `natural_biomes` as an ordered list rather than an object and the loader
below preserves that order without sorting it.
"""
import json
from pathlib import Path
from .terrain_leyline_history import SCHOOLS, KNOWN_SCHOOLS, HIDDEN_SCHOOLS

REGISTRY_PATH = Path(__file__).with_name('biomes.json')


def _registry():
    """Fail closed: a registry that has lost a school or a name is not a smaller catalogue."""
    document = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    if document.get('schema_version') != 1:
        raise ValueError('biomes.json must declare schema version 1')
    rows = document['natural_biomes']
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('biomes.json has a duplicate natural biome id')
    names = document['variant_names']
    if set(names) != set(SCHOOLS):
        raise ValueError('biomes.json must name every school in SCHOOLS, and no others')
    if any(len(v) != len(rows) for v in names.values()):
        raise ValueError('every school needs one variant name per natural biome, in catalogue order')
    return rows, names


_ROWS, _NAMES = _registry()
NATURAL_BIOMES = {row['id']: row['core'] for row in _ROWS}
NATURAL_COLORS = {row['id']: list(row['color']) for row in _ROWS}
VARIANT_NAMES = {school: list(values) for school, values in _NAMES.items()}


def _entry(i,bid,core,school):
    return dict(id=f'{core}.{school}', core=core, core_biome_id=bid, magic_school=school,
                group=SCHOOLS[school][0], descriptors=SCHOOLS[school][1],
                name=VARIANT_NAMES[school][i], color=SCHOOLS[school][2],
                asset_id=f'terrain.mutation.{core}.{school}')


def _block(schools):
    return [_entry(i,bid,core,school)
            for i,(bid,core) in enumerate(NATURAL_BIOMES.items()) for school in schools]


def biome_catalogue():
    """Every core crossed with every school: the known block first, then the hidden one.

    A position in this list is a contract. `biome_variant` stores a flat index into it, so
    the known cores-by-schools block keeps the positions it has always had and hidden
    schools take the positions after it. That is why this is two passes and not more
    columns in one: another column would renumber every variant in every saved world.
    Both blocks go through one entry builder so key insertion order, which the output
    bytes depend on, cannot drift between them.
    """
    return _block(KNOWN_SCHOOLS)+_block(HIDDEN_SCHOOLS)


def natural_catalogue():
    return [dict(id=bid, core=core,
                 name='Persistent land ice' if bid == 17 else core.replace('_', ' ').capitalize(),
                 color=list(NATURAL_COLORS[bid]), asset_id=f'terrain.biome.{bid:03d}')
            for bid, core in NATURAL_BIOMES.items()]


def cell_variant(result, x, z):
    index = result['layers'].get('biome_variant')
    value = index[z][x] if index is not None else -1
    return result['terrain']['magical_biomes'][value]['id'] if value >= 0 else None
