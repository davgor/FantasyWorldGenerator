"""Every surviving natural biome is reachable, and the tombstoned two are not.

Ruling 3.0 asks that each natural biome be reachable through seed-driven generation.
This file is the machine-checkable half of that answer. It has two independent halves,
because they fail for different reasons:

  * the PURE half sweeps the real `classify`, the real cold pass and the real marsh
    predicate over their declared legal domains. It catches a biome going dead inside
    the two functions that write the layer. It imports those functions; it never
    reimplements an eligibility test it is auditing.
  * the WITNESS half generates recorded (seed, size) worlds and reads the realised
    `natural_biome` layer. It catches a biome going unrealisable in the generator even
    when the functions still admit it.

WHY THE WITNESSES RUN AT PHASE 10, not 9 and not 16.

The biome layer stops changing after stage 9. The classification pass DOES re-run later:
`age_transition` (`Sim/icarus_sim/terrain_history.py:318`) calls `rebuild_tail`, which calls
`refresh_environment`, which runs `add_terrain_labels` and `add_environment` and rewrites
`natural_biome`. That happens at stages 14 and 15. It recomputes the same answer only
because nothing between stages 10 and 15 moves height, water_type or rain_river.
MEASURED on this tree, in one process, at seeds 42 and 0 at size 17: a phase-10 world and a
phase-16 world agree cell for cell across natural_biome, biome, temperature, moisture, slope,
height and water_type -- 0 differing cells in all seven layers, at 0.36 s against 77 s.
FALSIFICATION: if a future change writes height, water_type or rain_river after stage 9,
that equality dies silently and this table must move to phase 16 (70-120 s per world).

Phase 10 rather than 9 because phase 10 is the first stage that runs `add_biome_variants`
(`Sim/icarus_sim/terrain_history.py:20`), whose bare `NATURAL_BIOMES[...]` index raises
KeyError on a natural_biome id that is not in the registry. Running the witnesses at 10
therefore also exercises the tombstone, at a measured cost of about 0.1 s per world.

A biome that these tests report as unreachable is a finding to re-measure and to record on
the board. It is never a reason to weaken an assertion here.
"""
import math
import unittest

from icarus_sim.terrain_biome_catalogue import NATURAL_BIOMES, UNREACHABLE_BIOMES
from icarus_sim.terrain_biomes import classify, marsh_suitable
from icarus_sim.terrain_ecology import cold_habitat, monthly_temperatures
from icarus_sim.terrain_world import generate_request

# The eleven identities a world is expected to be able to contain, derived from the
# registry rather than listed, so the tombstone lane and this file cannot disagree.
ROSTER = frozenset(set(NATURAL_BIOMES) - UNREACHABLE_BIOMES)
TOMBSTONED = frozenset(UNREACHABLE_BIOMES)

# `add_environment` maps the cold pass onto these ids (terrain_ecology.py:107).
COLD_ID = {'boreal': 15, 'tundra': 16, 'ice_cap': 17}

# `8 lake` is NOT produced by `classify`. `add_terrain_labels` overrides the classified
# label with 8 wherever `water_type == 2` (`elif water==2:biome=8`). It therefore cannot
# appear in a sweep of the classifier, and asserting it there would be asserting a literal.
# It is established instead by `test_lake_comes_from_the_water_type_override`, which reads
# a generated world and checks that every lake cell really is a `water_type == 2` cell.
WATER_OVERRIDE_ONLY = frozenset({8})

# Declared legal option domains, from `Sim/icarus_sim/terrain_world.py:65-66`:
#   seasonality      spec(1., 0., 2.)
#   ice_accumulation spec(.5, 0., 1.)
# `temperature_offset` is bounded (-40, 40) in `registry()`, so a mean of -60..70 C spans
# every latitude band the proxy can reach at either extreme of that offset.
SEASONALITY = (0., 1., 2.)
ICE_ACCUMULATION = (0., .5, 1.)
LATITUDES = (90., 60., 45., 30., 15., 0., -15., -30., -45., -60., -90.)
SLOPES = (0., 5., 20., 37.9, 38., 60.)


def _temperatures():
    coarse = [t / 2. for t in range(-60, 20)]          # -30.0 .. 9.5 in 0.5 C steps
    fine = [t / 2. for t in range(20, 70)]             # 10.0 .. 34.5 in 0.5 C steps
    wide = [float(t) for t in range(-60, -30, 5)] + [float(t) for t in range(35, 71, 5)]
    return sorted(set(coarse + fine + wide))


def _sweep_the_real_functions():
    """Outcomes of the real classification and cold passes over the legal domains.

    Returns (emitted_by_classify, producible, tombstoned_survivors). `producible` is
    what a cell can end up labelled with once the cold pass has had its say, which is
    the order `add_terrain_labels` then `add_environment` runs them in.
    """
    emitted = set()
    producible = set()
    survivors = []
    # `classify` returns 0 for any cell at or below sea level, before anything else.
    for slope in SLOPES:
        for temp in (-60., 0., 15., 70.):
            emitted.add(classify(0., slope, temp, .5))
            emitted.add(classify(-1., slope, temp, .5))
    producible |= emitted
    for temp in _temperatures():
        for step in range(0, 21):
            wet = step / 20.
            dry_ids = {classify(10., slope, temp, wet) for slope in SLOPES}
            emitted |= dry_ids
            for latitude in LATITUDES:
                for seasonality in SEASONALITY:
                    temps = monthly_temperatures(temp, latitude, wet, seasonality)
                    for accumulation in ICE_ACCUMULATION:
                        cold = cold_habitat(temps, wet, accumulation)
                        if cold:
                            producible.add(COLD_ID[cold])
                            continue
                        producible |= dry_ids
                        bad = dry_ids & TOMBSTONED
                        if bad:
                            survivors.append((temp, wet, latitude, seasonality,
                                              accumulation, sorted(bad)))
            # Marsh is written over the classified label by `add_terrain_labels` when the
            # cell is unfrozen land inside the wetland margin. Use the real predicate.
            for slope in SLOPES:
                if marsh_suitable(wet, temp, slope, 0., 0.):
                    producible.add(13)
    return emitted, producible, survivors


_SWEEP = None


def sweep():
    global _SWEEP
    if _SWEEP is None:
        _SWEEP = _sweep_the_real_functions()
    return _SWEEP


# Recorded witnesses. Every row was generated on this tree at phase 10 and its realised
# `natural_biome` set read back. `expected` is a SUBSET assertion except where noted.
# Measured costs: the three size-17 rows about 0.3 s each, (3, 33) about 0.9 s,
# (0, 65) about 3.7 s.
#
# (0, 65) is the all-eleven row. It is preferred over (6, 33), which also carries all
# eleven for about 1 s, because all six of seeds 0-5 carry all eleven at raster 65 where
# only 1 of the 12 sampled seeds does at raster 33 -- a row that holds for one seed in
# twelve is a row that a small retune breaks for reasons that are not a regression.
WITNESSES = (
    (0, 17, frozenset({0, 3, 4, 7, 13, 15, 16, 17})),
    (1, 17, frozenset({2})),
    (9, 17, frozenset({8})),
    (3, 33, frozenset({5})),
    (0, 65, ROSTER),
)

# Raster 17 is the default world size and cannot produce `5 exposed_rock`: 0 of 232 seeds,
# maximum land slope 31.39 degrees against the `if slope>=38: return 5` branch. The cause
# is the relief-to-cell-width ratio, not the threshold, and it is recorded in
# board/backlog/BIOME-EXPOSED-ROCK-NEEDS-RELIEF.md with the measurements and the ruling.
# If this constant ever has to change, re-measure and update that card. Do not delete it.
UNREACHABLE_AT_DEFAULT_RASTER = frozenset({5})
DEFAULT_RASTER = 17

_WORLDS = {}


def world(seed, size):
    """A phase-10 world, generated once per process and shared by the witness tests."""
    key = (seed, size)
    if key not in _WORLDS:
        _WORLDS[key] = generate_request(
            {'seed': seed, 'recipe_version': 3, 'overrides': {'size': size, 'phase': 10}})
    return _WORLDS[key]


def realised(seed, size):
    """Realised natural_biome ids, counting interior cells only.

    The seam column and the duplicated pole rows are copies, not cells, so counting them
    would report a biome as present in places the world does not have.
    """
    layers = world(seed, size)['layers']
    ids = set()
    for z in range(size):
        for x in range(1 if z in (0, size - 1) else size - 1):
            ids.add(layers['natural_biome'][z][x])
    return ids


class BiomeReachabilityTest(unittest.TestCase):

    def test_the_roster_is_the_registry_minus_the_tombstone(self):
        self.assertEqual(TOMBSTONED, frozenset({1, 6}))
        self.assertEqual(len(ROSTER), 11)
        self.assertTrue(ROSTER.isdisjoint(TOMBSTONED))

    def test_every_surviving_biome_has_a_producing_input(self):
        """The real classifier and the real cold pass between them produce the roster.

        `8 lake` is excluded on purpose: nothing in either function can emit it. See
        WATER_OVERRIDE_ONLY above and the test below it.
        """
        _, producible, _ = sweep()
        self.assertEqual(producible, set(ROSTER) - WATER_OVERRIDE_ONLY)

    def test_lake_comes_from_the_water_type_override(self):
        """Lake is a water statement, not a climate one, so it is checked on a world.

        Asserting `8` in the classifier sweep would assert a literal. Instead: no legal
        input makes `classify` return 8, and on the world that does carry lakes every
        lake cell is a `water_type == 2` cell -- the override in `add_terrain_labels`.
        """
        emitted, producible, _ = sweep()
        self.assertNotIn(8, emitted)
        self.assertNotIn(8, producible)
        layers = world(9, DEFAULT_RASTER)['layers']
        lakes = [(x, z)
                 for z in range(DEFAULT_RASTER)
                 for x in range(1 if z in (0, DEFAULT_RASTER - 1) else DEFAULT_RASTER - 1)
                 if layers['natural_biome'][z][x] == 8]
        self.assertTrue(lakes, 'witness (9, 17) is recorded as carrying lake cells')
        for x, z in lakes:
            self.assertEqual(layers['water_type'][z][x], 2)

    def test_tombstoned_ids_cannot_survive_the_ecology_pass(self):
        """The tombstone is a fact about the pipeline, not a declaration in a registry.

        `classify` must STILL emit 1 and 6 -- they are load-bearing intermediate labels,
        and the "Snow region" feature marker is derived from `biome == 6`. What must not
        happen is one of them reaching the published layer.
        """
        emitted, producible, survivors = sweep()
        self.assertTrue(TOMBSTONED <= emitted,
                        'classify no longer emits the tombstoned intermediate labels')
        self.assertEqual(survivors, [])
        self.assertTrue(producible.isdisjoint(TOMBSTONED))

    def test_recorded_seed_witnesses(self):
        for seed, size, expected in WITNESSES:
            with self.subTest(seed=seed, size=size):
                got = realised(seed, size)
                self.assertTrue(expected <= got,
                                f'seed {seed} size {size} lost {sorted(expected - got)}; '
                                're-measure and move the witness, do not weaken it')
                self.assertTrue(got <= set(ROSTER),
                                f'seed {seed} size {size} published {sorted(got - set(ROSTER))}, '
                                'which is not in the registry roster')
                self.assertTrue(got.isdisjoint(TOMBSTONED))
                # Phase 10 runs add_biome_variants, which raises KeyError on a surviving
                # tombstoned id. Assert the layer so the coverage cannot silently regress
                # to a phase that never executes it.
                self.assertIn('biome_variant', world(seed, size)['layers'])

    def test_every_surviving_biome_has_a_generated_world(self):
        """The union over the GENERATED witnesses covers the roster.

        Compared against generated output rather than against the WITNESSES table, so a
        biome cannot be declared reachable by a literal that no world backs.
        """
        union = set()
        for seed, size, _ in WITNESSES:
            union |= realised(seed, size)
        self.assertEqual(union, set(ROSTER))

    def test_exposed_rock_needs_a_finer_raster_than_the_default(self):
        """Recorded state, not an approval: see BIOME-EXPOSED-ROCK-NEEDS-RELIEF.md.

        A failure here means the measurement moved. Re-run the sweep, correct the card
        and this constant together. It is not licence to lower the 38 degree threshold:
        raster 65 already puts every sampled seed over 38 degrees, so a lowered threshold
        floods every large world with rock.
        """
        coarse = set()
        fine = set()
        for seed, size, _ in WITNESSES:
            (coarse if size <= DEFAULT_RASTER else fine).add(
                frozenset(realised(seed, size)))
        self.assertTrue(coarse, 'the table must keep at least one default-raster witness')
        self.assertTrue(fine, 'the table must keep at least one finer-raster witness')
        self.assertTrue(set().union(*coarse).isdisjoint(UNREACHABLE_AT_DEFAULT_RASTER))
        self.assertTrue(UNREACHABLE_AT_DEFAULT_RASTER <= set().union(*fine))

    def test_the_slope_a_raster_can_represent_is_bounded_by_relief_over_cell_width(self):
        """The mechanism behind the row above, as arithmetic rather than as a story.

        `measure_globe` (`Sim/icarus_sim/terrain_globe.py:86`) takes slope as a centred
        difference whose denominator is `2*radius*angle`, two cell widths. The steepest
        grade a raster can represent is therefore about (height range)/(2*cell width),
        and the classifier's 38 degree branch needs a rise of `tan(38) * 2 * cell width`.
        At the 200 km default that is 9766 m at raster 17 against a 1667 m relief budget.
        """
        circumference_m = 200000.
        radius = circumference_m / (2 * math.pi)
        for size, expected_cell_m in ((17, 6250.), (33, 3125.), (65, 1562.5)):
            with self.subTest(size=size):
                angle = math.pi / (size - 1)
                cell = radius * angle
                self.assertAlmostEqual(cell, expected_cell_m, places=2)
                needed = math.tan(math.radians(38)) * 2 * cell
                self.assertGreater(needed, 1667.)
                if size == 17:
                    self.assertAlmostEqual(needed, 9766., delta=5.)


if __name__ == '__main__':
    unittest.main()
