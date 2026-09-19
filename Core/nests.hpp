#pragma once
#include "society.hpp"
#include <string>
#include <vector>
namespace fantasy_world_generator {
// A habitat anchor: a static proposal that a species belongs here, not a spawned
// creature, a population or a territory the game must respect.
struct Nest {
    std::string id,species_id,name,family,kind,size,role,layer,creature_class;
    std::size_t node=0;
    std::int64_t x=0,z=0,tier=0;
    Vec3 direction{};
    double suitability=0.,range_m=0.;
    bool real=false,den=false;
};
// How many anchors a species ended up with, which is the part that makes an empty
// result readable rather than mysterious.
struct NestDiagnostic {
    std::string species_id,name,role;
    std::int64_t tier=0,placed=0;
};
struct NestResult {
    std::vector<Nest> sites;
    std::vector<NestDiagnostic> diagnostics;
};
// Two independent thinned point processes over the ground. Tier `t` receives
// `density * falloff^(1-t)` groups per square kilometre of its own medium, spread
// over whatever ground that tier can use; each cell then places
// `floor(lambda) + [u < frac(lambda)]` groups and picks the species in proportion to
// its share. An animal competes only with its own species; a monster is refused only
// by an equal or greater monster, so lesser lairs nest inside a greater territory.
struct Habitats {
    NestResult animals,monsters;
};
Habitats add_nests(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                   const Catalogues& catalogues,const Layers& layers,
                   const std::vector<FoundedCity>& sites,const Humans& humans,
                   const Society& society);
}
