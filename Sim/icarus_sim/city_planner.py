"""Deterministic final-world schematic city packing, in local metres."""
import hashlib
import os
import json
import math
from .city_geometry import grow_roads, corners, footprint_cells
from .terrain_detail import HeightField
from .civilization_registry import city_plan, section, registry_identity
from .city_shapes import select_shape, load_catalogue
from .city_fortifications import program_half_m, build_fortifications, wall_and_gate_defs
from .terrain_settlements import FOUNDED_BY, PLAYER

VERSION=8
CELL=4
_ROOT2=math.sqrt(2)


def _clearance(free,size):
    """Chebyshev cell distance from each cell to the nearest cell that is not free ground.

    Two sweeps over the city raster, once per city, so that the candidate sweep can
    decide most positions without rasterizing anything. Roughly four candidate positions
    in five are rejected because the plot overlaps blocked ground or a street, and each
    of those used to cost a footprint rasterization and two set tests.
    """
    far=size+size
    grid=[[far if (i,j) in free else 0 for i in range(size)] for j in range(size)]
    for j in range(size):
        row=grid[j];up=grid[j-1] if j else None
        for i in range(size):
            if not row[i]:continue
            best=row[i-1]+1 if i else 1
            if up is None:
                if best>1:best=1
            else:
                if up[i]+1<best:best=up[i]+1
                if i and up[i-1]+1<best:best=up[i-1]+1
                if i+1<size and up[i+1]+1<best:best=up[i+1]+1
            if best<row[i]:row[i]=best
    for j in range(size-1,-1,-1):
        row=grid[j];down=grid[j+1] if j+1<size else None
        for i in range(size-1,-1,-1):
            if not row[i]:continue
            best=row[i+1]+1 if i+1<size else 1
            if down is None:
                if best>1:best=1
            else:
                if down[i]+1<best:best=down[i]+1
                if i+1<size and down[i+1]+1<best:best=down[i+1]+1
                if i and down[i-1]+1<best:best=down[i-1]+1
            if best<row[i]:row[i]=best
    return grid


def planner_identity():
    return {'version':VERSION,'registry':registry_identity(),
            'shapes_sha256':hashlib.sha256(json.dumps(load_catalogue(),sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def _sampler(world,site,half):
    field=HeightField(world)
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
    def direction_at(x,z):
        p=[up[i]+(east[i]*x+north[i]*z)/radius for i in range(3)];length=math.sqrt(sum(v*v for v in p))
        return [v/length for v in p]
    # Resolved once instead of on every layer read inside sample(); plan_city only
    # reads these grids, so hoisting them changes no value, just the lookup count.
    _layers=world['layers']
    _slope=_layers.get('slope');_water=_layers.get('water_type');_river=_layers.get('river')
    _flood=_layers.get('flood_risk');_moisture=_layers.get('moisture')
    _biome=_layers.get('natural_biome');_variant=_layers.get('biome_variant')
    _has_definition=bool(field.definition)
    def sample(x,z,with_slope=True):
        p=[up[i]+(east[i]*x+north[i]*z)/radius for i in range(3)];length=math.sqrt(sum(v*v for v in p));p=[v/length for v in p]
        gx=round((math.atan2(p[2],p[0])+math.pi)/(2*math.pi)*(n-1))%(n-1)
        gz=max(0,min(n-1,round((math.pi/2-math.asin(p[1]))/math.pi*(n-1))))
        distance=river_distance(x,z)
        slope=0 if _slope is None else _slope[gz][gx]
        if _has_definition and with_slope:
            dx=(field.height(direction_at(x+1,z))-field.height(direction_at(x-1,z)))/2
            dz=(field.height(direction_at(x,z+1))-field.height(direction_at(x,z-1)))/2
            slope=math.degrees(math.atan(math.hypot(dx,dz)))
        # Two different things used to share one `flood` key, and a caller could not tell
        # which it had read. `channel` is local: this point is inside the reserved river
        # channel and setback, measured in metres from a routed centerline. `flood_risk`
        # is the regional proxy, one value for a raster cell thousands of metres across --
        # far larger than a city, so it is the same number everywhere in this footprint
        # and can only ever block all of it or none of it.
        channel=int(distance<28) if lines and (0 if _river is None else _river[gz][gx])>.5 else 0
        return {'water':(0 if _water is None else _water[gz][gx])!=0 or distance<12,'slope':slope,
                'channel':channel,'flood_risk':(0 if _flood is None else _flood[gz][gx]),
                'height':field.height(p),'moisture':.5 if _moisture is None else _moisture[gz][gx],
                'biome':3 if _biome is None else _biome[gz][gx],'variant':-1 if _variant is None else _variant[gz][gx]}
    def height_at(x,z):
        """Elevation alone, for the callers that read only v['height'].

        direction_at builds and normalises the very same vector sample() does and
        field.height is a pure function of it, so this returns the identical float.
        What it skips is what a height-only caller discards anyway: the river
        distance loop, two inverse trigonometric grid-index calls, six layer
        lookups and a seven-key dict. The surface grid alone asks for this
        (size+1) squared times per city.
        """
        return field.height(direction_at(x,z))
    sample.height_at=height_at
    return sample,math.pi*radius/(n-1)


class _Replay:
    """A generator's output, remembered so it can be iterated any number of times.

    `candidates` used to build the whole anchor sweep for every plot size, but
    `install` takes the first free option and stops: between 22% and 61% of each
    list was built and never looked at. Yielding on demand and keeping what was
    yielded leaves the order and the first match identical -- no plot moves -- and
    simply stops producing options past the deepest one anybody asked for.
    """
    __slots__=('_memo','_source','_spent')
    def __init__(self,source):self._memo=[];self._source=source;self._spent=False
    def __iter__(self):
        memo=self._memo;i=0
        while True:
            if i<len(memo):
                yield memo[i];i+=1;continue
            if self._spent:return
            try:option=next(self._source)
            except StopIteration:
                self._spent=True;return
            memo.append(option);yield option;i+=1


def plan_city(world,site,nearby_counts=None,shape_only=False):
    preset=city_plan(site['population_profile'],site['city_class']+'_city')
    housing=section('housing_profiles');house=housing['worker_house'];apartment=housing['worker_apartment']
    # Bound footprints by neighbouring city anchors, without moving any anchor.
    n=world['config']['size'];radius=world.get('effective_config',world['config'])['globe_radius']
    neighbour_half={'small':240,'medium':320,'capital':400}[site['city_class']]
    for other in world['settlements']['sites']:
        if other is site or other.get('uid')==site.get('uid'):continue
        lat1=math.pi/2-math.pi*site['z']/(n-1);lat2=math.pi/2-math.pi*other['z']/(n-1)
        dl=2*math.pi*(other['x']-site['x'])/(n-1)
        distance=radius*math.acos(max(-1,min(1,math.sin(lat1)*math.sin(lat2)+math.cos(lat1)*math.cos(lat2)*math.cos(dl))))
        neighbour_half=min(neighbour_half,distance*.28)
    half=program_half_m(preset,site['city_class'],neighbour_half,
                        house_plot=(house['plot_m']['width'],house['plot_m']['depth']),
                        beds_per_house=house['worker_beds'])
    size=2*half//CELL
    sample,resolution=_sampler(world,site,half)
    terrain=[];biomes=[];mutations=[];valid=set();slopes=[];woods=0;heights={}
    for j in range(size):
        row=[];biome_row=[];mutation_row=[]
        for i in range(size):
            v=sample(-half+(i+.5)*CELL,-half+(j+.5)*CELL)
            heights[(i,j)]=v['height']
            # Standing water, real steepness and the reserved river channel block a cell.
            # The regional flood proxy does not, for the reason hamlet_planner already
            # records: it is a coarse layer, not a local inundation mask. It is emitted
            # as 0 or 1 and a city is smaller than one of its cells, so honouring it here
            # disqualified whole cities outright -- 23 of 35 in a seed-42 size-33 world,
            # every one of them on a cell reading exactly 1.0, on ground under 21 degrees.
            code=1 if v['water'] else 2 if v['slope']>25 or v['channel'] else 0
            row.append(code);biome_row.append(v['biome']);mutation_row.append(v['variant'])
            if code==0:valid.add((i,j));slopes.append(v['slope']);woods+=v['biome'] in (4,7,15)
        terrain.append(row);biomes.append(biome_row);mutations.append(mutation_row)
    center=sample(0,0)
    threat=next((c['regional_threat'] for c in world.get('threat_assessments',{}).get('cities',[])
                 if c['city_uid']==site.get('uid',str(site['id']))),0.)
    facts={'buildable_area_m2':len(valid)*CELL*CELL,'usable_land_fraction':len(valid)/(size*size),
           'local_slope_degrees':sum(slopes)/len(slopes) if slopes else 90,
           'aridity':1-max(0,min(1,center['moisture'])),'wooded_fraction':woods/max(1,len(valid)),
           'regional_threat':threat,'defense_priority':threat}
    # Shape selection reads `facts` and nothing below it, and fill_cities needs every
    # city's shape before it can plan any city, because the repetition counter runs in
    # uid order. A caller taking that pass asks for the facts alone; the surface grid
    # below is (size+1) squared height samples it would only throw away.
    if shape_only:return facts
    surface_size=size+1
    surface={'size':surface_size,'step_m':2*half/(surface_size-1),
             'heights_m':[[round(sample.height_at(-half+i*2*half/(surface_size-1),-half+j*2*half/(surface_size-1)),4) for i in range(surface_size)] for j in range(surface_size)],
             'source':'canonical terrain height in metres','terrain_detail':world.get('terrain_detail'),
             'coordinates':'local east/north gnomonic coordinates; radial elevation above reference sphere'}
    # Fine topology/navigability is unknown in this world raster; do not invent it.
    selected=select_shape(facts,world['config']['seed'],str(site.get('uid',site['id'])),site['city_class'],nearby_counts)
    # A city the player authored is not packed here. The record is still produced in full
    # -- terrain, reference frame, road connections -- because a consumer rendering the
    # player's town needs the ground it stands on; what it does not get is a planner's
    # opinion about where the buildings go. `unbuildable` is a status the planner already
    # emits, so no consumer needs a new branch for it.
    authored=site.get(FOUNDED_BY)==PLAYER
    # The site's own two demographic figures, copied verbatim and named for their axes.
    # This used to be one key, `simulation_population`, holding the urban estimate under a
    # name that said neither which axis nor whose number it was.
    population_stats={'population_estimate':site.get('population_estimate'),
                      'urban_population_estimate':site.get('urban_population_estimate')}
    if authored:
        selected={**selected,'shape_id':None,'parameters':{},
                  'reason':'Layout authored by the player; the generator chooses no shape for an authored city.'}
    result={'version':VERSION,'city_uid':site.get('uid',str(site['id'])),'site_id':site['id'],'name':site['name'],
            'civilization_id':site['population_profile'],'city_class':site['city_class'],'unit':'metres',
            'bounds_m':[-half,-half,half,half],'terrain':{'cell_m':CELL,'size':size,'codes':terrain,'surface':surface,'natural_biome':biomes,'biome_variant':mutations,'biome_catalogue':world.get('terrain',{}).get('biomes',[]),'magical_catalogue':world.get('terrain',{}).get('magical_biomes',[]),'magic_colors':{k:v['color'] for k,v in world.get('magic',{}).get('networks',{}).items()}},
            'reference_frame':{'radius_m':radius,'latitude_degrees':90-180*site['z']/(n-1),'longitude_degrees':-180+360*site['x']/(n-1),'projection':'direction=normalize(up+(east*x_m+north*z_m)/radius_m); position=(radius_m+height_m)*direction'},
            'location':facts,'shape':selected,'plots':[],'roads':[],'unplaced':[],'fortifications':None,
            'passes':[{'id':key,'placed':0} for key in ('map','shape','fortification','high','high_housing','low','low_housing')],
            'warnings':['Schematic packing over canonical detailed terrain; groundwater and structural feasibility are not resolved.',
                        'Routed river centerlines reserve a provisional 24 m channel and 28 m setback from centerline, not a simulated flood extent.',
                        'Four worker beds per house; 16 per apartment building when land is constrained. Dependents, commuters and households are not modeled.',
                        'City walls are schematic enceintes separate from castle bailey generation.'],
            'source_resolution_m':round(resolution,2),'status':'unbuildable','stats':{}}
    result['debug']={'terrain_safe_cells':len(valid),'total_cells':size*size,'housing_passes':[],
                     'apartment_policy':'houses_first_then_upgrade_on_plot_exhaustion'}
    from .world_scene import road_entries
    result['road_connections']=road_entries(world,site,half)
    if resolution>half:result['warnings'].append('Regional land categories repeat coarse samples; canonical local relief supplies finer elevation detail.')
    if not selected['shape_id']:
        reason='Layout authored by the player' if authored else 'No compatible buildable footprint'
        result['unplaced']=[{'building_id':r['structure_id'],'count':r['count'],'reason':reason} for r in preset['buildings']]
        result['stats']={'workers':0,'worker_beds':0,'housing_shortfall':0,'service_buildings':0,'houses':0,
                         **population_stats}
        if authored:result['authored_by']=PLAYER
        return result
    result['passes'][0]['placed']=len(valid);result['passes'][1]['placed']=1
    family=next(s['family'] for s in load_catalogue()['shapes'] if s['id']==selected['shape_id'])
    spacing=max(72,selected['parameters']['block_spacing_m'])
    aspect=selected['parameters']['aspect_ratio'];rx=half*.94;rz=half*.94/min(aspect,2)
    def inside(x,z):
        if family in ('grid','compound','hybrid'):return abs(x)<rx and abs(z)<rz
        if family=='cluster':return any((x-cx)**2+(z-cz)**2<(half*.52)**2 for cx,cz in ((-half*.32,0),(half*.32,0),(0,half*.25)))
        # organic, contour, rings and paired lobes share an elliptical clip; ring scales are fortification-only.
        return (x/rx)**2+(z/rz)**2<1
    terrain_valid=set(valid)
    valid={c for c in valid if inside(-half+(c[0]+.5)*CELL,-half+(c[1]+.5)*CELL)}
    seed=int.from_bytes(hashlib.sha256(f"{world['config']['seed']}:{result['city_uid']}:streets-v2".encode()).digest()[:8],'big')
    entries=result['road_connections']
    for c in entries:c['cell']=[max(0,min(size-1,math.floor((v+half)/CELL))) for v in c['gate_local_m']]
    road,paths=grow_roads(terrain_valid if entries else valid,heights.__getitem__,size,seed,spacing/CELL,[tuple(c['cell']) for c in entries])
    for c in entries:
        cell=tuple(c['cell']);gate=c['gate_local_m'];point=[-half+(v+.5)*CELL for v in cell]
        v=sample(*gate);length=math.dist(point,gate)
        if cell in road and not v['water'] and not v['channel'] and v['slope']<=25 and abs(v['height']-heights[cell])<=.35*length+1e-6:
            approach=next((path for path in paths if path[-1]==cell),[cell])
            c.update(status='connected',reason='Terrain-safe junction to regional road',local_path_m=[[-half+(a+.5)*CELL,-half+(b+.5)*CELL] for a,b in approach]+[gate])
    result['roads']=[list(c) for c in sorted(road)]
    clearance=_clearance(valid-road,size)
    result['street_paths_m']=[[[round(-half+(x+.5)*CELL,2),round(-half+(z+.5)*CELL,2)] for x,z in path] for path in paths]
    wall_def,gate_def=wall_and_gate_defs(preset)
    gate_budget=next((row['count'] for row in preset['buildings'] if row['structure_id']=='building.gatehouse'),0)
    tower_budget=next((row['count'] for row in preset['buildings'] if row['structure_id']=='building.tower'),0)
    fortifications=build_fortifications(valid=valid,half=half,cell=CELL,rx=rx,rz=rz,family=family,
                                        shape_id=selected['shape_id'],parameters=selected['parameters'],
                                        city_class=site['city_class'],road_connections=result['road_connections'],
                                        wall_structure=wall_def,gate_structure=gate_def,
                                        tower_budget=tower_budget,gate_budget=max(1,gate_budget))
    result['fortifications']=fortifications
    result['passes'][2]['placed']=len(fortifications['segments'])
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
    occupied=set();access=set();reserved=set();candidate_cache={};housing_reserve=[]
    # An access corridor depends only on its two endpoints, so every building that
    # shares a plot depth reuses the same one. Rebuilding it per (width, depth)
    # made the eleven-step rasterization the hottest call in city planning.
    corridor_cache={}
    def cells(x,z,w,d,angle=0):return footprint_cells(x,z,w,d,angle,half,CELL)
    def _stream(w,d):
        for ax,az,angle in anchors:
            for side in (1,-1):
                dx=-math.sin(angle)*side;dz=math.cos(angle)*side
                x=round(ax+dx*(d/2+10),2);z=round(az+dz*(d/2+10),2)
                degrees=round(math.degrees(angle),4);angle=math.radians(degrees)
                # The nearest cell that is not free ground has its centre within
                # (k+1)*CELL of this plot centre in Chebyshev terms, so within
                # (k+1)*CELL*sqrt(2) Euclidean. When that lands inside the inscribed
                # circle it is inside the rectangle and therefore inside the footprint,
                # so the two tests below are already decided and the rasterization is
                # skipped. It can never fire on a candidate they would have accepted.
                ci=int((x+half)//CELL);cj=int((z+half)//CELL)
                if 0<=ci<size and 0<=cj<size and (clearance[cj][ci]+1)*CELL*_ROOT2<=(w if w<d else d)/2:continue
                footprint=cells(x,z,w,d,angle)
                if not footprint<=valid or footprint&road:continue
                # Check the actual interpolated ground, including within coarse raster cells.
                ground=[sample.height_at(px,pz) for px,pz in corners(x,z,w,d,angle)]
                # Only max() and min() are ever read from this list, so the sort was
                # ordering a few hundred thousand short lists for nothing.
                ground += [heights[c] for c in footprint]
                if max(ground)-min(ground)>math.hypot(w,d)*math.tan(math.radians(25)):continue
                ex=x-dx*d/2;ez=z-dz*d/2
                corridor=corridor_cache.get((ax,az,ex,ez))
                if corridor is None:
                    corridor=set()
                    for t in range(11):corridor|=cells(ax+(ex-ax)*t/10,az+(ez-az)*t/10,4,4)
                    corridor_cache[(ax,az,ex,ez)]=corridor
                if corridor<=valid:yield (x,z,degrees,ax,az,footprint,corridor,ground)
    def candidates(w,d):
        options=candidate_cache.get((w,d))
        if options is None:options=candidate_cache[(w,d)]=_Replay(_stream(w,d))
        return options
    def free_frontage(w,d):
        return sum(1 for x,z,degrees,ax,az,footprint,corridor,ground in candidates(w,d)
                   if not (footprint&occupied or footprint&access or corridor&occupied or footprint&reserved or corridor&reserved))
    def reserve_housing(worker_budget):
        """Hold street-front plots so later service packing cannot starve worker houses."""
        need=max(0,math.ceil(max(0,worker_budget-sum(p['beds'] for p in result['plots']))/house['worker_beds'])-len(housing_reserve))
        w,d=house['plot_m']['width'],house['plot_m']['depth']
        for option in candidates(w,d):
            if need<=0:break
            footprint,corridor=option[5],option[6]
            if footprint&occupied or footprint&access or corridor&occupied:continue
            if footprint&reserved or corridor&reserved:continue
            reserved.update(footprint);reserved.update(corridor-footprint)
            housing_reserve.append(option);need-=1
        return len(housing_reserve)
    def install(row,phase,kind='service',placement=None):
        w=row['plot_m']['width'];d=row['plot_m']['depth']
        options=[placement] if placement else candidates(w,d)
        for option in options:
            x,z,degrees,ax,az,footprint,corridor,ground=option
            if footprint&occupied or footprint&access or corridor&occupied:continue
            if kind!='housing' and (footprint&reserved or corridor&reserved):continue
            occupied.update(footprint);access.update(corridor-footprint)
            reserved.difference_update(footprint|corridor)
            if kind=='housing' and option in housing_reserve:housing_reserve.remove(option)
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
    # Reserve gatehouse footprints on the enceinte openings before street-front packing.
    placed_gates=0;placed_towers=0
    if fortifications['defended_perimeter'] and gate_def and 'plot_m' in gate_def:
        for gate in fortifications['gates']:
            x,z=gate['position_m'];approach=gate.get('approach_m') or [x+1,z]
            angle=math.atan2(approach[1]-z,approach[0]-x)
            degrees=round(math.degrees(angle),4)
            footprint=cells(x,z,gate_def['plot_m']['width'],gate_def['plot_m']['depth'],angle)
            ground=[sample.height_at(px,pz) for px,pz in corners(x,z,gate_def['plot_m']['width'],gate_def['plot_m']['depth'],angle)]
            ground+=[heights[c] for c in sorted(footprint) if c in heights] or [sample.height_at(x,z)]
            corridor=footprint
            if install(gate_def,'fortification','service',(x,z,degrees,x,z,footprint,corridor,ground)):
                placed_gates+=1;gate['plot_id']=result['plots'][-1]['id']
    tower_row=next((row for row in preset['buildings'] if row['structure_id']=='building.tower'),None)
    if fortifications['defended_perimeter'] and tower_row:
        for tower in fortifications['towers']:
            if placed_towers>=tower_budget:break
            x,z=tower['position_m'];degrees=0.
            footprint=cells(x,z,tower_row['plot_m']['width'],tower_row['plot_m']['depth'],0)
            if not footprint<=valid or footprint&road or footprint&occupied:continue
            ground=[sample.height_at(px,pz) for px,pz in corners(x,z,tower_row['plot_m']['width'],tower_row['plot_m']['depth'],0)]
            ground+=[heights[c] for c in sorted(footprint)]
            if install(tower_row,'fortification','service',(x,z,degrees,x,z,footprint,footprint,ground)):
                placed_towers+=1;tower['plot_id']=result['plots'][-1]['id']
    conditions={'usable_groundwater':False,'water_collection_or_delivery':site.get('freshwater_distance_m') is not None,
                'navigable_shore':False,'flowing_water':False,'reliable_wind':False,
                'ore_and_fuel_supply':site.get('resource_potential',0)>=.5,'food_surplus':False,
                'working_animals':False,'clay_and_fuel_supply':False,'medicinal_supply':facts['wooded_fraction']>.1,
                'clear_sky_view':True,'isolation_access':True,'defended_perimeter':fortifications['defended_perimeter']}
    high=[];low=[]
    for row in preset['buildings']:
        remaining=row['count']
        if row['structure_id']=='building.gatehouse':remaining=max(0,remaining-placed_gates)
        if row['structure_id']=='building.tower':remaining=max(0,remaining-placed_towers)
        if remaining<=0:continue
        missing=[c for c in row['placement_conditions'] if not conditions.get(c,False)]
        if missing:
            result['unplaced'].append({'building_id':row['structure_id'],'count':remaining,'reason':'Unverified prerequisite: '+', '.join(missing)})
            continue
        entry={**row,'count':remaining}
        (high if row['priority']=='core' else low).append(entry)
    def house_workers(phase):
        workers=sum(p['workers'] for p in result['plots']);beds=sum(p['beds'] for p in result['plots'])
        audit={'phase':phase,'workers':workers,'starting_beds':beds,'houses_placed':0,'upgrades':0,
               'plots_exhausted':False,'reserved_slots':len(housing_reserve)}
        while beds<workers:
            placement=housing_reserve[0] if housing_reserve else None
            if not install(house,phase,'housing',placement):
                if placement:
                    # Reserved slot became unusable; drop it and keep seeking free frontage.
                    housing_reserve.pop(0);reserved.difference_update(placement[5]|placement[6]);continue
                audit['plots_exhausted']=True;break
            audit['houses_placed']+=1
            beds+=house['worker_beds']
        # Replace existing dwellings in place: access and occupied land stay valid.
        for plot in result['plots']:
            if beds>=workers:break
            if plot['building_id']!=house['id']:continue
            audit['upgrades']+=1
            plot.setdefault('housing_upgrade',{'phase':phase,'previous':{k:plot[k] for k in ('building_id','name','dimensions_m','beds')}})
            beds+=apartment['worker_beds']-plot['beds']
            plot.update(building_id=apartment['id'],name=apartment['name'],dimensions_m=apartment['dimensions_m'],beds=apartment['worker_beds'])
        # Unused housing holds are released so later lower-priority services may use the land.
        while housing_reserve:
            option=housing_reserve.pop();reserved.difference_update(option[5]|option[6])
        audit.update(final_beds=beds,shortfall=max(0,workers-beds))
        result['debug']['housing_passes'].append(audit)
    for priority,rows in (('high',high),('low',low)):
        if priority=='low' and sum(p['workers']-p['beds'] for p in result['plots'])>0:
            result['unplaced'].extend({'building_id':r['structure_id'],'count':r['count'],'reason':'High-priority worker housing must be completed first'} for r in rows)
            break
        demand=sum(p['workers'] for p in result['plots'])
        demand+=sum(sum(r['target'] for r in row.get('staffing',{}).get('roles',[]))*row['count'] for row in rows)
        reserve_housing(demand)
        result['debug'].setdefault('housing_reservations',[]).append(
            {'phase':priority,'workers_budgeted':demand,'slots':len(housing_reserve)})
        for row in rows:
            failed=0
            for _ in range(row['count']):
                if not install(row,priority):failed+=1
            if failed:result['unplaced'].append({'building_id':row['structure_id'],'count':failed,'reason':'No terrain-safe plot with road access remaining'})
        house_workers(priority+'_housing')
    workers=sum(p['workers'] for p in result['plots']);beds=sum(p['beds'] for p in result['plots'])
    result['debug'].update(shape_safe_cells=len(valid),road_cells=len(road),occupied_cells=len(occupied),access_cells=len(access),
                           vacant_shape_cells=len(valid-road-occupied-access),
                           housing_frontage_candidates=free_frontage(house['plot_m']['width'],house['plot_m']['depth']),
                           fortification_rings=len(fortifications['rings']),program_half_m=half)
    core_ids={r['structure_id'] for r in preset['buildings'] if r['priority']=='core'}
    failed_core=sum(r['count'] for r in result['unplaced'] if r['building_id'] in core_ids)
    result['status']='complete' if not failed_core and beds>=workers else 'partial'
    result['stats']={'workers':workers,'worker_beds':beds,'housing_shortfall':max(0,workers-beds),
                     'service_buildings':sum(p['kind']=='service' for p in result['plots']),
                     'houses':sum(p['building_id']==house['id'] for p in result['plots']),
                     'apartments':sum(p['building_id']==apartment['id'] for p in result['plots']),
                     'unplaced_core':failed_core,'unplaced_total':sum(r['count'] for r in result['unplaced']),
                     **population_stats,
                     'reserved_plot_area_m2':sum(p['plot_m']['width']*p['plot_m']['depth'] for p in result['plots']),
                     'wall_segments':len(fortifications['segments']),'defended_perimeter':fortifications['defended_perimeter']}
    return result


# One city's plan is a pure function of (world, site, nearby_counts) -- it reads the
# world and never writes to it -- so the only thing serialising the cities is the shape
# repetition counter, which each city reads and the next one sees updated. Splitting that
# one dependency out lets the geometry, which is all of the cost, run in a pool.
_POOL_WORLD=None
_MIN_SITES_FOR_POOL=3


def _pool_init(blob):
    global _POOL_WORLD
    import pickle
    _POOL_WORLD=pickle.loads(blob)


def _pool_sites():
    return sorted(_POOL_WORLD['settlements']['sites'],key=lambda s:str(s.get('uid',s['id'])))


def _pool_facts(index):
    return plan_city(_POOL_WORLD,_pool_sites()[index],None,shape_only=True)


def _pool_plan(task):
    index,counts=task
    return plan_city(_POOL_WORLD,_pool_sites()[index],counts)


def _shape_counts(world,sites,facts):
    """The nearby_counts each city sees, in uid order, without planning any of them.

    This is the serial loop's counter and nothing else: fill_cities increments on the
    shape a city was given, and an authored city is given none, so it does not count.
    """
    counts={};seen=[]
    for site,fact in zip(sites,facts):
        seen.append(dict(counts))
        if site.get(FOUNDED_BY)==PLAYER:continue
        selected=select_shape(fact,world['config']['seed'],str(site.get('uid',site['id'])),
                              site['city_class'],counts)
        key=selected['shape_id']
        if key:counts[key]=counts.get(key,0)+1
    return seen


def _plan_serial(world,sites):
    cities=[];counts={}
    for site in sites:
        plan=plan_city(world,site,counts);cities.append(plan)
        key=plan['shape']['shape_id']
        if key:counts[key]=counts.get(key,0)+1
    return cities


def _plan_pooled(world,sites,workers):
    """Same plans, two passes. Falls back to the serial loop rather than failing.

    A process pool on a spawn platform re-imports the caller's __main__, so a caller
    that generates a world at import time instead of under `if __name__ == "__main__"`
    cannot use this. That is what the fallback is for; set workers=1 to skip it outright.
    """
    import os,pickle
    from concurrent.futures import ProcessPoolExecutor
    blob=pickle.dumps(world,protocol=pickle.HIGHEST_PROTOCOL)
    workers=min(workers or (os.cpu_count() or 1),len(sites))
    with ProcessPoolExecutor(max_workers=workers,initializer=_pool_init,initargs=(blob,)) as pool:
        facts=list(pool.map(_pool_facts,range(len(sites))))
        counts=_shape_counts(world,sites,facts)
        return list(pool.map(_pool_plan,list(enumerate(counts))))


def fill_cities(world,workers=None):
    sites=sorted(world['settlements']['sites'],key=lambda s:str(s.get('uid',s['id'])))
    env=os.environ.get('ICARUS_CITY_WORKERS')
    if workers is None and env:workers=int(env)
    cities=None
    if workers!=1 and len(sites)>=_MIN_SITES_FOR_POOL:
        # A world must still generate if the pool cannot start, so this falls back rather
        # than failing -- but a silent fallback is indistinguishable from a planner that
        # is simply slow, which is exactly the thing nobody would investigate. Say it.
        try:cities=_plan_pooled(world,sites,workers)
        except Exception as error:
            import warnings
            warnings.warn('City planning fell back to one process (%s: %s). A spawn platform '
                          're-imports the caller\'s __main__, so generation must happen under '
                          '`if __name__ == "__main__"` for the pool to start.'
                          %(type(error).__name__,error),RuntimeWarning,stacklevel=2)
            cities=None
    if cities is None:cities=_plan_serial(world,sites)
    world['city_plans']={'version':VERSION,'identity':planner_identity(),'cities':cities,
                         'phase_order':['map','shape','fortification','high','high_housing','low','low_housing'],
                         'scope':'Schematic local metres from final world raster; does not change simulated population.'}
    from .world_scene import build_scene
    build_scene(world)
    return world['city_plans']