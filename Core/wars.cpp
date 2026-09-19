#include "wars.hpp"
#include "cityplan.hpp"
#include "globe.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <set>
namespace fantasy_world_generator {
namespace {
const char* kCivil="civil";
const char* kRegional="regional";
const char* kInternational="international";
std::string reason_for(const std::string& kind) {
    if(kind==kCivil)
        return "Two cities of one civilization fell out over contested ground and supply, and only one survived the war.";
    if(kind==kRegional)
        return "Kindred civilizations of one parent race fought a regional war over contested ground and supply.";
    return "Cities of different parent races fought an international war over contested ground and supply.";
}
std::int64_t residents_of(const std::vector<PopulationEstimate>& residents,std::size_t index) {
    return index<residents.size() ? residents[index].residents : 0;
}
}

std::string war_kind(const FoundedCity& a,const FoundedCity& b) {
    if(a.population_profile==b.population_profile) return kCivil;
    if(a.parent_race_id==b.parent_race_id) return kRegional;
    return kInternational;
}

double shortfall(const CityCore* core) {
    if(core==nullptr || core->food_demand<=0) return 0.;
    return std::max(0.,std::min(1.,(core->food_demand-core->food_supply)/core->food_demand));
}

double war_chance(double pressure) {
    return std::min(war_max_chance,war_base_chance+war_pressure_gain*std::max(0.,std::min(1.,pressure)));
}

double war_strength(std::int64_t residents,const CityCore* core) {
    const std::size_t forts=core==nullptr ? 0 : core->fortress_ids.size();
    return static_cast<double>(residents)+fort_strength*static_cast<double>(forts);
}

std::vector<ContestedPair> contested_pairs(const std::vector<FoundedCity>& cities,
                                           const std::vector<CityCore>& cores,
                                           const std::vector<Road>& roads,
                                           const SphereGrid& grid,
                                           double radius,double spacing,std::int64_t size) {
    std::map<std::int64_t,const CityCore*> by_site;
    for(const CityCore& core:cores) by_site[core.site_id]=&core;
    std::set<std::pair<std::size_t,std::size_t>> linked;
    for(const Road& road:roads) linked.insert({road.from,road.to});
    const double limit=proximity_factor*spacing;
    std::vector<ContestedPair> pairs;
    for(std::size_t i=0;i<cities.size();++i) {
        for(std::size_t j=i+1;j<cities.size();++j) {
            const FoundedCity& a=cities[i];
            const FoundedCity& b=cities[j];
            const Vec3 pa=direction(grid.points[a.node].first,grid.points[a.node].second,size);
            const Vec3 pb=direction(grid.points[b.node].first,grid.points[b.node].second,size);
            const double distance=radius*std::acos(std::max(-1.,std::min(1.,dot(pa,pb))));
            const double proximity=limit>0 ? std::max(0.,1.-distance/limit) : 0.;
            double supply=0.;
            const bool joined=linked.count({i,j})!=0 || linked.count({j,i})!=0;
            if(joined) {
                const auto found_a=by_site.find(static_cast<std::int64_t>(i));
                const auto found_b=by_site.find(static_cast<std::int64_t>(j));
                supply=std::max(shortfall(found_a==by_site.end() ? nullptr : found_a->second),
                                shortfall(found_b==by_site.end() ? nullptr : found_b->second));
            }
            if(proximity<=0 && supply<=0) continue;
            ContestedPair pair;
            pair.a=i;pair.b=j;pair.a_uid=a.uid;pair.b_uid=b.uid;
            pair.distance_m=distance;pair.proximity_pressure=proximity;pair.supply_pressure=supply;
            pair.pressure=std::min(1.,proximity+supply);
            pair.kind=war_kind(a,b);
            pairs.push_back(pair);
        }
    }
    std::stable_sort(pairs.begin(),pairs.end(),[](const ContestedPair& x,const ContestedPair& y) {
        if(x.pressure!=y.pressure) return x.pressure>y.pressure;
        if(x.a_uid!=y.a_uid) return x.a_uid<y.a_uid;
        return x.b_uid<y.b_uid;
    });
    return pairs;
}

std::vector<War> resolve_wars(const std::vector<FoundedCity>& cities,
                              const std::vector<CityCore>& cores,
                              const std::vector<Road>& roads,
                              const std::vector<PopulationEstimate>& residents,
                              const SphereGrid& grid,
                              double radius,double spacing,std::uint64_t seed,std::int64_t age,
                              std::int64_t size,std::map<std::string,std::size_t>& fates) {
    std::map<std::int64_t,const CityCore*> by_site;
    for(const CityCore& core:cores) by_site[core.site_id]=&core;
    std::vector<War> wars;
    std::set<std::string> lost;
    wars.reserve(cities.size());
    for(const ContestedPair& pair:contested_pairs(cities,cores,roads,grid,radius,spacing,size)) {
        const FoundedCity& a=cities[pair.a];
        const FoundedCity& b=cities[pair.b];
        if(lost.count(a.uid)!=0 || lost.count(b.uid)!=0) continue;
        const std::string war_id="war-"+std::to_string(age)+"-"+std::to_string(wars.size());
        const double chance=war_chance(pair.pressure);
        PyRandom rng(child_seed(seed,"war-"+a.uid+"-"+b.uid,static_cast<std::uint64_t>(age)));
        const double draw=rng.next();
        if(draw>=chance) continue;
        const auto core_of=[&by_site](std::size_t index)->const CityCore* {
            const auto found=by_site.find(static_cast<std::int64_t>(index));
            return found==by_site.end() ? nullptr : found->second;
        };
        const double a_strength=war_strength(residents_of(residents,pair.a),core_of(pair.a));
        const double b_strength=war_strength(residents_of(residents,pair.b),core_of(pair.b));
        // Strength decides it; a genuine tie goes to the lower uid, as the reference does.
        const bool a_wins=a_strength>b_strength || (a_strength==b_strength && a.uid<b.uid);
        const FoundedCity& victor=a_wins ? a : b;
        const FoundedCity& defeated=a_wins ? b : a;
        War war;
        war.id=war_id;war.age=age;war.kind=pair.kind;war.reason=reason_for(pair.kind);
        war.victor_uid=victor.uid;war.defeated_uid=defeated.uid;
        war.victor_civilization_id=victor.population_profile;
        war.defeated_civilization_id=defeated.population_profile;
        war.victor_parent_race_id=victor.parent_race_id;
        war.defeated_parent_race_id=defeated.parent_race_id;
        war.distance_m=pair.distance_m;war.proximity_pressure=pair.proximity_pressure;
        war.supply_pressure=pair.supply_pressure;war.pressure=pair.pressure;
        war.victor_strength=a_wins ? a_strength : b_strength;
        war.defeated_strength=a_wins ? b_strength : a_strength;
        war.chance=chance;war.roll=draw;
        wars.push_back(war);
        lost.insert(defeated.uid);
    }
    // Indices, not pointers: the vector reallocates as wars are appended.
    fates.clear();
    for(std::size_t index=0;index<wars.size();++index) fates[wars[index].defeated_uid]=index;
    return wars;
}

WarParticipation participation(const War& war,const std::string& uid) {
    const bool victor=war.victor_uid==uid;
    WarParticipation record;
    record.war_id=war.id;record.age=war.age;record.kind=war.kind;
    record.outcome=victor ? "victor" : "defeated";
    record.opponent_uid=victor ? war.defeated_uid : war.victor_uid;
    record.opponent_civilization_id=victor ? war.defeated_civilization_id : war.victor_civilization_id;
    record.opponent_parent_race_id=victor ? war.defeated_parent_race_id : war.victor_parent_race_id;
    return record;
}

std::int64_t veteran_wars(const FoundedCity& city) {
    return static_cast<std::int64_t>(city.war_history.size());
}
}
