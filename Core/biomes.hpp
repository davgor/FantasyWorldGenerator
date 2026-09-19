#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
#include <array>
#include <string>
namespace fantasy_world_generator {
// Natural surface identities and their lab colours, from terrain_biome_catalogue.
struct NaturalBiome {std::int64_t id;const char* core;std::array<int,3> color;};
const std::vector<NaturalBiome>& natural_catalogue();
std::int64_t classify(double above_sea,double slope,double temperature,double moisture);
// Marsh needs wet, warm, flat ground within a short reach of mapped water and barely
// above it. Shared so a surface sample can ask the same question the labels asked.
bool marsh_suitable(double wet,double temp,double slope,double water_distance,double height_above_water);
// Temperature, moisture, biome and landform labels on the scaled surface.
void add_terrain_labels(const WorldConfig& cfg,double sea_level,const SphereGrid& grid,Layers& layers);
// Cold-habitat reclassification from the ecology stage: boreal, tundra and land ice.
void add_cold_habitats(const WorldConfig& cfg,const SphereGrid& grid,Layers& layers);
// Monthly temperature proxy and the cold-habitat rule, shared with the ecology stage.
std::vector<double> monthly_temperatures(double mean,double latitude,double wet,double seasonality);
std::string cold_habitat(const std::vector<double>& temps,double wet,double accumulation);
// Salinity, freshwater distance and the flood-risk proxy the detailed surface reads.
void add_surface_fields(const WorldConfig& cfg,const SphereGrid& grid,Layers& layers);
}
