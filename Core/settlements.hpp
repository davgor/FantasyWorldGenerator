#pragma once
#include "config.hpp"
#include "hydrology.hpp"
#include "layers.hpp"
#include "profiles.hpp"
#include <map>
#include <string>
#include <vector>
namespace fantasy_world_generator {
// Which landmass a node belongs to, and how big that landmass is.
struct LandmassContext {double area_m2=0.,fraction=0.;bool largest=false;};
std::vector<LandmassContext> landmass_context(const SphereGrid& grid,const std::vector<double>& water);
// Magical biome identity per cell, or an empty string where no school dominates.
std::vector<std::string> biome_variants(const Layers& layers,const SphereGrid& grid);
// Natural food yield and the irrigated surplus a people can reach.
struct Farming {double natural=0.,supported=0.;};
Farming farming_potential(const Profile& profile,double slope,double temperature,double moisture,
                          double flood,double freshwater_distance,double adaptation);
// Per-people suitability, productive capacity and the derived population budget.
struct SpeciesField {
    std::vector<double> suitability,potential;
    std::vector<std::size_t> candidates;
    std::vector<double> support_reach;   // empty unless the people supports outside its habitat
};
struct PopulationBudget {
    std::int64_t world_cap=0;
    // How many cities the ground can hold at the settlement spacing, and the land
    // that figure is measured over. The ceiling on city counts is this, not a number.
    std::int64_t spacing_ceiling=0;
    // The ceiling actually in force: the ground's packing where the world infers its
    // own quotas, the caller's count where it does not, and zero where the caller
    // asked for no cities at all. That last case is not "no ceiling": a diaspora
    // bonus exists to waive a zero quota, so without a real zero here it would settle
    // a world that was asked to stay empty.
    std::int64_t city_limit=0;
    double habitable_km2=0.;
    std::map<std::string,std::int64_t> allowances,quotas;
    std::map<std::string,double> weighted_habitat_km2,shares;
};
struct SettlementFields {
    std::map<std::string,SpeciesField> species;
    PopulationBudget budget;
    std::vector<double> resource,flood,freshwater_distance,suitability;
};
// Step (a) and (b) of the placement port: the fields and the budget, before any site
// is chosen. Reads the stage-nine layers and the authoring catalogue.
SettlementFields evaluate_settlement_fields(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                                            const Catalogues& catalogues,Layers& layers);
}
