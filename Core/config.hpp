#pragma once
#include <cstdint>
#include <string>
namespace fantasy_world_generator {
// Recipe-3 world options this native slice reads, holding the terrain_world.OPTIONS
// defaults. Rules read these fields rather than literals so that the day a request can
// carry option overrides, nothing else has to change. GenerateRequest currently
// exposes only size and shape, so they are defaults in practice.
struct WorldOptions {
    double mountain_abundance=1.3,metal_abundance=1.,salinity=.65,seasonality=1.,ice_accumulation=.5;
    std::int64_t archipelago_count=5,islands_per_cluster=5;
    double archipelago_occurrence=.8,island_radius=.035,island_spacing=2.5,archipelago_extent=1.;
    double volcanic_island_weight=1.,atoll_weight=1.,continental_island_weight=1.,cold_island_weight=1.;
    double sea_draft=1.,fishing_reach=700.,fish_productivity=60.;
    std::int64_t coastal_hamlets=2;
    // Habitat anchors, not populations. Zero overall density disables both passes;
    // the limits are safety valves, so zero means the ground decides.
    std::int64_t nest_limit=0,nest_per_species=0,nest_variation=0;
    // Tier one groups per square kilometre of a medium; higher tiers follow the
    // pyramid `density * falloff^(1-tier)`.
    double animal_density=4.5,monster_density=.53;
    double animal_tier_falloff=4.,monster_tier_falloff=2.;
    double nest_density=1.,nest_fantasy=1.,nest_min_suitability=.3,nest_spacing=1.;
    double nest_settlement_clearance=250.;
};
// Resolved recipe-3 configuration. Field names follow terrain_lab.Config so the
// Python oracle and this port stay comparable line by line.
struct WorldConfig {
    std::int64_t world_recipe=3,phase=16,tectonics=1,auto_parameters=0;
    std::string shape="globe",world_size="small",population_profile="mixed";
    double globe_radius=10000.,world_scale=0.17744123532462844;
    std::int64_t seed=42,size=65,octaves=5,plate_count=12,layout_variation=0,detail_variation=0;
    double crust_bias=0.,belt_width=.08,tectonic_relief=800.,mountain_detail=.65,sea_level=0.;
    // Gain on collision uplift alone. The hypsometric profile puts ocean floor far
    // below continental platform, as Earth's does, so raising tectonic_relief deepens
    // basins as fast as it raises peaks. This lifts orogenic belts without touching
    // the basins, which is how a world gets mountains that answer to its oceans.
    double orogeny=1.;
    double amplitude=1100.,wavelength=4300.,ridge=.55,radius=500.;
    double depth=500.,width=450.,meander=650.,extent=8000.;
    std::int64_t magic_enabled=1,ley_nodes=10,college_count=2;
    // fortress_count is a ceiling, not a count: the default sits at the parameter
    // bound so it never binds and the road network decides the world's route defence.
    std::int64_t settlement_count=24,hamlets_per_core=3,fortress_count=1024;
    double settlement_spacing=450.,support_reach=1000.,culture_link_cost=1800.;
    double urban_food_demand=10.,human_adaptation=.7,stubbornness=.2,road_max_grade=.35,bridge_cost=200.;
    double ley_width=180.,magic_instability=.45,human_magic_limit=.45;
    std::int64_t erosion_passes=6;
    double erosion_strength=.5;
    std::int64_t rain_passes=48;
    double rain_strength=1.,wind_bearing=90.,temperature_offset=0.,moisture_bias=0.,river_threshold_km2=.15;
    WorldOptions options;
};
}
