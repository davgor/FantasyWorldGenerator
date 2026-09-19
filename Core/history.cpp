#include "history.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator {
namespace {
Vec3 rotate(const Vec3& p,const Vec3& omega,double t) {
    const double speed=std::sqrt(dot(omega,omega));
    const Vec3 axis=unit(omega);
    const double angle=speed*t,c=std::cos(angle),s=std::sin(angle);
    const Vec3 crossed=cross(axis,p);
    const double along=dot(axis,p);
    Vec3 out{};
    for(int i=0;i<3;++i) out[i]=p[i]*c+crossed[i]*s+axis[i]*along*(1-c);
    return out;
}
void measure_surface(const WorldConfig& cfg,double radius,double tpi_radius,double sea_level,Layers& layers) {
    measure_globe(layers.height,radius,tpi_radius,layers.slope,layers.tpi);
    const auto n=static_cast<std::size_t>(cfg.size);
    layers.land=filled(n,0.);
    for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x)
        layers.land[z][x]=layers.height[z][x]>sea_level ? 1. : 0.;
}
Grid abandoned_rivers(const Grid& old_river,const Layers& current) {
    const std::size_t n=old_river.size();
    Grid out=filled(n,0.);
    for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x)
        out[z][x]=(old_river[z][x]!=0. && current.river[z][x]==0. && current.water_type[z][x]==0.) ? 1. : 0.;
    return out;
}
Grid abandoned_water(const Grid& old_water,const Layers& current) {
    const std::size_t n=old_water.size();
    Grid out=filled(n,0.);
    for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x)
        out[z][x]=(old_water[z][x]!=0. && current.water_type[z][x]==0.) ? 1. : 0.;
    return out;
}
}
GeologicalHistory apply_geological_history(const WorldConfig& cfg,double radius,double tpi_radius,double sea_level,
                                           const SphereGrid& grid,std::uint32_t crust_seed,
                                           const std::vector<Plate>& plates,Layers& layers) {
    GeologicalHistory history;
    history.plates_before=plates;
    history.plates_after=plates;
    const double duration=history.angular_duration;
    for(auto& plate:history.plates_after) plate.center=rotate(plate.center,plate.omega,duration);
    const Grid old_height=layers.height,old_river=layers.river;
    const Grid old_water_type=layers.water_type,old_water_depth=layers.water_depth;
    const auto n=static_cast<std::size_t>(cfg.size);
    Grid height=filled(n,0.);
    for(std::size_t z=0;z<n;++z) {
        const std::size_t columns=(z==0 || z==n-1) ? 1 : n-1;
        std::vector<double> row;
        for(std::size_t x=0;x<columns;++x) {
            const Vec3 p=direction(static_cast<std::int64_t>(x),static_cast<std::int64_t>(z),cfg.size);
            const PointResult record=layout_point(p,history.plates_after,crust_seed,cfg);
            const auto owner=static_cast<std::size_t>(record.owner);
            const Vec3 back=rotate(p,history.plates_after[owner].omega,-duration);
            const double transported=sample(old_height,back);
            const double uplift=cfg.world_scale*cfg.tectonic_relief
                *(.9*record.convergence-.7*record.divergence+.18*record.shear);
            row.push_back(.25*old_height[z][x]+.75*transported+uplift);
        }
        const double first=row[0];
        if(z==0 || z==n-1) row.assign(n,first);
        else row.push_back(first);
        height[z]=row;
    }
    layers.height=height;
    measure_surface(cfg,radius,tpi_radius,sea_level,layers);
    add_water(cfg,sea_level,grid,layers);
    // Abandoned beds become terrain: incise them, then reroute water once more.
    const Grid gorges=abandoned_rivers(old_river,layers),valleys=abandoned_water(old_water_type,layers);
    std::vector<double> cuts;
    cuts.reserve(grid.points.size());
    for(const auto& point:grid.points) {
        const auto x=static_cast<std::size_t>(point.first),z=static_cast<std::size_t>(point.second);
        if(gorges[z][x]!=0.) cuts.push_back(std::min(45.,std::max(4.,cfg.tectonic_relief*cfg.world_scale*.12)));
        else if(valleys[z][x]!=0.) cuts.push_back(std::min(100.,std::max(12.,old_water_depth[z][x]*.6)));
        else cuts.push_back(0.);
    }
    // Small shoulders make former river beds visible as terrain, not marker pixels.
    std::vector<double> shouldered=cuts;
    for(std::size_t i=0;i<cuts.size();++i) {
        double best=0.;
        for(const auto& edge:grid.neighbors[i]) best=std::max(best,cuts[static_cast<std::size_t>(edge.first)]*.25);
        shouldered[i]=std::max(cuts[i],best);
    }
    const Grid incision=node_grid(shouldered,grid);
    for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x) layers.height[z][x]-=incision[z][x];
    measure_surface(cfg,radius,tpi_radius,sea_level,layers);
    add_water(cfg,sea_level,grid,layers);
    return history;
}
}
