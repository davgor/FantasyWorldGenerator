"""One globe coordinate boundary for regional roads, city streets and buildings."""
import math
from .terrain_globe import direction
from .terrain_detail import HeightField


def frame(world, site):
    n=world['config']['size'];r=world.get('effective_config',world['config'])['globe_radius']
    lat=math.pi/2-math.pi*site['z']/(n-1);lon=-math.pi+2*math.pi*site['x']/(n-1)
    up=(math.cos(lat)*math.cos(lon),math.sin(lat),math.cos(lat)*math.sin(lon))
    east=(-math.sin(lon),0.,math.cos(lon));north=(-math.sin(lat)*math.cos(lon),math.cos(lat),-math.sin(lat)*math.sin(lon))
    return r,up,east,north


def local_direction(f,x,z):
    r,up,east,north=f;p=[up[i]+(east[i]*x+north[i]*z)/r for i in range(3)]
    length=math.sqrt(sum(v*v for v in p));return [v/length for v in p]


def position(field,p,height=None):
    return [(field.radius+(field.height(p) if height is None else height))*v for v in p]


def road_entries(world,site,half):
    f=frame(world,site);r,up,east,north=f;n=world['config']['size'];points=world.get('water',{}).get('nodes',[])
    site_index=next((i for i,s in enumerate(world['settlements']['sites']) if s.get('uid',s['id'])==site.get('uid',site['id'])),None)
    entries=[]
    for ri,road in enumerate(world.get('roads',{}).get('routes',[])):
        if site_index not in (road['from'],road['to']):continue
        reverse=site_index==road['to'];indices=list(reversed(road['nodes'])) if reverse else road['nodes']
        prev=(0.,0.)
        for k,index in enumerate(indices):
            p=direction(*points[index],n);den=sum(a*b for a,b in zip(p,up))
            if den<=0:break
            q=(r*sum(a*b for a,b in zip(p,east))/den,r*sum(a*b for a,b in zip(p,north))/den)
            if max(abs(v) for v in q)>half:
                ts=[((half if q[j]>0 else -half)-prev[j])/(q[j]-prev[j]) for j in (0,1) if abs(q[j])>half]
                t=min(ts);gate=[prev[j]+t*(q[j]-prev[j]) for j in (0,1)]
                entries.append({'route_id':f'regional-road-{ri}','route_index':ri,'end':'to' if reverse else 'from',
                    'outside_index':len(indices)-1-k if reverse else k,
                    'junction_id':f'junction:{site.get("uid",site["id"])}:{ri}',
                    'gate_local_m':gate,'direction':local_direction(f,*gate),
                    'status':'unreachable','reason':'No terrain-safe street connection to regional road'})
                break
            prev=q
    return entries


def _emit_local_plan(scene,world,field,site,plan,*,settlement_kind,uid_field,uid_value,gates=None):
    f=frame(world,site)
    tag={'settlement_kind':settlement_kind,uid_field:uid_value}
    for i,path in enumerate(plan.get('street_paths_m',[])):
        scene['streets'].append({'id':f'{uid_value}:street:{i}',**tag,
            'positions_m':[position(field,local_direction(f,*p)) for p in path]})
    for c in plan.get('road_connections',[]):
        if gates is not None and c.get('route_index',-1)>=0:
            gates[(c['route_index'],c['end'])]=c
        pos=position(field,c['direction'])
        scene['junctions'].append({'id':c['junction_id'],**tag,'route_id':c['route_id'],
                                  'position_m':pos,'status':c['status']})
        if c['status']=='connected':
            vertices=[position(field,local_direction(f,*p)) for p in c['local_path_m']]
            vertices[-1]=pos
            scene['streets'].append({'id':c['junction_id']+':approach',**tag,
                                    'junction_id':c['junction_id'],'positions_m':vertices})
    for b in plan['plots']:
        p=local_direction(f,b['x_m'],b['z_m']);angle=math.radians(b['rotation_degrees'])
        dot=sum(a*v for a,v in zip(f[2],p));east=[a-dot*v for a,v in zip(f[2],p)]
        length=math.sqrt(sum(v*v for v in east));east=[v/length for v in east]
        north=[east[1]*p[2]-east[2]*p[1],east[2]*p[0]-east[0]*p[2],east[0]*p[1]-east[1]*p[0]]
        width_axis=[a*math.cos(angle)+v*math.sin(angle) for a,v in zip(east,north)]
        depth_axis=[-a*math.sin(angle)+v*math.cos(angle) for a,v in zip(east,north)]
        center=position(field,p,b['ground_elevation_m'])
        scene['buildings'].append({'id':f'{uid_value}:{b["id"]}',**tag,
             'plot_id':b['id'],'asset_id':b['building_id'],'position_m':center,
             'up':p,'width_axis':width_axis,'depth_axis':depth_axis,
             'rotation_degrees':b['rotation_degrees'],'dimensions_m':b['dimensions_m'],
             'footprint_positions_m':[[center[k]+u*width_axis[k]+v*depth_axis[k] for k in range(3)]
                for u,v in ((-b['dimensions_m']['width']/2,-b['dimensions_m']['depth']/2),(b['dimensions_m']['width']/2,-b['dimensions_m']['depth']/2),(b['dimensions_m']['width']/2,b['dimensions_m']['depth']/2),(-b['dimensions_m']['width']/2,b['dimensions_m']['depth']/2))]})


def build_scene(world):
    field=HeightField(world);n=world['config']['size'];points=world.get('water',{}).get('nodes',[])
    scene={'version':1,'unit':'metres','coordinates':'globe-centred XYZ; Y north; X at latitude 0 longitude 0; Z at latitude 0 longitude 90',
           'radius_m':field.radius,'terrain_detail':world.get('terrain_detail'),
           'buildings':[],'streets':[],'junctions':[],'regional_roads':[],
           'limits':'Regional routes remain coarse transport proposals, including unengineered bridge candidates; local connection failures are explicit. Hamlet entries are tagged settlement_kind=hamlet and castle entries settlement_kind=castle; both remain filterable from city payloads.'}
    gates={}
    for city in world.get('city_plans',{}).get('cities',[]):
        site=next(s for s in world['settlements']['sites'] if s.get('uid',str(s['id']))==city['city_uid'])
        _emit_local_plan(scene,world,field,site,city,settlement_kind='city',uid_field='city_uid',
                         uid_value=city['city_uid'],gates=gates)
    for plan in world.get('hamlet_plans',{}).get('hamlets',[]):
        site={'x':plan['x'],'z':plan['z'],'id':plan['hamlet_id'],'uid':plan['hamlet_id']}
        _emit_local_plan(scene,world,field,site,plan,settlement_kind='hamlet',uid_field='hamlet_id',
                         uid_value=plan['hamlet_id'])
    for plan in world.get('castle_plans',{}).get('castles',[]):
        site={'x':plan['x'],'z':plan['z'],'id':plan['fortress_id'],'uid':plan['fortress_id']}
        _emit_local_plan(scene,world,field,site,plan,settlement_kind='castle',uid_field='fortress_id',
                         uid_value=plan['fortress_id'])
    for i,road in enumerate(world.get('roads',{}).get('routes',[])):
        a=gates.get((i,'from'));b=gates.get((i,'to'))
        lo=a['outside_index'] if a else 0;hi=b['outside_index']+1 if b else len(road['nodes'])
        vectors=[direction(*points[k],n) for k in road['nodes'][lo:hi]]
        if a:vectors.insert(0,a['direction'])
        if b:vectors.append(b['direction'])
        # Densify the regional polyline onto the same surface; route topology is unchanged.
        dense=[]
        for p,q in zip(vectors,vectors[1:]):
            count=max(1,math.ceil(field.radius*math.acos(max(-1,min(1,sum(x*y for x,y in zip(p,q)))))/4))
            for k in range(count):
                v=[x+(y-x)*k/count for x,y in zip(p,q)];length=math.sqrt(sum(x*x for x in v));dense.append([x/length for x in v])
        if vectors:dense.append(vectors[-1])
        vertices=[position(field,p) for p in dense]
        if a and vertices:vertices[0]=position(field,a['direction'])
        if b and vertices:vertices[-1]=position(field,b['direction'])
        scene['regional_roads'].append({'id':f'regional-road-{i}','source_route_index':i,'positions_m':vertices,
            'from_junction':a['junction_id'] if a else None,'to_junction':b['junction_id'] if b else None,
            'from_status':a['status'] if a else 'no_city_boundary','to_status':b['status'] if b else 'no_city_boundary',
            'bridge_candidates':road.get('river_crossings',[])})
    world['world_scene']=scene
    return scene
