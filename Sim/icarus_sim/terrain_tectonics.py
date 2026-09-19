"""Inspectable static tectonic stages; a game model, not geodynamics."""
from dataclasses import asdict
import hashlib
import math
import random
from time import perf_counter
from .terrain_globe import direction, perlin3, measure_globe


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def unit(p):
    norm=math.sqrt(dot(p,p))
    return tuple(v/norm for v in p)


def child_seed(master,domain,variation=0):
    return int.from_bytes(hashlib.sha256(f'tectonics-v1:{master}:{domain}:{variation}'.encode()).digest()[:4],'big')


def make_plates(seed,count):
    rng=random.Random(seed)
    plates=[]
    cutoff=math.cos(.55*math.sqrt(4*math.pi/count))
    for _ in range(count*1000):
        center=unit(tuple(rng.gauss(0,1) for _ in range(3)))
        if any(dot(center,p['center'])>cutoff for p in plates):
            continue
        axis=unit(tuple(rng.gauss(0,1) for _ in range(3)))
        speed=rng.uniform(.25,1)
        plates.append({'id':len(plates),'center':center,'omega':tuple(v*speed for v in axis)})
        if len(plates)==count:
            return plates
    raise ValueError('Could not distribute plate centers')


def relative_motion(p,normal,omega_i,omega_j):
    vi,vj=cross(omega_i,p),cross(omega_j,p)
    relative=tuple(b-a for a,b in zip(vi,vj))
    opening=dot(relative,normal)
    shear=math.sqrt(max(0,dot(relative,relative)-opening*opening))
    return min(1,max(0,-opening/2)),min(1,max(0,opening/2)),min(1,shear/2)


def crust(p,seed,bias):
    # Continental affinity independent of plate identity: plates can contain both.
    v=.5+1.65*perlin3(p[0]*1.4+.17,p[1]*1.4+.39,p[2]*1.4+.71,seed)+bias*.5
    v=max(0,min(1,v))
    return v*v*(3-2*v)


def continental_profile(c):
    anchors=((0,-1.8),(.3,-1.65),(.45,-.12),(.6,.08),(1,.3))
    for (a,ha),(b,hb) in zip(anchors,anchors[1:]):
        if c<=b:
            t=max(0,min(1,(c-a)/(b-a)))
            return ha+(hb-ha)*t*t*(3-2*t)
    return anchors[-1][1]


def mountain_modulation(along,across,strength):
    # Elongated cross-belt ridges with peaks/passes varying along their length.
    ridge=.5+.5*math.cos(9*across+.6*math.sin(3*along))
    peaks=.7+.3*(.5+.5*math.sin(5*along+.4))
    shaped=.35+.65*ridge*peaks
    return 1-strength+strength*shaped


def layout_point(p,plates,crust_seed,cfg):
    # Compact, continuous memberships keep distant great-circle extensions out.
    ordered=sorted(plates,key=lambda plate:plate['id'])
    scores=[dot(p,plate['center']) for plate in ordered]; best=max(scores)
    support=2*cfg.belt_width
    weights=[max(0,1-(best-score)/support)**3 for score in scores]
    c=crust(p,crust_seed,cfg.crust_bias)
    contributions=[]
    for i,left in enumerate(ordered):
        if not weights[i]: continue
        for j in range(i+1,len(ordered)):
            if not weights[j]: continue
            right=ordered[j]
            normal=unit(tuple(b-a for a,b in zip(left['center'],right['center'])))
            projection=max(-1,min(1,dot(p,normal)))
            raw=tuple(v-projection*q for v,q in zip(p,normal))
            if dot(raw,raw)<1e-20: continue
            boundary=unit(raw)
            cv,dv,sh=relative_motion(boundary,normal,left['omega'],right['omega'])
            angle=cfg.belt_width
            ci=crust(tuple(v*math.cos(angle)-q*math.sin(angle) for v,q in zip(boundary,normal)),crust_seed,cfg.crust_bias)
            cj=crust(tuple(v*math.cos(angle)+q*math.sin(angle) for v,q in zip(boundary,normal)),crust_seed,cfg.crust_bias)
            reference=unit(tuple(a+b for a,b in zip(left['center'],right['center'])))
            along=math.atan2(dot(boundary,cross(normal,reference)),dot(boundary,reference))
            across=math.asin(projection)/angle
            distance=abs(across)*angle*cfg.globe_radius
            # Smoothly choose crust on this side, including across the boundary.
            side=.5+.5*math.tanh(across*3)
            here=ci*(1-side)+cj*side; there=cj*(1-side)+ci*side
            values=relief_at(c,distance,cv,dv,here,there,cfg,along,across)
            contributions.append((weights[i]*weights[j],distance,cv,dv,sh,*values))
    total=sum(v[0] for v in contributions)
    # A baseline weight fades isolated pair tails to zero without a hard cutoff.
    denominator=max(1.,total)
    blended=[sum(v[0]*v[k] for v in contributions)/denominator for k in range(2,8)]
    cv,dv,sh,unused,interaction,volcanic=blended
    owner_index=max(range(len(scores)),key=lambda i:scores[i])
    owner=ordered[owner_index]['id']
    # Distance to the nearest half-space edge of the owning Voronoi cell.
    # Independent of the compact blend support, so candidates fading out do not jump it.
    center=ordered[owner_index]['center']
    normals=[unit(tuple(b-a for a,b in zip(center,plate['center'])))
             for plate in ordered if plate['id']!=owner]
    distance=min(abs(math.asin(max(-1,min(1,dot(p,normal))))) for normal in normals)*cfg.globe_radius
    return owner,c,distance,cv,dv,sh,c,c,0.,0.,cfg.tectonic_relief*continental_profile(c)+interaction,interaction,volcanic


def relief_at(c,distance,conv,div,ci,cj,cfg,along=0,across=0):
    width=cfg.belt_width*cfg.globe_radius
    d=distance/width
    belt=math.exp(-d*d)
    collision=conv*ci*cj
    subduction=conv*(1-ci*cj)
    # The more continental side overrides. Equal crust is a simplified tie.
    overriding=.5+.5*math.tanh(8*(ci-cj))
    abundance=1.
    if cfg.world_recipe:
        from .terrain_world import options
        abundance=options(cfg)['mountain_abundance']
    uplift=getattr(cfg,'orogeny',1.)*2*collision*math.exp(-(d/(abundance*(1+.25*cfg.mountain_detail*math.tanh(across))))**2)*mountain_modulation(along,across,cfg.mountain_detail)
    volcanic=subduction*math.exp(-((d-.8)/.5)**2) *overriding
    trench=-1.2*subduction*math.exp(-((d-.25)/.25)**2) *(1-overriding)
    rift=-.7*div*c*belt
    ridge=.6*div*(1-c)*belt
    interaction=uplift+trench+rift+ridge+.55*volcanic
    return cfg.tectonic_relief*(continental_profile(c)+interaction),cfg.tectonic_relief*interaction,volcanic


def generate_tectonics(cfg):
    start=perf_counter(); n=cfg.size; r=cfg.globe_radius
    layout_seed=child_seed(cfg.seed,'plates',cfg.layout_variation)
    crust_seed=child_seed(cfg.seed,'crust',cfg.layout_variation)
    detail_seed=child_seed(cfg.seed,'surface',cfg.detail_variation)
    plates=make_plates(layout_seed,cfg.plate_count)
    keys=('plates','crust','boundary_distance','convergence','divergence','shear')
    layers={k:[] for k in keys}; records=[]
    for z in range(n):
        row=[]
        for x in range(1 if z in (0,n-1) else n-1):
            row.append(layout_point(direction(x,z,n),plates,crust_seed,cfg))
        row=row*n if z in (0,n-1) else row+[row[0]]
        records.append(row)
        for index,key in enumerate(keys):
            layers[key].append([v[index] for v in row])
    layout_end=perf_counter()
    layers['base']=[[0.]*n for _ in range(n)]
    layers['height']=[[0.]*n for _ in range(n)]
    if cfg.phase>=2:
        layers.update({k:[] for k in ('structure','interaction','volcanic')})
        for row in records:
            results=[v[-3:] for v in row]
            for index,key in enumerate(('structure','interaction','volcanic')):
                layers[key].append([v[index] for v in results])
        layers['continental']=[[cfg.tectonic_relief*continental_profile(c) for c in row] for row in layers['crust']]
        layers['base']=([[cfg.tectonic_relief*continental_profile(c) for c in row] for row in layers['crust']]
                        if cfg.phase==2 else [row[:] for row in layers['structure']])
        layers['height']=[row[:] for row in layers['structure']]
    archipelagos=[]
    if cfg.world_recipe and cfg.phase>=2:
        from .terrain_ecology import shape_islands
        archipelagos=shape_islands(layers,cfg)
    interaction_end=perf_counter()
    step=2*math.pi*r/(n-1)
    frequencies=[2**k/cfg.wavelength for k in range(cfg.octaves) if cfg.wavelength/2**k>=2*step]
    if cfg.phase>=3:
        layers['noise']=[]
        for z in range(n):
            row=[]
            for x in range(1 if z in (0,n-1) else n-1):
                p=direction(x,z,n); value=0.
                for k,f in enumerate(frequencies):
                    noise=max(-1,min(1,perlin3(p[0]*r*f+.173,p[1]*r*f+.391,p[2]*r*f+.719,detail_seed+k*1013)))
                    value+=cfg.amplitude*.5**k*((1-cfg.ridge)*noise+cfg.ridge*((1-abs(noise))**3-.5))
                # Roughness follows boundary influence, with a small interior floor.
                influence=min(1,layers['convergence'][z][x]+layers['divergence'][z][x]+layers['shear'][z][x])
                row.append(value*(.2+.8*influence))
            row=row*n if z in (0,n-1) else row+[row[0]]
            layers['noise'].append(row)
            layers['height'][z]=[a+b for a,b in zip(layers['structure'][z],row)]
    if cfg.phase>=3:
        layers['surface']=[row[:] for row in layers['height']]
    noise_end=perf_counter()
    sediment=None
    if cfg.phase>=4:
        from .terrain_erosion import erode
        erosion,sediment=erode(layers['height'],r,cfg.sea_level,cfg.erosion_passes,cfg.erosion_strength)
        layers.update(erosion)
        layers['base']=[row[:] for row in layers['surface']]
    erosion_end=perf_counter()
    if cfg.phase>=2:
        layers['slope'],layers['tpi']=measure_globe(layers['height'],r,cfg.radius)
    end=perf_counter()
    warnings=['Static tectonic approximation: relative motion is dimensionless, not a time-evolving Earth simulation.',
              'Nearby plate pairs blend continuously; plate identity itself remains categorical.',
              'Erosion uses downhill grid neighbors and closed-depression sediment sinks. Later water routing does not rerun sediment transport.',
              'Latitude grid is not equal-area. TPI uses an 8-point geodesic ring.']
    if cfg.phase>=3 and len(frequencies)<cfg.octaves:
        warnings.append(f'Only {len(frequencies)}/{cfg.octaves} surface-noise octaves resolved; fine layers omitted.')
    return {'generator_version':6 if cfg.world_recipe else 5,'ocean_archipelagos':archipelagos,'sediment_budget':sediment,'config':asdict(cfg),'spacing_m':step,
            'effective_tpi_radius_m':min(math.pi*r/2,max(math.pi*r/(n-1),cfg.radius)),
            'resolved_octaves':len(frequencies) if cfg.phase>=3 else 0,
            'topology':{'type':'sphere','radius_m':r,'longitude_deg':[-180,180],'latitude_deg':[90,-90],
                        'duplicate_seam':True,'tpi_method':'8-point geodesic ring'},
            'phases':{'completed':cfg.phase,'seeds':{'layout':layout_seed,'crust':crust_seed,'detail':detail_seed},
                      'plates':plates,'motion_units':'dimensionless angular velocity',
                      'default_layer':'plates' if cfg.phase==1 else 'height'},
            'warnings':warnings,'layers':layers,
            'timing_ms':{'layout':(layout_end-start)*1000,'interactions':(interaction_end-layout_end)*1000,
                         'noise':(noise_end-interaction_end)*1000,'erosion':(erosion_end-noise_end)*1000,'measure':(end-erosion_end)*1000,'total':(end-start)*1000}}
