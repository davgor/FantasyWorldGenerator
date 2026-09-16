"""Explicit producer capabilities, independent of the package release number."""
import json
from importlib.resources import files


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
