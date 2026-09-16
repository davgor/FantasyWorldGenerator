import copy
import unittest
from unittest.mock import patch

from icarus_sim import civilization_registry as registry


class CityStaffingTests(unittest.TestCase):
    def test_every_city_has_one_core_guild_hall_with_two_service_staff(self):
        for entity_id in registry.load_registry()['entities']:
            for tier in registry.CITY_BLOCKS:
                halls = [row for row in registry.city_plan(entity_id, tier)['buildings']
                         if row['structure_id'] == 'building.guildhall']
                self.assertEqual(len(halls), 1, (entity_id, tier))
                hall = halls[0]
                self.assertEqual(hall['count'], 1)
                self.assertEqual(hall['priority'], 'core')
                self.assertEqual(hall['placement_conditions'], [])
                self.assertEqual({r['role'] for r in hall['staffing']['roles']}, {'cook', 'bartender'})
                self.assertEqual(hall['staffing_totals']['city_worker_beds'],
                                 {'minimum': 2, 'target': 2, 'maximum': 2})

    def test_all_structures_have_valid_staff_rosters(self):
        data = registry.load_registry()
        for library in data['structure_blocks'].values():
            for block in library['blocks']:
                for structure in block['structures']:
                    staff = structure['staffing']
                    self.assertEqual(staff['basis'], 'distinct_people_all_shifts')
                    for role in staff['roles']:
                        self.assertLessEqual(role['minimum'], role['target'])
                        self.assertLessEqual(role['target'], role['maximum'])
                    if structure['geometry_type'] == 'linear_segment':
                        self.assertEqual(staff['roles'], [])

    def test_quantities_and_conditional_staff_are_separate(self):
        plan = registry.city_plan('human_maritime', 'medium_city')
        summary = plan['staffing_summary']
        for level in ('minimum', 'target', 'maximum'):
            expected = sum(row['count'] * sum(role[level] for role in row['staffing']['roles']) for row in plan['buildings'])
            self.assertEqual(summary['all_configured']['workers'][level], expected)
            self.assertEqual(summary['unconditional']['workers'][level] + summary['conditional']['workers'][level], expected)
            self.assertEqual(summary['all_configured']['city_worker_beds'][level], expected)
        dock = next(row for row in plan['buildings'] if row['structure_id'] == 'building.dock')
        self.assertGreater(dock['staffing_totals']['workers']['target'], 0)
        self.assertGreater(summary['conditional']['workers']['target'], 0)
        self.assertIsNone(summary['total_residents'])
        self.assertIsNone(summary['houses_required'])

    def test_invalid_staffing_rejected(self):
        original = registry.load_registry()
        for bad in (-1, True, 1.5, 100001):
            data = copy.deepcopy(original)
            data['structure_blocks']['common']['blocks'][0]['structures'][0]['staffing']['roles'][0]['target'] = bad
            with self.assertRaises(ValueError): registry.validate_registry(data)
        data = copy.deepcopy(original)
        del data['structure_blocks']['common']['blocks'][0]['structures'][0]['staffing']
        with self.assertRaises(ValueError): registry.validate_registry(data)

    def test_hinterland_workers_do_not_require_city_beds(self):
        staff = {'basis':'distinct_people_all_shifts', 'housing_location':'hinterland',
                 'roles':[{'role':'farmer','minimum':2,'target':4,'maximum':6}],
                 'notes':'Resident farm workers.'}
        totals = registry.staffing_totals(staff, 3)
        self.assertEqual(totals['workers']['target'], 12)
        self.assertEqual(totals['city_worker_beds']['target'], 0)
        self.assertEqual(totals['hinterland_worker_beds']['target'], 12)

    def test_per_civilization_override_changes_only_selected_roster(self):
        data = registry.load_registry()
        row = data['entities']['gnome']['small_city']['buildings'][0]
        row['staffing'] = {'basis':'distinct_people_all_shifts','housing_location':'city',
            'roles':[{'role':'keeper','minimum':1,'target':5,'maximum':6}], 'notes':'Local roster.'}
        registry.validate_registry(data)
        with patch.object(registry, '_document', return_value=data):
            resolved = registry.city_plan('gnome', 'small_city')['buildings'][0]
            self.assertEqual(resolved['staffing_totals']['workers']['target'], 5 * row['count'])
        data['entities']['gnome']['small_city']['infrastructure'][0]['staffing'] = row['staffing']
        with self.assertRaises(ValueError): registry.validate_registry(data)
