#pragma once
#include "scene.hpp"
#include "wars.hpp"
namespace fantasy_world_generator {
// One deep-time transition: nests are judged first, then each city meets its fate,
// then the leylines evolve, the environment is re-derived and the surviving world
// rebuilds everything that depended on the cities that are gone.
struct AgeResult {
    std::int64_t age=0;
    std::vector<Ruin> ruins;
    std::vector<std::string> surviving_uids,new_uids;
    // Every war this age produced, in the order they were settled.
    std::vector<War> wars;
};
// Advances the world by one age in place. `previous` is the populated world before the
// transition and the returned world is the one after it; the ruins are reported rather
// than silently dropped, because a lost city is history a game can show.
// Prints each city's fate weights to stderr. A diagnostic for parity work, never on
// in a shipped consumer.
void trace_city_fates(bool enabled);
PopulatedWorld advance_age(WorldEnvelope& world,const Catalogues& catalogues,
                           const PopulatedWorld& previous,std::int64_t age,AgeResult& out);
}
