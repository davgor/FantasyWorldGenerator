#include "nests.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <map>
namespace fantasy_world_generator {
namespace {
double clamp01(double value) {return std::max(0.,std::min(1.,value));}
// The habitat sample at one cell: every layer by name, plus the derived descriptions
// the profiles are written against. A field a profile asks for and the world does not
// have reads as absent, which fails a requirement closed rather than passing it.
struct Habitat {
    std::map<std::string,double> fields;
    std::string medium;
    std::size_t node=0;
    std::int64_t x=0,z=0,biome=0;
    double area_km2=0.;
    Vec3 direction{};
    double get(const std::string& key,double fallback) const {
        const auto found=fields.find(key);
        return found==fields.end() ? fallback : found->second;
    }
};
struct Scored {double score=0.;bool eligible=false;};
Scored suitability(const NestProfile& profile,const Habitat& habitat) {
    Scored result;
    const std::string expected=profile.medium=="shore" ? "land" : profile.medium;
    if(habitat.medium!=expected) return result;
    if(profile.medium=="shore" && habitat.get("coast",0.)<.1) return result;
    const double temperature=habitat.get("temperature",100.);
    if(!(profile.temperature_min<=temperature && temperature<=profile.temperature_max)) return result;
    for(const auto& need:profile.requires_at_least)
        if(habitat.get(need.first,0.)<need.second) return result;
    Sum total;
    for(const auto& weight:profile.weights) total.add(weight.second);
    Sum score;
    for(const auto& weight:profile.weights)
        score.add(clamp01(habitat.get(weight.first,0.))*weight.second/total.value());
    result.score=score.value();
    result.eligible=true;
    return result;
}
// Species table first, then its role's, then no preference. Keys are decimal strings
// of natural biome ids, matching how civilization biome preferences are authored. An
// absent biome is habitat the species does not use.
double biome_weight(const NestProfile& profile,
                    const std::map<std::string,std::map<std::string,double>>& roles,
                    std::int64_t biome) {
    const std::map<std::string,double>* table=nullptr;
    if(!profile.biome_weights.empty()) table=&profile.biome_weights;
    else if(!profile.role.empty()) {
        const auto role=roles.find(profile.role);
        if(role!=roles.end()) table=&role->second;
    }
    if(table==nullptr || table->empty()) return 1.;
    const auto found=table->find(std::to_string(biome));
    return found==table->end() ? 0. : found->second;
}
double arc(const Vec3& a,const Vec3& b,double radius) {
    // Keep the compensated sum: the reference's dot product is Neumaier, and an ulp
    // here moves an anchor across a clearance threshold.
    return radius*std::acos(std::max(-1.,std::min(1.,dot(a,b))));
}
// Groups per square kilometre at full suitability; a pyramid, not a ladder. The share
// belongs to the tier, and `occurrence` divides it among the tier's members and
// nothing else -- it is authored as a pure function of `size`, so spending it as an
// absolute multiplier would tax the big creatures a second time for being big.
double tier_density(double base,double falloff,std::int64_t tier) {
    return base*std::pow(falloff,static_cast<double>(1-tier));
}
// The share of a cell that goes to one species.
struct Share {const NestProfile* profile=nullptr;double rate=0.,score=0.;};
// The species that claims this group, in proportion to its share of the cell.
const Share& pick(PyRandom& rng,const std::vector<Share>& shares,double total) {
    const double draw=rng.next()*total;
    double cursor=0.;
    for(const Share& share:shares) {
        cursor+=share.rate;
        if(draw<=cursor) return share;
    }
    return shares.back();
}
using Dominance=std::function<bool(const NestProfile&,double,const Habitat&,
                                   const std::vector<Nest>&,double)>;
using Clearance=std::function<double(const NestProfile&)>;
// One thinned point process over the cells, shared by both passes. `dominance`
// decides whether a candidate is refused by what is already there.
NestResult place(const std::string& kind_of,const std::vector<const NestProfile*>& catalogue,
                 const Catalogues& catalogues,const WorldConfig& cfg,
                 const std::vector<Habitat>& cells,const std::vector<Vec3>& settled,
                 double radius,const std::string& domain,double density,double falloff,
                 const Clearance& clearance,const Dominance& dominance) {
    NestResult result;
    for(const NestProfile* profile:catalogue)
        result.diagnostics.push_back(NestDiagnostic{profile->id,profile->name,profile->role,
                                                    profile->tier,0});
    if(catalogue.empty()) return result;
    PyRandom rng(child_seed(static_cast<std::uint64_t>(cfg.seed),domain,
                            static_cast<std::uint64_t>(cfg.options.nest_variation)));
    std::vector<Nest> placed;
    std::map<std::string,std::int64_t> counts;
    for(const NestProfile* profile:catalogue) counts.emplace(profile->id,0);
    const std::int64_t per_species=cfg.options.nest_per_species;
    // Distance to the nearest settled thing, once per cell. Keeping clear of people is
    // a property of the ground rather than of luck, so it belongs in the rate: reject
    // a draw that already happened and the world quietly holds far fewer creatures
    // than the density asked for.
    std::vector<double> nearest(cells.size(),std::numeric_limits<double>::infinity());
    for(std::size_t index=0;index<cells.size();++index)
        for(const Vec3& site:settled)
            nearest[index]=std::min(nearest[index],arc(cells[index].direction,site,radius));
    // Where each species can live and how much room it has there. `room` is what the
    // species would claim if nothing else existed: how common it is, how well the
    // ground suits it, and how much ground there is. Plain accumulation, matching the
    // reference, which does not run these through a compensated sum.
    struct Room {const NestProfile* profile=nullptr;bool wet=false;double room=0.,score=0.;};
    std::vector<std::vector<Room>> rooms(cells.size());
    std::map<std::pair<std::int64_t,bool>,double> tier_room;
    std::map<bool,double> ground;
    for(std::size_t index=0;index<cells.size();++index) {
        const Habitat& cell=cells[index];
        // Land and open water are two ecosystems sharing a planet, and a species
        // belongs to exactly one of them. Budget them apart or the sea decides how
        // empty the land is.
        const bool wet=cell.medium!="land";
        ground[wet]+=cell.area_km2;
        for(const NestProfile* profile:catalogue) {
            if(nearest[index]<clearance(*profile)) continue;
            const double weight=biome_weight(*profile,catalogues.nest_roles(),cell.biome);
            if(weight<=0.) continue;
            const Scored scored=suitability(*profile,cell);
            if(!scored.eligible || scored.score<cfg.options.nest_min_suitability) continue;
            const double room=profile->occurrence*scored.score*weight*cell.area_km2;
            if(room<=0.) continue;
            rooms[index].push_back(Room{profile,wet,room,scored.score});
            tier_room[std::make_pair(profile->tier,wet)]+=room;
        }
    }
    // The pyramid is a claim about the world, so it is a budget for the world: tier t
    // gets `density * falloff^(1-t)` groups per square kilometre of its own medium,
    // and that budget is then spread over whatever ground the tier can actually use.
    // Sharing per cell instead loses a tier its share wherever no member qualifies,
    // and the low monster tiers are the specialised ones.
    std::map<std::pair<std::int64_t,bool>,double> budget;
    for(const auto& entry:tier_room)
        if(entry.second>0.)
            budget.emplace(entry.first,tier_density(density,falloff,entry.first.first)
                                       *ground[entry.first.second]/entry.second);
    for(std::size_t index=0;index<cells.size();++index) {
        const Habitat& cell=cells[index];
        std::vector<Share> shares;
        shares.reserve(rooms[index].size());
        for(const Room& room:rooms[index])
            shares.push_back(Share{room.profile,
                                   budget.at(std::make_pair(room.profile->tier,room.wet))*room.room,
                                   room.score});
        if(shares.empty()) continue;
        // The reference sums the cell's rates with the builtin, which is Neumaier.
        Sum sum;
        for(const Share& share:shares) sum.add(share.rate);
        const double total=sum.value();
        // floor plus one Bernoulli draw: an exact discretisation while the cell rate
        // is below one, which it is almost everywhere.
        std::int64_t groups=static_cast<std::int64_t>(total);
        if(rng.next()<total-static_cast<double>(groups)) groups+=1;
        for(std::int64_t draw=0;draw<groups;++draw) {
            const Share& chosen=pick(rng,shares,total);
            const NestProfile& profile=*chosen.profile;
            if(per_species!=0 && counts[profile.id]>=per_species) continue;
            const double reach=profile.spacing_m*cfg.options.nest_spacing/2;
            if(dominance(profile,reach,cell,placed,radius)) continue;
            counts[profile.id]+=1;
            Nest nest;
            nest.id=kind_of+"-"+profile.id+"-"+std::to_string(cell.node);
            nest.species_id=profile.id;
            nest.name=profile.name;
            nest.node=cell.node;
            nest.x=cell.x;
            nest.z=cell.z;
            nest.layer="surface";
            nest.direction=cell.direction;
            nest.tier=profile.tier;
            nest.family=profile.family;
            nest.kind=profile.kind;
            nest.size=profile.size;
            nest.role=profile.role;
            nest.creature_class=profile.creature_class;
            nest.suitability=chosen.score;
            nest.range_m=reach;
            // A den or lair is a place you can find and raid; a herd, roost or shoal
            // is only a range where you meet them.
            nest.den=profile.kind=="den" || profile.kind=="lair";
            nest.real=profile.creature_class=="animal";
            placed.push_back(nest);
        }
    }
    const std::int64_t limit=cfg.options.nest_limit;
    if(limit!=0 && static_cast<std::int64_t>(placed.size())>limit) {
        // A safety valve, not the thing that decides how full a world is. When it has
        // to bite it keeps the notable creatures: highest tier first, then by id.
        std::stable_sort(placed.begin(),placed.end(),[](const Nest& a,const Nest& b) {
            if(a.tier!=b.tier) return a.tier>b.tier;
            return a.id<b.id;
        });
        placed.resize(static_cast<std::size_t>(limit));
        for(auto& entry:counts) entry.second=0;
        for(const Nest& nest:placed) counts[nest.species_id]+=1;
    }
    std::stable_sort(placed.begin(),placed.end(),[](const Nest& a,const Nest& b) {
        return a.id<b.id;
    });
    for(NestDiagnostic& diagnostic:result.diagnostics) {
        const auto found=counts.find(diagnostic.species_id);
        diagnostic.placed=found==counts.end() ? 0 : found->second;
    }
    result.sites=placed;
    return result;
}
}
Habitats add_nests(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                   const Catalogues& catalogues,const Layers& layers,
                   const std::vector<FoundedCity>& sites,const Humans& humans,
                   const Society& society) {
    Habitats result;
    const std::vector<NestProfile>& profiles=catalogues.nest_profiles();
    if(profiles.empty()) return result;
    const std::size_t count=grid.points.size();
    // Everything already standing on the surface, for clearance tests.
    std::vector<Vec3> settled;
    for(const FoundedCity& site:sites)
        settled.push_back(direction(grid.points[site.node].first,grid.points[site.node].second,cfg.size));
    for(const Port& port:society.ports)
        settled.push_back(direction(port.x,port.z,cfg.size));
    for(const RuralSite& hamlet:humans.hamlets)
        settled.push_back(direction(hamlet.x,hamlet.z,cfg.size));
    const std::vector<double> water=node_values(layers.water_type,grid);
    const std::vector<double> salinity=layers.salinity.empty()
        ? std::vector<double>(count,0.) : node_values(layers.salinity,grid);
    const std::vector<double> moisture=node_values(layers.moisture,grid);
    const std::vector<double> slope=node_values(layers.slope,grid);
    const std::vector<double> temperature=node_values(layers.temperature,grid);
    const std::vector<double> depth=node_values(layers.water_depth,grid);
    const std::vector<double> river=node_values(layers.river,grid);
    const std::vector<double> maritime=node_values(layers.maritime,grid);
    // Every cell's habitat description, in grid order: the ground both passes read.
    std::vector<Habitat> cells;
    cells.reserve(count);
    for(std::size_t node=0;node<count;++node) {
        Habitat habitat;
        const auto x=static_cast<std::size_t>(grid.points[node].first);
        const auto z=static_cast<std::size_t>(grid.points[node].second);
        for(const auto& named:named_layers(layers))
            if(!named.second->empty()) habitat.fields.emplace(named.first,(*named.second)[z][x]);
        const double wet=moisture[node];
        habitat.medium=water[node]==1. ? "marine"
            : (water[node]!=0. && salinity[node]<.2) ? "freshwater"
            : water[node]!=0. ? "salt_lake" : "land";
        habitat.fields["depth"]=depth[node];
        habitat.fields["dryness"]=1-clamp01(wet);
        habitat.fields["coast"]=maritime[node];
        habitat.fields["mountain"]=clamp01(slope[node]/25);
        habitat.fields["plains"]=clamp01(1-slope[node]/15)*(1-std::fabs(wet-.45));
        habitat.fields["wetland"]=std::max({water[node]!=0. ? 1. : 0.,river[node],
                                            wet*std::exp(-slope[node]/8)});
        habitat.fields["cold"]=clamp01((10-temperature[node])/25);
        habitat.node=node;
        habitat.x=grid.points[node].first;
        habitat.z=grid.points[node].second;
        habitat.area_km2=grid.areas[node]/1e6;
        habitat.direction=direction(habitat.x,habitat.z,cfg.size);
        const auto natural=habitat.fields.find("natural_biome");
        const auto fallback=habitat.fields.find("biome");
        habitat.biome=static_cast<std::int64_t>(natural!=habitat.fields.end() ? natural->second
            : fallback!=habitat.fields.end() ? fallback->second : 0.);
        cells.push_back(habitat);
    }
    std::vector<const NestProfile*> animals,monsters;
    for(const NestProfile& profile:profiles)
        (profile.creature_class=="animal" ? animals : monsters).push_back(&profile);
    // Hunting grounds. Territorial within a species only: a wolf range over a deer
    // range is the point of the map, not a collision.
    result.animals=place("animal",animals,catalogues,cfg,cells,settled,radius,"animals-v1",
        cfg.options.animal_density*cfg.options.nest_density,cfg.options.animal_tier_falloff,
        [&cfg](const NestProfile& profile) {
            // Game keeps its distance from people in proportion to how dangerous it is.
            return cfg.options.nest_settlement_clearance*static_cast<double>(profile.tier)/3;
        },
        [](const NestProfile& profile,double reach,const Habitat& cell,
           const std::vector<Nest>& placed,double radius_m) {
            for(const Nest& other:placed)
                if(other.species_id==profile.id
                   && arc(other.direction,cell.direction,radius_m)<std::max(reach,other.range_m))
                    return true;
            return false;
        });
    // Territory. Rank, not spacing: only an equal or greater monster holds the ground
    // against this one, so lesser lairs nest inside a greater territory.
    result.monsters=place("nest",monsters,catalogues,cfg,cells,settled,radius,"monsters-v1",
        cfg.options.monster_density*cfg.options.nest_density*cfg.options.nest_fantasy,
        cfg.options.monster_tier_falloff,
        [&cfg](const NestProfile& profile) {
            return cfg.options.nest_settlement_clearance*static_cast<double>(profile.tier);
        },
        [](const NestProfile& profile,double reach,const Habitat& cell,
           const std::vector<Nest>& placed,double radius_m) {
            for(const Nest& other:placed)
                if(other.tier>=profile.tier
                   && arc(other.direction,cell.direction,radius_m)<std::max(reach,other.range_m))
                    return true;
            return false;
        });
    return result;
}
}
