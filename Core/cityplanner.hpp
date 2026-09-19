#pragma once
#include "citygeometry.hpp"
#include "cityfortifications.hpp"
#include "globe.hpp"
#include "sceneframe.hpp"
#include "settlementpresets.hpp"
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::cityplanner {
// Deterministic final-world schematic city packing, in local metres.
//
// This is the slice the rest of the engine consumes: `plan_city` emits one record per
// city and the plot rows inside it are the placement contract. Everything below is
// shaped by three properties of the reference.
//
// First, the record is a Python dict that is serialized verbatim, so key ORDER and the
// int/float distinction of every value are part of the contract. The port therefore
// builds a `settlementpresets::Value` -- an insertion-ordered JSON tree that keeps ints
// and floats apart -- rather than a struct, and `dumps()` of it is byte-identical to
// `json.dumps(plan, ensure_ascii=False, separators=(',',':'))`.
//
// Second, plan_city reads a large slice of the world envelope and nothing else. `World`
// below is exactly that slice, in the same spirit as `sceneframe::World`: a host that
// already holds a generated world fills it in, and nothing here needs the whole
// envelope or a file.
//
// Third, the heavy lifting already has accepted ports. Streets come from
// `grow_roads`, plots from `footprint_cells`/`corners`, the shape from
// `cityshapes::select_shape`, the enceinte from `build_fortifications`, the crop size
// from `program_half_m`, the presets from `settlementpresets::city_plan` and the road
// gates from `sceneframe::road_entries`. This file adds the packing policy on top and
// re-derives none of them.
using Value=settlementpresets::Value;
// The reference raises out of Python (KeyError on an unknown city class, ValueError
// out of the shape catalogue). Callers read the sentence, so the port carries it.
struct PlannerError : std::runtime_error {
    explicit PlannerError(const std::string& message) : std::runtime_error(message) {}
};
// A world of grid size one makes the grid span `n-1` zero, and every one of the
// reference's `.../(n-1)` divisions is then a ZeroDivisionError a caller can catch and
// move on from. The port raises this instead of letting the arithmetic run: the float
// divisions would quietly produce infinities, and `sample()`'s integer `% (n-1)` is a
// hardware divide fault on Windows, which kills the host process outright rather than
// failing one degenerate world. Derived from PlannerError so existing handlers keep
// working; `what()` is CPython's own sentence.
struct PlannerZeroDivision : PlannerError {
    PlannerZeroDivision() : PlannerError("float division by zero") {}
};
constexpr std::int64_t planner_version=6;
// The local raster step in metres. The reference's module-level CELL.
constexpr std::int64_t planner_cell=4;

// One optional raster of `world['layers']`. `present` false is the reference's
// `layers.get(key)` returning None, which every read replaces with a literal default.
struct Layer {
    bool present=false;
    Grid rows;
};
// A raster whose cell values reach the emitted record unchanged. `natural_biome` and
// `biome_variant` are copied straight into `terrain`, so a Python int has to stay an
// int: a double would print `5.0` where the reference prints `5`.
struct ValueLayer {
    bool present=false;
    std::vector<std::vector<Value>> rows;
};
// One continuous-terrain band of `world['terrain_detail']['bands']`.
struct DetailBand {double scale_m=0.,amplitude_m=0.;};

// The slice of the world envelope `plan_city` reads.
struct World {
    // world['config']['size'] and world['config']['seed'].
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
    // ['river_segments']`.
    std::vector<std::pair<std::int64_t,std::int64_t>> water_nodes;
    std::vector<std::pair<std::int64_t,std::int64_t>> river_segments;
    // world['settlements']['sites'], as the site dicts themselves. The neighbour scan
    // tests `other is site`, so `plan_city` is handed a reference INTO this vector and
    // compares addresses; a site that is not an element of it is a different site to
    // the reference too.
    std::vector<Value> sites;
    // world['roads']['routes'], for sceneframe::road_entries.
    std::vector<sceneframe::Route> routes;
    // world['threat_assessments']['cities'], reduced to (city_uid, regional_threat).
    //
    // The reference matches a row with `c['city_uid']==site.get('uid',str(site['id']))`,
    // which is Python `==`: a row keyed by the STRING "90210" does not match a site
    // whose uid is the INT 90210, and the miss is not cosmetic -- regional_threat and
    // defense_priority feed the weighted shape draw, so the city comes out a different
    // city. `threat_cities` is the string-keyed shorthand every generated world needs.
    // A host whose rows carry a city_uid that is not a string fills `threat_rows`
    // instead; when it is non-empty it is read in its place, and the two are never
    // merged, because `next()` takes the first match in one list's order.
    std::vector<std::pair<std::string,Value>> threat_cities;
    std::vector<std::pair<Value,Value>> threat_rows;
    // Echoed verbatim into `terrain`: the two biome catalogues and the per-network
    // magic colours, the last in dict insertion order.
    Value biome_catalogue,magical_catalogue;
    std::vector<std::pair<std::string,Value>> magic_colors;
};

// `planner_identity()`: the planner version, the civilization registry identity and the
// sha256 of the canonical city-shape catalogue.
Value planner_identity();
// One city's schematic plan. `site` must be a reference to an element of
// `world.sites` for a real settlement, so the reference's `other is site` skip lands on
// the same row; anything else is a site the settlement list does not contain.
// Raises PlannerZeroDivision on a world of grid size one, and PlannerError carrying
// CPython's sentence wherever the reference raises out of Python.
Value plan_city(const World& world,const Value& site,
                const std::map<std::string,std::int64_t>& nearby_counts={});
// `fill_cities()` minus the scene build: every city in `str(uid or id)` order, with the
// running nearby-shape counts threaded through, wrapped in the `city_plans` envelope.
// The reference then calls world_scene.build_scene, which is not part of this slice.
Value fill_cities(const World& world);
}
