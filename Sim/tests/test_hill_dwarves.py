import unittest
from icarus_sim.civilization_registry import load_registry,city_plan
from icarus_sim.terrain_civilizations import matches
from fantasy_world_generator.asset_list import compile_asset_list
class HillDwarfTests(unittest.TestCase):
    def test_identity_habitat_presets_and_asset_coverage(self):
        data=load_registry();hill=data['entities']['hill_dwarf']
        self.assertEqual(hill['parent_race_id'],'dwarf')
        self.assertEqual(data['entities']['elf']['population']['name'],'High Elf')
        rule=hill['settlement']['world_habitat']
        self.assertTrue(matches(rule,dict(biome=3,slope=4,temperature=18,moisture=.6)))
        self.assertFalse(matches(rule,dict(biome=5,slope=35,temperature=18,moisture=.6)))
        for tier in ('small_city','medium_city','capital_city'):
            self.assertTrue(any(b['structure_id']=='building.guildhall' for b in city_plan('hill_dwarf',tier)['buildings']))
        refs=[r for a in compile_asset_list()['assets'] if a['source']=='simulation.building_packs' for r in a['metadata']['references']]
        self.assertTrue(any('hill_dwarf' in r['civilization_ids'] for r in refs))
