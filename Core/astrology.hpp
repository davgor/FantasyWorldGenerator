#pragma once
#include "globe.hpp"
#include "layers.hpp"
#include "magic.hpp"
#include <array>
#include <cstdint>
#include <string>
namespace fantasy_world_generator {
// The reference moon (Sim/icarus_sim/terrain_astrology.py): one body, two hemispheres,
// eight school regions, three seeded integer-day cycles with a coprime preference.
// Every quantity is a cycle fraction or a unit vector, never a metre, and the tide
// uses only sin, cos, products, sums, min and max, so this mirror is bit-exact.
constexpr std::int64_t days_per_month=30,months_per_year=12,days_per_year=360;
struct Moon {
    std::int64_t synodic=0,spin=0,nod=0;              // periods in days
    std::int64_t synodic_offset=0,spin_offset=0,nod_offset=0;
    double tilt_max_degrees=0.;
    std::int64_t great_year_days=0;
};
// Draw order is part of the contract: synodic, spin (redrawn until coprime), nod
// (redrawn until coprime with both), the three offsets, then the tilt.
Moon seed_moon(std::uint64_t seed);
// Region centre of a school in the moon frame, in school order.
Vec3 moon_region(std::size_t school);
// Per-school strength multiplier on an integer day, in school order.
std::array<double,school_count> lunar_tide(const Moon& moon,std::int64_t day);
// The nod in degrees on a day: positive leans the still hemisphere toward the world.
double lunar_nod_degrees(const Moon& moon,std::int64_t day);
// How far each cell's magic sways: instability and shores, from fields already in 0..1.
Grid lunar_sensitivity(const Layers& layers,std::int64_t size);
}
