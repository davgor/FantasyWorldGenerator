#include "humans.hpp"
#include "wars.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <set>
namespace fantasy_world_generator {
namespace {
// Single-link groups over roads cheap enough to count as interaction, keyed by the
// lowest member city index so the identity does not depend on iteration order.
std::vector<std::int64_t> culture_groups(std::size_t count,const std::vector<Road>& links,double threshold) {
    std::vector<std::size_t> groups(count);
    for(std::size_t i=0;i<count;++i) groups[i]=i;
    auto root=[&](std::size_t i) {
        while(groups[i]!=i) i=groups[i];
        return i;
    };
    for(const Road& link:links) {
        if(link.cost>threshold) continue;
        const std::size_t a=root(link.from),b=root(link.to);
        groups[std::max(a,b)]=std::min(a,b);
    }
    std::vector<std::int64_t> resolved(count);
    for(std::size_t i=0;i<count;++i) resolved[i]=static_cast<std::int64_t>(root(i));
    return resolved;
}
std::string culture_identity(const std::string& people,std::uint32_t seed) {
    static const char* digits="0123456789abcdef";
    std::string hex(8,'0');
    for(int place=7;place>=0;--place) {hex[static_cast<std::size_t>(place)]=digits[seed&0xf];seed>>=4;}
    return people+"-"+hex;
}
double arc(const Vec3& a,const Vec3& b,double radius) {
    return radius*std::acos(std::max(-1.,std::min(1.,dot(a,b))));
}
}
Humans add_humans(const WorldConfig& cfg,double radius,const SphereGrid& grid,const Catalogues& catalogues,
                  Layers& layers,const std::vector<FoundedCity>& sites,
                  const std::vector<PopulationEstimate>& residents,const std::vector<Road>& roads,
                  const std::vector<std::string>& variants) {
    Humans humans;
    const std::size_t count=grid.points.size();
    if(sites.empty() || roads.empty()) return humans;
    const std::vector<double> height=node_values(layers.height,grid);
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> slope=node_values(layers.slope,grid);
    const std::vector<double> flood=node_values(layers.flood_risk,grid);
    const std::vector<double> wet=node_values(layers.moisture,grid);
    const std::vector<double> temp=node_values(layers.temperature,grid);
    const std::vector<double> tpi=node_values(layers.tpi,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<double> biome=node_values(layers.biome,grid);
    const std::vector<double> fresh=node_values(layers.freshwater_distance,grid);
    const std::vector<double> resource=node_values(layers.resource_potential,grid);
    const std::vector<double> hazard=layers.magic_hazard.empty()
        ? std::vector<double>(count,0.) : node_values(layers.magic_hazard,grid);
    auto cost_for=[&](const std::string& people) {
        RoadCost cost;
        cost.grid=&grid;cost.water=&water;cost.height=&height;cost.flood=&flood;cost.river=&river;
        cost.hazard=&hazard;cost.bridge_cost=cfg.bridge_cost;cost.size=cfg.size;
        if(people.empty()) {
            cost.magic_limit=cfg.human_magic_limit;cost.max_grade=cfg.road_max_grade;
        } else {
            const Profile& profile=catalogues.profile(people);
            cost.magic_limit=profile.trait("mutation_limit");
            cost.max_grade=profile.trait("road_grade_limit");
        }
        return cost;
    };
    const RoadCost shared=cost_for(std::string());
    // Every city keeps its own traversal rules out to the support reach, and a frontier
    // cannot change hands mid-path, so ownership is resolved with the owning people's
    // cost rather than a shared one.
    std::vector<RoadCost> costs;
    costs.reserve(sites.size());
    for(const FoundedCity& site:sites) costs.push_back(cost_for(site.population_profile));
    std::vector<double> distance(count,std::numeric_limits<double>::infinity());
    std::vector<std::int64_t> owner(count,-1),parent(count,-1);
    using Entry=std::tuple<double,std::int64_t,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(std::size_t index=0;index<sites.size();++index) {
        distance[sites[index].node]=0.;
        owner[sites[index].node]=static_cast<std::int64_t>(index);
        queue.emplace(0.,static_cast<std::int64_t>(index),sites[index].node);
    }
    while(!queue.empty()) {
        const auto [value,label,i]=queue.top();queue.pop();
        if(value!=distance[i] || label!=owner[i]) continue;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            double step=0.;
            if(!costs[static_cast<std::size_t>(label)](i,j,edge.second,step)) continue;
            const double candidate=value+step;
            if(candidate<distance[j] && candidate<=cfg.support_reach) {
                distance[j]=candidate;owner[j]=label;parent[j]=static_cast<std::int64_t>(i);
                queue.emplace(candidate,label,j);
            }
        }
    }
    // Cultures: cities of one people joined by a road cheap enough to interact over.
    std::vector<Road> links;
    for(const Road& road:roads)
        if(sites[road.from].population_profile==sites[road.to].population_profile) links.push_back(road);
    humans.groups=culture_groups(sites.size(),links,cfg.culture_link_cost);
    std::map<std::int64_t,std::string> culture_ids;
    for(std::int64_t group:humans.groups) {
        if(culture_ids.count(group)!=0) continue;
        const std::uint32_t seed=child_seed(static_cast<std::uint64_t>(cfg.seed),
                                            "culture-"+std::to_string(group));
        culture_ids.emplace(group,culture_identity(sites[static_cast<std::size_t>(group)].population_profile,seed));
    }
    for(const auto& entry:culture_ids) {
        Culture culture;
        culture.index=entry.first;
        culture.id=entry.second;
        culture.population_profile=sites[static_cast<std::size_t>(entry.first)].population_profile;
        for(std::size_t index=0;index<humans.groups.size();++index)
            if(humans.groups[index]==entry.first) culture.city_ids.push_back(static_cast<std::int64_t>(index));
        humans.cultures.push_back(culture);
    }
    // Exportable surplus per cell, under the owning people's own farming rules.
    const std::vector<std::string>& ids=catalogues.civilization_ids();
    std::vector<double> natural(count,0.),food(count,0.);
    humans.irrigation_benefit.assign(count,0.);
    for(std::size_t i=0;i<count;++i) {
        const std::string people=owner[i]>=0 ? sites[static_cast<std::size_t>(owner[i])].population_profile
                                             : catalogues.aggregate_profile_id();
        const Profile& profile=catalogues.profile(people);
        Farming yield{0.,0.};
        if(water[i]==0.)
            yield=farming_potential(profile,slope[i],temp[i],wet[i],flood[i],fresh[i],
                                    profile.trait("irrigation"));
        const double multiplier=biome_food_multiplier(profile,static_cast<std::int64_t>(biome[i]),variants[i])
            *(1-hazard[i]);
        natural[i]=yield.natural*multiplier;
        food[i]=yield.supported*multiplier;
        humans.irrigation_benefit[i]=food[i]-natural[i];
    }
    humans.natural_food_potential=natural;
    humans.food_potential=food;
    // Hamlets: the best reachable farming or resource ground inside a city's catchment,
    // kept apart from the city and from each other.
    std::vector<Vec3> vectors;
    vectors.reserve(count);
    for(const auto& point:grid.points) vectors.push_back(direction(point.first,point.second,cfg.size));
    std::vector<std::size_t> occupied;
    for(const FoundedCity& site:sites) occupied.push_back(site.node);
    // Separation is measured on the world the player walks, so it is the effective
    // radius; the design radius would make every spacing rule 5.6 times too generous.
    auto separated=[&](std::size_t i,double minimum) {
        for(std::size_t node:occupied) if(arc(vectors[i],vectors[node],radius)<minimum) return false;
        return true;
    };
    auto record=[&](std::size_t i,const std::string& kind,std::size_t number,const std::string& reason) {
        RuralSite site;
        site.id=kind+"-"+std::to_string(number);
        site.kind=kind;
        site.node=i;
        site.x=grid.points[i].first;
        site.z=grid.points[i].second;
        site.core_id=owner[i];
        const auto core=static_cast<std::size_t>(std::max<std::int64_t>(0,owner[i]));
        site.population_profile=sites[core].population_profile;
        site.culture_id=culture_ids.at(humans.groups[core]);
        site.height_m=height[i];
        site.access_cost=distance[i];
        site.access_nodes.push_back(i);
        while(parent[site.access_nodes.back()]>=0)
            site.access_nodes.push_back(static_cast<std::size_t>(parent[site.access_nodes.back()]));
        site.reason=reason;
        return site;
    };
    for(std::size_t index=0;index<sites.size();++index) {
        const Profile& profile=catalogues.profile(sites[index].population_profile);
        const double work_limit=profile.trait("work_slope_limit");
        std::vector<std::size_t> eligible;
        for(std::size_t i=0;i<count;++i)
            if(owner[i]==static_cast<std::int64_t>(index) && distance[i]>=100 && distance[i]<=cfg.support_reach
               && water[i]==0. && slope[i]<work_limit) eligible.push_back(i);
        const std::int64_t limit=cfg.auto_parameters
            ? std::min<std::int64_t>(cfg.hamlets_per_core,
                static_cast<std::int64_t>(std::ceil(
                    (index<residents.size() ? static_cast<double>(residents[index].rural) : 0.)/40)))
            : cfg.hamlets_per_core;
        for(std::int64_t k=0;k<limit;++k) {
            const bool farming=k%3!=2;
            auto score=[&](std::size_t i) {
                return (farming ? food[i] : resource[i]*(1-flood[i]))*std::exp(-distance[i]/cfg.support_reach);
            };
            std::vector<std::size_t> ranked=eligible;
            std::stable_sort(ranked.begin(),ranked.end(),[&](std::size_t a,std::size_t b) {
                const double left=score(a),right=score(b);
                if(left!=right) return left>right;
                return a<b;
            });
            for(std::size_t i:ranked) {
                if(score(i)<.025) break;
                if(!separated(i,120)) continue;
                RuralSite hamlet=record(i,"hamlet",humans.hamlets.size(),
                    std::string("Reachable ")+(farming ? "farming" : "resource")
                    +" potential with low transport cost");
                hamlet.role=farming ? "farming" : "resource";
                hamlet.irrigation_benefit=food[i]-natural[i];
                humans.hamlets.push_back(hamlet);
                occupied.push_back(i);
                break;
            }
        }
    }
    // Each productive cell belongs to at most one hamlet, and never crosses a city
    // catchment: a farm cannot be worked from another city's land.
    struct FarmCost {
        const std::vector<std::int64_t>* owner=nullptr;
        const std::vector<double>* distance=nullptr;
        const std::vector<RoadCost>* costs=nullptr;
        const RoadCost* shared=nullptr;
        double reach=0.;
        bool operator()(std::size_t i,std::size_t j,double d,double& step) const {
            if((*owner)[i]!=(*owner)[j] || (*distance)[j]>reach) return false;
            if((*owner)[i]>=0) return (*costs)[static_cast<std::size_t>((*owner)[i])](i,j,d,step);
            return (*shared)(i,j,d,step);
        }
    };
    const FarmCost farm{&owner,&distance,&costs,&shared,cfg.support_reach};
    std::vector<std::pair<std::size_t,std::int64_t>> seeds;
    for(std::size_t k=0;k<humans.hamlets.size();++k)
        seeds.emplace_back(humans.hamlets[k].node,static_cast<std::int64_t>(k));
    const Allocation farms=allocate_access(grid,seeds,farm,250.);
    humans.hamlet_catchment.assign(count,-1.);
    std::set<std::size_t> city_nodes;
    for(const FoundedCity& site:sites) city_nodes.insert(site.node);
    for(std::size_t i=0;i<count;++i) {
        humans.hamlet_catchment[i]=static_cast<double>(farms.owner[i]);
        const std::int64_t k=farms.owner[i];
        if(k<0 || city_nodes.count(i)!=0) continue;
        const std::string people=owner[i]>=0 ? sites[static_cast<std::size_t>(owner[i])].population_profile
                                             : catalogues.aggregate_profile_id();
        if(slope[i]>=catalogues.profile(people).trait("work_slope_limit")) continue;
        RuralSite& hamlet=humans.hamlets[static_cast<std::size_t>(k)];
        const double area=grid.areas[i]/1e6;
        const double delivery=std::exp(-hamlet.access_cost/cfg.support_reach);
        hamlet.worked_area_km2+=area;
        hamlet.delivered_food+=100*area*food[i]*delivery*(hamlet.role=="farming" ? 1 : .25);
        hamlet.delivered_materials+=100*area*resource[i]*delivery*(hamlet.role=="resource" ? 1 : .25);
    }
    // Fortresses watch route junctions and river crossings from defensible ground.
    std::map<std::size_t,std::set<std::size_t>> route_neighbors;
    std::set<std::size_t> crossings;
    std::set<std::pair<std::size_t,std::size_t>> crossing_edges;
    Sum road_length;
    for(const Road& road:roads) {
        for(std::size_t k=0;k+1<road.nodes.size();++k) {
            route_neighbors[road.nodes[k]].insert(road.nodes[k+1]);
            route_neighbors[road.nodes[k+1]].insert(road.nodes[k]);
        }
        for(const auto& edge:road.river_crossings) {
            crossings.insert(edge.first);crossings.insert(edge.second);
            crossing_edges.insert(std::minmax(edge.first,edge.second));
        }
        // The reference totals these with the interpreter's own sum(), which is
        // Neumaier-compensated in 3.12, so this one has to be as well.
        road_length.add(road.length_m);
    }
    // The road network asks for its own defence: one watch per support reach of road
    // plus one per distinct crossing, never more forts than the cities that raise
    // them. cfg.fortress_count is a caller's ceiling over both, never a target.
    //
    // A city that has fought a war wants more watching its roads, so its wars raise both
    // what the world asks for and how much it is allowed. A world that has never been to
    // war keeps exactly the road-and-city answer.
    std::vector<std::int64_t> veteran(sites.size(),0);
    std::int64_t veteran_demand=0;
    for(std::size_t index=0;index<sites.size();++index) {
        veteran[index]=std::min<std::int64_t>(3,veteran_wars(sites[index]));
        veteran_demand+=veteran[index];
    }
    const std::int64_t proposed=static_cast<std::int64_t>(std::floor(road_length.value()/cfg.support_reach))
        +static_cast<std::int64_t>(crossing_edges.size())+veteran_demand;
    const std::int64_t fortress_limit=std::min({cfg.fortress_count,proposed,
                                                static_cast<std::int64_t>(sites.size())+veteran_demand});
    std::map<std::size_t,std::pair<double,std::size_t>> strategic;
    for(const auto& entry:route_neighbors) {
        const std::size_t node=entry.first;
        const double base=1+std::min<double>(2,std::max<double>(0,static_cast<double>(entry.second.size())-2))
            +(crossings.count(node)!=0 ? 1 : 0);
        std::vector<std::pair<std::size_t,double>> around{{node,0.}};
        for(const auto& edge:grid.neighbors[node])
            around.emplace_back(static_cast<std::size_t>(edge.first),edge.second);
        for(const auto& pair:around) {
            const std::size_t i=pair.first;
            const std::string people=owner[i]>=0 ? sites[static_cast<std::size_t>(owner[i])].population_profile
                                                 : catalogues.aggregate_profile_id();
            if(water[i]!=0. || slope[i]>=catalogues.profile(people).trait("work_slope_limit")
               || owner[i]<0 || distance[i]>cfg.support_reach) continue;
            double step=0.;
            if(i!=node && !shared(node,i,pair.second,step)) continue;
            // Ground belonging to a city that has fought outranks equally defensible
            // ground belonging to one that has not.
            const double veteran_bonus=owner[i]>=0 ? .5*static_cast<double>(veteran[static_cast<std::size_t>(owner[i])]) : 0.;
            const double value=base+std::max(-.5,std::min(1.,tpi[i]/30))-.5*flood[i]-slope[i]/40-pair.second/500+veteran_bonus;
            const auto found=strategic.find(i);
            if(found==strategic.end() || value>found->second.first) strategic[i]={value,node};
        }
    }
    std::vector<std::pair<std::size_t,std::pair<double,std::size_t>>> ranked(strategic.begin(),strategic.end());
    std::stable_sort(ranked.begin(),ranked.end(),[](const auto& a,const auto& b) {
        if(a.second.first!=b.second.first) return a.second.first>b.second.first;
        return a.first<b.first;
    });
    for(const auto& entry:ranked) {
        if(static_cast<std::int64_t>(humans.fortresses.size())>=fortress_limit) break;
        if(!separated(entry.first,200)) continue;
        RuralSite fort=record(entry.first,"fortress",humans.fortresses.size(),
            "Nearby city road; junction/crossing importance and elevated surroundings");
        fort.defence_score=entry.second.first;
        fort.protected_route_node=entry.second.second;
        humans.fortresses.push_back(fort);
        occupied.push_back(entry.first);
    }
    // What each city's hinterland delivers. Food trading between cities is reporting
    // the final world does not read, so the shipments themselves are not computed.
    for(std::size_t index=0;index<sites.size();++index) {
        CityCore core;
        core.site_id=static_cast<std::int64_t>(index);
        core.population_profile=sites[index].population_profile;
        core.culture_id=culture_ids.at(humans.groups[index]);
        Sum supply,materials;
        for(const RuralSite& hamlet:humans.hamlets)
            if(hamlet.core_id==static_cast<std::int64_t>(index)) {
                core.hamlet_ids.push_back(hamlet.id);
                supply.add(hamlet.delivered_food);
                materials.add(hamlet.delivered_materials);
            }
        for(const RuralSite& fort:humans.fortresses)
            if(fort.core_id==static_cast<std::int64_t>(index)) core.fortress_ids.push_back(fort.id);
        core.food_supply=supply.value();
        core.material_supply=materials.value();
        core.food_demand=index<residents.size()
            ? catalogues.profile(core.population_profile).trait("food_demand")
              *static_cast<double>(residents[index].urban)/100
            : cfg.urban_food_demand;
        core.food_deficit=std::max(0.,cfg.urban_food_demand-core.food_supply);
        humans.cores.push_back(core);
    }
    humans.culture_region.assign(count,-1.);
    humans.civilization_region.assign(count,-1.);
    for(std::size_t i=0;i<count;++i) {
        if(owner[i]<0 || distance[i]>cfg.support_reach) continue;
        humans.culture_region[i]=static_cast<double>(humans.groups[static_cast<std::size_t>(owner[i])]);
        const std::string& people=sites[static_cast<std::size_t>(owner[i])].population_profile;
        for(std::size_t k=0;k<ids.size();++k) if(ids[k]==people) humans.civilization_region[i]=static_cast<double>(k);
    }
    layers.food_potential=node_grid(humans.food_potential,grid);
    layers.natural_food_potential=node_grid(humans.natural_food_potential,grid);
    layers.irrigation_benefit=node_grid(humans.irrigation_benefit,grid);
    layers.culture_region=node_grid(humans.culture_region,grid);
    layers.hamlet_catchment=node_grid(humans.hamlet_catchment,grid);
    layers.civilization_region=node_grid(humans.civilization_region,grid);
    return humans;
}
}
