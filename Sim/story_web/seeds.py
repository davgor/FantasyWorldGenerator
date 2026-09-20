"""Seed helpers, byte-for-byte the generator's `child_seed`, so a web is a pure function of the world seed.

The compiler itself is deterministic without draws (weights decide, ties break on ids); the
seed is reserved for the initiative deadline jitter so heroes do not all fire on one day.
"""
import hashlib
import random


def child_seed(master, domain, variation=0):
    return int.from_bytes(hashlib.sha256(f'tectonics-v1:{master}:{domain}:{variation}'.encode()).digest()[:4], 'big')


def rng(master, domain, variation=0):
    return random.Random(child_seed(master, domain, variation))
