"""Deterministic final-world schematic city packing, in local metres."""
import hashlib
import json
import math
from .city_geometry import grow_roads, corners, footprint_cells
from .terrain_globe import sample as sample_height
from .civilization_registry import city_plan, section, registry_identity
from .city_shapes import select_shape, load_catalogue

VERSION=2
CELL=4


def planner_identity():
    return {'version':VERSION,'registry':registry_identity(),
            'shapes_sha256':hashlib.sha256(json.dumps(load_catalogue(),sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def _sampler(world,site,half):
    n=world['config']['size'];radius=world.get('effective_config',world['config'])['globe_radius']
    lat=math.pi/2-math.pi*site['z']/(n-1);lon=-math.pi+2*math.pi*site['x']/(n-1)
    up=(math.cos(lat)*math.cos(lon),math.sin(lat),math.cos(lat)*math.sin(lon))
    east=(-math.sin(lon),0,math.cos(lon));north=(-math.sin(lat)*math.cos(lon),math.cos(lat),-math.sin(lat)*math.sin(lon))
    def local(node):
        x,z=node;la=math.pi/2-math.pi*z/(n-1);lo=-math.pi+2*math.pi*x/(n-1)
        p=(math.cos(la)*math.cos(lo),math.sin(la),math.cos(la)*math.sin(lo));den=sum(a*b for a,b in zip(p,up))
        if den<=.1:return None
        return (radius*sum(a*b for a,b in zip(p,east))/den,radius*sum(a*b for a,b in zip(p,north))/den)
    nodes=world.get('water',{}).get('nodes',[]);lines=[]
    for i,j in world.get('climate',world.get('water',{})).get('river_segments',[]):
        a=local(nodes[i]);b=local(nodes[j])
        if a and b and all(min(a[k],b[k])<=half+40 and max(a[k],b[k])>=-half-40 for k in (0,1)):lines.append((a,b))
    def river_distance(x,z):
        best=1e30
        for a,b in lines:
            dx=b[0]-a[0];dz=b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(z-a[1])*dz)/(dx*dx+dz*dz or 1)))
            best=min(best,math.hypot(x-a[0]-t*dx,z-a[1]-t*dz))
        return best
    def sample(x,z):
        p=[up[i]+(east[i]*x+north[i]*z)/radius for i in range(3)];length=math.sqrt(sum(v*v for v in p));p=[v/length for v in p]
        gx=round((math.atan2(p[2],p[0])+math.pi)/(2*math.pi)*(n-1))%(n-1)
        gz=max(0,min(n-1,round((math.pi/2-math.asin(p[1]))/math.pi*(n-1))))
        def get(key,default=0):
            layer=world['layers'].get(key)
            return default if layer is None else layer[gz][gx]
        distance=river_distance(x,z)
        return {'water':get('water_type')!=0 or distance<12,'slope':get('slope'),
                'flood':int(distance<28) if lines and get('river')>.5 else get('flood_risk'),
                'height':sample_height(world['layers']['height'],p),'moisture':get('moisture',.5),'biome':get('natural_biome',3)}
    return sample,math.pi*radius/(n-1)


def plan_city(world,site,nearby_counts=None):
    preset=city_plan(site['population_profile'],site['city_class']+'_city')
    housing=section('housing_profiles');house=housing['worker_house'];apartment=housing['worker_apartment']
    half={'small':240,'medium':320,'capital':400}[site['city_class']]
    # Bound footprints by neighbouring city anchors, without moving any anchor.
    n=world['config']['size'];radius=world.get('effective_config',world['config'])['globe_radius']
    for other in world['settlements']['sites']:
        if other is site or other.get('uid')==site.get('uid'):continue
        lat1=math.pi/2-math.pi*site['z']/(n-1);lat2=math.pi/2-math.pi*other['z']/(n-1)
        dl=2*math.pi*(other['x']-site['x'])/(n-1)
        distance=radius*math.acos(max(-1,min(1,math.sin(lat1)*math.sin(lat2)+math.cos(lat1)*math.cos(lat2)*math.cos(dl))))
        half=min(half,distance*.28)
    half=max(CELL,int(half/CELL)*CELL);size=2*half//CELL
    sample,resolution=_sampler(world,site,half)
    terrain=[];valid=set();slopes=[];woods=0;heights={}
    for j in range(size):
        row=[]
        for i in range(size):
            v=sample(-half+(i+.5)*CELL,-half+(j+.5)*CELL)
            heights[(i,j)]=v['height']
            code=1 if v['water'] else 2 if v['slope']>25 or v['flood']>.65 else 0
            row.append(code)
            if code==0:valid.add((i,j));slopes.append(v['slope']);woods+=v['biome'] in (4,7,15)
        terrain.append(row)
    surface_size=33
    surface={'size':surface_size,'step_m':2*half/(surface_size-1),
             'heights_m':[[round(sample(-half+i*2*half/(surface_size-1),-half+j*2*half/(surface_size-1))['height'],4) for i in range(surface_size)] for j in range(surface_size)],
             'source':'bilinear final world height; no added detail'}
    center=sample(0,0)
    facts={'buildable_area_m2':len(valid)*CELL*CELL,'usable_land_fraction':len(valid)/(size*size),
           'local_slope_degrees':sum(slopes)/len(slopes) if slopes else 90,
           'aridity':1-max(0,min(1,center['moisture'])),'wooded_fraction':woods/max(1,len(valid))}
    # Fine topology/navigability is unknown in this world raster; do not invent it.
    selected=select_shape(facts,world['config']['seed'],str(site.get('uid',site['id'])),site['city_class'],nearby_counts)
    result={'version':VERSION,'city_uid':site.get('uid',str(site['id'])),'site_id':site['id'],'name':site['name'],
            'civilization_id':site['population_profile'],'city_class':site['city_class'],'unit':'metres',
            'bounds_m':[-half,-half,half,half],'terrain':{'cell_m':CELL,'size':size,'codes':terrain,'surface':surface},
            'location':facts,'shape':selected,'plots':[],'roads':[],'unplaced':[],
            'passes':[{'id':key,'placed':0} for key in ('map','shape','high','high_housing','low','low_housing')],
            'warnings':['Schematic packing from final world raster; sub-grid terrain, groundwater and structural feasibility are not resolved.',
                        'Routed river centerlines reserve a provisional 24 m channel and 28 m setback from centerline, not a simulated flood extent.',
                        'Four worker beds per house; 16 per apartment building when land is constrained. Dependents, commuters and households are not modeled.'],
            'source_resolution_m':round(resolution,2),'status':'unbuildable','stats':{}}
    if resolution>half:result['warnings'].append('World samples are wider than this city: elevation is interpolated and land categories repeat coarse samples; no new terrain detail is added.')
    if not selected['shape_id']:
        result['unplaced']=[{'building_id':r['structure_id'],'count':r['count'],'reason':'No compatible buildable footprint'} for r in preset['buildings']]
        result['stats']={'workers':0,'worker_beds':0,'housing_shortfall':0,'service_buildings':0,'houses':0}
        return result
    result['passes'][0]['placed']=len(valid);result['passes'][1]['placed']=1
    family=next(s['family'] for s in load_catalogue()['shapes'] if s['id']==selected['shape_id'])
    spacing=max(72,selected['parameters']['block_spacing_m'])
    aspect=selected['parameters']['aspect_ratio'];rx=half*.94;rz=half*.94/min(aspect,2)
    def inside(x,z):
        if family in ('grid','compound','hybrid'):return abs(x)<rx and abs(z)<rz
        if family=='cluster':return any((x-cx)**2+(z-cz)**2<(half*.52)**2 for cx,cz in ((-half*.32,0),(half*.32,0),(0,half*.25)))
        return (x/rx)**2+(z/rz)**2<1
    valid={c for c in valid if inside(-half+(c[0]+.5)*CELL,-half+(c[1]+.5)*CELL)}
    seed=int.from_bytes(hashlib.sha256(f"{world['config']['seed']}:{result['city_uid']}:streets-v2".encode()).digest()[:8],'big')
    road,paths=grow_roads(valid,heights.__getitem__,size,seed,spacing/CELL)
    result['roads']=[list(c) for c in sorted(road)]
    result['street_paths_m']=[[[round(-half+(x+.5)*CELL,2),round(-half+(z+.5)*CELL,2)] for x,z in path] for path in paths]
    anchors=[]
    for path in result['street_paths_m']:
        for i in range(0,len(path),1):
            a=path[max(0,i-3)];b=path[min(len(path)-1,i+3)]
            if a==b:continue
            x,z=path[i];angle=math.atan2(b[1]-a[1],b[0]-a[0])
            # Stable frontage variation follows the street, with modest organic deviations.
            angle+=math.radians(5*math.sin(x*.13+z*.17+(seed%1000)))
            anchors.append((x,z,angle))
    anchors=sorted(set(anchors),key=lambda p:(p[0]**2+p[1]**2,p))
    occupied=set();access=set();candidate_cache={}
    def cells(x,z,w,d,angle=0):return footprint_cells(x,z,w,d,angle,half,CELL)
    def candidates(w,d):
        if (w,d) in candidate_cache:return candidate_cache[(w,d)]
        options=[]
        for ax,az,angle in anchors:
            for side in (1,-1):
                dx=-math.sin(angle)*side;dz=math.cos(angle)*side
                x=round(ax+dx*(d/2+10),2);z=round(az+dz*(d/2+10),2)
                degrees=round(math.degrees(angle),4);angle=math.radians(degrees)
                footprint=cells(x,z,w,d,angle)
                if not footprint<=valid or footprint&road:continue
                # Check the actual interpolated ground, including within coarse raster cells.
                ground=[sample(px,pz)['height'] for px,pz in corners(x,z,w,d,angle)]
                if max(ground)-min(ground)>math.hypot(w,d)*math.tan(math.radians(25)):continue
                ex=x-dx*d/2;ez=z-dz*d/2;corridor=set()
                for t in range(11):corridor|=cells(ax+(ex-ax)*t/10,az+(ez-az)*t/10,4,4)
                if corridor<=valid:options.append((x,z,degrees,ax,az,footprint,corridor,ground))
        candidate_cache[(w,d)]=options
        return options
    def install(row,phase,kind='service'):
        w=row['plot_m']['width'];d=row['plot_m']['depth']
        for x,z,degrees,ax,az,footprint,corridor,ground in candidates(w,d):
            if footprint&occupied or footprint&access or corridor&occupied:continue
            occupied.update(footprint);access.update(corridor-footprint)
            plot={'id':f"plot-{len(result['plots'])}",'building_id':row.get('structure_id',row.get('id')),
                  'name':row['name'],'kind':kind,'phase':phase,'x_m':x,'z_m':z,
                  'rotation_degrees':degrees,'ground_elevation_m':round(max(ground),4),
                  'foundation_bottom_m':round(min(ground),4),
                  'plot_m':row['plot_m'],'dimensions_m':row['dimensions_m'],'road_access':[ax,az],
                  'workers':sum(r['target'] for r in row.get('staffing',{}).get('roles',[])),
                  'beds':row.get('worker_beds',0)}
            result['plots'].append(plot)
            result['passes'][next(i for i,p in enumerate(result['passes']) if p['id']==phase)]['placed']+=1
            return True
        return False
    conditions={'usable_groundwater':False,'water_collection_or_delivery':site.get('freshwater_distance_m') is not None,
                'navigable_shore':False,'flowing_water':False,'reliable_wind':False,
                'ore_and_fuel_supply':site.get('resource_potential',0)>=.5,'food_surplus':False,
                'working_animals':False,'clay_and_fuel_supply':False,'medicinal_supply':facts['wooded_fraction']>.1,
                'clear_sky_view':True,'isolation_access':True,'defended_perimeter':False}
    high=[];low=[]
    for row in preset['buildings']:
        missing=[c for c in row['placement_conditions'] if not conditions.get(c,False)]
        if missing:
            result['unplaced'].append({'building_id':row['structure_id'],'count':row['count'],'reason':'Unverified prerequisite: '+', '.join(missing)})
            continue
        (high if row['priority']=='core' else low).append(row)
    def house_workers(phase):
        workers=sum(p['workers'] for p in result['plots']);beds=sum(p['beds'] for p in result['plots'])
        while beds<workers:
            if not install(house,phase,'housing'):break
            beds+=house['worker_beds']
        # Replace existing dwellings in place: access and occupied land stay valid.
        for plot in result['plots']:
            if beds>=workers:break
            if plot['building_id']!=house['id']:continue
            plot.setdefault('housing_upgrade',{'phase':phase,'previous':{k:plot[k] for k in ('building_id','name','dimensions_m','beds')}})
            beds+=apartment['worker_beds']-plot['beds']
            plot.update(building_id=apartment['id'],name=apartment['name'],dimensions_m=apartment['dimensions_m'],beds=apartment['worker_beds'])
    for priority,rows in (('high',high),('low',low)):
        if priority=='low' and sum(p['workers']-p['beds'] for p in result['plots'])>0:
            result['unplaced'].extend({'building_id':r['structure_id'],'count':r['count'],'reason':'High-priority worker housing must be completed first'} for r in rows)
            break
        for row in rows:
            failed=0
            for _ in range(row['count']):
                if not install(row,priority):failed+=1
            if failed:result['unplaced'].append({'building_id':row['structure_id'],'count':failed,'reason':'No terrain-safe plot with road access remaining'})
        house_workers(priority+'_housing')
    workers=sum(p['workers'] for p in result['plots']);beds=sum(p['beds'] for p in result['plots'])
    core_ids={r['structure_id'] for r in preset['buildings'] if r['priority']=='core'}
    failed_core=sum(r['count'] for r in result['unplaced'] if r['building_id'] in core_ids)
    result['status']='complete' if not failed_core and beds>=workers else 'partial'
    result['stats']={'workers':workers,'worker_beds':beds,'housing_shortfall':max(0,workers-beds),
                     'service_buildings':sum(p['kind']=='service' for p in result['plots']),
                     'houses':sum(p['building_id']==house['id'] for p in result['plots']),
                     'apartments':sum(p['building_id']==apartment['id'] for p in result['plots']),
                     'unplaced_core':failed_core,'unplaced_total':sum(r['count'] for r in result['unplaced']),
                     'simulation_population':site.get('urban_population_estimate',site.get('population_estimate')),
                     'reserved_plot_area_m2':sum(p['plot_m']['width']*p['plot_m']['depth'] for p in result['plots'])}
    return result


def fill_cities(world):
    cities=[];counts={}
    for site in sorted(world['settlements']['sites'],key=lambda s:str(s.get('uid',s['id']))):
        plan=plan_city(world,site,counts);cities.append(plan)
        key=plan['shape']['shape_id']
        if key:counts[key]=counts.get(key,0)+1
    world['city_plans']={'version':VERSION,'identity':planner_identity(),'cities':cities,
                         'phase_order':['map','shape','high','high_housing','low','low_housing'],
                         'scope':'Schematic local metres from final world raster; does not change simulated population.'}
    return world['city_plans']
