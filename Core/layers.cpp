#include "layers.hpp"
#include "ecology.hpp"
#include "magic.hpp"
namespace fantasy_world_generator {
std::vector<std::pair<std::string,const Grid*>> named_layers(const Layers& layers) {
    std::vector<std::pair<std::string,const Grid*>> named{
        {"height",&layers.height},{"slope",&layers.slope},{"tpi",&layers.tpi},{"land",&layers.land},
        {"water_type",&layers.water_type},{"water_depth",&layers.water_depth},
        {"water_surface",&layers.water_surface},{"river",&layers.river},{"rain_river",&layers.rain_river},
        {"temperature",&layers.temperature},{"moisture",&layers.moisture},{"biome",&layers.biome},
        {"landform",&layers.landform},{"natural_biome",&layers.natural_biome},
        {"salinity",&layers.salinity},{"flood_risk",&layers.flood_risk},
        {"freshwater_distance",&layers.freshwater_distance},{"volcanic",&layers.volcanic},
        {"magic_density",&layers.magic_density},{"magic_hazard",&layers.magic_hazard},
        {"magic_growth",&layers.magic_growth},{"magic_opposition",&layers.magic_opposition},
        {"dominant_magic",&layers.dominant_magic},
        {"ley_holy",&layers.ley_holy},{"ley_primordial",&layers.ley_primordial},
        {"lunar_sensitivity",&layers.lunar_sensitivity},
        {"metal_richness",&layers.metal_richness},{"coastal_exposure",&layers.coastal_exposure},
        {"harbor_suitability",&layers.harbor_suitability},
        {"fishing_productivity",&layers.fishing_productivity},
        {"reef",&layers.reef},{"lagoon",&layers.lagoon},{"estuary",&layers.estuary},
        {"sheltered_bay",&layers.sheltered_bay},{"rocky_coast",&layers.rocky_coast},
        {"kelp",&layers.kelp},{"fjord",&layers.fjord},{"open_ocean",&layers.open_ocean},
        {"maritime",&layers.maritime},{"boreal",&layers.boreal},{"tundra",&layers.tundra},
        {"ice_cap",&layers.ice_cap},{"coastal_support",&layers.coastal_support},
        {"island_habitat",&layers.island_habitat},{"suitability",&layers.suitability},
        {"resource_potential",&layers.resource_potential},{"food_potential",&layers.food_potential},
    };
    for(std::size_t index=0;index<school_count;++index)
        named.emplace_back(std::string("ley_")+school_names()[index],&layers.ley[index]);
    for(std::size_t index=0;index<school_count;++index)
        named.emplace_back(std::string("instability_")+school_names()[index],&layers.instability[index]);
    for(std::size_t index=0;index<zone_count;++index)
        named.emplace_back(std::string("zone_")+zone_names()[index],&layers.zone[index]);
    return named;
}
}
