// Original material owned by David Gorden; see the repository LICENSE.
//
// Guards the temporary mirror in FantasyWorldGeneratorFrame.h against silent drift from Core.
// No Core translation unit is linked here: only genesis.hpp is read, so this file
// adds compile-time checks without making the module depend on Core objects.
//
// When ML-03e compiles Core into this module, delete the mirror and these asserts.

#include "FantasyWorldGeneratorFrame.h"

#ifndef FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT 0
#endif

#if FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT

#include "genesis.hpp"

static_assert(FantasyWorldGenerator::SupportedRecipeVersion == fantasy_world_generator::genesis_recipe,
	"mirrored recipe version drifted from Core");
static_assert(FantasyWorldGenerator::MaximumSeed == fantasy_world_generator::max_seed,
	"mirrored seed bound drifted from Core");
static_assert(FantasyWorldGenerator::MinimumRasterSize == fantasy_world_generator::min_grid,
	"mirrored minimum raster size drifted from Core");
static_assert(FantasyWorldGenerator::MaximumRasterSize == fantasy_world_generator::max_grid,
	"mirrored maximum raster size drifted from Core");
static_assert(FantasyWorldGenerator::UnrealCentimetresPerMetre == static_cast<double>(fantasy_world_generator::centimetres_per_metre),
	"mirrored metre-to-centimetre scale drifted from Core");

#endif
