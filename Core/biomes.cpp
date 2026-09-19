#include "biomes.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
namespace fantasy_world_generator {
namespace {
constexpr double deg_to_rad=pi/180.0;
constexpr double infinite=std::numeric_limits<double>::infinity();
double clamp01(double v) {return std::max(0.,std::min(1.,v));}
// Nearest mapped water on the sphere, limited to a 180 metre wetland margin.
void wetland_access(const SphereGrid& grid,Layers& layers) {
    const std::size_t count=grid.points.size();
    const std::vector<double> kind=node_values(layers.water_type,grid);
    const std::vector<double> river=node_values(layers.rain_river.empty() ? layers.river : layers.rain_river,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    std::vector<double> distance(count,infinite);
    std::vector<std::int64_t> source(count,-1);
    using Entry=std::pair<double,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(std::size_t i=0;i<count;++i) if(kind[i]!=0. || river[i]!=0.) {
        distance[i]=0;source[i]=static_cast<std::int64_t>(i);queue.emplace(0.,i);
    }
    while(!queue.empty()) {
        const auto entry=queue.top();queue.pop();
        const std::size_t i=entry.second;
        if(entry.first!=distance[i]) continue;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            const double candidate=entry.first+edge.second;
            if(candidate<=180 && candidate<distance[j]) {
                distance[j]=candidate;source[j]=source[i];queue.emplace(candidate,j);
            }
        }
    }
    std::vector<double> reported(count,0.),relief(count,0.);
    for(std::size_t i=0;i<count;++i) {
        const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
        std::size_t sx=x,sz=z;
        if(source[i]>=0) {
            const auto& origin=grid.points[static_cast<std::size_t>(source[i])];
            sx=static_cast<std::size_t>(origin.first);sz=static_cast<std::size_t>(origin.second);
        }
        relief[i]=layers.height[z][x]-layers.water_surface[sz][sx];
        reported[i]=std::isfinite(distance[i]) ? distance[i] : -1.;
    }
    layers.wetland_distance=node_grid(reported,grid);
    layers.wetland_relief=node_grid(relief,grid);
}
}
std::vector<double> monthly_temperatures(double mean,double latitude,double wet,double seasonality) {
    const double amplitude=20*std::sin(latitude*deg_to_rad)*(1-.4*wet)*seasonality;
    std::vector<double> months;
    for(int month=0;month<12;++month) months.push_back(mean+amplitude*std::cos(2*pi*(month-6)/12));
    return months;
}
// Empty when the cell is not a cold habitat.
std::string cold_habitat(const std::vector<double>& temps,double wet,double accumulation) {
    const double warmest=*std::max_element(temps.begin(),temps.end());
    if(warmest<1 && wet>=accumulation*.4) return "ice_cap";
    if(warmest<10) return "tundra";
    std::int64_t warm_months=0;
    for(double t:temps) warm_months+=(t>5) ? 1 : 0;
    if(warm_months<=6) return wet>=.4 ? "boreal" : "tundra";
    return "";
}
const std::vector<NaturalBiome>& natural_catalogue() {
    static const std::vector<NaturalBiome> catalogue{
        {0,"ocean",{42,102,147}},{1,"tundra",{156,164,126}},{2,"desert",{218,184,120}},
        {3,"grassland",{139,176,99}},{4,"forest",{65,135,80}},{5,"exposed_rock",{145,143,139}},
        {6,"snow",{230,240,241}},{7,"rainforest",{22,83,58}},{8,"lake",{68,160,185}},
        {13,"marsh",{105,135,101}},{15,"boreal_forest",{56,104,95}},{16,"cold_tundra",{152,164,136}},
        {17,"land_ice",{223,240,245}}};
    return catalogue;
}
bool marsh_suitable(double wet,double temp,double slope,double water_distance,double height_above_water) {
    return wet>=.55 && temp>0 && slope<6 && water_distance>=0 && water_distance<=180
        && height_above_water>=0 && height_above_water<=4;
}
std::int64_t classify(double above_sea,double slope,double temperature,double moisture) {
    if(above_sea<=0) return 0;
    if(temperature<=0) return 6;
    if(slope>=38) return 5;
    if(temperature<5) return 1;
    if(moisture<.3) return 2;
    if(temperature>=20 && moisture>=.78) return 7;
    if(moisture>=.55) return 4;
    return 3;
}
void add_terrain_labels(const WorldConfig& cfg,double sea_level,const SphereGrid& grid,Layers& layers) {
    const auto n=static_cast<std::size_t>(cfg.size);
    wetland_access(grid,layers);
    layers.temperature=filled(n,0.);layers.moisture=filled(n,0.);
    layers.biome=filled(n,0.);layers.landform=filled(n,0.);
    for(std::size_t z=0;z<n;++z) {
        const std::size_t columns=(z==0 || z==n-1) ? 1 : n-1;
        for(std::size_t x=0;x<columns;++x) {
            const Vec3 p=direction(static_cast<std::int64_t>(x),static_cast<std::int64_t>(z),cfg.size);
            const double h=layers.height[z][x]-sea_level;
            const double temp=28-45*std::pow(p[1],2.)-.0065*std::max(0.,h)+cfg.temperature_offset;
            const double wet=layers.climate_moisture[z][x];
            const double slope=layers.slope[z][x],tpi=layers.tpi[z][x];
            double biome=static_cast<double>(classify(h,slope,temp,wet));
            const double water=layers.water_type[z][x];
            if(water==1.) biome=0.;
            else if(water==2.) biome=8.;
            if(water==0. && h>0 && layers.wetland_distance[z][x]>=0
               && marsh_suitable(wet,temp,slope,layers.wetland_distance[z][x],layers.wetland_relief[z][x])) biome=13.;
            const double form=h<=0 ? 0. : (h>30 && tpi>12 ? 2. : (tpi<-10 ? 3. : 1.));
            layers.temperature[z][x]=temp;layers.moisture[z][x]=wet;
            layers.biome[z][x]=biome;layers.landform[z][x]=form;
        }
        for(Grid* target:{&layers.temperature,&layers.moisture,&layers.biome,&layers.landform}) {
            const double first=(*target)[z][0];
            if(z==0 || z==n-1) (*target)[z].assign(n,first);
            else (*target)[z][n-1]=first;
        }
    }
    layers.natural_biome=layers.biome;
}
void add_cold_habitats(const WorldConfig& cfg,const SphereGrid& grid,Layers& layers) {
    const auto n=static_cast<std::size_t>(cfg.size);
    const double span=static_cast<double>(cfg.size-1);
    for(std::size_t i=0;i<grid.points.size();++i) {
        const auto x=static_cast<std::size_t>(grid.points[i].first),z=static_cast<std::size_t>(grid.points[i].second);
        if(layers.water_type[z][x]!=0.) continue;
        const double wet=layers.moisture[z][x];
        const std::vector<double> temps=monthly_temperatures(layers.temperature[z][x],
            90-180*static_cast<double>(z)/span,wet,cfg.options.seasonality);
        const std::string cold=cold_habitat(temps,wet,cfg.options.ice_accumulation);
        if(cold.empty()) continue;
        layers.biome[z][x]=cold=="boreal" ? 15. : cold=="tundra" ? 16. : 17.;
    }
    // Return categorical edits to the duplicate seam and unique poles.
    for(std::size_t z=0;z<n;++z) {
        const double first=layers.biome[z][0];
        if(z==0 || z==n-1) layers.biome[z].assign(n,first);
        else layers.biome[z][n-1]=first;
    }
    layers.natural_biome=layers.biome;
}
void add_surface_fields(const WorldConfig& cfg,const SphereGrid& grid,Layers& layers) {
    const std::size_t count=grid.points.size();
    const std::vector<double> kind=node_values(layers.water_type,grid);
    const std::vector<double> wet=node_values(layers.moisture,grid);
    const std::vector<double> river=node_values(layers.rain_river,grid);
    const std::vector<double> height=node_values(layers.height,grid);
    std::vector<double> salt(count,0.);
    for(std::size_t i=0;i<count;++i)
        salt[i]=kind[i]==1. ? 1. : (kind[i]==2. ? clamp01((.6-wet[i])*2*cfg.options.salinity) : 0.);
    layers.salinity=node_grid(salt,grid);
    // Freshwater distance skips ocean cells and saline lakes, as the settlement stage does.
    std::vector<double> distance(count,infinite);
    std::vector<std::int64_t> source(count,-1);
    using Entry=std::pair<double,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(std::size_t i=0;i<count;++i) {
        const bool fresh=(kind[i]==2. || river[i]!=0.) && (!cfg.world_recipe || salt[i]<.2);
        if(!fresh) continue;
        distance[i]=0;source[i]=static_cast<std::int64_t>(i);queue.emplace(0.,i);
    }
    while(!queue.empty()) {
        const auto entry=queue.top();queue.pop();
        const std::size_t i=entry.second;
        if(entry.first!=distance[i]) continue;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            if(kind[j]==1.) continue;
            if(entry.first+edge.second<distance[j]) {
                distance[j]=entry.first+edge.second;source[j]=source[i];queue.emplace(distance[j],j);
            }
        }
    }
    std::vector<double> flood(count,0.),reported(count,0.);
    for(std::size_t i=0;i<count;++i) {
        double level=0.;
        if(source[i]>=0) {
            const auto& origin=grid.points[static_cast<std::size_t>(source[i])];
            level=layers.water_surface[static_cast<std::size_t>(origin.second)][static_cast<std::size_t>(origin.first)];
        }
        flood[i]=std::exp(-distance[i]/80)*std::max(0.,1-std::max(0.,height[i]-level)/10);
        reported[i]=std::isfinite(distance[i]) ? distance[i] : -1.;
    }
    layers.flood_risk=node_grid(flood,grid);
    layers.freshwater_distance=node_grid(reported,grid);
}
}
