"""Deterministic final-world schematic hamlet packing, independent of city_plans."""
import hashlib
import math
from .city_geometry import grow_roads, corners, footprint_cells
from .city_planner import _sampler, CELL
from .civilization_registry import hamlet_plan, section, registry_identity

VERSION=1
HALF_DEFAULT=100  # 200 m across; smaller than small-city 480 m


def planner_identity():
    return {'version':VERSION,'registry':registry_identity()}


def _coastal_role(role):
    role=role or ''
    return role in ('harbor','fishing','landing','harbor + fishing') or 'harbor' in role or 'fishing' in role or role=='landing'


def _role_conditions(hamlet):
    role=hamlet.get('role','')
    return {
        'farming_support':role=='farming',
        'resource_support':role=='resource',
        'navigable_shore':_coastal_role(role),
        'usable_groundwater':False,
        'water_collection_or_delivery':True,
        'flowing_water':False,
        'reliable_wind':False,
        'ore_and_fuel_supply':role=='resource',
        'food_surplus':role=='farming',
        'working_animals':role=='farming',
        'clay_and_fuel_supply':False,
        'medicinal_supply':False,
        'clear_sky_view':True,
        'isolation_access':True,
        'route_crossing':False,
        'grade_change':False,
        'retention_needed':False,
        'defended_perimeter':False,
    }


def support_road_entries(world,hamlet,half):
    """Project the parent-city support path and take the window-boundary crossing as a gate."""
    from .world_scene import frame, local_direction
    from .terrain_globe import direction
    nodes=world.get('water',{}).get('nodes',[])
    path=list(hamlet.get('access_nodes') or [])
    if len(path)<2 or not nodes:
        return []
    f=frame(world,hamlet);r,up,east,north=f
    # access_nodes runs from the hamlet toward the parent city.
    prev=(0.,0.);entries=[]
    for index in path[1:]:
        if index<0 or index>=len(nodes):break
        x,z=nodes[index]
        p=direction(x,z,world['config']['size']);den=sum(a*b for a,b in zip(p,up))
        if den<=0:break
        q=(r*sum(a*b for a,b in zip(p,east))/den,r*sum(a*b for a,b in zip(p,north))/den)
        if max(abs(v) for v in q)>half:
            ts=[((half if q[j]>0 else -half)-prev[j])/(q[j]-prev[j]) for j in (0,1) if abs(q[j])>half]
            t=min(ts);gate=[prev[j]+t*(q[j]-prev[j]) for j in (0,1)]
            entries.append({'route_id':f"support:{hamlet['id']}",'route_index':-1,'end':'to',
                'outside_index':0,'junction_id':f"junction:{hamlet['id']}:support",
                'gate_local_m':gate,'direction':local_direction(f,*gate),
                'status':'unreachable','reason':'No terrain-safe street connection to parent-city approach'})
            break
        prev=q
    return entries


def plan_hamlet(world,hamlet):
    preset=hamlet_plan(hamlet['population_profile'])
    housing=section('housing_profiles');house=housing['hamlet_house']
    n=world['config']['size'];radius=world.get('effective_config',world['config'])['globe_radius']
    half=HALF_DEFAULT
    # Bound by parent city and neighbouring hamlets without moving anchors.
    sites=[]
    for site in world['settlements']['sites']:
        sites.append(site)
    for other in world.get('humans',{}).get('hamlets',[]):
        if other is hamlet or other.get('id')==hamlet.get('id'):continue
        sites.append(other)
    for other in sites:
        lat1=math.pi/2-math.pi*hamlet['z']/(n-1);lat2=math.pi/2-math.pi*other['z']/(n-1)
        dl=2*math.pi*(other['x']-hamlet['x'])/(n-1)
        distance=radius*math.acos(max(-1,min(1,math.sin(lat1)*math.sin(lat2)+math.cos(lat1)*math.cos(lat2)*math.cos(dl))))
        half=min(half,distance*.28)
    half=max(CELL,int(half/CELL)*CELL);size=2*half//CELL
    sample,resolution=_sampler(world,hamlet,half)
    terrain=[];biomes=[];mutations=[];valid=set();slopes=[];woods=0;heights={}
    for j in range(size):
        row=[];biome_row=[];mutation_row=[]
        for i in range(size):
            v=sample(-half+(i+.5)*CELL,-half+(j+.5)*CELL)
            heights[(i,j)]=v['height']
            code=1 if v['water'] else 2 if v['slope']>25 or v['flood']>.65 else 0
            row.append(code);biome_row.append(v['biome']);mutation_row.append(v['variant'])
            if code==0:valid.add((i,j));slopes.append(v['slope']);woods+=v['biome'] in (4,7,15)
        terrain.append(row);biomes.append(biome_row);mutations.append(mutation_row)
    surface_size=size+1
    surface={'size':surface_size,'step_m':2*half/(surface_size-1),
             'heights_m':[[round(sample(-half+i*2*half/(surface_size-1),-half+j*2*half/(surface_size-1),False)['height'],4)
                           for i in range(surface_size)] for j in range(surface_size)],
             'source':'canonical terrain height in metres','terrain_detail':world.get('terrain_detail'),
             'coordinates':'local east/north gnomonic coordinates; radial elevation above reference sphere'}
    core=world['settlements']['sites'][hamlet['core_id']]
    result={'version':VERSION,'hamlet_id':hamlet['id'],'kind':'hamlet','role':hamlet.get('role'),
            'core_city_uid':core.get('uid',str(core['id'])),'core_id':hamlet['core_id'],
            'x':hamlet['x'],'z':hamlet['z'],'node':hamlet['node'],
            'civilization_id':hamlet['population_profile'],'unit':'metres',
            'bounds_m':[-half,-half,half,half],
            'terrain':{'cell_m':CELL,'size':size,'codes':terrain,'surface':surface,'natural_biome':biomes,
                       'biome_variant':mutations,'biome_catalogue':world.get('terrain',{}).get('biomes',[]),
                       'magical_catalogue':world.get('terrain',{}).get('magical_biomes',[]),
                       'magic_colors':{k:v['color'] for k,v in world.get('magic',{}).get('networks',{}).items()}},
            'reference_frame':{'radius_m':radius,'latitude_degrees':90-180*hamlet['z']/(n-1),
                               'longitude_degrees':-180+360*hamlet['x']/(n-1),
                               'projection':'direction=normalize(up+(east*x_m+north*z_m)/radius_m); position=(radius_m+height_m)*direction'},
            'shape':{'shape_id':'hamlet_compact','family':'organic','parameters':{'block_spacing_m':48,'aspect_ratio':1.1}},
            'plots':[],'roads':[],'unplaced':[],
            'passes':[{'id':key,'placed':0} for key in ('map','shape','high','high_housing','low','low_housing')],
            'warnings':['Schematic rural packing; groundwater and structural feasibility are not resolved.',
                        'Hamlet cottages use dedicated rural housing IDs, not city worker houses.',
                        'Compact elliptical boundary is provisional; historical village morphology is future work.'],
            'source_resolution_m':round(resolution,2),'status':'unbuildable','stats':{},
            'debug':{'terrain_safe_cells':len(valid),'total_cells':size*size,'housing_passes':[],
                     'apartment_policy':'hamlet_houses_only'}}
    result['road_connections']=support_road_entries(world,hamlet,half)
    if resolution>half:result['warnings'].append('Regional land categories repeat coarse samples; canonical local relief supplies finer elevation detail.')
    if len(valid)<8:
        result['unplaced']=[{'building_id':r['structure_id'],'count':r['count'],'reason':'No compatible buildable footprint'} for r in preset['buildings']]
        result['stats']={'workers':0,'worker_beds':0,'housing_shortfall':0,'service_buildings':0,'houses':0}
        return result
    result['passes'][0]['placed']=len(valid);result['passes'][1]['placed']=1
    spacing=48;rx=half*.9;rz=half*.9/1.1
    seed=int.from_bytes(hashlib.sha256(f"{world['config']['seed']}:{result['hamlet_id']}:hamlet-streets-v1".encode()).digest()[:8],'big')
    # Seeded irregular ellipse keeps city shape catalogues independent.
    wobble=0.08+0.04*((seed%1000)/1000)
    def inside(x,z):
        return (x/(rx*(1+wobble*math.sin(x*.07+seed))))**2+(z/(rz*(1+wobble*math.cos(z*.09+seed))))**2<1
    terrain_valid=set(valid)
    valid={c for c in valid if inside(-half+(c[0]+.5)*CELL,-half+(c[1]+.5)*CELL)}
    if len(valid)<8:
        result['unplaced']=[{'building_id':r['structure_id'],'count':r['count'],'reason':'No compatible buildable footprint'} for r in preset['buildings']]
        result['stats']={'workers':0,'worker_beds':0,'housing_shortfall':0,'service_buildings':0,'houses':0}
        return result
    entries=result['road_connections']
    for c in entries:c['cell']=[max(0,min(size-1,math.floor((v+half)/CELL))) for v in c['gate_local_m']]
    road,paths=grow_roads(terrain_valid if entries else valid,heights.__getitem__,size,seed,spacing/CELL,[tuple(c['cell']) for c in entries])
    for c in entries:
        cell=tuple(c['cell']);gate=c['gate_local_m'];point=[-half+(v+.5)*CELL for v in cell]
        v=sample(*gate);length=math.dist(point,gate)
        if cell in road and not v['water'] and v['flood']<=.65 and v['slope']<=25 and abs(v['height']-heights[cell])<=.35*length+1e-6:
            approach=next((path for path in paths if path[-1]==cell),[cell])
            c.update(status='connected',reason='Terrain-safe junction to parent-city approach',
                     local_path_m=[[-half+(a+.5)*CELL,-half+(b+.5)*CELL] for a,b in approach]+[gate])
    result['roads']=[list(c) for c in sorted(road)]
    result['street_paths_m']=[[[round(-half+(x+.5)*CELL,2),round(-half+(z+.5)*CELL,2)] for x,z in path] for path in paths]
    anchors=[]
    for path in result['street_paths_m']:
        for i in range(len(path)):
            a=path[max(0,i-3)];b=path[min(len(path)-1,i+3)]
            if a==b:continue
            x,z=path[i];angle=math.atan2(b[1]-a[1],b[0]-a[0])
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
                x=round(ax+dx*(d/2+8),2);z=round(az+dz*(d/2+8),2)
                degrees=round(math.degrees(angle),4);angle=math.radians(degrees)
                footprint=cells(x,z,w,d,angle)
                if not footprint<=valid or footprint&road:continue
                ground=[sample(px,pz,False)['height'] for px,pz in corners(x,z,w,d,angle)]
                ground+=[heights[c] for c in sorted(footprint)]
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
    conditions=_role_conditions(hamlet)
    high=[];low=[]
    for row in preset['buildings']:
        missing=[c for c in row['placement_conditions'] if not conditions.get(c,False)]
        if missing:
            result['unplaced'].append({'building_id':row['structure_id'],'count':row['count'],
                                       'reason':'Unverified prerequisite: '+', '.join(missing)})
            continue
        (high if row['priority']=='core' else low).append(row)
    def house_workers(phase):
        workers=sum(p['workers'] for p in result['plots']);beds=sum(p['beds'] for p in result['plots'])
        audit={'phase':phase,'workers':workers,'starting_beds':beds,'houses_placed':0,'upgrades':0,'plots_exhausted':False}
        while beds<workers:
            if not install(house,phase,'housing'):
                audit['plots_exhausted']=True;break
            audit['houses_placed']+=1
            beds+=house['worker_beds']
        audit.update(final_beds=beds,shortfall=max(0,workers-beds))
        result['debug']['housing_passes'].append(audit)
    for priority,rows in (('high',high),('low',low)):
        if priority=='low' and sum(p['workers']-p['beds'] for p in result['plots'])>0:
            result['unplaced'].extend({'building_id':r['structure_id'],'count':r['count'],
                                       'reason':'High-priority worker housing must be completed first'} for r in rows)
            break
        for row in rows:
            failed=0
            for _ in range(row['count']):
                if not install(row,priority):failed+=1
            if failed:result['unplaced'].append({'building_id':row['structure_id'],'count':failed,
                                                 'reason':'No terrain-safe plot with road access remaining'})
        house_workers(priority+'_housing')
    workers=sum(p['workers'] for p in result['plots']);beds=sum(p['beds'] for p in result['plots'])
    result['debug'].update(shape_safe_cells=len(valid),road_cells=len(road),occupied_cells=len(occupied),
                           access_cells=len(access),vacant_shape_cells=len(valid-road-occupied-access),
                           housing_frontage_candidates=len(candidates(house['plot_m']['width'],house['plot_m']['depth'])))
    core_ids={r['structure_id'] for r in preset['buildings'] if r['priority']=='core'}
    failed_core=sum(r['count'] for r in result['unplaced'] if r['building_id'] in core_ids)
    result['status']='complete' if not failed_core and beds>=workers else 'partial'
    result['stats']={'workers':workers,'worker_beds':beds,'housing_shortfall':max(0,workers-beds),
                     'service_buildings':sum(p['kind']=='service' for p in result['plots']),
                     'houses':sum(p['building_id']==house['id'] for p in result['plots']),
                     'apartments':0,'unplaced_core':failed_core,'unplaced_total':sum(r['count'] for r in result['unplaced']),
                     'reserved_plot_area_m2':sum(p['plot_m']['width']*p['plot_m']['depth'] for p in result['plots'])}
    return result


def fill_hamlets(world):
    hamlets=[]
    for site in sorted(world.get('humans',{}).get('hamlets',[]),key=lambda h:str(h['id'])):
        hamlets.append(plan_hamlet(world,site))
    world['hamlet_plans']={'version':VERSION,'identity':planner_identity(),'hamlets':hamlets,
                           'phase_order':['map','shape','high','high_housing','low','low_housing'],
                           'scope':'Schematic local metres for support hamlets; independent of city_plans; does not change simulated population.'}
    from .world_scene import build_scene
    build_scene(world)
    return world['hamlet_plans']
