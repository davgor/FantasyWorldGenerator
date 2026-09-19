#include "tectonics.hpp"
#include "pyrandom.hpp"
#include "json.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator {
namespace {
double clamp01(double v) {return std::max(0.,std::min(1.,v));}
Vec3 scaled(const Vec3& p,double factor) {return Vec3{p[0]*factor,p[1]*factor,p[2]*factor};}
Vec3 added(const Vec3& a,const Vec3& b) {return Vec3{a[0]+b[0],a[1]+b[1],a[2]+b[2]};}
Vec3 subtracted(const Vec3& a,const Vec3& b) {return Vec3{a[0]-b[0],a[1]-b[1],a[2]-b[2]};}
double angle_between(const Vec3& a,const Vec3& b) {return std::acos(std::max(-1.,std::min(1.,dot(a,b))));}
// Elongated cross-belt ridges with peaks and passes varying along their length.
double mountain_modulation(double along,double across,double strength) {
    const double ridge=.5+.5*std::cos(9*across+.6*std::sin(3*along));
    const double peaks=.7+.3*(.5+.5*std::sin(5*along+.4));
    const double shaped=.35+.65*ridge*peaks;
    return 1-strength+strength*shaped;
}
struct Motion {double convergence=0.,divergence=0.,shear=0.;};
Motion relative_motion(const Vec3& p,const Vec3& normal,const Vec3& omega_i,const Vec3& omega_j) {
    const Vec3 vi=cross(omega_i,p),vj=cross(omega_j,p);
    const Vec3 relative=subtracted(vj,vi);
    const double opening=dot(relative,normal);
    const double shear=std::sqrt(std::max(0.,dot(relative,relative)-opening*opening));
    return Motion{std::min(1.,std::max(0.,-opening/2)),std::min(1.,std::max(0.,opening/2)),std::min(1.,shear/2)};
}
struct Relief {double structure=0.,interaction=0.,volcanic=0.;};
Relief relief_at(double c,double distance,double conv,double div,double ci,double cj,
                 const WorldConfig& cfg,double along,double across) {
    const double width=cfg.belt_width*cfg.globe_radius;
    const double d=distance/width;
    const double belt=std::exp(-d*d);
    const double collision=conv*ci*cj;
    const double subduction=conv*(1-ci*cj);
    // The more continental side overrides. Equal crust is a simplified tie.
    const double overriding=.5+.5*std::tanh(8*(ci-cj));
    const double abundance=cfg.world_recipe ? cfg.options.mountain_abundance : 1.;
    const double uplift=cfg.orogeny*2*collision
        *std::exp(-std::pow(d/(abundance*(1+.25*cfg.mountain_detail*std::tanh(across))),2.))
        *mountain_modulation(along,across,cfg.mountain_detail);
    const double volcanic=subduction*std::exp(-std::pow((d-.8)/.5,2.))*overriding;
    const double trench=-1.2*subduction*std::exp(-std::pow((d-.25)/.25,2.))*(1-overriding);
    const double rift=-.7*div*c*belt;
    const double ridge=.6*div*(1-c)*belt;
    const double interaction=uplift+trench+rift+ridge+.55*volcanic;
    return Relief{cfg.tectonic_relief*(continental_profile(c)+interaction),cfg.tectonic_relief*interaction,volcanic};
}
}
PointResult layout_point(const Vec3& p,const std::vector<Plate>& plates,std::uint32_t crust_seed,const WorldConfig& cfg) {
    const std::size_t count=plates.size();
    std::vector<double> scores(count,0.);
    double best=-2.;
    for(std::size_t i=0;i<count;++i) {scores[i]=dot(p,plates[i].center);if(scores[i]>best) best=scores[i];}
    // Compact, continuous memberships keep distant great-circle extensions out.
    const double support=2*cfg.belt_width;
    std::vector<double> weights(count,0.);
    for(std::size_t i=0;i<count;++i) weights[i]=std::pow(std::max(0.,1-(best-scores[i])/support),3.);
    const double c=crust_value(p,crust_seed,cfg.crust_bias);
    struct Contribution {double weight,distance,convergence,divergence,shear,structure,interaction,volcanic;};
    std::vector<Contribution> contributions;
    for(std::size_t i=0;i<count;++i) {
        if(weights[i]==0.) continue;
        for(std::size_t j=i+1;j<count;++j) {
            if(weights[j]==0.) continue;
            const Vec3 normal=unit(subtracted(plates[j].center,plates[i].center));
            const double projection=std::max(-1.,std::min(1.,dot(p,normal)));
            const Vec3 raw=subtracted(p,scaled(normal,projection));
            if(dot(raw,raw)<1e-20) continue;
            const Vec3 boundary=unit(raw);
            const Motion motion=relative_motion(boundary,normal,plates[i].omega,plates[j].omega);
            const double angle=cfg.belt_width;
            const double ci=crust_value(subtracted(scaled(boundary,std::cos(angle)),scaled(normal,std::sin(angle))),crust_seed,cfg.crust_bias);
            const double cj=crust_value(added(scaled(boundary,std::cos(angle)),scaled(normal,std::sin(angle))),crust_seed,cfg.crust_bias);
            const Vec3 reference=unit(added(plates[i].center,plates[j].center));
            const double along=std::atan2(dot(boundary,cross(normal,reference)),dot(boundary,reference));
            const double across=std::asin(projection)/angle;
            const double distance=std::fabs(across)*angle*cfg.globe_radius;
            // Smoothly choose crust on this side, including across the boundary.
            const double side=.5+.5*std::tanh(across*3);
            const double here=ci*(1-side)+cj*side,there=cj*(1-side)+ci*side;
            const Relief relief=relief_at(c,distance,motion.convergence,motion.divergence,here,there,cfg,along,across);
            contributions.push_back(Contribution{weights[i]*weights[j],distance,motion.convergence,motion.divergence,
                                                 motion.shear,relief.structure,relief.interaction,relief.volcanic});
        }
    }
    Sum weight_total;
    for(const auto& item:contributions) weight_total.add(item.weight);
    const double total=weight_total.value();
    // A baseline weight fades isolated pair tails to zero without a hard cutoff.
    const double denominator=std::max(1.,total);
    Sum convergence,divergence,shear,interaction,volcanic;
    for(const auto& item:contributions) convergence.add(item.weight*item.convergence);
    for(const auto& item:contributions) divergence.add(item.weight*item.divergence);
    for(const auto& item:contributions) shear.add(item.weight*item.shear);
    for(const auto& item:contributions) interaction.add(item.weight*item.interaction);
    for(const auto& item:contributions) volcanic.add(item.weight*item.volcanic);
    std::size_t owner=0;
    for(std::size_t i=1;i<count;++i) if(scores[i]>scores[owner]) owner=i;
    // Distance to the nearest half-space edge of the owning Voronoi cell.
    double nearest=-1.;
    for(std::size_t i=0;i<count;++i) {
        if(i==owner) continue;
        const Vec3 normal=unit(subtracted(plates[i].center,plates[owner].center));
        const double edge=std::fabs(std::asin(std::max(-1.,std::min(1.,dot(p,normal)))));
        if(nearest<0. || edge<nearest) nearest=edge;
    }
    PointResult result;
    result.owner=static_cast<double>(plates[owner].id);
    result.crust=c;
    result.boundary_distance=nearest*cfg.globe_radius;
    result.convergence=convergence.value()/denominator;
    result.divergence=divergence.value()/denominator;
    result.shear=shear.value()/denominator;
    const double blended_interaction=interaction.value()/denominator;
    result.structure=cfg.tectonic_relief*continental_profile(c)+blended_interaction;
    result.interaction=blended_interaction;
    result.volcanic=volcanic.value()/denominator;
    return result;
}
namespace {
Vec3 random_point(PyRandom& rng) {
    const double y=rng.uniform(-1,1);
    const double lon=rng.uniform(-pi,pi);
    const double c=std::sqrt(1-y*y);
    return Vec3{c*std::cos(lon),y,c*std::sin(lon)};
}
std::string weighted_kind(PyRandom& rng,const WorldOptions& o) {
    const double weights[4]={o.volcanic_island_weight,o.atoll_weight,o.continental_island_weight,o.cold_island_weight};
    double cumulative[4];
    double running=0.;
    for(int i=0;i<4;++i) {running+=weights[i];cumulative[i]=running;}
    const double total=cumulative[3]+0.0;
    const double target=rng.next()*total;
    int index=0;
    while(index<3 && cumulative[index]<=target) ++index;
    static const char* kinds[4]={"volcanic","atoll","continental","cold"};
    return kinds[index];
}
std::vector<Archipelago> island_layout(const WorldConfig& cfg) {
    const WorldOptions& o=cfg.options;
    PyRandom rng(child_seed(static_cast<std::uint64_t>(cfg.seed),"ocean-archipelagos-v1"));
    std::vector<Archipelago> clusters;
    for(std::int64_t k=0;k<o.archipelago_count;++k) {
        Vec3 center=random_point(rng);
        const std::string kind=weighted_kind(rng,o);
        if(kind=="cold") {
            center=Vec3{center[0]*.4,std::copysign(.9,center[1]),center[2]*.4};
            center=unit(center);
        }
        if(rng.next()>o.archipelago_occurrence) continue;
        Archipelago cluster;
        cluster.id="ocean-"+std::to_string(k);
        cluster.kind=kind;
        cluster.direction=center;
        for(std::int64_t j=0;j<o.islands_per_cluster;++j) {
            const Vec3 q=random_point(rng);
            const double scale=o.island_radius*o.island_spacing*o.archipelago_extent*std::sqrt(static_cast<double>(j));
            const Vec3 p=unit(added(center,scaled(q,scale)));
            cluster.islands.push_back(Island{p,o.island_radius*rng.uniform(.7,1.3)});
        }
        clusters.push_back(cluster);
    }
    return clusters;
}
// Compact ocean uplifts before erosion and drainage; retain continental foundations.
std::vector<Archipelago> shape_islands(Layers& layers,const WorldConfig& cfg) {
    std::vector<Archipelago> clusters=island_layout(cfg);
    const auto n=static_cast<std::size_t>(cfg.size);
    const double span=static_cast<double>(cfg.size-1);
    layers.archipelago_relief=filled(n,0.);
    for(auto& cluster:clusters) {
        const Vec3& p=cluster.direction;
        const auto x=static_cast<std::size_t>(std::nearbyint((std::atan2(p[2],p[0])+pi)/(2*pi)*span));
        const auto z=static_cast<std::size_t>(std::nearbyint(std::acos(p[1])/pi*span));
        cluster.eligible=layers.continental[z][x]<cfg.sea_level;
    }
    for(std::size_t z=0;z<n;++z) {
        const std::size_t columns=(z==0 || z==n-1) ? 1 : n-1;
        for(std::size_t x=0;x<columns;++x) {
            const Vec3 p=direction(static_cast<std::int64_t>(x),static_cast<std::int64_t>(z),cfg.size);
            const double original=layers.structure[z][x];
            double value=original;
            for(const auto& cluster:clusters) {
                if(!cluster.eligible) continue;
                for(const auto& island:cluster.islands) {
                    const double d=angle_between(p,island.direction)/island.angular_radius;
                    if(d>=2) continue;
                    const double support=clamp01((2-d)/.7);
                    double target;
                    if(cluster.kind=="atoll")
                        target=cfg.sea_level+cfg.tectonic_relief*(.22*std::exp(-std::pow((d-.7)/.24,2.))-.07);
                    else
                        target=cfg.sea_level+cfg.tectonic_relief*((cluster.kind=="volcanic" ? .9 : .45)*std::exp(-d*d*2)-.1);
                    value=std::max(value,original+(target-original)*support);
                }
            }
            const double delta=value-original;
            layers.archipelago_relief[z][x]=delta;
            layers.structure[z][x]+=delta;layers.height[z][x]+=delta;layers.base[z][x]+=delta;
        }
        for(Grid* grid:{&layers.structure,&layers.height,&layers.base,&layers.archipelago_relief}) {
            const double first=(*grid)[z][0];
            if(z==0 || z==n-1) (*grid)[z].assign(n,first);
            else (*grid)[z][n-1]=first;
        }
    }
    return clusters;
}
}
double continental_profile(double c) {
    static const double anchors[5][2]={{0,-1.8},{.3,-1.65},{.45,-.12},{.6,.08},{1,.3}};
    for(int i=0;i<4;++i) {
        const double a=anchors[i][0],ha=anchors[i][1],b=anchors[i+1][0],hb=anchors[i+1][1];
        if(c<=b) {
            const double t=clamp01((c-a)/(b-a));
            return ha+(hb-ha)*t*t*(3-2*t);
        }
    }
    return anchors[4][1];
}
double crust_value(const Vec3& p,std::uint32_t seed,double bias) {
    // Continental affinity independent of plate identity: plates can contain both.
    double v=.5+1.65*perlin3(p[0]*1.4+.17,p[1]*1.4+.39,p[2]*1.4+.71,seed)+bias*.5;
    v=clamp01(v);
    return v*v*(3-2*v);
}
std::vector<Plate> make_plates(std::uint32_t seed,std::int64_t count) {
    PyRandom rng(seed);
    std::vector<Plate> plates;
    const double cutoff=std::cos(.55*std::sqrt(4*pi/static_cast<double>(count)));
    for(std::int64_t attempt=0;attempt<count*1000;++attempt) {
        const Vec3 center=unit(Vec3{rng.gauss(0,1),rng.gauss(0,1),rng.gauss(0,1)});
        bool crowded=false;
        for(const auto& plate:plates) if(dot(center,plate.center)>cutoff) {crowded=true;break;}
        if(crowded) continue;
        const Vec3 axis=unit(Vec3{rng.gauss(0,1),rng.gauss(0,1),rng.gauss(0,1)});
        const double speed=rng.uniform(.25,1);
        plates.push_back(Plate{static_cast<std::int64_t>(plates.size()),center,scaled(axis,speed)});
        if(static_cast<std::int64_t>(plates.size())==count) return plates;
    }
    throw Error("STATE_CAPACITY");
}
TectonicResult generate_tectonics(const WorldConfig& cfg,const SphereGrid& grid,Layers& layers) {
    TectonicResult result;
    const auto n=static_cast<std::size_t>(cfg.size);
    const double r=cfg.globe_radius;
    result.layout_seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"plates",static_cast<std::uint64_t>(cfg.layout_variation));
    result.crust_seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"crust",static_cast<std::uint64_t>(cfg.layout_variation));
    result.detail_seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"surface",static_cast<std::uint64_t>(cfg.detail_variation));
    result.plates=make_plates(result.layout_seed,cfg.plate_count);
    std::vector<std::vector<PointResult>> records;
    for(Grid* g:{&layers.plates,&layers.crust,&layers.boundary_distance,&layers.convergence,&layers.divergence,&layers.shear})
        *g=filled(n,0.);
    for(std::size_t z=0;z<n;++z) {
        const std::size_t columns=(z==0 || z==n-1) ? 1 : n-1;
        std::vector<PointResult> row;
        for(std::size_t x=0;x<columns;++x)
            row.push_back(layout_point(direction(static_cast<std::int64_t>(x),static_cast<std::int64_t>(z),cfg.size),
                                       result.plates,result.crust_seed,cfg));
        if(z==0 || z==n-1) {const PointResult first=row[0];row.assign(n,first);}
        else {const PointResult first=row[0];row.push_back(first);}
        for(std::size_t x=0;x<n;++x) {
            layers.plates[z][x]=row[x].owner;
            layers.crust[z][x]=row[x].crust;
            layers.boundary_distance[z][x]=row[x].boundary_distance;
            layers.convergence[z][x]=row[x].convergence;
            layers.divergence[z][x]=row[x].divergence;
            layers.shear[z][x]=row[x].shear;
        }
        records.push_back(row);
    }
    layers.base=filled(n,0.);layers.height=filled(n,0.);
    if(cfg.phase>=2) {
        layers.structure=filled(n,0.);layers.interaction=filled(n,0.);layers.volcanic=filled(n,0.);
        for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x) {
            layers.structure[z][x]=records[z][x].structure;
            layers.interaction[z][x]=records[z][x].interaction;
            layers.volcanic[z][x]=records[z][x].volcanic;
        }
        layers.continental=filled(n,0.);
        for(std::size_t z=0;z<n;++z) for(std::size_t x=0;x<n;++x)
            layers.continental[z][x]=cfg.tectonic_relief*continental_profile(layers.crust[z][x]);
        layers.base=cfg.phase==2 ? layers.continental : layers.structure;
        layers.height=layers.structure;
    }
    if(cfg.world_recipe && cfg.phase>=2) result.archipelagos=shape_islands(layers,cfg);
    const double step=2*pi*r/static_cast<double>(cfg.size-1);
    result.spacing_m=step;
    std::vector<double> frequencies;
    for(std::int64_t k=0;k<cfg.octaves;++k) {
        const double frequency=std::pow(2.,static_cast<double>(k))/cfg.wavelength;
        if(cfg.wavelength/std::pow(2.,static_cast<double>(k))>=2*step) frequencies.push_back(frequency);
    }
    result.resolved_octaves=cfg.phase>=3 ? static_cast<std::int64_t>(frequencies.size()) : 0;
    if(cfg.phase>=3) {
        layers.noise=filled(n,0.);
        for(std::size_t z=0;z<n;++z) {
            const std::size_t columns=(z==0 || z==n-1) ? 1 : n-1;
            std::vector<double> row;
            for(std::size_t x=0;x<columns;++x) {
                const Vec3 p=direction(static_cast<std::int64_t>(x),static_cast<std::int64_t>(z),cfg.size);
                double value=0.;
                for(std::size_t k=0;k<frequencies.size();++k) {
                    const double f=frequencies[k];
                    const double noise=std::max(-1.,std::min(1.,perlin3(p[0]*r*f+.173,p[1]*r*f+.391,p[2]*r*f+.719,
                        static_cast<std::int64_t>(result.detail_seed)+static_cast<std::int64_t>(k)*1013)));
                    value+=cfg.amplitude*std::pow(.5,static_cast<double>(k))*((1-cfg.ridge)*noise+cfg.ridge*(std::pow(1-std::fabs(noise),3.)-.5));
                }
                // Roughness follows boundary influence, with a small interior floor.
                const double influence=std::min(1.,layers.convergence[z][x]+layers.divergence[z][x]+layers.shear[z][x]);
                row.push_back(value*(.2+.8*influence));
            }
            const double first=row[0];
            if(z==0 || z==n-1) row.assign(n,first);
            else row.push_back(first);
            layers.noise[z]=row;
            for(std::size_t x=0;x<n;++x) layers.height[z][x]=layers.structure[z][x]+row[x];
        }
        layers.surface=layers.height;
    }
    if(cfg.phase>=4)
        result.sediment=erode(layers.height,r,cfg.sea_level,cfg.erosion_passes,cfg.erosion_strength,grid,layers);
    if(cfg.phase>=4) layers.base=layers.surface;
    if(cfg.phase>=2) measure_globe(layers.height,r,cfg.radius,layers.slope,layers.tpi);
    return result;
}
}
