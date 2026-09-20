"""The four hidden schools: each draws on something the known eight do not.

Generation can never raise one, so every test here places a key point by hand through
the same `edit_network` boundary the corruption API uses, then rebuilds the fields.
"""
import math
import unittest

from icarus_sim.terrain_globe import direction
from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_leyline_history import edit_network, evaluate_networks
from icarus_sim.terrain_world import generate_request


def world(size=17, seed=42):
    # Stage 10 is the first with cities; blood needs somebody to draw on.
    return generate_request({'seed': seed, 'recipe_version': 3, 'overrides': {'size': size, 'phase': 10}})


def place(result, school, direction, intensity=3.):
    nets = result['magic']['networks']
    nets[school] = edit_network(nets[school], new_node={'id': school + '-probe', 'direction': list(direction),
                                                        'intensity': intensity})
    evaluate_networks(result, Config(**result['config']))
    return result['layers']['ley_' + school]


def at(layer, result, point):
    x, z = result['water']['nodes'][point]
    return layer[z][x]


def total(layer):
    return sum(v for row in layer for v in row)


def reach_m(result, layer, seat, size, share=.1):
    """How far from `seat` the field still carries `share` of its peak, in metres."""
    radius = result['effective_config']['globe_radius']
    peak = max(v for row in layer for v in row)
    far = 0.
    for x, z in result['water']['nodes']:
        if layer[z][x] < peak * share:
            continue
        point = direction(x, z, size)
        angle = math.acos(max(-1., min(1., sum(a * b for a, b in zip(point, seat)))))
        far = max(far, radius * angle)
    return far


class HiddenSchoolTests(unittest.TestCase):
    def test_a_generated_world_carries_them_empty(self):
        result = world()
        for school in ('blood', 'void', 'rot', 'eldritch'):
            net = result['magic']['networks'][school]
            self.assertEqual((net['nodes'], net['edges']), ([], []))
            self.assertEqual(total(result['layers']['ley_' + school]), 0.)

    def test_blood_draws_on_the_living(self):
        """The same key point is stronger where people are dense than where they are not."""
        fed = world()
        cities = fed['settlements']['sites']
        self.assertTrue(cities, 'stage 10 world should have founded cities')
        crowded = max(cities, key=lambda c: c.get('population_estimate') or 0.)
        here = place(fed, 'blood', crowded['direction'])
        near_people = at(here, fed, crowded['node'])

        # The identical node in a world with nobody in it: blood has nothing to draw on.
        empty = world()
        empty['settlements']['sites'] = []
        there = place(empty, 'blood', crowded['direction'])
        near_nobody = at(there, empty, crowded['node'])

        self.assertGreater(near_people, near_nobody)

    def test_eldritch_draws_on_what_the_world_already_fears(self):
        fed = world()
        fed['ruins'] = [{'direction': fed['settlements']['sites'][0]['direction']}]
        seat = fed['settlements']['sites'][0]
        here = place(fed, 'eldritch', seat['direction'])

        barren = world()
        barren['ruins'] = []
        barren['beast_nests'] = {'sites': []}
        there = place(barren, 'eldritch', seat['direction'])

        self.assertGreater(at(here, fed, seat['node']), at(there, barren, seat['node']))

    def test_rot_creeps_past_its_own_falloff(self):
        """Contagion, not a Gaussian: rot still holds ground a Gaussian would have lost.

        One key point's Gaussian is down to `exp(-4)`, under two percent of its peak, at
        twice the network width. Rot carrying a tenth of its peak out there is the creep.
        """
        result = world()
        seat = result['settlements']['sites'][0]['direction']
        layer = place(result, 'rot', seat)
        width = result['magic']['networks']['rot']['width_m']
        self.assertGreater(reach_m(result, layer, seat, 17), 2 * width)

    def test_rot_creeps_at_the_same_physical_rate_on_a_finer_grid(self):
        """Scale invariance: cells are not the unit of spread, metres are.

        A fixed iteration count over cells would make a 33-grid world rot roughly twice
        as far as a 17-grid one, because its cells are half the size.
        """
        def rot_reach(size):
            result = world(size=size)
            seat = result['settlements']['sites'][0]['direction']
            layer = place(result, 'rot', seat)
            return reach_m(result, layer, seat, size)

        coarse, fine = rot_reach(17), rot_reach(33)
        self.assertGreater(coarse, 0.)
        self.assertLess(abs(fine - coarse) / coarse, .35,
                        f'rot reached {coarse:.0f} m on a 17 grid and {fine:.0f} m on a 33 grid')

    def test_void_takes_ground_from_its_neighbours(self):
        result = world()
        seat = result['settlements']['sites'][0]
        before = max(result['layers']['ley_' + s][seat['z']][seat['x']]
                     for s in ('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air'))
        self.assertGreater(before, 0., 'need a school with potency here to take it from')
        place(result, 'void', seat['direction'])
        after = max(result['layers']['ley_' + s][seat['z']][seat['x']]
                    for s in ('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air'))
        self.assertLess(after, before)

    def test_void_absent_does_not_flip_a_negative_zero(self):
        """`max(0., -0.) is 0.`, which would move every magic-disabled world's bytes."""
        result = generate_request({'seed': 42, 'recipe_version': 3,
                                   'overrides': {'size': 17, 'phase': 10, 'magic_enabled': 0}})
        weave = result['layers']['ley_weave']
        self.assertTrue(any(math.copysign(1., v) < 0 for row in weave for v in row),
                        'an unmanifested network writes negative zero')


if __name__ == '__main__':
    unittest.main()
