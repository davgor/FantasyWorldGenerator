#include "astrology.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <numeric>
namespace fantasy_world_generator {
namespace {
constexpr double deg_to_rad=pi/180.0;
constexpr double tide_floor=.7,tide_gain=1.1,tide_min=.5,tide_max=1.8;
constexpr int redraws=8;
// Still hemisphere (+45) carries radiant, water, earth, umbral at longitudes 0, 90,
// 180, 270; the restless hemisphere (-45) carries weave, fire, air, infernal. The
// school order is weave, umbral, infernal, radiant, fire, water, earth, air.
constexpr double region_latitude[school_count]={-45.,45.,-45.,45.,-45.,45.,45.,-45.};
constexpr double region_quarter[school_count]={0.,3.,3.,0.,1.,1.,2.,2.};
double fraction(std::int64_t day,std::int64_t offset,std::int64_t period) {
    return static_cast<double>((day+offset)%period)/static_cast<double>(period);
}
}

Vec3 moon_region(std::size_t school) {
    const double latitude=region_latitude[school]*deg_to_rad;
    const double longitude=region_quarter[school]*90*deg_to_rad;
    return Vec3{std::cos(latitude)*std::cos(longitude),std::sin(latitude),std::cos(latitude)*std::sin(longitude)};
}

Moon seed_moon(std::uint64_t seed) {
    PyRandom rng(child_seed(seed,"astrology-v1"));
    Moon moon;
    moon.synodic=rng.randint(26,34);
    moon.spin=rng.randint(15,63);
    for(int i=0;i<redraws;++i) {
        if(std::gcd(moon.spin,moon.synodic)==1) break;
        moon.spin=rng.randint(15,63);
    }
    moon.nod=rng.randint(17,37);
    for(int i=0;i<redraws;++i) {
        if(std::gcd(moon.nod,moon.synodic)==1 && std::gcd(moon.nod,moon.spin)==1) break;
        moon.nod=rng.randint(17,37);
    }
    moon.synodic_offset=rng.randint(0,moon.synodic-1);
    moon.spin_offset=rng.randint(0,moon.spin-1);
    moon.nod_offset=rng.randint(0,moon.nod-1);
    moon.tilt_max_degrees=rng.uniform(10.,35.);
    moon.great_year_days=std::lcm(std::lcm(moon.synodic,moon.spin),moon.nod);
    return moon;
}

double lunar_nod_degrees(const Moon& moon,std::int64_t day) {
    return moon.tilt_max_degrees*std::sin(2*pi*fraction(day,moon.nod_offset,moon.nod));
}

std::array<double,school_count> lunar_tide(const Moon& moon,std::int64_t day) {
    const double phase=2*pi*fraction(day,moon.synodic_offset,moon.synodic);
    const double spin=2*pi*fraction(day,moon.spin_offset,moon.spin);
    const double nod=lunar_nod_degrees(moon,day);
    const double sun_x=std::cos(phase),sun_z=std::sin(phase);
    const double cs=std::cos(spin),ss=std::sin(spin);
    const double cn=std::cos(nod*deg_to_rad),sn=std::sin(nod*deg_to_rad);
    std::array<double,school_count> factors{};
    for(std::size_t school=0;school<school_count;++school) {
        const Vec3 c=moon_region(school);
        double x=c[0],y=c[1],z=c[2];
        // Spin about the polar axis, then lean the still hemisphere toward +x: the
        // same two rotations, in the same order and association, as the reference.
        const double xs=x*cs+z*ss;
        const double zs=-x*ss+z*cs;
        x=xs;z=zs;
        const double xn=x*cn+y*sn;
        const double yn=-x*sn+y*cn;
        x=xn;y=yn;
        const double visible=std::max(0.,x);
        const double lit=std::max(0.,x*sun_x+z*sun_z);
        factors[school]=std::min(tide_max,std::max(tide_min,tide_floor+tide_gain*visible*lit));
    }
    return factors;
}

Grid lunar_sensitivity(const Layers& layers,std::int64_t size) {
    const std::size_t n=static_cast<std::size_t>(size);
    Grid grid=filled(n,0.);
    for(std::size_t z=0;z<n;++z)
        for(std::size_t x=0;x<n;++x) {
            double total=0.;
            for(std::size_t school=0;school<school_count;++school)
                if(!layers.instability[school].empty()) total+=layers.instability[school][z][x];
            const double water=layers.water_type.empty()?0.:layers.water_type[z][x];
            const double exposure=layers.coastal_exposure.empty()?0.:layers.coastal_exposure[z][x];
            const double shore=water==2.?1.:exposure;
            grid[z][x]=std::min(1.,std::max(0.,.2+.5*total+.3*shore));
        }
    return grid;
}
}
