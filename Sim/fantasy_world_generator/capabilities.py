"""Explicit producer capabilities, independent of the package release number."""
import json
from importlib.resources import files

CONTROLS_VERSION = 1


def capabilities_document(version: int = 1) -> dict:
    """Return a caller-owned capability descriptor for the requested version."""
    if type(version) is not int or version != 1:
        raise ValueError('unsupported capability_version')
    return json.loads(files(__package__).joinpath('capabilities.json').read_text(encoding='utf-8'))


def require_capabilities(request: dict) -> dict:
    """Reject unsupported exact ID/version requirements; no world is validated."""
    if not isinstance(request, dict) or set(request) != {'capability_version', 'requires'}:
        raise ValueError('capability request requires exactly capability_version and requires')
    document = capabilities_document(request['capability_version'])
    required = request['requires']
    if not isinstance(required, dict):
        raise ValueError('requires must be an object of capability IDs and integer versions')
    for name, version in required.items():
        if not isinstance(name, str) or name not in document['supported']:
            raise ValueError('unknown or unavailable capability')
        if type(version) is not int or version not in document['supported'][name]:
            raise ValueError('unsupported capability version: ' + name)
    return document


def controls_document(version: int = CONTROLS_VERSION) -> dict:
    """Return the whole published control catalogue, without generating a world.

    The catalogue used to be reachable only inside a generated world, at
    `recipe.parameters`, so learning what knobs existed cost a full generation.
    """
    if type(version) is not int or version != CONTROLS_VERSION:
        raise ValueError('unsupported controls version')
    return json.loads(files(__package__).joinpath('world_controls.json').read_text(encoding='utf-8'))


def describe_controls(version: int = CONTROLS_VERSION, *, group=None, names=None,
                      query=None, include_pinned: bool = False) -> dict:
    """Return the controls a caller asked about, rather than all two hundred of them.

    The whole catalogue is about 33 kB, roughly nine thousand tokens, and the packaged
    orchestrator would otherwise pay that on every request for a table it needs once. The
    filters are the point of this function, not a convenience on top of it.

    `include_pinned` is false by default. A pinned control has `min == max` and refuses
    every value; an inert one is read by nothing on this recipe. Both are returned only
    when asked for, so the default answer is the set a caller can actually use.
    """
    document = controls_document(version)
    controls = document['controls']

    if names is not None:
        if isinstance(names, str):
            names = [names]
        unknown = sorted(set(names) - set(controls))
        if unknown:
            raise ValueError('unknown control: ' + ', '.join(unknown))
        controls = {k: v for k, v in controls.items() if k in set(names)}
    if group is not None:
        wanted = group.casefold()
        controls = {k: v for k, v in controls.items()
                    if str(v.get('group', '')).casefold() == wanted}
    if query is not None:
        needle = query.casefold()
        controls = {k: v for k, v in controls.items()
                    if needle in k.casefold() or needle in str(v.get('description', '')).casefold()}
    if not include_pinned:
        controls = {k: v for k, v in controls.items() if v.get('status') == 'open'}

    return {'schema': document['schema'], 'version': document['version'],
            'recipe_version': document['recipe_version'],
            'groups': sorted({str(v.get('group', '')) for v in document['controls'].values()}),
            'total': len(document['controls']), 'returned': len(controls),
            'controls': dict(sorted(controls.items()))}
