"""Seed derivation, re-exported from :mod:`world_geometry.seeds`.

This package reads only the finished world JSON and never the generator's modules, and it
still does: ``world_geometry`` is pure arithmetic over ``math``, ``hashlib`` and ``random``
and imports no generator. What has changed is that the derivation is no longer copied here.
It used to be, and a per-package test pinned the copy; there is now one implementation and
one pin, in ``Sim/tests/test_world_geometry.py``.

The import path is unchanged, so every caller in this package keeps working. Nothing in this
module computes anything, so there is nothing here that can fork from the generator.
"""
from world_geometry.seeds import child_seed, rng

__all__ = ['child_seed', 'rng']
