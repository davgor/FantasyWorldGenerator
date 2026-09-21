import unittest
from icarus_sim.terrain_nomads import (CLASSIFICATIONS, add_nomads, policy, population_of,
                                       ground, ruggedness, seasonal_swing)

# The pass is not yet wired into `generate_history`, so these call it directly on a
# finished world. The phase gate and the stage-snapshot tests arrive with that wiring.
PHASE = 16


def build(seed=42, size=33, **overrides):
    from icarus_sim.terrain_world import generate_request
    return generate_request({'seed': seed, 'overrides': {'size': size, 'phase': PHASE, **overrides}})


def nomads(world, routes=False):
    from icarus_sim.terrain_lab import Config
    world.setdefault('timing_ms', {'total': 0.})
    world['timing_ms'].setdefault('total', 0.)
    cfg = Config(**world['config'])
    add_nomads(world, cfg)
    if routes:
        from icarus_sim.terrain_nomad_routes import add_nomad_routes
        add_nomad_routes(world, cfg)
    return world['nomads']


class NomadPolicyTests(unittest.TestCase):
    def test_the_table_names_every_classification_and_no_others(self):
        table = policy()['classifications']
        self.assertEqual(set(table), set(CLASSIFICATIONS))
        for name, entry in table.items():
            self.assertGreater(entry['weight'], 0, name)
            self.assertTrue(entry['gate'], name)
            low, high = entry['size']
            self.assertLessEqual(low, high, name)

    def test_a_hamlet_is_worth_something(self):
        # Hamlets carry population_estimate None; without the delivered-food fallback they
        # score zero and bandits ignore the rural settlements that are their easiest prey.
        self.assertEqual(population_of({'population_estimate': None, 'delivered_food': 400.}), 400.)
        self.assertEqual(population_of({'population_estimate': 9000}), 9000.)
        self.assertEqual(population_of({}), 0.)

    def test_ruggedness_and_swing_stay_bounded(self):
        self.assertEqual(ruggedness({'slope': 0., 'tpi': 0.}), 0.)
        self.assertLessEqual(ruggedness({'slope': 90., 'tpi': 200.}), 1.35)
        self.assertEqual(seasonal_swing({'seasonal_environment': {'months': []}}, 0, 0), 0.)


class NomadWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_erosion import sphere_grid
        cls.world = build()
        cls.block = nomads(cls.world, routes=True)
        cls.cfg = Config(**cls.world['config'])
        cls.radius = cls.world['effective_config']['globe_radius']
        points, areas, _ = sphere_grid(cls.cfg.size, cls.radius)
        cls.ground = ground(cls.world, cls.cfg, cls.radius, points)
        from icarus_sim.terrain_nests import habitat_cells
        cls.cells = habitat_cells(cls.world, cls.cfg, points, areas)
        # Grid row per node, for the hemisphere assertions.
        cls.rows = [z for _, z in points]
        cls.gates = policy()['classifications']

    def bands(self, name):
        return [b for b in self.block['groups'] if b['classification'] == name]

    def test_replay_is_identical(self):
        import copy
        import json
        again = nomads(copy.deepcopy({k: v for k, v in self.world.items() if k != 'nomads'}), routes=True)
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.block, sort_keys=True))

    def test_the_document_stays_finite(self):
        import json
        json.dumps(self.world, allow_nan=False)

    def test_every_band_traces_back_to_a_roll_or_to_a_parent(self):
        # A placed band comes from a candidate roll. A fission child comes from a band that
        # did, and is deliberately NOT written into `rolls`: `rolls` answers "what did the
        # point process consider here", and a child was never considered -- it descends.
        rolled = {r['uid'] for r in self.block['rolls'] if r.get('uid')}
        placed = {b['uid'] for b in self.block['groups'] if not b.get('parent_uid')}
        self.assertEqual(placed, rolled)
        for band in self.block['groups']:
            if band.get('parent_uid'):
                self.assertIn(band['parent_uid'], rolled, band['uid'])
        self.assertEqual(len({b['uid'] for b in self.block['groups']}), len(self.block['groups']))

    def test_a_candidate_that_satisfies_nothing_raises_nobody(self):
        # Empty ground is a result, not a failure: a roll with no eligible classification
        # must record itself and produce no band.
        for roll in self.block['rolls']:
            if roll['eligible']:
                continue
            self.assertFalse(roll['precipitated'])
            self.assertIsNone(roll.get('uid'))

    def test_no_cult_without_sacred_ground(self):
        # The reason this feature exists. A cult needs charged ground AND a god bound to
        # its school, never merely a good weight.
        rule = self.gates['cultists']['gate']
        gods = {g['id'] for g in self.world.get('religion', {}).get('gods', [])}
        for band in self.bands('cultists'):
            basis = band['basis']
            self.assertIn(band['god_id'], gods, band['uid'])
            self.assertTrue(band['school'], band['uid'])
            if 'ley_node_id' in basis:
                self.assertGreaterEqual(basis['ley_intensity'], rule['min_ley_intensity'], band['uid'])
                self.assertLessEqual(basis['ley_distance_m'],
                                     rule['ley_reach_spacings'] * self.ground['spacing'], band['uid'])
            elif 'shrine_id' in basis:
                self.assertLessEqual(basis['shrine_distance_m'],
                                     rule['shrine_reach_spacings'] * self.ground['spacing'], band['uid'])
            else:
                self.assertIn('claim_id', basis, band['uid'])

    def test_no_caravan_without_a_road_and_two_markets(self):
        rule = self.gates['merchants']['gate']
        for band in self.bands('merchants'):
            basis = band['basis']
            self.assertGreaterEqual(basis['market_count'], rule['min_markets'], band['uid'])
            self.assertLessEqual(basis['road_distance_m'],
                                 rule['road_reach_spacings'] * self.ground['spacing'], band['uid'])

    def test_no_bandits_without_both_refuge_and_wealth(self):
        rule = self.gates['bandits']['gate']
        spacing = self.ground['spacing']
        for band in self.bands('bandits'):
            basis = band['basis']
            self.assertGreaterEqual(basis['ruggedness'], rule['min_ruggedness'], band['uid'])
            self.assertLessEqual(basis['prize_distance_m'], rule['strike_reach_spacings'] * spacing, band['uid'])
            # Weak control is the third condition, and the one that is easy to forget.
            self.assertGreaterEqual(basis['nearest_seat_m'], rule['control_clear_spacings'] * spacing, band['uid'])

    def test_no_survivors_without_a_town_that_died_this_age(self):
        latest = self.ground['latest_age']
        fresh = {r['uid'] for r in self.world.get('ruins', []) if r.get('destroyed_age') == latest}
        for band in self.bands('survivors'):
            self.assertIn(band['basis']['ruin_uid'], fresh, band['uid'])
            self.assertTrue(band['basis']['refuge_uid'], band['uid'])

    def test_no_deserters_without_a_decided_war_and_cover(self):
        rule = self.gates['deserters']['gate']
        fought = {r['uid'] for r in self.world.get('ruins', []) if r.get('war_history')}
        fought |= {s['uid'] for s in self.world['settlements']['sites'] if s.get('war_history')}
        for band in self.bands('deserters'):
            self.assertIn(band['basis']['war_site_uid'], fought, band['uid'])
            self.assertGreaterEqual(band['basis']['ruggedness'], rule['min_ruggedness'], band['uid'])

    def test_no_herders_without_forage_that_moves_with_the_year(self):
        rule = self.gates['wanderers']['gate']
        for band in self.bands('wanderers'):
            self.assertGreaterEqual(band['basis']['forage'], rule['min_forage'], band['uid'])
            self.assertGreaterEqual(band['basis']['seasonal_swing'], rule['min_seasonal_swing'], band['uid'])

    def test_every_band_is_shaped_for_a_time_mover(self):
        # The next piece of work moves these day by day, so a speed and a column must
        # exist on every band regardless of how it was classified.
        for band in self.block['groups']:
            self.assertGreater(band['speed_m_per_day'], 0, band['uid'])
            self.assertGreater(band['column_length_m'], 0, band['uid'])
            self.assertTrue(band['camps'], band['uid'])
            self.assertEqual(band['origin']['kind'], 'world', band['uid'])
            self.assertIn(band['classification'], CLASSIFICATIONS, band['uid'])


class NomadScaleTests(unittest.TestCase):
    def test_bands_scale_with_the_ground_rather_than_the_raster(self):
        # A band count that tracks the grid instead of the land means the density is a
        # per-cell accident; the same world at two rasters must hold a comparable number.
        coarse = nomads(build(size=17))
        fine = nomads(build(size=33))
        self.assertTrue(coarse['groups'] and fine['groups'])
        ratio = len(fine['groups']) / len(coarse['groups'])
        self.assertTrue(.4 < ratio < 2.5, (len(coarse['groups']), len(fine['groups'])))

class NomadRouteTests(NomadWorldTests):
    """Route assertions over the same world the classification tests use."""

    def routed(self):
        return [b for b in self.block['groups'] if b.get('route_status') == 'routed']

    def test_every_routed_band_has_a_schedule_a_mover_can_read(self):
        from icarus_sim.terrain_astrology import DAYS_PER_YEAR
        self.assertTrue(self.routed(), 'this world must route at least one band')
        for band in self.routed():
            self.assertTrue(band['legs'], band['uid'])
            for camp in band['camps']:
                # A camp with no window is a camp a time-mover cannot place anyone in.
                self.assertIsNotNone(camp['arrive_day'], (band['uid'], camp['kind']))
                self.assertTrue(0 <= camp['arrive_day'] < DAYS_PER_YEAR, camp)
                self.assertTrue(0 <= camp['depart_day'] < DAYS_PER_YEAR, camp)

    def test_leg_paths_are_contiguous_walks(self):
        """A leg is a walk, so consecutive nodes must actually be neighbours."""
        from icarus_sim.terrain_erosion import sphere_grid
        _, _, graph = sphere_grid(self.cfg.size, self.radius)
        for band in self.routed():
            for leg in band['legs']:
                self.assertGreaterEqual(len(leg['nodes']), 2, (band['uid'], leg['from']))
                for a, b in zip(leg['nodes'], leg['nodes'][1:]):
                    self.assertIn(b, [j for j, _ in graph[a]], (band['uid'], a, b))

    def test_no_caravan_leg_exceeds_a_day_march(self):
        """The whole logic of a caravan stop: never spend a night in the gap."""
        from icarus_sim.terrain_nomad_routes import DAY_MARCH_M
        for band in self.routed():
            if band['classification'] != 'merchants':
                continue
            for leg in band['legs']:
                self.assertLessEqual(leg['length_m'], DAY_MARCH_M * 1.05, (band['uid'], leg['length_m']))

    def test_a_raid_is_measured_in_days_not_seasons(self):
        """A bandit holds its lair and leaves what it robbed; an even split put it in the
        hamlet it had raided for three weeks."""
        from icarus_sim.terrain_nomad_routes import CAMP_REST_CEILING
        from icarus_sim.terrain_astrology import DAYS_PER_YEAR
        for band in self.routed():
            for camp in band['camps']:
                if camp['kind'] != 'terminal':
                    continue
                held = (camp['depart_day'] - camp['arrive_day']) % DAYS_PER_YEAR
                self.assertLessEqual(held, CAMP_REST_CEILING['terminal'], (band['uid'], held))

    def test_a_winter_camp_holds_midwinter_on_its_own_hemisphere(self):
        """The seasonal phase inverts across the equator. A world whose land sits in one
        hemisphere hides this completely, so it is asserted rather than eyeballed."""
        from icarus_sim.terrain_nomad_routes import midwinter_day
        from icarus_sim.terrain_astrology import DAYS_PER_YEAR
        checked = 0
        for band in self.routed():
            for camp in band['camps']:
                if camp['kind'] != 'winter':
                    continue
                target = midwinter_day(self.rows[camp['node']], self.cfg.size)
                held = (camp['depart_day'] - camp['arrive_day']) % DAYS_PER_YEAR
                offset = (target - camp['arrive_day']) % DAYS_PER_YEAR
                self.assertLessEqual(offset, held + 1, (band['uid'], camp['arrive_day'], target))
                checked += 1
        if not checked:
            self.skipTest('this world routed no herding band with a winter camp')

    def test_a_stranded_band_says_so_and_keeps_its_start(self):
        for band in self.block['groups']:
            if band.get('route_status') != 'stranded':
                continue
            self.assertFalse(band['legs'], band['uid'])
            self.assertEqual(len(band['camps']), 1, band['uid'])

    def test_the_route_summary_accounts_for_every_band(self):
        summary = self.block['routes']
        self.assertEqual(summary['routed'] + summary['stranded'], len(self.block['groups']))

    # ---------------------------------------------------------------- lineage fission

    def children(self):
        return [b for b in self.block['groups'] if b.get('parent_uid')]

    def test_a_clan_that_outgrows_its_round_splits_onto_ground_it_already_held(self):
        """`fission` was a declared branch and `parent_uid` sat on every band; neither was
        ever populated, so the vocabulary promised something the generator did not do."""
        children = self.children()
        self.assertTrue(children, 'no band names a parent: lineage fission never ran')
        self.assertIn('fission', {leg['branch'] for b in children for leg in b['legs']},
                      'no leg joins a child to its parent')
        from icarus_sim.terrain_nomad_routes import round_forage, round_capacity
        by_uid = {b['uid']: b for b in self.block['groups']}
        pol = policy()
        for child in children:
            parent = by_uid.get(child['parent_uid'])
            self.assertIsNotNone(parent, child['uid'])
            self.assertEqual(child['classification'], parent['classification'], child['uid'])
            # Inherited ground, not fresh ground: the child starts on a camp of the
            # parent's own round.
            self.assertIn(child['node'], [c['node'] for c in parent['camps']], child['uid'])
            # The trigger is the parent's size against what its round carries, not a roll.
            self.assertGreater(parent['size'],
                               round_capacity(parent, pol, round_forage(parent, self.cells)),
                               parent['uid'])
            joins = [leg for leg in child['legs'] if leg['branch'] == 'fission']
            self.assertEqual(len(joins), 1, child['uid'])
            # The join names the parent's own start camp, which is what makes it a join
            # between two rounds rather than a leg inside one.
            self.assertEqual(joins[0]['to'], parent['camps'][0]['id'], child['uid'])
            self.assertEqual(joins[0]['from'], child['camps'][0]['id'], child['uid'])

    def test_the_trigger_is_head_count_against_the_round_and_nothing_else(self):
        """A fixture placed on both sides of the threshold on purpose.

        The bands this world happens to raise sit wherever the size draw put them, so a
        test that only reads them passes for a trigger that fired for everybody and for a
        trigger that fired for nobody. These two populations are built one head above and
        one head below each band's own computed capacity, so both readings go red.
        """
        import copy
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_nomad_routes import add_nomad_routes, round_forage, round_capacity
        cfg = Config(**self.world['config'])
        pol = policy()
        outcome = {}
        for label in ('over', 'under'):
            world = {k: v for k, v in self.world.items() if k != 'nomads'}
            world['nomads'] = copy.deepcopy(self.block)
            world['nomads']['groups'] = [b for b in world['nomads']['groups']
                                         if not b.get('parent_uid')]
            for band in world['nomads']['groups']:
                if band['classification'] != 'wanderers':
                    continue
                carries = round_capacity(band, pol, round_forage(band, self.cells))
                band['size'] = max(1, int(carries) + 1 if label == 'over' else int(carries))
            add_nomad_routes(world, cfg)
            outcome[label] = world['nomads']['routes']['fissioned']
        self.assertGreater(outcome['over'], 0,
                           'no clan split with every herder one head over what its round carries')
        self.assertEqual(outcome['under'], 0,
                         'a clan split while no herder was over what its round carries')

    def test_fission_is_bounded_because_a_child_never_splits_again(self):
        """The ceiling, and the whole reason the conservative reading was taken: fission
        runs once at placement, at most one child per band, and a child is not a parent."""
        children = self.children()
        parents = [b['parent_uid'] for b in children]
        self.assertEqual(len(parents), len(set(parents)), 'a band fissioned more than once')
        child_uids = {b['uid'] for b in children}
        self.assertFalse(child_uids & set(parents), 'a child fissioned')
        self.assertLessEqual(len(children),
                             len(self.block['groups']) - len(children))

    def test_rebuilding_the_routes_does_not_breed_more_bands(self):
        """`add_nomad_routes` runs again on every `nomad_request` and on the monthly route
        cadence. A fission step that accumulated there is the unbounded growth the card
        warned about, so it is re-derived rather than added to."""
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_nomad_routes import add_nomad_routes
        import json
        before = json.dumps(self.block, sort_keys=True)
        add_nomad_routes(self.world, Config(**self.world['config']))
        self.assertEqual(json.dumps(self.world['nomads'], sort_keys=True), before)

    def test_the_counts_include_the_children(self):
        tally = {}
        for band in self.block['groups']:
            tally[band['classification']] = tally.get(band['classification'], 0) + 1
        for name in CLASSIFICATIONS:
            self.assertEqual(self.block['counts'][name], tally.get(name, 0), name)


if __name__ == '__main__':
    unittest.main()
