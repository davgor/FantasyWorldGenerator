import unittest
from icarus_sim.world_debug import build_debug
from icarus_sim.terrain_society import make_sky
from icarus_sim.terrain_lab import Config


class DebugTests(unittest.TestCase):
    def test_diaspora_destroyed_is_not_counted_as_surviving(self):
        event={'status':'diaspora_founded','node':3,'population_profile':'human_cold','founding_year':1000,'diaspora':True}
        world={'config':{'size':17,'globe_radius':10000},'settlements':{'sites':[],'founding':{'events':[event]}},
               'ruins':[{'node':3,'population_profile':'human_cold','destroyed_age':1,'name':'Lost'}],
               'build_stages':[{'stage':10,'state':{'settlements':{'sites':[],'founding':{'events':[event]}}}}]}
        d=build_debug(world)
        self.assertEqual(d['diaspora']['founded'],1)
        self.assertEqual(d['diaspora']['surviving'],0)
        self.assertEqual(d['diaspora']['destroyed'],1)

    def test_sky_is_disabled_for_supported_recipe(self):
        self.assertEqual(make_sky({},Config(world_recipe=3,shape="globe",tectonics=1)),([],[],[]))

    def test_housing_diagnostics_explain_upgrades(self):
        from test_city_planner import fixture
        from icarus_sim.city_planner import plan_city
        w=fixture();p=plan_city(w,w['settlements']['sites'][0])
        self.assertTrue(p['debug']['housing_passes'])
        self.assertGreater(p['debug']['terrain_safe_cells'],0)
        self.assertEqual(p['debug']['apartment_policy'],'houses_first_then_upgrade_on_plot_exhaustion')

    def test_colleges_have_regional_separation(self):
        from icarus_sim.terrain_magic import college_spacing_m
        self.assertEqual(college_spacing_m(10000),1500)
        self.assertEqual(college_spacing_m(30000),4500)

    def test_warm_dry_climate_has_more_evaporation(self):
        from icarus_sim.terrain_climate import climate_wetness
        self.assertLess(climate_wetness(.02,30,3),climate_wetness(.02,0,3))
        self.assertAlmostEqual(climate_wetness(.02,30,0),.02/.045)

    def test_ley_alignment(self):
        from icarus_sim.terrain_leyline_history import network_geometry
        from icarus_sim.terrain_magic import arc_frame, distance_to_frame
        points,edges,meta=network_geometry(42,8)
        self.assertLess(distance_to_frame(points[2],arc_frame(points[0],points[1])),1e-7)
        self.assertEqual(meta['model'],'landscape_alignments')
