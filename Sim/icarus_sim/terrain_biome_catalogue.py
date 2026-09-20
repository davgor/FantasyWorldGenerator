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
    allowed = {'id', 'core', 'color', 'reachable', 'unreachable_note'}
    for row in rows:
        if set(row) - allowed:
            raise ValueError('biomes.json row has an unknown key: ' + repr(sorted(set(row) - allowed)))
        if 'reachable' in row and type(row['reachable']) is not bool:
            raise ValueError('biomes.json reachable must be a boolean')
        if row.get('reachable') is False and not row.get('unreachable_note'):
            raise ValueError('a tombstoned biome must say why it is unreachable')
    if not any(row.get('reachable', True) for row in rows):
        raise ValueError('biomes.json tombstoned every natural biome')
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
UNREACHABLE_BIOMES = frozenset(row['id'] for row in _ROWS if row.get('reachable') is False)


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


def reachable_natural_catalogue():
    """natural_catalogue() minus the tombstones, for anything that commissions art.

    natural_catalogue() itself is deliberately unchanged, and so are the dicts it emits:
    terrain_history.py compares world['terrain']['biomes'] and ['natural_biomes'] against it
    for equality, so those dicts are world-output bytes and a key added here would be a key in
    every saved world and a schema change in Contracts/schemas/world-output.schema.json. A
    tombstone is a statement about commissioning, not about the contract, so it gets its own
    accessor and the contract keeps its thirteen ordered rows.
    """
    return [entry for entry in natural_catalogue() if entry['id'] not in UNREACHABLE_BIOMES]


def reachable_biome_catalogue():
    """The 156-entry cross product minus the variants whose core is tombstoned.

    biome_catalogue() keeps all 156 because biome_variant is a flat index into it; this is the
    same commissioning view, one level down.
    """
    return [entry for entry in biome_catalogue() if entry['core_biome_id'] not in UNREACHABLE_BIOMES]


def cell_variant(result, x, z):
    index = result['layers'].get('biome_variant')
    value = index[z][x] if index is not None else -1
    return result['terrain']['magical_biomes'][value]['id'] if value >= 0 else None
