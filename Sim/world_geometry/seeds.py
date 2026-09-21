"""Seed derivation, byte-identical to the generator's own ``child_seed``.

Every reader package derives its draws from the world's master seed through this function, so
a saved ``world.json`` replays exactly as a live result does. It is the generator's
expression verbatim, including the literal domain prefix, which is part of the replay
contract and not a detail: changing it renames every stream in every package at once.

``Sim/tests/test_world_geometry.py`` pins it against the generator.
"""
import hashlib
import random


def child_seed(master, domain, variation=0):
    return int.from_bytes(hashlib.sha256(f'tectonics-v1:{master}:{domain}:{variation}'.encode()).digest()[:4], 'big')


def rng(master, domain, variation=0):
    return random.Random(child_seed(master, domain, variation))
