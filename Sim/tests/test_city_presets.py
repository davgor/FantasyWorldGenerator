import copy
import unittest

from icarus_sim import civilization_registry as registry


class CityPresetTests(unittest.TestCase):
    def test_every_entity_has_complete_measured_size_blocks(self):
        data = registry.load_registry()
        for key, entity in data['entities'].items():
            totals = []
            for tier in ('small_city', 'medium_city', 'capital_city'):
                self.assertIn(tier, entity)
                plan = registry.city_plan(key, tier)
                self.assertEqual(plan['unit'], 'metres')
                self.assertFalse(plan['runtime_placement_enabled'])
                self.assertTrue(plan['buildings'])
                totals.append(sum(row['count'] for row in plan['buildings']))
                for row in plan['buildings']:
                    self.assertGreater(row['plot_m']['width'], 0)
                    self.assertGreater(row['plot_m']['depth'], 0)
                    self.assertNotEqual(row['module_family'], 'housing')
                    self.assertNotEqual(row['geometry_type'], 'linear_segment')
                    self.assertTrue(row['requirements'])
            self.assertLess(totals[0], totals[1])
            self.assertLess(totals[1], totals[2])

    def test_culture_and_tier_choices(self):
        def ids(key, tier):
            return {r['structure_id'] for r in registry.city_plan(key, tier)['buildings']}
        self.assertIn('building.dock', ids('human_maritime', 'small_city'))
        self.assertIn('building.cistern', ids('human_desert', 'small_city'))
        self.assertIn('building.smelter', ids('dwarf', 'medium_city'))
        self.assertNotIn('building.keep', ids('human_heartland', 'small_city'))
        self.assertIn('building.keep', ids('human_heartland', 'capital_city'))
        plan = registry.city_plan('human_maritime', 'small_city')
        dock = next(r for r in plan['buildings'] if r['structure_id'] == 'building.dock')
        self.assertEqual(dock['placement_conditions'], ['navigable_shore'])

    def test_bad_counts_references_and_missing_blocks_rejected(self):
        source = registry.load_registry()
        for count in (0, -1, True, 1.5, 10001):
            data = copy.deepcopy(source)
            data['entities']['gnome']['small_city']['buildings'][0]['count'] = count
            with self.assertRaises(ValueError): registry.validate_registry(data)
        data = copy.deepcopy(source)
        del data['entities']['gnome']['capital_city']
        with self.assertRaises(ValueError): registry.validate_registry(data)
        data = copy.deepcopy(source)
        data['entities']['gnome']['small_city']['buildings'][0]['structure_id'] = 'missing'
        with self.assertRaises(ValueError): registry.validate_registry(data)
        data = copy.deepcopy(source)
        data['entities']['gnome']['small_city']['buildings'][0]['placement_conditions'] = ['unknown_condition']
        with self.assertRaises(ValueError): registry.validate_registry(data)
        data = copy.deepcopy(source)
        data['structure_blocks']['common']['blocks'][0]['structures'][0]['plot_m']['width'] = 1
        with self.assertRaises(ValueError): registry.validate_registry(data)

    def test_resolved_plan_is_independent_copy(self):
        plan = registry.city_plan('elf', 'small_city')
        plan['buildings'][0]['plot_m']['width'] = -1
        self.assertGreater(registry.city_plan('elf', 'small_city')['buildings'][0]['plot_m']['width'], 0)
