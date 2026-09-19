#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
namespace fantasy_world_generator {
struct ClimateResult {double residual=0.;std::int64_t passes=0;double transport_step_m=0.;};
// Deterministic steady-wind moisture transport on the scaled globe.
ClimateResult add_climate(const WorldConfig& cfg,double radius,double sea_level,const SphereGrid& grid,
                          const WaterRouting& water,Layers& layers);
}
