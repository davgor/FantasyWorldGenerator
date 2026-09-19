#include "society.hpp"
#include "routing.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <set>
namespace fantasy_world_generator {
namespace {
double arc(const Vec3& a,const Vec3& b,double radius) {
    return radius*std::acos(std::max(-1.,std::min(1.,dot(a,b))));
}
// Cheapest ground route from one city, stopped once every candidate landing has been
// settled: the reference does the same, and an unreached candidate stays unreachable.
struct Routed {
    std::vector<double> distance;
    std::vector<std::int64_t> parent;
};
Routed shortest_paths(const SphereGrid& grid,std::size_t start,const RoadCost& cost,
                      const std::set<std::size_t>& targets) {
    Routed routed;
    routed.distance.assign(grid.points.size(),std::numeric_limits<double>::infinity());
    routed.parent.assign(grid.points.size(),-1);
    routed.distance[start]=0.;
    std::set<std::size_t> remaining=targets;
    using Entry=std::pair<double,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    queue.emplace(0.,start);
    while(!queue.empty()) {
        const auto [value,i]=queue.top();queue.pop();
        if(value!=routed.distance[i]) continue;
        remaining.erase(i);
        if(remaining.empty()) break;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            double step=0.;
            if(!cost(i,j,edge.second,step)) continue;
            if(value+step<routed.distance[j]) {
                routed.distance[j]=value+step;routed.parent[j]=static_cast<std::int64_t>(i);
                queue.emplace(routed.distance[j],j);
            }
        }
    }
    return routed;
}
}
Society add_world_society(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                          const Catalogues& catalogues,const Layers& layers,
                          const std::vector<RegionInfluence>& regions,
                          const std::vector<FoundedCity>& sites,const Humans& humans) {
    Society society;
    const std::size_t count=grid.points.size();
    if(sites.empty()) return society;
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> depth=node_values(layers.water_depth,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    const std::vector<double> flood=node_values(layers.flood_risk,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<double> harbor=node_values(layers.harbor_suitability,grid);
    const std::vector<double> coastal_support=node_values(layers.coastal_support,grid);
    const std::vector<double> suitability=node_values(layers.suitability,grid);
    const std::vector<double> hazard=layers.magic_hazard.empty()
        ? std::vector<double>(count,0.) : node_values(layers.magic_hazard,grid);
    std::vector<Vec3> vectors;
    vectors.reserve(count);
    for(const auto& point:grid.points) vectors.push_back(direction(point.first,point.second,cfg.size));
    // Witch huts leave their zone centres for isolated ground that conventional
    // settlement does not want. Necropolises stay where the ecology put them.
    auto zone_of=[&](const std::string& name)->const Grid* {
        for(std::size_t index=0;index<zone_count;++index)
            if(std::string(zone_names()[index])==name) return &layers.zone[index];
        return nullptr;
    };
    std::size_t wanted=0;
    for(const RegionInfluence& region:regions) {
        const bool hut=region.id=="witch_huts";
        if(!hut && region.id!="haunted_sands") continue;
        const Grid* zone=zone_of(region.id);
        for(std::size_t centre:region.centres) {
            if(hut) {++wanted;continue;}
            Landmark landmark;
            landmark.id=region.id+"-"+std::to_string(centre);
            landmark.kind="necropolis";
            landmark.node=centre;
            landmark.x=grid.points[centre].first;
            landmark.z=grid.points[centre].second;
            if(zone!=nullptr && !zone->empty())
                landmark.intensity=(*zone)[static_cast<std::size_t>(landmark.z)][static_cast<std::size_t>(landmark.x)];
            society.landmarks.push_back(landmark);
        }
    }
    const Grid* hut_zone=zone_of("witch_huts");
    if(hut_zone!=nullptr && wanted>0 && !hut_zone->empty()) {
        std::vector<double> intensity=node_values(*hut_zone,grid);
        std::vector<std::size_t> ranked(count);
        for(std::size_t i=0;i<count;++i) ranked[i]=i;
        std::stable_sort(ranked.begin(),ranked.end(),[&](std::size_t a,std::size_t b) {
            return intensity[a]>intensity[b];
        });
        std::vector<std::size_t> chosen;
        for(std::size_t i:ranked) {
            if(chosen.size()>=wanted) break;
            if(water[i]!=0. || suitability[i]>=.55 || intensity[i]<.02) continue;
            bool clear=true;
            for(const FoundedCity& site:sites)
                if(arc(vectors[i],vectors[site.node],radius)<cfg.settlement_spacing) {clear=false;break;}
            if(!clear) continue;
            for(std::size_t other:chosen)
                if(arc(vectors[i],vectors[other],radius)<200) {clear=false;break;}
            if(!clear) continue;
            chosen.push_back(i);
            Landmark landmark;
            landmark.id="witch-hut-"+std::to_string(i);
            landmark.kind="witch_hut";
            landmark.node=i;
            landmark.x=grid.points[i].first;
            landmark.z=grid.points[i].second;
            landmark.intensity=intensity[i];
            landmark.conventional_suitability=suitability[i];
            landmark.reason="Umbral influence, isolation and low conventional settlement suitability.";
            society.landmarks.push_back(landmark);
        }
    }
    // Coastal landings: reachable harbour ground a city can work, one sea neighbour
    // deep enough to land on, and never a node something already stands on.
    std::set<std::size_t> occupied;
    for(const FoundedCity& site:sites) occupied.insert(site.node);
    for(const RuralSite& hamlet:humans.hamlets) occupied.insert(hamlet.node);
    std::set<std::size_t> ground;
    for(std::size_t i=0;i<count;++i) if(harbor[i]>.1) ground.insert(i);
    for(std::size_t index=0;index<sites.size();++index) {
        const FoundedCity& site=sites[index];
        const Profile& profile=catalogues.profile(site.population_profile);
        RoadCost cost;
        cost.grid=&grid;cost.water=&water;cost.height=&height;cost.flood=&flood;cost.river=&river;
        cost.hazard=&hazard;cost.bridge_cost=cfg.bridge_cost;cost.size=cfg.size;
        cost.magic_limit=profile.trait("mutation_limit");
        cost.max_grade=profile.trait("road_grade_limit");
        const Routed routed=shortest_paths(grid,site.node,cost,ground);
        std::vector<std::size_t> eligible;
        for(std::size_t i:ground)
            if(routed.distance[i]<=cfg.support_reach && occupied.count(i)==0) eligible.push_back(i);
        std::stable_sort(eligible.begin(),eligible.end(),[&](std::size_t a,std::size_t b) {
            const double left=-(harbor[a]+.5*coastal_support[a])*std::exp(-routed.distance[a]/cfg.support_reach);
            const double right=-(harbor[b]+.5*coastal_support[b])*std::exp(-routed.distance[b]/cfg.support_reach);
            return left<right;
        });
        const std::size_t take=std::min<std::size_t>(eligible.size(),
            static_cast<std::size_t>(std::max<std::int64_t>(0,cfg.options.coastal_hamlets)));
        for(std::size_t rank=0;rank<take;++rank) {
            const std::size_t node=eligible[rank];
            bool found=false;
            std::size_t sea_node=0;
            double landing=0.;
            for(const auto& edge:grid.neighbors[node]) {
                const auto j=static_cast<std::size_t>(edge.first);
                if(water[j]!=1. || depth[j]<cfg.options.sea_draft || hazard[j]>profile.trait("mutation_limit")) continue;
                if(!found || edge.second<landing) {found=true;sea_node=j;landing=edge.second;}
            }
            if(!found) continue;
            occupied.insert(node);
            Port port;
            port.id="coastal-"+std::to_string(index)+"-"+std::to_string(society.ports.size());
            port.node=node;
            port.sea_node=sea_node;
            port.landing_distance_m=landing;
            port.x=grid.points[node].first;
            port.z=grid.points[node].second;
            port.core_id=static_cast<std::int64_t>(index);
            port.population_profile=site.population_profile;
            port.culture_id=index<humans.cores.size() ? humans.cores[index].culture_id : std::string();
            port.height_m=height[node];
            port.harbor_quality=harbor[node];
            port.trade_terminal=harbor[node]>=.4;
            port.access_cost=routed.distance[node];
            std::size_t walk=node;
            port.access_nodes.push_back(walk);
            while(walk!=site.node && routed.parent[walk]>=0) {
                walk=static_cast<std::size_t>(routed.parent[walk]);
                port.access_nodes.push_back(walk);
            }
            std::reverse(port.access_nodes.begin(),port.access_nodes.end());
            society.ports.push_back(port);
        }
    }
    return society;
}
}
