"""The war outlook (threat assessment 3) and the war_survival option.

The outlook is a forecast the wars module stands behind: the same pair pressure the next
age draws against. Survival is a world option that defaults to zero so every existing
seed replays byte for byte; above zero a defeated city may stand as a vassal.
"""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # the war test helpers live beside this file

from icarus_sim.terrain_wars import resolve_wars, war_outlook

from test_terrain_wars import city, core, flat_layers


def pair():
    angle = 200. / 1000.
    strong = city('strong', 'gnome', 'dwarf', 0, (1., 0., 0.), population=400)
    weak = city('weak', 'elf', 'elf', 1, (math.cos(angle), math.sin(angle), 0.), population=40)
    return strong, weak


class WarOutlookTests(unittest.TestCase):
    def test_outlook_reports_recent_wars_living_enemies_and_the_strongest_contention(self):
        strong, weak = pair()
        far = city('far', 'elf', 'elf', 2, (math.cos(2.), math.sin(2.), 0.))
        strong['war_history'] = [{'war_id': 'war-1-0', 'age': 1, 'kind': 'civil', 'outcome': 'victor', 'opponent_uid': 'gone'}]
        weak['war_history'] = [{'war_id': 'war-2-0', 'age': 2, 'kind': 'civil', 'outcome': 'defeated', 'opponent_uid': 'strong'}]
        outlook = war_outlook([strong, weak, far], [core(0), core(1), core(2)], [], radius=1000., spacing=450., age=2)
        self.assertEqual(outlook['strong']['wars_recent'], 0)
        self.assertEqual(outlook['weak']['wars_recent'], 1)
        self.assertFalse(outlook['strong']['enemy_living'], 'its opponent is a ruin')
        self.assertTrue(outlook['weak']['enemy_living'], 'strong still stands')
        self.assertGreater(outlook['strong']['war_risk'], 0.)
        self.assertEqual(outlook['strong']['war_risk_opponent_uid'], 'weak')
        self.assertEqual(outlook['weak']['war_risk_opponent_uid'], 'strong')
        self.assertEqual((outlook['far']['war_risk'], outlook['far']['war_risk_opponent_uid']), (0., None))
        self.assertEqual((outlook['strong']['war_hunger'], outlook['weak']['war_hunger']), (0., 0.), 'proximity has no direction')
        self.assertEqual(outlook, war_outlook([strong, weak, far], [core(0), core(1), core(2)], [], 1000., 450., 2))

    def test_a_hungry_city_carries_the_hunger_and_its_road_neighbour_the_risk(self):
        fed = city('fed', 'gnome', 'dwarf', 0, (1., 0., 0.), population=100)
        hungry = city('hungry', 'gnome', 'dwarf', 1, (math.cos(1.), math.sin(1.), 0.), population=100)
        routes = [{'from': 0, 'to': 1}]
        outlook = war_outlook([fed, hungry], [core(0, demand=10., supply=10.), core(1, demand=10., supply=2.)], routes, 1000., 450., 2)
        self.assertGreater(outlook['hungry']['war_hunger'], 0.)
        self.assertEqual(outlook['hungry']['war_hunger_target_uid'], 'fed')
        self.assertEqual(outlook['hungry']['war_risk'], 0.)
        self.assertGreater(outlook['fed']['war_risk'], 0.)
        self.assertEqual(outlook['fed']['war_risk_opponent_uid'], 'hungry')
        self.assertEqual(outlook['fed']['war_hunger'], 0.)


class WarSurvivalTests(unittest.TestCase):
    def test_zero_survival_changes_nothing(self):
        strong, weak = pair()
        plain = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(), 1000., 450., seed=42, age=1, rolls={'*': 0.})
        same = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(), 1000., 450., seed=42, age=1, rolls={'*': 0.}, survival=0.)
        self.assertEqual(plain, same)
        self.assertNotIn('outcome', plain[0][0])
        self.assertIn('weak', plain[1])

    def test_a_spared_loser_is_a_vassal_with_no_fate(self):
        strong, weak = pair()
        wars, fates = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(), 1000., 450., seed=42, age=1,
                                   rolls={'*': 0.}, survival=.5, survival_rolls={'*': .1})
        self.assertEqual(len(wars), 1)
        self.assertEqual((wars[0]['outcome'], wars[0]['survival_chance'], wars[0]['survival_roll']), ('vassalage', .5, .1))
        self.assertEqual(fates, {})
        wars, fates = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(), 1000., 450., seed=42, age=1,
                                   rolls={'*': 0.}, survival=.5, survival_rolls={'*': .9})
        self.assertEqual(wars[0]['outcome'], 'ruin')
        self.assertIn('weak', fates)

    def test_the_seeded_survival_draw_replays(self):
        strong, weak = pair()
        first = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(), 1000., 450., seed=42, age=1, rolls={'*': 0.}, survival=.5)
        second = resolve_wars([strong, weak], [core(0), core(1)], [], flat_layers(), 1000., 450., seed=42, age=1, rolls={'*': 0.}, survival=.5)
        self.assertEqual(first, second)
        self.assertIn(first[0][0]['outcome'], ('vassalage', 'ruin'))
        self.assertEqual(first[0][0]['survival_chance'], .5)


if __name__ == '__main__':
    unittest.main()
