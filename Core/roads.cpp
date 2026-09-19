#include "founding.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <set>
namespace fantasy_world_generator {
namespace {
// The same passability rule the hinterland uses, parameterised by the people whose
// road it is: a mountain people climbs grades a maritime one refuses.
struct RoadRule {
    const SphereGrid* grid=nullptr;
    const std::vector<double>*water=nullptr,*height=nullptr,*flood=nullptr,*river=nullptr,*hazard=nullptr;
    double magic_limit=0.,max_grade=0.,bridge_cost=0.;
    std::int64_t size=0;
    bool operator()(std::size_t i,std::size_t j,double d,double& step) const {
        const std::vector<double>& w=*water;
        if(w[i]!=0. || w[j]!=0. || d<=0) return false;
        if(std::max((*hazard)[i],(*hazard)[j])>magic_limit) return false;
        const std::int64_t xi=grid->points[i].first,zi=grid->points[i].second;
        const std::int64_t xj=grid->points[j].first,zj=grid->points[j].second;
        // A diagonal cannot slip between two water or two unsafe corner cells.
        if(xi!=xj && zi!=zj && zi!=0 && zi!=size-1 && zj!=0 && zj!=size-1) {
            const auto first=static_cast<std::size_t>(grid->index(xi,zj));
            const auto second=static_cast<std::size_t>(grid->index(xj,zi));
            if(w[first]!=0. || w[second]!=0.) return false;
            if(std::max((*hazard)[first],(*hazard)[second])>magic_limit) return false;
        }
        const double grade=std::fabs((*height)[j]-(*height)[i])/d;
        if(grade>max_grade) return false;
        step=d*(1+12*std::pow(grade,2.)+.5*((*flood)[i]+(*flood)[j]))
            +(((*river)[i]!=0. || (*river)[j]!=0.) ? bridge_cost : 0.);
        return true;
    }
};
struct RouteCandidate {
    double cost=0.;
    std::size_t from=0,to=0;
    std::vector<std::size_t> nodes;
};
double edge_length(const SphereGrid& grid,std::size_t from,std::size_t to) {
    for(const auto& edge:grid.neighbors[from])
        if(static_cast<std::size_t>(edge.first)==to) return edge.second;
    return 0.;
}
}
std::vector<Road> build_roads(const WorldConfig& cfg,const SphereGrid& grid,const Catalogues& catalogues,
                              const Layers& layers,const std::vector<FoundedCity>& sites) {
    const std::size_t count=grid.points.size();
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<double> hazard=node_values(layers.magic_hazard,grid);
    const std::vector<double> flood=node_values(layers.flood_risk,grid);
    auto rule_for=[&](const std::string& civilization) {
        const Profile& profile=catalogues.profile(civilization);
        RoadRule rule;
        rule.grid=&grid;rule.water=&water;rule.height=&height;rule.flood=&flood;
        rule.river=&river;rule.hazard=&hazard;
        rule.magic_limit=profile.trait("mutation_limit");
        rule.max_grade=profile.trait("road_grade_limit");
        rule.bridge_cost=cfg.bridge_cost;
        rule.size=cfg.size;
        return rule;
    };
    std::vector<RouteCandidate> candidates;
    for(std::size_t a=0;a<sites.size();++a) {
        const RoadRule rule=rule_for(sites[a].population_profile);
        std::vector<double> distance(count,std::numeric_limits<double>::infinity());
        std::vector<std::int64_t> parent(count,-1);
        distance[sites[a].node]=0.;
        using Entry=std::pair<double,std::size_t>;
        std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
        queue.emplace(0.,sites[a].node);
        std::set<std::size_t> remaining;
        for(const FoundedCity& site:sites) remaining.insert(site.node);
        while(!queue.empty()) {
            const auto entry=queue.top();queue.pop();
            if(entry.first!=distance[entry.second]) continue;
            remaining.erase(entry.second);
            if(remaining.empty()) break;
            for(const auto& edge:grid.neighbors[entry.second]) {
                const auto j=static_cast<std::size_t>(edge.first);
                double step=0.;
                if(!rule(entry.second,j,edge.second,step)) continue;
                const double candidate=entry.first+step;
                if(candidate<distance[j]) {
                    distance[j]=candidate;parent[j]=static_cast<std::int64_t>(entry.second);
                    queue.emplace(candidate,j);
                }
            }
        }
        for(std::size_t b=a+1;b<sites.size();++b) {
            const std::size_t goal=sites[b].node;
            if(!std::isfinite(distance[goal])) continue;
            std::vector<std::size_t> path;
            std::size_t node=goal;
            while(node!=sites[a].node) {
                path.push_back(node);
                node=static_cast<std::size_t>(parent[node]);
            }
            path.push_back(node);
            std::reverse(path.begin(),path.end());
            // The destination city has to be able to travel the road by its own rules,
            // or it is not a shared route.
            const RoadRule other=rule_for(sites[b].population_profile);
            bool usable=true;
            for(std::size_t k=0;k+1<path.size();++k) {
                double step=0.;
                if(!other(path[k],path[k+1],edge_length(grid,path[k],path[k+1]),step)) {usable=false;break;}
            }
            if(!usable) continue;
            candidates.push_back(RouteCandidate{distance[goal],a,b,path});
        }
    }
    std::stable_sort(candidates.begin(),candidates.end(),[](const RouteCandidate& a,const RouteCandidate& b) {
        if(a.cost!=b.cost) return a.cost<b.cost;
        if(a.from!=b.from) return a.from<b.from;
        return a.to<b.to;
    });
    std::vector<std::size_t> groups(sites.size());
    for(std::size_t i=0;i<groups.size();++i) groups[i]=i;
    auto root=[&](std::size_t i) {
        while(groups[i]!=i) i=groups[i];
        return i;
    };
    std::vector<Road> roads;
    for(const RouteCandidate& candidate:candidates) {
        const std::size_t ra=root(candidate.from),rb=root(candidate.to);
        if(ra==rb) continue;
        groups[ra]=rb;
        Sum length;
        for(std::size_t k=0;k+1<candidate.nodes.size();++k)
            length.add(edge_length(grid,candidate.nodes[k],candidate.nodes[k+1]));
        Road road;
        road.from=candidate.from;road.to=candidate.to;road.nodes=candidate.nodes;
        road.length_m=length.value();road.cost=candidate.cost;
        for(std::size_t k=0;k+1<candidate.nodes.size();++k)
            if(river[candidate.nodes[k]]!=0. || river[candidate.nodes[k+1]]!=0.)
                road.river_crossings.emplace_back(candidate.nodes[k],candidate.nodes[k+1]);
        roads.push_back(road);
    }
    return roads;
}
}
