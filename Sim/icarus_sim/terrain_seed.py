"""Versioned seed adapters; prompt hashing is not semantic terrain control."""
import hashlib
import unicodedata


def manual_seed(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError('seed must be an integer from 0 to 4294967295')
    return {'seed':value, 'method':'manual-u32-v1'}


def prompt_seed(prompt):
    if not isinstance(prompt,str) or not 1 <= len(prompt) <= 4096:
        raise ValueError('prompt must contain 1..4096 characters')
    normalized = unicodedata.normalize('NFC',prompt.replace('\r\n','\n').replace('\r','\n')).strip()
    if not normalized:
        raise ValueError('prompt must not be blank')
    digest = hashlib.sha256(('icarus-terrain-prompt-v1\0'+normalized).encode('utf-8')).digest()
    return {'seed':int.from_bytes(digest[:4],'big'), 'method':'sha256-nfc-u32-v1',
            'digest':digest.hex()}
