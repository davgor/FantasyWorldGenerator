#include "sceneframe.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator::sceneframe {
namespace {
// `points[index]` with Python's list semantics: a negative index counts from the end
// and anything past either end raises. Route node indices come from the water graph
// and are never negative in a generated world, but the reference would honour one, so
// the port does rather than silently reading out of bounds.
const std::pair<std::int64_t,std::int64_t>&
node_at(const std::vector<std::pair<std::int64_t,std::int64_t>>& points,std::int64_t index) {
    const std::int64_t count=static_cast<std::int64_t>(points.size());
    const std::int64_t at=index<0?index+count:index;
    if(at<0 || at>=count) throw IndexError();
    return points[static_cast<std::size_t>(at)];
}
// The reference divides by a Python int here, so a one-node world is a ZeroDivisionError
// and not the infinity C++ would hand back.
double span_of(std::int64_t size) {
    if(size-1==0) throw ZeroDivision();
    return static_cast<double>(size-1);
}
}

Frame frame(const World& world,const Site& site) {
    const double span=span_of(world.size);
    const double lat=pi/2-pi*site.z/span;
    // Not `direction`'s longitude: no `x % (n-1)` wrap, so x==n-1 lands on +pi where
    // direction would fold it back to -pi and flip the sign of the Z component.
    const double lon=-pi+2*pi*site.x/span;
    Frame f;
    f.radius=world.globe_radius();
    f.up=Vec3{std::cos(lat)*std::cos(lon),std::sin(lat),std::cos(lat)*std::sin(lon)};
    f.east=Vec3{-std::sin(lon),0.,std::cos(lon)};
    f.north=Vec3{-std::sin(lat)*std::cos(lon),std::cos(lat),-std::sin(lat)*std::sin(lon)};
    return f;
}

Vec3 local_direction(const Frame& f,double x,double z) {
    Vec3 p{};
    for(int i=0;i<3;++i) p[i]=f.up[i]+(f.east[i]*x+f.north[i]*z)/f.radius;
    // `math.sqrt(sum(v*v for v in p))`: a compensated sum of the three squares, which
    // is what unit() already builds on through dot().
    return unit(p);
}

std::vector<RoadEntry> road_entries(const World& world,const Site& site,double half) {
    const Frame f=frame(world,site);
    const double r=f.radius;
    const std::int64_t n=world.size;
    // `next((i for i,s in ... if ...), None)`: the first matching site, or nothing.
    bool located=false;
    std::int64_t site_index=0;
    for(std::size_t i=0;i<world.site_ids.size();++i) {
        if(world.site_ids[i]==site.id) {site_index=static_cast<std::int64_t>(i);located=true;break;}
    }
    std::vector<RoadEntry> entries;
    for(std::size_t ri=0;ri<world.routes.size();++ri) {
        const Route& road=world.routes[ri];
        // A site the settlement list does not carry is `None`, which is in no route's
        // endpoint pair, so the reference skips every route and returns nothing.
        if(!located || (site_index!=road.from && site_index!=road.to)) continue;
        // A self-loop takes the reversed branch, because `to` is tested second.
        const bool reverse=site_index==road.to;
        std::vector<std::int64_t> indices=road.nodes;
        if(reverse) std::reverse(indices.begin(),indices.end());
        double prev[2]={0.,0.};
        for(std::size_t k=0;k<indices.size();++k) {
            const std::pair<std::int64_t,std::int64_t>& point=node_at(world.water_nodes,indices[k]);
            // The route nodes DO use terrain_globe.direction, poles, seam wrap and all.
            const Vec3 p=direction(point.first,point.second,n);
            // Three-term compensated dot products, not plain accumulation.
            const double den=dot(p,f.up);
            // The horizon guard. It abandons this route outright: a node behind the
            // tangent plane means the gnomonic projection has no meaning past here,
            // and the reference emits no entry rather than skipping to the next node.
            if(den<=0.) break;
            const double q[2]={r*dot(p,f.east)/den,r*dot(p,f.north)/den};
            if(std::max(std::fabs(q[0]),std::fabs(q[1]))>half) {
                bool have=false;
                double t=0.;
                for(int j=0;j<2;++j) {
                    if(!(std::fabs(q[j])>half)) continue;
                    const double denominator=q[j]-prev[j];
                    if(denominator==0.) throw ZeroDivision();
                    const double candidate=((q[j]>0.?half:-half)-prev[j])/denominator;
                    if(!have || candidate<t) {t=candidate;have=true;}
                }
                RoadEntry entry;
                entry.route_id="regional-road-"+std::to_string(ri);
                entry.route_index=static_cast<std::int64_t>(ri);
                entry.end=reverse?"to":"from";
                entry.outside_index=reverse?static_cast<std::int64_t>(indices.size())-1
                                            -static_cast<std::int64_t>(k)
                                          :static_cast<std::int64_t>(k);
                entry.junction_id="junction:"+site.id.label()+":"+std::to_string(ri);
                // The crossing is interpolated on both axes even though only the
                // exceeding one chose `t`.
                for(int j=0;j<2;++j) entry.gate_local_m[j]=prev[j]+t*(q[j]-prev[j]);
                entry.direction=local_direction(f,entry.gate_local_m[0],entry.gate_local_m[1]);
                entry.status="unreachable";
                entry.reason="No terrain-safe street connection to regional road";
                entries.push_back(std::move(entry));
                break;
            }
            prev[0]=q[0];prev[1]=q[1];
        }
    }
    return entries;
}
}
