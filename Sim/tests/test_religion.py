"""The pantheon resolves from world state and changes nothing until summoned.

Hand-built worlds keep this independent of terrain_history wiring; the generated-world
checks (stage 13 presence, age re-evaluation) join once that file is free.
"""
import copy
import json
import unittest

from icarus_sim.terrain_religion import (catalogue, catalogue_identity, lint_catalogue, world_facts, rule_holds,
                                         resolve_gods, choose_cosmology, add_religion, gods_by_id)
from icarus_sim.terrain_astrology import almanac
from icarus_sim.terrain_leyline_history import SCHOOLS


def grid(value=0., n=3):
    return [[value] * n for _ in range(n)]


def network(intensities, instability=.2):
    return {'nodes': [{'id': f'n{i}', 'direction': [1, 0, 0], 'intensity': v} for i, v in enumerate(intensities)],
            'edges': [], 'instability': instability, 'strength': .7}


def small_world(**overrides):
    world = {
        'config': {'seed': 42},
        'effective_config': {'globe_radius': 1000.},
        'magic': {'enabled': True, 'networks': {s: network([]) for s in SCHOOLS}},
        'layers': {'ley_' + s: grid() for s in SCHOOLS},
        'settlements': {'sites': [{'id': 0, 'uid': 'c1', 'population_profile': 'human_maritime', 'x': 1, 'z': 1,
                                   'direction': [1, 0, 0], 'city_class': 'capital'}],
                        'founding': {'used_civilizations': ['human_maritime'], 'events': []}},
        'water': {'ocean_km2': 60., 'lake_km2': 0., 'dry_km2': 40.},
        'beast_nests': {'sites': [{'id': 'n1', 'name': 'Cinder dragons', 'family': 'draconic', 'real': False,
                                   'direction': [1, 0, 0], 'layer': 'surface', 'tier': 4, 'spacing_m': 300.}]},
        'ruins': [], 'history': {'ages': []}, 'sky': {'settlements': []},
        'recipe': {'resolved': {'lunar_influence': .5}},
    }
    world['magic']['networks']['weave'] = network([1.4, 1.5])
    world['magic']['networks']['water'] = network([.5, .6])
    world['layers']['ley_water'][1][1] = .8
    world['lunar_almanac'] = {'version': 1, **almanac({'periods': {'synodic': 30, 'spin': 40, 'nod': 20},
                                                       'offsets': {'synodic': 0, 'spin': 0, 'nod': 5},
                                                       'tilt_max_degrees': 30., 'great_year_days': 120}, 0)}
    world.update(overrides)
    return world


def status(world, god_id):
    return next(g for g in world['religion']['gods'] if g['id'] == god_id)


class CatalogueTests(unittest.TestCase):
    def test_catalogue_is_well_formed_and_identified(self):
        self.assertTrue(lint_catalogue())
        identity = catalogue_identity()
        self.assertEqual(identity['revision'], catalogue()['revision'])
        self.assertEqual(len(identity['sha256']), 64)
        self.assertEqual(len(catalogue()['gods']), 25)
        self.assertEqual(len(catalogue()['cosmologies']), 11)

    def test_rule_interpreter(self):
        facts = world_facts(small_world())
        self.assertTrue(facts['schools']['weave'] and not facts['schools']['fire'])
        self.assertEqual(facts['races'], ['human'])
        self.assertAlmostEqual(facts['ocean_share'], .6)
        self.assertEqual(facts['dragons'], 1)
        self.assertTrue(rule_holds({'kind': 'dragon'}, facts))
        self.assertFalse(rule_holds({'kind': 'sky'}, facts))
        self.assertTrue(rule_holds({'kind': 'any', 'rules': [{'kind': 'sky'}, {'kind': 'ocean_share', 'min': .5}]}, facts))
        self.assertFalse(rule_holds({'kind': 'gods', 'ids': ['god_fire']}, facts, frozenset({'god_weave'})))
        self.assertTrue(rule_holds({'kind': 'gods', 'ids': ['god_weave', 'god_fire'], 'all': False}, facts, frozenset({'god_weave'})))
        with self.assertRaises(ValueError):
            rule_holds({'kind': 'comet'}, facts)


class ResolutionTests(unittest.TestCase):
    def test_existence_follows_the_world_and_is_deterministic(self):
        a = add_religion(small_world()); b = add_religion(small_world())
        self.assertEqual(a['religion'], b['religion'])
        json.dumps(a['religion'], allow_nan=False)
        expected = {'god_weave': 'manifest', 'god_water': 'manifest', 'god_fire': 'absent', 'god_great_wyrm': 'manifest',
                    'god_sky_court': 'absent', 'god_first_hearth': 'manifest', 'god_elder_star': 'absent',
                    'god_drowned_mother': 'manifest', 'god_turning_moon': 'manifest', 'god_hearth_harvest': 'manifest',
                    'god_fallen_cities': 'absent', 'god_wanderer': 'absent'}
        for god_id, state in expected.items():
            self.assertEqual(status(a, god_id)['status'], state, god_id)
        self.assertEqual(status(a, 'god_weave')['aspect'], 'wild', 'mean 1.45 * 1.2 sits above the midpoint')
        self.assertEqual(status(a, 'god_water')['aspect'], 'sovereign')
        self.assertEqual(status(a, 'god_turning_moon')['aspect'], 'sovereign')
        self.assertEqual(status(a, 'god_hearth_harvest')['saint_of'], None, 'earth is absent, so nothing to fold into')
        self.assertIsNone(status(a, 'god_fire')['aspect'])

    def test_removing_the_dragon_removes_the_wyrm_and_nothing_else(self):
        with_dragon = add_religion(small_world())
        without = add_religion(small_world(beast_nests={'sites': []}))
        changed = {g['id'] for g, h in zip(with_dragon['religion']['gods'], without['religion']['gods']) if g['status'] != h['status']}
        self.assertEqual(changed, {'god_great_wyrm'})
        self.assertEqual(status(without, 'god_great_wyrm')['status'], 'absent')

    def test_a_god_that_stops_qualifying_sleeps_with_its_last_aspect(self):
        world = add_religion(small_world())
        self.assertEqual(status(world, 'god_weave')['aspect'], 'wild')
        world['magic']['networks']['weave'] = network([])
        add_religion(world)
        god = status(world, 'god_weave')
        self.assertEqual((god['status'], god['aspect']), ('sleeping', 'wild'))
        self.assertNotIn('god_weave', world['religion']['faiths']['human_maritime']['gods'])

    def test_cosmology_is_drawn_from_eligible_templates_only(self):
        world = add_religion(small_world())
        cosmology = world['religion']['cosmology']
        eligible = {c['id'] for c in cosmology['eligible']}
        self.assertIn(cosmology['id'], eligible)
        self.assertIn('cos_mosaic', eligible)
        self.assertIn('cos_wyrm_thrones', eligible)
        self.assertIn('cos_sea_and_sky', eligible)
        self.assertNotIn('cos_elemental_court', eligible)
        self.assertNotIn('cos_dual_dawn', eligible)
        facts = world_facts(world)
        seeds = {choose_cosmology(facts, frozenset(g['id'] for g in world['religion']['gods'] if g['status'] == 'manifest'), s)['id'] for s in range(30)}
        self.assertGreater(len(seeds), 1, 'the seed decides among eligible templates')

    def test_faith_patron_gods_fear_and_feasts(self):
        world = add_religion(small_world())
        faith = world['religion']['faiths']['human_maritime']
        self.assertEqual(faith['patron'], 'god_first_hearth')
        self.assertEqual(faith['names']['god_first_hearth'], 'Harbour-Mother')
        manifest = {g['id'] for g in world['religion']['gods'] if g['status'] == 'manifest'}
        self.assertTrue(set(faith['gods']) <= manifest)
        self.assertLessEqual(len(faith['gods']), 4)
        self.assertEqual([f['god_id'] for f in faith['fear']], ['god_great_wyrm'])
        events = world['lunar_almanac']['events']
        for god_id, days in faith['feasts']['surges'].items():
            school = gods_by_id()[god_id]['exists']['school']
            self.assertEqual(days, [e['day'] for e in events if e['kind'] == 'surge' and e['school'] == school])
        self.assertEqual(faith['feasts']['hollow_nights']['kept_as'], 'dread')
        self.assertEqual(faith['sects'], [])

    def test_schism_founding_makes_one_sect(self):
        world = small_world()
        world['settlements']['founding']['events'].append({'status': 'diaspora_founded', 'diaspora_reason': 'religious_schism',
                                                           'population_profile': 'human_maritime', 'node': 4, 'founding_year': 1000})
        add_religion(world)
        sects = world['religion']['faiths']['human_maritime']['sects']
        self.assertEqual(len(sects), 1)
        self.assertEqual(sects[0]['rival'], 'god_first_hearth')
        self.assertNotEqual(sects[0]['patron'], 'god_first_hearth')
        self.assertTrue(sects[0]['epithet'].endswith('of the Schism'))

    def test_magic_disabled_world_still_has_a_pantheon(self):
        world = small_world()
        world['magic'] = {'enabled': False, 'networks': {s: network([]) for s in SCHOOLS}}
        add_religion(world)
        gods = world['religion']['gods']
        self.assertEqual([g['id'] for g in gods if g['family'] == 'civic' and g['status'] == 'manifest'],
                         ['god_hearth_harvest', 'god_forge_craft', 'god_road_market', 'god_crown_law', 'god_grave_memory', 'god_fortune_fate', 'god_red_field'])
        self.assertTrue(all(g['status'] == 'absent' for g in gods if g['family'] == 'school'))
        self.assertEqual(status(world, 'god_turning_moon')['status'], 'manifest')
        eligible = {c['id'] for c in world['religion']['cosmology']['eligible']}
        self.assertIn('cos_one_sun', eligible)
        self.assertNotIn('cos_turning_moon', eligible)
        self.assertNotIn('cos_the_woven', eligible)

    def test_sites_follow_ruins_and_the_moon(self):
        world = small_world()
        world['ruins'] = [{'id': 'ruin-a', 'node': 3, 'cause': 'self_magic', 'destroyed_age': 1, 'population_profile': 'human_maritime'},
                          {'id': 'ruin-b', 'node': 5, 'cause': 'war_civil', 'destroyed_age': 1, 'population_profile': 'human_maritime'}]
        world['history'] = {'ages': [{'age': 1, 'wars': [{}], 'moon': {'tide': {'weave': 1.5}}}]}
        add_religion(world)
        sites = {s['id']: s for s in world['religion']['sites']}
        self.assertTrue(sites['cult-ruin-a']['born_under_surge'])
        self.assertEqual(sites['shrine-ruin-b']['god_id'], 'god_red_field')
        self.assertEqual(status(world, 'god_fallen_cities')['status'], 'manifest')
        self.assertEqual(world['religion']['facts']['wars'], 1)

    def test_religion_never_touches_the_world(self):
        world = small_world()
        before = copy.deepcopy(world)
        add_religion(world)
        world.pop('religion')
        self.assertEqual(world, before)


if __name__ == '__main__':
    unittest.main()
