"""Pure world-shape arithmetic: a circumference and a relief budget in, config overrides out.

No filesystem, no engine, no Config import -- floats in, floats out, so the caller
builds whatever config object it likes and the native port can mirror this directly.

The design follows the note already in `Core/genesis.cpp:153-155`: the scale stays at
the recipe's constant so a metre of relief means the same thing at every world width,
and the *design radius* carries the width instead. What is added here is the piece
`world_shape_overrides` omits -- `wavelength` -- without which surface detail silently
vanishes as the world grows.
"""
import math

# Recipe-3 authoring ratio, amplitude relative to tectonic relief (1100/800). The same
# ratio Core/genesis.cpp:160 uses when it derives amplitude from a relief request.
AMPLITUDE_RATIO = 1100./800.

# `Config.__post_init__` bounds the active relief budget at 90% of the design radius
# (terrain_lab.py:148-151): 5*tectonic_relief + 2*amplitude < .9*globe_radius.
RELIEF_BUDGET_FACTOR = 5.
DETAIL_BUDGET_FACTOR = 2.
BUDGET_HEADROOM = .9


# Physical size of the reference world: design radius 10000 at the recipe world_scale.
REFERENCE_RADIUS_M = 1774.4123532462844
REFERENCE_CIRCUMFERENCE_M = 2*math.pi*REFERENCE_RADIUS_M


def reach_scale(circumference_m):
    """Factor for distances authored against the reference world.

    Reaches, spacings and influence radii are authored as absolute metres that only
    make sense at the 11.15 km reference world. They have to grow with the world or
    they stop spanning anything: a 1000 m support reach is a sixth of one cell on a
    200 km world at raster 33, so no node is ever near enough to farm and hamlets --
    and the fortresses that follow their roads -- both vanish entirely.
    """
    return circumference_m/REFERENCE_CIRCUMFERENCE_M


def design_radius(circumference_m, world_scale):
    """Design-space radius that yields a physical circumference. Core/genesis.cpp:156."""
    return circumference_m/(2*math.pi*world_scale)


def physical_radius(circumference_m):
    """The radius a player actually walks on."""
    return circumference_m/(2*math.pi)


def tectonic_relief_for(relief_m, world_scale):
    """Design-space relief unit for a physical relief budget. Core/genesis.cpp:158."""
    return relief_m/world_scale


def amplitude_for(tectonic_relief, amplitude_ratio=AMPLITUDE_RATIO):
    """Surface-noise amplitude that keeps the recipe's relief-to-detail balance."""
    return tectonic_relief*amplitude_ratio


def detail_wavelength(radius, plate_count):
    """Surface-noise wavelength that holds detail at a constant fraction of the world.

    The formula already in `terrain_recipes.seed_config` (terrain_recipes.py:23) but
    never reached on the recipe-3 path. Tying wavelength to the radius is what makes
    the resolved octave count scale-invariant: leave it at a fixed 4300 m and a world
    an order of magnitude wider resolves no surface noise at all.
    """
    return radius*1.6/math.sqrt(plate_count)


def belt_width_for(plate_count):
    """Boundary belt width that keeps belts a constant share of a plate's span."""
    return .28/math.sqrt(plate_count)


def max_relief_m(circumference_m, amplitude_ratio=AMPLITUDE_RATIO):
    """Largest physical relief the config guard admits for a circumference.

    Derived by inverting terrain_lab.py:148-151. `world_scale` cancels out entirely,
    so this is purely a relief-to-circumference statement: relief cannot approach the
    planet's own size. At the default amplitude ratio the ceiling is about 1.85% of
    circumference -- roughly 206 m on today's 11.15 km world, which is why relief
    cannot be raised before the world is made bigger.
    """
    divisor = 2*math.pi*(RELIEF_BUDGET_FACTOR+DETAIL_BUDGET_FACTOR*amplitude_ratio)
    return BUDGET_HEADROOM*circumference_m/divisor


def resolved_octaves(radius, size, wavelength, octaves):
    """Surface-noise octaves surviving the Nyquist filter in `generate_tectonics`.

    Mirrors terrain_tectonics.py:177-178 exactly. `radius` is the DESIGN radius,
    `cfg.globe_radius`, not the physical radius in `effective_config` -- the filter
    runs before `apply_world_scale` and the two differ by a factor of 1/world_scale.
    Reading the physical radius here overstates the surviving octaves badly.
    """
    step = 2*math.pi*radius/(size-1)
    kept = sum(1 for k in range(octaves) if wavelength/2**k >= 2*step)
    return {'resolved_octaves': kept, 'requested_octaves': octaves,
            'resolved_octave_fraction': kept/octaves if octaves else 0.,
            'cell_step_m': step}


def shape_overrides(circumference_m, relief_m, orogeny, plate_count, world_scale,
                    amplitude_ratio=AMPLITUDE_RATIO, scale_belt_width=False):
    """Config overrides for a world of a given width and relief budget.

    The `world_shape_overrides` set from Core/genesis.cpp:148-167 plus `wavelength`.
    Raises when the relief budget cannot be satisfied, rather than letting
    `Config.__post_init__` refuse a config the caller cannot easily diagnose.
    """
    if not (math.isfinite(circumference_m) and circumference_m > 0):
        raise ValueError('circumference must be a positive number of metres')
    if not (math.isfinite(relief_m) and relief_m > 0):
        raise ValueError('relief must be a positive number of metres')
    if plate_count < 2:
        raise ValueError('plate_count must be at least 2')
    ceiling = max_relief_m(circumference_m, amplitude_ratio)
    if relief_m >= ceiling:
        raise ValueError(f'relief of {relief_m:g} m needs a circumference above '
                         f'{circumference_m*relief_m/ceiling/1000:.0f} km; '
                         f'{circumference_m/1000:g} km admits at most {ceiling:.0f} m')
    radius = design_radius(circumference_m, world_scale)
    relief = tectonic_relief_for(relief_m, world_scale)
    overrides = {'globe_radius': radius, 'world_scale': world_scale,
                 'tectonic_relief': relief, 'amplitude': amplitude_for(relief, amplitude_ratio),
                 'wavelength': detail_wavelength(radius, plate_count),
                 'plate_count': plate_count, 'orogeny': orogeny}
    if scale_belt_width:
        overrides['belt_width'] = belt_width_for(plate_count)
    return overrides
