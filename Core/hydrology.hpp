#pragma once
#include "config.hpp"
#include "layers.hpp"
#include <utility>
namespace fantasy_world_generator {
// Unique spherical nodes: pole rows collapse to one node and the duplicate seam
// column is dropped, matching terrain_erosion.sphere_grid.
struct SphereGrid {
    std::vector<std::pair<std::int64_t,std::int64_t>> points;   // (x,z) of each node
    std::vector<double> areas;
    std::vector<std::vector<std::pair<std::int64_t,double>>> neighbors;  // (node, arc metres)
    std::int64_t index(std::int64_t x,std::int64_t z) const;
    std::int64_t n=0;
};
SphereGrid sphere_grid(std::int64_t n,double radius);
// Grid assembly used by every node-space stage: poles repeat and the seam duplicates.
Grid node_grid(const std::vector<double>& values,const SphereGrid& sphere);
std::vector<double> node_values(const Grid& grid,const SphereGrid& sphere);
struct SedimentBudget {double eroded_m3=0.,deposited_m3=0.,stored_sediment_m3=0.,balance_error_m3=0.;};
SedimentBudget erode(const Grid& height,double radius,double sea_level,std::int64_t passes,double strength,
                     const SphereGrid& grid,Layers& layers);
// Connected ocean and equilibrium lake spill routing; fills the water layers.
struct WaterRouting {
    std::vector<std::int64_t> receivers;
    std::vector<double> level,flow;
    std::vector<bool> ocean;
    bool has_ocean=false;
};
WaterRouting add_water(const WorldConfig& cfg,double sea_level,const SphereGrid& grid,Layers& layers);
}
