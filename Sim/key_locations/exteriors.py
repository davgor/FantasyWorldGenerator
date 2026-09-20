"""The packaged exterior kits, and the plans they produce for a finished world.

A kit says what stands on the ground at a location and how it is arranged. Kits resolve per
archetype and fall back to the family, so every one of the ninety-seven has one; parts are
shared, so a rubble pile is a single asset identity wherever it appears.

The block this produces is top-level `key_location_plans`, in the same shape as `city_plans`,
`hamlet_plans` and `castle_plans` — a consumer scanning for plan blocks finds it where the
other three are, and the importer that already reads city plots reads these without a second
code path.
"""
from importlib.resources import files
import json

from .core import exterior, world as readers
from .core.exterior import ARRANGEMENTS
from .core.shaping import SHAPES
from .seeds import rng

CATALOGUE = 'exteriors.json'
VERSION = 1
PART_KINDS = ('structure', 'terrain', 'opening', 'path')
METHOD = ('One plan per key location, in the local metre frame the city and castle planners already use. A kit '
          'resolves per archetype and falls back to its family; parts are shared across kits. Seven arrangement '
          'rules place them: a single centred part, a ring, a golden-angle scatter, a row, an inward-facing '
          'courtyard, a terrace stepped along the fall of the ground, or a mouth with its approach fanned in front. '
          'Ground elevation is sampled at each plot corner, and a location in a ruined or buried state gains rubble '
          'in proportion to how far gone it is. Parts that move the ground do so: a barrow is a mound in the terrain, a quarry is a cut, a crater is a rim with a bowl inside it, and plots are seated on the shaped ground rather than on the raw layer, so a marker standing on a barrow stands on the barrow.')
LIMITS = ('Schematic footprints, not measured art: plot and dimension metres are sized for legibility and every part '
          'is a placeholder identity. Ground elevation is bilinear over the height layer, because the generator own '
          'continuous height field is not importable from a reader package - at plot scale on a multi-kilometre '
          'raster that is below one cell, so ground_elevation_m and foundation_bottom_m come out near-equal and a '
          'consumer should conform plots to its own landscape rather than trust these to describe local relief. '
          'Ground shaping is emitted twice over: as parametric primitives, which are exact and are what an engine with its own landscape should apply, and as a sampled surface grid, which is the coarse derived form for a consumer that only reads grids. Where they disagree the primitives are right.')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate exteriors key {key!r}')
        result[key] = value
    return result


def _reject(token):
    raise ValueError(f'non-finite exteriors number {token}')


def load():
    text = files('key_locations').joinpath(CATALOGUE).read_text(encoding='utf-8')
    return lint(json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject))


def lint(document):
    """Every kit names real parts and a real arrangement, or nothing loads."""
    if document.get('schema') != 'fantasy-world-generator.key-location-exteriors':
        raise ValueError('not a key-location exteriors catalogue')
    if type(document.get('revision')) is not int or document['revision'] < 1:
        raise ValueError('exteriors catalogue needs a positive integer revision')
    parts = {}
    for part in document['parts']:
        if part['id'] in parts:
            raise ValueError(f'duplicate part {part["id"]!r}')
        if part.get('kind') not in PART_KINDS:
            raise ValueError(f'part {part["id"]!r} has unknown kind {part.get("kind")!r}')
        shape = part.get('shaping')
        if shape is not None:
            if shape.get('shape') not in SHAPES:
                raise ValueError(f'part {part["id"]!r} has unknown shape {shape.get("shape")!r}')
            if not isinstance(shape.get('radius_m') or shape.get('length_m'), (int, float)):
                raise ValueError(f'part {part["id"]!r} shapes the ground over no extent')
            # `level` flattens toward the centre height, so height_m 0 is meaningful there and
            # means "flat, no offset". Every other shape moving the ground by nothing is a
            # no-op wearing a shaping spec.
            if shape['shape'] != 'level' and not any(
                    isinstance(shape.get(k), (int, float)) and shape[k] != 0
                    for k in ('height_m', 'depth_m')):
                raise ValueError(f'part {part["id"]!r} shapes the ground by nothing')
        for box, fields in (('plot_m', ('width', 'depth')), ('dimensions_m', ('width', 'depth', 'height'))):
            for field in fields:
                if not isinstance(part.get(box, {}).get(field), (int, float)) or part[box][field] <= 0:
                    raise ValueError(f'part {part["id"]!r} needs a positive {box}.{field}')
        parts[part['id']] = part
    for group in ('family_kits', 'archetype_kits'):
        for key, kit in document[group].items():
            if kit['arrangement'] not in ARRANGEMENTS:
                raise ValueError(f'kit {key!r} has unknown arrangement {kit["arrangement"]!r}')
            if not kit.get('parts'):
                raise ValueError(f'kit {key!r} places nothing')
            for entry in kit['parts']:
                if entry['part'] not in parts:
                    raise ValueError(f'kit {key!r} names unknown part {entry["part"]!r}')
                if entry.get('arrangement', kit['arrangement']) not in ARRANGEMENTS:
                    raise ValueError(f'kit {key!r} has unknown arrangement {entry["arrangement"]!r}')
                low, high = entry.get('count', [1, 1])
                if not (0 <= low <= high):
                    raise ValueError(f'kit {key!r} has a malformed count {entry.get("count")}')
    return document


def kit_for(archetype_id, family, document):
    """The kit an archetype uses: its own, or its family's. Never nothing."""
    kit = document['archetype_kits'].get(archetype_id) or document['family_kits'].get(family)
    if kit is None:
        raise ValueError(f'no exterior kit for {archetype_id!r} and no family kit for {family!r}')
    return kit


RUIN_STATES = {'ruined': 4, 'buried': 3, 'drowned': 2, 'abandoned': 2, 'reclaimed': 3, 'corrupted': 1}
RUBBLE = 'keyloc.part.rubble_pile'
OVERGROWN = 'keyloc.part.overgrown_mound'


def _weathering(site, kit, document):
    """A kit plus what time did to it.

    The same fort is a different place ruined and held, and the difference a consumer sees
    should not be only a `state` string next to identical geometry. Rubble scales with how far
    gone the site is, and ground that nature took back gets mounded over instead.
    """
    extra = RUIN_STATES.get(site['state'], 0)
    if not extra:
        return kit
    part = OVERGROWN if site['state'] == 'reclaimed' else RUBBLE
    return dict(kit, parts=list(kit['parts']) + [
        {'part': part, 'count': [max(1, extra - 2), extra], 'arrangement': 'scatter', 'kind': 'terrain'}])


def generate(world, block, document=None):
    """Exterior plans for every location in a finished `key_locations` block."""
    document = document or load()
    parts = {p['id']: p for p in document['parts']}
    layers = world.get('layers', {})
    n, radius = readers.size(world), readers.radius_m(world)
    seed = readers.world_seed(world)
    plans = []
    for site in block.get('sites', []):
        kit = _weathering(site, kit_for(site['kind'], site['family'], document), document)
        draw = rng(seed, 'keyloc-exterior-' + site['id'])
        plans.append(exterior.plan(site, kit, parts, layers, n, radius, draw))
    total = sum(p['stats']['plots'] for p in plans)
    return {'version': VERSION, 'status': 'ok', 'catalogue_revision': document['revision'],
            'part_count': len(parts), 'kit_count': len(document['archetype_kits']) + len(document['family_kits']),
            'unit': 'metres',
            'coordinates': 'local to each location; place the frame at the location direction and height',
            'summary': {'plans': len(plans), 'plots': total,
                        'plots_per_plan': round(total / len(plans), 2) if plans else 0},
            'plans': plans, 'method': METHOD, 'limits': LIMITS}
