import math
import unittest
from icarus_sim.terrain_detail import attach_detail, HeightField, export_height_tile


class DetailTests(unittest.TestCase):
    def world(self):
        w={'config':{'seed':42,'size':17},'effective_config':{'globe_radius':1774.4},
           'layers':{'height':[[50.]*17 for _ in range(17)],'natural_biome':[[3]*17 for _ in range(17)]}}
        attach_detail(w)
        return w

    def test_position_seed_and_real_relief(self):
        w=self.world();f=HeightField(w)
        values=[f.height((math.cos(a/1774.4),0,math.sin(a/1774.4))) for a in range(300)]
        self.assertGreater(max(values)-min(values),3)
        self.assertEqual(values,[HeightField(w).height((math.cos(a/1774.4),0,math.sin(a/1774.4))) for a in range(300)])
        w['config']['seed']=43;attach_detail(w)
        self.assertNotEqual(values[31],HeightField(w).height((math.cos(31/1774.4),0,math.sin(31/1774.4))))

    def test_adjacent_nested_tiles_and_wrap(self):
        w=self.world()
        a=export_height_tile(w,8,100,100,8)
        b=export_height_tile(w,8,108,100,8)
        self.assertEqual([r[-1] for r in a['heights_m']],[r[0] for r in b['heights_m']])
        fine=export_height_tile(w,9,200,200,16)
        self.assertEqual(a['heights_m'],[r[::2] for r in fine['heights_m'][::2]])
        west=export_height_tile(w,8,0,100,1)
        east=export_height_tile(w,8,511,100,1)
        self.assertEqual([r[0] for r in west['heights_m']],[r[-1] for r in east['heights_m']])

    def test_water_is_preserved(self):
        w=self.world();w['layers']['water_type']=[[1]*17 for _ in range(17)]
        f=HeightField(w)
        self.assertEqual(f.height((1,0,0)),50)
        w['layers']['water_type']=[[0]*17 for _ in range(17)]
        w['layers']['river']=[[1.]*17 for _ in range(17)]
        self.assertEqual(HeightField(w).height((1,0,0)),50)

    def test_patch_uses_shared_height(self):
        from icarus_sim.terrain_patch import generate_patch,PatchConfig
        w=self.world();p=generate_patch(w,PatchConfig(span=16,spacing=1))
        self.assertEqual(p['height'][8][8],HeightField(w).height((1,0,0)))
        self.assertEqual(p['patch_version'],2)

    def test_invalid_tile(self):
        for args in ((0,0,0,8),(8,-1,0,8),(8,0,255,8),(8,0,0,257)):
            with self.assertRaises(ValueError):export_height_tile(self.world(),*args)

    def test_city_surface_and_slopes_use_shared_field(self):
        from test_city_planner import fixture
        from icarus_sim.city_planner import _sampler,plan_city
        w=fixture();attach_detail(w)
        site=w['settlements']['sites'][0];sampler,_=_sampler(w,site,240)
        self.assertAlmostEqual(sampler(0,0)['height'],HeightField(w).height((1,0,0)))
        self.assertNotEqual(sampler(0,0)['slope'],2)
        plan=plan_city(w,site)
        self.assertTrue(plan['plots'])
        surf=plan['terrain']['surface'];mid=surf['size']//2
        self.assertAlmostEqual(surf['heights_m'][mid][mid],sampler(0,0)['height'],places=3)
        self.assertGreater(max(map(max,surf['heights_m']))-min(map(min,surf['heights_m'])),3)
