// Original material owned by David Gorden; see the repository LICENSE.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

FANTASYWORLDGENERATOR_API DECLARE_LOG_CATEGORY_EXTERN(LogFantasyWorldGenerator, Log, All);

/**
 * Runtime module for the FantasyWorldGenerator engine boundary.
 *
 * When the packaged plugin vendors Core/, its translation units are compiled into this
 * module and UFantasyWorldGeneratorSubsystem generates a recipe-3 world in process,
 * samples the detailed surface and resolves asset identities through the registry
 * table shipped in Data/. No Python runtime, sidecar or embedded interpreter is used.
 * A cooked-runtime guarantee still depends on a recorded packaged Win64 digest.
 */
class FFantasyWorldGeneratorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
