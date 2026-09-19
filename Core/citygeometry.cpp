#include "citygeometry.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
namespace fantasy_world_generator {
namespace {
constexpr double pi_value=3.14159265358979323846;
// One entry of the Dijkstra frontier. Python pushes the tuple (cost, cell) onto a
// heapq, so ties on cost fall through to the cell itself, and the cell is compared
// component by component. Reproducing that ordering is not cosmetic: two cells at an
// equal cost settle a different street network depending on which pops first.
struct Frontier {
    double cost=0.;
    Cell cell{};
    bool operator>(const Frontier& other) const {
        if(cost!=other.cost) return cost>other.cost;
        return cell>other.cell;
    }
};
}
std::vector<std::pair<double,double>> corners(double x,double z,double w,double d,double angle) {
    const double c=std::cos(angle),s=std::sin(angle);
    const double offsets[4][2]={{-w/2,-d/2},{w/2,-d/2},{w/2,d/2},{-w/2,d/2}};
    std::vector<std::pair<double,double>> result;
    result.reserve(4);
    for(const auto& offset:offsets) {
        const double u=offset[0],v=offset[1];
        result.emplace_back(x+u*c-v*s,z+u*s+v*c);
    }
    return result;
}
std::set<Cell> footprint_cells(double x,double z,double w,double d,double angle,double half,
                               double cell) {
    const std::vector<std::pair<double,double>> points=corners(x,z,w,d,angle);
    const double c=std::cos(angle),s=std::sin(angle);
    double min_x=points[0].first,max_x=points[0].first;
    double min_z=points[0].second,max_z=points[0].second;
    for(const auto& point:points) {
        min_x=std::min(min_x,point.first);max_x=std::max(max_x,point.first);
        min_z=std::min(min_z,point.second);max_z=std::max(max_z,point.second);
    }
    // Python's math.floor returns an integer however negative the argument, where a
    // C++ cast truncates towards zero and would shift the whole plot by a cell on the
    // negative side of the raster.
    const std::int64_t lo_x=static_cast<std::int64_t>(std::floor((min_x+half)/cell));
    const std::int64_t hi_x=static_cast<std::int64_t>(std::floor((max_x+half)/cell));
    const std::int64_t lo_z=static_cast<std::int64_t>(std::floor((min_z+half)/cell));
    const std::int64_t hi_z=static_cast<std::int64_t>(std::floor((max_z+half)/cell));
    std::set<Cell> cells;
    const double r=cell/2*(std::fabs(c)+std::fabs(s));
    const double half_w=w/2+r-1e-8,half_d=d/2+r-1e-8;
    // Hoisted exactly as the reference hoists it, so the arithmetic is the same
    // expression evaluated in the same order.
    std::vector<double> columns;
    columns.reserve(static_cast<std::size_t>(std::max<std::int64_t>(0,hi_x-lo_x+1)));
    for(std::int64_t i=lo_x;i<=hi_x;++i)
        columns.push_back(-half+(static_cast<double>(i)+.5)*cell-x);
    for(std::int64_t j=lo_z;j<=hi_z;++j) {
        const double dz=-half+(static_cast<double>(j)+.5)*cell-z;
        const double dz_c=dz*c,dz_s=dz*s;
        for(std::size_t index=0;index<columns.size();++index) {
            const double dx=columns[index];
            if(std::fabs(dx*c+dz_s)<half_w && std::fabs(-dx*s+dz_c)<half_d)
                cells.emplace(lo_x+static_cast<std::int64_t>(index),j);
        }
    }
    return cells;
}
RoadNetwork grow_roads(const std::set<Cell>& valid,const std::map<Cell,double>& height,
                       std::int64_t size,std::uint64_t seed,double spacing_cells,
                       const std::vector<Cell>& required,std::int64_t branch_floor) {
    RoadNetwork result;
    if(valid.empty()) return result;
    PyRandom rng(seed);
    // The centremost cell, ties broken by the cell itself. `size/2` is exact in
    // binary and the coordinates are small integers, so the squares are exact and
    // multiplication agrees with Python's float pow to the bit; no libm pow needed.
    const double centre=static_cast<double>(size)/2.;
    Cell root=*valid.begin();
    double best=std::numeric_limits<double>::infinity();
    for(const Cell& c:valid) {
        const double dx=static_cast<double>(c.first)-centre;
        const double dz=static_cast<double>(c.second)-centre;
        const double key=dx*dx+dz*dz;
        if(key<best || (key==best && c<root)) {best=key;root=c;}
    }
    // Three draws, before anything else touches the stream.
    double phases[3];
    for(double& phase:phases) phase=rng.uniform(-pi_value,pi_value);
    // A smooth travel-cost field produces persistent bends rather than white-noise
    // zigzags. Built over the cells in sorted order, as the reference's comprehension
    // over `sorted(valid)` does; std::set already iterates sorted.
    std::map<Cell,double> costs;
    for(const Cell& c:valid) {
        const double x=static_cast<double>(c.first),z=static_cast<double>(c.second);
        costs.emplace(c,1+.45*(1+std::sin(x/9+phases[0])*std::cos(z/11+phases[1]))
                        +.3*(1+std::sin((x+z)/17+phases[2])));
    }
    std::map<Cell,double> distances;
    std::map<Cell,Cell> previous;
    distances.emplace(root,0.);
    std::priority_queue<Frontier,std::vector<Frontier>,std::greater<Frontier>> queue;
    queue.push(Frontier{0.,root});
    static const std::int64_t steps[8][2]={{-1,0},{0,-1},{0,1},{1,0},{-1,-1},{-1,1},{1,-1},{1,1}};
    while(!queue.empty()) {
        const Frontier top=queue.top();
        queue.pop();
        const auto known=distances.find(top.cell);
        if(known==distances.end() || top.cost!=known->second) continue;
        const std::int64_t x=top.cell.first,z=top.cell.second;
        for(const auto& step:steps) {
            const std::int64_t dx=step[0],dz=step[1];
            const Cell q(x+dx,z+dz);
            if(valid.count(q)==0) continue;
            const Cell side_x(x+dx,z),side_z(x,z+dz);
            if(dx && dz && (valid.count(side_x)==0 || valid.count(side_z)==0)) continue;
            if(dx && dz) {
                // No corner cutting across a step: both orthogonal supports must be
                // level with both ends of the diagonal.
                bool blocked=false;
                for(const Cell& support:{side_x,side_z})
                    for(const Cell& end:{top.cell,q})
                        if(std::fabs(height.at(support)-height.at(end))>1.4) blocked=true;
                if(blocked) continue;
            }
            // CPython's hypot, not the platform's: Core carries the port because the
            // two differ in the last bit and a road is a chain of these.
            const double length=python_hypot(static_cast<double>(dx),static_cast<double>(dz))*4;
            const double grade=std::fabs(height.at(q)-height.at(top.cell))/length;
            if(grade>.35) continue;
            const double next=top.cost+length*((costs.at(top.cell)+costs.at(q))/2+18*grade*grade);
            const auto found=distances.find(q);
            if(found==distances.end() || next<found->second) {
                distances[q]=next;
                previous[q]=top.cell;
                queue.push(Frontier{next,q});
            }
        }
    }
    std::vector<Cell> reachable;
    reachable.reserve(distances.size());
    for(const auto& entry:distances) reachable.push_back(entry.first);
    // Destinations represent gates and growing districts, never an imposed grid.
    std::vector<Cell> targets;
    {
        std::set<Cell> wanted;
        for(const Cell& cell:required)
            if(distances.count(cell)!=0) wanted.insert(cell);
        targets.assign(wanted.begin(),wanted.end());
    }
    // round() is banker's rounding in Python, so std::nearbyint under the default
    // rounding mode, not std::round which would break ties away from zero.
    const double span=std::max(12.,spacing_cells);
    const double raw=static_cast<double>(valid.size())/std::pow(span,2.)*1.5;
    const double rounded=std::nearbyint(raw);
    // Clamp before the cast: the reference's min() happens in Python's unbounded
    // integers, where a huge value is merely large, while the cast would be undefined.
    const std::int64_t bounded=rounded>=36. ? 36
        : rounded<=0. ? 0 : static_cast<std::int64_t>(rounded);
    const std::int64_t count=std::max(branch_floor,std::min<std::int64_t>(36,bounded));
    const std::size_t wanted=static_cast<std::size_t>(
        std::max<std::int64_t>(256,count*20));
    const std::size_t take=std::min(reachable.size(),wanted);
    std::vector<Cell> candidates;
    candidates.reserve(take);
    for(std::size_t index:rng.sample_indices(reachable.size(),take))
        candidates.push_back(reachable[index]);
    for(std::int64_t drawn=0;drawn<count;++drawn) {
        if(candidates.empty()) break;
        // Farthest-point selection against the root and everything already chosen.
        // These coordinates are integers and Python squares them as integers, so the
        // comparison is exact and must be done in integers here too.
        std::size_t choice=0;
        std::int64_t best_distance=-1;
        for(std::size_t index=0;index<candidates.size();++index) {
            const Cell& c=candidates[index];
            std::int64_t nearest=std::numeric_limits<std::int64_t>::max();
            const std::int64_t dx0=c.first-root.first,dz0=c.second-root.second;
            nearest=dx0*dx0+dz0*dz0;
            for(const Cell& q:targets) {
                const std::int64_t dx=c.first-q.first,dz=c.second-q.second;
                nearest=std::min(nearest,dx*dx+dz*dz);
            }
            if(nearest>best_distance || (nearest==best_distance && candidates[choice]<c)) {
                best_distance=nearest;choice=index;
            }
        }
        targets.push_back(candidates[choice]);
        candidates.erase(candidates.begin()+static_cast<std::ptrdiff_t>(choice));
    }
    std::set<Cell> network{root};
    for(const Cell& target:targets) {
        std::vector<Cell> path{target};
        while(network.count(path.back())==0) path.push_back(previous.at(path.back()));
        if(path.size()>1) {
            std::reverse(path.begin(),path.end());
            for(const Cell& cell:path) network.insert(cell);
            result.paths.push_back(path);
        }
    }
    result.roads=network;
    for(const Cell& cell:network) {
        static const std::int64_t sides[4][2]={{1,0},{-1,0},{0,1},{0,-1}};
        for(const auto& side:sides) {
            const Cell q(cell.first+side[0],cell.second+side[1]);
            if(distances.count(q)!=0 && std::fabs(height.at(q)-height.at(cell))<=1.4)
                result.roads.insert(q);
        }
    }
    return result;
}
}
