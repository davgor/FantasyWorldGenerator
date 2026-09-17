// Original material owned by David Gorden; see the repository LICENSE.

#include "FantasyWorldGeneratorModule.h"

#ifndef FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT 0
#endif
#ifndef FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT 0
#endif

DEFINE_LOG_CATEGORY(LogFantasyWorldGenerator);

void FFantasyWorldGeneratorModule::StartupModule()
{
	UE_LOG(LogFantasyWorldGenerator, Log,
		TEXT("FantasyWorldGenerator loaded: coordinate contract 1, core include path %d, Core genesis linked %d. ")
		TEXT("Native world generate, importer, Landscape and asset registry are not available in this module."),
		static_cast<int32>(FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT), static_cast<int32>(FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT));
}

void FFantasyWorldGeneratorModule::ShutdownModule()
{
}

IMPLEMENT_MODULE(FFantasyWorldGeneratorModule, FantasyWorldGenerator)
