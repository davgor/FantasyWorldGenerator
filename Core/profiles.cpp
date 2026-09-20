#include "profiles.hpp"
#include "counter.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator {
namespace {
void require(bool ok) {if(!ok) throw Error("INVALID_INPUT");}
double environment_field(const Environment& environment,const std::string& name) {
    if(name=="biome") return environment.biome;
    if(name=="temperature") return environment.temperature;
    if(name=="moisture") return environment.moisture;
    if(name=="maritime") return environment.maritime;
    if(name=="landmass_area_m2") return environment.landmass_area_m2;
    if(name=="landmass_fraction") return environment.landmass_fraction;
    if(name=="largest_landmass") return environment.largest_landmass ? 1. : 0.;
    if(name=="resource") return environment.resource;
    if(name=="slope") return environment.slope;
    if(name=="height") return environment.height;
    if(name=="tpi") return environment.tpi;
    if(name=="coastal_support") return environment.coastal_support;
    if(name=="abs_latitude") return environment.abs_latitude;
    throw Error("INVALID_INPUT");
}
HabitatRule read_rule(const catalogue::Value& value) {
    HabitatRule rule;
    const auto& members=catalogue::object(value);
    if(members.empty()) return rule;   // an empty rule admits every cell
    for(const char* combiner:{"all","any"}) {
        const auto found=members.find(combiner);
        if(found==members.end()) continue;
        require(members.size()==1);
        rule.kind=std::string(combiner)=="all" ? HabitatRule::Kind::All : HabitatRule::Kind::Any;
        for(const auto& child:catalogue::array(found->second)) rule.children.push_back(read_rule(child));
        require(!rule.children.empty());
        return rule;
    }
    rule.kind=HabitatRule::Kind::Compare;
    rule.field=catalogue::text(catalogue::field(value,"field"));
    rule.textual=rule.field=="variant";
    for(const auto& entry:members) {
        if(entry.first=="field") continue;
        if(entry.first=="min") {rule.has_min=true;rule.minimum=catalogue::number(entry.second);}
        else if(entry.first=="max") {rule.has_max=true;rule.maximum=catalogue::number(entry.second);}
        else if(entry.first=="gt") {rule.has_gt=true;rule.greater_than=catalogue::number(entry.second);}
        else if(entry.first=="equals") {
            rule.has_equals=true;
            if(std::holds_alternative<std::string>(entry.second.data)) {
                rule.textual=true;rule.text_equals=catalogue::text(entry.second);
            } else {
                rule.equals=std::holds_alternative<bool>(entry.second.data)
                    ? (catalogue::boolean(entry.second) ? 1. : 0.) : catalogue::number(entry.second);
            }
        } else if(entry.first=="in") {
            rule.has_in=true;
            for(const auto& item:catalogue::array(entry.second)) {
                if(std::holds_alternative<std::string>(item.data)) {
                    rule.textual=true;rule.text_members.push_back(catalogue::text(item));
                } else {
                    rule.members.push_back(std::holds_alternative<bool>(item.data)
                        ? (catalogue::boolean(item) ? 1. : 0.) : catalogue::number(item));
                }
            }
        } else {
            throw Error("INVALID_INPUT");
        }
    }
    return rule;
}
std::map<std::int64_t,double> read_core_map(const catalogue::Value& value) {
    std::map<std::int64_t,double> out;
    for(const auto& entry:catalogue::object(value))
        out.emplace(std::stoll(entry.first),catalogue::number(entry.second));
    return out;
}
std::map<std::string,double> read_variant_map(const catalogue::Value& value) {
    std::map<std::string,double> out;
    for(const auto& entry:catalogue::object(value)) out.emplace(entry.first,catalogue::number(entry.second));
    return out;
}
}
bool matches(const HabitatRule& rule,const Environment& environment) {
    switch(rule.kind) {
        case HabitatRule::Kind::Always: return true;
        case HabitatRule::Kind::All:
            for(const HabitatRule& child:rule.children) if(!matches(child,environment)) return false;
            return true;
        case HabitatRule::Kind::Any:
            for(const HabitatRule& child:rule.children) if(matches(child,environment)) return true;
            return false;
        case HabitatRule::Kind::Compare: break;
    }
    if(rule.textual) {
        // A cell with no variant matches no membership and no equality, exactly as the
        // reference's None does.
        const std::string& value=environment.variant;
        if(rule.has_in && (value.empty()
            || std::find(rule.text_members.begin(),rule.text_members.end(),value)==rule.text_members.end()))
            return false;
        if(rule.has_equals && value!=rule.text_equals) return false;
        return true;
    }
    const double value=environment_field(environment,rule.field);
    if(rule.has_in && std::find(rule.members.begin(),rule.members.end(),value)==rule.members.end()) return false;
    if(rule.has_min && !(value>=rule.minimum)) return false;
    if(rule.has_max && !(value<=rule.maximum)) return false;
    if(rule.has_gt && !(value>rule.greater_than)) return false;
    if(rule.has_equals && !(value==rule.equals)) return false;
    return true;
}
double Profile::trait(const std::string& key) const {
    const auto found=traits.find(key);
    if(found==traits.end()) throw Error("INVALID_INPUT");
    return found->second;
}
namespace {
// Feature counts, layout profiles and building packs arrive already normalized by the
// exporter, so this reads the settled shape rather than re-deriving authoring defaults.
FeatureCount read_count(const catalogue::Value& value) {
    FeatureCount count;
    count.base=catalogue::number(catalogue::field(value,"base"));
    count.per_100_residents=catalogue::number(catalogue::field(value,"per_100_residents"));
    const catalogue::Value& minimum=catalogue::field(value,"min");
    count.has_min=!catalogue::is_null(minimum);
    if(count.has_min) count.minimum=static_cast<std::int64_t>(catalogue::number(minimum));
    const catalogue::Value& maximum=catalogue::field(value,"max");
    count.has_max=!catalogue::is_null(maximum);
    if(count.has_max) count.maximum=static_cast<std::int64_t>(catalogue::number(maximum));
    const catalogue::Value& profiles=catalogue::field(value,"profiles");
    count.has_profiles=!catalogue::is_null(profiles);
    if(count.has_profiles)
        for(const auto& item:catalogue::array(profiles)) count.profiles.push_back(catalogue::text(item));
    return count;
}
std::vector<std::string> read_strings(const catalogue::Value& value) {
    std::vector<std::string> items;
    for(const auto& item:catalogue::array(value)) items.push_back(catalogue::text(item));
    return items;
}
CityCatalogues read_city(const catalogue::Value& document) {
    CityCatalogues city;
    const catalogue::Value& layouts=catalogue::field(document,"city_layout_profiles");
    city.fallback_profile_id=catalogue::text(catalogue::field(layouts,"fallback_profile_id"));
    for(const auto& item:catalogue::array(catalogue::field(layouts,"profiles"))) {
        LayoutProfile profile;
        profile.id=catalogue::text(catalogue::field(item,"id"));
        profile.name=catalogue::text(catalogue::field(item,"name"));
        for(const auto& feature:catalogue::object(catalogue::field(item,"features")))
            profile.features.emplace(feature.first,read_count(feature.second));
        const catalogue::Value& placement=catalogue::field(item,"placement");
        profile.placement.river_buffer_m=catalogue::number(catalogue::field(placement,"river_buffer_m"));
        profile.placement.max_anchor_slope_degrees=
            catalogue::number(catalogue::field(placement,"max_anchor_slope_degrees"));
        profile.placement.river_fork_bridge_threshold=
            static_cast<std::int64_t>(catalogue::number(catalogue::field(placement,"river_fork_bridge_threshold")));
        profile.placement.bridge_if_river_fork=catalogue::boolean(catalogue::field(placement,"bridge_if_river_fork"));
        city.layout_profiles.push_back(profile);
    }
    const catalogue::Value& packs=catalogue::field(document,"city_building_packs");
    city.fallback_pack_id=catalogue::text(catalogue::field(packs,"fallback_pack_id"));
    for(const auto& item:catalogue::array(catalogue::field(packs,"packs"))) {
        BuildingPack pack;
        pack.id=catalogue::text(catalogue::field(item,"id"));
        pack.name=catalogue::text(catalogue::field(item,"name"));
        const catalogue::Value& profiles=catalogue::field(item,"profiles");
        pack.has_profiles=!catalogue::is_null(profiles);
        if(pack.has_profiles) pack.profiles=read_strings(profiles);
        const catalogue::Value& layout=catalogue::field(item,"layout_profile_id");
        pack.has_layout_profile=!catalogue::is_null(layout);
        if(pack.has_layout_profile) pack.layout_profile_id=catalogue::text(layout);
        const catalogue::Value& biomes=catalogue::field(item,"biomes");
        pack.has_biomes=!catalogue::is_null(biomes);
        if(pack.has_biomes)
            for(const auto& biome:catalogue::array(biomes))
                pack.biomes.push_back(static_cast<std::int64_t>(catalogue::number(biome)));
        pack.biome_variants=read_strings(catalogue::field(item,"biome_variants"));
        pack.height_min=catalogue::number(catalogue::field(item,"height_min"));
        pack.height_max=catalogue::number(catalogue::field(item,"height_max"));
        pack.resource_min=catalogue::number(catalogue::field(item,"resource_min"));
        pack.resource_max=catalogue::number(catalogue::field(item,"resource_max"));
        pack.slope_max=catalogue::number(catalogue::field(item,"slope_max"));
        pack.water_distance_min=catalogue::number(catalogue::field(item,"water_distance_min"));
        pack.water_distance_max=catalogue::number(catalogue::field(item,"water_distance_max"));
        pack.weight=catalogue::number(catalogue::field(item,"weight"));
        for(const auto& raw:catalogue::array(catalogue::field(item,"building_options"))) {
            BuildingOption option;
            option.id=catalogue::text(catalogue::field(raw,"id"));
            option.name=catalogue::text(catalogue::field(raw,"name"));
            option.placement=catalogue::text(catalogue::field(raw,"placement"));
            option.count=read_count(catalogue::field(raw,"count"));
            const catalogue::Value& allowed=catalogue::field(raw,"profiles");
            option.has_profiles=!catalogue::is_null(allowed);
            if(option.has_profiles) option.profiles=read_strings(allowed);
            option.required=catalogue::boolean(catalogue::field(raw,"required"));
            option.requires_bridge=catalogue::boolean(catalogue::field(raw,"requires_bridge"));
            option.tags=read_strings(catalogue::field(raw,"tags"));
            for(const auto& choice:catalogue::array(catalogue::field(raw,"asset_choices"))) {
                BuildingChoice entry;
                entry.asset_id=catalogue::text(catalogue::field(choice,"asset_id"));
                entry.weight=catalogue::number(catalogue::field(choice,"weight"));
                option.asset_choices.push_back(entry);
            }
            pack.building_options.push_back(option);
        }
        city.packs.push_back(pack);
    }
    require(!city.packs.empty() && !city.layout_profiles.empty());
    return city;
}
}
const LayoutProfile* CityCatalogues::layout(const std::string& id) const {
    for(const LayoutProfile& profile:layout_profiles) if(profile.id==id) return &profile;
    return nullptr;
}
const BuildingPack& CityCatalogues::pack(const std::string& id) const {
    for(const BuildingPack& entry:packs) if(entry.id==id) return entry;
    throw Error("INVALID_INPUT");
}
Catalogues Catalogues::parse(const std::string& text) {
    const catalogue::Value document=catalogue::parse(text);
    if(catalogue::text(catalogue::field(document,"schema"))!="fantasy-world-generator.native-catalogues")
        throw Error("UNSUPPORTED_VERSION");
    if(catalogue::number(catalogue::field(document,"version"))!=1) throw Error("UNSUPPORTED_VERSION");
    Catalogues result;
    result.registry_sha256_=catalogue::text(catalogue::field(catalogue::field(document,"registry"),"sha256"));
    result.default_profile_id_=catalogue::text(catalogue::field(catalogue::field(document,"defaults"),"profile_id"));
    result.aggregate_profile_id_=
        catalogue::text(catalogue::field(catalogue::field(document,"defaults"),"aggregate_profile_id"));
    for(const auto& item:catalogue::array(catalogue::field(document,"civilization_ids")))
        result.civilization_ids_.push_back(catalogue::text(item));
    for(const auto& entry:catalogue::object(catalogue::field(document,"profiles"))) {
        Profile profile;
        profile.id=entry.first;
        for(const auto& trait:catalogue::object(entry.second)) {
            const std::string& key=trait.first;
            if(key=="name") {profile.name=catalogue::text(trait.second);continue;}
            if(key=="id" || key=="description" || key=="definition_hash") continue;
            if(key=="schema_version") continue;
            if(key=="biome_preferences") {profile.biome_preferences=read_core_map(trait.second);continue;}
            if(key=="food_biome_multipliers") {profile.food_biome_multipliers=read_core_map(trait.second);continue;}
            if(key=="magic_biome_preferences") {profile.magic_biome_preferences=read_variant_map(trait.second);continue;}
            if(key=="food_magic_biome_multipliers") {
                profile.food_magic_biome_multipliers=read_variant_map(trait.second);continue;
            }
            if(key=="civilization") {
                const catalogue::Value& identity=trait.second;
                profile.kind=catalogue::text(catalogue::field(identity,"kind"));
                profile.environment=catalogue::text(catalogue::field(identity,"environment"));
                const catalogue::Value& group=catalogue::field(identity,"allocation_group");
                profile.allocation_group=catalogue::is_null(group) ? std::string() : catalogue::text(group);
                const catalogue::Value& blocks=catalogue::field(identity,"structure_blocks");
                profile.structure_blocks=catalogue::is_null(blocks) ? std::string() : catalogue::text(blocks);
                profile.priority=static_cast<std::int64_t>(catalogue::number(catalogue::field(identity,"priority")));
                profile.habitat=read_rule(catalogue::field(identity,"habitat"));
                continue;
            }
            profile.traits.emplace(key,catalogue::number(trait.second));
        }
        require(!profile.kind.empty());
        result.profiles_.emplace(entry.first,profile);
    }
    for(const auto& entry:catalogue::object(catalogue::field(document,"entities"))) {
        const catalogue::Value& settlement=catalogue::field(entry.second,"settlement");
        const catalogue::Value& economy=catalogue::field(entry.second,"economy");
        EntityRules rules;
        rules.surface_habitat=read_rule(catalogue::field(settlement,"surface_habitat"));
        rules.world_habitat=read_rule(catalogue::field(settlement,"world_habitat"));
        const catalogue::Value& reach=catalogue::field(settlement,"freshwater_reach_multiplier");
        rules.has_freshwater_reach_multiplier=!catalogue::is_null(reach);
        if(rules.has_freshwater_reach_multiplier) rules.freshwater_reach_multiplier=catalogue::number(reach);
        rules.support_outside_habitat=catalogue::boolean(catalogue::field(settlement,"support_outside_habitat"));
        rules.coastal_score_weight=catalogue::number(catalogue::field(settlement,"coastal_score_weight"));
        rules.resource_score_weight=catalogue::number(catalogue::field(settlement,"resource_score_weight"));
        rules.fishing_reach_multiplier=catalogue::number(catalogue::field(economy,"fishing_reach_multiplier"));
        rules.winter_fishing_fraction=catalogue::number(catalogue::field(economy,"winter_fishing_fraction"));
        result.entities_.emplace(entry.first,rules);
        result.parents_.emplace(entry.first,catalogue::text(catalogue::field(entry.second,"parent_race_id")));
    }
    for(const auto& item:catalogue::array(catalogue::field(document,"parent_races"))) {
        ParentRace race;
        race.id=catalogue::text(catalogue::field(item,"id"));
        race.name=catalogue::text(catalogue::field(item,"name"));
        race.founding_participation_percent=catalogue::number(catalogue::field(item,"founding_participation_percent"));
        result.parent_races_.push_back(race);
    }
    const catalogue::Value& rules=catalogue::field(document,"founding_rules");
    result.founding_rules_.years_per_round=catalogue::number(catalogue::field(rules,"years_per_round"));
    result.founding_rules_.origin_min_separation_degrees=
        catalogue::number(catalogue::field(rules,"origin_min_separation_degrees"));
    result.founding_rules_.diaspora_interval_years=catalogue::number(catalogue::field(rules,"diaspora_interval_years"));
    result.founding_rules_.diaspora_bonus_per_parent=
        catalogue::number(catalogue::field(rules,"diaspora_bonus_per_parent"));
    result.founding_rules_.medium_suitability_min=
        catalogue::number(catalogue::field(catalogue::field(document,"city_classification"),"medium_suitability_min"));
    result.city_=read_city(document);
    for(const auto& item:catalogue::array(catalogue::field(document,"nest_profiles"))) {
        NestProfile profile;
        profile.id=catalogue::text(catalogue::field(item,"id"));
        profile.name=catalogue::text(catalogue::field(item,"name"));
        profile.family=catalogue::text(catalogue::field(item,"family"));
        profile.kind=catalogue::text(catalogue::field(item,"kind"));
        profile.size=catalogue::text(catalogue::field(item,"size"));
        profile.medium=catalogue::text(catalogue::field(item,"medium"));
        profile.creature_class=catalogue::text(catalogue::field(item,"class"));
        profile.tier=static_cast<std::int64_t>(catalogue::number(catalogue::field(item,"tier")));
        require(profile.creature_class=="animal" || profile.creature_class=="monster");
        require(profile.tier>=1 && profile.tier<=5);
        // Monsters carry no feeding role; their family already says what they are.
        if(catalogue::has(item,"role")) profile.role=catalogue::text(catalogue::field(item,"role"));
        if(catalogue::has(item,"biome_weights"))
            for(const auto& weight:catalogue::object(catalogue::field(item,"biome_weights")))
                profile.biome_weights.emplace(weight.first,catalogue::number(weight.second));
        profile.real=catalogue::boolean(catalogue::field(item,"real"));
        profile.sky=catalogue::boolean(catalogue::field(item,"sky"));
        const catalogue::Value::Array& range=catalogue::array(catalogue::field(item,"temperature"));
        require(range.size()==2);
        profile.temperature_min=catalogue::number(range[0]);
        profile.temperature_max=catalogue::number(range[1]);
        profile.spacing_m=catalogue::number(catalogue::field(item,"spacing_m"));
        profile.occurrence=catalogue::number(catalogue::field(item,"occurrence"));
        for(const auto& weight:catalogue::object(catalogue::field(item,"weights")))
            profile.weights.emplace_back(weight.first,catalogue::number(weight.second));
        for(const auto& need:catalogue::object(catalogue::field(item,"requires")))
            profile.requires_at_least.emplace_back(need.first,catalogue::number(need.second));
        require(!profile.weights.empty());
        result.nests_.push_back(profile);
    }
    for(const auto& role:catalogue::object(catalogue::field(document,"nest_roles"))) {
        std::map<std::string,double> table;
        for(const auto& weight:catalogue::object(catalogue::field(role.second,"biome_weights")))
            table.emplace(weight.first,catalogue::number(weight.second));
        require(!table.empty());
        result.nest_roles_.emplace(role.first,table);
    }
    // An animal placed by a role the catalogue does not describe would silently lose
    // its whole range map, so it is an authoring error rather than an empty world.
    // A monster has no role to fall back on, so a monster with no table of its own
    // scores 1.0 on every biome and is equally at home on a glacier and in a rainforest.
    // That was the whole of the monster half's opinion about biome until the 2026-09-20
    // ruling; both loaders now refuse it rather than let it come back quietly.
    for(const NestProfile& profile:result.nests_) {
        require(profile.creature_class!="animal" || result.nest_roles_.count(profile.role)!=0);
        require(profile.creature_class!="monster" || !profile.biome_weights.empty());
    }
    require(!result.profiles_.empty() && !result.civilization_ids_.empty() && !result.parent_races_.empty());
    return result;
}
const std::string& Catalogues::parent_race_id(const std::string& civilization) const {
    const auto found=parents_.find(civilization);
    if(found==parents_.end()) throw Error("INVALID_INPUT");
    return found->second;
}
const Profile& Catalogues::profile(const std::string& id) const {
    const auto found=profiles_.find(id);
    if(found==profiles_.end()) throw Error("INVALID_INPUT");
    return found->second;
}
const EntityRules& Catalogues::entity(const std::string& id) const {
    const auto found=entities_.find(id);
    if(found==entities_.end()) throw Error("INVALID_INPUT");
    return found->second;
}
std::vector<std::string> Catalogues::eligible_civilizations(const Environment& environment) const {
    std::vector<const Profile*> ordered;
    for(const auto& entry:profiles_) ordered.push_back(&entry.second);
    std::stable_sort(ordered.begin(),ordered.end(),[](const Profile* a,const Profile* b) {
        if(a->priority!=b->priority) return a->priority<b->priority;
        return a->id<b->id;
    });
    std::vector<std::string> eligible;
    std::vector<std::string> claimed;
    for(const Profile* profile:ordered) {
        if(profile->kind!="entity") continue;
        const bool group_taken=!profile->allocation_group.empty()
            && std::find(claimed.begin(),claimed.end(),profile->allocation_group)!=claimed.end();
        if(group_taken) continue;
        if(!matches(profile->habitat,environment)) continue;
        eligible.push_back(profile->id);
        if(!profile->allocation_group.empty()) claimed.push_back(profile->allocation_group);
    }
    return eligible;
}
double biome_preference(const Profile& profile,std::int64_t core,const std::string& variant) {
    if(!variant.empty()) {
        const auto found=profile.magic_biome_preferences.find(variant);
        if(found!=profile.magic_biome_preferences.end()) return found->second;
    }
    const auto found=profile.biome_preferences.find(core);
    return found==profile.biome_preferences.end() ? 0. : found->second;
}
double biome_food_multiplier(const Profile& profile,std::int64_t core,const std::string& variant) {
    if(!variant.empty()) {
        const auto found=profile.food_magic_biome_multipliers.find(variant);
        if(found!=profile.food_magic_biome_multipliers.end()) return found->second;
    }
    const auto found=profile.food_biome_multipliers.find(core);
    return found==profile.food_biome_multipliers.end() ? 1. : found->second;
}
}
