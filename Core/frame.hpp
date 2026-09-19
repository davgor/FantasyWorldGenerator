#pragma once
#include "globe.hpp"
namespace fantasy_world_generator {
constexpr std::int64_t coordinate_version=1;
// Source frames are right-handed metres. Unreal is left-handed, Z-up centimetres:
// east becomes +X, north becomes +Y, radial up becomes +Z, lengths scale by 100 once
// and copied triangle winding reverses. Core keeps plain vectors; no engine types.
struct TangentFrame {Vec3 up{},east{},north{};};
TangentFrame tangent_frame(double latitude_degrees,double longitude_degrees);
Vec3 globe_position(double latitude_degrees,double longitude_degrees,double radius_m,double height_m);
// (east, up, north) metres of a globe point relative to a tangent origin.
Vec3 local_position(const Vec3& position_m,double latitude_degrees,double longitude_degrees,
                    double radius_m,double origin_height_m);
// Unreal world centimetres from the source tangent triple.
struct UnrealVector {double x_cm=0.,y_cm=0.,z_cm=0.;};
UnrealVector unreal_centimetres(const Vec3& local_east_up_north);
// Unit axes permute without the length scale.
UnrealVector unreal_axis(const Vec3& east_up_north);
Vec3 tile_direction(std::int64_t level,std::int64_t x,std::int64_t z);
}
