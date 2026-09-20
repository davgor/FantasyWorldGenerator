#include "scene.hpp"
#include "castleplanner.hpp"
#include "cityplanner.hpp"
#include "hamletplanner.hpp"
#include "hydrology.hpp"
#include "pyrandom.hpp"
#include "scenebuildings.hpp"
#include "sceneframe.hpp"
#include "settlementpresets.hpp"
#include <cmath>
#include <exception>
#include <map>
#include <tuple>
#include <type_traits>
namespace fantasy_world_generator {
namespace {
Vec3 normalized(const Vec3& v) {
    Sum squares;
    for(double value:v) squares.add(value*value);
    const double length=std::sqrt(squares.value());
    return Vec3{v[0]/length,v[1]/length,v[2]/length};
}
// Radial position of a direction on the sampled surface, in globe-centred metres.
Vec3 surface_position(const WorldEnvelope& world,const Vec3& direction) {
    const double distance=world.effective.globe_radius+sample_height(world,direction);
    return Vec3{distance*direction[0],distance*direction[1],distance*direction[2]};
}
}
WorldScene build_scene(const WorldEnvelope& world,const std::vector<FoundedCity>& sites,
                       const std::vector<Road>& roads,const SettlementFields& fields) {
    WorldScene scene;
    scene.radius_m=world.effective.globe_radius;
    for(std::size_t index=0;index<roads.size();++index) {
        const Road& road=roads[index];
        std::vector<Vec3> vectors;
        vectors.reserve(road.nodes.size());
        for(std::size_t node:road.nodes) {
            const auto& point=world.grid.points[node];
            vectors.push_back(direction(point.first,point.second,world.size));
        }
        // Densify onto the same surface; the route topology is unchanged, only its
        // resolution, so a polyline cannot drift off the terrain between two nodes.
        std::vector<Vec3> dense;
        for(std::size_t k=0;k+1<vectors.size();++k) {
            const Vec3& p=vectors[k];
            const Vec3& q=vectors[k+1];
            const double arc=scene.radius_m*std::acos(std::max(-1.,std::min(1.,dot(p,q))));
            const auto steps=static_cast<std::int64_t>(std::max(1.,std::ceil(arc/4)));
            for(std::int64_t step=0;step<steps;++step) {
                Vec3 between{};
                for(int axis=0;axis<3;++axis)
                    between[axis]=p[axis]+(q[axis]-p[axis])*static_cast<double>(step)/static_cast<double>(steps);
                dense.push_back(normalized(between));
            }
        }
        if(!vectors.empty()) dense.push_back(vectors.back());
        RegionalRoad emitted;
        emitted.id="regional-road-"+std::to_string(index);
        emitted.route_index=index;
        emitted.bridge_candidates=road.river_crossings;
        emitted.positions_m.reserve(dense.size());
        for(const Vec3& point:dense) emitted.positions_m.push_back(surface_position(world,point));
        scene.regional_roads.push_back(emitted);
    }
    for(std::size_t index=0;index<sites.size();++index) {
        const FoundedCity& site=sites[index];
        const auto& point=world.grid.points[site.node];
        CityAnchor anchor;
        anchor.id="city-"+std::to_string(index);
        anchor.population_profile=site.population_profile;
        // The anchor is the settlement's place on the map, not a structure: its
        // buildings each carry their own registry identity in scene.buildings.
        anchor.asset_id="marker.city_ruins";
        anchor.node=site.node;
        anchor.direction=direction(point.first,point.second,world.size);
        anchor.height_m=sample_height(world,anchor.direction);
        anchor.position_m=surface_position(world,anchor.direction);
        anchor.suitability=fields.species.at(site.population_profile).suitability[site.node];
        anchor.founding_capital=site.founding_capital;
        scene.cities.push_back(anchor);
    }
    return scene;
}
namespace {
// The reference's own city names, in its order: a city is named by its index in the
// founding order, so the list and the modulo are part of the world, not decoration.
const char* const city_names[]={"Alder","Bracken","Cedar","Dunlin","Ember","Fern","Glen","Hazel","Ivy",
    "Juniper","Kestrel","Larch","Mallow","Nettle","Oak","Pine","Quartz","Reed","Sage","Thistle","Umber",
    "Vale","Willow","Yarrow"};
constexpr std::size_t city_name_count=sizeof(city_names)/sizeof(city_names[0]);
}
PopulatedWorld populate_world(WorldEnvelope& world,const Catalogues& catalogues,
                              const PopulateContext& context) {
    PopulatedWorld populated;
    populated.fields=evaluate_settlement_fields(world.config,world.effective.globe_radius,world.grid,
                                                catalogues,world.layers);
    const std::uint32_t seed=child_seed(static_cast<std::uint64_t>(world.config.seed),"settlements");
    FoundingContext founding_context;
    founding_context.survivors=context.survivors;
    founding_context.forbidden=context.forbidden;
    founding_context.bonus_used=context.bonus_used;
    founding_context.used_civilizations=context.used_civilizations;
    founding_context.start_year=context.start_year;
    populated.founding=found_cities(seed,world.config,world.effective.globe_radius,world.grid,
                                    catalogues,populated.fields,founding_context);
    // Names follow the founding order, then a surviving city takes back the identity
    // it had before the age: same uid, same name, same founding age.
    for(std::size_t index=0;index<populated.founding.sites.size();++index) {
        FoundedCity& site=populated.founding.sites[index];
        site.name=std::string(city_names[index%city_name_count])+" City";
        for(const FoundedCity& old:context.survivors)
            if(old.node==site.node && old.population_profile==site.population_profile && !old.uid.empty()) {
                site.uid=old.uid;site.name=old.name;site.founded_age=old.founded_age;
                site.source_culture=old.source_culture;
                // The wars travel with the city: a survivor that rebuilds its hinterland
                // is still the city that fought, and its forts answer to that.
                site.war_history=old.war_history;
                break;
            }
    }
    populated.roads=build_roads(world.config,world.grid,catalogues,world.layers,populated.founding.sites);
    populated.scene=build_scene(world,populated.founding.sites,populated.roads,populated.fields);
    populated.residents=estimate_population(populated.fields.budget,populated.founding.sites);
    // The reference plans a city twice: once before its population is known and again
    // once the budget has credited it residents. Only the second plan is the world's.
    populated.plans=plan_cities(world.config,world.grid,catalogues,world.layers,populated.fields,
                                populated.founding.sites,populated.residents);
    populated.humans=add_humans(world.config,world.effective.globe_radius,world.grid,catalogues,
                                world.layers,populated.founding.sites,
                                populated.residents,populated.roads,biome_variants(world.layers,world.grid));
    populated.society=add_world_society(world.config,world.effective.globe_radius,world.grid,catalogues,
                                        world.layers,world.regions,populated.founding.sites,populated.humans);
    populated.nests=add_nests(world.config,world.effective.globe_radius,world.grid,catalogues,world.layers,
                              populated.founding.sites,populated.humans,populated.society);
    // A city founded in this age is named for it and takes its culture from the
    // hinterland that grew around it; one that was already here keeps what it had.
    for(std::size_t index=0;index<populated.founding.sites.size();++index) {
        FoundedCity& site=populated.founding.sites[index];
        if(site.uid.empty()) {
            if(context.age>0) site.name+=" (Age "+std::to_string(context.age)+")";
            site.uid="surface-city-"+std::to_string(context.age)+"-"+std::to_string(site.node)
                +"-"+site.population_profile;
            site.founded_age=context.age;
        }
        if(site.founded_age==context.age && index<populated.humans.cores.size())
            site.source_culture=populated.humans.cores[index].culture_id;
        if(site.source_culture.empty())
            site.source_culture=site.population_profile+"-founders-"+std::to_string(site.node);
    }
    return populated;
}

// ---------------------------------------------------------------------------
// The building slice: Core's populated world rendered into the envelope the four
// ported planner modules read, and their scene rendered back into plain structs.
//
// Those modules do not take a WorldEnvelope. Each declares the exact slice of the
// reference's world dict it reads, as insertion-ordered `settlementpresets::Value`
// trees for the parts that are Python dicts, because the int/float spelling and the
// key order of those parts are part of their byte-exact contract. Everything below
// is that translation and nothing more; no geometry is derived here.
// ---------------------------------------------------------------------------
namespace {
using settlementpresets::Value;
Value vint(std::int64_t value) {return Value::make_int(value);}
Value vflt(double value) {return Value::make_float(value);}
Value vstr(std::string value) {return Value::make_string(std::move(value));}
Value varr() {return Value::make_array();}
Value vobj() {return Value::make_object();}

double number_of(const Value& value) {
    if(value.kind==Value::Kind::Int) return value.whole_fits?static_cast<double>(value.whole):value.number;
    if(value.kind==Value::Kind::Float) return value.number;
    if(value.kind==Value::Kind::Bool) return value.boolean?1.:0.;
    return 0.;
}
// `str(value)` for the identities the scene keys records by: a uid is already a
// string, a plot id is `plot-3`, and an integer id spells itself.
std::string text_of(const Value& value) {
    switch(value.kind) {
        case Value::Kind::String: return value.text;
        case Value::Kind::Int: return value.whole_fits?std::to_string(value.whole):value.text;
        case Value::Kind::Float: return settlementpresets::py_repr(value.number);
        case Value::Kind::Bool: return value.boolean?"True":"False";
        default: return "None";
    }
}
Vec3 vector_of(const Value& value) {
    Vec3 out{};
    for(int axis=0;axis<3&&axis<static_cast<int>(value.items.size());++axis)
        out[axis]=number_of(value.items[static_cast<std::size_t>(axis)]);
    return out;
}
// A categorical raster whose cells reach a planner's report unchanged. scenebuildings
// is explicit about this one: `natural_biome` reaches a dict lookup and a serialized
// record, so a cell has to stay a Python int -- a float would print 5.0 where the
// reference prints 5, and every building record in the world would differ.
std::vector<std::vector<Value>> integer_rows(const Grid& grid) {
    std::vector<std::vector<Value>> rows;
    rows.reserve(grid.size());
    for(const std::vector<double>& row:grid) {
        std::vector<Value> cells;
        cells.reserve(row.size());
        for(double cell:row) cells.push_back(vint(static_cast<std::int64_t>(cell)));
        rows.push_back(std::move(cells));
    }
    return rows;
}

// `world['climate']['river_segments']`: one edge from each climate river node to the
// water receiver it drains into. terrain_climate.py:79 builds it from
// `world['water']['receivers']`, and Core's climate stage marks exactly the same nodes
// in layers.rain_river -- but the envelope keeps the flags and not the receivers.
// Routing is a pure function of the final height, which nothing after the second
// add_water touches, so it is re-run here over a scratch layer set that holds only the
// height rather than stored on every world that will never plan a city.
std::vector<std::pair<std::int64_t,std::int64_t>> river_segments(const WorldEnvelope& world) {
    std::vector<std::pair<std::int64_t,std::int64_t>> segments;
    if(world.layers.rain_river.empty()||world.layers.height.empty()) return segments;
    Layers scratch;
    scratch.height=world.layers.height;
    const WaterRouting routed=add_water(world.config,world.effective.sea_level,world.grid,scratch);
    const std::vector<double> rivers=node_values(world.layers.rain_river,world.grid);
    for(std::size_t i=0;i<rivers.size()&&i<routed.receivers.size();++i)
        if(rivers[i]!=0.) segments.emplace_back(static_cast<std::int64_t>(i),routed.receivers[i]);
    return segments;
}

// `world['terrain_detail']`, which the planners echo into their surface reports and
// whose presence is what switches the detail bands on in their height fields.
// terrain_detail.attach_detail, verbatim, including the float spelling of the bands.
Value terrain_detail_value(const WorldEnvelope& world) {
    if(world.bands.empty()) return Value::make_null();
    Value detail=vobj();
    detail.set("version",vint(terrain_detail_version));
    detail.set("seed",vint(static_cast<std::int64_t>(world.detail_seed)));
    Value bands=varr();
    for(const DetailBand& band:world.bands) {
        Value row=vobj();
        row.set("scale_m",vflt(band.scale_m));
        row.set("amplitude_m",vflt(band.amplitude_m));
        bands.items.push_back(std::move(row));
    }
    detail.set("bands",std::move(bands));
    detail.set("height_reference",vstr("radial metres above reference sphere; same datum as layers.height"));
    detail.set("coordinates",vstr("unit direction (cos(lat)*cos(lon), sin(lat), cos(lat)*sin(lon))"));
    detail.set("method",vstr("Coarse elevation plus continuous spherical Perlin bands; interpolated biome "
                             "amplitude and water/river/flood protection. Resolved samples are authoritative; "
                             "LOD never changes the height function."));
    return detail;
}

// terrain_civilizations.classify_cities: one capital per people -- the founding
// capital, else the best suitability, node breaking ties -- and everyone else medium
// or small on the authored threshold. The city planner reads city_class for its
// programme size, its shape draw and its enceinte, so this is not decoration.
std::vector<std::string> city_classes(const std::vector<FoundedCity>& sites,
                                      const std::vector<double>& suitability,double threshold) {
    std::map<std::string,std::size_t> capital;
    for(std::size_t index=0;index<sites.size();++index) {
        const auto entry=capital.find(sites[index].population_profile);
        if(entry==capital.end()) {capital.emplace(sites[index].population_profile,index);continue;}
        const std::size_t best=entry->second;
        // `min(members,key=lambda s:(not founding_capital,-suitability,node))`: a strict
        // improvement replaces, so the earliest member wins a tie exactly as min does.
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

// `world['settlements']['sites']`, reduced to the keys the three planners read plus
// the identity fields the scene keys every record by. Order is founding order, which
// is the order the reference's list is in; fill_cities sorts its own copy.
std::vector<Value> settlement_sites(const WorldEnvelope& world,const Catalogues& catalogues,
                                    const PopulatedWorld& populated) {
    const std::vector<FoundedCity>& sites=populated.founding.sites;
    std::vector<double> suitability(sites.size(),0.);
    for(std::size_t index=0;index<sites.size();++index) {
        const auto species=populated.fields.species.find(sites[index].population_profile);
        if(species!=populated.fields.species.end()&&sites[index].node<species->second.suitability.size())
            suitability[index]=species->second.suitability[sites[index].node];
    }
    const std::vector<std::string> classes=
        city_classes(sites,suitability,catalogues.founding_rules().medium_suitability_min);
    std::vector<Value> rows;
    rows.reserve(sites.size());
    for(std::size_t index=0;index<sites.size();++index) {
        const FoundedCity& site=sites[index];
        const auto& point=world.grid.points[site.node];
        Value row=vobj();
        row.set("id",vint(static_cast<std::int64_t>(index)));
        row.set("name",vstr(site.name));
        row.set("population_profile",vstr(site.population_profile));
        row.set("node",vint(static_cast<std::int64_t>(site.node)));
        row.set("x",vint(point.first));
        row.set("z",vint(point.second));
        row.set("kind",vstr("city"));
        row.set("founding_capital",Value::make_bool(site.founding_capital));
        row.set("suitability",vflt(suitability[index]));
        // `distances[i] if math.isfinite(distances[i]) else None`. The layer spells an
        // unreachable cell -1, and the planner tests this key for None, not for a
        // number, when it decides whether the city can collect water at all.
        const double fresh=site.node<populated.fields.freshwater_distance.size()
            ?populated.fields.freshwater_distance[site.node]:-1.;
        row.set("freshwater_distance_m",std::isfinite(fresh)&&fresh>=0.?vflt(fresh):Value::make_null());
        row.set("resource_potential",vflt(site.node<populated.fields.resource.size()
                                          ?populated.fields.resource[site.node]:0.));
        row.set("city_class",vstr(classes[index]));
        if(index<populated.residents.size()) {
            row.set("population_estimate",vint(populated.residents[index].residents));
            row.set("urban_population_estimate",vint(populated.residents[index].urban));
            row.set("rural_population_estimate",vint(populated.residents[index].rural));
        }
        // Every city of a populated world carries one by the time this runs, and the
        // scene keys its buildings by it: `surface-city-0-115-tidekin:plot-0`.
        if(!site.uid.empty()) row.set("uid",vstr(site.uid));
        rows.push_back(std::move(row));
    }
    return rows;
}

// terrain_humans.record: one hamlet or fortress row, with the keys its planner reads.
Value rural_site_value(const RuralSite& site) {
    Value row=vobj();
    row.set("id",vstr(site.id));
    row.set("kind",vstr(site.kind));
    row.set("node",vint(static_cast<std::int64_t>(site.node)));
    row.set("x",vint(site.x));
    row.set("z",vint(site.z));
    row.set("core_id",vint(site.core_id));
    row.set("population_profile",vstr(site.population_profile));
    row.set("culture_id",vstr(site.culture_id));
    row.set("height_m",vflt(site.height_m));
    row.set("access_cost",vflt(site.access_cost));
    Value nodes=varr();
    for(std::size_t node:site.access_nodes) nodes.items.push_back(vint(static_cast<std::int64_t>(node)));
    row.set("access_nodes",std::move(nodes));
    row.set("reason",vstr(site.reason));
    // A fortress has no role in the reference's record; a hamlet's decides its preset.
    if(!site.role.empty()) row.set("role",vstr(site.role));
    return row;
}

// Everything the four modules share, built once. The grids are borrowed: each planner
// world copies the ones it needs and is destroyed before the next is built, so a large
// world holds one copy at a time rather than four.
struct PlannerInputs {
    std::int64_t size=0,seed=0;
    double globe_radius=0.,sea_level=0.;
    Value radius,terrain_detail;
    bool has_terrain_detail=false;
    std::int64_t detail_seed=0;
    std::vector<std::pair<double,double>> bands;
    const Grid *height=nullptr,*slope=nullptr,*water_type=nullptr,*river=nullptr,
               *flood_risk=nullptr,*moisture=nullptr;
    std::vector<std::vector<Value>> natural_biome;
    std::vector<std::pair<std::int64_t,std::int64_t>> water_nodes,river_segments;
    std::vector<Value> sites,hamlets,fortresses;
    std::vector<sceneframe::Route> routes;
};

PlannerInputs planner_inputs(const WorldEnvelope& world,const Catalogues& catalogues,
                             const PopulatedWorld& populated) {
    PlannerInputs inputs;
    inputs.size=world.size;
    inputs.seed=world.config.seed;
    inputs.globe_radius=world.effective.globe_radius;
    // `world['effective_config']['globe_radius']` is a float once the world scale has
    // resolved, and the planners echo the value itself into reference_frame.radius_m.
    inputs.radius=vflt(world.effective.globe_radius);
    inputs.sea_level=world.effective.sea_level;
    inputs.height=&world.layers.height;
    inputs.slope=&world.layers.slope;
    inputs.water_type=&world.layers.water_type;
    inputs.river=&world.layers.river;
    inputs.flood_risk=&world.layers.flood_risk;
    inputs.moisture=&world.layers.moisture;
    inputs.natural_biome=integer_rows(world.layers.natural_biome);
    inputs.terrain_detail=terrain_detail_value(world);
    inputs.has_terrain_detail=!world.bands.empty();
    inputs.detail_seed=static_cast<std::int64_t>(world.detail_seed);
    for(const DetailBand& band:world.bands) inputs.bands.emplace_back(band.scale_m,band.amplitude_m);
    inputs.water_nodes=world.grid.points;
    inputs.river_segments=river_segments(world);
    inputs.sites=settlement_sites(world,catalogues,populated);
    for(const RuralSite& hamlet:populated.humans.hamlets) inputs.hamlets.push_back(rural_site_value(hamlet));
    for(const RuralSite& fort:populated.humans.fortresses) inputs.fortresses.push_back(rural_site_value(fort));
    for(const Road& road:populated.roads) {
        sceneframe::Route route;
        route.from=static_cast<std::int64_t>(road.from);
        route.to=static_cast<std::int64_t>(road.to);
        for(std::size_t node:road.nodes) route.nodes.push_back(static_cast<std::int64_t>(node));
        inputs.routes.push_back(std::move(route));
    }
    return inputs;
}

// The rasters and the terrain definition, which the three planners declare with the
// same field names and their own copies of the two layer types.
template<class W> void fill_rasters(W& slice,const PlannerInputs& inputs) {
    using LayerType=std::decay_t<decltype(slice.slope)>;
    using ValueLayerType=std::decay_t<decltype(slice.natural_biome)>;
    using BandType=typename std::decay_t<decltype(slice.bands)>::value_type;
    slice.size=inputs.size;
    slice.seed=inputs.seed;
    slice.globe_radius=inputs.globe_radius;
    slice.sea_level=inputs.sea_level;
    slice.height=*inputs.height;
    slice.slope=LayerType{true,*inputs.slope};
    slice.water_type=LayerType{true,*inputs.water_type};
    slice.river=LayerType{true,*inputs.river};
    slice.flood_risk=LayerType{true,*inputs.flood_risk};
    slice.moisture=LayerType{true,*inputs.moisture};
    slice.natural_biome=ValueLayerType{true,inputs.natural_biome};
    // `biome_variant` is left absent on purpose: the reference's layer is an index into
    // the magical biome catalogue, which this core does not publish, and every planner
    // substitutes -1 for a missing one. It is echoed into their terrain reports and is
    // read by no geometry, so an absent layer changes no building.
    slice.has_terrain_detail=inputs.has_terrain_detail;
    slice.detail_seed=inputs.detail_seed;
    for(const auto& band:inputs.bands) slice.bands.push_back(BandType{band.first,band.second});
    slice.water_nodes=inputs.water_nodes;
    slice.river_segments=inputs.river_segments;
    slice.sites=inputs.sites;
}

// One building record of the scene, back into a plain struct. The record's key order is
// the reference's and is not relied on here; every field is read by name.
SceneBuilding read_building(const Value& record) {
    SceneBuilding building;
    building.id=text_of(record.at("id"));
    building.settlement_kind=text_of(record.at("settlement_kind"));
    // The identity key is named for the settlement kind. All three are the same thing.
    for(const char* key:{"city_uid","hamlet_id","fortress_id"}) {
        const Value* identity=record.find(key);
        if(identity!=nullptr) {building.settlement_id=text_of(*identity);break;}
    }
    building.plot_id=text_of(record.at("plot_id"));
    building.asset_id=text_of(record.at("asset_id"));
    building.position_m=vector_of(record.at("position_m"));
    building.up=vector_of(record.at("up"));
    building.width_axis=vector_of(record.at("width_axis"));
    building.depth_axis=vector_of(record.at("depth_axis"));
    building.rotation_degrees=number_of(record.at("rotation_degrees"));
    const Value& dimensions=record.at("dimensions_m");
    building.width_m=number_of(dimensions.at("width"));
    building.depth_m=number_of(dimensions.at("depth"));
    building.height_m=number_of(dimensions.at("height"));
    const Value& footprint=record.at("footprint_positions_m");
    for(std::size_t corner=0;corner<4&&corner<footprint.items.size();++corner)
        building.footprint_m[corner]=vector_of(footprint.items[corner]);
    return building;
}
}  // namespace

void plan_settlement_buildings(const WorldEnvelope& world,const Catalogues& catalogues,
                               PopulatedWorld& populated) {
    populated.scene.buildings.clear();
    populated.scene.buildings_status.clear();
    if(world.layers.height.empty()) {
        populated.scene.buildings_status="no world raster to plan on";
        return;
    }
    try {
        const PlannerInputs inputs=planner_inputs(world,catalogues,populated);
        // The three plan lists, each built and released before the next: a planner world
        // holds its own copy of every raster it reads.
        std::vector<Value> city_plans,hamlet_plans,castle_plans;
        {
            cityplanner::World slice;
            fill_rasters(slice,inputs);
            slice.radius=inputs.radius;
            slice.terrain_detail=inputs.terrain_detail;
            slice.routes=inputs.routes;
            // `world['threat_assessments']` has no port in this core, and the reference
            // reads a missing row as a regional threat of zero, which is what an
            // unthreatened world scores anyway.
            city_plans=cityplanner::fill_cities(slice).at("cities").items;
        }
        {
            hamletplanner::World slice;
            fill_rasters(slice,inputs);
            slice.radius=inputs.radius;
            slice.terrain_detail=inputs.terrain_detail;
            slice.hamlets=inputs.hamlets;
            hamlet_plans=hamletplanner::fill_hamlets(slice).at("hamlets").items;
        }
        {
            castleplanner::World slice;
            fill_rasters(slice,inputs);
            slice.fortresses=inputs.fortresses;
            castle_plans=castleplanner::fill_castles(slice).at("castles").items;
        }
        scenebuildings::World slice;
        slice.size=inputs.size;
        slice.globe_radius=inputs.globe_radius;
        slice.radius=inputs.radius;
        slice.sea_level=inputs.sea_level;
        slice.height=*inputs.height;
        slice.water_type=scenebuildings::Layer{true,*inputs.water_type};
        slice.river=scenebuildings::Layer{true,*inputs.river};
        slice.flood_risk=scenebuildings::Layer{true,*inputs.flood_risk};
        slice.natural_biome=scenebuildings::ValueLayer{true,inputs.natural_biome};
        slice.has_terrain_detail=inputs.has_terrain_detail;
        slice.detail_seed=inputs.detail_seed;
        for(const auto& band:inputs.bands)
            slice.bands.push_back(scenebuildings::DetailBand{band.first,band.second});
        slice.terrain_detail=inputs.terrain_detail;
        slice.water_nodes=inputs.water_nodes;
        slice.sites=inputs.sites;
        for(std::size_t index=0;index<populated.roads.size();++index) {
            scenebuildings::Route route;
            for(std::size_t node:populated.roads[index].nodes)
                route.nodes.push_back(static_cast<std::int64_t>(node));
            // `road.get('river_crossings',[])`, echoed into bridge_candidates untouched.
            Value crossings=varr();
            for(const auto& edge:populated.roads[index].river_crossings) {
                Value pair=varr();
                pair.items.push_back(vint(static_cast<std::int64_t>(edge.first)));
                pair.items.push_back(vint(static_cast<std::int64_t>(edge.second)));
                crossings.items.push_back(std::move(pair));
            }
            route.river_crossings=std::move(crossings);
            slice.routes.push_back(std::move(route));
        }
        slice.city_plans=std::move(city_plans);
        slice.hamlet_plans=std::move(hamlet_plans);
        slice.castle_plans=std::move(castle_plans);
        const Value scene=scenebuildings::build_scene(slice);
        const Value* buildings=scene.find("buildings");
        if(buildings!=nullptr) {
            populated.scene.buildings.reserve(buildings->items.size());
            for(const Value& record:buildings->items)
                populated.scene.buildings.push_back(read_building(record));
        }
    } catch(const std::exception& failure) {
        // A missing or rejected catalogue, and anything the planners raise out of the
        // reference's own error paths. The world stays populated and says why it has no
        // buildings rather than taking the host down with it.
        populated.scene.buildings.clear();
        populated.scene.buildings_status=failure.what()[0]!='\0'?failure.what()
            :"the settlement planners stopped without a message";
    }
}
}
