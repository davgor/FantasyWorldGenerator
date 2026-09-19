#pragma once
#include "founding.hpp"
#include "humans.hpp"
#include "cityplan.hpp"
#include "hydrology.hpp"
#include <map>
#include <string>
#include <vector>
namespace fantasy_world_generator {
// One war between two cities, named for the relationship between them: civil inside one
// civilization, regional inside one parent race, international across parent races.
struct War {
    std::string id,kind,reason;
    std::string victor_uid,defeated_uid;
    std::string victor_civilization_id,defeated_civilization_id;
    std::string victor_parent_race_id,defeated_parent_race_id;
    std::int64_t age=0;
    double distance_m=0.,proximity_pressure=0.,supply_pressure=0.,pressure=0.;
    double victor_strength=0.,defeated_strength=0.,chance=0.,roll=0.;
};
// A pair with something to fight over: ground, supply, or both.
struct ContestedPair {
    std::size_t a=0,b=0;
    std::string a_uid,b_uid,kind;
    double distance_m=0.,proximity_pressure=0.,supply_pressure=0.,pressure=0.;
};
// Reference constants. These are the dial on how bloody a world's history is.
constexpr double proximity_factor=1.5;
constexpr double war_base_chance=.5,war_pressure_gain=.4,war_max_chance=.92;
constexpr double fort_strength=50.;

std::string war_kind(const FoundedCity& a,const FoundedCity& b);
// The share of its own demand a city's hinterland cannot feed, before any trade.
double shortfall(const CityCore* core);
double war_chance(double pressure);
double war_strength(std::int64_t residents,const CityCore* core);
// Contested pairs, strongest contention first, ordered exactly as the reference orders
// them so the same world fights the same wars in the same sequence.
std::vector<ContestedPair> contested_pairs(const std::vector<FoundedCity>& cities,
                                           const std::vector<CityCore>& cores,
                                           const std::vector<Road>& roads,
                                           const SphereGrid& grid,
                                           double radius,double spacing,std::int64_t size);
// Fight every contested pair that draws for it. `fates` maps a defeated city's uid to
// the war that ended it, so the age transition can ruin it through the path it already
// has. A city can be dragged into several wars but is only ever lost once.
std::vector<War> resolve_wars(const std::vector<FoundedCity>& cities,
                              const std::vector<CityCore>& cores,
                              const std::vector<Road>& roads,
                              const std::vector<PopulationEstimate>& residents,
                              const SphereGrid& grid,
                              double radius,double spacing,std::uint64_t seed,std::int64_t age,
                              std::int64_t size,std::map<std::string,std::size_t>& fates);
WarParticipation participation(const War& war,const std::string& uid);
// How many wars a city carries, whatever it did in them.
std::int64_t veteran_wars(const FoundedCity& city);
}
