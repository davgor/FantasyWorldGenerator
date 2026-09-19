#pragma once
#include "warhistory.hpp"
#include <vector>
#include "globe.hpp"
#include <cstdint>
#include <string>
namespace fantasy_world_generator {
// A city that did not survive an age. It keeps the identity it had, so a consumer can
// say which of its cities this used to be and why it is gone, and its node is never
// resettled by a later age.
struct Ruin {
    std::string id,uid,name,population_profile,civilization_id,source_culture;
    std::string cause,reason,new_node_school;
    std::size_t node=0;
    std::int64_t x=0,z=0,destroyed_age=0,founded_age=0;
    Vec3 direction{};
    double height_m=0.,probability=0.,roll=0.;
    // Marker identity, so a ruin resolves through the asset registry like anything else.
    std::string asset_id="marker.city_ruins";
    // What this city fought before it fell, carried out of the city it used to be.
    std::vector<WarParticipation> war_history;
};
}
