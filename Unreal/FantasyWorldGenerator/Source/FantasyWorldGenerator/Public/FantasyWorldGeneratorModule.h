// Original material owned by David Gorden; see the repository LICENSE.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

FANTASYWORLDGENERATOR_API DECLARE_LOG_CATEGORY_EXTERN(LogFantasyWorldGenerator, Log, All);

/**
 * Runtime module for the FantasyWorldGenerator engine boundary.
 *
 * This module currently exposes the source-to-Unreal frame and generate-request
 * validation only. It does not generate a world, build a Landscape, resolve the
 * asset-ID registry or provide any cooked-runtime guarantee.
 */
class FFantasyWorldGeneratorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
