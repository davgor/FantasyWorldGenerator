#include "ecology.hpp"
#include "biomes.hpp"
#include "json.hpp"
#include "magic.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <set>
namespace fantasy_world_generator {
namespace {
constexpr double infinite=std::numeric_limits<double>::infinity();
double clamp01(double v) {return std::max(0.,std::min(1.,v));}
double angle_between(const Vec3& a,const Vec3& b) {return std::acos(std::max(-1.,std::min(1.,dot(a,b))));}
// One terrain-cost owner per node; deterministic ties, no water shortcuts. Every seed
// here carries the same label, so the tie rule reduces to the node index.
std::vector<double> ocean_access(const SphereGrid& grid,const std::vector<double>& water) {
    const std::size_t count=grid.points.size();
    std::vector<double> distance(count,infinite);
    using Entry=std::pair<double,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(std::size_t i=0;i<count;++i) if(water[i]==1.) {distance[i]=0.;queue.emplace(0.,i);}
    while(!queue.empty()) {
        const auto entry=queue.top();queue.pop();
        if(entry.first!=distance[entry.second]) continue;
        for(const auto& edge:grid.neighbors[entry.second]) {
            const auto j=static_cast<std::size_t>(edge.first);
            const double candidate=entry.first+edge.second;
            if(candidate<distance[j]) {distance[j]=candidate;queue.emplace(candidate,j);}
        }
    }
    return distance;
}
double zone_option(const char* which) {
    // terrain_world.OPTIONS gives every region the same defaults.
    if(std::string(which)=="occurrence") return .55;
    if(std::string(which)=="extent") return .22;
    return .8;   // intensity
}
}
const std::array<const char*,zone_count>& zone_names() {
    static const std::array<const char*,zone_count> names{
        "demonic","draconic","pirate","steampunk","witch_huts","red_sands","dead_sea",
        "starlight_lakes","haunted_sands","enchanted","fungal","crystal","haunted_marsh"};
    return names;
}
std::vector<RegionInfluence> add_environment(const WorldConfig& cfg,double radius,double spacing_m,
                                             const SphereGrid& grid,Layers& layers) {
    (void)radius;
    const std::size_t count=grid.points.size();
    const auto n=static_cast<std::size_t>(cfg.size);
    const double span=static_cast<double>(cfg.size-1);
    std::vector<Vec3> vectors;
    vectors.reserve(count);
    for(const auto& point:grid.points) vectors.push_back(direction(point.first,point.second,cfg.size));
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> temp=node_values(layers.temperature,grid);
    const std::vector<double> wet=node_values(layers.moisture,grid);
    const std::vector<double> slope=node_values(layers.slope,grid);
    const std::vector<double> depth=node_values(layers.water_depth,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    const std::vector<double> distance=ocean_access(grid,water);
    const std::uint32_t metal_seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"metals-v1");

    std::vector<double> metal(count,0.),salt(count,0.),exposure(count,0.),harbor(count,0.),fish(count,0.);
    std::vector<double> reef(count,0.),lagoon(count,0.),estuary(count,0.),rocky(count,0.),kelp(count,0.);
    std::vector<double> fjord(count,0.),open_ocean(count,0.),maritime(count,0.),support(count,0.);
    std::vector<double> boreal(count,0.),tundra(count,0.),ice_cap(count,0.);
    for(std::size_t i=0;i<count;++i) {
        const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
        const auto& near=grid.neighbors[i];
        std::int64_t ocean_neighbours=0,wet_neighbours=0,steep_dry=0;
        bool river_mouth=false,deep_neighbour=false;
        for(const auto& edge:near) {
            const auto j=static_cast<std::size_t>(edge.first);
            ocean_neighbours+=water[j]==1. ? 1 : 0;
            wet_neighbours+=water[j]>0. ? 1 : 0;
            steep_dry+=(slope[j]>12 && water[j]==0.) ? 1 : 0;
            if(river[j]!=0. && water[j]==0.) river_mouth=true;
            if(water[j]==1. && depth[j]>=cfg.options.sea_draft) deep_neighbour=true;
        }
        const double neighbours=static_cast<double>(std::max<std::size_t>(1,near.size()));
        const double adjacency=static_cast<double>(ocean_neighbours)/neighbours;
        const bool coast=water[i]==0. && distance[i]<=std::max(spacing_m,120.);
        exposure[i]=clamp01(coast ? adjacency : static_cast<double>(wet_neighbours)/neighbours);
        const double shallow=water[i]!=0. ? clamp01(1-depth[i]/80) : 0.;
        salt[i]=water[i]==1. ? 1. : (water[i]==2. ? clamp01((.6-wet[i])*2*cfg.options.salinity) : 0.);
        reef[i]=water[i]==1. ? shallow*clamp01((temp[i]-15)/12)*(1-.5*exposure[i]) : 0.;
        lagoon[i]=water[i]==1. ? shallow*(1-exposure[i]) : 0.;
        estuary[i]=(water[i]==1. && river_mouth) ? 1. : 0.;
        kelp[i]=water[i]==1. ? shallow*clamp01(1-std::fabs(temp[i]-10)/15) : 0.;
        fjord[i]=(water[i]==1. ? 1. : 0.)*clamp01(static_cast<double>(steep_dry)/3)*clamp01((15-temp[i])/15);
        harbor[i]=(coast && deep_neighbour) ? clamp01((1-exposure[i])*.7+.3)*std::exp(-slope[i]/22) : 0.;
        fish[i]=water[i]!=0. ? clamp01(.12+.55*shallow+.3*estuary[i]+.2*kelp[i]+.15*reef[i]) : 0.;
        rocky[i]=(coast ? 1. : 0.)*exposure[i]*clamp01(slope[i]/25);
        open_ocean[i]=(water[i]==1. ? 1. : 0.)*(1-shallow);
        maritime[i]=water[i]==0. ? std::exp(-distance[i]/300) : 0.;
        const std::string cold=water[i]==0.
            ? cold_habitat(monthly_temperatures(temp[i],90-180*static_cast<double>(z)/span,wet[i],
                                                cfg.options.seasonality),wet[i],cfg.options.ice_accumulation)
            : std::string();
        boreal[i]=cold=="boreal" ? 1. : 0.;
        tundra[i]=cold=="tundra" ? 1. : 0.;
        ice_cap[i]=cold=="ice_cap" ? 1. : 0.;
        const Vec3& p=vectors[i];
        metal[i]=clamp01((.45+.7*perlin3(p[0]*5,p[1]*5,p[2]*5,metal_seed)+.2*layers.volcanic[z][x])
                         *cfg.options.metal_abundance);
        support[i]=harbor[i]*.5;
    }
    // Nearby coastal support is opportunity, never credited as harvested food.
    for(std::size_t i=0;i<count;++i) {
        if(water[i]!=0.) continue;
        double best=0.;
        bool any=false;
        for(const auto& edge:grid.neighbors[i]) {
            const double value=fish[static_cast<std::size_t>(edge.first)];
            if(!any || value>best) {best=value;any=true;}
        }
        support[i]=harbor[i]*.5+.5*(any ? best : 0.);
    }
    layers.metal_richness=node_grid(metal,grid);
    layers.salinity=node_grid(salt,grid);
    layers.coastal_exposure=node_grid(exposure,grid);
    layers.harbor_suitability=node_grid(harbor,grid);
    layers.fishing_productivity=node_grid(fish,grid);
    layers.reef=node_grid(reef,grid);
    layers.lagoon=node_grid(lagoon,grid);
    layers.estuary=node_grid(estuary,grid);
    layers.sheltered_bay=node_grid(harbor,grid);
    layers.rocky_coast=node_grid(rocky,grid);
    layers.kelp=node_grid(kelp,grid);
    layers.fjord=node_grid(fjord,grid);
    layers.open_ocean=node_grid(open_ocean,grid);
    layers.maritime=node_grid(maritime,grid);
    layers.boreal=node_grid(boreal,grid);
    layers.tundra=node_grid(tundra,grid);
    layers.ice_cap=node_grid(ice_cap,grid);
    layers.coastal_support=node_grid(support,grid);

    // Small dry components are islands; the threshold is relative to the world's land.
    std::set<std::size_t> unvisited;
    Sum land_total;
    for(std::size_t i=0;i<count;++i) if(water[i]==0.) {unvisited.insert(i);land_total.add(grid.areas[i]);}
    std::vector<double> islandness(count,0.);
    while(!unvisited.empty()) {
        const std::size_t start=*unvisited.begin();
        unvisited.erase(unvisited.begin());
        std::vector<std::size_t> component{start},stack{start};
        while(!stack.empty()) {
            const std::size_t i=stack.back();stack.pop_back();
            for(const auto& edge:grid.neighbors[i]) {
                const auto j=static_cast<std::size_t>(edge.first);
                if(unvisited.erase(j)) {component.push_back(j);stack.push_back(j);}
            }
        }
        Sum area;
        for(std::size_t i:component) area.add(grid.areas[i]);
        const double value=area.value()<std::min(3e6,land_total.value()*.15) ? 1. : 0.;
        for(std::size_t i:component) islandness[i]=value;
    }
    layers.island_habitat=node_grid(islandness,grid);

    // Independent overlapping region fields; low suitability can still be valuable to a
    // specialist site, so nothing here is a hard mask.
    std::vector<RegionInfluence> regions;
    for(std::size_t index=0;index<zone_count;++index) {
        const std::string name=zone_names()[index];
        std::vector<double> scores(count,0.);
        for(std::size_t i=0;i<count;++i) {
            const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
            const double dry=water[i]!=0. ? 0. : 1.;
            const double arid=clamp01((.5-wet[i])*3);
            const double mountain=clamp01(std::max(0.,height[i])/100)*clamp01(slope[i]/20);
            const double infernal=layers.ley[2][z][x],umbral=layers.ley[1][z][x],weave=layers.ley[0][z][x];
            const double holy=layers.ley_holy[z][x],primordial=layers.ley_primordial[z][x];
            double value=0.;
            if(name=="demonic") value=dry*infernal;
            else if(name=="draconic") value=dry*mountain*std::max(primordial,weave);
            else if(name=="pirate") value=harbor[i];
            else if(name=="steampunk") value=dry*metal[i]*std::max(std::max(maritime[i],layers.volcanic[z][x]),.2);
            else if(name=="witch_huts") value=dry*umbral*(1-support[i]);
            else if(name=="red_sands") value=dry*arid;
            else if(name=="dead_sea") value=(water[i]==2. ? 1. : 0.)*salt[i];
            else if(name=="starlight_lakes") value=(water[i]==2. ? 1. : 0.)*std::max(weave,holy);
            else if(name=="haunted_sands") value=dry*arid*umbral;
            else if(name=="enchanted") value=dry*wet[i]*weave;
            else if(name=="fungal") value=dry*wet[i]*primordial;
            else if(name=="crystal") value=dry*arid*primordial;
            else value=dry*wet[i]*std::exp(-slope[i]/6)*umbral;   // haunted_marsh
            scores[i]=value;
        }
        PyRandom rng(child_seed(static_cast<std::uint64_t>(cfg.seed),"region-"+name+"-v1"));
        std::vector<std::size_t> candidates;
        for(std::size_t i=0;i<count;++i) if(scores[i]>.04) candidates.push_back(i);
        const double occurrence=zone_option("occurrence"),extent=zone_option("extent"),intensity=zone_option("intensity");
        const bool active=!candidates.empty() && rng.next()<occurrence;
        std::vector<std::size_t> centres;
        if(active) {
            // One jitter draw per candidate, in candidate order, then a stable ranking.
            std::vector<double> ranked_score(candidates.size(),0.);
            for(std::size_t k=0;k<candidates.size();++k) ranked_score[k]=-(scores[candidates[k]]*(.6+.4*rng.next()));
            std::vector<std::size_t> order(candidates.size());
            for(std::size_t k=0;k<order.size();++k) order[k]=k;
            std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
                return ranked_score[a]<ranked_score[b];
            });
            for(std::size_t k:order) {
                const std::size_t i=candidates[k];
                bool separated=true;
                for(std::size_t j:centres) if(!(angle_between(vectors[i],vectors[j])>extent*1.5)) {separated=false;break;}
                if(separated) centres.push_back(i);
                if(centres.size()>=3) break;
            }
        }
        std::vector<double> values(count,0.);
        for(std::size_t i=0;i<count;++i) {
            double best=0.;
            bool any=false;
            for(std::size_t j:centres) {
                const double reach=std::exp(-std::pow(angle_between(vectors[i],vectors[j])/extent,2.));
                if(!any || reach>best) {best=reach;any=true;}
            }
            values[i]=intensity*scores[i]*(any ? best : 0.);
        }
        layers.zone[index]=node_grid(values,grid);
        RegionInfluence influence;
        influence.id=name;
        influence.centres=centres;
        influence.maximum=values.empty() ? 0. : *std::max_element(values.begin(),values.end());
        Sum area;
        for(std::size_t i=0;i<count;++i) if(values[i]>.05) area.add(grid.areas[i]);
        influence.area_km2=area.value()/1e6;
        influence.reason=!centres.empty() ? "manifested"
            : (candidates.empty() ? "insufficient suitable habitat" : "not selected by occurrence seed");
        regions.push_back(influence);
    }
    (void)n;
    return regions;
}
}
