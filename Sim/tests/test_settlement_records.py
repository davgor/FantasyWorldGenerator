"""What a settlement record says about itself, and whether the blocks beside it agree.

One generated world, four questions a consumer actually asks of it:

* which block is authoritative for the buildings a city has;
* what each figure with a magnitude in it measures;
* whether a plan's built capacity agrees with the people standing in it;
* and whether a garrison that demonstrably lives on site reports nowhere to sleep.

The world is generated once for the class because a phase-16 generation is the single
largest cost in this suite, and every question here needs the same one.
"""
import unittest

SEED = 42
SIZE = 17

# The three axes a settlement record measures people on. Every emitted key with
# `population` in its name must be one of these, an id, or a block name -- a magnitude
# that shares the word without naming its axis is the defect this pins.
SITE_POPULATION_AXES = ('population_estimate', 'urban_population_estimate',
                        'rural_population_estimate')


class SettlementRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_world import generate_request
        cls.world = generate_request({'seed': SEED, 'overrides': {'size': SIZE, 'phase': 16}})
        cls.sites = cls.world['settlements']['sites']
        cls.plans = {c['city_uid']: c for c in cls.world['city_plans']['cities']}
        npcs = cls.world.get('npcs') or {}
        cls.posts = {row['uid']: row['posts'] for row in npcs.get('sites') or []}
        standing = {}
        for person in npcs.get('people') or []:
            key = person.get('site_uid')
            standing[key] = standing.get(key, 0) + 1
        cls.standing = standing

    # --- CONTENT-CITY-LAYOUT-DEAD-BLOCK ------------------------------------------------

    def test_only_one_block_reports_the_buildings_a_city_has(self):
        """`city_plans` is authoritative; `city_layout` makes no placement claim at all.

        Both blocks used to describe the same city's buildings and they disagreed:
        `city_layout.buildings.options[].placed_count` was 0 for every option of every
        city beside a `city_plans` entry holding placed plots. They cannot be reconciled
        by arithmetic -- they draw from two different catalogues, at two different scales,
        at two different stages -- so only one of them speaks.
        """
        for site in self.sites:
            layout = site['city_layout']
            with self.subTest(city=site['uid']):
                self.assertNotIn('buildings', layout,
                                 'city_layout must make no building-placement claim; '
                                 'city_plans is authoritative')
                self.assertEqual(layout['version'], 2)
                self.assertIn(site['uid'], self.plans,
                              'every site must join a city_plans entry by uid')

    def test_the_asset_requirement_survives_the_removal(self):
        """Deleting the placement claim must not delete what the block is actually for."""
        for site in self.sites:
            layout = site['city_layout']
            with self.subTest(city=site['uid']):
                self.assertIsInstance(layout['required_assets'], list)
                self.assertIsInstance(layout['required_asset_count'], int)
                self.assertIsInstance(layout['required_node_slots'], int)
                self.assertIsInstance(layout['asset_anchors_missing'], bool)

    # --- CONTENT-POPULATION-THREE-NUMBERS ----------------------------------------------

    def test_every_emitted_magnitude_names_the_axis_it_measures(self):
        """No two fields with `population` in the name may measure different axes.

        `city_layout.residents` held the catchment estimate under a word that reads as
        instantiated people, and `city_plans.stats.simulation_population` held the urban
        estimate under a word that names neither. Both now carry the axis in the name and
        equal the site field they copy, so a consumer can join them instead of guessing.
        """
        for site in self.sites:
            layout = site['city_layout']
            plan = self.plans[site['uid']]
            with self.subTest(city=site['uid']):
                self.assertNotIn('residents', layout)
                self.assertEqual(layout['population_estimate'], site['population_estimate'])
                self.assertNotIn('simulation_population', plan['stats'])
                self.assertEqual(plan['stats']['urban_population_estimate'],
                                 site['urban_population_estimate'])
                self.assertEqual(plan['stats']['population_estimate'],
                                 site['population_estimate'])
                for key in site:
                    if 'population' in key and isinstance(site[key], (int, float)):
                        self.assertIn(key, SITE_POPULATION_AXES,
                                      '%r is a magnitude whose name does not name its axis' % key)

    def test_the_three_site_figures_still_add_up(self):
        for site in self.sites:
            with self.subTest(city=site['uid']):
                self.assertEqual(site['population_estimate'],
                                 site['urban_population_estimate']
                                 + site['rural_population_estimate'])

    def test_no_castle_plan_reports_zero_beds_beside_placed_people(self):
        """A castle plan declares no sleeping capacity, rather than declaring none exists.

        Every castle plot used to carry `beds: 0` beside 37-42 `workers`, and `npcs` then
        stood exactly that many people in it. No castle structure in the registry carries
        a bed count, so the zero was never measured; a consumer computing occupancy from
        it got a division by zero rather than a wrong answer. The field is absent now, and
        the block says why.
        """
        castles = self.world['castle_plans']
        self.assertIn('beds', castles, 'the block must say what it does not model')
        fortresses = {str(f['id']): f for f in self.world['humans']['fortresses']}
        for plan in castles['castles']:
            with self.subTest(fortress=plan['fortress_id']):
                for plot in plan['plots']:
                    self.assertNotIn('beds', plot,
                                     'a castle plot declares no bed count rather than zero')
                self.assertNotIn('worker_beds', plan['stats'])
                if not plan['plots']:
                    continue
                node = fortresses[str(plan['fortress_id'])]['node']
                self.assertEqual(self.posts.get('fortress-node-%s' % node, 0),
                                 plan['stats']['workers'],
                                 'workers is the garrison axis a castle plan does report')

    def test_roster_size_agrees_with_built_capacity_for_every_planned_site(self):
        """The two blocks a runtime instantiates must not drift apart.

        `npcs` opens exactly one post per worker the plan staffs, and the planner houses
        every worker it places, so a plan's beds cover its posts. The cast -- heroes and
        villains folded in by presence -- stands in the same places without being staffed
        there, so the people standing in a city exceed its beds by a small margin; the
        tolerance is stated rather than left to be discovered.

        Asserted for cities and hamlets, which model beds. Castles do not, and say so.
        """
        checked = 0
        for kind, plans, key in (
                ('city', self.world['city_plans']['cities'], lambda p: p['city_uid']),
                ('hamlet', self.world['hamlet_plans']['hamlets'],
                 lambda p: 'hamlet-node-%s' % p['node'])):
            for plan in plans:
                if plan['status'] == 'unbuildable':
                    continue
                uid = key(plan)
                stats = plan['stats']
                with self.subTest(**{kind: uid}):
                    self.assertEqual(self.posts.get(uid, 0), stats['workers'],
                                     'the roster opens one post per staffed worker')
                    self.assertGreaterEqual(stats['worker_beds'], stats['workers'],
                                            'the plan must build a bed for every worker it staffs')
                    self.assertLessEqual(self.standing.get(uid, 0) - stats['worker_beds'], 10,
                                         'more than ten people stand here beyond the beds built')
                checked += 1
        self.assertGreater(checked, 0, 'no buildable plan in this world; nothing was tested')


class SurvivorCarryBackTests(unittest.TestCase):
    """The one branch that decides whether a player-authored layout outlives a rebuild.

    Asserted against the function the generator calls rather than against a world, because
    whether a given town survives an age is a property of the war model: on this seed an
    age advance ruins ten of twelve cities, so a world-level assertion would be vacuous
    most runs and flaky the rest.
    """

    def _authored(self):
        return {'population_profile': 'human_heartland', 'uid': 'surface-city-0-1-human',
                'name': 'Player Town', 'founded_by': 'player',
                'city_layout': {'version': 2, 'layout_profile_id': 'player'}}

    def test_a_player_authored_layout_is_carried_onto_the_rebuilt_site(self):
        from icarus_sim.terrain_settlements import carry_survivor
        old = self._authored()
        rebuilt = carry_survivor({'city_layout': {'version': 2, 'layout_profile_id': 'standard_city_layout'}}, old)
        self.assertEqual(rebuilt['city_layout'], old['city_layout'])
        self.assertEqual(rebuilt['founded_by'], 'player')
        self.assertEqual(rebuilt['uid'], old['uid'])

    def test_a_generated_survivor_keeps_the_layout_the_rebuild_derived(self):
        from icarus_sim.terrain_settlements import carry_survivor
        old = dict(self._authored())
        del old['founded_by']
        derived = {'version': 2, 'layout_profile_id': 'standard_city_layout'}
        rebuilt = carry_survivor({'city_layout': derived}, old)
        self.assertEqual(rebuilt['city_layout'], derived)
        self.assertNotIn('founded_by', rebuilt)

    def test_a_player_site_with_no_layout_yet_is_not_given_one(self):
        from icarus_sim.terrain_settlements import carry_survivor
        old = self._authored()
        del old['city_layout']
        derived = {'version': 2, 'layout_profile_id': 'standard_city_layout'}
        rebuilt = carry_survivor({'city_layout': derived}, old)
        self.assertEqual(rebuilt['city_layout'], derived)


if __name__ == '__main__':
    unittest.main()
