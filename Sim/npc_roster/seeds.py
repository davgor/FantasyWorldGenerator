"""Seed derivation, re-exported from :mod:`world_geometry.seeds`, so a roster is a pure
function of the world seed.

This package reads only the finished world JSON and never the generator's modules, so a saved
`world.json` serves it as well as a live result. That is unchanged: ``world_geometry`` is pure
arithmetic over ``math``, ``hashlib`` and ``random`` and imports no generator.

What has changed is that the derivation is no longer a copy. It used to be copied here and
pinned by a per-package test; there is now one implementation and one pin, in
``Sim/tests/test_world_geometry.py``.
"""
from world_geometry.seeds import child_seed, rng

__all__ = ['child_seed', 'rng']
