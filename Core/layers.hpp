#pragma once
#include "globe.hpp"
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator {
// Named grids of the reference pipeline. Every grid is size x size with a duplicate
// seam column and pole rows, exactly as the Python layers dictionary exports them.
struct Layers {
    Grid plates,crust,boundary_distance,convergence,divergence,shear;
    Grid structure,interaction,volcanic,continental,archipelago_relief;
    Grid base,height,noise,surface,erosion,deposition,erosion_delta,catchment;
    Grid slope,tpi,land;
    Grid water_type,water_depth,water_surface,routed_catchment,river;
    Grid air_moisture,rainfall,wind_uplift,climate_moisture,rain_runoff,rain_river;
    Grid temperature,moisture,biome,landform,natural_biome;
    Grid salinity,flood_risk,freshwater_distance,wetland_distance,wetland_relief;
    // Magic: one grid per school, in school order, plus the derived fields and the
    // two compatibility projections older rules read.
    Grid ley[8],instability[8];
    Grid magic_density,magic_hazard,magic_growth,magic_opposition,dominant_magic;
    Grid ley_holy,ley_primordial;
    // How far each cell's magic sways with the moon (terrain_astrology.lunar_sensitivity).
    Grid lunar_sensitivity;
    // Ecology: coastal, marine, cold and mineral proxies, plus one field per region.
    Grid metal_richness,coastal_exposure,harbor_suitability,fishing_productivity;
    Grid reef,lagoon,estuary,sheltered_bay,rocky_coast,kelp,fjord,open_ocean,maritime;
    Grid boreal,tundra,ice_cap,coastal_support,island_habitat;
    Grid zone[13];
    // Civilization: what the settlement round publishes for the stages after it, and
    // what the hinterlands add. Empty until those stages run.
    Grid suitability,resource_potential;
    Grid food_potential,natural_food_potential,irrigation_benefit;
    Grid culture_region,hamlet_catchment,civilization_region,fishing_ground_owner;
};
inline Grid filled(std::size_t n,double value) {return Grid(n,std::vector<double>(n,value));}
// The layers a rule may name at runtime. Creature habitat profiles are authored
// against layer names, so the native side needs the same name to grid mapping the
// reference gets for free from its dictionary. Only fields a rule can ask for are
// listed; anything absent reads as missing, which fails a requirement closed.
std::vector<std::pair<std::string,const Grid*>> named_layers(const Layers& layers);
}
