#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
#include <array>
#include <string>
namespace fantasy_world_generator {
// Regional influence fields, in the order terrain_world declares them. Placement and
// habitat rules read them by name, so the order is only for reporting.
constexpr std::size_t zone_count=13;
const std::array<const char*,zone_count>& zone_names();
struct RegionInfluence {
    std::string id;
    std::vector<std::size_t> centres;
    double maximum=0.,area_km2=0.;
    std::string reason;
};
// Coastal, marine, cold and mineral proxies plus the magical region fields. Quantities
// are explicit proxies, not simulated tides, currents or biology.
std::vector<RegionInfluence> add_environment(const WorldConfig& cfg,double radius,double spacing_m,
                                             const SphereGrid& grid,Layers& layers);
}
