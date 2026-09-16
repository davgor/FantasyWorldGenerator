"""Verify renderer geometry in Node without depending on a GPU or browser."""
import shutil
import subprocess
import unittest
from pathlib import Path


class CityViewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for renderer geometry checks')
    def test_true_scale_rotated_box_and_interpolated_terrain(self):
        script=r"""
const assert=require('node:assert/strict');
const {boxVertices,heightAt,geometry}=require('./tools/city_view_3d.js');
const b={x_m:10,z_m:20,rotation_degrees:37,ground_elevation_m:105,foundation_bottom_m:100,
 dimensions_m:{width:8,depth:10,height:12},kind:'housing'};
const v=boxVertices(b,100);
const dist=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));
assert.ok(Math.abs(dist(v[0],v[1])-8)<1e-10);
assert.ok(Math.abs(dist(v[1],v[2])-10)<1e-10);
assert.equal(dist(v[0],v[4]),12);
assert.equal(v[0][1],5);
const p={bounds_m:[0,0,4,4],roads:[],terrain:{cell_m:4,size:1,codes:[[0]],
 surface:{size:2,step_m:4,heights_m:[[100,104],[108,112]]}}};
assert.equal(heightAt(p,2,2),106);
const mesh=geometry(p,[b]);
assert.equal(mesh.positions.length,mesh.colors.length);
assert.ok([...mesh.positions,...mesh.colors].every(Number.isFinite));
assert.equal(mesh.positions.length/3,6+36+36); // ground, foundation, measured building
"""
        subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)
