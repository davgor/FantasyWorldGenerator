"""Ground shaping: the deformations a location makes in the terrain it stands on.

A barrow is a mound. A quarry is a hole. A crater has a rim with a bowl inside it, and a dyke
is a bank running across the ground. Until now every one of those was a *part standing on flat
ground* — a mound-shaped mesh sitting on terrain that did not rise, which reads wrong from any
angle that shows the horizon.

Each shaping entry is emitted twice over, deliberately:

* as a **parametric primitive** — shape, centre, radius, height — so an engine with a
  high-resolution landscape can apply it at its own fidelity, which is what a game actually
  wants. A sampled grid at three metres a post cannot describe a barrow.
* as a **sampled surface grid** in the same shape `castle_plans` already emits, so a consumer
  that only knows how to read that gets something correct without understanding primitives.

The grid is the derived form; the primitives are the truth. Where they disagree, the
primitives are right and the grid is merely coarse.

Pure: no filesystem, no network, no engine, no generator imports.
"""
import math

SHAPES = ('mound', 'cut', 'rim', 'platform', 'bank', 'trench', 'level')
EDGE = .22


def _smoothstep(t):
    t = max(0., min(1., t))
    return t * t * (3 - 2 * t)


def _radial(distance, radius):
    """1 at the centre, 0 at the radius, smooth in between."""
    if radius <= 0:
        return 0.
    return _smoothstep(1. - distance / radius)


def _along(x, z, cx, cz, degrees, length, width):
    """Distance from the axis of a linear feature, and whether we are within its run."""
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    dx, dz = x - cx, z - cz
    along = dx * c + dz * s
    across = -dx * s + dz * c
    if abs(along) > length / 2:
        return None
    return abs(across) / (width / 2) if width > 0 else 1.


def delta(entry, x, z):
    """Height change one shaping entry makes at a local point, in metres."""
    shape = entry['shape']
    cx, cz = entry.get('x_m', 0.), entry.get('z_m', 0.)
    distance = math.hypot(x - cx, z - cz)
    radius = float(entry.get('radius_m', 1.))

    if shape == 'mound':
        return float(entry.get('height_m', 0.)) * _radial(distance, radius)
    if shape == 'cut':
        return -float(entry.get('depth_m', 0.)) * _radial(distance, radius)
    if shape == 'platform':
        if distance >= radius:
            return 0.
        inner = radius * (1 - EDGE)
        held = 1. if distance <= inner else _smoothstep((radius - distance) / (radius - inner))
        return float(entry.get('height_m', 0.)) * held
    if shape == 'rim':
        # A raised ring with a bowl inside it: the crater profile, and the reason a rim is not
        # just a mound with a hole punched in it.
        height = float(entry.get('height_m', 0.))
        bowl = float(entry.get('depth_m', 0.))
        if distance > radius * 1.4:
            return 0.
        ring = math.exp(-((distance - radius) / max(1e-6, radius * .28)) ** 2)
        inside = _radial(distance, radius * .82) if bowl else 0.
        return height * ring - bowl * inside
    if shape in ('bank', 'trench'):
        across = _along(x, z, cx, cz, entry.get('rotation_degrees', 0.),
                        float(entry.get('length_m', radius * 2)), float(entry.get('width_m', radius)))
        if across is None or across > 1:
            return 0.
        profile = _smoothstep(1. - across)
        return profile * (float(entry.get('height_m', 0.)) if shape == 'bank'
                          else -float(entry.get('depth_m', 0.)))
    if shape == 'level':
        return 0.  # handled against the base surface, not as an additive delta
    raise ValueError(f'unknown shape {shape!r}; expected one of {SHAPES}')


def levelling(entries, x, z, base, centre_base):
    """Flattening pulls ground toward the height at the feature's centre.

    A courtyard, a hearth or a foundation line sits on ground somebody made flat. That cannot
    be expressed as a delta independent of the terrain, so it is applied against the base.
    """
    height = base
    for entry in entries:
        if entry['shape'] != 'level':
            continue
        cx, cz = entry.get('x_m', 0.), entry.get('z_m', 0.)
        strength = _radial(math.hypot(x - cx, z - cz), float(entry.get('radius_m', 1.)))
        target = centre_base + float(entry.get('height_m', 0.))
        height += (target - height) * strength
    return height


def shaped_height(entries, x, z, base, centre_base):
    """Final ground height at a local point: levelled first, then every additive shape."""
    height = levelling(entries, x, z, base, centre_base)
    for entry in entries:
        if entry['shape'] != 'level':
            height += delta(entry, x, z)
    return height


def surface(entries, half_m, size, sample_base, centre_base):
    """A sampled height grid over the plan's bounds, in the castle-plan surface shape.

    ``sample_base(x, z)`` returns the unshaped terrain height at a local offset. The grid is
    the coarse, directly-usable form of what the primitives describe exactly.
    """
    step = 2 * half_m / (size - 1)
    heights = []
    for j in range(size):
        row = []
        z = -half_m + j * step
        for i in range(size):
            x = -half_m + i * step
            row.append(round(shaped_height(entries, x, z, sample_base(x, z), centre_base), 4))
        heights.append(row)
    return {'size': size, 'step_m': round(step, 4), 'heights_m': heights}


def relief(entries, half_m, sample_base, centre_base):
    """How much the shaping actually moves the ground, for a consumer deciding whether to care."""
    if not entries:
        return {'raised_m': 0., 'lowered_m': 0.}
    highest = lowest = 0.
    step = half_m / 6
    j = -half_m
    while j <= half_m:
        i = -half_m
        while i <= half_m:
            base = sample_base(i, j)
            change = shaped_height(entries, i, j, base, centre_base) - base
            highest, lowest = max(highest, change), min(lowest, change)
            i += step
        j += step
    return {'raised_m': round(highest, 3), 'lowered_m': round(lowest, 3)}
