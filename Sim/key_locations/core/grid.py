"""Sphere-grid geometry, re-exported from :mod:`world_geometry.grid`.

Unlike a consumer that only reads *placed* records, this package has to *choose* ground, and
choosing means addressing cells the world never occupied — which requires the generator's
exact node layout, not just the ``node``/``x``/``z`` stamped on existing records. That layout
used to be copied into this file and pinned against the generator by this package's own test.

It is now shared. ``world_geometry`` holds one implementation of each primitive, imports no
generator and touches no filesystem, so the isolation this package asserts is unaffected, and
``Sim/tests/test_world_geometry.py`` is the single pin holding it to the generator at five
raster sizes.

The import path is unchanged: ``from .grid import ...`` still works everywhere in this
package, and ``key_locations.core.grid.direction`` is now the same function object as
``world_geometry.grid.direction`` rather than an equal one.
"""
from world_geometry.grid import (cell, cell_area_m2, cell_of_direction, direction,
                                 great_circle_m, node_count, node_index, normalise, offset,
                                 slerp)

__all__ = ['cell', 'cell_area_m2', 'cell_of_direction', 'direction', 'great_circle_m',
           'node_count', 'node_index', 'normalise', 'offset', 'slerp']
