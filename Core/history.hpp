#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
#include "tectonics.hpp"
namespace fantasy_world_generator {
// Stage six and seven of the recipe-3 world history: a 50-million-year artistic
// epoch that rotates the plates and backtraces crust, then incises the river beds
// and lake floors the reroute abandoned. Angular speeds stay dimensionless.
struct GeologicalHistory {
    std::vector<Plate> plates_before,plates_after;
    double angular_duration=.65;
    std::int64_t elapsed_million_years=50;
};
GeologicalHistory apply_geological_history(const WorldConfig& cfg,double radius,double tpi_radius,double sea_level,
                                           const SphereGrid& grid,std::uint32_t crust_seed,
                                           const std::vector<Plate>& plates,Layers& layers);
}
