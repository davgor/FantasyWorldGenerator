#pragma once
#include "citygeometry.hpp"
#include <cstdint>
#include <set>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator {
// City-only defensive rings: polylines, segments and gate openings, in metres.
// The schema version the reference stamps on every fortification export.
constexpr std::int64_t fortification_version=1;
// One row of a resolved city preset, carrying only the fields this slice reads. The
// reference's rows are catalogue dicts; `structure_id` is always present because the
// lookup tables are keyed by it.
struct FortificationPresetRow {
    std::string structure_id,id;
    // plot_m.width/plot_m.depth and the instance count of this row.
    double plot_width=0.,plot_depth=0.,count=0.;
    // staffing.roles[].target, in catalogue order. Absent staffing is an empty list.
    std::vector<double> role_targets;
    // dimensions_m, which an infrastructure row may omit.
    bool has_dimensions=false;
    double width=0.,depth=0.,height=0.;
};
// The `buildings` and `infrastructure` groups of a resolved city size preset.
struct FortificationPreset {
    std::vector<FortificationPresetRow> buildings,infrastructure;
};
// A wall or gatehouse definition as `wall_and_gate_defs` resolves it. `present` is the
// reference's None: no such structure in the preset at all.
struct FortificationStructure {
    bool present=false;
    std::string id;
    bool has_dimensions=false;
    double width=0.,depth=0.,height=0.;
};
// One regional road arriving at the city, as the planner's `road_connections` entries
// carry it. Only a connected entry with a non-empty gate point can open a gate.
struct FortificationRoadConnection {
    std::string status;
    bool has_gate=false;
    std::pair<double,double> gate_local_m{0.,0.};
    bool has_route_index=false;
    std::int64_t route_index=0;
};
// The shape parameters this slice reads. The reference is handed the whole parameter
// dict of the chosen shape and looks up one key; absent means the reference default.
struct FortificationShapeParameters {
    bool has_ring_count=false;
    double ring_count=0.;
};
// A gate opening chosen on a ring, before it is given an identity.
struct FortificationGateSite {
    std::int64_t ring_vertex=0;
    bool has_route_index=false;
    std::int64_t route_index=0;
    std::pair<double,double> position_m{0.,0.},approach_m{0.,0.};
};
// One curtain wall segment: a straight run of `segment_depth_m` along the enceinte.
struct FortificationSegment {
    std::string id,ring_id,structure_id;
    std::pair<double,double> from_m{0.,0.},to_m{0.,0.},center_m{0.,0.};
    double length_m=0.,rotation_degrees=0.;
};
// A polyline vertex of a ring, kept as a joinable node.
struct FortificationNode {
    std::string id,kind,ring_id;
    std::pair<double,double> position_m{0.,0.};
};
// A placed gatehouse, with the road approach point it answers.
struct FortificationGate {
    std::string id,ring_id,structure_id;
    std::pair<double,double> position_m{0.,0.},approach_m{0.,0.};
    bool has_route_index=false;
    std::int64_t route_index=0;
};
struct FortificationTower {
    std::string id,ring_id,structure_id;
    std::pair<double,double> position_m{0.,0.};
};
// A ring that closed, with the polyline it closed on.
struct FortificationRing {
    std::string id,role,status;
    double scale=0.;
    std::vector<std::pair<double,double>> polyline_m;
    std::int64_t segment_count=0,gate_count=0;
};
// A structure the fortification pass could not place, and why.
struct FortificationUnplaced {
    std::string building_id,ring_id,reason;
    bool has_ring_id=false;
};
// The whole city fortification export. `defended_perimeter` is true only when a ring
// closed; the method and limits strings are part of the reference's contract.
struct FortificationReport {
    std::int64_t version=fortification_version;
    bool defended_perimeter=false;
    std::vector<FortificationRing> rings;
    std::vector<FortificationSegment> segments;
    std::vector<FortificationNode> nodes;
    std::vector<FortificationGate> gates;
    std::vector<FortificationTower> towers;
    std::vector<FortificationUnplaced> unplaced;
    std::string method,limits;
};
// CPython's round(value, digits) on a float, which is not nearbyint(x*10**n)/10**n:
// the reference rounds the exact decimal expansion half to even, so round(0.125, 2) is
// 0.12. Exported because every rounded coordinate in this slice goes through it, and
// the castle wall port rounds the same way.
double fortification_round_digits(double value,int digits);
// Signed heading change of the polyline a->b->c, in degrees on (-180, 180].
double path_turn_degrees(const std::pair<double,double>& a,const std::pair<double,double>& b,
                         const std::pair<double,double>& c);
// Pull in needle vertices so an enceinte cannot form one giant outward point. Fewer
// than eight points are returned untouched, and unrounded, exactly as the reference
// returns them; castle geometry depends on that.
std::vector<std::pair<double,double>> smooth_closed_ring(
    const std::vector<std::pair<double,double>>& points,double max_turn_degrees=95.,
    double radius_factor=1.12,std::int64_t passes=12);
// Grow the city crop from its class minimum toward programme demand, capped by the
// distance to the nearest neighbouring city. Returns the half extent in metres.
std::int64_t program_half_m(const FortificationPreset& preset,const std::string& city_class,
                            double neighbour_half,double house_plot_width=12.,
                            double house_plot_depth=16.,std::int64_t beds_per_house=4);
// How many enceintes this shape and class ask for.
std::int64_t ring_count_for(const std::string& shape_id,
                            const FortificationShapeParameters& parameters,
                            const std::string& city_class);
// The wall and gatehouse rows of a preset, with the reference's fallback dimensions
// filled in for a wall row that carries no measured ones.
std::pair<FortificationStructure,FortificationStructure> wall_and_gate_defs(
    const FortificationPreset& preset);
// Angular samples of the outermost valid cell on each of 48 rays, clipped to the shape
// scale. A reference-private helper, exported so each family's clip can be pinned.
std::vector<std::pair<double,double>> fortification_boundary_points(
    const std::set<Cell>& valid,double half,double cell,double rx,double rz,double scale,
    const std::string& family);
// Break a closed polyline into curtain segments of `segment_depth_m` and the corner
// nodes of its vertices. A reference-private helper, exported for the same reason.
void fortification_segmentize(const std::vector<std::pair<double,double>>& polyline,
                              double segment_depth_m,const std::string& structure_id,
                              const std::string& ring_id,
                              std::vector<FortificationSegment>& segments,
                              std::vector<FortificationNode>& nodes);
// Which ring vertices open as gates for the connected roads. A reference-private
// helper, exported for the same reason.
std::vector<FortificationGateSite> fortification_gate_sites(
    const std::vector<std::pair<double,double>>& polyline,
    const std::vector<FortificationRoadConnection>& road_connections,std::int64_t gate_budget);
// The city fortification export. The reference takes these keyword-only, in this order.
FortificationReport build_fortifications(const std::set<Cell>& valid,double half,double cell,
                                         double rx,double rz,const std::string& family,
                                         const std::string& shape_id,
                                         const FortificationShapeParameters& parameters,
                                         const std::string& city_class,
                                         const std::vector<FortificationRoadConnection>& road_connections,
                                         const FortificationStructure& wall_structure,
                                         const FortificationStructure& gate_structure,
                                         std::int64_t tower_budget,std::int64_t gate_budget);
}
