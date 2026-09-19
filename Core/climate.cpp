#include "climate.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator {
namespace {
constexpr double deg_to_rad=pi/180.0;   // math.radians multiplies by this constant
struct Weight {std::size_t node;double share;};
double climate_wetness(double rain,double temperature,std::int64_t recipe) {
    const double demand=recipe==3 ? .025*(1+std::max(0.,temperature-10)/15) : .025;
    return rain/(rain+demand);
}
double stencil_sum(const std::vector<double>& values,const std::vector<Weight>& stencil) {
    Sum total;
    for(const auto& item:stencil) total.add(values[item.node]*item.share);
    return total.value();
}
}
ClimateResult add_climate(const WorldConfig& cfg,double radius,double sea_level,const SphereGrid& grid,
                          const WaterRouting& water,Layers& layers) {
    ClimateResult result;
    const std::int64_t n=cfg.size;
    const double span=static_cast<double>(n-1);
    const double bearing=cfg.wind_bearing*deg_to_rad,angle=2*pi/span;
    const std::size_t count=grid.points.size();
    std::vector<std::vector<Weight>> stencils;
    stencils.reserve(count);
    for(const auto& point:grid.points) {
        const std::int64_t x=point.first,z=point.second;
        const Vec3 p=direction(x,z,n);
        const double lon=2*pi*static_cast<double>(x)/span-pi,lat=pi/2-pi*static_cast<double>(z)/span;
        const Vec3 east{-std::sin(lon),0,std::cos(lon)};
        const Vec3 north{-std::sin(lat)*std::cos(lon),std::cos(lat),-std::sin(lat)*std::sin(lon)};
        Vec3 wind{},q{};
        for(int j=0;j<3;++j) wind[j]=std::sin(bearing)*east[j]+std::cos(bearing)*north[j];
        for(int j=0;j<3;++j) q[j]=p[j]*std::cos(angle)-wind[j]*std::sin(angle);
        const double xx=(std::atan2(q[2],q[0])+pi)/(2*pi)*span;
        const double zz=std::max(0.,std::min(span,(pi/2-std::asin(std::max(-1.,std::min(1.,q[1]))))/pi*span));
        const auto ix=static_cast<std::int64_t>(xx),iz=static_cast<std::int64_t>(zz);
        const double fx=xx-static_cast<double>(ix),fz=zz-static_cast<double>(iz);
        const std::int64_t jz=std::min(n-1,iz+1);
        stencils.push_back({Weight{static_cast<std::size_t>(grid.index(ix,iz)),(1-fx)*(1-fz)},
                            Weight{static_cast<std::size_t>(grid.index(ix+1,iz)),fx*(1-fz)},
                            Weight{static_cast<std::size_t>(grid.index(ix,jz)),(1-fx)*fz},
                            Weight{static_cast<std::size_t>(grid.index(ix+1,jz)),fx*fz}});
    }
    const std::vector<double> surface=node_values(layers.water_surface,grid);
    const std::vector<double> kind=node_values(layers.water_type,grid);
    std::vector<bool> wet_cell(count,false);
    for(std::size_t i=0;i<count;++i) wet_cell[i]=kind[i]>0.;
    std::vector<double> rise(count,0.),loss(count,0.),humidity(count,0.),rain(count,0.);
    for(std::size_t i=0;i<count;++i) {
        rise[i]=std::max(0.,surface[i]-stencil_sum(surface,stencils[i]));
        loss[i]=std::min(.85,.06+cfg.rain_strength*rise[i]/150);
    }
    for(std::int64_t pass=0;pass<cfg.rain_passes;++pass) {
        std::vector<double> following(count,0.);
        rain.assign(count,0.);
        for(std::size_t i=0;i<count;++i) {
            const double incoming=stencil_sum(humidity,stencils[i]);
            const double available=wet_cell[i] ? incoming+.45*(1-incoming) : incoming;
            rain[i]=available*loss[i];
            following[i]=available-rain[i];
        }
        double residual=0.;
        for(std::size_t i=0;i<count;++i) residual=std::max(residual,std::fabs(following[i]-humidity[i]));
        result.residual=residual;
        humidity=following;
    }
    const std::vector<double> height=node_values(layers.height,grid);
    std::vector<double> moisture(count,0.),runoff(count,0.);
    for(std::size_t i=0;i<count;++i) {
        const std::int64_t x=grid.points[i].first,z=grid.points[i].second;
        const double y=direction(x,z,n)[1];
        const double temperature=28-45*std::pow(y,2.)-std::max(0.,height[i]-sea_level)*.0065+cfg.temperature_offset;
        moisture[i]=std::max(0.,std::min(1.,climate_wetness(rain[i],temperature,cfg.world_recipe)+cfg.moisture_bias));
        runoff[i]=grid.areas[i]*rain[i]/.04;
    }
    // Leaf-to-root accumulation works for any acyclic receiver ordering.
    std::vector<std::int64_t> children(count,0);
    for(std::size_t i=0;i<count;++i) if(water.receivers[i]>=0) ++children[static_cast<std::size_t>(water.receivers[i])];
    std::vector<std::size_t> queue;
    for(std::size_t i=0;i<count;++i) if(children[i]==0) queue.push_back(i);
    for(std::size_t k=0;k<queue.size();++k) {
        const std::size_t i=queue[k];
        const std::int64_t parent=water.receivers[i];
        if(parent<0) continue;
        const auto p=static_cast<std::size_t>(parent);
        runoff[p]+=runoff[i];
        if(--children[p]==0) queue.push_back(p);
    }
    std::vector<double> river(count,0.);
    for(std::size_t i=0;i<count;++i)
        river[i]=(!wet_cell[i] && water.receivers[i]>=0 && runoff[i]>=cfg.river_threshold_km2*1e6) ? 1. : 0.;
    layers.air_moisture=node_grid(humidity,grid);
    layers.rainfall=node_grid(rain,grid);
    layers.wind_uplift=node_grid(rise,grid);
    layers.climate_moisture=node_grid(moisture,grid);
    layers.rain_runoff=node_grid(runoff,grid);
    layers.rain_river=node_grid(river,grid);
    result.passes=cfg.rain_passes;
    result.transport_step_m=radius*angle;
    return result;
}
}
