"""Verify renderer geometry in Node without depending on a GPU or browser."""
import shutil
import subprocess
import unittest
from pathlib import Path


class CityViewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_biome_fill_survives_magic_outline(self):
        script=r"""
const assert=require('node:assert/strict');
const {terrainColor,magicColor}=require('./tools/city_view_3d.js');
const p={terrain:{natural_biome:[[3]],biome_variant:[[0]],biome_catalogue:[{id:3,color:[100,150,70]}],magical_catalogue:[{magic_school:'fire'}],magic_colors:{fire:[207,86,37]},codes:[[0]]}};
assert.deepEqual(terrainColor(p,0,0),[100,150,70]);
assert.deepEqual(magicColor(p,0,0),[207,86,37]);
"""
        subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)

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

    @unittest.skipUnless(shutil.which('node'), 'Node is required for wall segment geometry')
    def test_wall_segments_follow_the_curtain_instead_of_spiking_off_it(self):
        script=r"""
const assert=require('node:assert/strict');
const {geometry,wallSegments,segmentPlot,boxVertices}=require('./tools/city_view_3d.js');
const seg={from_m:[0,0],to_m:[40,0],thickness_m:3,height_m:8};
const plot=segmentPlot(seg);
assert.equal(plot.dimensions_m.width,3);
assert.equal(plot.dimensions_m.depth,40);
const v=boxVertices({...plot,ground_elevation_m:0},0,0,8);
const xs=v.map(p=>p[0]), zs=v.map(p=>p[2]);
assert.ok(Math.max(...xs)-Math.min(...xs)>35, 'curtain length must run along from_m→to_m');
assert.ok(Math.max(...zs)-Math.min(...zs)<4, 'thickness must not become a giant sideways spike');
const city={bounds_m:[-20,-20,20,20],roads:[],fortifications:{segments:[seg]},
 terrain:{cell_m:4,size:1,codes:[[0]],surface:{size:2,step_m:40,heights_m:[[100,100],[100,100]]}}};
const castle={bounds_m:[-20,-20,20,20],roads:[],wall_networks:[{status:'closed',segments:[seg]}],
 terrain:{cell_m:4,size:1,codes:[[0]],surface:{size:2,step_m:40,heights_m:[[100,100],[100,100]]}}};
assert.equal(wallSegments(city).length,1);
assert.equal(wallSegments(castle).length,1);
const bare=geometry({bounds_m:[-20,-20,20,20],roads:[],terrain:{cell_m:4,size:1,codes:[[0]],
 surface:{size:2,step_m:40,heights_m:[[100,100],[100,100]]}}},[]);
const withWalls=geometry(castle,[]);
assert.equal(withWalls.wall_segment_count,1);
assert.ok(withWalls.positions.length>bare.positions.length);
assert.equal((withWalls.positions.length-bare.positions.length)/3,36);
assert.ok([...withWalls.positions,...withWalls.colors].every(Number.isFinite));
"""
        subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)
