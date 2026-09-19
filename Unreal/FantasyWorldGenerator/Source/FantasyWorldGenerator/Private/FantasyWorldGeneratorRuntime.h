// Original material owned by David Gorden; see the repository LICENSE.
//
// Core state held by the subsystem. Core/ types never appear in a public UObject
// header, so the engine-independent generator and the UObject layer stay separable.

#pragma once

#include "CoreMinimal.h"

#if FANTASY_WORLD_GENERATOR_CORE_LINKED
#include "frame.hpp"
#include "registry.hpp"
#include "ages.hpp"
#include "scene.hpp"
#include "world.hpp"
#endif

namespace FantasyWorldGeneratorRuntime
{
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	class FWorldState
	{
	public:
		bool bHasWorld = false;
		fantasy_world_generator::WorldEnvelope World;
		bool bRegistryLoaded = false;
		fantasy_world_generator::AssetRegistry Registry;
		// The authoring catalogue is data the consumer ships; without it a world has
		// terrain but no civilizations, and that is reported rather than faked.
		bool bCataloguesLoaded = false;
		fantasy_world_generator::Catalogues Catalogues;
		bool bPopulated = false;
		fantasy_world_generator::PopulatedWorld Populated;
	};
#else
	class FWorldState
	{
	public:
		bool bHasWorld = false;
		bool bRegistryLoaded = false;
		bool bCataloguesLoaded = false;
		bool bPopulated = false;
	};
#endif
}
