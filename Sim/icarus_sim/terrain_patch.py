"""Local physical-metre sampling over a coarse globe, plus explicit micro relief."""
from dataclasses import dataclass, asdict
import math
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
                raise ValueError(f'{key} must be a finite number')
        if not -90<=self.latitude<=90 or not -180<=self.longitude<=180:
            raise ValueError('Invalid patch latitude/longitude')
        if not 4<=self.span<=512 or not .1<=self.spacing<=8:
            raise ValueError('Patch span is 4..512 m; spacing is 0.1..8 m')
        if math.ceil(self.span/self.spacing)>256:
            raise ValueError('Patch limited to 257 vertices per axis; reduce span or increase spacing')
        if not 0<=self.detail_height<=5 or not .5<=self.detail_scale<=100:
            raise ValueError('Detail height is 0..5 m; detail scale is 0.5..100 m')


def generate_patch(world,cfg):
    started=perf_counter()
    radius=world.get('effective_config',world['config'])['globe_radius']
    if cfg.span>radius*.5 or cfg.detail_height>radius*.01:
        raise ValueError('Patch extent/detail is too large relative to this globe')
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
    if not isinstance(body,dict) or set(body)!={'config','patch'}:
        raise ValueError('Patch request requires config and patch objects')
    if not isinstance(body['config'],dict) or not isinstance(body['patch'],dict):
        raise ValueError('config and patch must be objects')
    cfg=Config(**body['config']); patch=PatchConfig(**body['patch'])
    if cfg.shape!='globe' or cfg.size>257 or (cfg.tectonics and cfg.phase<2):
        raise ValueError('Generate a globe with elevation first; world grid limit is 257')
    return generate_patch(generate(cfg),patch)
