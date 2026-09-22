"""Creatures that do not hold ground, and the one of them that answers to the calendar.

The pass itself is exercised by `tests/test_world_schema_conformance.py`, which validates
the whole block against `Contracts/schemas/beast-movements.schema.json`. What that cannot
see is behaviour *across time*, because it reads one world at one moment. This module runs
the pass repeatedly against the same world at different years, which is the only way to
tell a swarm that erupts from a swarm that is simply always there.

It also holds the two pieces of mathematics the pass uses to avoid looking at the whole
world: a search that stops at the reach, and a walk that stops at the nearest host. Both
are supposed to give exactly what the exhaustive form gave, and both are checked here by
running the exhaustive form beside them rather than by reasoning about them.
"""
import unittest

from icarus_sim.terrain_astrology import DAYS_PER_YEAR

PHASE = 16
# A century of years to search for the best and worst forage year. Long enough that the
# extremes of the draw are actually sampled; short enough that finding them is free,
# because `year_forage_factor` touches no world.
WINDOW = 100

_SHARED = {}


def build(seed=42, size=17, **overrides):
    from icarus_sim.terrain_world import generate_request
    return generate_request({'seed': seed, 'overrides': {'size': size, 'phase': PHASE, **overrides}})


def shared_world():
    """One world for the classes that only read it, built once and at size 33.

    `IrruptionTriggerTests` builds its own at 17, because it re-runs the pass against a
    moved clock and would otherwise hand the others a block from a year they did not ask
    for. It can afford 17; the two below cannot, and the reason is measured rather than
    assumed. At size 17 a search from a routed group's cell settles **2.0 cells on
    average** -- mostly the group's own -- so a bounded search agrees with an unbounded one
    for want of anywhere to disagree, and every perturbation of it still passes. At 33 the
    same sample settles 13, and four separate ways of breaking the search all go red.

    The cost is one size-33 generation, about 35 s against 12 s, paid once for both
    classes. `test_searches_here_are_not_trivial` is what will say so if that stops being
    enough on some future world.
    """
    if 'world' not in _SHARED:
        from icarus_sim.terrain_lab import Config
        world = build(size=33)
        _SHARED['world'] = world
        _SHARED['cfg'] = Config(**world['config'])
    return _SHARED['world'], _SHARED['cfg']


def ground(world, cfg):
    """The graph, the cells and the walking cost, exactly as the pass builds them."""
    from icarus_sim.terrain_erosion import sphere_grid
    from icarus_sim.terrain_nests import habitat_cells
    from icarus_sim.terrain_nomad_routes import travel_cost
    radius = world['effective_config']['globe_radius']
    points, areas, graph = sphere_grid(cfg.size, radius)
    cells = habitat_cells(world, cfg, points, areas)
    return radius, graph, cells, travel_cost(points, cells, cfg)


class IrruptionTriggerTests(unittest.TestCase):
    """A swarm is normally sparse and occasionally overwhelming.

    Before this, every irruptive group marched in every year, because nothing in the
    generator distinguished one year from another. `world_clock` now does.
    """

    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_beast_movement import year_forage_factor
        cls.world = build()
        cls.cfg = Config(**cls.world['config'])
        factors = {year: year_forage_factor(cls.world, year) for year in range(WINDOW)}
        cls.lean = min(factors, key=lambda year: factors[year])
        cls.fat = max(factors, key=lambda year: factors[year])

    def movements_in(self, year):
        """Re-run the pass with the clock standing at `year`, and return the block."""
        from icarus_sim.terrain_beast_movement import add_beast_movements
        self.world['world_clock'] = {
            'version': 1, 'day': float(year) * DAYS_PER_YEAR,
            'age': len(self.world['history']['ages']), 'epoch_day': 0.,
            'derived_from': 'test'}
        add_beast_movements(self.world, self.cfg)
        return self.world['beast_movements']

    @staticmethod
    def marching(block):
        return {group['uid'] for group in block['groups']
                if group['movement'] == 'irruptive' and group['route_status'] == 'routed'}

    def test_a_swarm_marches_in_a_lean_year_and_stays_put_in_a_fat_one(self):
        """The whole card. A fixture on both sides of the threshold: the leanest and the
        fattest year of a century, so a trigger that fired always and one that fired never
        both go red here rather than passing on whichever year the world happened to be
        standing in."""
        lean = self.movements_in(self.lean)
        lean_marching = self.marching(lean)
        fat = self.movements_in(self.fat)
        fat_marching = self.marching(fat)
        self.assertTrue(lean_marching, 'no swarm marched in the leanest year of a century')
        self.assertGreater(len(lean_marching), len(fat_marching),
                           'the same swarms march in a lean year and a fat one, so the year '
                           'is not deciding anything')
        # The solitary phase is the normal state, so a group that marches in the lean year
        # and not in the fat one must exist rather than merely being implied by the counts.
        self.assertTrue(lean_marching - fat_marching)
        self.assertGreater(fat['solitary'], 0, 'every swarm erupted in the fattest year')

    def test_a_group_that_is_not_swarming_is_solitary_rather_than_stranded(self):
        """Two different facts that shared one word. `stranded` means no ground to march
        to; `solitary` means nothing worth marching for this year."""
        block = self.movements_in(self.fat)
        self.assertEqual(block['routed'] + block['stranded'] + block['solitary'],
                         len(block['groups']))
        for group in block['groups']:
            if group['route_status'] != 'solitary':
                continue
            self.assertEqual(group['movement'], 'irruptive', group['uid'])
            self.assertFalse(group['legs'], group['uid'])
            # It keeps a camp, so the encounter index can still place it: a player can meet
            # the solitary phase, just not a swarm on the march.
            self.assertEqual(len(group['camps']), 1, group['uid'])

    def test_the_year_survives_the_tick_that_asks_about_it(self):
        """The trap this pass sits in. `terrain_time` runs it on a MONTHLY cadence and
        hands it `replace(cfg, seed=child_seed(cfg.seed, 'time-beast_movements', index))`,
        so a year factor drawn from `cfg.seed` would be a different number in every month
        of one year -- twelve different weathers inside a year, and a swarm that formed and
        dissolved with the call rather than with the world."""
        from dataclasses import replace
        from icarus_sim.terrain_tectonics import child_seed
        expected = self.movements_in(self.lean)['year_forage_factor']
        for index in (1, 7, 12):
            stepped = replace(self.cfg, seed=child_seed(self.cfg.seed, 'time-beast_movements', index))
            from icarus_sim.terrain_beast_movement import add_beast_movements
            add_beast_movements(self.world, stepped)
            self.assertEqual(self.world['beast_movements']['year_forage_factor'], expected,
                             'month %d of the same year drew a different year' % index)

    def test_the_clock_decides_the_year_and_a_world_without_one_still_has_a_year(self):
        """A generated world carries no `world_clock` -- it is minted by the first time
        advance -- so the pass reads its founding year instead, which is the same day the
        age lottery already samples."""
        from icarus_sim.terrain_beast_movement import world_year
        from icarus_sim.terrain_astrology import reported_year
        naked = {k: v for k, v in self.world.items() if k != 'world_clock'}
        self.assertEqual(world_year(naked), int(reported_year(naked)[0]))
        self.world['world_clock'] = {'version': 1, 'day': 41.0 * DAYS_PER_YEAR, 'age': 0,
                                     'epoch_day': 0., 'derived_from': 'test'}
        self.assertEqual(world_year(self.world), 41)


class BoundedSearchTests(unittest.TestCase):
    """The search that stops at the reach, against the one that searched the whole map.

    The claim the pass rests on is that stopping early costs nothing inside the bound:
    edge costs are strictly positive, so a node the bounded search settles keeps the
    distance and the parent the unbounded search gave it, and the set it settles is
    exactly the set that falls inside the bound. Neither half is obvious enough to take on
    trust, and a defect in either is silent -- a route quietly re-pointed at a different
    cell, on some seeds only.
    """

    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_beast_movement import _priced, _searcher, SEASONAL_REACH
        cls.world, cls.cfg = shared_world()
        cls.radius, cls.graph, cls.cells, cost = ground(cls.world, cls.cfg)
        # staticmethod on both, or `self.search` hands the search the test case as its
        # start node and `self.cost` hands the cost function a fourth argument.
        cls.cost = staticmethod(cost)
        cls.search = staticmethod(_searcher(_priced(cls.graph, cost)))
        cls.limit = SEASONAL_REACH * float(cls.cfg.settlement_spacing)
        # Start nodes of groups that actually routed, sampled across the list.
        #
        # **Not simply the lowest two dozen node indices.** That was the first shape of
        # this and it proved nothing: node 0 is the north pole and the cells around it on
        # this world are all isolated, so every one of those searches settled exactly one
        # cell -- itself -- and passed against any search that can return its own start.
        # A group that routed reached somewhere by definition, and `test_searches_here_are
        # _not_trivial` keeps that honest rather than leaving it to this comment.
        nodes = sorted({group['node'] for group in cls.world['beast_movements']['groups']
                        if group['route_status'] == 'routed'})
        cls.starts = nodes[::max(1, len(nodes) // 24)][:24]

    def test_searches_here_are_not_trivial(self):
        """The guard on the two tests below: a search that settles only its own start
        agrees with everything, so a suite full of them is green and empty."""
        self.assertTrue(self.starts, 'no group start nodes to search from')
        settled = [len(self.search(start, self.limit)[2]) for start in self.starts]
        # 13 on the world this runs against, 2.0 at size 17 where this test is empty.
        self.assertGreater(sum(settled) / len(settled), 6.,
                           'the sampled starts barely reach anywhere, so the comparison '
                           'below is against a search that returns its own start')

    def test_inside_the_bound_it_is_the_search_it_replaced(self):
        from icarus_sim.terrain_settlements import shortest_paths
        from icarus_sim.terrain_nomad_routes import _within
        self.assertTrue(self.starts, 'no group start nodes to search from')
        for start in self.starts:
            distances, parent, reached = self.search(start, self.limit)
            want_d, want_p = shortest_paths(self.graph, start, self.cost)
            # The set, both ways round: nothing reached that is outside the bound, and
            # nothing inside the bound left unreached.
            self.assertEqual(reached, [i for i, d in enumerate(want_d) if d <= self.limit],
                             'node %d settled a different set' % start)
            self.assertEqual(reached, _within(distances, self.limit))
            for node in reached:
                self.assertEqual(distances[node], want_d[node], 'node %d to %d' % (start, node))
                self.assertEqual(parent[node], want_p[node], 'node %d to %d' % (start, node))

    def test_a_target_traces_the_route_the_whole_search_would_have_traced(self):
        from icarus_sim.terrain_settlements import shortest_paths
        from icarus_sim.terrain_society import trace
        pairs = set()
        for group in self.world['beast_movements']['groups']:
            for leg in group['legs']:
                pairs.add((leg['nodes'][0], leg['nodes'][-1]))
        pairs = sorted(pairs)[:24]
        self.assertTrue(pairs, 'the world routed nothing, so this proves nothing')
        for source, destination in pairs:
            _, parent, _ = self.search(source, target=destination)
            _, want_p = shortest_paths(self.graph, source, self.cost)
            self.assertEqual(trace(parent, source, destination),
                             trace(want_p, source, destination),
                             'route %d -> %d' % (source, destination))


class HostWalkTests(unittest.TestCase):
    """The nearest host, found by walking outwards instead of by looking at every host.

    `_follow` stops the walk on two floors, and if either is a hair too tight it drops the
    winner: the follower silently attaches to the wrong thing, or to nothing. So the flat
    scan it replaced is run here against every follower the world placed.
    """

    @classmethod
    def setUpClass(cls):
        cls.world, cls.cfg = shared_world()
        cls.radius, _, cls.cells, _ = ground(cls.world, cls.cfg)

    def test_every_follower_took_the_host_a_flat_scan_would_have_given(self):
        from icarus_sim.terrain_nests import distance
        from icarus_sim.terrain_beast_movement import FOLLOW_REACH, HOST_BIAS, DEFAULT_BIAS
        block = self.world['beast_movements']
        # The host list as it stood when the followers were built: the bands that walk,
        # then the herds this pass had already routed.
        hosts = [band for band in (self.world.get('nomads', {}).get('groups') or [])
                 if band.get('legs')]
        hosts += [group for group in block['groups']
                  if group['movement'] != 'follower' and group['legs']]
        reach = FOLLOW_REACH * float(self.cfg.settlement_spacing)
        followers = [group for group in block['groups'] if group['movement'] == 'follower']
        self.assertTrue(followers, 'the world placed no followers, so this proves nothing')
        self.assertTrue(hosts, 'the world placed no hosts, so this proves nothing')
        attached = 0
        for group in followers:
            bias = HOST_BIAS.get(group.get('role'), DEFAULT_BIAS)
            here = self.cells[group['node']]['direction']
            best = None
            for host in hosts:
                span = distance(here, self.cells[host['node']]['direction'], self.radius)
                if span > reach:
                    continue
                kind = 'nomad' if host['uid'].startswith('nomad-') else 'beastmove'
                mark = (span * bias.get(kind, 1.), host['uid'])
                if best is None or mark < best:
                    best = mark
            self.assertEqual(group['host_uid'], best[1] if best else None, group['uid'])
            attached += best is not None
        self.assertTrue(attached, 'no follower found a host, so the walk was never tested')


if __name__ == '__main__':
    unittest.main()
