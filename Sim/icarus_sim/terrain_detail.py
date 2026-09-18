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
        self.n=len(self.base)
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

    def _cell(self, p):
        """The index arithmetic terrain_globe.sample performs, computed once.

        height() interpolates three grids of identical shape at the same
        direction, so the two inverse trigonometric calls and the clamping were
        being repeated for each of them.
        """
        n=self.n
        x=((math.atan2(p[2],p[0])+math.pi)/(2*math.pi)*(n-1))%(n-1)
        z=(math.pi/2-math.asin(max(-1,min(1,p[1]))))/math.pi*(n-1)
        z=max(0,min(n-1,z))
        ix,iz=int(x),int(z)
        return ix,iz,min(n-1,iz+1),x-ix,z-iz

    @staticmethod
    def _at(h,ix,iz,jz,fx,fz):
        return ((1-fx)*h[iz][ix]+fx*h[iz][ix+1])*(1-fz)+((1-fx)*h[jz][ix]+fx*h[jz][ix+1])*fz

    def height(self, direction):
        p=direction
        if not self.definition:return sample(self.base,p)
        ix,iz,jz,fx,fz=self._cell(p)
        base=self._at(self.base,ix,iz,jz,fx,fz)
        # Each factor below can independently zero the detail, and the result is
        # `base` whenever it does. Testing them as they are computed skips the
        # remaining grid samples for water, shoreline and protected cells instead
        # of multiplying by zero after paying for all of them.
        coast=max(0.,min(1.,(base-self.sea)/20.))
        if not coast:return base
        strength=self._at(self.strength,ix,iz,jz,fx,fz)
        # A zero plateau protects entire water cells and makes shores conservative.
        strength=max(0.,(strength-.15)/.85)
        if not strength:return base
        wet=max(0.,1-2*self._at(self.water,ix,iz,jz,fx,fz))
        strength*=coast*coast*(3-2*coast)*wet*wet
        if not strength:return base
        radius=self.radius;p0,p1,p2=p
        detail=sum(amplitude*perlin3(p0*radius/scale,p1*radius/scale,p2*radius/scale,seed)
                   for scale,amplitude,seed in self.bands)
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
