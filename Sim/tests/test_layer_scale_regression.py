"""Guard against a published layer quietly becoming a constant at the live world scale.

The defect this file exists for (user ruling 2.0): three published layers -- island_habitat,
freshwater_distance and flood_risk -- carried no information at the 200 km default world,
because each was gated by an absolute-metre constant authored for the 11.15 km reference
world. `island_habitat` was identically 0 at the DEFAULT size-17 raster, where the smallest
sphere-grid cell is 15.217 km2 and no component of any seed can reach the `min(3e6, ...)`
floor; above size 17 the floor is occasionally reachable by a one-cell polar component
(seed 40 reads 1 island cell at size 33 and 6 at size 65) and the layer was all but empty
rather than provably constant. Separately, every land cell was a river, so
`freshwater_distance` was identically 0 on land and `flood_risk` identically 1.0.

These are SHAPE assertions, deliberately. The class of defect is "a layer became a
constant", and a shape assertion catches the next absolute-metre constant too, where a
value assertion would only re-break on the next retune. Specific counts are seed- and
raster-dependent and are recorded in board/backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md.

Phase 12 is the cheapest phase that publishes all four layers (0.9 s at size 17, 4.7 s at
33; phase 16 costs about 97 s and adds nothing this file checks).
"""
import unittest

from icarus_sim.terrain_erosion import sphere_grid
from icarus_sim.terrain_world import generate_request

# A land-river fraction outside this band is the saturation/emptiness defect returning.
# Chosen against measurement, not taste. The bound must sit ABOVE every correct world and
# BELOW every saturated one, and those two populations are close together, so 0.95 is a
# narrow ceiling and is deliberately left narrow. Measured, all at 200 km, phase 12:
#
#   saturated, pre-fix          1.000 at size 17, 0.996 at size 33
#   correct, post-fix           seeds 40-79 swept at size 17: worst 0.9118 (seed 40),
#                               then 0.8929 (seed 47), then 0.8750 (seed 43 -- one of
#                               this file's own four cases). Seed 42 sits at 0.6809.
#   correct, 11.15 km reference 0.897 at size 17 -- a world that SHIPPED, so any ceiling
#                               at or below 0.90 would fail a known-good world.
#
# So the legal window is (0.9118, 0.9963] and 0.95 is within 0.005 of its midpoint
# (0.9541): 0.038 of headroom above the worst correct world, 0.046 of margin below the
# tightest saturated one. It is NOT widened, because widening spends the half of the
# margin that does the work -- 0.98 would pass a world that is 98% river, which is the
# defect. If a retune ever pushes a correct world past 0.9118, re-run that sweep before
# moving this number; the right answer may be to retune the threshold instead.
MAX_LAND_RIVER_FRACTION = .95
MIN_LAND_RIVER_FRACTION = .02

CASES = ((42, 17), (42, 33), (43, 17), (43, 33))


_CACHE = {}


def world(seed, size, phase=12):
    # Memoised: four worlds shared across every test here, rather than one generation
    # per assertion. Generation is deterministic, so a cached world is the same world.
    key = (seed, size, phase)
    if key not in _CACHE:
        _CACHE[key] = _build(seed, size, phase)
    return _CACHE[key]


def _build(seed, size, phase):
    result = generate_request({'recipe_version': 3, 'seed': seed,
                               'overrides': {'size': size, 'phase': phase}})
    layers = result['layers']
    n = len(layers['water_type'])
    points, _, _ = sphere_grid(n, result['effective_config']['globe_radius'])
    water_type = layers['water_type']
    land = [(x, z) for (x, z) in points if water_type[z][x] <= 0]
    water = [(x, z) for (x, z) in points if water_type[z][x] > 0]
    return result, layers, land, water


def values(layers, key, cells):
    return [layers[key][z][x] for (x, z) in cells]


class LandRiverFractionTests(unittest.TestCase):
    """rain_river must be a proper subset of land: neither every cell nor none."""

    def test_river_network_is_neither_saturated_nor_empty(self):
        for seed, size in CASES:
            with self.subTest(seed=seed, size=size):
                _, layers, land, _ = world(seed, size)
                fraction = sum(1 for v in values(layers, 'rain_river', land) if v)/len(land)
                self.assertLess(fraction, MAX_LAND_RIVER_FRACTION,
                                f'rain_river saturated at seed {seed} size {size}: '
                                f'{fraction:.3f} of land is river')
                self.assertGreater(fraction, MIN_LAND_RIVER_FRACTION,
                                   f'rain_river empty at seed {seed} size {size}')

    def test_threshold_is_scaled_off_its_reference_value(self):
        # The recipe default is the 11.15 km reference world's 0.15 km2. If this ever
        # reads 0.15 again on a 200 km world, the derivation stopped being applied.
        result = generate_request({'recipe_version': 3, 'seed': 42,
                                   'overrides': {'size': 17, 'phase': 1}})
        self.assertGreater(result['config']['river_threshold_km2'], 1.0)


class FreshwaterDistanceTests(unittest.TestCase):
    """The dijkstra needs somewhere to travel; a saturated source set leaves it nothing."""

    def test_land_carries_both_sources_and_distances(self):
        for seed, size in CASES:
            with self.subTest(seed=seed, size=size):
                _, layers, land, _ = world(seed, size)
                distances = values(layers, 'freshwater_distance', land)
                self.assertTrue(any(v == 0 for v in distances),
                                'no freshwater sources on land')
                self.assertTrue(any(v > 0 for v in distances),
                                f'freshwater_distance is identically 0 on land at seed '
                                f'{seed} size {size}: every land cell is its own source')

    def test_minus_one_means_unreachable_not_water(self):
        # -1 is terrain_settlements.py:946 substituting for math.inf: no freshwater
        # SOURCE is reachable from this cell. It is not a water sentinel, though it
        # looked like one before this fix -- when every land cell was its own source,
        # nothing on land could be infinite and -1 fell exactly on the water cells.
        # It no longer does: seed 42 size 33 has one land cell at -1, a single-cell
        # island with no river on it, correctly unreachable. So the equality
        # "-1 count == water count" that the plan proposed asserting is false on a
        # CORRECT world, and asserting it would have failed this fix rather than
        # guarding it. The real invariant is that -1 never lands on a river cell.
        for seed, size in CASES:
            with self.subTest(seed=seed, size=size):
                _, layers, land, water = world(seed, size)
                for (x, z) in land:
                    if layers['freshwater_distance'][z][x] == -1:
                        self.assertFalse(layers['rain_river'][z][x],
                                         'a river cell reads as unreachable from freshwater')
                unreachable = sum(1 for v in values(layers, 'freshwater_distance', water)
                                  if v == -1)
                self.assertGreater(unreachable, .9*len(water),
                                   'open water stopped reading as unreachable')


class FloodRiskTests(unittest.TestCase):
    """flood_risk saturates at 1.0 wherever every land cell is its own river."""

    def test_flood_risk_is_not_saturated_across_land(self):
        for seed, size in CASES:
            with self.subTest(seed=seed, size=size):
                _, layers, land, _ = world(seed, size)
                risks = values(layers, 'flood_risk', land)
                saturated = sum(1 for v in risks if v == 1.0)/len(land)
                self.assertLess(saturated, MAX_LAND_RIVER_FRACTION,
                                f'flood_risk is 1.0 on {saturated:.3f} of land at seed '
                                f'{seed} size {size}')
                self.assertTrue(any(v < 1.0 for v in risks))


class IslandHabitatTests(unittest.TestCase):
    """island_habitat was identically zero at the DEFAULT raster on the 200 km world.

    Scoped to size 17 on purpose. The old `min(3e6, ...)` floor is unreachable there --
    the smallest sphere-grid cell is 15.217 km2 -- but reachable above it, so "zero at
    every raster" was false. The four cases below cover sizes 17 and 33.
    """

    def test_island_habitat_spans_something_at_the_live_scale(self):
        # NOT a universal invariant, and deliberately not asserted as one: a world whose
        # land is a few comparable masses legitimately has no island (seed 45 at phase 6
        # yields two components of 56 and 50 cells and zero islands). These four cases
        # were measured: 1 of 47, 42 of 268, 14 of 48 and 36 of 271.
        for seed, size in CASES:
            with self.subTest(seed=seed, size=size):
                _, layers, land, _ = world(seed, size)
                islands = sum(1 for v in values(layers, 'island_habitat', land) if v)
                self.assertGreater(islands, 0,
                                   f'island_habitat is identically zero at seed {seed} '
                                   f'size {size}')
                self.assertLess(islands, len(land),
                                'every land cell reads as an island')

    def test_island_habitat_is_a_land_only_field(self):
        _, layers, _, water = world(42, 17)
        self.assertEqual(set(values(layers, 'island_habitat', water)), {0.},
                         'island_habitat is nonzero on water')


if __name__ == '__main__':
    unittest.main()
