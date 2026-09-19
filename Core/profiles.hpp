#pragma once
#include "catalogue.hpp"
#include <map>
#include <string>
#include <vector>
namespace fantasy_world_generator {
// A habitat rule tree: all/any combinations over comparisons on one environment field.
struct HabitatRule {
    enum class Kind {Always,All,Any,Compare} kind=Kind::Always;
    std::vector<HabitatRule> children;
    std::string field;
    bool has_min=false,has_max=false,has_gt=false,has_equals=false,has_in=false;
    double minimum=0.,maximum=0.,greater_than=0.,equals=0.;
    std::vector<double> members;
    // The variant field names a magical biome identity, so membership and equality can
    // be textual. A numeric comparison against a variant is a broken rule, not a zero.
    bool textual=false;
    std::string text_equals;
    std::vector<std::string> text_members;
};
// One environment sample a habitat rule is matched against.
struct Environment {
    double landmass_area_m2=0.,landmass_fraction=0.,abs_latitude=0.,biome=0.;
    double temperature=0.,moisture=0.,maritime=0.,resource=0.,slope=0.,height=0.;
    double tpi=0.,coastal_support=0.;
    bool largest_landmass=false;
    std::string variant;   // magical biome identity, empty when the cell has none
};
bool matches(const HabitatRule& rule,const Environment& environment);
// Population traits and the civilization identity that owns them.
struct Profile {
    std::string id,name;
    std::map<std::string,double> traits;
    std::map<std::int64_t,double> biome_preferences,food_biome_multipliers;
    std::map<std::string,double> magic_biome_preferences,food_magic_biome_multipliers;
    std::string kind,environment,allocation_group,structure_blocks;
    std::int64_t priority=0;
    HabitatRule habitat;
    double trait(const std::string& key) const;
};
// Settlement and economy rule blocks, per entity.
struct EntityRules {
    HabitatRule surface_habitat,world_habitat;
    bool has_freshwater_reach_multiplier=false;
    double freshwater_reach_multiplier=0.;
    bool support_outside_habitat=false;
    double coastal_score_weight=0.,resource_score_weight=0.;
    double fishing_reach_multiplier=1.,winter_fishing_fraction=0.;
};
// A parent race owns one or more civilizations and takes turns founding.
struct ParentRace {std::string id,name;double founding_participation_percent=0.;};
struct FoundingRules {
    double years_per_round=250.,origin_min_separation_degrees=90.;
    double diaspora_interval_years=1000.,diaspora_bonus_per_parent=1.;
    double medium_suitability_min=.65;
};
// How many of a district or building a city gets, before the residents are known.
struct FeatureCount {
    double base=0.,per_100_residents=0.;
    bool has_min=false,has_max=false,has_profiles=false;
    std::int64_t minimum=0,maximum=0;
    std::vector<std::string> profiles;
};
struct LayoutPlacement {
    double river_buffer_m=30.,max_anchor_slope_degrees=12.;
    std::int64_t river_fork_bridge_threshold=2;
    bool bridge_if_river_fork=true;
};
// A city layout profile: named districts and where they may stand.
struct LayoutProfile {
    std::string id,name;
    std::map<std::string,FeatureCount> features;
    LayoutPlacement placement;
};
struct BuildingChoice {std::string asset_id;double weight=1.;};
// One building option of a pack. `placement` is the authoring keyword, kept as text so
// an unknown one fails loudly instead of silently becoming an anchored building.
struct BuildingOption {
    std::string id,name,placement;
    FeatureCount count;
    bool has_profiles=false,required=false,requires_bridge=false;
    std::vector<std::string> profiles,tags;
    std::vector<BuildingChoice> asset_choices;
};
struct BuildingPack {
    std::string id,name,layout_profile_id;
    bool has_profiles=false,has_layout_profile=false,has_biomes=false;
    std::vector<std::string> profiles,biome_variants;
    std::vector<std::int64_t> biomes;
    double height_min=0.,height_max=0.,resource_min=0.,resource_max=0.,slope_max=0.;
    double water_distance_min=0.,water_distance_max=0.,weight=1.;
    std::vector<BuildingOption> building_options;
};
// The city-planning half of the authoring catalogue. Pack order matters: the weighted
// draw walks it, so a reordered table is a different world.
struct CityCatalogues {
    std::string fallback_profile_id,fallback_pack_id;
    std::vector<LayoutProfile> layout_profiles;
    std::vector<BuildingPack> packs;
    const LayoutProfile* layout(const std::string& id) const;
    const BuildingPack& pack(const std::string& id) const;
};
// One creature profile: where a species can live, how far apart its anchors stand and
// how likely it is to appear at all. Habitat anchors, never populations.
struct NestProfile {
    std::string id,name,family,kind,size,medium,creature_class,role;
    bool real=false,sky=false;
    std::int64_t tier=0;
    double temperature_min=0.,temperature_max=0.,spacing_m=0.,occurrence=0.;
    std::vector<std::pair<std::string,double>> weights,requires_at_least;
    // Keyed by the decimal spelling of a natural biome id, as the reference authors
    // them. Empty means the species defers to its role's table.
    std::map<std::string,double> biome_weights;
};
// The resolved authoring catalogue the native rules read.
class Catalogues {
public:
    static Catalogues parse(const std::string& text);
    const Profile& profile(const std::string& id) const;
    const EntityRules& entity(const std::string& id) const;
    const std::vector<std::string>& civilization_ids() const {return civilization_ids_;}
    const std::string& default_profile_id() const {return default_profile_id_;}
    // The aggregate people, which stands in for a cell no city owns.
    const std::string& aggregate_profile_id() const {return aggregate_profile_id_;}
    const std::string& registry_sha256() const {return registry_sha256_;}
    const std::vector<ParentRace>& parent_races() const {return parent_races_;}
    const FoundingRules& founding_rules() const {return founding_rules_;}
    const CityCatalogues& city() const {return city_;}
    const std::vector<NestProfile>& nest_profiles() const {return nests_;}
    // Feeding roles: the biome table every animal of that role uses unless it
    // authors its own.
    const std::map<std::string,std::map<std::string,double>>& nest_roles() const {return nest_roles_;}
    const std::string& parent_race_id(const std::string& civilization) const;
    // Exclusive habitat groups partition capacity; priority then id orders the claim.
    std::vector<std::string> eligible_civilizations(const Environment& environment) const;
private:
    std::map<std::string,Profile> profiles_;
    std::map<std::string,EntityRules> entities_;
    std::vector<std::string> civilization_ids_;
    std::string default_profile_id_,aggregate_profile_id_,registry_sha256_;
    std::vector<ParentRace> parent_races_;
    std::map<std::string,std::string> parents_;
    FoundingRules founding_rules_;
    std::map<std::string,std::map<std::string,double>> nest_roles_;
    CityCatalogues city_;
    std::vector<NestProfile> nests_;
};
// An exact magical state overrides its natural-core preference.
double biome_preference(const Profile& profile,std::int64_t core,const std::string& variant);
double biome_food_multiplier(const Profile& profile,std::int64_t core,const std::string& variant);
}
