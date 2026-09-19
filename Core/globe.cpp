#include "globe.hpp"
#include <cmath>
namespace fantasy_world_generator {
namespace {
constexpr double inv_root2=0.7071067811865476;  // 2**-.5
constexpr double rad_to_deg=180.0/pi;   // math.degrees multiplies by this constant
}
double python_mod(double value,double modulus) {
    double remainder=std::fmod(value,modulus);
    if(remainder!=0. && ((remainder<0.)!=(modulus<0.))) remainder+=modulus;
    return remainder;
}
void Sum::add(double x) {
    const double t=total+x;
    if(std::fabs(total)>=std::fabs(x)) compensation+=(total-t)+x;
    else compensation+=(x-t)+total;
    total=t;
}
double python_hypot(const double* values,std::size_t count) {
    double max=0.;
    for(std::size_t i=0;i<count;++i) {
        const double value=std::fabs(values[i]);
        if(std::isnan(value)) return value;
        max=std::max(max,value);
    }
    if(std::isinf(max) || max==0. || count<=1) return max;
    int max_e=0;
    std::frexp(max,&max_e);
    const double scale=std::ldexp(1.,-max_e);
    double csum=1.,frac1=0.,frac2=0.;
    for(std::size_t i=0;i<count;++i) {
        const double value=std::fabs(values[i]);
        const double t=value*scale;
        const double z=t*t,zz=std::fma(t,t,-z);        // lossless square
        const double sum=csum+z,low=(csum-sum)+z;      // lossless addition
        csum=sum;frac1+=zz;frac2+=low;
    }
    double h=std::sqrt(csum-1.+(frac1+frac2));
    const double z=-h*h,zz=std::fma(-h,h,-z);
    const double sum=csum+z,low=(csum-sum)+z;
    csum=sum;frac1+=zz;frac2+=low;
    h+=(csum-1.+(frac1+frac2))/(2.*h);
    return h/scale;
}
double python_hypot(double x,double y) {
    const double values[2]={x,y};
    return python_hypot(values,2);
}
double dot(const Vec3& a,const Vec3& b) {
    Sum sum;
    for(int i=0;i<3;++i) sum.add(a[i]*b[i]);
    return sum.value();
}
Vec3 cross(const Vec3& a,const Vec3& b) {
    return Vec3{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
}
Vec3 unit(const Vec3& p) {
    const double norm=std::sqrt(dot(p,p));
    return Vec3{p[0]/norm,p[1]/norm,p[2]/norm};
}
Vec3 direction(std::int64_t x,std::int64_t z,std::int64_t n) {
    if(z==0) return Vec3{0.,1.,0.};
    if(z==n-1) return Vec3{0.,-1.,0.};
    const double span=static_cast<double>(n-1);
    const double lon=2*pi*static_cast<double>(((x%(n-1))+(n-1))%(n-1))/span-pi;
    const double lat=pi/2-pi*static_cast<double>(z)/span;
    return Vec3{std::cos(lat)*std::cos(lon),std::sin(lat),std::cos(lat)*std::sin(lon)};
}
double perlin3(double x,double y,double z,std::int64_t seed) {
    const double fx=std::floor(x),fy=std::floor(y),fz=std::floor(z);
    const auto ix=static_cast<std::int64_t>(fx),iy=static_cast<std::int64_t>(fy),iz=static_cast<std::int64_t>(fz);
    const double f0=x-fx,f1=y-fy,f2=z-fz;
    const double b0=std::pow(f0,3.)*(f0*(f0*6-15)+10);
    const double b1=std::pow(f1,3.)*(f1*(f1*6-15)+10);
    const double b2=std::pow(f2,3.)*(f2*(f2*6-15)+10);
    const double weight0[2]={1-b0,b0},weight1[2]={1-b1,b1},weight2[2]={1-b2,b2};
    using u64=std::uint64_t;
    const u64 hash_x=static_cast<u64>(ix)*374761393u,hash_y=static_cast<u64>(iy)*668265263u;
    const u64 hash_z=static_cast<u64>(iz)*2147483647u+static_cast<u64>(seed)*1442695041u;
    double value=0.;
    for(int a=0;a<2;++a) {
        const u64 hash_a=hash_x+static_cast<u64>(a)*374761393u+hash_y;
        const double offset0=f0-a,blend_a=weight0[a];
        for(int b=0;b<2;++b) {
            const u64 hash_b=hash_a+static_cast<u64>(b)*668265263u+hash_z;
            const double offset1=f1-b,blend_ab=blend_a*weight1[b];
            for(int c=0;c<2;++c) {
                std::uint32_t h=static_cast<std::uint32_t>((hash_b+static_cast<u64>(c)*2147483647u)&0xffffffffu);
                h=static_cast<std::uint32_t>((h^(h>>13))*1274126177u);
                h^=h>>16;
                // Twelve unit edge gradients of a cube.
                const unsigned axis=h%3u,u=(axis+1)%3u,v=(axis+2)%3u;
                const double offsets[3]={offset0,offset1,f2-c};
                const double product=(offsets[u]*((h&4u)?1.:-1.)+offsets[v]*((h&8u)?1.:-1.))*inv_root2;
                value+=product*(blend_ab*weight2[c]);
            }
        }
    }
    return value;
}
double sample(const Grid& h,const Vec3& p) {
    const auto n=static_cast<std::int64_t>(h.size());
    const double span=static_cast<double>(n-1);
    double x=python_mod((std::atan2(p[2],p[0])+pi)/(2*pi)*span,span);
    double z=(pi/2-std::asin(std::max(-1.,std::min(1.,p[1]))))/pi*span;
    z=std::max(0.,std::min(span,z));
    const auto ix=static_cast<std::size_t>(x);
    const auto iz=static_cast<std::size_t>(z);
    const double fx=x-static_cast<double>(ix),fz=z-static_cast<double>(iz);
    const std::size_t jz=std::min(static_cast<std::size_t>(n-1),iz+1);
    return ((1-fx)*h[iz][ix]+fx*h[iz][ix+1])*(1-fz)+((1-fx)*h[jz][ix]+fx*h[jz][ix+1])*fz;
}
void measure_globe(const Grid& h,double radius,double neighborhood,Grid& slope,Grid& tpi) {
    const auto n=static_cast<std::int64_t>(h.size());
    const double angle=pi/static_cast<double>(n-1);
    const double ring=std::min(pi/2,std::max(angle,neighborhood/radius));
    slope.clear();tpi.clear();
    for(std::int64_t z=0;z<n;++z) {
        std::vector<double> sr,tr;
        const std::int64_t columns=(z==0 || z==n-1) ? 1 : n-1;
        for(std::int64_t x=0;x<columns;++x) {
            const Vec3 p=direction(x,z,n);
            const double norm=python_hypot(p[0],p[2]);
            const Vec3 e=norm>1e-10 ? Vec3{-p[2]/norm,0,p[0]/norm} : Vec3{1,0,0};
            const Vec3 v{p[1]*e[2]-p[2]*e[1],p[2]*e[0]-p[0]*e[2],p[0]*e[1]-p[1]*e[0]};
            auto around=[&](double theta,double azimuth) {
                const double c=std::cos(theta),s=std::sin(theta),ca=std::cos(azimuth),sa=std::sin(azimuth);
                Vec3 q{};
                for(int j=0;j<3;++j) q[j]=p[j]*c+(e[j]*ca+v[j]*sa)*s;
                return sample(h,q);
            };
            const double gx=(around(angle,0)-around(angle,pi))/(2*radius*angle);
            const double gy=(around(angle,pi/2)-around(angle,3*pi/2))/(2*radius*angle);
            sr.push_back(std::atan(python_hypot(gx,gy))*rad_to_deg);
            Sum ring_total;
            for(int j=0;j<8;++j) ring_total.add(around(ring,j*pi/4));
            tr.push_back(h[static_cast<std::size_t>(z)][static_cast<std::size_t>(x)]-ring_total.value()/8);
        }
        if(z==0 || z==n-1) {
            sr.assign(static_cast<std::size_t>(n),sr[0]);
            tr.assign(static_cast<std::size_t>(n),tr[0]);
        } else {
            sr.push_back(sr[0]);tr.push_back(tr[0]);
        }
        slope.push_back(sr);tpi.push_back(tr);
    }
}
}
