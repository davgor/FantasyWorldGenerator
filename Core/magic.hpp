#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
#include <array>
#include <string>
namespace fantasy_world_generator {
// Eight independently seeded schools, in the order the reference declares them; the
// order is part of the contract because dominance ties break on it.
constexpr std::size_t school_count=8;
const std::array<const char*,school_count>& school_names();
struct LeyNode {Vec3 direction{};double intensity=0.;};
struct LeyEdge {std::size_t from=0,to=0;double intensity=0.;};
struct LeyNetwork {
    std::string name;
    double strength=0.,width_m=0.,instability=0.;
    std::uint32_t seed=0;
    bool enabled=false;
    std::vector<LeyNode> nodes;
    std::vector<LeyEdge> edges;
};
// Great-circle frame between two unit directions: start, end, tangent and angle.
struct ArcFrame {Vec3 start{},end{},tangent{};double angle=0.;};
ArcFrame arc_frame(const Vec3& a,const Vec3& b);
double distance_to_frame(const Vec3& p,const ArcFrame& frame);
// Uneven seeded clusters, scattered outliers and independently variable links.
void network_geometry(std::uint32_t seed,std::int64_t count,std::vector<Vec3>& nodes,
                      std::vector<std::pair<std::size_t,std::size_t>>& pairs);
std::vector<LeyNetwork> generate_networks(const WorldConfig& cfg);
// Rebuilds only the magic-derived layers, leaving the network inputs alone.
void evaluate_networks(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                       const std::vector<LeyNetwork>& networks,Layers& layers);
// Highest school at a cell, or -1 when no school leads by the required margin.
std::int64_t dominant_school(const std::array<double,school_count>& potency,
                             double threshold=.35,double margin=.08);
}
