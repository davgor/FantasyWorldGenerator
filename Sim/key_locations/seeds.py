"""Seed derivation, re-exported from :mod:`world_geometry.seeds`.

This package reads only the finished world JSON and never the generator's modules, and still
does: ``world_geometry`` is pure arithmetic over ``math``, ``hashlib`` and ``random`` and
imports no generator.

The derivation used to be copied here and pinned by this package's own test. There is now one
implementation and one pin, in ``Sim/tests/test_world_geometry.py``.
"""
from world_geometry.seeds import child_seed, rng

__all__ = ['child_seed', 'rng']
