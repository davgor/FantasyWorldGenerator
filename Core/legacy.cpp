#include "legacy.hpp"
#include <map>
#include <tuple>
namespace fantasy_world_generator {
namespace {
const std::map<std::string,std::string>& nest_family_school() {
    static const std::map<std::string,std::string> table{
        {"infernal","infernal"},{"undead","umbral"},{"aberrant","weave"},{"fey","weave"},{"holy","radiant"},
        {"unholy","infernal"},{"draconic","fire"},{"primordial","primordial"}};
    return table;
}
const std::map<std::string,std::string>& culture_school() {
    static const std::map<std::string,std::string> table{
        {"human_maritime","water"},{"human_desert","fire"},{"human_cold","water"},{"human_large_island","air"},
        {"human_rainforest","earth"},{"human_heartland","radiant"},{"dwarf","earth"},{"elf","weave"},
        {"gnome","weave"},{"tidekin","water"},{"hill_dwarf","earth"},{"frosthold_dwarf","water"}};
    return table;
}
constexpr double self_magic_floor=2.5,divine_intensity=4.;
double class_intensity(const std::string& city_class) {
    if(city_class=="capital") return 3.5;
    if(city_class=="medium") return 2.5;
    return 1.5;
}
bool starts_with(const std::string& text,const std::string& prefix) {return text.rfind(prefix,0)==0;}
std::string lookup(const std::map<std::string,std::string>& table,const std::string& key) {
    const auto entry=table.find(key);
    return entry==table.end() ? std::string() : entry->second;
}
// The school the destroyer itself leaves behind, or empty when it has no magic of its own.
std::string source_school(const std::string& cause,const std::array<double,school_count>& potency,
                          const std::string& nest_family,const std::string& victor_culture,
                          const std::string& god_school,const std::string& villain_school) {
    for(std::size_t index=0;index<school_count;++index)
        if(cause==school_names()[index]) return cause;
    if(cause=="self_magic") return "weave";
    if(starts_with(cause,"divine")) return god_school;
    // A villain scars the ground with whatever it holds. Holding nothing, it falls
    // through to the region and then the culture, exactly as an unmagical cause does.
    // Ordered after divine and before war_, as terrain_ruins.source_school orders it.
    if(starts_with(cause,"villain")) return villain_school;
    if(starts_with(cause,"war_")) return lookup(culture_school(),victor_culture);
    const std::string school=lookup(nest_family_school(),nest_family);
    if(school=="primordial") {
        // Strongest element at the ruin; a dead tie keeps school order (fire, water, earth, air).
        std::size_t best=4;
        for(std::size_t index=5;index<8;++index)
            if(potency[index]>potency[best]) best=index;
        return school_names()[best];
    }
    return school;
}
}

RuinLegacy ruin_legacy(const std::string& city_class,const std::string& population_profile,const std::string& cause,
                       const std::array<double,school_count>& potency,const std::string& nest_family,
                       const std::string& victor_culture,const std::string& god_school,
                       const std::string& villain_school) {
    RuinLegacy legacy;
    legacy.school=source_school(cause,potency,nest_family,victor_culture,god_school,villain_school);
    legacy.basis="source";
    if(legacy.school.empty()) {
        const std::int64_t dominant=dominant_school(potency);
        if(dominant>=0) legacy.school=school_names()[static_cast<std::size_t>(dominant)];
        legacy.basis="region";
    }
    if(legacy.school.empty()) {
        legacy.school=lookup(culture_school(),population_profile);
        if(legacy.school.empty()) legacy.school="weave";
        legacy.basis="culture";
    }
    legacy.intensity=class_intensity(city_class);
    if(cause=="self_magic") legacy.intensity=std::max(legacy.intensity,self_magic_floor);
    if(starts_with(cause,"divine")) legacy.intensity=divine_intensity;
    return legacy;
}

std::vector<std::string> legacy_city_classes(const std::vector<FoundedCity>& sites,
                                             const std::vector<double>& suitability,double threshold) {
    std::map<std::string,std::size_t> capital;
    for(std::size_t index=0;index<sites.size();++index) {
        const auto entry=capital.find(sites[index].population_profile);
        if(entry==capital.end()) {capital.emplace(sites[index].population_profile,index);continue;}
        const std::size_t best=entry->second;
        if(std::make_tuple(!sites[index].founding_capital,-suitability[index],sites[index].node)
           <std::make_tuple(!sites[best].founding_capital,-suitability[best],sites[best].node))
            entry->second=index;
    }
    std::vector<std::string> classes(sites.size(),"small");
    for(std::size_t index=0;index<sites.size();++index)
        classes[index]=capital[sites[index].population_profile]==index?"capital"
            :suitability[index]>=threshold?"medium":"small";
    return classes;
}
}
