#pragma once
#include "founding.hpp"
#include "profiles.hpp"
#include "settlements.hpp"
#include <string>
#include <vector>
namespace fantasy_world_generator {
// One anchor slot a plan reserves: a grid node, not a metre footprint. Buildings get
// their geometry from the city-geometry slice, which is not ported.
struct PlanAnchor {
    std::size_t node=0;
    std::int64_t x=0,z=0,sequence=-1;
    double distance_to_city_m=0.;
};
// A named district of the layout profile, with the anchors it managed to claim.
struct PlanFeature {
    std::string name;
    std::int64_t target_count=0;
    std::vector<PlanAnchor> anchors;
};
// One building option of the chosen pack, resolved against this city.
struct BuildingOptionPlan {
    std::string option_id,name,placement,skip_reason;
    std::int64_t target_count=0,required_node_slots=0;
    bool required=false,bridge_required=false;
    std::vector<std::string> tags,assets;
    std::vector<PlanAnchor> anchors;
};
// The city plan the reference stores as `settlements.sites[].city_layout`.
struct CityPlan {
    std::string layout_profile_id,layout_profile_name,population_profile;
    std::string building_pack_id,fallback_reason;
    std::uint32_t city_seed=0;
    bool has_residents=false;
    double residents=0.;
    std::int64_t adjacent_river_edges=0,bridge_threshold=0;
    bool river_distance_finite=false,bridge_recommended=false;
    double river_distance_m=0.;
    std::vector<PlanFeature> features;
    std::vector<BuildingOptionPlan> options;
    std::vector<std::pair<std::string,std::int64_t>> required_assets;
    std::int64_t required_asset_count=0,required_node_slots=0;
    bool missing_anchors=false;
};
// Freshwater routing the plan needs: metres along the grid to the nearest river cell.
std::vector<double> river_distances(const SphereGrid& grid,const std::vector<double>& river);
// Which pack a city builds from: the authoring criteria filter, then one weighted draw
// from the city seed. An unmatched city falls back rather than building nothing.
std::string pick_building_pack(std::uint32_t city_seed,const CityCatalogues& city,
                               const std::string& population_profile,std::int64_t biome,
                               const std::string& variant,double height_m,double slope_degrees,
                               double resource,double freshwater_distance_m);
// The pack may force a layout; otherwise a river-adjacent city takes the riverfront
// profile and everything else the fallback.
const LayoutProfile& pick_layout_profile(const CityCatalogues& city,const BuildingPack& pack,
                                         bool river_distance_finite,double river_distance_m);
// Step (d) of the placement port: the layout plan for one city, anchored on the
// walkable land around it. Residents are unknown at this stage, exactly as the
// reference leaves them until the population round.
CityPlan build_city_plan(std::uint32_t city_seed,std::size_t node,const SphereGrid& grid,
                         const CityCatalogues& city,const BuildingPack& pack,
                         const LayoutProfile& layout,const std::string& population_profile,
                         bool river_distance_finite,double river_distance_m,
                         const std::vector<double>& river,const std::vector<double>& water,
                         const std::vector<double>& slope,const std::vector<double>& rivers_distance,
                         bool has_residents=false,double residents=0.);
// How many people a founded city is credited with: the budget allowance for its people
// split evenly across that people's cities, remainder to the earliest. Not a simulated
// population; it is the number the layout plan sizes districts from.
struct PopulationEstimate {std::int64_t residents=0,urban=0,rural=0;};
std::vector<PopulationEstimate> estimate_population(const PopulationBudget& budget,
                                                    const std::vector<FoundedCity>& sites);
// Every founded city's plan, in founding order. Residents may be empty, which plans the
// city before its population is known, exactly as the reference's first round does.
std::vector<CityPlan> plan_cities(const WorldConfig& cfg,const SphereGrid& grid,const Catalogues& catalogues,
                                  const Layers& layers,const SettlementFields& fields,
                                  const std::vector<FoundedCity>& sites,
                                  const std::vector<PopulationEstimate>& residents={});
}
