#pragma once
#include "citygeometry.hpp"
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator {
// Castle wall-ring geometry: joins, segmentation and perimeter polylines, in metres.
// The schema version the reference stamps on the geometry it produces.
constexpr std::int64_t castle_geometry_version=1;
// A measurement the caller may override. The reference takes these as keyword
// arguments defaulting to None, and falls back to the module's nominal when unset.
struct CastleMeasure {
    bool set=false;
    double value=0.;
};
// An approach point, or the reference's None when a ring has no road arriving at it.
struct CastleApproach {
    bool set=false;
    std::pair<double,double> value{0.,0.};
};
// The `join_rules` block of the castle registry. `segment_depth_m` and
// `min_turn_degrees_for_corner` are whole numbers in the shipped registry but only ever
// feed arithmetic, so a double carries them without changing a result. The two deltas
// are different: they are printed into the refusal messages, and the reference prints
// them with str(), so they must really be the floats the registry holds.
struct CastleJoinRules {
    double max_thickness_delta_m=0.,max_height_delta_m=0.;
    double min_turn_degrees_for_corner=0.,max_turn_degrees=0.,segment_depth_m=0.;
    bool walkway_required=false;
};
// One entry of the registry's `modules` table. Every `has_` flag is a key the reference
// may leave out or set to null, which is not the same as zero: a court has no join end
// and no thickness at all, and a module with no `walkway` key is not a module whose
// walkway is False.
struct CastleModule {
    std::string id,structure_id,role;
    bool has_end_type=false;
    std::string end_type;
    bool has_thickness=false;
    double thickness_nominal=0.;
    bool has_height=false;
    double height_nominal=0.;
    bool has_walkway=false;
    bool walkway=false;
    std::vector<std::string> compatible_ends;
};
// Whether two modules may be joined, and the reference's refusal text when they may
// not. A successful join carries no reason, which is not the same as an empty one.
struct CastleJoinResult {
    bool ok=false;
    bool has_reason=false;
    std::string reason;
};
// One curtain segment: a straight run of about `segment_depth_m` along the ring.
struct CastleSegment {
    std::string id,ring_id,structure_id,module_id;
    std::pair<double,double> from_m{0.,0.},to_m{0.,0.},center_m{0.,0.};
    double length_m=0.,rotation_degrees=0.,thickness_m=0.,height_m=0.;
    bool walkway=true;
};
// A polyline vertex of a ring, kept as a joinable node.
struct CastleRingNode {
    std::string id,kind,ring_id;
    std::pair<double,double> position_m{0.,0.};
};
// A gate, tower or stair sitting on the ring: the things a curtain run joins onto.
// `kind` is empty except on a postern, and `approach_m` is set only on a main gate,
// matching the keys the reference actually writes on each one.
struct CastleJoinNode {
    std::string id,ring_id,module_key,module_id,structure_id;
    std::pair<double,double> position_m{0.,0.};
    bool has_approach=false;
    std::pair<double,double> approach_m{0.,0.};
    bool has_thickness=false;
    double thickness_m=0.;
    double height_m=0.;
    bool has_curtain_height=false;
    double curtain_height_m=0.;
    bool walkway=true;
    std::string kind;
};
// A join the chain validator rejected. The reference keys it by `segment_id` or by
// `node_id`, and a node that carries no id at all leaves the key None.
struct CastleJoinFailure {
    bool is_segment=false;
    bool has_id=false;
    std::string id,reason;
};
// What the ring could not place, and why. `has_building_id` is false for the
// reference's None, which a failed join with no id produces.
struct CastleUnplaced {
    bool has_building_id=true;
    std::string building_id,reason;
};
// The ring the planner asks for: which gate module opens it, whether it gets a postern,
// how many stairs and towers it may afford, and whether it is ditched.
struct CastleRingSpec {
    std::string gate;
    bool postern=false;
    std::int64_t stairs=0,tower_budget=4;
    bool ditch=false;
};
// One assembled fortification ring. `has_counts` marks the three keys the reference
// only writes when the ring closes; a broken ring simply does not carry them.
struct CastleWallNetwork {
    std::string id,role,status;
    std::vector<std::pair<double,double>> polyline_m;
    std::vector<CastleSegment> segments;
    std::vector<CastleRingNode> nodes;
    std::vector<CastleJoinNode> gates,towers,stairs;
    bool walkway_continuous=false;
    std::vector<CastleUnplaced> unplaced;
    bool has_counts=false;
    std::int64_t segment_count=0,gate_count=0;
    bool ditch=false;
};
// CPython's round(x, ndigits) for ndigits >= 0: the exact binary value is rounded to a
// decimal with ties to even and read back, which is not what nearbyint(x*100)/100 or a
// printf round trip give. Every coordinate this module publishes goes through it, so it
// is exported rather than hidden, and the harness pins it directly.
double python_round(double value,int ndigits);
// Signed exterior turn at b going a->b->c, in degrees on (-180, 180].
double turn_degrees(const std::pair<double,double>& a,const std::pair<double,double>& b,
                    const std::pair<double,double>& c);
// End-type and thickness/height compatibility between two modules. A null pointer is
// the reference's None module.
CastleJoinResult can_join(const CastleModule* module_a,const CastleModule* module_b,
                          const CastleJoinRules& rules,
                          const CastleMeasure& thickness_a={},const CastleMeasure& thickness_b={},
                          const CastleMeasure& height_a={},const CastleMeasure& height_b={});
// Closed-ready polyline samples on an axis-aligned ellipse; the last point is not the
// first.
std::vector<std::pair<double,double>> ellipse_ring(double rx,double rz,std::int64_t samples=48);
// Snap each ray sample inward until it lies on buildable land. The reference also takes
// a height lookup and never reads it, so it is not a parameter here; `slope` is the
// dict lookup it does read, and is only consulted for cells in `valid`. A cell step of
// zero or less yields nothing, where the reference raises or produces an empty range.
std::vector<std::pair<double,double>> clip_ring_to_valid(
    const std::vector<std::pair<double,double>>& points,const std::set<Cell>& valid,double half,
    std::int64_t cell,double max_slope_deg,const std::map<Cell,double>& slope);
// Break a closed polyline into curtain segments with stable ids, and keep its vertices
// as nodes. Both outputs are emptied first, so a polyline too short to segment clears
// them exactly as the reference returns two empty lists.
void segmentize(const std::vector<std::pair<double,double>>& polyline,double segment_depth_m,
                const std::string& structure_id,const std::string& ring_id,double thickness_m,
                double height_m,std::vector<CastleSegment>& segments,
                std::vector<CastleRingNode>& nodes);
// Indices where the absolute exterior turn reaches the kit's corner threshold.
std::vector<std::int64_t> corner_indices(const std::vector<std::pair<double,double>>& polyline,
                                         double min_turn_degrees);
// Nearest ring vertex to the approach point, or the +x extremity when there is none.
// The reference returns None for an empty ring; that is -1 here.
std::int64_t approach_gate_index(const std::vector<std::pair<double,double>>& polyline,
                                 const CastleApproach& approach_m);
// The vertex half a ring away. -1 for an empty ring, as above.
std::int64_t opposite_index(const std::vector<std::pair<double,double>>& polyline,
                            std::int64_t index);
// Every consecutive curtain and node join that breaks walkway or dimensional
// continuity. A node naming a module the kit does not carry fails as a missing module.
std::vector<CastleJoinFailure> validate_segment_chain(
    const std::vector<CastleSegment>& segments,const std::vector<CastleJoinNode>& nodes_by_join,
    const std::map<std::string,CastleModule>& modules,const CastleJoinRules& rules);
// Assemble one closed fortification ring with gates, corners, stairs and curtain
// segments. The reference takes these keyword-only, in this order.
CastleWallNetwork build_wall_network(const std::string& ring_id,const std::string& role,
                                     const std::vector<std::pair<double,double>>& polyline,
                                     const CastleApproach& approach_m,
                                     const CastleRingSpec& ring_spec,
                                     const std::map<std::string,CastleModule>& modules,
                                     const CastleJoinRules& rules,bool ditch=false);
}
