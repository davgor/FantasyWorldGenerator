#pragma once
#include "castlegeometry.hpp"
#include "globe.hpp"
#include "sceneframe.hpp"
#include "settlementpresets.hpp"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::castleplanner {
// Deterministic final-world castle layouts from fortress pins, independent of the city
// plans (Sim/icarus_sim/castle_planner.py).
//
// Four properties of the reference shape this port.
//
// First, `plan_castle` returns a Python dict that the engine serializes verbatim, so key
// ORDER and the int/float spelling of every number are part of the contract. The port
// therefore builds a `settlementpresets::Value` -- an insertion-ordered JSON tree that
// keeps ints and floats apart -- and `dumps()` of it is byte-identical to
// `json.dumps(plan, ensure_ascii=False, separators=(',',':'))`. The same applies to the
// wall-network reports, which the reference embeds unchanged: the port re-renders the
// accepted `castlegeometry` structs into exactly the key order castle_geometry.py's
// dict literal and its `report.update(...)` produce.
//
// Second, the ring geometry is already ported. Every ellipse, clip, segmentation and
// join decision comes from `castlegeometry`; this file only feeds it and publishes what
// it returns.
//
// Third, castle_planner.py:46-112 carries a value-identical DUPLICATE of
// city_planner._sampler. The Core city planner keeps its own copy inside an anonymous
// namespace, so there is nothing to call; the duplicate is ported privately here and the
// harness proves the two REFERENCE samplers agree value for value on real terrain.
//
// Fourth, the neighbour scan compares `other is fortress` before it compares ids, so
// `plan_castle` has to be handed a reference INTO `World::fortresses` for a real pin.
using Value=settlementpresets::Value;

// The reference raises out of Python (a KeyError from the structure table, a ValueError
// from the registry check, a ZeroDivisionError from the approach interpolation). Callers
// read the sentence, so the port carries it.
struct PlannerError : std::runtime_error {
    explicit PlannerError(const std::string& message) : std::runtime_error(message) {}
};
// castle_planner.VERSION and castle_planner.CELL.
constexpr std::int64_t planner_version=1;
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

// The slice of the world envelope `plan_castle` reads.
struct World {
    // world['config']['size'] and world['config']['seed'].
    std::int64_t size=0,seed=0;
    // `world.get('effective_config', world['config'])['globe_radius']` and that same
    // mapping's `.get('sea_level', 0.)`, which HeightField reads.
    double globe_radius=0.,sea_level=0.;
    // world['layers']['height'] is required; the rest are optional.
    Grid height;
    Layer slope,water_type,river,flood_risk,moisture;
    ValueLayer natural_biome,biome_variant;
    // world.get('terrain_detail'). Without it HeightField returns the coarse bilinear
    // height and `sample` never computes a gradient slope.
    bool has_terrain_detail=false;
    std::int64_t detail_seed=0;
    std::vector<DetailBand> bands;
    // world['water']['nodes'] and `world.get('climate', world.get('water', {}))
    // ['river_segments']`.
    std::vector<std::pair<std::int64_t,std::int64_t>> water_nodes;
    std::vector<std::pair<std::int64_t,std::int64_t>> river_segments;
    // world['settlements']['sites'], read only for the neighbour scan's x and z.
    std::vector<Value> sites;
    // world['humans']['fortresses'], the castle pins themselves. Each needs 'id', 'x',
    // 'z' and may carry 'core_id' and 'access_nodes'.
    std::vector<Value> fortresses;
    // Echoed verbatim into `terrain`: the two biome catalogues and the per-network
    // magic colours, the last in dict insertion order.
    Value biome_catalogue,magical_catalogue;
    std::vector<std::pair<std::string,Value>> magic_colors;
};

// The reference derives `castles.json` from `__file__`; a native build has none, so the
// host names it once. Defaults to the repository layout relative to the working
// directory. `civilizations.json` is named separately, through
// `settlementpresets::set_registry_path`.
void set_castles_path(const std::string& path);
const std::string& castles_path();

// `load_castles()`: read and schema-check the castle registry, cached on (path,
// modification time, size) as the reference's lru_cache is. Owned by the cache.
const Value& load_castles();
// `castle_structures()`: every castle structure row keyed by id, in the order the
// blocks and their structure lists are walked. A repeated id keeps its FIRST position
// and its LAST value, which is what re-assigning a Python dict key does.
Value castle_structures();
// `planner_identity()`: the planner and geometry versions plus the two sha256 sums,
// each over `json.dumps(..., sort_keys=True, separators=(',',':'))` -- note the
// reference leaves ensure_ascii at its default, so that hash is over ESCAPED bytes and
// not over the UTF-8 the registry identity hashes.
Value planner_identity();
// `select_kit(seed, fortress_id, kits)`: one weighted draw from a Mersenne Twister
// seeded with a sha256 HEX DIGEST. CPython turns a str seed into
// `int.from_bytes(text + sha512(text).digest())` and runs init_by_array over its
// little-endian 32-bit words, so this cannot go through `PyRandom`, which takes a
// 64-bit seed. Returns the chosen element of `kits`.
const Value& select_kit(const Value& kits,std::int64_t seed,const std::string& fortress_id);
// `support_approach(world, fortress, half)`: where the fortress access path leaves the
// window, and the single road-connection entry that records it. `has_approach` false is
// the reference's None.
struct SupportApproach {
    bool has_approach=false;
    double x=0.,z=0.;
    Value entries;                       // a JSON array, empty when nothing crossed
};
SupportApproach support_approach(const World& world,const Value& fortress,std::int64_t half);
// One query into the local sampler.
struct Probe {double x=0.,z=0.;bool with_slope=true;};
// The local east/north metre sampler of castle_planner.py:46-112, exposed so the
// duplication stays auditable: the harness feeds the same probes to city_planner's
// sampler, to castle_planner's and to this one, and all three must agree.
//
// Each answer is an array of the SIX fields `plan_castle` actually reads --
// [water, slope, flood, height, natural_biome, biome_variant] -- with the two raster
// reads verbatim, because those two are the only sampler outputs whose int/float
// spelling reaches the published record. `moisture` is in the reference's dict and is
// never read by this planner, so it is not published here.
Value sample_probe(const World& world,const Value& fortress,double half,
                   const std::vector<Probe>& probes);
// One castle's schematic plan. `fortress` must be a reference to an element of
// `world.fortresses` for a real pin, so the reference's `other is fortress` skip lands
// on the same row; anything else is a fortress the list does not contain.
Value plan_castle(const World& world,const Value& fortress);
// `fill_castles()` minus the scene build: every fortress in `str(f['id'])` order,
// wrapped in the `castle_plans` envelope. The reference then calls
// world_scene.build_scene, which is not part of this slice.
Value fill_castles(const World& world);
}
