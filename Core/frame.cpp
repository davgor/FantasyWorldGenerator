#include "frame.hpp"
#include "genesis.hpp"
#include <cmath>
namespace fantasy_world_generator {
namespace {
constexpr double deg_to_rad=pi/180.0;
void require(bool ok) {if(!ok) throw Error("INVALID_INPUT");}
double radial_distance(double radius,double height) {
    const double distance=radius+height;
    require(distance>0);
    return distance;
}
}
TangentFrame tangent_frame(double latitude_degrees,double longitude_degrees) {
    require(latitude_degrees>=-90 && latitude_degrees<=90);
    require(longitude_degrees>=-180 && longitude_degrees<=180);
    const double lat=latitude_degrees*deg_to_rad;
    const double lon=(longitude_degrees==180 ? -180.0 : longitude_degrees)*deg_to_rad;
    TangentFrame frame;
    frame.up=Vec3{std::cos(lat)*std::cos(lon),std::sin(lat),std::cos(lat)*std::sin(lon)};
    if(std::fabs(latitude_degrees)==90) frame.up=Vec3{0.,latitude_degrees>0 ? 1. : -1.,0.};
    frame.east=Vec3{-std::sin(lon),0.,std::cos(lon)};
    frame.north=Vec3{-std::sin(lat)*std::cos(lon),std::cos(lat),-std::sin(lat)*std::sin(lon)};
    return frame;
}
Vec3 globe_position(double latitude_degrees,double longitude_degrees,double radius_m,double height_m) {
    require(radius_m>0);
    const TangentFrame frame=tangent_frame(latitude_degrees,longitude_degrees);
    const double distance=radial_distance(radius_m,height_m);
    return Vec3{distance*frame.up[0],distance*frame.up[1],distance*frame.up[2]};
}
Vec3 local_position(const Vec3& position_m,double latitude_degrees,double longitude_degrees,
                    double radius_m,double origin_height_m) {
    require(radius_m>0);
    const TangentFrame frame=tangent_frame(latitude_degrees,longitude_degrees);
    const double distance=radial_distance(radius_m,origin_height_m);
    Vec3 delta{};
    for(int i=0;i<3;++i) delta[i]=position_m[i]-distance*frame.up[i];
    return Vec3{dot(delta,frame.east),dot(delta,frame.up),dot(delta,frame.north)};
}
UnrealVector unreal_centimetres(const Vec3& local_east_up_north) {
    // Lengths scale once, here, and the axes permute to Unreal's left-handed Z-up.
    return UnrealVector{local_east_up_north[0]*centimetres_per_metre,
                        local_east_up_north[2]*centimetres_per_metre,
                        local_east_up_north[1]*centimetres_per_metre};
}
UnrealVector unreal_axis(const Vec3& east_up_north) {
    return UnrealVector{east_up_north[0],east_up_north[2],east_up_north[1]};
}
Vec3 tile_direction(std::int64_t level,std::int64_t x,std::int64_t z) {
    require(level>=1 && level<=24);
    const std::int64_t rows=static_cast<std::int64_t>(1)<<level;
    require(x>=0 && x<=2*rows && z>=0 && z<=rows);
    const double latitude=90-180*static_cast<double>(z)/static_cast<double>(rows);
    const double longitude=-180+180*static_cast<double>(x%(2*rows))/static_cast<double>(rows);
    return tangent_frame(latitude,longitude).up;
}
}
