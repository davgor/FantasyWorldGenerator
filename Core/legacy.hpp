#pragma once
#include "founding.hpp"
#include "magic.hpp"
#include <array>
#include <string>
#include <vector>
namespace fantasy_world_generator {
// Ruin legacies (Sim/icarus_sim/terrain_ruins.py): every fallen city leaves a key point
// in the school of the source of its destruction, else the region's dominant school,
// else its own culture's school. Intensity follows city class.
struct RuinLegacy {
    std::string school,basis;
    double intensity=0.;
};
// `cause` is the ruin cause; `nest_family` the family of a nest cause; `victor_culture`
// the civilization that won a war cause; `god_school` the school of a divine cause;
// `villain_school` the school a super villain holds when it is the proximate cause.
// The last two are always empty natively - no god is summoned here and `villain_rise`
// is zero, so nothing can be seated - and are carried because the reference takes
// them: a port that drops a parameter agrees only for the inputs it never receives.
RuinLegacy ruin_legacy(const std::string& city_class,const std::string& population_profile,const std::string& cause,
                       const std::array<double,school_count>& potency,const std::string& nest_family,
                       const std::string& victor_culture,const std::string& god_school,
                       const std::string& villain_school);
// terrain_civilizations.classify_cities, as the scene unit applies it: one capital per
// people (the founding capital, else best suitability, node breaking ties), medium at
// or above the threshold, small below. Kept here so the age transition can class a city
// before it becomes a ruin.
std::vector<std::string> legacy_city_classes(const std::vector<FoundedCity>& sites,
                                             const std::vector<double>& suitability,double threshold);
}
