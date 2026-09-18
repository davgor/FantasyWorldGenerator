"""City-only defensive rings: polylines, segments and gate openings (metres)."""
import math

VERSION=1


def path_turn_degrees(a, b, c):
    """Signed heading change of polyline a→b→c, degrees in (-180, 180]."""
    delta=math.degrees(math.atan2(c[1]-b[1], c[0]-b[0])-math.atan2(b[1]-a[1], b[0]-a[0]))
    while delta<=-180:delta+=360
    while delta>180:delta-=360
    return delta


def smooth_closed_ring(points, max_turn_degrees=95, radius_factor=1.12, passes=12):
    """Pull in needle vertices so an enceinte cannot form one giant outward point."""
    if len(points)<8:
        return [tuple(p) for p in points]
    pts=[(float(p[0]), float(p[1])) for p in points]
    n=len(pts)
    cx=sum(p[0] for p in pts)/n
    cz=sum(p[1] for p in pts)/n
    for _ in range(passes):
        radii=[math.hypot(p[0]-cx, p[1]-cz) or 1.0 for p in pts]
        nxt=[]
        for i,point in enumerate(pts):
            cap=radius_factor*max(radii[(i-1)%n], radii[(i+1)%n])
            r=min(radii[i], cap)
            ux,uz=(point[0]-cx)/radii[i], (point[1]-cz)/radii[i]
            nxt.append((cx+ux*r, cz+uz*r))
        pts=nxt
        nxt=[]
        for i,point in enumerate(pts):
            prev,following=pts[(i-1)%n], pts[(i+1)%n]
            if abs(path_turn_degrees(prev, point, following))>max_turn_degrees:
                nxt.append(((prev[0]+2*point[0]+following[0])/4, (prev[1]+2*point[1]+following[1])/4))
            else:
                nxt.append(point)
        pts=nxt
    return [(round(p[0], 2), round(p[1], 2)) for p in pts]


def program_half_m(preset,city_class,neighbour_half,house_plot=(12,16),beds_per_house=4):
    """Grow the city crop from class minimum toward program demand, capped by neighbours."""
    base={'small':240,'medium':320,'capital':400}[city_class]
    plot_area=sum(row['plot_m']['width']*row['plot_m']['depth']*row['count'] for row in preset['buildings'])
    workers=sum(sum(r['target'] for r in row.get('staffing',{}).get('roles',[]))*row['count'] for row in preset['buildings'])
    houses=math.ceil(workers/max(1,beds_per_house))
    plot_area+=houses*house_plot[0]*house_plot[1]
    # Streets, wall reserve and access corridors roughly double service/housing land.
    needed=math.sqrt(max(plot_area,1)*2.4)/2*1.15
    half=min(float(neighbour_half),max(base,needed))
    return max(4,int(half/4)*4)


def ring_count_for(shape_id,parameters,city_class):
    if shape_id=='concentric_enceintes':
        return max(2,min(3,int(parameters.get('ring_count',3))))
    if city_class in ('medium','capital'):return 1
    return 0


def _boundary_points(valid,half,cell,rx,rz,scale,family):
    """Angular samples of the outermost valid cell on each ray, clipped to the shape scale."""
    if not valid:return []
    cx=sum(c[0] for c in valid)/len(valid);cz=sum(c[1] for c in valid)/len(valid)
    points=[]
    for i in range(48):
        angle=2*math.pi*i/48
        dx,dz=math.cos(angle),math.sin(angle)
        best=None
        for dist in range(1,max(1,int(max(rx,rz)/cell)+2)):
            x=cx+dx*dist;z=cz+dz*dist
            cell_i=(int(math.floor(x)),int(math.floor(z)))
            if cell_i not in valid:break
            ex=-half+(cell_i[0]+.5)*cell;ez=-half+(cell_i[1]+.5)*cell
            if family in ('grid','compound','hybrid'):
                if abs(ex)>rx*scale or abs(ez)>rz*scale:break
            elif family=='cluster':
                if all((ex-ox)**2+(ez-oz)**2>=(half*.52*scale)**2 for ox,oz in ((-half*.32,0),(half*.32,0),(0,half*.25))):break
            else:
                if (ex/(rx*scale))**2+(ez/(rz*scale))**2>=1:break
            best=(round(ex,2),round(ez,2))
        if best:points.append(best)
    return points


def _segmentize(polyline,segment_depth_m,structure_id,ring_id):
    if len(polyline)<2:return [],[]
    segments=[];nodes=[]
    for i,point in enumerate(polyline):
        nodes.append({'id':f'{ring_id}-node-{i}','kind':'corner','position_m':list(point),'ring_id':ring_id})
    closed=polyline+[polyline[0]]
    seg_i=0;carry=0.;path=[]
    for a,b in zip(closed,closed[1:]):
        path.append(a)
        edge=math.dist(a,b)
        while carry+edge>=segment_depth_m-.01:
            need=segment_depth_m-carry
            t=need/edge if edge else 0
            end=(round(a[0]+(b[0]-a[0])*t,2),round(a[1]+(b[1]-a[1])*t,2))
            start=path[-1] if path else a
            mid=((start[0]+end[0])/2,(start[1]+end[1])/2)
            heading=math.degrees(math.atan2(end[1]-start[1],end[0]-start[0]))
            segments.append({'id':f'{ring_id}-seg-{seg_i}','ring_id':ring_id,'structure_id':structure_id,
                             'from_m':list(start),'to_m':list(end),'center_m':[round(mid[0],2),round(mid[1],2)],
                             'length_m':round(math.dist(start,end),3),'rotation_degrees':round(heading-90,4)})
            seg_i+=1;path=[end];a=end;edge=math.dist(a,b);carry=0.
        carry+=edge
    return segments,nodes


def _gate_sites(polyline,road_connections,gate_budget):
    if not polyline or gate_budget<=0:return []
    candidates=[]
    for conn in road_connections or []:
        if conn.get('status')!='connected':continue
        gate=conn.get('gate_local_m')
        if not gate:continue
        best=min(range(len(polyline)),key=lambda i:math.dist(polyline[i],gate))
        candidates.append((math.dist(polyline[best],gate),best,conn.get('route_index'),gate))
    candidates.sort()
    chosen=[];used=set()
    for dist,idx,route,gate in candidates:
        if idx in used or dist>48:continue
        used.add(idx);chosen.append({'ring_vertex':idx,'route_index':route,'position_m':list(polyline[idx]),
                                     'approach_m':list(gate)})
        if len(chosen)>=gate_budget:break
    if not chosen and polyline:
        # Ensure at least one schematic gate on the primary approach axis.
        idx=min(range(len(polyline)),key=lambda i:abs(polyline[i][1])+abs(polyline[i][0]-max(p[0] for p in polyline)))
        chosen.append({'ring_vertex':idx,'route_index':None,'position_m':list(polyline[idx]),'approach_m':list(polyline[idx])})
    return chosen[:gate_budget]


def build_fortifications(*,valid,half,cell,rx,rz,family,shape_id,parameters,city_class,
                         road_connections,wall_structure,gate_structure,tower_budget,gate_budget):
    """Return city fortification export; defended_perimeter is true only when a ring closes."""
    rings_wanted=ring_count_for(shape_id,parameters,city_class)
    report={'version':VERSION,'defended_perimeter':False,'rings':[],'segments':[],'nodes':[],'gates':[],
            'towers':[],'unplaced':[],'method':'Angular boundary samples of the buildable shape; city-only wall network.',
            'limits':'Schematic enceinte, not structural engineering. Castle baileys use a separate generator.'}
    if rings_wanted<=0 or not valid or not wall_structure:
        if rings_wanted>0:report['unplaced'].append({'building_id':wall_structure['id'] if wall_structure else 'building.wall',
                                                    'reason':'No buildable perimeter for fortification'})
        return report
    scales=[1.0] if rings_wanted==1 else [0.45+(i/(rings_wanted-1))*0.55 for i in range(rings_wanted)]
    segment_depth=wall_structure['dimensions_m']['depth']
    for ring_i,scale in enumerate(scales):
        ring_id=f'ring-{ring_i}'
        role='outer' if ring_i==rings_wanted-1 else 'inner' if ring_i==0 else 'middle'
        points=smooth_closed_ring(_boundary_points(valid,half,cell,rx,rz,scale,family))
        if len(points)<8:
            report['unplaced'].append({'building_id':wall_structure['id'],'ring_id':ring_id,
                                       'reason':'Perimeter could not close on buildable land'})
            continue
        segments,nodes=_segmentize(points,segment_depth,wall_structure['id'],ring_id)
        if len(segments)<6:
            report['unplaced'].append({'building_id':wall_structure['id'],'ring_id':ring_id,
                                       'reason':'Insufficient continuous wall segments'})
            continue
        gates=_gate_sites(points,road_connections if role=='outer' else [],
                          gate_budget if role=='outer' else max(1,gate_budget//2))
        gate_records=[]
        for g_i,gate in enumerate(gates):
            gate_records.append({'id':f'{ring_id}-gate-{g_i}','ring_id':ring_id,
                                 'structure_id':gate_structure['id'] if gate_structure else 'building.gatehouse',
                                 'position_m':gate['position_m'],'approach_m':gate['approach_m'],
                                 'route_index':gate['route_index']})
        # Drop wall segments that collide with gate centres.
        keep=[]
        for seg in segments:
            if any(math.dist(seg['center_m'],g['position_m'])<max(8,segment_depth*.6) for g in gate_records):
                continue
            keep.append(seg)
        towers=[]
        step=max(1,len(nodes)//max(1,tower_budget if role=='outer' else max(1,tower_budget//2)))
        for t_i,node in enumerate(nodes[::step][:max(1,tower_budget if role=='outer' else 2)]):
            towers.append({'id':f'{ring_id}-tower-{t_i}','ring_id':ring_id,'structure_id':'building.tower',
                           'position_m':node['position_m']})
        report['rings'].append({'id':ring_id,'role':role,'scale':round(scale,4),'polyline_m':[list(p) for p in points],
                                'status':'closed','segment_count':len(keep),'gate_count':len(gate_records)})
        report['segments'].extend(keep);report['nodes'].extend(nodes)
        report['gates'].extend(gate_records);report['towers'].extend(towers)
    report['defended_perimeter']=any(r['status']=='closed' for r in report['rings'])
    return report


def wall_and_gate_defs(preset):
    structures={row['structure_id']:row for row in preset.get('infrastructure',[])}
    buildings={row['structure_id']:row for row in preset.get('buildings',[])}
    wall=structures.get('building.wall') or buildings.get('building.wall')
    gate=buildings.get('building.gatehouse') or structures.get('building.gatehouse')
    # Fall back to catalogue dimensions when infrastructure rows omit measured fields.
    if wall and 'dimensions_m' not in wall:
        wall={**wall,'dimensions_m':{'width':3,'depth':10,'height':7},'id':wall.get('structure_id','building.wall')}
    elif wall:wall={**wall,'id':wall.get('structure_id',wall.get('id','building.wall'))}
    if gate:gate={**gate,'id':gate.get('structure_id',gate.get('id','building.gatehouse'))}
    return wall,gate
