#pragma once
#include <cstdint>
#include <string>
namespace fantasy_world_generator {
// One city's line in its own war history, carried by living cities and by the ruins of
// the ones that lost. It lives in its own header because both a founded city and a ruin
// hold it, and the war rules themselves are built on top of those.
struct WarParticipation {
    std::string war_id,kind,outcome,opponent_uid,opponent_civilization_id,opponent_parent_race_id;
    std::int64_t age=0;
};
}
