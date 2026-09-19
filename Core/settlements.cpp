#include "settlements.hpp"
#include "biomes.hpp"
#include "counter.hpp"
#include "magic.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <set>
namespace fantasy_world_generator {
namespace {
constexpr double infinite=std::numeric_limits<double>::infinity();
double clamp01(double v) {return std::max(0.,std::min(1.,v));}
// One terrain-cost owner per node, deterministic ties, no water shortcuts. The label
// orders equal-distance claims, so a cheaper owner never loses to arrival order.
struct Access {std::vector<double> distance;std::vector<std::int64_t> owner;};
template<typename Cost>
Access allocate_access(const SphereGrid& grid,const std::vector<std::pair<std::size_t,std::int64_t>>& seeds,
                       Cost cost,double limit) {
    const std::size_t count=grid.points.size();
    Access access;
    access.distance.assign(count,infinite);
    access.owner.assign(count,-1);
    using Entry=std::tuple<double,std::int64_t,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(const auto& seed:seeds) {
        access.distance[seed.first]=0.;
        access.owner[seed.first]=seed.second;
        queue.emplace(0.,seed.second,seed.first);
    }
    while(!queue.empty()) {
        const auto entry=queue.top();queue.pop();
        const double value=std::get<0>(entry);
        const std::int64_t label=std::get<1>(entry);
        const std::size_t i=std::get<2>(entry);
        if(value!=access.distance[i] || label!=access.owner[i]) continue;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            double step=0.;
            if(!cost(i,j,edge.second,step)) continue;
            const double candidate=value+step;
            if(candidate<=limit && (candidate<access.distance[j]
                                    || (candidate==access.distance[j] && label<access.owner[j]))) {
                access.distance[j]=candidate;access.owner[j]=label;
                queue.emplace(candidate,label,j);
            }
        }
    }
    return access;
}
// A road edge: no water, no unsafe magic, no diagonal slipping between water corners,
// and no grade the people's roads cannot climb.
bool road_step(const WorldConfig& cfg,const SphereGrid& grid,const std::vector<double>& water,
               const std::vector<double>& height,const std::vector<double>& flood,
               const std::vector<double>& river,const std::vector<double>& hazard,
               std::size_t i,std::size_t j,double d,double& step) {
    if(water[i]!=0. || water[j]!=0. || d<=0) return false;
    if(std::max(hazard[i],hazard[j])>cfg.human_magic_limit) return false;
    const std::int64_t xi=grid.points[i].first,zi=grid.points[i].second;
    const std::int64_t xj=grid.points[j].first,zj=grid.points[j].second;
    if(xi!=xj && zi!=zj && zi!=0 && zi!=cfg.size-1 && zj!=0 && zj!=cfg.size-1) {
        const auto first=static_cast<std::size_t>(grid.index(xi,zj));
        const auto second=static_cast<std::size_t>(grid.index(xj,zi));
        if(water[first]!=0. || water[second]!=0.) return false;
        if(std::max(hazard[first],hazard[second])>cfg.human_magic_limit) return false;
    }
    const double grade=std::fabs(height[j]-height[i])/d;
    if(grade>cfg.road_max_grade) return false;
    step=d*(1+12*std::pow(grade,2.)+.5*(flood[i]+flood[j]))+((river[i]!=0. || river[j]!=0.) ? cfg.bridge_cost : 0.);
    return true;
}
// A sea lane: open water deep enough to sail, with the same diagonal rule.
bool water_step(const SphereGrid& grid,const std::vector<double>& water,const std::vector<double>& depth,
                const std::vector<double>& hazard,double limit,double draft,
                std::size_t i,std::size_t j,double d,double& step) {
    auto passable=[&](std::size_t node) {
        return water[node]==1. && depth[node]>=draft && hazard[node]<=limit;
    };
    if(!passable(i) || !passable(j)) return false;
    const std::int64_t xi=grid.points[i].first,zi=grid.points[i].second;
    const std::int64_t xj=grid.points[j].first,zj=grid.points[j].second;
    const std::int64_t last=grid.n-1;
    if(xi!=xj && zi!=zj && zi!=0 && zi!=last && zj!=0 && zj!=last) {
        if(!passable(static_cast<std::size_t>(grid.index(xi,zj)))) return false;
        if(!passable(static_cast<std::size_t>(grid.index(xj,zi)))) return false;
    }
    step=d;
    return true;
}
}
namespace {
void evaluate_population_budget(const WorldConfig& cfg,const SphereGrid& grid,const Catalogues& catalogues,
                                SettlementFields& result);
}
namespace {
// 100 residents per fully productive square kilometre: an explicit provisional food
// calibration, not a validated agricultural yield. Overlapping peoples divide a cell's
// best supported capacity between them; they never multiply it.
void evaluate_population_budget(const WorldConfig& cfg,const SphereGrid& grid,const Catalogues& catalogues,
                                SettlementFields& result) {
    const std::vector<std::string>& species=catalogues.civilization_ids();
    std::map<std::string,double> totals;
    for(const std::string& id:species) totals.emplace(id,0.);
    double total=0.;
    for(std::size_t i=0;i<grid.areas.size();++i) {
        Sum weight;
        double best=0.;
        bool first=true;
        for(const std::string& id:species) {
            const double value=result.species.at(id).potential[i];
            weight.add(value);
            if(first || value>best) {best=value;first=false;}
        }
        if(!(weight.value()>0)) continue;
        const double capacity=grid.areas[i]/1e6*100*best;
        total+=capacity;
        for(const std::string& id:species)
            totals.at(id)+=capacity*result.species.at(id).potential[i]/weight.value();
    }
    PopulationBudget& budget=result.budget;
    budget.world_cap=static_cast<std::int64_t>(std::floor(total));
    for(const std::string& id:species)
        budget.allowances.emplace(id,static_cast<std::int64_t>(std::floor(totals.at(id))));
    for(const std::string& id:species) {
        const Profile& profile=catalogues.profile(id);
        const SpeciesField& field=result.species.at(id);
        Sum footprint;
        for(std::size_t i:field.candidates) footprint.add(grid.areas[i]*field.suitability[i]);
        const double weighted=footprint.value()/1e6;
        budget.weighted_habitat_km2.emplace(id,weighted);
        const std::int64_t minimum=static_cast<std::int64_t>(profile.trait("minimum_founding_residents"));
        const std::int64_t by_land=static_cast<std::int64_t>(std::floor(weighted/profile.trait("land_per_city_km2")));
        const std::int64_t by_food=minimum>0 ? budget.allowances.at(id)/minimum : 0;
        budget.quotas.emplace(id,std::min(by_land,by_food));
        budget.shares.emplace(id,budget.world_cap ? static_cast<double>(budget.allowances.at(id))
                                                    /static_cast<double>(budget.world_cap) : 0.);
    }
    // The shared ceiling is the ground itself: cities stand a settlement spacing
    // apart, so habitable land divided by the densest packing of that separation is
    // how many can exist at all. It applies after every people is assessed, so an
    // early registry entry cannot exhaust the budget before a later one is considered.
    std::set<std::size_t> habitable;
    for(const std::string& id:species)
        for(std::size_t node:result.species.at(id).candidates) habitable.insert(node);
    Sum habitable_area;
    for(std::size_t node:habitable) habitable_area.add(grid.areas[node]);
    const double per_city_km2=std::sqrt(3.)/2*std::pow(cfg.settlement_spacing/1000,2.);
    const std::int64_t packing=per_city_km2>0
        ? static_cast<std::int64_t>(std::floor(habitable_area.value()/1e6/per_city_km2)) : 0;
    budget.habitable_km2=habitable_area.value()/1e6;
    budget.spacing_ceiling=packing;
    // A world that infers its own quotas is ceilinged by its ground, not by a count
    // the caller never set. The quota above is inferred for any recipe world or mixed
    // population, and the ceiling has to agree with it.
    const bool inferred=cfg.world_recipe!=0 || cfg.auto_parameters!=0 || cfg.population_profile=="mixed";
    // Asking for no cities is not the same as asking for no ceiling, and it outranks
    // the ground: a caller who wants an empty world gets one, inferred or not.
    const bool none_wanted=cfg.auto_parameters==0 && cfg.settlement_count==0;
    if(none_wanted) for(auto& entry:budget.quotas) entry.second=0;
    const std::int64_t limit=none_wanted ? 0
        : inferred ? packing : std::min(packing,cfg.settlement_count);
    budget.city_limit=limit;
    while(true) {
        std::int64_t requested=0;
        for(const auto& entry:budget.quotas) requested+=entry.second;
        if(requested<=limit) break;
        std::string highest;
        for(const auto& entry:budget.quotas) {
            if(highest.empty() || entry.second>budget.quotas.at(highest)
               || (entry.second==budget.quotas.at(highest) && entry.first>highest)) highest=entry.first;
        }
        --budget.quotas.at(highest);
    }
}
}
std::vector<LandmassContext> landmass_context(const SphereGrid& grid,const std::vector<double>& water) {
    const std::size_t count=grid.points.size();
    std::vector<LandmassContext> contexts(count);
    std::set<std::size_t> remaining;
    for(std::size_t i=0;i<count;++i) if(water[i]==0.) remaining.insert(i);
    std::vector<std::pair<std::vector<std::size_t>,double>> components;
    while(!remaining.empty()) {
        const std::size_t start=*remaining.begin();
        remaining.erase(remaining.begin());
        std::vector<std::size_t> members{start},stack{start};
        while(!stack.empty()) {
            const std::size_t i=stack.back();stack.pop_back();
            for(const auto& edge:grid.neighbors[i]) {
                const auto j=static_cast<std::size_t>(edge.first);
                if(remaining.erase(j)) {members.push_back(j);stack.push_back(j);}
            }
        }
        Sum area;
        for(std::size_t i:members) area.add(grid.areas[i]);
        components.emplace_back(members,area.value());
    }
    Sum total;
    double largest=0.;
    for(const auto& component:components) {total.add(component.second);largest=std::max(largest,component.second);}
    for(const auto& component:components) {
        for(std::size_t i:component.first) {
            contexts[i].area_m2=component.second;
            contexts[i].fraction=total.value() ? component.second/total.value() : 0.;
            contexts[i].largest=component.second==largest;
        }
    }
    return contexts;
}
std::vector<std::string> biome_variants(const Layers& layers,const SphereGrid& grid) {
    // The magical catalogue is the natural cores crossed with the schools, in that
    // order; a cell carries the identity of the school that dominates it.
    std::vector<std::string> variants(grid.points.size());
    for(std::size_t i=0;i<grid.points.size();++i) {
        const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
        const auto school=static_cast<std::int64_t>(layers.dominant_magic[z][x]);
        if(school<0) continue;
        const auto identity=static_cast<std::int64_t>(layers.natural_biome[z][x]);
        for(const auto& entry:natural_catalogue()) {
            if(entry.id!=identity) continue;
            variants[i]=std::string(entry.core)+"."+school_names()[static_cast<std::size_t>(school)];
            break;
        }
    }
    return variants;
}
Farming farming_potential(const Profile& profile,double slope,double temperature,double moisture,
                          double flood,double freshwater_distance,double adaptation) {
    const double comfort=profile.trait("food_slope_comfort");
    const double ideal=profile.trait("food_temperature_ideal");
    const double tolerance=profile.trait("food_temperature_tolerance");
    const double wet_ideal=profile.trait("food_moisture_ideal");
    const double terrain=std::exp(-std::pow(slope/comfort,2.))
        *std::max(0.,1-std::fabs(temperature-ideal)/tolerance)*(1-.7*flood);
    const double natural=terrain*std::max(0.,1-std::fabs(moisture-wet_ideal)/wet_ideal);
    const double access=freshwater_distance>=0 ? std::exp(-freshwater_distance/profile.trait("water_reach")) : 0.;
    const double irrigation=adaptation*access*std::max(0.,(wet_ideal-moisture)/wet_ideal);
    // Maintenance reduces the added exportable surplus; no source means no irrigation.
    return Farming{natural,natural+.75*terrain*irrigation};
}
SettlementFields evaluate_settlement_fields(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                                            const Catalogues& catalogues,Layers& layers) {
    (void)radius;
    const std::size_t count=grid.points.size();
    const double span=static_cast<double>(cfg.size-1);
    SettlementFields result;
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    const std::vector<double> slope=node_values(layers.slope,grid);
    const std::vector<double> temperature=node_values(layers.temperature,grid);
    const std::vector<double> moisture=node_values(layers.moisture,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<double> hazard=node_values(layers.magic_hazard,grid);
    const std::vector<double> depth=node_values(layers.water_depth,grid);
    const std::vector<double> tpi=node_values(layers.tpi,grid);
    const std::vector<double> coastal_support=node_values(layers.coastal_support,grid);
    const std::vector<double> maritime=node_values(layers.maritime,grid);
    const std::vector<double> fishing=node_values(layers.fishing_productivity,grid);
    result.resource=node_values(layers.metal_richness,grid);
    result.flood=node_values(layers.flood_risk,grid);
    result.freshwater_distance=node_values(layers.freshwater_distance,grid);
    const std::vector<LandmassContext> contexts=landmass_context(grid,water);
    const std::vector<std::string> variants=biome_variants(layers,grid);

    // Each people scores the whole world, then keeps the cells it can actually live on.
    for(const std::string& species:catalogues.civilization_ids()) {
        const Profile& profile=catalogues.profile(species);
        const EntityRules& rules=catalogues.entity(species);
        SpeciesField field;
        field.suitability.assign(count,0.);
        field.potential.assign(count,0.);
        for(std::size_t i=0;i<count;++i) {
            const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
            const auto identity=static_cast<std::int64_t>(layers.biome[z][x]);
            const double fresh=std::isfinite(result.freshwater_distance[i]) && result.freshwater_distance[i]>=0
                ? result.freshwater_distance[i] : -1.;
            const double distance=fresh>=0 ? fresh : infinite;
            double score=profile.trait("water_weight")*std::exp(-distance/profile.trait("water_reach"))
                +profile.trait("slope_weight")*std::exp(-std::pow(slope[i]/profile.trait("slope_comfort"),2.))
                +profile.trait("climate_weight")*std::exp(-std::pow((temperature[i]-profile.trait("temperature_ideal"))
                                                                    /profile.trait("temperature_tolerance"),2.))
                +profile.trait("moisture_weight")*std::max(0.,1-std::fabs(moisture[i]-profile.trait("moisture_ideal")))
                +profile.trait("resource_weight")*result.resource[i]
                -profile.trait("flood_penalty")*result.flood[i]
                +biome_preference(profile,identity,variants[i])
                -profile.trait("magic_penalty")*hazard[i];
            score+=coastal_support[i]*rules.coastal_score_weight;
            if(rules.resource_score_weight!=0.) score+=rules.resource_score_weight*result.resource[i];
            field.suitability[i]=water[i]==0. ? clamp01(score) : 0.;

            Environment environment;
            environment.landmass_area_m2=contexts[i].area_m2;
            environment.landmass_fraction=contexts[i].fraction;
            environment.largest_landmass=contexts[i].largest;
            environment.abs_latitude=std::fabs(90-180*static_cast<double>(z)/span);
            environment.biome=static_cast<double>(identity);
            environment.temperature=temperature[i];
            environment.moisture=moisture[i];
            environment.maritime=maritime[i];
            environment.resource=result.resource[i];
            environment.slope=slope[i];
            environment.height=height[i];
            environment.tpi=tpi[i];
            environment.variant=variants[i];
            environment.coastal_support=coastal_support[i];
            const std::vector<std::string> eligible=catalogues.eligible_civilizations(environment);
            bool habitat=std::find(eligible.begin(),eligible.end(),species)!=eligible.end();
            habitat=habitat && matches(rules.world_habitat,environment);
            if(identity==17) habitat=false;   // nobody founds on permanent land ice
            const bool safe=water[i]==0. && hazard[i]<=profile.trait("mutation_limit");
            bool suitable=habitat && safe && slope[i]<profile.trait("site_slope_limit");
            if(rules.has_freshwater_reach_multiplier)
                suitable=suitable && distance<=profile.trait("water_reach")*rules.freshwater_reach_multiplier;
            if(suitable) field.candidates.push_back(i);
            Farming farming=farming_potential(profile,slope[i],temperature[i],moisture[i],result.flood[i],
                                              fresh,profile.trait("irrigation"));
            double food=farming.supported*biome_food_multiplier(profile,identity,variants[i])*(1-hazard[i]);
            if(identity==17) food=0.;
            const bool productive=safe && slope[i]<profile.trait("work_slope_limit")
                && (suitable || rules.support_outside_habitat);
            field.potential[i]=productive ? food : 0.;
        }
        if(rules.support_outside_habitat) {
            // Support must follow passable terrain, not a circle drawn across water or
            // cliffs, so the productive hinterland is routed, not measured as the crow flies.
            std::vector<std::pair<std::size_t,std::int64_t>> seeds;
            for(std::size_t k=0;k<field.candidates.size();++k)
                seeds.emplace_back(field.candidates[k],static_cast<std::int64_t>(k));
            const Access access=allocate_access(grid,seeds,
                [&](std::size_t i,std::size_t j,double d,double& step) {
                    return road_step(cfg,grid,water,height,result.flood,river,hazard,i,j,d,step);
                },cfg.support_reach);
            field.support_reach.assign(count,0.);
            for(std::size_t i=0;i<count;++i) {
                const bool reached=access.owner[i]>=0 && access.distance[i]<=cfg.support_reach;
                field.support_reach[i]=reached ? 1. : 0.;
                if(!reached) field.potential[i]=0.;
            }
        }
        {
            // Every people can reach some fishing ground; where one is in range it
            // replaces farmland as that cell's capacity, which is what makes a coastal
            // or marine civilization viable at all.
            std::set<std::size_t> starts;
            for(std::size_t i:field.candidates) {
                for(const auto& edge:grid.neighbors[i]) {
                    const auto j=static_cast<std::size_t>(edge.first);
                    if(water[j]==1. && depth[j]>=.1 && hazard[j]<=profile.trait("mutation_limit")) starts.insert(j);
                }
            }
            std::vector<std::pair<std::size_t,std::int64_t>> seeds;
            for(std::size_t i:starts) seeds.emplace_back(i,0);
            const double reach=cfg.options.fishing_reach*rules.fishing_reach_multiplier;
            const Access marine=allocate_access(grid,seeds,
                [&](std::size_t i,std::size_t j,double d,double& step) {
                    return water_step(grid,water,depth,hazard,profile.trait("mutation_limit"),.1,i,j,d,step);
                },reach);
            for(std::size_t i=0;i<count;++i)
                if(std::isfinite(marine.distance[i]))
                    field.potential[i]=fishing[i]*cfg.options.fish_productivity/100;
        }
        result.species.emplace(species,field);
    }
    // The aggregate people's own score, which is what the stages after this one read
    // as `suitability`: witch huts avoid it, colleges rank by it. It carries none of
    // the per-people extras, exactly as the reference computes it.
    const Profile& aggregate=catalogues.profile(catalogues.aggregate_profile_id());
    result.suitability.assign(count,0.);
    for(std::size_t i=0;i<count;++i) {
        if(water[i]!=0.) continue;
        const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
        const double fresh=std::isfinite(result.freshwater_distance[i]) && result.freshwater_distance[i]>=0
            ? result.freshwater_distance[i] : infinite;
        const double score=aggregate.trait("water_weight")*std::exp(-fresh/aggregate.trait("water_reach"))
            +aggregate.trait("slope_weight")*std::exp(-std::pow(slope[i]/aggregate.trait("slope_comfort"),2.))
            +aggregate.trait("climate_weight")*std::exp(-std::pow((temperature[i]-aggregate.trait("temperature_ideal"))
                                                                  /aggregate.trait("temperature_tolerance"),2.))
            +aggregate.trait("moisture_weight")*std::max(0.,1-std::fabs(moisture[i]-aggregate.trait("moisture_ideal")))
            +aggregate.trait("resource_weight")*result.resource[i]
            -aggregate.trait("flood_penalty")*result.flood[i]
            +biome_preference(aggregate,static_cast<std::int64_t>(layers.biome[z][x]),variants[i]);
        result.suitability[i]=std::max(0.,std::min(1.,score-aggregate.trait("magic_penalty")*hazard[i]));
    }
    // Published for the stages that follow: the hinterlands, ports and colleges read
    // these back out of the layers rather than recomputing them.
    layers.suitability=node_grid(result.suitability,grid);
    layers.resource_potential=node_grid(result.resource,grid);
    evaluate_population_budget(cfg,grid,catalogues,result);
    return result;
}
}
