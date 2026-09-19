#include "cityplan.hpp"
#include "counter.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <set>
namespace fantasy_world_generator {
namespace {
using Entry=std::pair<double,std::size_t>;
// The reference resolves a count from the authoring spec and the residents, which are
// unknown until the population round; an absent resident count keeps the base.
std::int64_t resolve_count(const FeatureCount& feature,bool has_residents,double residents) {
    double base=feature.base;
    if(has_residents) base+=feature.per_100_residents*(std::max(0.,residents)/100);
    auto count=static_cast<std::int64_t>(std::floor(base));
    if(feature.has_min) count=std::max(count,feature.minimum);
    if(feature.has_max) count=std::min(count,feature.maximum);
    return std::max<std::int64_t>(0,count);
}
bool listed(const std::vector<std::string>& names,const std::string& name) {
    return std::find(names.begin(),names.end(),name)!=names.end();
}
bool fits_profile(const FeatureCount& feature,const std::string& population_profile) {
    return !feature.has_profiles || listed(feature.profiles,population_profile);
}
// random.choices is not used here: the reference walks the options with one uniform
// draw and a running cursor, and an empty or zero-weight list takes the first entry.
std::string weighted_pick(PyRandom& rng,const std::vector<BuildingChoice>& choices) {
    Sum total;
    for(const BuildingChoice& choice:choices) total.add(choice.weight);
    if(total.value()<=0) return choices.front().asset_id;
    const double draw=rng.next()*total.value();
    double cursor=0.;
    for(const BuildingChoice& choice:choices) {
        cursor+=choice.weight;
        if(draw<=cursor) return choice.asset_id;
    }
    return choices.back().asset_id;
}
// Walks the candidate ring from a cursor, skipping nodes another district already
// claimed, and reports whether it ran out before the target count.
struct AnchorPicker {
    const SphereGrid* grid=nullptr;
    std::set<std::size_t>* used=nullptr;
    const std::map<std::size_t,double>* distance=nullptr;
    bool collect(const std::vector<std::size_t>& candidates,std::int64_t target,std::size_t& cursor,
                 std::vector<PlanAnchor>& anchors) const {
        if(target<=0) return false;
        if(candidates.empty()) return true;
        const std::size_t count=candidates.size();
        std::int64_t attempts=0;
        const std::int64_t limit=target*static_cast<std::int64_t>(std::max<std::size_t>(1,count));
        cursor%=count;
        while(static_cast<std::int64_t>(anchors.size())<target && attempts<limit) {
            const std::size_t node=candidates[cursor];
            cursor=(cursor+1)%count;
            ++attempts;
            if(used->count(node)!=0) continue;
            used->insert(node);
            PlanAnchor anchor;
            anchor.node=node;
            anchor.x=grid->points[node].first;
            anchor.z=grid->points[node].second;
            const auto found=distance->find(node);
            anchor.distance_to_city_m=found==distance->end() ? 0. : found->second;
            anchor.sequence=static_cast<std::int64_t>(anchors.size());
            anchors.push_back(anchor);
        }
        return static_cast<std::int64_t>(anchors.size())<target;
    }
};
}
std::vector<double> river_distances(const SphereGrid& grid,const std::vector<double>& river) {
    std::vector<double> distance(grid.points.size(),std::numeric_limits<double>::infinity());
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(std::size_t node=0;node<grid.points.size();++node)
        if(river[node]!=0.) {distance[node]=0.;queue.emplace(0.,node);}
    while(!queue.empty()) {
        const Entry entry=queue.top();queue.pop();
        if(entry.first!=distance[entry.second]) continue;
        for(const auto& edge:grid.neighbors[entry.second]) {
            const auto j=static_cast<std::size_t>(edge.first);
            const double candidate=entry.first+edge.second;
            if(candidate<distance[j]) {distance[j]=candidate;queue.emplace(candidate,j);}
        }
    }
    return distance;
}
std::string pick_building_pack(std::uint32_t city_seed,const CityCatalogues& city,
                               const std::string& population_profile,std::int64_t biome,
                               const std::string& variant,double height_m,double slope_degrees,
                               double resource,double freshwater_distance_m) {
    std::vector<const BuildingPack*> candidates;
    for(const BuildingPack& pack:city.packs) {
        if(pack.has_profiles && !listed(pack.profiles,population_profile)) continue;
        if((pack.has_biomes || !pack.biome_variants.empty())
           && !(pack.has_biomes && std::find(pack.biomes.begin(),pack.biomes.end(),biome)!=pack.biomes.end())
           && !listed(pack.biome_variants,variant)) continue;
        if(!(pack.height_min<=height_m && height_m<=pack.height_max)) continue;
        if(resource<pack.resource_min || resource>pack.resource_max) continue;
        if(slope_degrees>pack.slope_max) continue;
        if(!(pack.water_distance_min<=freshwater_distance_m
             && freshwater_distance_m<=pack.water_distance_max)) continue;
        candidates.push_back(&pack);
    }
    if(candidates.empty()) return city.fallback_pack_id;
    Sum total;
    for(const BuildingPack* pack:candidates) total.add(pack->weight);
    PyRandom rng(city_seed);
    const double draw=rng.next()*total.value();
    double current=0.;
    for(const BuildingPack* pack:candidates) {
        current+=pack->weight;
        if(draw<=current) return pack->id;
    }
    return candidates.back()->id;
}
const LayoutProfile& pick_layout_profile(const CityCatalogues& city,const BuildingPack& pack,
                                         bool river_distance_finite,double river_distance_m) {
    const LayoutProfile* riverfront=city.layout("riverfront_city_layout");
    if(pack.has_layout_profile) {
        const LayoutProfile* forced=city.layout(pack.layout_profile_id);
        if(forced!=nullptr) return *forced;
    }
    const LayoutProfile* fallback=city.layout(city.fallback_profile_id);
    if(fallback==nullptr) throw Error("INVALID_INPUT");
    if(riverfront==nullptr) return *fallback;
    if(river_distance_finite && river_distance_m<=riverfront->placement.river_buffer_m*1.8) return *riverfront;
    return *fallback;
}
namespace {
// The walkable land around a city, ordered by walking distance then node: every
// district and building claims from this one ring, so its order is the plan's order.
std::vector<std::pair<double,std::size_t>> land_anchor_candidates(
    const SphereGrid& grid,std::size_t start,const std::vector<double>& rivers_distance,
    const std::vector<double>& water,const std::vector<double>& slope,double max_slope,
    double min_river_distance) {
    const double max_walk=std::isfinite(min_river_distance)
        ? std::max(180.,4*min_river_distance+180) : 800.;
    std::vector<double> distance(grid.points.size(),std::numeric_limits<double>::infinity());
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    distance[start]=0.;
    queue.emplace(0.,start);
    std::vector<std::pair<double,std::size_t>> candidates;
    while(!queue.empty()) {
        const Entry entry=queue.top();queue.pop();
        if(entry.first!=distance[entry.second]) continue;
        if(entry.first>max_walk) continue;
        if(water[entry.second]==0. && slope[entry.second]<=max_slope
           && (std::isinf(min_river_distance) || rivers_distance[entry.second]>=min_river_distance))
            candidates.emplace_back(entry.first,entry.second);
        for(const auto& edge:grid.neighbors[entry.second]) {
            const auto j=static_cast<std::size_t>(edge.first);
            const double candidate=entry.first+edge.second;
            if(candidate<distance[j]) {distance[j]=candidate;queue.emplace(candidate,j);}
        }
    }
    std::stable_sort(candidates.begin(),candidates.end(),
                     [](const std::pair<double,std::size_t>& a,const std::pair<double,std::size_t>& b) {
                         if(a.first!=b.first) return a.first<b.first;
                         return a.second<b.second;
                     });
    return candidates;
}
}
CityPlan build_city_plan(std::uint32_t city_seed,std::size_t node,const SphereGrid& grid,
                         const CityCatalogues& city,const BuildingPack& pack,
                         const LayoutProfile& layout,const std::string& population_profile,
                         bool river_distance_finite,double river_distance_m,
                         const std::vector<double>& river,const std::vector<double>& water,
                         const std::vector<double>& slope,const std::vector<double>& rivers_distance,
                         bool has_residents,double residents) {
    (void)city;
    PyRandom rng(city_seed);
    CityPlan plan;
    plan.has_residents=has_residents;
    plan.residents=residents;
    plan.city_seed=city_seed;
    plan.layout_profile_id=layout.id;
    plan.layout_profile_name=layout.name;
    plan.population_profile=population_profile;
    plan.building_pack_id=pack.id;
    std::int64_t fork_degree=0;
    for(const auto& edge:grid.neighbors[node])
        if(river[static_cast<std::size_t>(edge.first)]!=0.) ++fork_degree;
    plan.adjacent_river_edges=fork_degree;
    plan.river_distance_finite=river_distance_finite;
    plan.river_distance_m=river_distance_finite ? river_distance_m : 0.;
    plan.bridge_threshold=layout.placement.river_fork_bridge_threshold;
    plan.bridge_recommended=fork_degree>=layout.placement.river_fork_bridge_threshold
                            && layout.placement.bridge_if_river_fork;
    const std::vector<std::pair<double,std::size_t>> candidates=land_anchor_candidates(
        grid,node,rivers_distance,water,slope,layout.placement.max_anchor_slope_degrees,
        layout.placement.river_buffer_m);
    std::vector<std::size_t> ordered;
    std::set<std::size_t> seen;
    std::map<std::size_t,double> anchor_distance;
    for(const auto& candidate:candidates) {
        anchor_distance.emplace(candidate.second,candidate.first);
        if(seen.insert(candidate.second).second) ordered.push_back(candidate.second);
    }
    std::set<std::size_t> used;
    AnchorPicker picker{&grid,&used,&anchor_distance};
    // The district ring starts at a seeded offset, so two cities with the same terrain
    // do not lay out identically.
    const std::size_t rotation=ordered.empty()
        ? 0 : static_cast<std::size_t>(rng.randrange(0,static_cast<std::int64_t>(ordered.size())));
    if(!ordered.empty()) std::rotate(ordered.begin(),ordered.begin()+static_cast<std::ptrdiff_t>(rotation),
                                     ordered.end());
    static const char* feature_order[]={"leader_homes","barracks","noble_homes","worker_housing",
                                        "apartments","market_district","religious_building"};
    std::size_t cursor=0;
    bool missing_anchors=false;
    for(const char* name:feature_order) {
        const auto found=layout.features.find(name);
        if(found==layout.features.end()) throw Error("INVALID_INPUT");
        const FeatureCount& spec=found->second;
        std::int64_t count=resolve_count(spec,plan.has_residents,plan.residents);
        if(!fits_profile(spec,population_profile)) count=0;
        PlanFeature feature;
        feature.name=name;
        feature.target_count=count;
        for(std::size_t k=cursor;k<ordered.size() && static_cast<std::int64_t>(feature.anchors.size())<count;++k) {
            PlanAnchor anchor;
            anchor.node=ordered[k];
            anchor.x=grid.points[ordered[k]].first;
            anchor.z=grid.points[ordered[k]].second;
            const auto distance=anchor_distance.find(ordered[k]);
            anchor.distance_to_city_m=distance==anchor_distance.end() ? 0. : distance->second;
            feature.anchors.push_back(anchor);
            used.insert(ordered[k]);
        }
        cursor+=feature.anchors.size();
        if(static_cast<std::int64_t>(feature.anchors.size())<count) missing_anchors=true;
        plan.features.push_back(feature);
    }
    if(missing_anchors)
        plan.fallback_reason="Not enough valid non-water land anchors for requested feature counts "
                             "within local search band.";
    // Buildings share the ring and the claimed set with the districts above.
    std::vector<std::size_t> river_frontier,boundary;
    for(std::size_t candidate:ordered) {
        bool touches_river=false,touches_outside=false;
        for(const auto& edge:grid.neighbors[candidate]) {
            const auto j=static_cast<std::size_t>(edge.first);
            if(j<river.size() && river[j]!=0.) touches_river=true;
            if(seen.count(j)==0) touches_outside=true;
        }
        if(touches_river) river_frontier.push_back(candidate);
        if(touches_outside) boundary.push_back(candidate);
    }
    std::size_t anchor_cursor=ordered.empty()
        ? 0 : static_cast<std::size_t>(rng.randrange(0,static_cast<std::int64_t>(ordered.size())));
    std::size_t wall_cursor=0;
    std::map<std::string,std::int64_t> required;
    bool building_missing=false;
    for(const BuildingOption& option:pack.building_options) {
        if(option.has_profiles && !listed(option.profiles,population_profile)) continue;
        BuildingOptionPlan emitted;
        emitted.option_id=option.id;
        emitted.name=option.name;
        emitted.placement=option.placement;
        emitted.required=option.required;
        emitted.bridge_required=option.requires_bridge;
        emitted.tags=option.tags;
        std::sort(emitted.tags.begin(),emitted.tags.end());
        emitted.target_count=resolve_count(option.count,plan.has_residents,plan.residents);
        if(emitted.target_count==0) {plan.options.push_back(emitted);continue;}
        std::int64_t planned=emitted.target_count;
        bool has_missing=false;
        if(option.placement=="anchored") {
            has_missing=picker.collect(ordered,emitted.target_count,anchor_cursor,emitted.anchors);
            planned=static_cast<std::int64_t>(emitted.anchors.size());
        } else if(option.placement=="river_gate") {
            if(option.requires_bridge && !plan.bridge_recommended) {
                has_missing=option.required;
                planned=0;
            } else {
                std::vector<std::size_t> gates(river_frontier.rbegin(),river_frontier.rend());
                has_missing=picker.collect(gates,emitted.target_count,anchor_cursor,emitted.anchors);
                planned=static_cast<std::int64_t>(emitted.anchors.size());
            }
        } else if(option.placement=="wall") {
            std::vector<std::size_t> walls;
            if(!boundary.empty()) {
                walls=boundary;
                std::stable_sort(walls.begin(),walls.end(),[&](std::size_t a,std::size_t b) {
                    const auto left=anchor_distance.find(a),right=anchor_distance.find(b);
                    const double first=left==anchor_distance.end() ? 0. : left->second;
                    const double second=right==anchor_distance.end() ? 0. : right->second;
                    return first>second;
                });
            } else {
                walls.assign(ordered.rbegin(),ordered.rend());
            }
            has_missing=picker.collect(walls,emitted.target_count,wall_cursor,emitted.anchors);
            planned=static_cast<std::int64_t>(emitted.anchors.size());
        } else if(option.placement=="structural") {
            has_missing=false;
        } else {
            throw Error("INVALID_INPUT");
        }
        if(has_missing) building_missing=true;
        if(!option.asset_choices.empty())
            for(std::int64_t k=0;k<planned;++k) {
                const std::string asset=weighted_pick(rng,option.asset_choices);
                emitted.assets.push_back(asset);
                required[asset]+=1;
            }
        emitted.required_node_slots=static_cast<std::int64_t>(emitted.anchors.size());
        plan.required_node_slots+=emitted.required_node_slots;
        if(option.placement=="river_gate" && option.requires_bridge && !plan.bridge_recommended)
            emitted.skip_reason="requires_bridge";
        plan.options.push_back(emitted);
    }
    for(const auto& entry:required) {
        plan.required_assets.push_back(entry);
        plan.required_asset_count+=entry.second;
    }
    plan.missing_anchors=building_missing;
    if(building_missing)
        plan.fallback_reason="Not enough valid non-water land anchors for requested feature and "
                             "building placement counts within local search band.";
    return plan;
}
std::vector<PopulationEstimate> estimate_population(const PopulationBudget& budget,
                                                    const std::vector<FoundedCity>& sites) {
    std::vector<PopulationEstimate> estimates(sites.size());
    for(const auto& entry:budget.allowances) {
        std::vector<std::size_t> members;
        for(std::size_t index=0;index<sites.size();++index)
            if(sites[index].population_profile==entry.first) members.push_back(index);
        if(members.empty()) continue;
        const auto count=static_cast<std::int64_t>(members.size());
        for(std::size_t position=0;position<members.size();++position) {
            PopulationEstimate estimate;
            estimate.residents=entry.second/count
                +(static_cast<std::int64_t>(position)<entry.second%count ? 1 : 0);
            // Python's round is banker's rounding, and half the cities land on .5.
            estimate.urban=static_cast<std::int64_t>(std::nearbyint(static_cast<double>(estimate.residents)*.55));
            estimate.rural=estimate.residents-estimate.urban;
            estimates[members[position]]=estimate;
        }
    }
    return estimates;
}
std::vector<CityPlan> plan_cities(const WorldConfig& cfg,const SphereGrid& grid,const Catalogues& catalogues,
                                  const Layers& layers,const SettlementFields& fields,
                                  const std::vector<FoundedCity>& sites,
                                  const std::vector<PopulationEstimate>& residents) {
    const CityCatalogues& city=catalogues.city();
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> slope=node_values(layers.slope,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    const std::vector<double> biome=node_values(layers.biome,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<std::string> variants=biome_variants(layers,grid);
    const std::vector<double> rivers_distance=river_distances(grid,river);
    const std::uint32_t seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"settlements");
    std::vector<CityPlan> plans;
    for(std::size_t index=0;index<sites.size();++index) {
        const FoundedCity& site=sites[index];
        const std::int64_t x=grid.points[site.node].first,z=grid.points[site.node].second;
        const std::string domain="building-pack-"+std::to_string(site.node)+"-"+std::to_string(index)
            +"-"+std::to_string(x)+"-"+std::to_string(z)+"-"+site.population_profile;
        const std::uint32_t city_seed=child_seed(static_cast<std::uint64_t>(seed),domain);
        // The freshwater layer already reports an unreachable cell as -1, which is what
        // the pack criteria are written against. The layout choice reads the separate
        // river distance, where unreachable stays infinite.
        const double criteria_distance=fields.freshwater_distance[site.node];
        const std::string chosen=pick_building_pack(city_seed,city,site.population_profile,
                                                    static_cast<std::int64_t>(biome[site.node]),
                                                    variants[site.node],height[site.node],
                                                    slope[site.node],fields.resource[site.node],
                                                    criteria_distance);
        const BuildingPack* pack=nullptr;
        for(const BuildingPack& entry:city.packs) if(entry.id==chosen) pack=&entry;
        if(pack==nullptr) pack=&city.pack(city.fallback_pack_id);
        const double river_distance=rivers_distance[site.node];
        const bool finite=std::isfinite(river_distance);
        const LayoutProfile& layout=pick_layout_profile(city,*pack,finite,river_distance);
        CityPlan plan=build_city_plan(city_seed,site.node,grid,city,*pack,layout,site.population_profile,
                                      finite,river_distance,river,water,slope,rivers_distance,
                                      index<residents.size(),
                                      index<residents.size() ? static_cast<double>(residents[index].residents) : 0.);
        plans.push_back(plan);
    }
    return plans;
}
}
