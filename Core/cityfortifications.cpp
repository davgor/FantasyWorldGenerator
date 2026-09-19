#include "cityfortifications.hpp"
#include "counter.hpp"
#include "globe.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
namespace fantasy_world_generator {
namespace {
// math.degrees multiplies by this constant; it does not divide by pi.
constexpr double rad_to_deg=180.0/pi;
// int() on a float truncates towards zero. Python's result is unbounded, so clamp
// before the cast rather than after: every caller here feeds the value straight into a
// min()/max() that a saturated value passes through identically.
std::int64_t python_int(double value) {
    if(value>=9.2233720368547758e18) return INT64_MAX;
    if(value<=-9.2233720368547758e18) return INT64_MIN;
    return static_cast<std::int64_t>(value);
}
// Python's // floors towards negative infinity; C++ integer division truncates.
std::int64_t floor_div(std::int64_t value,std::int64_t divisor) {
    std::int64_t quotient=value/divisor;
    if(value%divisor!=0 && ((value<0)!=(divisor<0))) --quotient;
    return quotient;
}
// math.dist over two points is math.hypot of the differences: both run CPython's own
// vector_norm, which differs from the platform hypot in the last bit.
double point_distance(const std::pair<double,double>& a,const std::pair<double,double>& b) {
    return python_hypot(a.first-b.first,a.second-b.second);
}
}
// Python's round(x, ndigits) is not nearbyint(x*10**n)/10**n. The reference formats the
// value to ndigits decimals with correct round-half-even (_Py_dg_dtoa in mode 3) and
// reads that decimal back correctly rounded (_Py_dg_strtod). The CRT's printf and
// strtod are the same pair of correctly rounded conversions, so this reproduces it,
// ties included: round(0.125, 2) is 0.12, not 0.13.
double fortification_round_digits(double value,int digits) {
    if(!std::isfinite(value)) return value;
    // The widest finite double needs 309 integer digits, a sign, a point and the
    // fractional digits; this slice only ever asks for two to four of those.
    char buffer[400];
    const int written=std::snprintf(buffer,sizeof buffer,"%.*f",digits,value);
    if(written<0 || static_cast<std::size_t>(written)>=sizeof buffer) return value;
    return std::strtod(buffer,nullptr);
}
double path_turn_degrees(const std::pair<double,double>& a,const std::pair<double,double>& b,
                         const std::pair<double,double>& c) {
    double delta=(std::atan2(c.second-b.second,c.first-b.first)
                 -std::atan2(b.second-a.second,b.first-a.first))*rad_to_deg;
    while(delta<=-180.) delta+=360.;
    while(delta>180.) delta-=360.;
    return delta;
}
std::vector<std::pair<double,double>> smooth_closed_ring(
        const std::vector<std::pair<double,double>>& points,double max_turn_degrees,
        double radius_factor,std::int64_t passes) {
    // Too short to have a needle: the reference hands the points straight back, and
    // notably does not round them. Castle geometry relies on that.
    if(points.size()<8) return points;
    std::vector<std::pair<double,double>> pts=points;
    const std::size_t n=pts.size();
    // The reference converts every coordinate to float before summing, so both of
    // these are float sums and carry CPython's Neumaier compensation.
    Sum sum_x,sum_z;
    for(const auto& point:pts) sum_x.add(point.first);
    for(const auto& point:pts) sum_z.add(point.second);
    const double cx=sum_x.value()/static_cast<double>(n);
    const double cz=sum_z.value()/static_cast<double>(n);
    std::vector<double> radii(n);
    std::vector<std::pair<double,double>> next(n);
    for(std::int64_t pass=0;pass<passes;++pass) {
        for(std::size_t i=0;i<n;++i) {
            const double radius=python_hypot(pts[i].first-cx,pts[i].second-cz);
            // `or 1.0`: a vertex exactly on the centroid keeps a unit radius, and that
            // substituted radius is what the projection below divides by.
            radii[i]=radius!=0.?radius:1.;
        }
        for(std::size_t i=0;i<n;++i) {
            // (i-1)%n at i==0 is n-1 in Python, which floors; C++ would give -1.
            const double cap=radius_factor*std::max(radii[(i+n-1)%n],radii[(i+1)%n]);
            const double r=std::min(radii[i],cap);
            const double ux=(pts[i].first-cx)/radii[i],uz=(pts[i].second-cz)/radii[i];
            next[i]={cx+ux*r,cz+uz*r};
        }
        pts=next;
        for(std::size_t i=0;i<n;++i) {
            const std::pair<double,double>& previous=pts[(i+n-1)%n];
            const std::pair<double,double>& point=pts[i];
            const std::pair<double,double>& following=pts[(i+1)%n];
            if(std::fabs(path_turn_degrees(previous,point,following))>max_turn_degrees)
                next[i]={(previous.first+2*point.first+following.first)/4,
                         (previous.second+2*point.second+following.second)/4};
            else next[i]=point;
        }
        pts=next;
    }
    for(auto& point:pts)
        point={fortification_round_digits(point.first,2),fortification_round_digits(point.second,2)};
    return pts;
}
std::int64_t program_half_m(const FortificationPreset& preset,const std::string& city_class,
                            double neighbour_half,double house_plot_width,double house_plot_depth,
                            std::int64_t beds_per_house) {
    double base;
    if(city_class=="small") base=240.;
    else if(city_class=="medium") base=320.;
    else if(city_class=="capital") base=400.;
    else throw Error("INVALID_INPUT");  // the reference raises KeyError here.
    // Both of these are sum() over the catalogue's integers, where Python stays in
    // exact integer arithmetic. Every term is a small exact integer, so a compensated
    // double sum reproduces that exactly, and it is also what the reference would do
    // had any row carried a measured float.
    Sum plot;
    for(const FortificationPresetRow& row:preset.buildings)
        plot.add(row.plot_width*row.plot_depth*row.count);
    double plot_area=plot.value();
    Sum staff;
    for(const FortificationPresetRow& row:preset.buildings) {
        // The inner sum() over the staffing roles, empty when a row has no staffing.
        Sum roles;
        for(double target:row.role_targets) roles.add(target);
        staff.add(roles.value()*row.count);
    }
    const double workers=staff.value();
    const double houses=std::ceil(workers/static_cast<double>(std::max<std::int64_t>(1,beds_per_house)));
    plot_area+=houses*house_plot_width*house_plot_depth;
    // Streets, wall reserve and access corridors roughly double service/housing land.
    const double needed=std::sqrt(std::max(plot_area,1.)*2.4)/2*1.15;
    const double half=std::min(neighbour_half,std::max(base,needed));
    const std::int64_t quarters=python_int(half/4);
    // Python multiplies unbounded integers and then clamps at 4; saturating here is
    // the same answer for every half a city can have, and defined behaviour.
    if(quarters>INT64_MAX/4) return INT64_MAX;
    if(quarters<1) return 4;
    return std::max<std::int64_t>(4,quarters*4);
}
std::int64_t ring_count_for(const std::string& shape_id,
                            const FortificationShapeParameters& parameters,
                            const std::string& city_class) {
    if(shape_id=="concentric_enceintes") {
        const double raw=parameters.has_ring_count?parameters.ring_count:3.;
        return std::max<std::int64_t>(2,std::min<std::int64_t>(3,python_int(raw)));
    }
    if(city_class=="medium" || city_class=="capital") return 1;
    return 0;
}
std::vector<std::pair<double,double>> fortification_boundary_points(
        const std::set<Cell>& valid,double half,double cell,double rx,double rz,double scale,
        const std::string& family) {
    std::vector<std::pair<double,double>> points;
    if(valid.empty()) return points;
    // sum() over the cell indices of a set: integers, so Python sums them exactly and
    // the set's iteration order cannot move the centroid. Integer division by len()
    // is CPython's correctly rounded long/long, which for cell counts that fit a
    // double is the same as dividing the two doubles.
    std::int64_t total_x=0,total_z=0;
    for(const Cell& c:valid) {total_x+=c.first;total_z+=c.second;}
    const double count=static_cast<double>(valid.size());
    const double cx=static_cast<double>(total_x)/count;
    const double cz=static_cast<double>(total_z)/count;
    const std::int64_t span=std::max<std::int64_t>(1,python_int(std::max(rx,rz)/cell)+2);
    const double reach=std::pow(half*.52*scale,2.);
    const double centres[3][2]={{-half*.32,0.},{half*.32,0.},{0.,half*.25}};
    for(std::int64_t i=0;i<48;++i) {
        const double angle=2*pi*static_cast<double>(i)/48;
        const double dx=std::cos(angle),dz=std::sin(angle);
        bool found=false;
        std::pair<double,double> best{0.,0.};
        for(std::int64_t dist=1;dist<span;++dist) {
            const double x=cx+dx*static_cast<double>(dist),z=cz+dz*static_cast<double>(dist);
            // math.floor before the cast: a cast alone truncates towards zero and
            // would shift every ray on the negative side of the raster by a cell.
            const Cell here(static_cast<std::int64_t>(std::floor(x)),
                            static_cast<std::int64_t>(std::floor(z)));
            if(valid.count(here)==0) break;
            const double ex=-half+(static_cast<double>(here.first)+.5)*cell;
            const double ez=-half+(static_cast<double>(here.second)+.5)*cell;
            if(family=="grid" || family=="compound" || family=="hybrid") {
                if(std::fabs(ex)>rx*scale || std::fabs(ez)>rz*scale) break;
            } else if(family=="cluster") {
                // all(...) over the three lobes: outside every one of them ends the ray.
                bool outside_all=true;
                for(const auto& centre:centres)
                    if(!(std::pow(ex-centre[0],2.)+std::pow(ez-centre[1],2.)>=reach))
                        {outside_all=false;break;}
                if(outside_all) break;
            } else {
                // organic, contour, rings and paired lobes share an elliptical clip.
                // x**2 on a Python float is libm pow, not x*x.
                if(std::pow(ex/(rx*scale),2.)+std::pow(ez/(rz*scale),2.)>=1.) break;
            }
            best={fortification_round_digits(ex,2),fortification_round_digits(ez,2)};
            found=true;
        }
        // The reference tests `if best`, and a coordinate pair is never falsy, so this
        // is a None test: a point at the origin still counts.
        if(found) points.push_back(best);
    }
    return points;
}
void fortification_segmentize(const std::vector<std::pair<double,double>>& polyline,
                              double segment_depth_m,const std::string& structure_id,
                              const std::string& ring_id,
                              std::vector<FortificationSegment>& segments,
                              std::vector<FortificationNode>& nodes) {
    segments.clear();
    nodes.clear();
    if(polyline.size()<2) return;
    for(std::size_t i=0;i<polyline.size();++i) {
        FortificationNode node;
        node.id=ring_id+"-node-"+std::to_string(i);
        node.kind="corner";
        node.ring_id=ring_id;
        node.position_m=polyline[i];
        nodes.push_back(node);
    }
    std::vector<std::pair<double,double>> closed=polyline;
    closed.push_back(polyline[0]);
    std::int64_t seg_i=0;
    double carry=0.;
    // The reference's `path` is never cleared between edges, only replaced by the last
    // split point, so a segment starts at the most recent vertex rather than at the
    // previous segment's end whenever a vertex fell in between.
    std::vector<std::pair<double,double>> path;
    for(std::size_t index=0;index+1<closed.size();++index) {
        std::pair<double,double> a=closed[index];
        const std::pair<double,double> b=closed[index+1];
        path.push_back(a);
        double edge=point_distance(a,b);
        while(carry+edge>=segment_depth_m-.01) {
            const double need=segment_depth_m-carry;
            const double t=edge!=0.?need/edge:0.;
            const std::pair<double,double> end{fortification_round_digits(a.first+(b.first-a.first)*t,2),
                                               fortification_round_digits(a.second+(b.second-a.second)*t,2)};
            const std::pair<double,double> start=path.empty()?a:path.back();
            const std::pair<double,double> mid{(start.first+end.first)/2,(start.second+end.second)/2};
            const double heading=std::atan2(end.second-start.second,end.first-start.first)*rad_to_deg;
            FortificationSegment segment;
            segment.id=ring_id+"-seg-"+std::to_string(seg_i);
            segment.ring_id=ring_id;
            segment.structure_id=structure_id;
            segment.from_m=start;
            segment.to_m=end;
            segment.center_m={fortification_round_digits(mid.first,2),fortification_round_digits(mid.second,2)};
            segment.length_m=fortification_round_digits(point_distance(start,end),3);
            segment.rotation_degrees=fortification_round_digits(heading-90,4);
            segments.push_back(segment);
            ++seg_i;
            path.assign(1,end);
            a=end;
            edge=point_distance(a,b);
            carry=0.;
        }
        carry+=edge;
    }
}
std::vector<FortificationGateSite> fortification_gate_sites(
        const std::vector<std::pair<double,double>>& polyline,
        const std::vector<FortificationRoadConnection>& road_connections,std::int64_t gate_budget) {
    std::vector<FortificationGateSite> chosen;
    if(polyline.empty() || gate_budget<=0) return chosen;
    struct Candidate {
        double distance=0.;
        std::int64_t vertex=0;
        bool has_route=false;
        std::int64_t route=0;
        std::pair<double,double> gate{0.,0.};
    };
    std::vector<Candidate> candidates;
    for(const FortificationRoadConnection& conn:road_connections) {
        if(conn.status!="connected") continue;
        // An absent or empty gate point is falsy in the reference.
        if(!conn.has_gate) continue;
        std::size_t best=0;
        double best_distance=0.;
        for(std::size_t i=0;i<polyline.size();++i) {
            const double distance=point_distance(polyline[i],conn.gate_local_m);
            // min(..., key=...) keeps the first minimum: only a strictly smaller key wins.
            if(i==0 || distance<best_distance) {best=i;best_distance=distance;}
        }
        Candidate candidate;
        candidate.distance=point_distance(polyline[best],conn.gate_local_m);
        candidate.vertex=static_cast<std::int64_t>(best);
        candidate.has_route=conn.has_route_index;
        candidate.route=conn.route_index;
        candidate.gate=conn.gate_local_m;
        candidates.push_back(candidate);
    }
    // list.sort() on the tuples (distance, vertex, route_index, gate), element by
    // element. Reaching a missing route_index would raise TypeError in the reference,
    // so the ordering chosen for it only covers a case the reference itself refuses.
    std::stable_sort(candidates.begin(),candidates.end(),
                     [](const Candidate& a,const Candidate& b) {
        if(a.distance!=b.distance) return a.distance<b.distance;
        if(a.vertex!=b.vertex) return a.vertex<b.vertex;
        if(a.has_route!=b.has_route) return !a.has_route;
        if(a.has_route && a.route!=b.route) return a.route<b.route;
        if(a.gate.first!=b.gate.first) return a.gate.first<b.gate.first;
        return a.gate.second<b.gate.second;
    });
    std::set<std::int64_t> used;
    for(const Candidate& candidate:candidates) {
        if(used.count(candidate.vertex)!=0 || candidate.distance>48.) continue;
        used.insert(candidate.vertex);
        FortificationGateSite site;
        site.ring_vertex=candidate.vertex;
        site.has_route_index=candidate.has_route;
        site.route_index=candidate.route;
        site.position_m=polyline[static_cast<std::size_t>(candidate.vertex)];
        site.approach_m=candidate.gate;
        chosen.push_back(site);
        if(static_cast<std::int64_t>(chosen.size())>=gate_budget) break;
    }
    if(chosen.empty()) {
        // Ensure at least one schematic gate on the primary approach axis.
        double furthest=polyline[0].first;
        for(const auto& point:polyline) furthest=std::max(furthest,point.first);
        std::size_t idx=0;
        double best_key=0.;
        for(std::size_t i=0;i<polyline.size();++i) {
            const double key=std::fabs(polyline[i].second)+std::fabs(polyline[i].first-furthest);
            if(i==0 || key<best_key) {idx=i;best_key=key;}
        }
        FortificationGateSite site;
        site.ring_vertex=static_cast<std::int64_t>(idx);
        site.has_route_index=false;
        site.position_m=polyline[idx];
        site.approach_m=polyline[idx];
        chosen.push_back(site);
    }
    if(static_cast<std::int64_t>(chosen.size())>gate_budget)
        chosen.resize(static_cast<std::size_t>(gate_budget));
    return chosen;
}
std::pair<FortificationStructure,FortificationStructure> wall_and_gate_defs(
        const FortificationPreset& preset) {
    // The reference builds two dicts keyed by structure_id, so a repeated row wins.
    const FortificationPresetRow* structure_wall=nullptr;
    const FortificationPresetRow* structure_gate=nullptr;
    const FortificationPresetRow* building_wall=nullptr;
    const FortificationPresetRow* building_gate=nullptr;
    for(const FortificationPresetRow& row:preset.infrastructure) {
        if(row.structure_id=="building.wall") structure_wall=&row;
        else if(row.structure_id=="building.gatehouse") structure_gate=&row;
    }
    for(const FortificationPresetRow& row:preset.buildings) {
        if(row.structure_id=="building.wall") building_wall=&row;
        else if(row.structure_id=="building.gatehouse") building_gate=&row;
    }
    const FortificationPresetRow* wall=structure_wall!=nullptr?structure_wall:building_wall;
    const FortificationPresetRow* gate=building_gate!=nullptr?building_gate:structure_gate;
    FortificationStructure wall_def,gate_def;
    if(wall!=nullptr) {
        wall_def.present=true;
        wall_def.has_dimensions=true;
        if(!wall->has_dimensions) {
            // Fall back to catalogue dimensions when an infrastructure row omits the
            // measured fields.
            wall_def.width=3.;wall_def.depth=10.;wall_def.height=7.;
            wall_def.id=wall->structure_id.empty()?"building.wall":wall->structure_id;
        } else {
            wall_def.width=wall->width;wall_def.depth=wall->depth;wall_def.height=wall->height;
            wall_def.id=!wall->structure_id.empty()?wall->structure_id
                        :!wall->id.empty()?wall->id:"building.wall";
        }
    }
    if(gate!=nullptr) {
        gate_def.present=true;
        gate_def.has_dimensions=gate->has_dimensions;
        gate_def.width=gate->width;gate_def.depth=gate->depth;gate_def.height=gate->height;
        gate_def.id=!gate->structure_id.empty()?gate->structure_id
                    :!gate->id.empty()?gate->id:"building.gatehouse";
    }
    return {wall_def,gate_def};
}
FortificationReport build_fortifications(const std::set<Cell>& valid,double half,double cell,
                                         double rx,double rz,const std::string& family,
                                         const std::string& shape_id,
                                         const FortificationShapeParameters& parameters,
                                         const std::string& city_class,
                                         const std::vector<FortificationRoadConnection>& road_connections,
                                         const FortificationStructure& wall_structure,
                                         const FortificationStructure& gate_structure,
                                         std::int64_t tower_budget,std::int64_t gate_budget) {
    const std::int64_t rings_wanted=ring_count_for(shape_id,parameters,city_class);
    FortificationReport report;
    report.method="Angular boundary samples of the buildable shape; city-only wall network.";
    report.limits="Schematic enceinte, not structural engineering. Castle baileys use a "
                  "separate generator.";
    if(rings_wanted<=0 || valid.empty() || !wall_structure.present) {
        if(rings_wanted>0) {
            FortificationUnplaced note;
            note.building_id=wall_structure.present?wall_structure.id:"building.wall";
            note.reason="No buildable perimeter for fortification";
            report.unplaced.push_back(note);
        }
        return report;
    }
    std::vector<double> scales;
    if(rings_wanted==1) scales.push_back(1.);
    else
        for(std::int64_t i=0;i<rings_wanted;++i)
            scales.push_back(0.45+(static_cast<double>(i)/static_cast<double>(rings_wanted-1))*0.55);
    const double segment_depth=wall_structure.depth;
    for(std::size_t ring_i=0;ring_i<scales.size();++ring_i) {
        const std::string ring_id="ring-"+std::to_string(ring_i);
        const bool outer=static_cast<std::int64_t>(ring_i)==rings_wanted-1;
        const std::string role=outer?"outer":ring_i==0?"inner":"middle";
        const std::vector<std::pair<double,double>> points=smooth_closed_ring(
            fortification_boundary_points(valid,half,cell,rx,rz,scales[ring_i],family));
        if(points.size()<8) {
            FortificationUnplaced note;
            note.building_id=wall_structure.id;
            note.ring_id=ring_id;
            note.has_ring_id=true;
            note.reason="Perimeter could not close on buildable land";
            report.unplaced.push_back(note);
            continue;
        }
        std::vector<FortificationSegment> segments;
        std::vector<FortificationNode> nodes;
        fortification_segmentize(points,segment_depth,wall_structure.id,ring_id,segments,nodes);
        if(segments.size()<6) {
            FortificationUnplaced note;
            note.building_id=wall_structure.id;
            note.ring_id=ring_id;
            note.has_ring_id=true;
            note.reason="Insufficient continuous wall segments";
            report.unplaced.push_back(note);
            continue;
        }
        const std::vector<FortificationRoadConnection> none;
        const std::vector<FortificationGateSite> gates=fortification_gate_sites(
            points,outer?road_connections:none,
            outer?gate_budget:std::max<std::int64_t>(1,floor_div(gate_budget,2)));
        std::vector<FortificationGate> gate_records;
        for(std::size_t g_i=0;g_i<gates.size();++g_i) {
            FortificationGate record;
            record.id=ring_id+"-gate-"+std::to_string(g_i);
            record.ring_id=ring_id;
            record.structure_id=gate_structure.present?gate_structure.id:"building.gatehouse";
            record.position_m=gates[g_i].position_m;
            record.approach_m=gates[g_i].approach_m;
            record.has_route_index=gates[g_i].has_route_index;
            record.route_index=gates[g_i].route_index;
            gate_records.push_back(record);
        }
        // Drop wall segments that collide with gate centres.
        std::vector<FortificationSegment> keep;
        const double clearance=std::max(8.,segment_depth*.6);
        for(const FortificationSegment& segment:segments) {
            bool blocked=false;
            for(const FortificationGate& record:gate_records)
                if(point_distance(segment.center_m,record.position_m)<clearance) {blocked=true;break;}
            if(blocked) continue;
            keep.push_back(segment);
        }
        std::vector<FortificationTower> towers;
        const std::int64_t budget=outer?tower_budget:std::max<std::int64_t>(1,floor_div(tower_budget,2));
        const std::int64_t step=std::max<std::int64_t>(
            1,floor_div(static_cast<std::int64_t>(nodes.size()),std::max<std::int64_t>(1,budget)));
        const std::int64_t limit=outer?std::max<std::int64_t>(1,tower_budget):2;
        std::int64_t t_i=0;
        for(std::size_t index=0;index<nodes.size() && t_i<limit;
            index+=static_cast<std::size_t>(step),++t_i) {
            FortificationTower tower;
            tower.id=ring_id+"-tower-"+std::to_string(t_i);
            tower.ring_id=ring_id;
            tower.structure_id="building.tower";
            tower.position_m=nodes[index].position_m;
            towers.push_back(tower);
        }
        FortificationRing ring;
        ring.id=ring_id;
        ring.role=role;
        ring.scale=fortification_round_digits(scales[ring_i],4);
        ring.polyline_m=points;
        ring.status="closed";
        ring.segment_count=static_cast<std::int64_t>(keep.size());
        ring.gate_count=static_cast<std::int64_t>(gate_records.size());
        report.rings.push_back(ring);
        report.segments.insert(report.segments.end(),keep.begin(),keep.end());
        report.nodes.insert(report.nodes.end(),nodes.begin(),nodes.end());
        report.gates.insert(report.gates.end(),gate_records.begin(),gate_records.end());
        report.towers.insert(report.towers.end(),towers.begin(),towers.end());
    }
    // Every ring the loop appends carries status 'closed'.
    report.defended_perimeter=!report.rings.empty();
    return report;
}
}
