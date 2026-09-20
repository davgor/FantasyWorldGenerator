"""Seed derivation, byte-identical to ``icarus_sim.terrain_tectonics.child_seed``.

Copied rather than imported so this package reads only the finished world JSON and never
the generator's modules. A test pins the two implementations against each other, so a
change on either side is caught instead of silently forking the replay contract.
"""
import hashlib
import random


def child_seed(master, domain, variation=0):
    return int.from_bytes(hashlib.sha256(f'tectonics-v1:{master}:{domain}:{variation}'.encode()).digest()[:4], 'big')


def rng(master, domain, variation=0):
    return random.Random(child_seed(master, domain, variation))
