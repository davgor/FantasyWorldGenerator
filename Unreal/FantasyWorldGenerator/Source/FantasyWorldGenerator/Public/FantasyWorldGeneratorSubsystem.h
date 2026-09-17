// Original material owned by David Gorden; see the repository LICENSE.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/EngineSubsystem.h"

#include "FantasyWorldGeneratorFrame.h"

#include "FantasyWorldGeneratorSubsystem.generated.h"

/**
 * What this plugin can actually do, so a host logs facts instead of assuming that an
 * enabled plugin implies native generate or a qualified cooked runtime.
 */
USTRUCT(BlueprintType)
struct FFantasyWorldGeneratorStatus
{
	GENERATED_BODY()

	/** Coordinate/unit contract version implemented by the frame conversion. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 CoordinateContractVersion = 1;

	/** Generator recipe version accepted by request validation. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 SupportedRecipeVersion = 3;

	/** True when a Core/ include path was resolved at build time. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bCoreIncludePathResolved = false;

	/** True when Core/genesis.hpp was read and its shared constants were asserted. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bCoreContractChecked = false;

	/** Always false in this module: no Core translation unit is compiled or linked. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bCoreGenesisLinked = false;

	/** Always false in this module: no world generate is implemented here. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bNativeGenerateAvailable = false;

	/** Always false until a packaged Win64 generate to materialize digest exists. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bUnrealQualified = false;
};

/**
 * Thin wrapper over the engine-independent FantasyWorldGenerator frame and request rules.
 *
 * The conversion and validation helpers are static so a host can use them without an
 * engine subsystem instance; the subsystem exists to report status and to be the hook
 * ML-03e extends with native generate, sampling and the asset-ID registry.
 */
UCLASS()
class FANTASYWORLDGENERATOR_API UFantasyWorldGeneratorSubsystem : public UEngineSubsystem
{
	GENERATED_BODY()

public:
	/**
	 * Convert a source local tangent sample in metres to Unreal world centimetres.
	 * X is east, Y is north, Z is up; lengths are scaled by 100 exactly once, here.
	 */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Frame")
	static FVector LocalMetresToUnreal(double EastMetres, double UpMetres, double NorthMetres);

	/**
	 * Permute a unit source axis given as (east, up, north) into Unreal (east, north, up).
	 * Unit axes are never multiplied by 100.
	 */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Frame")
	static FVector LocalUnitAxisToUnreal(FVector SourceEastUpNorth);

	/** Validate a generate request against the mirrored Core rules. */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Generate")
	static bool ValidateGenerateRequest(int32 RecipeVersion, int64 Seed, int32 RegionalRasterSize,
		bool bGlobeShape, FString& OutStatusName, FString& OutDiagnostic);

	/** Report what this build of the plugin implements. */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator")
	static FFantasyWorldGeneratorStatus GetStatus();
};
