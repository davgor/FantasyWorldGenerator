// Original material owned by David Gorden; see the repository LICENSE.

#include "FantasyWorldGeneratorModule.h"

#ifndef FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT 0
#endif
#ifndef FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT 0
#endif
#ifndef FANTASY_WORLD_GENERATOR_CORE_LINKED
#define FANTASY_WORLD_GENERATOR_CORE_LINKED 0
#endif

DEFINE_LOG_CATEGORY(LogFantasyWorldGenerator);

void FFantasyWorldGeneratorModule::StartupModule()
{
	// Say what is linked rather than what is enabled: a descriptor-only plugin and a
	// plugin that can generate a world in process must not log the same line.
	UE_LOG(LogFantasyWorldGenerator, Log,
		TEXT("FantasyWorldGenerator loaded: coordinate contract 1, Core include path %d, Core sources compiled in %d. ")
		TEXT("Native in-process world generate %s."),
		static_cast<int32>(FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT),
		static_cast<int32>(FANTASY_WORLD_GENERATOR_CORE_LINKED),
		FANTASY_WORLD_GENERATOR_CORE_LINKED ? TEXT("available") : TEXT("unavailable in this build"));
}

void FFantasyWorldGeneratorModule::ShutdownModule()
{
}

IMPLEMENT_MODULE(FFantasyWorldGeneratorModule, FantasyWorldGenerator)
