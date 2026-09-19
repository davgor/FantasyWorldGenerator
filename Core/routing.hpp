#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
#include <cmath>
#include <cstdint>
#include <queue>
#include <tuple>
#include <limits>
#include <vector>
namespace fantasy_world_generator {
// The reference's one road cost function, shared by roads, hinterlands, ports and
// colleges. Water, unsafe magic and grades beyond the rule are impassable; flood and
// grade make a step dearer and a river crossing costs a bridge. A people is expressed
// by its own magic limit and grade limit, which is what `replace(cfg, ...)` does there.
struct RoadCost {
    const SphereGrid* grid=nullptr;
    const std::vector<double>*water=nullptr,*height=nullptr,*flood=nullptr,*river=nullptr;
    const std::vector<double>* hazard=nullptr;   // null means magic is not consulted
    double magic_limit=0.,max_grade=0.,bridge_cost=0.;
    std::int64_t size=0;
    // Returns false where the step is impassable, otherwise sets `step` to its cost.
    bool operator()(std::size_t i,std::size_t j,double d,double& step) const {
        const std::vector<double>& w=*water;
        if(w[i]!=0. || w[j]!=0. || d<=0) return false;
        if(hazard!=nullptr && std::max((*hazard)[i],(*hazard)[j])>magic_limit) return false;
        const std::int64_t xi=grid->points[i].first,zi=grid->points[i].second;
        const std::int64_t xj=grid->points[j].first,zj=grid->points[j].second;
        // A diagonal cannot slip between two water or two unsafe corner cells.
        if(xi!=xj && zi!=zj && zi!=0 && zi!=size-1 && zj!=0 && zj!=size-1) {
            const auto first=static_cast<std::size_t>(grid->index(xi,zj));
            const auto second=static_cast<std::size_t>(grid->index(xj,zi));
            if(w[first]!=0. || w[second]!=0.) return false;
            if(hazard!=nullptr && std::max((*hazard)[first],(*hazard)[second])>magic_limit) return false;
        }
        const double grade=std::fabs((*height)[j]-(*height)[i])/d;
        if(grade>max_grade) return false;
        step=d*(1+12*std::pow(grade,2.)+.5*((*flood)[i]+(*flood)[j]))
            +(((*river)[i]!=0. || (*river)[j]!=0.) ? bridge_cost : 0.);
        return true;
    }
};
// One terrain-cost owner per node, with the reference's tie rule: a cheaper path wins,
// and an equal one goes to the lower label, so ownership never depends on heap order.
struct Allocation {
    std::vector<double> distance;
    std::vector<std::int64_t> owner,parent;
};
template <typename Cost>
Allocation allocate_access(const SphereGrid& grid,const std::vector<std::pair<std::size_t,std::int64_t>>& seeds,
                           const Cost& cost,double limit=std::numeric_limits<double>::infinity()) {
    const std::size_t count=grid.points.size();
    Allocation result;
    result.distance.assign(count,std::numeric_limits<double>::infinity());
    result.owner.assign(count,-1);
    result.parent.assign(count,-1);
    // The queue orders by cost then label then node, matching the reference's tuples.
    using Entry=std::tuple<double,std::int64_t,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(const auto& seed:seeds) {
        result.distance[seed.first]=0.;
        result.owner[seed.first]=seed.second;
        queue.emplace(0.,seed.second,seed.first);
    }
    while(!queue.empty()) {
        const auto [value,label,i]=queue.top();queue.pop();
        if(value!=result.distance[i] || label!=result.owner[i]) continue;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            double step=0.;
            if(!cost(i,j,edge.second,step)) continue;
            const double candidate=value+step;
            if(candidate<=limit && (candidate<result.distance[j]
                                    || (candidate==result.distance[j] && label<result.owner[j]))) {
                result.distance[j]=candidate;result.owner[j]=label;result.parent[j]=static_cast<std::int64_t>(i);
                queue.emplace(candidate,label,j);
            }
        }
    }
    return result;
}
}
