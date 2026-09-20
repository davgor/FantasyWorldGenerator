#include "world.hpp"
#include "history.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator {
namespace {
void scale_grid(Grid& grid,double factor) {
    for(auto& row:grid) for(double& value:row) value*=factor;
}
// Reference-sphere land footprint; duplicate longitude excluded, height > sea level.
double land_area_m2(const Grid& h,double radius,double sea_level) {
    const auto n=static_cast<std::int64_t>(h.size());
    const double dlat=pi/static_cast<double>(n-1),dlon=2*pi/static_cast<double>(n-1);
    double land=0.;
    for(std::int64_t z=0;z<n;++z) {
        const double lat=pi/2-static_cast<double>(z)*dlat;
        const double north=std::min(pi/2,lat+dlat/2),south=std::max(-pi/2,lat-dlat/2);
        const double weight=radius*radius*dlon*(std::sin(north)-std::sin(south));
        std::int64_t cells=0;
        for(std::int64_t x=0;x<n-1;++x) cells+=(h[static_cast<std::size_t>(z)][static_cast<std::size_t>(x)]>sea_level) ? 1 : 0;
        land+=weight*static_cast<double>(cells);
    }
    return land;
}
double interpolate(const Grid& h,std::size_t ix,std::size_t iz,std::size_t jz,double fx,double fz) {
    return ((1-fx)*h[iz][ix]+fx*h[iz][ix+1])*(1-fz)+((1-fx)*h[jz][ix]+fx*h[jz][ix+1])*fz;
}
double sample_field(const WorldEnvelope& world,const Grid& field,const Vec3& p) {
    const auto n=static_cast<std::int64_t>(field.size());
    if(n<2) return 0.;
    const double span=static_cast<double>(n-1);
    double x=python_mod((std::atan2(p[2],p[0])+pi)/(2*pi)*span,span);
    double z=(pi/2-std::asin(std::max(-1.,std::min(1.,p[1]))))/pi*span;
    z=std::max(0.,std::min(span,z));
    const auto ix=static_cast<std::size_t>(x);
    const auto iz=static_cast<std::size_t>(z);
    const std::size_t jz=std::min(static_cast<std::size_t>(n-1),iz+1);
    return interpolate(field,ix,iz,jz,x-static_cast<double>(ix),z-static_cast<double>(iz));
}
}
WorldConfig resolve_config(const GenerateRequest& request) {
    WorldConfig cfg;
    cfg.seed=request.seed;
    if(request.size) cfg.size=*request.size;
    if(request.shape) cfg.shape=*request.shape;
    // The physical size of the finished world. Terrain pattern, plates and noise are
    // unchanged by it: the same seed keeps its world and gains metres. Distances that
    // are stated in metres, such as settlement spacing and support reach, are not
    // scaled, so a larger world holds proportionally more of them, which is the
    // reference's own behaviour for this override.
    if(request.world_scale) cfg.world_scale=*request.world_scale;
    // Named recipe inputs. Vertical relief lives here: the recipe's default world is
    // a gentle one, and a caller that wants mountains raises the relief rather than
    // stretching the result, so erosion, rivers and biomes all answer to the change.
    for(const auto& entry:request.overrides) {
        const std::string& key=entry.first;
        const double value=entry.second;
        if(key=="amplitude") cfg.amplitude=value;
        else if(key=="tectonic_relief") cfg.tectonic_relief=value;
        else if(key=="mountain_detail") cfg.mountain_detail=value;
        else if(key=="orogeny") cfg.orogeny=value;
        else if(key=="globe_radius") cfg.globe_radius=value;
        else if(key=="ridge") cfg.ridge=value;
        else if(key=="octaves") cfg.octaves=static_cast<std::int64_t>(value);
        else if(key=="sea_level") cfg.sea_level=value;
        else if(key=="wavelength") cfg.wavelength=value;
        else if(key=="radius") cfg.radius=value;
        else if(key=="extent") cfg.extent=value;
        else if(key=="plate_count") cfg.plate_count=static_cast<std::int64_t>(value);
        else if(key=="belt_width") cfg.belt_width=value;
        else if(key=="crust_bias") cfg.crust_bias=value;
        else if(key=="temperature_offset") cfg.temperature_offset=value;
        else if(key=="moisture_bias") cfg.moisture_bias=value;
        else if(key=="erosion_passes") cfg.erosion_passes=static_cast<std::int64_t>(value);
        else if(key=="erosion_strength") cfg.erosion_strength=value;
        else if(key=="settlement_spacing") cfg.settlement_spacing=value;
        else if(key=="support_reach") cfg.support_reach=value;
        else throw Error("INVALID_INPUT");
    }
    // The design radius preset, exactly as the reference resolves it: an explicit
    // globe_radius override wins, otherwise the size name picks one, two or three
    // times ten kilometres. The shared scale is applied later.
    if(request.world_size) {
        cfg.world_size=*request.world_size;
        const double multiple=cfg.world_size=="large" ? 3. : (cfg.world_size=="medium" ? 2. : 1.);
        if(request.overrides.count("globe_radius")==0) cfg.globe_radius=10000.*multiple;
    }
    return cfg;
}
Vec3 globe_direction(double latitude_degrees,double longitude_degrees) {
    const double lat=latitude_degrees*(pi/180.0),lon=longitude_degrees*(pi/180.0);
    return Vec3{std::cos(lat)*std::cos(lon),std::sin(lat),std::cos(lat)*std::sin(lon)};
}
GlobeCoordinates unwrap_coordinates(const Vec3& direction) {
    GlobeCoordinates coordinates;
    coordinates.latitude_degrees=std::asin(std::max(-1.,std::min(1.,direction[1])))*(180.0/pi);
    coordinates.longitude_degrees=std::atan2(direction[2],direction[0])*(180.0/pi);
    return coordinates;
}
WorldEnvelope generate_world(const GenerateRequest& request) {
    WorldEnvelope world;
    world.config=resolve_config(request);
    const WorldConfig& cfg=world.config;
    world.size=cfg.size;
    const SphereGrid design_grid=sphere_grid(cfg.size,cfg.globe_radius);
    const TectonicResult tectonics=generate_tectonics(cfg,design_grid,world.layers);
    world.plates=tectonics.plates;
    world.archipelagos=tectonics.archipelagos;
    world.sediment=tectonics.sediment;
    world.resolved_octaves=tectonics.resolved_octaves;
    // Shared physical scaling: design inputs stay in the request, metres in effective.
    const double factor=cfg.world_scale;
    world.effective=cfg;
    world.effective.globe_radius*=factor;world.effective.extent*=factor;world.effective.amplitude*=factor;
    world.effective.wavelength*=factor;world.effective.depth*=factor;world.effective.width*=factor;
    world.effective.meander*=factor;world.effective.radius*=factor;world.effective.tectonic_relief*=factor;
    world.effective.sea_level*=factor;
    for(Grid* grid:{&world.layers.base,&world.layers.height,&world.layers.structure,&world.layers.interaction,
                    &world.layers.noise,&world.layers.tpi,&world.layers.boundary_distance,&world.layers.continental,
                    &world.layers.surface,&world.layers.erosion,&world.layers.deposition,&world.layers.erosion_delta,
                    &world.layers.archipelago_relief})
        if(!grid->empty()) scale_grid(*grid,factor);
    if(!world.layers.catchment.empty()) scale_grid(world.layers.catchment,factor*factor);
    world.sediment.eroded_m3*=factor*factor*factor;world.sediment.deposited_m3*=factor*factor*factor;
    world.sediment.stored_sediment_m3*=factor*factor*factor;world.sediment.balance_error_m3*=factor*factor*factor;
    world.spacing_m=tectonics.spacing_m*factor;
    const double radius=world.effective.globe_radius,sea=world.effective.sea_level;
    world.land_km2=land_area_m2(world.layers.height,radius,sea)/1e6;
    const auto n=static_cast<std::size_t>(cfg.size);
    world.layers.land=filled(n,0.);
    for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x)
        world.layers.land[z][x]=world.layers.height[z][x]>sea ? 1. : 0.;
    world.grid=sphere_grid(cfg.size,radius);
    add_water(cfg,sea,world.grid,world.layers);
    // Stages six and seven: the second tectonic epoch and its abandoned waterways.
    world.history=apply_geological_history(cfg,radius,world.effective.radius,sea,world.grid,
                                           tectonics.crust_seed,tectonics.plates,world.layers);
    const WaterRouting routed=add_water(cfg,sea,world.grid,world.layers);
    world.has_ocean=routed.has_ocean;
    world.land_km2=land_area_m2(world.layers.height,radius,sea)/1e6;
    Sum ocean,lake,dry;
    for(std::size_t i=0;i<world.grid.points.size();++i) {
        const auto x=static_cast<std::size_t>(world.grid.points[i].first),z=static_cast<std::size_t>(world.grid.points[i].second);
        const double kind=world.layers.water_type[z][x];
        if(kind==1.) ocean.add(world.grid.areas[i]);
        else if(kind==2.) lake.add(world.grid.areas[i]);
        else dry.add(world.grid.areas[i]);
    }
    world.ocean_km2=ocean.value()/1e6;world.lake_km2=lake.value()/1e6;world.dry_km2=dry.value()/1e6;
    world.climate=add_climate(cfg,radius,sea,world.grid,routed,world.layers);
    add_terrain_labels(cfg,sea,world.grid,world.layers);
    // Stage nine: the magic networks come before the environment that reads them, and
    // the labels above are what the cold habitats reclassify.
    world.networks=generate_networks(cfg);
    evaluate_networks(cfg,radius,world.grid,world.networks,world.layers);
    add_cold_habitats(cfg,world.grid,world.layers);
    world.regions=add_environment(cfg,radius,world.spacing_m,world.grid,world.layers);
    add_surface_fields(cfg,world.grid,world.layers);
    // The moon is seeded once per world; how far each cell sways reads the fields above.
    world.moon=seed_moon(static_cast<std::uint64_t>(cfg.seed));
    world.layers.lunar_sensitivity=lunar_sensitivity(world.layers,cfg.size);
    // Continuous terrain definition and its interpolated amplitude mask.
    world.detail_seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"continuous-terrain-v1");
    const double scales[3]={120.,28.,6.},amplitudes[3]={12.,2.5,.3};
    for(int i=0;i<3;++i)
        world.bands.push_back(DetailBand{scales[i],amplitudes[i],
            child_seed(static_cast<std::uint64_t>(world.detail_seed),std::to_string(i))});
    world.detail_strength=filled(n,0.);
    for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x) {
        if(world.layers.water_type[z][x]!=0.) continue;
        const double river=world.layers.river[z][x],flood=world.layers.flood_risk[z][x];
        const std::int64_t biome=static_cast<std::int64_t>(world.layers.natural_biome[z][x]);
        const double relief=biome==5 ? 1.4 : biome==3 ? .8 : biome==4 ? 1. : biome==7 ? 1. : biome==15 ? .8 : .65;
        world.detail_strength[z][x]=std::max(0.,1-std::min(1.,river*2))*std::max(0.,1-std::min(1.,flood))*relief;
    }
    return world;
}
namespace {
// Categorical layers read the nearest node, never a blend of two identities.
std::pair<std::size_t,std::size_t> nearest_cell(const WorldEnvelope& world,const Vec3& p) {
    const auto n=static_cast<std::int64_t>(world.size);
    const double span=static_cast<double>(n-1);
    const double x=python_mod((std::atan2(p[2],p[0])+pi)/(2*pi)*span,span);
    double z=(pi/2-std::asin(std::max(-1.,std::min(1.,p[1]))))/pi*span;
    z=std::max(0.,std::min(span,z));
    const auto column=static_cast<std::size_t>(std::min(span,std::nearbyint(x)));
    const auto row=static_cast<std::size_t>(std::min(span,std::nearbyint(z)));
    return {column,row};
}
}
SurfaceSample sample_surface(const WorldEnvelope& world,const Vec3& direction) {
    const auto cell=nearest_cell(world,direction);
    const std::size_t x=cell.first,z=cell.second;
    SurfaceSample sample;
    sample.height_m=sample_height(world,direction);
    // The regional raster labels cells; a consumer draws a surface. Painting the cell
    // label puts every coastline and treeline on the grid rather than on the ground,
    // so the rule the reference classifies with is evaluated here at the point asked
    // for, from the sampled height and the interpolated climate. Between raster nodes
    // this is the same rule applied where the reference simply has no value.
    const double above_sea=sample.height_m-world.effective.sea_level;
    sample.temperature_c=28-45*std::pow(direction[1],2.)-.0065*std::max(0.,above_sea)
        +world.config.temperature_offset;
    sample.moisture=sample_field(world,world.layers.climate_moisture,direction);
    const double slope=sample_field(world,world.layers.slope,direction);
    // Which body of water a cell belongs to is topology from the flood fill, so it
    // comes from the cell; whether this point lies under that body is geometry, and
    // taking it from the drawn height keeps the painted shore on the drawn shore.
    const double kind=world.layers.water_type[z][x];
    const double level=sample_field(world,world.layers.water_surface,direction);
    sample.water_type=(kind!=0. && sample.height_m<level) ? static_cast<std::int64_t>(kind) : 0;
    sample.water_surface_m=sample.water_type!=0 ? level : sample.height_m;
    std::int64_t identity=classify(above_sea,slope,sample.temperature_c,sample.moisture);
    if(sample.water_type==1) identity=0;
    else if(sample.water_type==2) identity=8;
    else if(above_sea>0) {
        // Marsh comes from the wetland catchment, which is a field the raster owns,
        // so it keeps the cell's answer. The cold habitats are applied after it and
        // overwrite it, exactly as the label pass and the ecology pass do in order:
        // a frozen marsh is reported as the cold habitat it has become.
        const double distance=world.layers.wetland_distance[z][x];
        if(distance>=0 && marsh_suitable(sample.moisture,sample.temperature_c,slope,distance,
                                         world.layers.wetland_relief[z][x])) identity=13;
        const double latitude=std::asin(std::max(-1.,std::min(1.,direction[1])))*(180.0/pi);
        const std::string cold=cold_habitat(
            monthly_temperatures(sample.temperature_c,latitude,sample.moisture,
                                 world.config.options.seasonality),
            sample.moisture,world.config.options.ice_accumulation);
        if(cold=="boreal") identity=15;
        else if(cold=="tundra") identity=16;
        else if(cold=="ice_cap") identity=17;
    }
    sample.natural_biome=identity;
    sample.landform=static_cast<std::int64_t>(world.layers.landform[z][x]);
    sample.water_depth_m=world.layers.water_depth[z][x];
    sample.flood_risk=world.layers.flood_risk[z][x];
    sample.river=world.layers.rain_river[z][x]!=0. || world.layers.river[z][x]!=0.;
    return sample;
}
std::array<int,3> natural_biome_color(std::int64_t identity) {
    for(const auto& entry:natural_catalogue()) if(entry.id==identity) return entry.color;
    throw Error("INVALID_INPUT");
}
double sample_height(const WorldEnvelope& world,const Vec3& p) {
    const Grid& base=world.layers.height;
    const auto n=static_cast<std::int64_t>(base.size());
    const double span=static_cast<double>(n-1);
    double x=python_mod((std::atan2(p[2],p[0])+pi)/(2*pi)*span,span);
    double z=(pi/2-std::asin(std::max(-1.,std::min(1.,p[1]))))/pi*span;
    z=std::max(0.,std::min(span,z));
    const auto ix=static_cast<std::size_t>(x);
    const auto iz=static_cast<std::size_t>(z);
    const std::size_t jz=std::min(static_cast<std::size_t>(n-1),iz+1);
    const double fx=x-static_cast<double>(ix),fz=z-static_cast<double>(iz);
    const double ground=interpolate(base,ix,iz,jz,fx,fz);
    // Each factor can independently zero the detail; the result is the coarse
    // height whenever it does, so water, shore and protected cells skip the bands.
    const double coast=std::max(0.,std::min(1.,(ground-world.effective.sea_level)/20.));
    if(coast==0.) return ground;
    double strength=interpolate(world.detail_strength,ix,iz,jz,fx,fz);
    // A zero plateau protects entire water cells and makes shores conservative.
    strength=std::max(0.,(strength-.15)/.85);
    if(strength==0.) return ground;
    const double wet=std::max(0.,1-2*interpolate(world.layers.water_type,ix,iz,jz,fx,fz));
    strength*=coast*coast*(3-2*coast)*wet*wet;
    if(strength==0.) return ground;
    const double radius=world.effective.globe_radius;
    Sum detail;
    for(const auto& band:world.bands)
        detail.add(band.amplitude_m*perlin3(p[0]*radius/band.scale_m,p[1]*radius/band.scale_m,
                                            p[2]*radius/band.scale_m,band.seed));
    return ground+strength*detail.value();
}
}
