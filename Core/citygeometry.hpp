#pragma once
#include "globe.hpp"
#include <cstdint>
#include <map>
#include <set>
#include <utility>
#include <vector>
namespace fantasy_world_generator {
// One cell of a settlement's local four-metre raster, as (x, z) column and row.
using Cell=std::pair<std::int64_t,std::int64_t>;
// The street network of one settlement: the cells a road covers, and the ordered
// centrelines that reached each destination.
struct RoadNetwork {
    std::set<Cell> roads;
    std::vector<std::vector<Cell>> paths;
};
// Seeded terrain routes over a settlement's buildable cells, in metres.
//
// `height` is the ground elevation of every cell in `valid`; the reference passes a
// dict's lookup, so a map is the same contract. `spacing_cells` is the street spacing
// in cells, `required` are gate cells that must be reached if they are reachable at
// all, and `branch_floor` is the least number of destinations to grow towards.
RoadNetwork grow_roads(const std::set<Cell>& valid,const std::map<Cell,double>& height,
                       std::int64_t size,std::uint64_t seed,double spacing_cells,
                       const std::vector<Cell>& required={},std::int64_t branch_floor=12);
// The four rotated corners of a plot, in the reference's winding order.
std::vector<std::pair<double,double>> corners(double x,double z,double w,double d,double angle);
// Conservative rasterization of a rotated plot to cell indices. The hot path of the
// city planner: roughly a million calls per world.
std::set<Cell> footprint_cells(double x,double z,double w,double d,double angle,double half,
                               double cell=4.);
}
