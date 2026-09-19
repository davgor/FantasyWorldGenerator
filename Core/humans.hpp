#pragma once
#include "cityplan.hpp"
#include "founding.hpp"
#include "routing.hpp"
#include <string>
#include <vector>
namespace fantasy_world_generator {
// A rural site: a hamlet that works a catchment, or a fortress that watches a route.
// Both are proposals on a grid node, not built settlements.
struct RuralSite {
    std::string id,kind,population_profile,culture_id,role,reason;
    std::size_t node=0;
    std::int64_t x=0,z=0,core_id=-1;
    double height_m=0.,access_cost=0.;
    std::vector<std::size_t> access_nodes;
    // Hamlet economy, in the reference's relative units rather than tonnes.
    double irrigation_benefit=0.,worked_area_km2=0.,delivered_food=0.,delivered_materials=0.;
    // Fortress only.
    double defence_score=0.;
    std::size_t protected_route_node=0;
};
// A single-link interaction group over cheap roads between cities of one people.
struct Culture {
    std::int64_t index=0;
    std::string id,population_profile;
    std::vector<std::int64_t> city_ids;
};
// What one city's hinterland delivers to it.
struct CityCore {
    std::int64_t site_id=0;
    std::string population_profile,culture_id;
    std::vector<std::string> hamlet_ids,fortress_ids;
    double food_demand=0.,food_supply=0.,food_deficit=0.,material_supply=0.;
};
struct Humans {
    std::vector<RuralSite> hamlets,fortresses;
    std::vector<Culture> cultures;
    std::vector<CityCore> cores;
    std::vector<std::int64_t> groups;           // culture group per city
    // Node fields the later stages read back out of the layers.
    std::vector<double> food_potential,natural_food_potential,irrigation_benefit;
    std::vector<double> culture_region,hamlet_catchment,civilization_region;
};
// City hinterlands: exclusive catchments per city, hamlets on the best reachable
// farming and resource ground, fortresses on route junctions and crossings, and the
// culture groups those cities fall into. Relative exportable potential, not yields.
Humans add_humans(const WorldConfig& cfg,double radius,const SphereGrid& grid,const Catalogues& catalogues,
                  Layers& layers,const std::vector<FoundedCity>& sites,
                  const std::vector<PopulationEstimate>& residents,const std::vector<Road>& roads,
                  const std::vector<std::string>& variants);
}
