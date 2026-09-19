#pragma once
#include "cityplan.hpp"
#include "humans.hpp"
#include "nests.hpp"
#include "ruins.hpp"
#include "society.hpp"
#include "founding.hpp"
#include "world.hpp"
#include <array>
#include <string>
#include <vector>
namespace fantasy_world_generator {
// The engine-facing scene: positions are globe-centred metres, Y north, X at latitude
// zero longitude zero, matching the reference world_scene contract. Heights come from
// the shared detailed sampling, so anything here meets the terrain the consumer draws.
struct RegionalRoad {
    std::string id;
    std::size_t route_index=0;
    std::vector<Vec3> positions_m;
    std::vector<std::pair<std::size_t,std::size_t>> bridge_candidates;
};
struct CityAnchor {
    std::string id,population_profile,asset_id;
    std::size_t node=0;
    Vec3 direction{},position_m{};
    double height_m=0.,suitability=0.;
    bool founding_capital=false;
};
// One building a settlement planner placed: a real, dimensioned, rotated footprint
// standing on its own ground plane, not a reserved grid node. This is what
// world_scene.build_scene emits and what an engine actually draws.
struct SceneBuilding {
    // `<settlement>:<plot>`, the reference's own composite id.
    std::string id;
    // "city", "hamlet" or "castle": which planner placed it.
    std::string settlement_kind;
    // The settlement it belongs to, as the generator names it. The reference keys this
    // city_uid, hamlet_id or fortress_id by kind; one field carries all three.
    std::string settlement_id,plot_id;
    // Registry identity, already namespaced, e.g. building.water_point.
    std::string asset_id;
    // Globe-centred metres, Y north, exactly as the scene emits them: the plot centre
    // on the ground elevation its planner chose, and the four corners around it.
    Vec3 position_m{},up{},width_axis{},depth_axis{};
    std::array<Vec3,4> footprint_m{};
    // Heading on the ground in degrees, as the planner drew it.
    double rotation_degrees=0.;
    // The authored size in metres. This is the thing a grid node never carried.
    double width_m=0.,depth_m=0.,height_m=0.;
};
struct WorldScene {
    std::vector<RegionalRoad> regional_roads;
    std::vector<CityAnchor> cities;
    // Empty until plan_settlement_buildings runs over the finished world; see the note
    // on that function for why it is not part of populate_world.
    std::vector<SceneBuilding> buildings;
    // Empty when `buildings` is the planners' own output. Otherwise the reason there is
    // none: the settlement planners read four shipped JSON catalogues from disk, and a
    // host that cannot reach them gets a populated world and this sentence rather than
    // an exception out of a stage that used to be pure arithmetic.
    std::string buildings_status;
    double radius_m=0.;
};
// Densifies each route onto the surface at roughly four metre spacing, the same
// interval the reference uses, so a drawn road follows the ground rather than cutting
// through it. City anchors are the site nodes: street plans are a later slice, so no
// building is invented here.
WorldScene build_scene(const WorldEnvelope& world,const std::vector<FoundedCity>& sites,
                       const std::vector<Road>& roads,const SettlementFields& fields);
// Everything the civilizations add to a generated world: capacity fields, founded
// cities, the road network between them and the scene a consumer materializes.
struct PopulatedWorld {
    SettlementFields fields;
    FoundingResult founding;
    std::vector<Road> roads;
    WorldScene scene;
    // One plan per founded city, in founding order: which pack it builds from and
    // which nodes its districts and buildings claim. This is the reference's OLD
    // grid-node district plan (city_layout), which is a different thing from the
    // metre-accurate plot geometry the city planner draws; both exist in the
    // reference and both exist here. The plots live in scene.buildings.
    std::vector<CityPlan> plans;
    // Credited residents per city, which is what sizes the districts above.
    std::vector<PopulationEstimate> residents;
    // Hamlets, fortresses, cultures and the catchment fields around each city.
    Humans humans;
    // Coastal landings and the specialist landmarks that keep away from cities.
    Society society;
    // Habitat anchors: hunting grounds and monster territory, placed independently.
    Habitats nests;
    // Every city the world has lost, in the order it lost them. A ruin's node is
    // never resettled, so this outlives the age that created it.
    std::vector<Ruin> ruins;
};
// What a rebuild after an age inherits: the cities that survived, the ruins their
// neighbours became, and the founding history those rounds must not repeat.
struct PopulateContext {
    std::vector<FoundedCity> survivors;
    std::vector<std::size_t> forbidden;
    std::vector<std::string> bonus_used,used_civilizations;
    double start_year=0.;
    std::int64_t age=0;
};
PopulatedWorld populate_world(WorldEnvelope& world,const Catalogues& catalogues,
                              const PopulateContext& context={});
// The building slice of world_scene.build_scene: every city, hamlet and castle is
// packed in local metres by its own planner, and every plot in every plan becomes a
// dimensioned, rotated, ground-anchored footprint in `populated.scene.buildings`.
//
// Why this is not inside populate_world. The reference runs fill_cities, fill_hamlets
// and fill_castles once, at its LAST stage, after both age transitions have settled
// (terrain_history.py:356 and 536 are the two earlier civilization rounds; stage 16 is
// where the planners run). populate_world is the civilization round, and advance_age
// calls it again for every age, so planning inside it would both cost the packing work
// two or three times over and publish plots for cities an age is about to ruin. A host
// calls this once, on the world it is going to show.
//
// Reads four shipped JSON catalogues through the planner modules
// (settlementpresets::set_registry_path, cityshapes::set_catalogue_path and
// castleplanner::set_castles_path name three of them; buildings.json is read beside the
// first). A failure to read or validate any of them, and any error the planners raise,
// is recorded in `populated.scene.buildings_status` and leaves `buildings` empty rather
// than propagating: a world whose data files are missing is still a populated world.
void plan_settlement_buildings(const WorldEnvelope& world,const Catalogues& catalogues,
                               PopulatedWorld& populated);
}
