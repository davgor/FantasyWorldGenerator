#pragma once
#include "ecology.hpp"
#include "humans.hpp"
#include <string>
#include <vector>
namespace fantasy_world_generator {
// A coastal landing worked from a city: a place, not a fishing economy. The reference
// also allocates monthly catch, ice cover and delivery losses to each port; those are
// reported quantities that nothing in the finished world reads back, so they are not
// computed here and a consumer must not present this as a provisioned harbour.
struct Port {
    std::string id,population_profile,culture_id;
    std::size_t node=0,sea_node=0;
    std::int64_t x=0,z=0,core_id=-1;
    double height_m=0.,harbor_quality=0.,access_cost=0.,landing_distance_m=0.;
    bool trade_terminal=false;
    std::vector<std::size_t> access_nodes;
};
// A specialist site that is not a settlement: a witch hut in an umbral zone, or a
// necropolis over haunted sand.
struct Landmark {
    std::string id,kind;
    std::size_t node=0;
    std::int64_t x=0,z=0;
    double intensity=0.,conventional_suitability=0.;
    std::string reason;
};
struct Society {
    std::vector<Port> ports;
    std::vector<Landmark> landmarks;
};
// Coastal landings and the specialist landmarks that avoid cities. Witch huts are
// re-placed here: the ecology stage puts them on zone centres, and this moves them to
// isolated ground with poor conventional suitability, which is where they belong.
Society add_world_society(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                          const Catalogues& catalogues,const Layers& layers,
                          const std::vector<RegionInfluence>& regions,
                          const std::vector<FoundedCity>& sites,const Humans& humans);
}
