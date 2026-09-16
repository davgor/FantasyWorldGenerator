import copy
import unittest

from icarus_sim import city_shapes


class CityShapeTests(unittest.TestCase):
    def setUp(self):
        self.site={'buildable_area_m2':120000,'local_slope_degrees':3,'usable_land_fraction':.8}

    def test_catalogue_is_sourced_and_varied(self):
        data=city_shapes.load_catalogue()
        self.assertGreaterEqual(len(data['shapes']),16)
        for shape in data['shapes']:
            self.assertTrue(shape['history']['source_ids'])
            self.assertTrue(shape['history']['adaptation'])
            self.assertTrue(shape['layout']['housing_fill'])
            self.assertTrue(shape['variation'])

    def test_inland_never_gets_water_dependent_shapes(self):
        ids={r['id'] for r in city_shapes.rank_shapes(self.site)}
        self.assertNotIn('waterfront_comb',ids)
        self.assertNotIn('lagoon_network',ids)
        self.assertNotIn('river_meander',ids)
        self.assertIn('market_grid',ids)
        self.assertGreaterEqual(len(ids),3)

    def test_terrain_gates_and_safe_failure(self):
        site={**self.site,'river_access':True,'river_bend':True,'bridge_feasible':True}
        ids={r['id'] for r in city_shapes.rank_shapes(site)}
        self.assertIn('river_meander',ids)
        self.assertIn('bridge_twin',ids)
        self.assertIsNone(city_shapes.select_shape({**self.site,'usable_land_fraction':0},42,'a')['shape_id'])
        steep={**self.site,'local_slope_degrees':20,'ridge':True}
        ids={r['id'] for r in city_shapes.rank_shapes(steep)}
        self.assertIn('ridge_fishbone',ids)
        self.assertNotIn('market_grid',ids)

    def test_seeded_selection_and_local_variation(self):
        a=city_shapes.select_shape(self.site,42,'town_a')
        self.assertEqual(a,city_shapes.select_shape(dict(reversed(list(self.site.items()))),42,'town_a'))
        results=[city_shapes.select_shape(self.site,seed,'town_a') for seed in range(50)]
        self.assertGreaterEqual(len({r['shape_id'] for r in results}),3)
        self.assertGreater(len({str(r['parameters']) for r in results}),10)
        self.assertNotIn('planned_extension',{r['id'] for r in city_shapes.rank_shapes(self.site)})

    def test_repetition_penalty_preserves_eligibility(self):
        before={r['id']:r['weight'] for r in city_shapes.rank_shapes(self.site)}
        after={r['id']:r['weight'] for r in city_shapes.rank_shapes(self.site,nearby_counts={'market_grid':4})}
        self.assertEqual(set(before),set(after))
        self.assertLess(after['market_grid'],before['market_grid'])

    def test_invalid_inputs_and_broken_sources_rejected(self):
        with self.assertRaises(ValueError):city_shapes.rank_shapes({})
        with self.assertRaises(ValueError):city_shapes.rank_shapes({**self.site,'local_slope_degrees':float('nan')})
        with self.assertRaises(ValueError):city_shapes.rank_shapes({**self.site,'river_access':1})
        data=copy.deepcopy(city_shapes.load_catalogue())
        data['shapes'][0]['history']['source_ids']=['missing']
        with self.assertRaises(ValueError):city_shapes.validate_catalogue(data)
