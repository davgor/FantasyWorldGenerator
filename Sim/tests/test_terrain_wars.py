import unittest

from icarus_sim.terrain_wars import (WAR_CIVIL, WAR_INTERNATIONAL, WAR_REGIONAL, contested_pairs,
                                     resolve_wars, war_chance, war_kind, war_strength)


def city(uid, profile, parent, node, direction, population=100, suitability=.5):
    return {'uid': uid, 'population_profile': profile, 'civilization_id': profile,
            'parent_race_id': parent, 'node': node, 'x': node, 'z': 0, 'direction': direction,
            'population_estimate': population, 'suitability': suitability}


def core(site_id, forts=0, demand=10., supply=10.):
    return {'site_id': site_id, 'fortress_ids': [f'fortress-{site_id}-{i}' for i in range(forts)],
            'food_demand': demand, 'food_supply': supply}


def flat_layers(schools=('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air'), value=0.):
    return {'ley_' + name: [[value, value, value]] for name in schools}


class WarKindTests(unittest.TestCase):
    def test_kind_follows_civilization_then_parent_race(self):
        gnome = city('a', 'gnome', 'dwarf', 0, (1., 0., 0.))
        gnome_two = city('b', 'gnome', 'dwarf', 1, (1., 0., 0.))
        hill = city('c', 'hill_dwarf', 'dwarf', 2, (1., 0., 0.))
        elf = city('d', 'elf', 'elf', 3, (1., 0., 0.))
        self.assertEqual(war_kind(gnome, gnome_two), WAR_CIVIL)
        self.assertEqual(war_kind(gnome, hill), WAR_REGIONAL)
        self.assertEqual(war_kind(gnome, elf), WAR_INTERNATIONAL)
        # The relation is symmetric; which city is asked first cannot change the kind.
        self.assertEqual(war_kind(hill, gnome), WAR_REGIONAL)
        self.assertEqual(war_kind(elf, gnome), WAR_INTERNATIONAL)


class ContestedPairTests(unittest.TestCase):
    def pair_at(self, metres, radius=1000., **kwargs):
        import math
        angle = metres / radius
        a = city('a', 'gnome', 'dwarf', 0, (1., 0., 0.))
        b = city('b', 'elf', 'elf', 1, (math.cos(angle), math.sin(angle), 0.))
        return contested_pairs([a, b], [core(0), core(1)], [], radius, spacing=450., **kwargs)

    def test_distance_inside_the_founding_spacing_is_contested(self):
        close = self.pair_at(300.)
        self.assertEqual(len(close), 1)
        self.assertGreater(close[0]['proximity_pressure'], 0)
        self.assertEqual(close[0]['kind'], WAR_INTERNATIONAL)
        # 1.5x the spacing is the outer edge: beyond it proximity alone is not a quarrel.
        self.assertEqual(self.pair_at(700.), [])

    def test_a_hungry_city_contests_the_neighbour_its_road_reaches(self):
        import math
        angle = 5000. / 1000.
        a = city('a', 'gnome', 'dwarf', 0, (1., 0., 0.))
        b = city('b', 'gnome', 'dwarf', 1, (math.cos(angle), math.sin(angle), 0.))
        roads = [{'from': 0, 'to': 1}]
        hungry = [core(0), core(1, demand=10., supply=4.)]
        pairs = contested_pairs([a, b], hungry, roads, radius=1000., spacing=450.)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]['proximity_pressure'], 0)
        self.assertAlmostEqual(pairs[0]['supply_pressure'], .6)
        self.assertEqual(pairs[0]['kind'], WAR_CIVIL)
        # Hunger with no road between them is nothing they can take from each other.
        self.assertEqual(contested_pairs([a, b], hungry, [], 1000., 450.), [])
        # A road between two cities that both feed themselves is just a road.
        self.assertEqual(contested_pairs([a, b], [core(0), core(1)], roads, 1000., 450.), [])

    def test_shortfall_is_the_pre_trade_share_a_city_cannot_feed(self):
        from icarus_sim.terrain_wars import shortfall
        self.assertEqual(shortfall(core(0, demand=10., supply=10.)), 0.)
        self.assertAlmostEqual(shortfall(core(0, demand=10., supply=2.5)), .75)
        # A surplus is not negative pressure, and a city with no demand is not hungry.
        self.assertEqual(shortfall(core(0, demand=10., supply=40.)), 0.)
        self.assertEqual(shortfall(core(0, demand=0., supply=0.)), 0.)
        self.assertEqual(shortfall(None), 0.)

    def test_pairs_are_ordered_by_pressure_and_are_deterministic(self):
        pairs = self.pair_at(100.) + self.pair_at(400.)
        self.assertGreater(pairs[0]['pressure'], pairs[1]['pressure'])
        self.assertEqual(self.pair_at(100.), self.pair_at(100.))


class WarResolutionTests(unittest.TestCase):
    def test_strength_counts_people_and_standing_forts(self):
        self.assertEqual(war_strength(city('a', 'gnome', 'dwarf', 0, (1., 0., 0.), population=100),
                                      core(0)), 100)
        self.assertGreater(war_strength(city('a', 'gnome', 'dwarf', 0, (1., 0., 0.), population=100),
                                        core(0, forts=2)), 100)

    def test_chance_rises_with_pressure_and_stays_bounded(self):
        self.assertLess(war_chance(0.), war_chance(1.))
        self.assertGreaterEqual(war_chance(0.), 0.)
        self.assertLessEqual(war_chance(1.), 1.)

    def test_the_weaker_city_falls_and_both_sides_are_logged(self):
        import math
        angle = 200. / 1000.
        strong = city('strong', 'gnome', 'dwarf', 0, (1., 0., 0.), population=400)
        weak = city('weak', 'elf', 'elf', 1, (math.cos(angle), math.sin(angle), 0.), population=40)
        wars, fates = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(),
                                   radius=1000., spacing=450., seed=42, age=1, rolls={'*': 0.})
        self.assertEqual(len(wars), 1)
        war = wars[0]
        self.assertEqual(war['kind'], WAR_INTERNATIONAL)
        self.assertEqual(war['victor_uid'], 'strong')
        self.assertEqual(war['defeated_uid'], 'weak')
        self.assertEqual(sorted(war['participants']), ['strong', 'weak'])
        self.assertIn('weak', fates)
        self.assertNotIn('strong', fates)
        self.assertEqual(fates['weak']['cause'], 'war_' + WAR_INTERNATIONAL)
        self.assertEqual(fates['weak']['evidence']['war_id'], war['id'])

    def test_a_city_dies_once_however_many_neighbours_it_angers(self):
        import math
        def at(metres):
            angle = metres / 1000.
            return (math.cos(angle), math.sin(angle), 0.)
        middle = city('middle', 'elf', 'elf', 1, at(200.), population=10)
        left = city('left', 'gnome', 'dwarf', 0, at(0.), population=500)
        right = city('right', 'gnome', 'dwarf', 2, at(400.), population=500)
        wars, fates = resolve_wars([left, middle, right], [core(0), core(1), core(2)], [],
                                   flat_layers(), 1000., 450., seed=42, age=1, rolls={'*': 0.})
        self.assertEqual(len([w for w in wars if w['defeated_uid'] == 'middle']), 1)
        self.assertEqual(sum(1 for uid in fates if uid == 'middle'), 1)

    def test_a_magically_charged_city_leaves_a_key_point_when_it_falls(self):
        import math
        angle = 200. / 1000.
        strong = city('strong', 'gnome', 'dwarf', 0, (1., 0., 0.), population=400)
        weak = city('weak', 'elf', 'elf', 1, (math.cos(angle), math.sin(angle), 0.), population=40)
        quiet = flat_layers()
        charged = flat_layers()
        # z=0, x=node: the loser stands on a strongly infernal cell, the victor does not.
        charged['ley_infernal'] = [[0., .8, 0.]]
        _, plain = resolve_wars([strong, weak], [core(0), core(1)], [], quiet,
                                1000., 450., seed=42, age=1, rolls={'*': 0.})
        _, magical = resolve_wars([strong, weak], [core(0), core(1)], [], charged,
                                  1000., 450., seed=42, age=1, rolls={'*': 0.})
        self.assertIsNone(plain['weak']['new_node_school'])
        self.assertEqual(magical['weak']['new_node_school'], 'infernal')
        # Magic off means no key point, however charged the ground is.
        _, mundane = resolve_wars([strong, weak], [core(0), core(1)], [], charged,
                                  1000., 450., seed=42, age=1, magic_enabled=False, rolls={'*': 0.})
        self.assertIsNone(mundane['weak']['new_node_school'])

    def test_a_high_roll_keeps_the_peace(self):
        import math
        angle = 200. / 1000.
        a = city('a', 'gnome', 'dwarf', 0, (1., 0., 0.), population=400)
        b = city('b', 'elf', 'elf', 1, (math.cos(angle), math.sin(angle), 0.), population=40)
        wars, fates = resolve_wars([a, b], [core(0), core(1)], [], flat_layers(),
                                   1000., 450., seed=42, age=1, rolls={'*': 1.})
        self.assertEqual(wars, [])
        self.assertEqual(fates, {})

    def test_resolution_is_reproducible_for_a_seed_and_age(self):
        import math
        angle = 200. / 1000.
        a = city('a', 'gnome', 'dwarf', 0, (1., 0., 0.), population=400)
        b = city('b', 'elf', 'elf', 1, (math.cos(angle), math.sin(angle), 0.), population=40)
        args = ([a, b], [core(0), core(1)], [], flat_layers(), 1000., 450.)
        self.assertEqual(resolve_wars(*args, seed=42, age=1), resolve_wars(*args, seed=42, age=1))


class WarsInGeneratedWorldTests(unittest.TestCase):
    """The age transition's side of it: ruins, histories and the defences that follow."""

    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_world import generate_request
        cls.world = generate_request({'recipe_version': 3, 'seed': 42,
                                      'overrides': {'size': 33, 'phase': 15}})

    def test_every_age_reports_its_wars_and_they_cost_cities(self):
        ages = self.world['history']['ages']
        self.assertTrue(ages)
        fought = [war for age in ages for war in age['wars']]
        self.assertTrue(fought, 'seed 42 at grid 33 is contested enough to go to war')
        for age in ages:
            self.assertIn('wars', age['order'])
            for war in age['wars']:
                self.assertEqual(war['age'], age['age'])
                self.assertIn(war['kind'], (WAR_CIVIL, WAR_REGIONAL, WAR_INTERNATIONAL))
                self.assertNotEqual(war['victor_uid'], war['defeated_uid'])
                self.assertEqual(sorted(war['participants']),
                                 sorted([war['victor_uid'], war['defeated_uid']]))
        # Every defeated city is a ruin naming the war that ended it, and no victor is.
        ruins = {ruin['uid']: ruin for ruin in self.world['ruins']}
        victors = {war['victor_uid'] for war in fought}
        for war in fought:
            self.assertIn(war['defeated_uid'], ruins)
            self.assertEqual(ruins[war['defeated_uid']]['cause'], 'war_' + war['kind'])
            self.assertEqual(ruins[war['defeated_uid']]['destroyed_age'], war['age'])
        # A city can be drawn into several wars in one age and is only lost once, so a
        # victor may still fall to another war; it is never the ruin of the war it won.
        for war in fought:
            ruin = ruins.get(war['victor_uid'])
            if ruin and ruin['cause'].startswith('war_'):
                self.assertNotEqual(ruin['evidence']['war_id'], war['id'])
        self.assertTrue(victors)
        # The invariant the resolver enforces: a city is lost at most once per age.
        for age in ages:
            lost = [war['defeated_uid'] for war in age['wars']]
            self.assertEqual(len(lost), len(set(lost)), 'a city can be dragged into several wars but is only lost once')

    def test_both_sides_keep_the_war_and_a_ruin_keeps_what_it_fought(self):
        fought = [war for age in self.world['history']['ages'] for war in age['wars']]
        ruins = {ruin['uid']: ruin for ruin in self.world['ruins']}
        living = {city['uid']: city for city in self.world['settlements']['sites']}
        for war in fought:
            for uid in war['participants']:
                record = living.get(uid) or ruins[uid]
                entries = [e for e in record.get('war_history', []) if e['war_id'] == war['id']]
                self.assertEqual(len(entries), 1, f'{uid} should log {war["id"]} exactly once')
                entry = entries[0]
                self.assertEqual(entry['kind'], war['kind'])
                self.assertEqual(entry['outcome'], 'victor' if uid == war['victor_uid'] else 'defeated')
                self.assertNotEqual(entry['opponent_uid'], uid)
        # A defeated city's ruin carries the history, not just the killing blow.
        self.assertTrue(any(ruins[w['defeated_uid']].get('war_history') for w in fought))

    def test_a_war_ruin_only_charges_ground_a_school_already_held(self):
        from icarus_sim.terrain_leyline_history import SCHOOLS, dominant_school
        layers = self.world['layers']
        war_ruins = [r for r in self.world['ruins'] if r['cause'].startswith('war_')]
        self.assertTrue(war_ruins)
        for ruin in war_ruins:
            potencies = {name: layers['ley_' + name][ruin['z']][ruin['x']] for name in SCHOOLS}
            self.assertEqual(ruin['new_node_school'], dominant_school(potencies))

    def test_veterans_ask_for_more_defence_than_cities_that_never_fought(self):
        demand = self.world['humans']['fortress_demand']
        sites = self.world['settlements']['sites']
        veterans = [s for s in sites if s.get('war_history')]
        self.assertEqual(demand['veteran_cities'], len(veterans))
        self.assertEqual(demand['veteran_demand'],
                         sum(min(3, len(s['war_history'])) for s in veterans))
        self.assertEqual(demand['city_ceiling'], len(sites) + demand['veteran_demand'])
        self.assertLessEqual(len(self.world['humans']['fortresses']), demand['limit'])
        # And they expect the next war, which is what thickens their walls.
        reports = {c['city_uid']: c for c in self.world['threat_assessments']['cities']}
        for site in veterans:
            report = reports[site['uid']]
            self.assertEqual(report['wars_fought'], len(site['war_history']))
            self.assertGreater(report['war_pressure'], 0)
            self.assertGreaterEqual(report['regional_threat'], report['war_pressure'])


if __name__ == '__main__':
    unittest.main()
