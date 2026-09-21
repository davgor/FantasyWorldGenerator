import math
import unittest
from icarus_sim.terrain_patch import generate_patch, PatchConfig


class PatchTests(unittest.TestCase):
    def world(self):
        return {'config':{'seed':42},'effective_config':{'globe_radius':1774.4},
                'layers':{'height':[[10.]*9 for _ in range(9)]}}

    def test_physical_spacing_curvature_and_no_detail(self):
        result=generate_patch(self.world(),PatchConfig(span=32,spacing=1,detail_height=0))
        self.assertEqual(result['size'],33)
        self.assertEqual(result['spacing_m'],1)
        self.assertEqual(result['height'][16][16],10)
        self.assertLess(result['local_y'][0][16],result['local_y'][16][16])
        self.assertAlmostEqual(result['local_y'][16][16],0)
        self.assertTrue(all(v==0 for row in result['detail'] for v in row))
        self.assertEqual(len(result['triangle_indices']),32*32*6)
        a,b,c=result['triangle_indices'][:3]
        def vertex(i):
            z,x=divmod(i,33)
            return [result[k][z][x] for k in ('local_x','local_y','local_z')]
        va,vb,vc=map(vertex,(a,b,c))
        ab=[v-u for u,v in zip(va,vb)]; ac=[v-u for u,v in zip(va,vc)]
        self.assertGreater(ab[2]*ac[0]-ab[0]*ac[2],0)

    def test_nested_resolution_samples_same_world_detail(self):
        a=generate_patch(self.world(),PatchConfig(span=32,spacing=1))
        b=generate_patch(self.world(),PatchConfig(span=32,spacing=.5))
        for z,row in enumerate(a['height']):
            for x,v in enumerate(row):
                self.assertAlmostEqual(v,b['height'][z*2][x*2])
        self.assertGreater(max(v for row in a['detail'] for v in row)-min(v for row in a['detail'] for v in row),.01)

    def test_poles_and_longitude_wrap(self):
        a=generate_patch(self.world(),PatchConfig(latitude=90,longitude=-180,span=16))
        b=generate_patch(self.world(),PatchConfig(latitude=90,longitude=180,span=16))
        for ra,rb in zip(a['height'],b['height']):
            for va,vb in zip(ra,rb): self.assertAlmostEqual(va,vb)
        self.assertTrue(all(math.isfinite(v) for row in a['local_y'] for v in row))

    def test_invalid_or_excessive_patch(self):
        for kwargs in ({'span':1000,'spacing':.1},{'latitude':91},{'spacing':0},
                       {'detail_height':-1},{'detail_scale':float('nan')},{'span':float('inf')}):
            with self.assertRaises(ValueError): PatchConfig(**kwargs)

    def test_unresolved_detail_is_omitted_and_seed_changes_detail(self):
        a=generate_patch(self.world(),PatchConfig(span=16,spacing=2,detail_scale=1))
        self.assertFalse(a['detail_resolved'])
        self.assertTrue(all(v==0 for row in a['detail'] for v in row))
        cfg=PatchConfig(span=16)
        first=generate_patch(self.world(),cfg)
        world=self.world(); world['config']['seed']=43
        second=generate_patch(world,cfg)
        self.assertNotEqual(first['detail'],second['detail'])

    def test_request_rejects_invalid_world_before_sampling(self):
        from icarus_sim.terrain_patch import patch_request
        from icarus_sim.terrain_world import registry
        # Derived, not written out: the sentinel is one step past the declared ceiling, so it
        # follows the bound if the bound moves. A literal here silently stops testing the
        # rejection the day the registry changes -- SDET-CEILING-SENTINELS.
        over_ceiling=registry(3)['size']['max']+1
        for body in ([],{}, {'config':[], 'patch':{}}, {'config':{'shape':'plane'},'patch':{}},
                     {'config':{'shape':'globe','size':over_ceiling},'patch':{}}):
            with self.assertRaises(ValueError): patch_request(body)
