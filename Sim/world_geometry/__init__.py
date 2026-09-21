"""Pure sphere-grid arithmetic shared by every package that reads a finished world.

A reader package reads only a world document and never imports the generator, so that a
saved ``world.json`` serves exactly as a live result does. That rule was satisfied for years
by copying the primitives into each reader and pinning each copy by its own test — four
implementations that agreed because four tests said so, rather than because there was one of
them.

The rule never required the copies. It required that no reader import the generator, and a
package holding nothing but ``math``, ``hashlib`` and ``random`` satisfies that as well as a
copy does. So the primitives live here once: the node layout, the direction of a cell, a
cell's area, great-circle distance, walking a bearing, spherical interpolation, and the
child-seed derivation.

The generator remains the oracle. Nothing here is imported by ``Sim/icarus_sim``, and one
test — ``Sim/tests/test_world_geometry.py`` — holds these functions to the generator's own
arithmetic at five raster sizes. This package is a consumer of that arithmetic, never its
definition.

The functions are the generator's expressions verbatim, in the generator's order. Float
addition is not associative; a tidier sum here is a different world.
"""
from .grid import (cell, cell_area_m2, cell_of_direction, direction, great_circle_m,
                   node_count, node_index, normalise, offset, slerp)
from .seeds import child_seed, rng

__all__ = ['cell', 'cell_area_m2', 'cell_of_direction', 'child_seed', 'direction',
           'great_circle_m', 'node_count', 'node_index', 'normalise', 'offset', 'rng',
           'slerp']
