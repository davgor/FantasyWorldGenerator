"""Local physical-metre sampling over a coarse globe, plus explicit micro relief."""
from dataclasses import dataclass, asdict
import math
from .terrain_errors import (cross_field, out_of_range, refused_by_world, unknown_field,
                             wrong_type)
from time import perf_counter
from .terrain_globe import perlin3, sample
from .terrain_tectonics import child_seed


@dataclass(frozen=True)
class PatchConfig:
    latitude: float = 0.
    longitude: float = 0.
    span: float = 64.
    spacing: float = .5
    detail_height: float = .4
    detail_scale: float = 8.

    def __post_init__(self):
        for key,value in asdict(self).items():
            if type(value) not in (float,int) or not math.isfinite(value):
                raise wrong_type('patch.'+key,value,{'type':'number'})
        if not -90<=self.latitude<=90:
            raise out_of_range('patch.latitude',self.latitude,
                               {'type':'number','min':-90,'max':90,'units':'degrees'})
        if not -180<=self.longitude<=180:
            raise out_of_range('patch.longitude',self.longitude,
                               {'type':'number','min':-180,'max':180,'units':'degrees'})
        if not 4<=self.span<=512:
            raise out_of_range('patch.span',self.span,
                               {'type':'number','min':4,'max':512,'units':'m'})
        if not .1<=self.spacing<=8:
            raise out_of_range('patch.spacing',self.spacing,
                               {'type':'number','min':.1,'max':8,'units':'m'})
        if math.ceil(self.span/self.spacing)>256:
            raise cross_field('A patch is at most 257 vertices per axis and span/spacing '
                              'asks for %d. Reduce span or increase spacing.'
                              %(math.ceil(self.span/self.spacing)+1),
                              ('span','spacing'))
        if not 0<=self.detail_height<=5:
            raise out_of_range('patch.detail_height',self.detail_height,
                               {'type':'number','min':0,'max':5,'units':'m'})
        if not .5<=self.detail_scale<=100:
            raise out_of_range('patch.detail_scale',self.detail_scale,
                               {'type':'number','min':.5,'max':100,'units':'m'})


def generate_patch(world,cfg):
    started=perf_counter()
    radius=world.get('effective_config',world['config'])['globe_radius']
    if cfg.span>radius*.5 or cfg.detail_height>radius*.01:
        raise refused_by_world('patch.span',cfg.span,
                               'A patch spans at most half this globe\'s radius (%g m) and '
                               'its detail at most a hundredth (%g m). This world has radius '
                               '%g m.'%(radius*.5,radius*.01,radius))
    lat=math.radians(cfg.latitude); lon=math.radians(cfg.longitude)
    center=(math.cos(lat)*math.cos(lon),math.sin(lat),math.cos(lat)*math.sin(lon))
    east=(-math.sin(lon),0.,math.cos(lon))
    north=(-math.sin(lat)*math.cos(lon),math.cos(lat),-math.sin(lat)*math.sin(lon))
    segments=math.ceil(cfg.span/cfg.spacing); step=cfg.span/segments
    from .terrain_detail import HeightField
    field=HeightField(world)
    canonical=bool(world.get('terrain_detail'))
    seed=child_seed(world['config']['seed'],'micro-relief')
    resolved=cfg.detail_scale>=2*step
    def elevation(p):
        base=sample(world['layers']['height'],p)
        detail=cfg.detail_height*perlin3(*(v*radius/cfg.detail_scale for v in p),seed) if resolved else 0.
        return (base,field.height(p)-base) if canonical else (base,detail)
    origin_height=sum(elevation(center))
    grids={key:[] for key in ('height','detail','local_x','local_y','local_z')}
    for z in range(segments+1):
        rows={key:[] for key in grids}
        v=z*step-cfg.span/2
        for x in range(segments+1):
            u=x*step-cfg.span/2; distance=math.hypot(u,v); theta=distance/radius
            tangent=tuple((u*e+v*n)/distance for e,n in zip(east,north)) if distance else east
            p=tuple(c*math.cos(theta)+t*math.sin(theta) for c,t in zip(center,tangent))
            base,detail=elevation(p); h=base+detail
            pos=tuple((radius+h)*q-(radius+origin_height)*c for q,c in zip(p,center))
            rows['height'].append(h); rows['detail'].append(detail)
            for key,axis in (('local_x',east),('local_y',center),('local_z',north)):
                rows[key].append(sum(a*b for a,b in zip(pos,axis)))
        for key in grids: grids[key].append(rows[key])
    indices=[]
    for z in range(segments):
        for x in range(segments):
            a=z*(segments+1)+x; b=a+segments+1
            indices.extend((a,b,a+1,a+1,b,b+1))
    return {'patch_version':2 if canonical else 1,'terrain_detail':world.get('terrain_detail'),'world_config':world['config'],'world_generator_version':world.get('generator_version'),
            'patch_config':asdict(cfg),'radius_m':radius,'size':segments+1,'spacing_m':step,
            'detail_seed':seed,'detail_resolved':True if canonical else resolved,'origin_height_m':origin_height,
            'triangle_indices':indices,'vertex_order':'row-major; flatten local_x/local_y/local_z; triangle normals face outward',
            'coordinates':'local tangent frame: x east, y up, z north; metres; origin on terrain at patch center',
            'warnings':(['Canonical world heights; legacy patch detail controls are ignored. Sample spacing changes mesh fidelity, not terrain.'] if canonical else [])+['Drainage is regional; protected water masks suppress local detail.',
                        'Spacing is on the reference sphere; elevated surface edge lengths differ slightly.'],
            'timing_ms':(perf_counter()-started)*1000,**grids}


def patch_request(body):
    """Validated loopback API payload; regenerate the exact submitted world config."""
    from .terrain_lab import Config, generate
    if not isinstance(body,dict):
        raise wrong_type('request',body,{'type':'object'})
    if set(body)!={'config','patch'}:
        # Unknown first: a caller who wrote `pathc` is also missing `patch`, and naming
        # the misspelling is the message that lets them fix it in one step.
        unknown=sorted(set(body)-{'config','patch'})
        if unknown:
            raise unknown_field(unknown[0],('config','patch'),noun='request field')
        raise cross_field('A patch request takes exactly config and patch; %s is missing.'
                          %' and '.join(sorted({'config','patch'}-set(body))),
                          ('config','patch'))
    if not isinstance(body['config'],dict):
        raise wrong_type('config',body['config'],{'type':'object'})
    if not isinstance(body['patch'],dict):
        raise wrong_type('patch',body['patch'],{'type':'object'})
    cfg=Config(**body['config']); patch=PatchConfig(**body['patch'])
    # This mirrors the world ceiling rather than setting one: the call regenerates the
    # exact submitted world before cutting a patch from it, so refusing a grid the
    # generator accepts would refuse a world that exists. The patch's own bounds (span,
    # spacing, 257 vertices per axis) are unchanged and are what actually limit a patch.
    # Regenerating a large world per request is the caller's cost; the lab keeps its own
    # interactive limit of 257 separately.
    if cfg.shape!='globe' or cfg.size>1025 or (cfg.tectonics and cfg.phase<2):
        raise cross_field('A patch is cut from a globe with elevation: shape must be globe, '
                          'size at most 1025, and phase at least 2 when tectonics run. This '
                          'config is shape %r, size %s, phase %s.'
                          %(cfg.shape,cfg.size,cfg.phase),('shape','size','phase'))
    return generate_patch(generate(cfg),patch)
