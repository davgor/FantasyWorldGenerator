#pragma once
#include "globe.hpp"
#include "sceneframe.hpp"
#include "settlementpresets.hpp"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::scenebuildings {
// The building-emission half of world_scene.py: `position`, `_emit_local_plan` and
// `build_scene`.
//
// This is the slice an engine actually draws. A city, hamlet or castle plan arrives in
// LOCAL metres -- a flat east/north window around the settlement -- and every plot in it
// has to become a dimensioned, rotated, ground-anchored footprint in globe-centred XYZ.
// All three settlement kinds funnel through the same `_emit_local_plan`, so one wrong
// axis here is wrong for every building in the world.
//
// Core/sceneframe.{hpp,cpp} is the OTHER half of the same reference file and holds
// `frame`, `local_direction` and `road_entries`. This module is its sibling: it reuses
// that tangent basis rather than re-deriving one, and follows its conventions (a World
// struct that is exactly the envelope slice the reference reads, Python's own exception
// wording on the error paths, compensated sums wherever the reference writes `sum()`).
//
// Four properties of the reference shape this port.
//
// First, the scene is a Python dict serialized verbatim into `world['world_scene']`, so
// key ORDER and the int/float spelling of every number are part of the contract. The
// port builds a `settlementpresets::Value` -- an insertion-ordered JSON tree that keeps
// ints and floats apart -- and `dumps()` of it is byte-identical to
// `json.dumps(scene, ensure_ascii=False, separators=(',',':'))`. A std::map would sort
// `asset_id` before `settlement_kind` and lose the round trip on every record.
//
// Second, the plan records this consumes are themselves Values, because the accepted
// `cityplanner`, `hamletplanner` and `castleplanner` ports emit them as Values. Nothing
// is re-derived from the plan: `x_m`, `z_m`, `rotation_degrees`, `ground_elevation_m` and
// `dimensions_m` are read as the planner left them, and `dimensions_m` and
// `rotation_degrees` are copied through with their Python types intact.
//
// Third, the reference's `sum(a*b for a,b in zip(...))` three-term dot products are
// CPython's Neumaier-compensated float sum, not a running `+=`. Reference lines 68, 69,
// 110 and 112 all sit on the path every building and every regional road takes, so a
// plain accumulation drifts by an ulp on a meaningful fraction of them. `globe.hpp`'s
// `Sum` is used for each one; the surviving plain additions (the width/depth axis mix and
// the footprint corner offsets) are plain in the reference too and are left plain here.
//
// Fourth, the reference raises out of Python rather than returning a sentinel -- a city
// whose settlement row is missing is a bare `StopIteration` out of `next()` -- and its
// callers let those propagate. The port raises too and keeps CPython's wording.
//
// DUPLICATION, declared: `terrain_detail.HeightField` lives in an anonymous namespace in
// both `cityplanner.cpp` and `hamletplanner.cpp`, where no other translation unit can
// reach it. `scenebuildings.cpp` therefore carries a third copy, kept line-for-line with
// those two. If it is ever promoted to a shared header, all three should be deleted in
// favour of it.

using Value=settlementpresets::Value;

// The reference's own exceptions, with CPython's own sentences. Callers read them.
struct SceneError : std::runtime_error {
    explicit SceneError(const std::string& message) : std::runtime_error(message) {}
};
// `next(s for s in ... if ...)` with no default, when no settlement row matches a city
// plan's `city_uid`. `str(StopIteration())` is the empty string, so this carries one.
struct SceneStopIteration : SceneError {
    SceneStopIteration() : SceneError("") {}
};
struct SceneIndexError : SceneError {
    SceneIndexError() : SceneError("list index out of range") {}
};
struct SceneZeroDivision : SceneError {
    SceneZeroDivision() : SceneError("float division by zero") {}
};

// One optional raster of `world['layers']`. `present` false is the reference's
// `layers.get(key)` returning None, which HeightField replaces with a literal default.
struct Layer {
    bool present=false;
    Grid rows;
};
// A raster whose cells stay Python values. `natural_biome` only ever reaches a dict
// lookup inside HeightField, which copes with any hashable cell, so the cells are kept as
// Values rather than forced to numbers.
struct ValueLayer {
    bool present=false;
    std::vector<std::vector<Value>> rows;
};
// One continuous-terrain band of `world['terrain_detail']['bands']`.
struct DetailBand {double scale_m=0.,amplitude_m=0.;};

// One entry of `world['roads']['routes']`, reduced to what `build_scene` reads. Note this
// is NOT `sceneframe::Route`: build_scene never looks at a route's endpoints, and it does
// echo `river_crossings` verbatim into `bridge_candidates`, which sceneframe has no
// reason to carry.
struct Route {
    // `road['nodes']`, indices into `water_nodes`.
    std::vector<std::int64_t> nodes;
    // `road.get('river_crossings',[])`, copied into the emitted record untouched. Leave
    // it an empty array for a route that has no such key.
    Value river_crossings=Value::make_array();
};

// The slice of the world envelope `build_scene` reads.
struct World {
    // `world['config']['size']`, which is the grid `n` the route nodes project through.
    std::int64_t size=0;
    // `world.get('effective_config', world['config'])['globe_radius']`: the number every
    // radial position multiplies by, and separately the Python value the scene echoes
    // into `radius_m` -- an int in a raw config, a float once the world scale resolves.
    double globe_radius=0.;
    Value radius=Value::make_float(0.);
    // `.get('sea_level', 0.)` of the same mapping, which HeightField reads.
    double sea_level=0.;
    // `world['layers']['height']` is required; the rest are optional.
    Grid height;
    Layer water_type,river,flood_risk;
    ValueLayer natural_biome;
    // `world.get('terrain_detail')`. Without it HeightField returns the coarse bilinear
    // height. `terrain_detail` is ALSO echoed verbatim into the scene, so it is carried
    // as a Value as well as decomposed; leave it Null when the world has none.
    bool has_terrain_detail=false;
    std::int64_t detail_seed=0;
    std::vector<DetailBand> bands;
    Value terrain_detail=Value::make_null();
    // `world.get('water',{}).get('nodes',[])`.
    std::vector<std::pair<std::int64_t,std::int64_t>> water_nodes;
    // `world['settlements']['sites']`, as the site dicts themselves. A city plan finds
    // its row by `s.get('uid', str(s['id'])) == city['city_uid']`, which is Python `==`:
    // the FALLBACK is stringified but a present uid is not, so an int uid never matches a
    // string city_uid. Only `x` and `z` are read off the row that matches.
    std::vector<Value> sites;
    // `world.get('roads',{}).get('routes',[])`, in order; the index is the route id.
    std::vector<Route> routes;
    // `world['city_plans']['cities']`, `world['hamlet_plans']['hamlets']` and
    // `world['castle_plans']['castles']`, exactly as the accepted planner ports emit
    // them. Emission order is cities, then hamlets, then castles, and the scene's lists
    // are append-ordered, so these three vectors decide the output order.
    std::vector<Value> city_plans,hamlet_plans,castle_plans;
};

// `world_scene.build_scene(world)`: the whole scene dict, ready for
// `settlementpresets::dumps`. The reference also assigns it to `world['world_scene']`;
// a caller that wants that does it itself.
//
// Raises SceneStopIteration for a city plan with no settlement row, SceneIndexError for
// a route node index past the end of the water-node list, and
// sceneframe::ZeroDivision for a world of grid size one.
Value build_scene(const World& world);
}
