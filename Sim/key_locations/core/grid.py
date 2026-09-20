"""Sphere-grid geometry, replicated from the generator's own node layout.

The generator lays a world out as ``sphere_grid(n, radius)``: one node at each pole and a
row-major body in between, with the seam column dropped because it duplicates column zero.

    points = [(0, 0)] + [(x, z) for z in 1..n-2 for x in 0..n-2] + [(0, n-1)]

Every exported record carries ``node``, ``x``, ``z`` and ``direction``, so a consumer that
only ever reads placed records needs none of this. A generator that must *choose* ground has
to address cells the world never occupied, which means reproducing the indexing exactly.
It is pure integer and trigonometric arithmetic, copied for the same reason
:mod:`key_locations.seeds` is copied, and pinned against the originals by test.

No filesystem, no network, no engine, and nothing here reads the generator's modules.
"""
import math


def node_count(n):
    return 2 + (n - 2) * (n - 1)


def node_index(x, z, n):
    """The node id the generator gives cell ``(x, z)``; poles collapse to one node each."""
    if z <= 0:
        return 0
    if z >= n - 1:
        return node_count(n) - 1
    return 1 + (z - 1) * (n - 1) + (x % (n - 1))


def cell(node, n):
    """The ``(x, z)`` a node id addresses — the inverse of :func:`node_index`."""
    if node <= 0:
        return 0, 0
    if node >= node_count(n) - 1:
        return 0, n - 1
    offset = node - 1
    return offset % (n - 1), offset // (n - 1) + 1


def direction(x, z, n):
    """Unit vector for a cell, matching ``icarus_sim.terrain_globe.direction`` exactly."""
    if z == 0:
        return (0., 1., 0.)
    if z == n - 1:
        return (0., -1., 0.)
    lon = 2 * math.pi * (x % (n - 1)) / (n - 1) - math.pi
    lat = math.pi / 2 - math.pi * z / (n - 1)
    return (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))


def cell_area_m2(z, n, radius):
    """Surface area of one cell's latitude band slice, as ``sphere_grid`` computes it."""
    step = math.pi / (n - 1)
    lat = math.pi / 2 - z * step
    band = radius ** 2 * 2 * step * (math.sin(min(math.pi / 2, lat + step / 2))
                                     - math.sin(max(-math.pi / 2, lat - step / 2)))
    return band * ((n - 1) if z in (0, n - 1) else 1)


def cell_of_direction(vector, n):
    """The nearest cell to an arbitrary direction — the inverse of :func:`direction`.

    Chain markers stand between cells, not on them: a waystone every two kilometres on a
    world whose cells are six kilometres apart cannot be node-snapped without collapsing
    three of them onto one point. They carry a real direction and use this only to read the
    layers underneath, so the rounding here costs a lookup's accuracy and never a position.
    """
    x_component, y_component, z_component = vector
    latitude = math.asin(max(-1., min(1., y_component)))
    longitude = math.atan2(z_component, x_component)
    z = int(round((math.pi / 2 - latitude) * (n - 1) / math.pi))
    x = int(round((longitude + math.pi) * (n - 1) / (2 * math.pi)))
    return max(0, min(n - 1, x)) % (n - 1), max(0, min(n - 1, z))


def great_circle_m(a, b, radius):
    """Surface distance between two unit directions, clamped against float overshoot."""
    dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    return radius * math.acos(max(-1., min(1., dot)))


def offset(origin, bearing, distance_m, radius):
    """Walk ``distance_m`` from ``origin`` along a great circle on the given bearing.

    A siege camp sits about a kilometre and a half from the wall it besieged. On a raster
    whose cells are twelve kilometres apart there is no *cell* that satisfies that, so a
    cluster member snapped to a node would be placed ten times too far away or not at all.
    Like chain members, they stand between cells and carry a real direction.

    ``bearing`` is radians clockwise from local north; near a pole the basis degenerates and
    any consistent direction there is as good as another.
    """
    up = (0., 1., 0.)
    east = normalise((up[1] * origin[2] - up[2] * origin[1],
                      up[2] * origin[0] - up[0] * origin[2],
                      up[0] * origin[1] - up[1] * origin[0]))
    north = normalise((origin[1] * east[2] - origin[2] * east[1],
                       origin[2] * east[0] - origin[0] * east[2],
                       origin[0] * east[1] - origin[1] * east[0]))
    angle = distance_m / radius
    across = math.sin(bearing)
    along = math.cos(bearing)
    return normalise(tuple(origin[i] * math.cos(angle)
                           + (east[i] * across + north[i] * along) * math.sin(angle) for i in range(3)))


def normalise(vector):
    length = math.sqrt(sum(component * component for component in vector))
    return tuple(component / length for component in vector) if length else (0., 1., 0.)


def slerp(a, b, t):
    """Great-circle interpolation, used to walk a road between its nodes.

    Falls back to the nearer endpoint when the two directions are effectively identical,
    where the sine denominator would otherwise divide by zero.
    """
    dot = max(-1., min(1., a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    angle = math.acos(dot)
    if angle < 1e-9:
        return tuple(a)
    sine = math.sin(angle)
    first, second = math.sin((1 - t) * angle) / sine, math.sin(t * angle) / sine
    return normalise(tuple(first * a[i] + second * b[i] for i in range(3)))
