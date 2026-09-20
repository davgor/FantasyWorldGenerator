#include "ages.hpp"
#include "wars.hpp"
#include "biomes.hpp"
#include "ecology.hpp"
#include "pyrandom.hpp"
#include "astrology.hpp"
#include "legacy.hpp"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <array>
#include <cmath>
#include <map>
#include <set>
namespace fantasy_world_generator {
namespace {
// What each school does to a city it destroys. The text is the world's own record of
// what happened, so it travels with the ruin rather than being invented by a consumer.
const char* destruction_reason(const std::string& school) {
    if(school=="weave") return "An arcane surge tore the city apart.";
    if(school=="umbral") return "Necrotic entropy extinguished the city.";
    if(school=="infernal") return "Infernal corruption and demonic incursions drove its people away.";
    if(school=="radiant") return "An overwhelming radiant surge forced the city to be abandoned.";
    if(school=="fire") return "A fire leyline engulfed the city in flames.";
    if(school=="water") return "A water leyline drowned or froze the city.";
    if(school=="earth") return "An earth leyline let roots and stone reclaim the city.";
    if(school=="air") return "An air leyline shattered the city with storms and force.";
    return "";
}
// A trace of every fate weight, for comparing one city against the oracle. Off unless
// a caller turns it on, and never part of the world it reports.
bool& fate_trace() {static bool enabled=false;return enabled;}
struct Cause {
    std::string kind,reason,school;
    double weight=0.;
    std::string family;   // nest family of a monster cause, for the ruin's legacy
};
double arc(const Vec3& a,const Vec3& b,double radius) {
    return radius*std::acos(std::max(-1.,std::min(1.,dot(a,b))));
}
bool contains(const std::string& text,const std::string& needle) {
    std::string lowered;
    for(char c:text) lowered+=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return lowered.find(needle)!=std::string::npos;
}
// Standing pressure from the monster lairs near a city. Weight scales with the danger
// tier, so a greater lair at the gates is the reason a city falls and a tier one
// nuisance is not; tier five keeps the flat .55 the single fixed weight used to give
// every monster alike. Animals are never a reason a city falls, nor is a distant lair.
std::vector<Cause> nest_threats(const Vec3& city,const std::vector<Nest>& nests,double radius) {
    std::vector<const Nest*> ordered;
    for(const Nest& nest:nests) ordered.push_back(&nest);
    std::stable_sort(ordered.begin(),ordered.end(),[](const Nest* a,const Nest* b) {return a->id<b->id;});
    std::vector<Cause> causes;
    for(const Nest* nest:ordered) {
        if(nest->layer!="surface" || nest->real) continue;
        const bool dragon=contains(nest->name,"dragon");
        const bool dangerous=dragon || nest->family=="infernal" || nest->family=="undead"
            || nest->family=="aberrant";
        if(!dangerous) continue;
        const double distance=arc(city,nest->direction,radius);
        const double reach=std::min(radius*.5,std::max(350.,nest->range_m*2));
        if(distance>reach) continue;
        causes.push_back(Cause{dragon ? "dragon" : "monster",nest->name+" drove the inhabitants away.",
                               std::string(),.11*static_cast<double>(nest->tier)*(1-distance/reach),nest->family});
    }
    return causes;
}
}
void trace_city_fates(bool enabled) {fate_trace()=enabled;}
PopulatedWorld advance_age(WorldEnvelope& world,const Catalogues& catalogues,
                           const PopulatedWorld& previous,std::int64_t age,AgeResult& out) {
    const WorldConfig& cfg=world.config;
    const double radius=world.effective.globe_radius;
    out=AgeResult{};
    out.age=age;
    // Every fate is decided from the pre-transition fields: the leylines only evolve
    // once the deaths are known, so a city cannot be killed by its own aftermath.
    //
    // Wars are settled first, between cities, out of the ground and supply the finished
    // age left them. A city a neighbour has already taken cannot also be eaten by a
    // dragon, and both sides carry the war whether they won it or not.
    std::vector<FoundedCity> cities=previous.founding.sites;
    std::map<std::string,std::size_t> war_fates;
    const std::vector<War> wars=resolve_wars(cities,previous.humans.cores,previous.roads,
                                             previous.residents,world.grid,radius,
                                             cfg.settlement_spacing,
                                             static_cast<std::uint64_t>(cfg.seed),age,cfg.size,
                                             war_fates);
    std::map<std::string,std::size_t> index_of;
    for(std::size_t index=0;index<cities.size();++index) index_of[cities[index].uid]=index;
    for(const War& war:wars) {
        cities[index_of[war.victor_uid]].war_history.push_back(participation(war,war.victor_uid));
        cities[index_of[war.defeated_uid]].war_history.push_back(participation(war,war.defeated_uid));
    }
    out.wars=wars;
    // The moon on the day the age turns: a momentary surge scales every potency the
    // lottery reads, but the fields themselves are not rewritten.
    const std::int64_t age_day=static_cast<std::int64_t>(previous.founding.end_year)*days_per_year;
    const std::array<double,school_count> tide=lunar_tide(world.moon,age_day);
    // City class decides how strong a key point a ruin leaves.
    std::vector<double> suitability(cities.size(),0.);
    for(std::size_t index=0;index<cities.size();++index) {
        const auto species=previous.fields.species.find(cities[index].population_profile);
        if(species!=previous.fields.species.end()&&cities[index].node<species->second.suitability.size())
            suitability[index]=species->second.suitability[cities[index].node];
    }
    const std::vector<std::string> classes=
        legacy_city_classes(cities,suitability,catalogues.founding_rules().medium_suitability_min);
    std::vector<FoundedCity> survivors;
    for(std::size_t city_index=0;city_index<cities.size();++city_index) {
        const FoundedCity& city=cities[city_index];
        const std::string& city_class=classes[city_index];
        const auto x=static_cast<std::size_t>(world.grid.points[city.node].first);
        const auto z=static_cast<std::size_t>(world.grid.points[city.node].second);
        std::array<double,school_count> potency{};
        const double sway=world.layers.lunar_sensitivity.empty() ? 0. : world.layers.lunar_sensitivity[z][x];
        for(std::size_t index=0;index<school_count;++index) {
            const double base=world.layers.ley[index].empty() ? 0. : world.layers.ley[index][z][x];
            const double factor=1+cfg.options.lunar_influence*sway*(tide[index]-1);
            potency[index]=base*factor;
        }
        const Vec3 seat=direction(world.grid.points[city.node].first,world.grid.points[city.node].second,cfg.size);
        const std::int64_t charged=dominant_school(potency);
        const auto lost=war_fates.find(city.uid);
        if(lost!=war_fates.end()) {
            const War& war=wars[lost->second];
            Ruin ruin;
            ruin.uid=city.uid;
            ruin.id="ruin-"+city.uid;
            ruin.name=city.name;
            ruin.population_profile=city.population_profile;
            ruin.civilization_id=city.population_profile;
            ruin.source_culture=city.source_culture;
            ruin.node=city.node;
            ruin.x=world.grid.points[city.node].first;
            ruin.z=world.grid.points[city.node].second;
            ruin.direction=seat;
            ruin.height_m=sample_height(world,seat);
            ruin.founded_age=city.founded_age;
            ruin.destroyed_age=age;
            ruin.cause="war_"+war.kind;
            ruin.reason=war.reason;
            ruin.probability=war.chance;
            ruin.roll=war.roll;
            // A city whose ground a school already held leaves a key point behind it.
            // The victor's own magic scars the ground it took.
            const RuinLegacy legacy=ruin_legacy(city_class,city.population_profile,ruin.cause,potency,
                                                std::string(),war.victor_civilization_id,std::string());
            ruin.new_node_school=legacy.school;
            ruin.legacy_intensity=legacy.intensity;
            ruin.legacy_basis=legacy.basis;
            ruin.war_history=city.war_history;
            out.ruins.push_back(ruin);
            continue;
        }
        std::vector<Cause> causes;
        const std::int64_t winner=charged;
        double ley_pressure=0.;
        std::string ley_school;
        if(winner>=0) {
            ley_school=school_names()[static_cast<std::size_t>(winner)];
            ley_pressure=std::min(.6,potency[static_cast<std::size_t>(winner)]*.45);
            causes.push_back(Cause{ley_school,destruction_reason(ley_school),ley_school,ley_pressure});
        }
        const Vec3 place=direction(world.grid.points[city.node].first,world.grid.points[city.node].second,cfg.size);
        for(const Cause& threat:nest_threats(place,previous.nests.monsters.sites,radius)) causes.push_back(threat);
        if(cfg.magic_enabled)
            causes.push_back(Cause{"self_magic",
                "The city destroyed itself in a magical experiment, leaving a new Weave key point.",
                std::string(),.035+.06*potency[0]});
        if(fate_trace())
            for(const Cause& cause:causes)
                std::fprintf(stderr,"FATE node %zu cause %s weight %.17g\n",city.node,
                             cause.kind.c_str(),cause.weight);
        Sum total;
        for(const Cause& cause:causes) total.add(cause.weight);
        const double chance=std::min(.9,total.value());
        PyRandom rng(child_seed(static_cast<std::uint64_t>(cfg.seed),"city-fate-"+city.uid,
                                static_cast<std::uint64_t>(age)));
        const double draw=rng.next();
        if(draw>=chance || causes.empty()) {survivors.push_back(city);continue;}
        double selector=(draw/chance)*total.value();
        const Cause* chosen=&causes.back();
        for(const Cause& cause:causes) {
            selector-=cause.weight;
            if(selector<=0) {chosen=&cause;break;}
        }
        Ruin ruin;
        ruin.uid=city.uid;
        ruin.id="ruin-"+city.uid;
        ruin.name=city.name;
        ruin.population_profile=city.population_profile;
        ruin.civilization_id=city.population_profile;
        ruin.source_culture=city.source_culture;
        ruin.node=city.node;
        ruin.x=world.grid.points[city.node].first;
        ruin.z=world.grid.points[city.node].second;
        ruin.direction=place;
        ruin.height_m=sample_height(world,place);
        ruin.founded_age=city.founded_age;
        ruin.destroyed_age=age;
        ruin.cause=chosen->kind;
        ruin.reason=chosen->reason;
        ruin.probability=chance;
        ruin.roll=draw;
        const RuinLegacy legacy=ruin_legacy(city_class,city.population_profile,chosen->kind,potency,
                                            chosen->family,std::string(),std::string());
        ruin.new_node_school=legacy.school;
        ruin.legacy_intensity=legacy.intensity;
        ruin.legacy_basis=legacy.basis;
        // A city that fought and then died to something else still carries its wars.
        ruin.war_history=city.war_history;
        out.ruins.push_back(ruin);
    }
    if(cfg.magic_enabled) {
        // Deep time rescales every leyline, and a city that killed itself with magic
        // leaves a key point behind: the network is edited, never regenerated.
        for(LeyNetwork& network:world.networks) {
            PyRandom rng(child_seed(static_cast<std::uint64_t>(cfg.seed),"age-ley-"+network.name,
                                    static_cast<std::uint64_t>(age)));
            for(LeyNode& node:network.nodes) node.intensity=std::min(4.,node.intensity*rng.uniform(.65,1.35));
            for(LeyEdge& edge:network.edges) edge.intensity=std::min(4.,edge.intensity*rng.uniform(.65,1.35));
        }
        for(const Ruin& ruin:out.ruins) {
            if(ruin.new_node_school.empty()) continue;
            for(LeyNetwork& network:world.networks) {
                if(network.name!=ruin.new_node_school) continue;
                LeyNode node;
                node.direction=ruin.direction;
                node.intensity=ruin.legacy_intensity;
                network.nodes.push_back(node);
            }
        }
        evaluate_networks(cfg,radius,world.grid,world.networks,world.layers);
    }
    // The environment is re-derived from the evolved magic, then the natural biome is
    // restated and the magical variants follow it.
    // The reference's refresh is one call; this core splits the same work into the
    // label pass, the cold reclassification and the environment fields, so a refresh
    // has to make all three or the world loses its boreal, tundra and ice labels.
    Grid density;
    density.swap(world.layers.magic_density);
    add_terrain_labels(cfg,world.effective.sea_level,world.grid,world.layers);
    world.layers.magic_density.swap(density);
    add_cold_habitats(cfg,world.grid,world.layers);
    world.regions=add_environment(cfg,radius,world.spacing_m,world.grid,world.layers);
    add_surface_fields(cfg,world.grid,world.layers);
    world.layers.lunar_sensitivity=lunar_sensitivity(world.layers,cfg.size);
    world.layers.natural_biome=world.layers.biome;
    // Everything a city supported is rebuilt around the cities that are left.
    PopulateContext context;
    context.survivors=survivors;
    // Every ruin the world has ever had, not just this age's: a lost city's ground
    // stays lost, which is what keeps a rebuilt world from reoccupying its own graves.
    for(const Ruin& ruin:previous.ruins) context.forbidden.push_back(ruin.node);
    for(const Ruin& ruin:out.ruins) context.forbidden.push_back(ruin.node);
    context.bonus_used=previous.founding.diaspora_bonus_used;
    context.used_civilizations=previous.founding.used_civilizations;
    context.start_year=previous.founding.end_year+catalogues.founding_rules().years_per_round;
    context.age=age;
    PopulatedWorld populated=populate_world(world,catalogues,context);
    populated.ruins=previous.ruins;
    populated.ruins.insert(populated.ruins.end(),out.ruins.begin(),out.ruins.end());
    world.history_stage=13+age;
    std::set<std::string> old_ids;
    for(const FoundedCity& city:survivors) old_ids.insert(city.uid);
    out.surviving_uids.assign(old_ids.begin(),old_ids.end());
    for(const FoundedCity& city:populated.founding.sites)
        if(old_ids.count(city.uid)==0) out.new_uids.push_back(city.uid);
    return populated;
}
}
