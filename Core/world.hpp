#pragma once
#include "biomes.hpp"
#include "climate.hpp"
#include "config.hpp"
#include "genesis.hpp"
#include "history.hpp"
#include "ecology.hpp"
#include "hydrology.hpp"
#include "magic.hpp"
#include "layers.hpp"
#include "tectonics.hpp"
namespace fantasy_world_generator {
// Versions a consumer can require: the envelope shape and the continuous-terrain
// definition the samples come from.
constexpr std::int64_t world_contract_version=1,terrain_detail_version=1;
// Continuous terrain: coarse elevation plus spherical Perlin bands. Resolved samples
// are authoritative and LOD never changes the height function.
struct DetailBand {double scale_m,amplitude_m;std::uint32_t seed;};
struct WorldEnvelope {
    WorldConfig config;        // requested design inputs
    WorldConfig effective;     // physical metres after the shared world scale
    Layers layers;
    SphereGrid grid;           // unique nodes at the physical radius
    std::vector<Plate> plates;
    std::vector<Archipelago> archipelagos;
    SedimentBudget sediment;
    GeologicalHistory history;
    ClimateResult climate;
    std::vector<LeyNetwork> networks;
    std::vector<RegionInfluence> regions;
    std::vector<DetailBand> bands;
    Grid detail_strength;
    std::uint32_t detail_seed=0;
    double spacing_m=0.,land_km2=0.,ocean_km2=0.,lake_km2=0.,dry_km2=0.;
    bool has_ocean=false;
    std::int64_t size=0,resolved_octaves=0;
    // History stage this envelope has reached. Nine means the magic networks and the
    // environment fields exist but the two age transitions have not run, so those
    // fields are civilization-stage inputs rather than the world's final state.
    std::int64_t history_stage=9;
};
// Seed to world. No engine, file or interpreter dependency.
WorldEnvelope generate_world(const GenerateRequest& request);
WorldConfig resolve_config(const GenerateRequest& request);
// Authoritative local height in metres above the reference sphere, at any globe
// direction. Landscape vertices, foundations, roads and nests all read this.
double sample_height(const WorldEnvelope& world,const Vec3& direction);
// Latitude/longitude helper for the rectangular tangent unwrap consumers use.
Vec3 globe_direction(double latitude_degrees,double longitude_degrees);
// The inverse: where a direction falls on that unwrap, in degrees.
struct GlobeCoordinates {double latitude_degrees=0.,longitude_degrees=0.;};
GlobeCoordinates unwrap_coordinates(const Vec3& direction);
// Everything a consumer needs at one point of the surface, read from the same
// sampled height a foundation, road or nest would use.
struct SurfaceSample {
    double height_m=0.,water_depth_m=0.,temperature_c=0.,moisture=0.,flood_risk=0.;
    // Where the water's own surface sits, for a consumer that draws a sea rather than
    // painting the seabed. Equals the ground height where there is no water.
    double water_surface_m=0.;
    std::int64_t natural_biome=0,water_type=0,landform=0;
    bool river=false;
};
SurfaceSample sample_surface(const WorldEnvelope& world,const Vec3& direction);
// Lab colour of a natural biome identity; three 0..255 channels.
std::array<int,3> natural_biome_color(std::int64_t identity);
}
