"""Seed derivation, re-exported from :mod:`world_geometry.seeds`.

The compiler itself is deterministic without draws (weights decide, ties break on ids); the
seed is reserved for the initiative deadline jitter so heroes do not all fire on one day.

The derivation used to be copied into this package and pinned by a test of its own. It is now
shared: ``world_geometry`` is pure arithmetic and imports no generator, so the isolation this
package asserts is unaffected, and one pin in ``Sim/tests/test_world_geometry.py`` holds the
single implementation to the generator's.
"""
from world_geometry.seeds import child_seed, rng

__all__ = ['child_seed', 'rng']
