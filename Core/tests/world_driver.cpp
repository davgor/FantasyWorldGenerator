// Headless parity driver: prints exact doubles for comparison with the Python oracle.
#include "frame.hpp"
#include "globe.hpp"
#include "hydrology.hpp"
#include "ecology.hpp"
#include "profiles.hpp"
#include "founding.hpp"
#include "cityplan.hpp"
#include "humans.hpp"
#include "ages.hpp"
#include "nests.hpp"
#include "scene.hpp"
#include "settlements.hpp"
#include "magic.hpp"
#include "pyrandom.hpp"
#include "registry.hpp"
#include "tectonics.hpp"
#include "world.hpp"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <algorithm>
#include <sstream>
#include <string>
using namespace fantasy_world_generator;
namespace {
void emit(double value) {std::printf("%.17g\n",value);}
void emit_grid(const std::string& key,const Grid& grid) {
    std::printf("#%s\n",key.c_str());
    for(const auto& row:grid) for(double value:row) emit(value);
}
}
namespace {
// Any operation may carry `scale=<decimal>`, the shared world scale, so a parity run
// can ask for the same physical world the reference builds from that override.
void apply_scale(fantasy_world_generator::GenerateRequest& request,int argc,char** argv) {
    for(int index=1;index<argc;++index) {
        const std::string argument=argv[index];
        if(argument.rfind("scale=",0)==0) {request.world_scale=std::stod(argument.substr(6));continue;}
        // `set:<name>=<value>` carries any named recipe override the core resolves.
        if(argument.rfind("worldsize=",0)==0) {request.world_size=argument.substr(10);continue;}
        if(argument.rfind("set:",0)!=0) continue;
        const std::size_t split=argument.find('=');
        if(split==std::string::npos) continue;
        request.overrides.emplace(argument.substr(4,split-4),std::stod(argument.substr(split+1)));
    }
}
}

int main(int argc,char** argv) {
    if(argc<2) return 2;
    const std::string operation=argv[1];
    if(operation=="frame") {
        // latitude longitude radius origin_height px py pz per line.
        double latitude,longitude,radius,height,px,py,pz;
        while(std::cin>>latitude>>longitude>>radius>>height>>px>>py>>pz) {
            const TangentFrame tangent=tangent_frame(latitude,longitude);
            for(const Vec3* axis:{&tangent.up,&tangent.east,&tangent.north}) {emit((*axis)[0]);emit((*axis)[1]);emit((*axis)[2]);}
            const Vec3 globe=globe_position(latitude,longitude,radius,height);
            emit(globe[0]);emit(globe[1]);emit(globe[2]);
            const Vec3 local=local_position(Vec3{px,py,pz},latitude,longitude,radius,height);
            emit(local[0]);emit(local[1]);emit(local[2]);
            const UnrealVector unreal=unreal_centimetres(local);
            emit(unreal.x_cm);emit(unreal.y_cm);emit(unreal.z_cm);
            const UnrealVector axis=unreal_axis(tangent.east);
            emit(axis.x_cm);emit(axis.y_cm);emit(axis.z_cm);
        }
        return 0;
    }
    if(operation=="registry") {
        std::ifstream file(argv[2],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const AssetRegistry registry=AssetRegistry::parse(buffer.str());
        std::printf("rows %zu\n",registry.size());
        std::printf("unbound %zu\n",registry.unbound().size());
        std::printf("asset_list %s\n",registry.asset_list_sha256().c_str());
        std::string identity;
        while(std::getline(std::cin,identity)) {
            while(!identity.empty() && (identity.back()=='\r' || identity.back()==' ')) identity.pop_back();
            if(identity.empty()) continue;
            const AssetBinding* binding=registry.find(identity);
            if(!binding) std::printf("%s missing_identity\n",identity.c_str());
            else if(binding->bound()) std::printf("%s %s %s\n",identity.c_str(),binding->status.c_str(),binding->path.c_str());
            else std::printf("%s unbound %s\n",identity.c_str(),binding->reason.c_str());
        }
        return 0;
    }
    if(operation=="perlin3") {
        double x,y,z;long long seed;
        while(std::cin>>x>>y>>z>>seed) emit(perlin3(x,y,z,seed));
        return 0;
    }
    if(operation=="random" || operation=="gauss") {
        PyRandom rng(std::stoull(argv[2]));
        const int count=std::stoi(argv[3]);
        for(int i=0;i<count;++i) emit(operation=="random" ? rng.next() : rng.gauss(0,1));
        return 0;
    }
    if(operation=="unit3") {
        double x,y,z;
        while(std::cin>>x>>y>>z) {const Vec3 u=unit(Vec3{x,y,z});emit(u[0]);emit(u[1]);emit(u[2]);}
        return 0;
    }
    if(operation=="world" || operation=="samples") {
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        const WorldEnvelope world=generate_world(request);
        if(operation=="samples") {
            double latitude,longitude;
            while(std::cin>>latitude>>longitude) emit(sample_height(world,globe_direction(latitude,longitude)));
            return 0;
        }
        const Layers& l=world.layers;
        const std::map<std::string,const Grid*> named{
            {"plates",&l.plates},{"crust",&l.crust},{"boundary_distance",&l.boundary_distance},
            {"convergence",&l.convergence},{"divergence",&l.divergence},{"shear",&l.shear},
            {"structure",&l.structure},{"interaction",&l.interaction},{"volcanic",&l.volcanic},
            {"continental",&l.continental},{"archipelago_relief",&l.archipelago_relief},
            {"noise",&l.noise},{"surface",&l.surface},{"base",&l.base},{"height",&l.height},
            {"erosion",&l.erosion},{"deposition",&l.deposition},{"erosion_delta",&l.erosion_delta},
            {"catchment",&l.catchment},{"slope",&l.slope},{"tpi",&l.tpi},{"land",&l.land},
            {"water_type",&l.water_type},{"water_depth",&l.water_depth},{"water_surface",&l.water_surface},
            {"routed_catchment",&l.routed_catchment},{"river",&l.river},
            {"air_moisture",&l.air_moisture},{"rainfall",&l.rainfall},{"wind_uplift",&l.wind_uplift},
            {"climate_moisture",&l.climate_moisture},{"rain_runoff",&l.rain_runoff},{"rain_river",&l.rain_river},
            {"temperature",&l.temperature},{"moisture",&l.moisture},{"biome",&l.biome},
            {"landform",&l.landform},{"natural_biome",&l.natural_biome},{"salinity",&l.salinity},
            {"flood_risk",&l.flood_risk},{"freshwater_distance",&l.freshwater_distance},
            {"lunar_sensitivity",&l.lunar_sensitivity},
            };
        for(const auto& entry:named) if(!entry.second->empty()) emit_grid(entry.first,*entry.second);
        emit_grid("area",Grid{{world.land_km2,world.ocean_km2,world.lake_km2,world.dry_km2}});
        return 0;
    }
    if(operation=="catalogues") {
        std::ifstream file(argv[2],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        Catalogues catalogues;
        try {
            catalogues=Catalogues::parse(buffer.str());
        } catch(const Error& failure) {
            std::fprintf(stderr,"catalogue rejected: %s\n",failure.what());
            return 2;
        }
        std::printf("default %s\n",catalogues.default_profile_id().c_str());
        std::printf("registry %s\n",catalogues.registry_sha256().c_str());
        for(const std::string& id:catalogues.civilization_ids()) {
            const Profile& profile=catalogues.profile(id);
            std::printf("profile %s %s %lld %s %s\n",id.c_str(),profile.kind.c_str(),
                static_cast<long long>(profile.priority),
                profile.allocation_group.empty() ? "-" : profile.allocation_group.c_str(),
                profile.name.c_str());
        }
        // Then one line per requested trait or habitat query from stdin.
        std::string line;
        while(std::getline(std::cin,line)) {
            while(!line.empty() && (line.back()=='\r' || line.back()==' ')) line.pop_back();
            if(line.empty()) continue;
            std::istringstream fields(line);
            std::string kind;
            fields>>kind;
            if(kind=="trait") {
                std::string id,key;
                fields>>id>>key;
                std::printf("%.17g\n",catalogues.profile(id).trait(key));
            } else if(kind=="preference") {
                std::string id,variant;long long core;
                fields>>id>>core>>variant;
                if(variant=="-") variant.clear();
                std::printf("%.17g %.17g\n",biome_preference(catalogues.profile(id),core,variant),
                    biome_food_multiplier(catalogues.profile(id),core,variant));
            } else if(kind=="habitat") {
                Environment environment;
                fields>>environment.biome>>environment.temperature>>environment.moisture>>environment.maritime
                      >>environment.landmass_area_m2>>environment.landmass_fraction>>environment.abs_latitude;
                double largest=0.;
                fields>>largest;
                environment.largest_landmass=largest!=0.;
                const std::vector<std::string> eligible=catalogues.eligible_civilizations(environment);
                std::string joined;
                for(const std::string& id:eligible) joined+=(joined.empty() ? "" : ",")+id;
                std::printf("%s\n",joined.empty() ? "-" : joined.c_str());
            }
        }
        return 0;
    }
    if(operation=="fields") {
        // Step (a): per-people suitability and capacity, against the same catalogue the
        // reference reads. Needs the catalogue path because the traits live there.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        WorldEnvelope world=generate_world(request);
        const SettlementFields fields=evaluate_settlement_fields(world.config,world.effective.globe_radius,
                                                                 world.grid,catalogues,world.layers);
        for(const std::string& species:catalogues.civilization_ids()) {
            const SpeciesField& field=fields.species.at(species);
            emit_grid("suitability_"+species,node_grid(field.suitability,world.grid));
            emit_grid("life_capacity_"+species,node_grid(field.potential,world.grid));
            if(!field.support_reach.empty())
                emit_grid(species+"_support_reach",node_grid(field.support_reach,world.grid));
        }
        const std::uint32_t settlement_seed=child_seed(static_cast<std::uint64_t>(world.config.seed),"settlements");
        const FoundingResult founded=found_cities(settlement_seed,world.config,world.effective.globe_radius,
                                                  world.grid,catalogues,fields);
        Grid cities;
        for(const FoundedCity& city:founded.sites) {
            std::size_t index=0;
            const std::vector<std::string>& ids=catalogues.civilization_ids();
            for(std::size_t k=0;k<ids.size();++k) if(ids[k]==city.population_profile) index=k;
            cities.push_back({static_cast<double>(city.node),static_cast<double>(index),
                static_cast<double>(city.founding_turn),city.founding_year,
                city.founding_capital ? 1. : 0.,city.diaspora ? 1. : 0.,
                city.cultural_branch ? 1. : 0.,city.migration_distance_m});
        }
        emit_grid("cities",cities);
        const std::vector<Road> roads=build_roads(world.config,world.grid,catalogues,world.layers,founded.sites);
        Grid routes;
        for(const Road& road:roads) {
            std::vector<double> row{static_cast<double>(road.from),static_cast<double>(road.to),
                road.length_m,road.cost,static_cast<double>(road.nodes.size()),
                static_cast<double>(road.river_crossings.size())};
            for(std::size_t node:road.nodes) row.push_back(static_cast<double>(node));
            routes.push_back(row);
        }
        const WorldScene scene=build_scene(world,founded.sites,roads,fields);
        for(const RegionalRoad& road:scene.regional_roads) {
            Grid polyline;
            for(const Vec3& point:road.positions_m) polyline.push_back({point[0],point[1],point[2]});
            emit_grid("polyline",polyline);
        }
        for(const CityAnchor& city:scene.cities)
            emit_grid("anchor",Grid{{static_cast<double>(city.node),city.position_m[0],city.position_m[1],
                city.position_m[2],city.height_m,city.suitability}});
        emit_grid("roads",Grid{{static_cast<double>(roads.size())}});
        for(const auto& row:routes) emit_grid("route",Grid{row});
        emit_grid("founding",Grid{{static_cast<double>(founded.turns),static_cast<double>(founded.target_cities),
            static_cast<double>(founded.sites.size())}});
        emit_grid("world_cap",Grid{{static_cast<double>(fields.budget.world_cap)}});
        for(const std::string& species:catalogues.civilization_ids())
            emit_grid("budget_"+species,Grid{{static_cast<double>(fields.budget.allowances.at(species)),
                static_cast<double>(fields.budget.quotas.at(species)),
                fields.budget.weighted_habitat_km2.at(species),fields.budget.shares.at(species)}});
        return 0;
    }
    if(operation=="cityplans") {
        // Step (d): the city layout plans, printed as tab-separated rows because the
        // identities here are text, not numbers.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        WorldEnvelope world=generate_world(request);
        const SettlementFields fields=evaluate_settlement_fields(world.config,world.effective.globe_radius,
                                                                 world.grid,catalogues,world.layers);
        const std::uint32_t settlement_seed=child_seed(static_cast<std::uint64_t>(world.config.seed),"settlements");
        const FoundingResult founded=found_cities(settlement_seed,world.config,world.effective.globe_radius,
                                                  world.grid,catalogues,fields);
        std::vector<PopulationEstimate> residents;
        for(int index=1;index<argc;++index)
            if(std::string(argv[index])=="residents=1")
                residents=estimate_population(fields.budget,founded.sites);
        const std::vector<CityPlan> plans=plan_cities(world.config,world.grid,catalogues,world.layers,
                                                      fields,founded.sites,residents);
        auto joined=[](const std::vector<std::string>& items) {
            std::string text;
            for(const std::string& item:items) text+=(text.empty() ? "" : ",")+item;
            return text.empty() ? std::string("-") : text;
        };
        for(std::size_t index=0;index<plans.size();++index) {
            const CityPlan& plan=plans[index];
            std::printf("PLAN\t%zu\t%u\t%s\t%s\t%lld\t%d\t%lld\t",index,plan.city_seed,
                plan.building_pack_id.c_str(),plan.layout_profile_id.c_str(),
                static_cast<long long>(plan.adjacent_river_edges),plan.bridge_recommended ? 1 : 0,
                static_cast<long long>(plan.bridge_threshold));
            if(plan.river_distance_finite) std::printf("%.17g",plan.river_distance_m); else std::printf("-");
            std::printf("\t%lld\t%lld\t%d\t%s\n",static_cast<long long>(plan.required_asset_count),
                static_cast<long long>(plan.required_node_slots),plan.missing_anchors ? 1 : 0,
                plan.fallback_reason.empty() ? "-" : plan.fallback_reason.c_str());
            for(const PlanFeature& feature:plan.features) {
                std::printf("FEATURE\t%zu\t%s\t%lld\t%zu",index,feature.name.c_str(),
                    static_cast<long long>(feature.target_count),feature.anchors.size());
                for(const PlanAnchor& anchor:feature.anchors)
                    std::printf("\t%zu:%.17g",anchor.node,anchor.distance_to_city_m);
                std::printf("\n");
            }
            for(const BuildingOptionPlan& option:plan.options) {
                std::printf("OPTION\t%zu\t%s\t%s\t%lld\t%zu\t%lld\t%d\t%d\t%s\t%s\t%s",index,
                    option.option_id.c_str(),option.placement.c_str(),
                    static_cast<long long>(option.target_count),option.anchors.size(),
                    static_cast<long long>(option.required_node_slots),option.required ? 1 : 0,
                    option.bridge_required ? 1 : 0,option.skip_reason.empty() ? "-" : option.skip_reason.c_str(),
                    joined(option.tags).c_str(),joined(option.assets).c_str());
                for(const PlanAnchor& anchor:option.anchors)
                    std::printf("\t%zu:%.17g",anchor.node,anchor.distance_to_city_m);
                std::printf("\n");
            }
            for(const auto& entry:plan.required_assets)
                std::printf("REQUIRED\t%zu\t%s\t%lld\n",index,entry.first.c_str(),
                    static_cast<long long>(entry.second));
        }
        return 0;
    }
    if(operation=="humans") {
        // The hinterlands: hamlets, fortresses, cultures and the fields they publish.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        WorldEnvelope world=generate_world(request);
        const PopulatedWorld populated=populate_world(world,catalogues);
        const Humans& humans=populated.humans;
        // The access path is emitted alongside the access cost, and it is the field that
        // tells the two kinds of access_cost divergence apart. `access_cost` is a Dijkstra
        // total, so the additions run strictly along the settled path: an identical path
        // gives an identical double. A differing cost with an IDENTICAL path is therefore
        // arithmetic inside one edge; a differing cost with a DIFFERING path is a routing
        // divergence wearing a small number's clothes. Six hamlets currently differ by one
        // to three ulp and nothing on either side recorded which of those it was.
        for(const RuralSite& site:humans.hamlets) {
            std::string path;
            for(std::size_t node:site.access_nodes)
                path+=(path.empty() ? "" : ",")+std::to_string(node);
            std::printf("HAMLET\t%s\t%zu\t%s\t%s\t%s\t%.17g\t%.17g\t%.17g\t%.17g\t%.17g\t%s\n",
                site.id.c_str(),site.node,site.role.c_str(),site.population_profile.c_str(),
                site.culture_id.c_str(),site.access_cost,site.worked_area_km2,site.delivered_food,
                site.delivered_materials,site.irrigation_benefit,path.c_str());
        }
        for(const RuralSite& site:humans.fortresses)
            std::printf("FORTRESS\t%s\t%zu\t%s\t%.17g\t%zu\t%.17g\n",site.id.c_str(),site.node,
                site.population_profile.c_str(),site.defence_score,site.protected_route_node,
                site.access_cost);
        for(const Culture& culture:humans.cultures) {
            std::printf("CULTURE\t%lld\t%s\t%s",static_cast<long long>(culture.index),culture.id.c_str(),
                culture.population_profile.c_str());
            for(std::int64_t city:culture.city_ids) std::printf("\t%lld",static_cast<long long>(city));
            std::printf("\n");
        }
        for(const CityCore& core:humans.cores)
            std::printf("CORE\t%lld\t%s\t%s\t%.17g\t%.17g\t%.17g\n",static_cast<long long>(core.site_id),
                core.population_profile.c_str(),core.culture_id.c_str(),core.food_supply,
                core.material_supply,core.food_demand);
        for(const Port& port:populated.society.ports)
            std::printf("PORT\t%s\t%zu\t%zu\t%s\t%.17g\t%.17g\t%d\t%zu\n",port.id.c_str(),port.node,
                port.sea_node,port.population_profile.c_str(),port.harbor_quality,port.access_cost,
                port.trade_terminal ? 1 : 0,port.access_nodes.size());
        for(const Landmark& mark:populated.society.landmarks)
            std::printf("LANDMARK\t%s\t%s\t%zu\t%.17g\n",mark.id.c_str(),mark.kind.c_str(),mark.node,
                mark.intensity);
        emit_grid("food_potential",node_grid(humans.food_potential,world.grid));
        emit_grid("culture_region",node_grid(humans.culture_region,world.grid));
        emit_grid("hamlet_catchment",node_grid(humans.hamlet_catchment,world.grid));
        emit_grid("civilization_region",node_grid(humans.civilization_region,world.grid));
        return 0;
    }
    if(operation=="nests") {
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        WorldEnvelope world=generate_world(request);
        const PopulatedWorld populated=populate_world(world,catalogues);
        // Two passes, tagged so the oracle compares each against its own export.
        const std::pair<const char*,const NestResult*> passes[]={
            {"animal",&populated.nests.animals},{"monster",&populated.nests.monsters}};
        for(const auto& pass:passes) {
            for(const Nest& nest:pass.second->sites)
                std::printf("NEST\t%s\t%s\t%s\t%zu\t%lld\t%.17g\t%.17g\t%d\n",pass.first,
                    nest.id.c_str(),nest.species_id.c_str(),nest.node,
                    static_cast<long long>(nest.tier),nest.suitability,nest.range_m,
                    nest.den ? 1 : 0);
            for(const NestDiagnostic& diagnostic:pass.second->diagnostics)
                std::printf("NESTDIAG\t%s\t%s\t%lld\t%lld\n",pass.first,
                    diagnostic.species_id.c_str(),static_cast<long long>(diagnostic.tier),
                    static_cast<long long>(diagnostic.placed));
        }
        return 0;
    }
    if(operation=="ages") {
        // The finished world: two age transitions on top of the populated one.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        WorldEnvelope world=generate_world(request);
        for(int index=1;index<argc;++index)
            if(std::string(argv[index])=="trace=fates") trace_city_fates(true);
        PopulatedWorld populated=populate_world(world,catalogues);
        std::int64_t last_age=2;
        for(int index=1;index<argc;++index)
            if(std::string(argv[index])=="ages=1") last_age=1;
        std::vector<Ruin> ruins;
        std::vector<War> wars;
        for(std::int64_t age=1;age<=last_age;++age) {
            AgeResult transition;
            populated=advance_age(world,catalogues,populated,age,transition);
            ruins.insert(ruins.end(),transition.ruins.begin(),transition.ruins.end());
            wars.insert(wars.end(),transition.wars.begin(),transition.wars.end());
        }
        for(const FoundedCity& city:populated.founding.sites)
            std::printf("CITY\t%s\t%zu\t%s\t%lld\t%.17g\t%s\n",city.uid.c_str(),city.node,
                city.population_profile.c_str(),static_cast<long long>(city.founded_age),
                city.founding_year,city.name.c_str());
        for(const Ruin& ruin:ruins)
            std::printf("RUIN\t%s\t%zu\t%s\t%lld\t%.17g\t%.17g\t%s\t%.17g\t%s\n",ruin.id.c_str(),ruin.node,
                ruin.cause.c_str(),static_cast<long long>(ruin.destroyed_age),ruin.probability,ruin.roll,
                ruin.new_node_school.c_str(),ruin.legacy_intensity,ruin.legacy_basis.c_str());
        for(const War& war:wars)
            std::printf("WAR\t%s\t%s\t%s\t%s\t%lld\t%.17g\t%.17g\t%.17g\n",war.id.c_str(),
                war.kind.c_str(),war.victor_uid.c_str(),war.defeated_uid.c_str(),
                static_cast<long long>(war.age),war.pressure,war.chance,war.roll);
        // Every surviving city's own record, so a victor's history is compared too.
        for(const FoundedCity& city:populated.founding.sites)
            for(const WarParticipation& record:city.war_history)
                std::printf("VETERAN\t%s\t%s\t%s\t%s\n",city.uid.c_str(),record.war_id.c_str(),
                    record.outcome.c_str(),record.opponent_uid.c_str());
        std::printf("COUNTS\t%zu\t%zu\t%zu\t%zu\t%zu\t%zu\n",populated.founding.sites.size(),
            ruins.size(),populated.roads.size(),populated.humans.hamlets.size(),
            populated.society.ports.size(),populated.nests.monsters.sites.size());
        for(std::size_t index=0;index<school_count;++index)
            emit_grid(std::string("ley_")+school_names()[index],world.layers.ley[index]);
        emit_grid("magic_hazard",world.layers.magic_hazard);
        emit_grid("dominant_magic",world.layers.dominant_magic);
        emit_grid("biome",world.layers.biome);
        return 0;
    }
    if(operation=="scenebuildings") {
        // The drawn world: every city, hamlet and castle packed in local metres and
        // every plot emitted as a dimensioned, rotated, ground-anchored footprint.
        //
        // The reference plans these once, at its LAST stage, after both age
        // transitions, so this runs the ages first by default; `ages=0` plans the
        // world as the civilization round leaves it, and `show=<n>` prints that many
        // records instead of the default three.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        std::int64_t last_age=2,show=3;
        for(int index=1;index<argc;++index) {
            const std::string argument=argv[index];
            if(argument.rfind("ages=",0)==0) last_age=std::stoll(argument.substr(5));
            if(argument.rfind("show=",0)==0) show=std::stoll(argument.substr(5));
        }
        WorldEnvelope world=generate_world(request);
        PopulatedWorld populated=populate_world(world,catalogues);
        for(std::int64_t age=1;age<=last_age;++age) {
            AgeResult transition;
            populated=advance_age(world,catalogues,populated,age,transition);
        }
        const double started=std::chrono::duration<double>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        plan_settlement_buildings(world,catalogues,populated);
        const double elapsed=std::chrono::duration<double>(
            std::chrono::steady_clock::now().time_since_epoch()).count()-started;
        const std::vector<SceneBuilding>& buildings=populated.scene.buildings;
        std::printf("STATUS\t%s\n",populated.scene.buildings_status.empty()
            ? "ok" : populated.scene.buildings_status.c_str());
        std::map<std::string,std::size_t> by_kind,by_settlement;
        std::set<std::string> assets;
        for(const SceneBuilding& building:buildings) {
            ++by_kind[building.settlement_kind];
            ++by_settlement[building.settlement_id];
            assets.insert(building.asset_id);
        }
        std::printf("COUNTS\tbuildings=%zu\tcities=%zu\thamlets=%zu\tfortresses=%zu\tsettlements=%zu\tassets=%zu\n",
            buildings.size(),populated.founding.sites.size(),populated.humans.hamlets.size(),
            populated.humans.fortresses.size(),by_settlement.size(),assets.size());
        for(const auto& entry:by_kind) std::printf("KIND\t%s\t%zu\n",entry.first.c_str(),entry.second);
        std::printf("PLAN_SECONDS\t%.3f\n",elapsed);
        // Properties worth checking on every building rather than eyeballing one: the
        // footprint really is the authored rectangle, the two axes really are a unit
        // right angle before and after the unwrap, and the centre stands on the ground
        // the terrain sampler reports. That last one is a MEASUREMENT, not a tolerance:
        // a planner stands a plot on the highest cell of its own footprint, so a
        // building on a slope sits above the sample taken at its centre, on purpose.
        // A mirror of the plugin's UnwrapPosition and UnwrapAxis. Unreal has no place in
        // this driver, so the arithmetic is repeated here rather than linked; if the two
        // ever disagree the plugin is the one that ships.
        const std::int64_t rows=129;
        const double span=static_cast<double>(rows-1);
        const double columns=2*span+1;
        const double spacing=pi*world.effective.globe_radius*centimetres_per_metre/span;
        const auto unwrap=[&](const Vec3& direction,double height_m) {
            const GlobeCoordinates place=unwrap_coordinates(direction);
            const double column=(place.longitude_degrees+180.)/360.*(columns-1);
            const double row=(90.-place.latitude_degrees)/180.*span;
            return Vec3{(column-(columns-1)/2.)*spacing,(span-row-span/2.)*spacing,
                        height_m*centimetres_per_metre};
        };
        const auto unwrap_axis=[&](const Vec3& direction,const Vec3& axis) {
            const GlobeCoordinates place=unwrap_coordinates(direction);
            const TangentFrame ground=tangent_frame(std::max(-90.,std::min(90.,place.latitude_degrees)),
                                                    std::max(-180.,std::min(180.,place.longitude_degrees)));
            return Vec3{dot(axis,ground.east),dot(axis,ground.north),0.};
        };
        double worst_footprint=0.,worst_height=0.,worst_axis=0.,worst_flat=0.,below=0.;
        std::size_t raised=0;
        for(const SceneBuilding& b:buildings) {
            const auto edge=[&](const Vec3& p,const Vec3& q) {
                return std::sqrt(std::pow(p[0]-q[0],2)+std::pow(p[1]-q[1],2)+std::pow(p[2]-q[2],2));
            };
            worst_footprint=std::max(worst_footprint,std::fabs(edge(b.footprint_m[0],b.footprint_m[1])-b.width_m));
            worst_footprint=std::max(worst_footprint,std::fabs(edge(b.footprint_m[1],b.footprint_m[2])-b.depth_m));
            worst_footprint=std::max(worst_footprint,std::fabs(edge(b.footprint_m[2],b.footprint_m[3])-b.width_m));
            const double length=std::sqrt(dot(b.position_m,b.position_m));
            const Vec3 direction{b.position_m[0]/length,b.position_m[1]/length,b.position_m[2]/length};
            const double above=length-world.effective.globe_radius-sample_height(world,direction);
            worst_height=std::max(worst_height,above);
            below=std::min(below,above);
            if(above>1.) ++raised;
            worst_axis=std::max(worst_axis,std::fabs(std::sqrt(dot(b.width_axis,b.width_axis))-1));
            worst_axis=std::max(worst_axis,std::fabs(std::sqrt(dot(b.depth_axis,b.depth_axis))-1));
            worst_axis=std::max(worst_axis,std::fabs(dot(b.width_axis,b.depth_axis)));
            const Vec3 flat_width=unwrap_axis(direction,b.width_axis);
            const Vec3 flat_depth=unwrap_axis(direction,b.depth_axis);
            worst_flat=std::max(worst_flat,std::fabs(std::sqrt(dot(flat_width,flat_width))-1));
            worst_flat=std::max(worst_flat,std::fabs(std::sqrt(dot(flat_depth,flat_depth))-1));
            worst_flat=std::max(worst_flat,std::fabs(dot(flat_width,flat_depth)));
        }
        std::printf("CHECK\tfootprint_edge_vs_dimension_m=%.3g\taxis_unit_and_square=%.3g"
                    "\tunwrap_axis_unit_and_square=%.3g\n",worst_footprint,worst_axis,worst_flat);
        std::printf("GROUND\tabove_centre_sample_m_max=%.3g\tbelow_centre_sample_m_min=%.3g"
                    "\tover_one_metre=%zu\n",worst_height,below,raised);
        for(std::size_t index=0;index<buildings.size()&&index<static_cast<std::size_t>(show);++index) {
            const SceneBuilding& b=buildings[index];
            std::printf("BUILDING\t%s\t%s\t%s\t%s\n",b.id.c_str(),b.settlement_kind.c_str(),
                b.settlement_id.c_str(),b.asset_id.c_str());
            std::printf("\tposition_m\t%.17g\t%.17g\t%.17g\n",b.position_m[0],b.position_m[1],b.position_m[2]);
            std::printf("\tdimensions_m\t%.17g\t%.17g\t%.17g\trotation\t%.17g\n",
                b.width_m,b.depth_m,b.height_m,b.rotation_degrees);
            std::printf("\twidth_axis\t%.17g\t%.17g\t%.17g\n",b.width_axis[0],b.width_axis[1],b.width_axis[2]);
            std::printf("\tdepth_axis\t%.17g\t%.17g\t%.17g\n",b.depth_axis[0],b.depth_axis[1],b.depth_axis[2]);
            std::printf("\tup\t%.17g\t%.17g\t%.17g\n",b.up[0],b.up[1],b.up[2]);
            for(const Vec3& corner:b.footprint_m)
                std::printf("\tcorner\t%.17g\t%.17g\t%.17g\n",corner[0],corner[1],corner[2]);
            // What the plugin hands a consumer for this same building, at 129 rows.
            const double length=std::sqrt(dot(b.position_m,b.position_m));
            const Vec3 direction{b.position_m[0]/length,b.position_m[1]/length,b.position_m[2]/length};
            const Vec3 place=unwrap(direction,length-world.effective.globe_radius);
            const Vec3 flat_width=unwrap_axis(direction,b.width_axis);
            const Vec3 flat_depth=unwrap_axis(direction,b.depth_axis);
            std::printf("\tunwrap_cm\t%.17g\t%.17g\t%.17g\n",place[0],place[1],place[2]);
            std::printf("\tunwrap_width_axis\t%.17g\t%.17g\t%.17g\n",flat_width[0],flat_width[1],flat_width[2]);
            std::printf("\tunwrap_depth_axis\t%.17g\t%.17g\t%.17g\n",flat_depth[0],flat_depth[1],flat_depth[2]);
        }
        return 0;
    }
    if(operation=="bench") {
        // Generate cost only: no printing of fields, because formatting a hundred
        // thousand doubles is not what a game pays for.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const auto catalogue_start=std::chrono::steady_clock::now();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        const auto terrain_start=std::chrono::steady_clock::now();
        WorldEnvelope world=generate_world(request);
        const auto placement_start=std::chrono::steady_clock::now();
        // One placement round, broken down, so the cost of a populated world can be
        // attributed rather than guessed at. Off by default: it repeats the round, so
        // leaving it on would make the total it is meant to explain untrue.
        bool breakdown=false;
        for(int index=1;index<argc;++index)
            if(std::string(argv[index])=="breakdown=1") breakdown=true;
        auto mark=std::chrono::steady_clock::now();
        if(breakdown) {
        auto since=[&mark]() {
            const auto now=std::chrono::steady_clock::now();
            const double ms=std::chrono::duration<double,std::milli>(now-mark).count();
            mark=now;
            return ms;
        };
        const SettlementFields step_fields=evaluate_settlement_fields(world.config,
            world.effective.globe_radius,world.grid,catalogues,world.layers);
        const double fields_ms=since();
        const std::uint32_t step_seed=child_seed(static_cast<std::uint64_t>(world.config.seed),"settlements");
        const FoundingResult step_founding=found_cities(step_seed,world.config,
            world.effective.globe_radius,world.grid,catalogues,step_fields);
        const double founding_ms=since();
        const std::vector<Road> step_roads=build_roads(world.config,world.grid,catalogues,world.layers,
                                                       step_founding.sites);
        const double roads_ms=since();
        const std::vector<PopulationEstimate> step_residents=estimate_population(step_fields.budget,
                                                                                step_founding.sites);
        const std::vector<CityPlan> step_plans=plan_cities(world.config,world.grid,catalogues,world.layers,
                                                           step_fields,step_founding.sites,step_residents);
        const double plans_ms=since();
        const Humans step_humans=add_humans(world.config,world.effective.globe_radius,world.grid,catalogues,
                                            world.layers,step_founding.sites,step_residents,step_roads,
                                            biome_variants(world.layers,world.grid));
        const double humans_ms=since();
        const Society step_society=add_world_society(world.config,world.effective.globe_radius,world.grid,
                                                     catalogues,world.layers,world.regions,
                                                     step_founding.sites,step_humans);
        const double society_ms=since();
        const Habitats step_nests=add_nests(world.config,world.effective.globe_radius,world.grid,catalogues,
                                              world.layers,step_founding.sites,step_humans,step_society);
        const double nests_ms=since();
        std::printf("placement fields %.0f founding %.0f roads %.0f plans %.0f humans %.0f society %.0f nests %.0f "
            "(cities %zu plans %zu)\n",fields_ms,founding_ms,roads_ms,plans_ms,humans_ms,society_ms,nests_ms,
            step_founding.sites.size(),step_plans.size());
        (void)step_nests;
        }
        PopulatedWorld populated=populate_world(world,catalogues);
        const auto ages_start=std::chrono::steady_clock::now();
        for(std::int64_t age=1;age<=2;++age) {
            AgeResult transition;
            populated=advance_age(world,catalogues,populated,age,transition);
        }
        const auto done=std::chrono::steady_clock::now();
        auto ms=[](auto a,auto b) {
            return std::chrono::duration<double,std::milli>(b-a).count();
        };
        std::printf("catalogue_ms %.1f terrain_ms %.1f placement_ms %.1f ages_ms %.1f total_ms %.1f\n",
            ms(catalogue_start,terrain_start),ms(terrain_start,placement_start),
            ms(placement_start,ages_start),ms(ages_start,done),ms(catalogue_start,done));
        std::printf("cities %zu ruins %zu hamlets %zu ports %zu nests %zu\n",
            populated.founding.sites.size(),populated.ruins.size(),populated.humans.hamlets.size(),
            populated.society.ports.size(),populated.nests.monsters.sites.size());
        return 0;
    }
    if(operation=="biomesamples") {
        // Natural biome identity at each requested latitude and longitude, through the
        // same continuous surface sample a consumer paints with.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        const WorldEnvelope world=generate_world(request);
        double latitude,longitude;
        while(std::cin>>latitude>>longitude)
            std::printf("%lld\n",static_cast<long long>(
                sample_surface(world,globe_direction(latitude,longitude)).natural_biome));
        return 0;
    }
    if(operation=="relief") {
        // Is this terrain actually hilly? Reports the vertical scale the recipe gives
        // at this world size, and what a walker would feel over short distances.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        const WorldEnvelope world=generate_world(request);
        const double sea=world.effective.sea_level;
        std::printf("radius_m %.1f sea_level_m %.2f amplitude_m %.2f tectonic_relief_m %.2f extent_m %.1f\n",
            world.effective.globe_radius,sea,world.effective.amplitude,world.effective.tectonic_relief,
            world.effective.extent);
        std::vector<double> land,slopes,ocean;
        for(std::size_t i=0;i<world.grid.points.size();++i) {
            const auto x=static_cast<std::size_t>(world.grid.points[i].first);
            const auto z=static_cast<std::size_t>(world.grid.points[i].second);
            if(world.layers.water_type[z][x]!=0.) {
                ocean.push_back(sea-world.layers.height[z][x]);
                continue;
            }
            land.push_back(world.layers.height[z][x]-sea);
            slopes.push_back(world.layers.slope[z][x]);
        }
        std::sort(land.begin(),land.end());
        std::sort(slopes.begin(),slopes.end());
        std::sort(ocean.begin(),ocean.end());
        auto at=[](const std::vector<double>& v,double q) {
            return v.empty() ? 0. : v[static_cast<std::size_t>(q*static_cast<double>(v.size()-1))];
        };
        std::printf("land_nodes %zu height_m p05 %.1f p50 %.1f p95 %.1f max %.1f\n",land.size(),
            at(land,.05),at(land,.5),at(land,.95),land.empty() ? 0. : land.back());
        std::printf("slope_deg p50 %.2f p95 %.2f max %.2f\n",at(slopes,.5),at(slopes,.95),
            slopes.empty() ? 0. : slopes.back());
        const double peak=land.empty() ? 0. : land.back();
        const double deepest=ocean.empty() ? 0. : ocean.back();
        std::printf("ocean_depth_m p50 %.1f p95 %.1f max %.1f peak_over_depth %.3f\n",
            at(ocean,.5),at(ocean,.95),deepest,deepest>0 ? peak/deepest : 0.);
        // What a walker meets: height along short transects on land, sampled at the
        // stride of a person rather than at the raster.
        double worst_rise=0.,worst_step=0.;
        Sum total_rise;
        std::int64_t transects=0;
        for(std::size_t i=0;i<world.grid.points.size();i+=7) {
            const auto x=static_cast<std::size_t>(world.grid.points[i].first);
            const auto z=static_cast<std::size_t>(world.grid.points[i].second);
            if(world.layers.water_type[z][x]!=0.) continue;
            const Vec3 start=direction(world.grid.points[i].first,world.grid.points[i].second,world.size);
            const TangentFrame frame=tangent_frame(
                std::asin(std::max(-1.,std::min(1.,start[1])))*(180.0/pi),
                std::atan2(start[2],start[0])*(180.0/pi));
            double previous=sample_height(world,start),lowest=previous,highest=previous;
            for(int step=1;step<=100;++step) {
                // One metre east per step, on the sphere.
                const double offset=static_cast<double>(step);
                Vec3 p{start[0]+frame.east[0]*offset/world.effective.globe_radius,
                       start[1]+frame.east[1]*offset/world.effective.globe_radius,
                       start[2]+frame.east[2]*offset/world.effective.globe_radius};
                const Vec3 q=unit(p);
                const double h=sample_height(world,q);
                worst_step=std::max(worst_step,std::fabs(h-previous));
                previous=h;
                lowest=std::min(lowest,h);highest=std::max(highest,h);
            }
            worst_rise=std::max(worst_rise,highest-lowest);
            total_rise.add(highest-lowest);
            ++transects;
        }
        std::printf("transects %lld over_100m mean_relief_m %.2f worst_relief_m %.2f worst_metre_step_m %.3f\n",
            static_cast<long long>(transects),
            transects ? total_rise.value()/static_cast<double>(transects) : 0.,worst_rise,worst_step);
        return 0;
    }
    if(operation=="regions") {
        // Are the mountains a place, or scattered cells? Reports the area each natural
        // biome covers, how that area breaks into connected regions, and how much of
        // it a magical school has claimed.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        const WorldEnvelope world=generate_world(request);
        const std::size_t count=world.grid.points.size();
        const std::vector<double> biome=node_values(world.layers.natural_biome,world.grid);
        const std::vector<double> landform=node_values(world.layers.landform,world.grid);
        const std::vector<std::string> variants=biome_variants(world.layers,world.grid);
        std::printf("world radius_m %.1f circumference_km %.2f cell_m %.1f\n",
            world.effective.globe_radius,2*pi*world.effective.globe_radius/1000.,
            pi*world.effective.globe_radius/static_cast<double>(world.size-1));
        // Connected regions of one label, over the grid's own neighbours.
        auto regions=[&](const std::vector<bool>& member) {
            std::vector<double> areas;
            std::vector<bool> seen(count,false);
            for(std::size_t start=0;start<count;++start) {
                if(!member[start] || seen[start]) continue;
                std::vector<std::size_t> stack{start};
                seen[start]=true;
                Sum area;
                while(!stack.empty()) {
                    const std::size_t node=stack.back();stack.pop_back();
                    area.add(world.grid.areas[node]);
                    for(const auto& edge:world.grid.neighbors[node]) {
                        const auto j=static_cast<std::size_t>(edge.first);
                        if(member[j] && !seen[j]) {seen[j]=true;stack.push_back(j);}
                    }
                }
                areas.push_back(area.value()/1e6);
            }
            std::sort(areas.begin(),areas.end(),std::greater<double>());
            return areas;
        };
        auto report=[&](const std::string& label,const std::vector<bool>& member) {
            Sum total;
            std::size_t cells=0,mutated=0;
            for(std::size_t i=0;i<count;++i) {
                if(!member[i]) continue;
                total.add(world.grid.areas[i]);
                ++cells;
                if(!variants[i].empty()) ++mutated;
            }
            const std::vector<double> areas=regions(member);
            std::printf("%-16s cells %5zu area_km2 %8.2f regions %3zu largest_km2 %8.2f "
                "second_km2 %8.2f mutated_cells %zu\n",label.c_str(),cells,total.value()/1e6,
                areas.size(),areas.empty() ? 0. : areas[0],areas.size()>1 ? areas[1] : 0.,mutated);
        };
        std::vector<bool> rock(count,false),mountain(count,false),highland(count,false);
        const double sea=world.effective.sea_level;
        for(std::size_t i=0;i<count;++i) {
            const auto x=static_cast<std::size_t>(world.grid.points[i].first);
            const auto z=static_cast<std::size_t>(world.grid.points[i].second);
            if(world.layers.water_type[z][x]!=0.) continue;
            rock[i]=biome[i]==5.;
            mountain[i]=landform[i]==2.;
            highland[i]=world.layers.height[z][x]-sea>=world.effective.tectonic_relief*.5;
        }
        report("exposed_rock",rock);
        report("landform_mountain",mountain);
        report("highland",highland);
        // Every natural biome's footprint, so a mountain can be compared with a forest.
        std::map<std::int64_t,std::pair<double,std::size_t>> footprint;
        for(std::size_t i=0;i<count;++i) {
            auto& entry=footprint[static_cast<std::int64_t>(biome[i])];
            entry.first+=world.grid.areas[i]/1e6;
            entry.second+=1;
        }
        for(const auto& entry:footprint)
            std::printf("biome %3lld area_km2 %8.2f cells %5zu\n",
                static_cast<long long>(entry.first),entry.second.first,entry.second.second);
        return 0;
    }
    if(operation=="budget") {
        // What the world could support, before any ceiling is applied.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        std::ifstream file(argv[4],std::ios::binary);
        if(!file) return 2;
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Catalogues catalogues=Catalogues::parse(buffer.str());
        WorldEnvelope world=generate_world(request);
        const SettlementFields fields=evaluate_settlement_fields(world.config,world.effective.globe_radius,
                                                                 world.grid,catalogues,world.layers);
        std::int64_t unclamped=0,granted=0;
        for(const std::string& id:catalogues.civilization_ids()) {
            const Profile& profile=catalogues.profile(id);
            const double weighted=fields.budget.weighted_habitat_km2.at(id);
            const std::int64_t minimum=static_cast<std::int64_t>(profile.trait("minimum_founding_residents"));
            const std::int64_t by_land=static_cast<std::int64_t>(std::floor(weighted/profile.trait("land_per_city_km2")));
            const std::int64_t by_food=minimum>0 ? fields.budget.allowances.at(id)/minimum : 0;
            const std::int64_t want=std::min(by_land,by_food);
            unclamped+=want;
            granted+=fields.budget.quotas.at(id);
            std::printf("%-22s habitat_km2 %9.2f allowance %7lld by_land %4lld by_food %4lld want %4lld granted %4lld\n",
                id.c_str(),weighted,static_cast<long long>(fields.budget.allowances.at(id)),
                static_cast<long long>(by_land),static_cast<long long>(by_food),
                static_cast<long long>(want),static_cast<long long>(fields.budget.quotas.at(id)));
        }
        // How many cities the ground can actually hold at the required spacing, by
        // densest packing of the minimum separation over habitable land.
        std::set<std::size_t> habitable;
        for(const std::string& id:catalogues.civilization_ids())
            for(std::size_t node:fields.species.at(id).candidates) habitable.insert(node);
        Sum area;
        for(std::size_t node:habitable) area.add(world.grid.areas[node]);
        const double habitable_km2=area.value()/1e6;
        const double per_city_km2=std::sqrt(3.)/2*std::pow(world.config.settlement_spacing/1000.,2.);
        std::printf("world_cap %lld unclamped_cities %lld granted_cities %lld habitable_km2 %.2f "
            "spacing_m %.0f packing_limit %lld\n",
            static_cast<long long>(fields.budget.world_cap),static_cast<long long>(unclamped),
            static_cast<long long>(granted),habitable_km2,world.config.settlement_spacing,
            static_cast<long long>(std::floor(habitable_km2/per_city_km2)));
        return 0;
    }
    if(operation=="stage9") {
        // Magic and ecology as they stand before the age transitions. The reference
        // rescales every ley intensity twice during ages one and two, so these are
        // inputs to the civilization stages, not the world's final magic fields.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        const WorldEnvelope world=generate_world(request);
        const Layers& l=world.layers;
        for(std::size_t index=0;index<school_count;++index) {
            emit_grid(std::string("ley_")+school_names()[index],l.ley[index]);
            emit_grid(std::string("instability_")+school_names()[index],l.instability[index]);
        }
        for(std::size_t index=0;index<zone_count;++index)
            emit_grid(std::string("zone_")+zone_names()[index],l.zone[index]);
        const std::map<std::string,const Grid*> derived{
            {"magic_density",&l.magic_density},{"magic_hazard",&l.magic_hazard},{"magic_growth",&l.magic_growth},
            {"magic_opposition",&l.magic_opposition},{"dominant_magic",&l.dominant_magic},
            {"ley_holy",&l.ley_holy},{"ley_primordial",&l.ley_primordial},
            {"metal_richness",&l.metal_richness},{"coastal_exposure",&l.coastal_exposure},
            {"harbor_suitability",&l.harbor_suitability},{"fishing_productivity",&l.fishing_productivity},
            {"reef",&l.reef},{"lagoon",&l.lagoon},{"estuary",&l.estuary},{"sheltered_bay",&l.sheltered_bay},
            {"rocky_coast",&l.rocky_coast},{"kelp",&l.kelp},{"fjord",&l.fjord},{"open_ocean",&l.open_ocean},
            {"maritime",&l.maritime},{"boreal",&l.boreal},{"tundra",&l.tundra},{"ice_cap",&l.ice_cap},
            {"coastal_support",&l.coastal_support},{"island_habitat",&l.island_habitat},
            {"lunar_sensitivity",&l.lunar_sensitivity}};
        for(const auto& entry:derived) if(!entry.second->empty()) emit_grid(entry.first,*entry.second);
        return 0;
    }
    if(operation=="noisecell") {
        WorldConfig cfg;
        cfg.seed=std::stoll(argv[2]);cfg.size=std::stoll(argv[3]);
        const long long z=std::stoll(argv[4]),x=std::stoll(argv[5]);
        const double r=cfg.globe_radius,step=2*pi*r/static_cast<double>(cfg.size-1);
        const std::uint32_t detail=child_seed(static_cast<std::uint64_t>(cfg.seed),"surface",0);
        const Vec3 p=direction(x,z,cfg.size);
        double value=0.;
        for(long long k=0;k<cfg.octaves;++k) {
            const double f=std::pow(2.,static_cast<double>(k))/cfg.wavelength;
            if(!(cfg.wavelength/std::pow(2.,static_cast<double>(k))>=2*step)) continue;
            const double noise=std::max(-1.,std::min(1.,perlin3(p[0]*r*f+.173,p[1]*r*f+.391,p[2]*r*f+.719,
                static_cast<std::int64_t>(detail)+k*1013)));
            emit(noise);
            value+=cfg.amplitude*std::pow(.5,static_cast<double>(k))*((1-cfg.ridge)*noise+cfg.ridge*(std::pow(1-std::fabs(noise),3.)-.5));
        }
        emit(step);emit(value);
        return 0;
    }
    if(operation=="hypot") {
        double x,y;
        while(std::cin>>x>>y) emit(python_hypot(x,y));
        return 0;
    }
    if(operation=="dot3") {
        double x,y,z;
        while(std::cin>>x>>y>>z) {emit(x);emit(y);emit(z);const double d=dot(Vec3{x,y,z},Vec3{x,y,z});emit(d);emit(std::sqrt(d));}
        return 0;
    }
    if(operation=="magic") {
        WorldConfig cfg;
        cfg.seed=std::stoll(argv[2]);cfg.size=std::stoll(argv[3]);
        const double radius=cfg.globe_radius*cfg.world_scale;
        const SphereGrid grid=sphere_grid(cfg.size,radius);
        const std::vector<LeyNetwork> networks=generate_networks(cfg);
        Layers layers;
        evaluate_networks(cfg,radius,grid,networks,layers);
        for(std::size_t index=0;index<school_count;++index) {
            const std::string name=school_names()[index];
            emit_grid("nodes_"+name,Grid{});
            for(const LeyNode& node:networks[index].nodes) {
                emit(node.direction[0]);emit(node.direction[1]);emit(node.direction[2]);emit(node.intensity);
            }
            emit_grid("edges_"+name,Grid{});
            for(const LeyEdge& edge:networks[index].edges) {
                emit(static_cast<double>(edge.from));emit(static_cast<double>(edge.to));emit(edge.intensity);
            }
            emit_grid("ley_"+name,layers.ley[index]);
            emit_grid("instability_"+name,layers.instability[index]);
        }
        emit_grid("magic_density",layers.magic_density);
        emit_grid("magic_hazard",layers.magic_hazard);
        emit_grid("magic_growth",layers.magic_growth);
        emit_grid("magic_opposition",layers.magic_opposition);
        emit_grid("dominant_magic",layers.dominant_magic);
        emit_grid("ley_holy",layers.ley_holy);
        emit_grid("ley_primordial",layers.ley_primordial);
        return 0;
    }
    if(operation=="networks") {
        // The resolved ley network parameters, with no world built at all. Cheap on
        // purpose: `resolve_config` plus `generate_networks` is milliseconds, where
        // `stage9` is a whole world, so a parity suite can pin these numbers without
        // paying for a raster.
        //
        // `width_m` is the reason this operation exists. It is authored as an absolute
        // reach on the 11.15 km reference world and has to be scaled by the world's own
        // circumference (Core/magic.cpp, mirroring terrain_leyline_history.py:101). Left
        // unscaled it was a flat 110 m against a kilometres-wide cell, which is a
        // divergence with no visible edge: every ley field, every instability field and
        // every categorical layer downstream of them collapses, and the failure surfaces
        // as fifty-five mismatched grids rather than as one wrong number. One tagged row
        // per school turns that back into one wrong number.
        GenerateRequest request;
        request.seed=std::stoll(argv[2]);
        request.size=std::stoll(argv[3]);
        apply_scale(request,argc,argv);
        const WorldConfig cfg=resolve_config(request);
        for(const LeyNetwork& network:generate_networks(cfg)) {
            std::printf("NETWORK\t%s\t%.17g\t%.17g\t%.17g\t%lld\t%d\n",network.name.c_str(),
                network.width_m,network.strength,network.instability,
                static_cast<long long>(network.nodes.size()),network.enabled ? 1 : 0);
        }
        return 0;
    }
    if(operation=="selection") {
        // seed count: prints getrandbits(k), randbelow, randint, choice draws.
        PyRandom rng(std::stoull(argv[2]));
        const int count=std::stoi(argv[3]);
        for(int i=0;i<count;++i) {
            emit(static_cast<double>(rng.getrandbits(1+(i%17))));
            emit(static_cast<double>(rng.randbelow(3+static_cast<std::uint64_t>(i%29))));
            emit(static_cast<double>(rng.randint(1,4+(i%7))));
            emit(static_cast<double>(rng.choice(2+static_cast<std::size_t>(i%11))));
        }
        return 0;
    }
    if(operation=="child_seed") {
        std::printf("%u\n",child_seed(std::stoull(argv[2]),argv[3],std::stoull(argv[4])));
        return 0;
    }
    if(operation=="direction") {
        const long long n=std::stoll(argv[2]);
        for(long long z=0;z<n;++z) for(long long x=0;x<n;++x) {
            const Vec3 p=direction(x,z,n);emit(p[0]);emit(p[1]);emit(p[2]);
        }
        return 0;
    }
    if(operation=="tectonics") {
        WorldConfig cfg;
        cfg.seed=std::stoll(argv[2]);cfg.size=std::stoll(argv[3]);cfg.phase=std::stoll(argv[4]);
        const SphereGrid grid=sphere_grid(cfg.size,cfg.globe_radius);
        Layers layers;
        const TectonicResult result=generate_tectonics(cfg,grid,layers);
        std::printf("#plate_count\n%zu\n",result.plates.size());
        for(const auto& plate:result.plates) {
            emit(plate.center[0]);emit(plate.center[1]);emit(plate.center[2]);
            emit(plate.omega[0]);emit(plate.omega[1]);emit(plate.omega[2]);
        }
        const std::map<std::string,const Grid*> named{
            {"plates",&layers.plates},{"crust",&layers.crust},{"boundary_distance",&layers.boundary_distance},
            {"convergence",&layers.convergence},{"divergence",&layers.divergence},{"shear",&layers.shear},
            {"structure",&layers.structure},{"interaction",&layers.interaction},{"volcanic",&layers.volcanic},
            {"continental",&layers.continental},{"archipelago_relief",&layers.archipelago_relief},
            {"noise",&layers.noise},{"surface",&layers.surface},{"base",&layers.base},{"height",&layers.height},
            {"erosion",&layers.erosion},{"deposition",&layers.deposition},{"erosion_delta",&layers.erosion_delta},
            {"catchment",&layers.catchment},{"slope",&layers.slope},{"tpi",&layers.tpi}};
        for(const auto& entry:named) if(!entry.second->empty()) emit_grid(entry.first,*entry.second);
        return 0;
    }
    return 2;
}
