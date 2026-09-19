#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
namespace fantasy_world_generator {
struct Plate {std::int64_t id=0;Vec3 center{};Vec3 omega{};};
struct Island {Vec3 direction{};double angular_radius=0.;};
struct Archipelago {std::string id,kind;Vec3 direction{};std::vector<Island> islands;bool eligible=false;};
std::vector<Plate> make_plates(std::uint32_t seed,std::int64_t count);
// Blended plate memberships and relief at one globe direction.
struct PointResult {
    double owner=0.,crust=0.,boundary_distance=0.,convergence=0.,divergence=0.,shear=0.;
    double structure=0.,interaction=0.,volcanic=0.;
};
PointResult layout_point(const Vec3& p,const std::vector<Plate>& plates,std::uint32_t crust_seed,const WorldConfig& cfg);
double crust_value(const Vec3& p,std::uint32_t seed,double bias);
double continental_profile(double c);
struct TectonicResult {
    std::vector<Plate> plates;
    std::vector<Archipelago> archipelagos;
    SedimentBudget sediment;
    std::uint32_t layout_seed=0,crust_seed=0,detail_seed=0;
    std::int64_t resolved_octaves=0;
    double spacing_m=0.;
};
// Static tectonic stages one through four in the order generate_tectonics runs
// them: plate layout, relief, ocean islands, surface noise, erosion, measurement.
TectonicResult generate_tectonics(const WorldConfig& cfg,const SphereGrid& grid,Layers& layers);
}
