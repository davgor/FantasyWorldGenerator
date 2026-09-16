"""Canonical, position-addressed local relief and resolved engine-neutral tiles."""
import math
import hashlib
import json
from .terrain_globe import perlin3, sample
from .terrain_tectonics import child_seed

VERSION = 1


def attach_detail(world):
    world['terrain_detail'] = {
        'version': VERSION, 'seed': child_seed(world['config']['seed'], 'continuous-terrain-v1'),
        'bands': [{'scale_m': 120., 'amplitude_m': 12.},
                  {'scale_m': 28., 'amplitude_m': 2.5},
                  {'scale_m': 6., 'amplitude_m': .3}],
        'height_reference': 'radial metres above reference sphere; same datum as layers.height',
        'coordinates': 'unit direction (cos(lat)*cos(lon), sin(lat), cos(lat)*sin(lon))',
        'method': 'Coarse elevation plus continuous spherical Perlin bands; interpolated biome amplitude and water/river/flood protection. Resolved samples are authoritative; LOD never changes the height function.'}


class HeightField:
    def __init__(self, world):
        self.world=world
        self.radius=world.get('effective_config',world['config'])['globe_radius']
        self.base=world['layers']['height']
        self.definition=world.get('terrain_detail')
        if self.definition and self.definition.get('version')!=VERSION:
            raise ValueError('Unsupported terrain detail version')
        layers=world['layers'];n=len(self.base)
        def grid(key,default):return layers.get(key,[[default]*n for _ in range(n)])
        water=grid('water_type',0);river=grid('river',0);flood=grid('flood_risk',0)
        self.water=water
        self.sea=world.get('effective_config',world['config']).get('sea_level',0.)
        self.bands=[(b['scale_m'],b['amplitude_m'],child_seed(self.definition['seed'],str(i)))
                    for i,b in enumerate(self.definition['bands'])] if self.definition else []
        biome=grid('natural_biome',3)
        # Smooth masks use the same bilinear geography as the coarse elevation.
        self.strength=[[0. if water[z][x] else max(0.,1-min(1.,river[z][x]*2))*max(0.,1-min(1.,flood[z][x]))*
                        ({5:1.4,3:.8,4:1.,7:1.,15:.8}.get(biome[z][x],.65))
                        for x in range(n)] for z in range(n)]

    def height(self, direction):
        p=direction
        base=sample(self.base,p)
        if not self.definition:return base
        strength=sample(self.strength,p)
        # A zero plateau protects entire water cells and makes shores conservative.
        strength=max(0.,(strength-.15)/.85)
        coast=max(0.,min(1.,(base-self.sea)/20.))
        wet=max(0.,1-2*sample(self.water,p))
        strength*=coast*coast*(3-2*coast)*wet*wet
        if not strength:return base
        detail=sum(amplitude*perlin3(*(v*self.radius/scale for v in p),seed) for scale,amplitude,seed in self.bands)
        return base+strength*detail


def export_height_tile(world, level, x, z, cells=64):
    """Indexed latitude/longitude samples; shared indices yield identical heights."""
    if any(type(v) is not int for v in (level,x,z,cells)) or not 1<=level<=24 or not 1<=cells<=256:
        raise ValueError('Tile level 1..24, cells 1..256 and integer indices required')
    rows=2**level;cols=2*rows
    if not 0<=x<cols or not 0<=z<rows or x+cells>cols or z+cells>rows:
        raise ValueError('Tile lies outside global grid')
    field=HeightField(world)
    if not field.definition:raise ValueError('World has no canonical terrain detail; regenerate')
    def point(i,j):
        # Canonicalize seam and pole coordinates before evaluating noise.
        if j==0:return (0.,1.,0.)
        if j==rows:return (0.,-1.,0.)
        lat=math.pi*(.5-j/rows);lon=math.pi*(2*(i%cols)/cols-1)
        return (math.cos(lat)*math.cos(lon),math.sin(lat),math.cos(lat)*math.sin(lon))
    return {'schema':'fantasy-world-generator.height-tile','version':1,
            'source_sha256':hashlib.sha256(json.dumps({'base':field.base,'strength':field.strength,'water':field.water,
                'sea':field.sea,'radius':field.radius,'detail':field.definition},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
            'generator_version':world.get('generator_version'),'terrain_detail':field.definition,
            'level':level,'origin_index':[x,z],'size':cells+1,'global_cells':[cols,rows],
            'radius_m':field.radius,'angular_step_degrees':180/rows,
            'equatorial_spacing_m':math.pi*field.radius/rows,
            'coordinates':'row-major; latitude=90-180*(origin_z+row)/2^level; longitude=-180+180*(origin_x+column)/2^level; globe Cartesian=(radius_m+height_m)*unit_direction',
            'height_reference':field.definition['height_reference'],
            'heights_m':[[field.height(point(x+i,z+j)) for i in range(cells+1)] for j in range(cells+1)]}
