"""Kernel numeric/serialization v1, intentionally separate from world generation."""
import hashlib
import json
import re

from .kernel_contract import KernelError, MAX_SAFE, integer, version as check_version

MAX_BYTES = 1024*1024
MAX_DEPTH = 32
MAX_NODES = 16384


def _text(value):
    if type(value) is not str:
        raise KernelError('INVALID_INPUT', 'JSON object keys must be strings')
    try:
        encoded = value.encode('utf-8')
    except UnicodeEncodeError:
        raise KernelError('INVALID_INPUT', 'unpaired Unicode surrogate') from None
    if len(encoded) > 4096:
        raise KernelError('INVALID_INPUT', 'string exceeds 4096 UTF-8 bytes')


def _validate(value, depth=0, count=None):
    if count is None:
        count = [0]
    count[0] += 1
    if depth > MAX_DEPTH or count[0] > MAX_NODES:
        raise KernelError('INVALID_INPUT', 'JSON depth/node limit exceeded')
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        integer(value, 'JSON integer', minimum=-MAX_SAFE)
    elif type(value) is str:
        _text(value)
    elif type(value) is list:
        for item in value:
            _validate(item, depth+1, count)
    elif type(value) is dict:
        for key, item in value.items():
            _text(key)
            _validate(key, depth+1, count)
            _validate(item, depth+1, count)
    else:
        raise KernelError('INVALID_INPUT', 'kernel JSON excludes floats and non-JSON types')


def canonical_bytes(value, *, version=1):
    check_version(version)
    _validate(value)
    result = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    if len(result) > MAX_BYTES:
        raise KernelError('INVALID_INPUT', 'JSON byte limit exceeded')
    return result


def canonical_loads(raw, *, version=1):
    check_version(version)
    if type(raw) is not bytes or len(raw) > MAX_BYTES or raw.startswith(b'\xef\xbb\xbf'):
        raise KernelError('INVALID_INPUT', 'expected UTF-8 bytes without BOM within byte limit')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise KernelError('INVALID_INPUT', 'duplicate JSON key')
            result[key] = value
        return result
    def parse_integer(token):
        if len(token.lstrip('-')) > 16:
            raise KernelError('INVALID_INPUT', 'integer token exceeds safe domain')
        return integer(int(token), 'JSON integer', minimum=-MAX_SAFE)
    def no_float(token):
        raise KernelError('INVALID_INPUT', 'floating-point JSON is not a kernel value')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_int=parse_integer,
                            parse_float=no_float, parse_constant=no_float)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise KernelError('INVALID_INPUT', 'invalid JSON encoding or structure') from error
    canonical_bytes(result)
    return result


def digest(value, *, version=1):
    return hashlib.sha256(canonical_bytes(value, version=version)).hexdigest()


def _word(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{16}', value) is None:
        raise KernelError('INVALID_INPUT', 'word/seed requires 16 lowercase hexadecimal digits')


def random_word(seed, stream, index, *, version=1):
    check_version(version)
    _word(seed)
    if type(stream) is not str or re.fullmatch('[a-z][a-z0-9._-]{0,63}', stream) is None:
        raise KernelError('INVALID_INPUT', 'invalid stream domain')
    integer(index, 'stream index')
    name = stream.encode('ascii')
    # Frozen kernel v1 domain label; not the product name. Do not rename.
    frame = b'MathLab/stream/v1\0' + bytes.fromhex(seed) + bytes([len(name)]) + name + index.to_bytes(8, 'big')
    return hashlib.sha256(frame).hexdigest()[:16]


def unit_float(word, *, version=1):
    check_version(version)
    _word(word)
    return (int(word, 16) >> 11) / (2**53)
