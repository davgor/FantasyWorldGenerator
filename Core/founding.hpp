#pragma once
#include "warhistory.hpp"
#include "profiles.hpp"
#include "settlements.hpp"
#include <string>
#include <vector>
namespace fantasy_world_generator {
// One founded city, before it is classified, named or given a layout.
struct FoundedCity {
    std::size_t node=0;
    std::string population_profile,parent_race_id,source_civilization_id,diaspora_reason;
    // Identity that outlives an age: a surviving city keeps its uid, name, founding
    // age and culture when the world is rebuilt around it.
    std::string uid,name,source_culture;
    std::int64_t founded_age=0;
    std::int64_t founding_turn=0;
    double founding_year=0.,migration_distance_m=0.;
    bool founding_capital=false,cultural_branch=false,diaspora=false,diaspora_bonus=false;
    bool has_source=false;
    std::size_t migration_source_node=0;
    // Every war this city has been part of, victories included; it survives an age.
    std::vector<WarParticipation> war_history;
};
struct FoundingResult {
    std::vector<FoundedCity> sites;
    std::map<std::string,std::int64_t> effective_quotas;
    std::int64_t turns=0,target_cities=0;
    std::string stop_reason;
    // What the next age needs to carry forward: a parent may spend its diaspora bonus
    // once across the whole history, and a civilization seated once is never unused
    // again, so both outlive the round that produced them.
    std::vector<std::string> diaspora_bonus_used,used_civilizations;
    double start_year=0.,end_year=0.;
};
// What a later founding round inherits. Empty for the world's first round.
struct FoundingContext {
    std::vector<FoundedCity> survivors;
    std::vector<std::size_t> forbidden;      // ruined nodes, never resettled
    std::vector<std::string> bonus_used,used_civilizations;
    double start_year=0.;
};
// A route between two cities: the cheapest passable path both peoples can use.
struct Road {
    std::size_t from=0,to=0;
    std::vector<std::size_t> nodes;
    double length_m=0.,cost=0.;
    std::vector<std::pair<std::size_t,std::size_t>> river_crossings;
};
// Minimum spanning forest over the cheapest terrain routes. Water, unsafe magic and
// grades a road cannot climb are forbidden, and a route counts only if both cities can
// use it; disconnected islands stay disconnected rather than gaining an imagined ferry.
std::vector<Road> build_roads(const WorldConfig& cfg,const SphereGrid& grid,const Catalogues& catalogues,
                              const Layers& layers,const std::vector<FoundedCity>& sites);
// Seeded parent-race founding rounds. Distances are physical metres on the globe, and
// every tie breaks on suitability, then civilization id, then node, so the same seed
// founds the same cities in the same order.
FoundingResult found_cities(std::uint32_t seed,const WorldConfig& cfg,double radius,const SphereGrid& grid,
                            const Catalogues& catalogues,const SettlementFields& fields,
                            const FoundingContext& context={});
}
