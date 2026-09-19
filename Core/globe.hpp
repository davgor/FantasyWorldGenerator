#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>
namespace fantasy_world_generator {
using Grid=std::vector<std::vector<double>>;
// CPython 3.12 sums float sequences with Neumaier compensation, so every ported
// sum() uses this accumulator; plain left-to-right addition drifts by an ulp.
struct Sum {
    double total=0.,compensation=0.;
    void add(double x);
    double value() const {return total+compensation;}
};
using Vec3=std::array<double,3>;
constexpr double pi=3.14159265358979323846;
// Latitude/longitude node of the export grid as a unit globe direction.
Vec3 direction(std::int64_t x,std::int64_t z,std::int64_t n);
// Spherical gradient noise of the reference generator; the integer hash and the
// left-to-right float products are the ones the Python oracle evaluates.
double perlin3(double x,double y,double z,std::int64_t seed);
// Bilinear read of a lat/lon grid at a globe direction.
double sample(const Grid& h,const Vec3& p);
double python_mod(double value,double modulus);
// math.hypot is CPython's own scaled double-length norm, not the libm routine.
double python_hypot(double x,double y);
double python_hypot(const double* values,std::size_t count);
Vec3 unit(const Vec3& p);
double dot(const Vec3& a,const Vec3& b);
Vec3 cross(const Vec3& a,const Vec3& b);
// Reference-sphere grade in degrees and eight-point geodesic-ring TPI in metres.
void measure_globe(const Grid& h,double radius,double neighborhood,Grid& slope,Grid& tpi);
}
