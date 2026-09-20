"""Seed helpers, byte-for-byte the generator's ``child_seed``, so a roster is a pure function of the world seed.

Copied rather than imported for the same reason `hero_generator` and `story_web` copy it:
this package reads only the finished world JSON and never the generator's modules, so a
saved `world.json` serves it as well as a live result. A test pins the two implementations
against each other, so a change on either side is caught instead of silently forking the
replay contract.
"""
import hashlib
import random


def child_seed(master, domain, variation=0):
    return int.from_bytes(hashlib.sha256(f'tectonics-v1:{master}:{domain}:{variation}'.encode()).digest()[:4], 'big')


def rng(master, domain, variation=0):
    return random.Random(child_seed(master, domain, variation))
