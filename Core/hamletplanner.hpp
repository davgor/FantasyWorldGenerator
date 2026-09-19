#pragma once
#include "citygeometry.hpp"
#include "globe.hpp"
#include "sceneframe.hpp"
#include "settlementpresets.hpp"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::hamletplanner {
// Deterministic final-world schematic hamlet packing, independent of city plans.
//
// A hamlet is the small rural sibling of a city plan: a 200 m window by default,
// clipped by the parent city and by every neighbouring anchor, packed with cottages and
// service sheds instead of districts and walls. The record it emits is consumed the same
// way a city plan is, so the same three properties shape this port.
//
// First, the record is a Python dict serialized verbatim, so key ORDER and the int/float
// distinction of every value are part of the contract. The port builds a
// `settlementpresets::Value` -- an insertion-ordered JSON tree that keeps ints and floats
// apart -- and `dumps()` of it is byte-identical to
// `json.dumps(plan, ensure_ascii=False, separators=(',',':'))`.
//
// Second, `plan_hamlet` reads a narrow slice of the world envelope and nothing else.
// `World` below is exactly that slice: the city planner's slice minus the road routes
// and threat table it does not read, plus the hamlet list, which the neighbour scan
// walks.
//
// Third, the heavy lifting already has accepted ports and none of it is re-derived here:
// streets come from `grow_roads`, plots from `footprint_cells`/`corners`, the presets
// from `settlementpresets::hamlet_plan`/`section`, the tangent basis from
// `sceneframe::frame`/`local_direction` and the decimal rounding from
// `fortification_round_digits`.
//
// DUPLICATION, declared: the reference imports `_sampler` and `CELL` from
// `city_planner`, and Core's `cityplanner.cpp` holds that sampler (and the
// `terrain_detail.HeightField` behind it) in an anonymous namespace where no other
// translation unit can reach it. `hamletplanner.cpp` therefore carries a second copy of
// both, kept line-for-line with the city planner's. If either is ever promoted to a
// shared header, this copy should be deleted in favour of it.

using Value=settlementpresets::Value;

// The reference raises out of Python -- KeyError on a missing site field, ValueError out
// of the registry, IndexError on a bad core index. Callers read the sentence, so the port
// carries it rather than inventing a status code.
struct PlannerError : std::runtime_error {
    explicit PlannerError(const std::string& message) : std::runtime_error(message) {}
};
struct PlannerZeroDivision : PlannerError {
    PlannerZeroDivision() : PlannerError("float division by zero") {}
};

// hamlet_planner.VERSION.
constexpr std::int64_t planner_version=2;
// city_planner.CELL, which the reference imports rather than redefining.
constexpr std::int64_t planner_cell=4;
// HALF_DEFAULT: 200 m across, smaller than a small city's 480 m.
constexpr std::int64_t half_default=100;
// NEIGHBOUR_GAP: metres reserved between facing hamlet windows.
constexpr std::int64_t neighbour_gap=8;

// One optional raster of `world['layers']`. `present` false is the reference's
// `layers.get(key)` returning None, which every read replaces with a literal default.
struct Layer {
    bool present=false;
    Grid rows;
};
// A raster whose cell values reach the emitted record unchanged. `natural_biome` and
// `biome_variant` are copied straight into `terrain`, so a Python int has to stay an int:
// a double would print `5.0` where the reference prints `5`.
struct ValueLayer {
    bool present=false;
    std::vector<std::vector<Value>> rows;
};
// One continuous-terrain band of `world['terrain_detail']['bands']`.
struct DetailBand {double scale_m=0.,amplitude_m=0.;};

// The slice of the world envelope `plan_hamlet` reads.
struct World {
    // world['config']['size'] and world['config']['seed']. The seed reaches the street
    // hash through an f-string, so an integer seed is what this models; a world whose
    // seed is a string would hash its text instead.
    std::int64_t size=0,seed=0;
    // `world.get('effective_config', world['config'])['globe_radius']`, both as the
    // number to compute with and as the value the record echoes into
    // `reference_frame.radius_m`, which is an int in a raw config and a float once the
    // world scale has resolved.
    double globe_radius=0.;
    Value radius;
    // `.get('sea_level', 0.)` of the same mapping, which HeightField reads.
    double sea_level=0.;
    // world['layers']['height'] is required; the rest are optional.
    Grid height;
    Layer slope,water_type,river,flood_risk,moisture;
    ValueLayer natural_biome,biome_variant;
    // world.get('terrain_detail'). Without it HeightField returns the coarse bilinear
    // height and `sample` never computes a gradient slope.
    bool has_terrain_detail=false;
    std::int64_t detail_seed=0;
    std::vector<DetailBand> bands;
    Value terrain_detail;                 // echoed into terrain.surface.terrain_detail
    // world['water']['nodes'] and `world.get('climate', world.get('water', {}))
    // ['river_segments']`. The nodes are also what `access_nodes` indexes.
    std::vector<std::pair<std::int64_t,std::int64_t>> water_nodes;
    std::vector<std::pair<std::int64_t,std::int64_t>> river_segments;
    // world['settlements']['sites'], as the site dicts themselves. Every one of them
    // bounds the window -- unlike the city planner there is no identity skip here -- and
    // `sites[hamlet['core_id']]` is the parent city the record names.
    std::vector<Value> sites;
    // world['humans']['hamlets']. The neighbour scan tests `other is hamlet` BEFORE it
    // tests the ids, so `plan_hamlet` must be handed a reference INTO this vector for a
    // hamlet of this world; a hamlet that is not an element of it is a different hamlet
    // to the reference too, and is then bounded by its own twin in the list.
    std::vector<Value> hamlets;
    // Echoed verbatim into `terrain`: the two biome catalogues and the per-network magic
    // colours, the last in dict insertion order.
    Value biome_catalogue,magical_catalogue;
    std::vector<std::pair<std::string,Value>> magic_colors;
};

// `planner_identity()`: the planner version and the civilization registry identity. The
// hamlet planner has no shape catalogue, so unlike the city planner's there is no third
// key.
Value planner_identity();
// `support_road_entries(world, hamlet, half)`: the parent-city support path projected
// into the window, with the boundary crossing recorded as a gate. Always 'unreachable'
// as emitted -- `plan_hamlet` is what upgrades an entry to 'connected'. Exposed because
// the reference exposes it and because it is the one piece with its own failure modes.
Value support_road_entries(const World& world,const Value& hamlet,double half);
// One hamlet's schematic plan. `hamlet` must be a reference to an element of
// `world.hamlets` for a hamlet of this world, so the reference's `other is hamlet` skip
// lands on the same row.
Value plan_hamlet(const World& world,const Value& hamlet);
// `fill_hamlets()` minus the scene build: every hamlet in `str(id)` order, wrapped in the
// `hamlet_plans` envelope. The reference then calls world_scene.build_scene, which is not
// part of this slice.
Value fill_hamlets(const World& world);
}
