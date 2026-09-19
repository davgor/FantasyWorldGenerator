// Original material owned by David Gorden; see the repository LICENSE.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/EngineSubsystem.h"
#include "Templates/PimplPtr.h"

#include "FantasyWorldGeneratorTypes.h"

#include "FantasyWorldGeneratorSubsystem.generated.h"

namespace FantasyWorldGeneratorRuntime { class FWorldState; }

/**
 * In-process world genesis for Unreal. The generator itself is the engine-independent
 * Core/ code compiled into this module: there is no Python runtime, no sidecar process,
 * no embedded interpreter and no JSON world file in this path. A host supplies a uint32
 * seed and receives a world it can sample numerically.
 *
 * Coordinates crossing this API are Unreal centimetres with X east, Y north, Z up.
 */
UCLASS()
class FANTASYWORLDGENERATOR_API UFantasyWorldGeneratorSubsystem : public UEngineSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

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

	/** Validate a generate request against the Core rules without generating. */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Generate")
	static bool ValidateGenerateRequest(int32 RecipeVersion, int64 Seed, int32 RegionalRasterSize,
		bool bGlobeShape, FString& OutStatusName, FString& OutDiagnostic);

	/**
	 * Generate a recipe-3 world in this process and keep it for sampling. A failed
	 * request leaves any previous world untouched and reports why.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Generate")
	bool GenerateWorld(int64 Seed, int32 RegionalRasterSize, FFantasyWorldSummary& OutSummary, FString& OutDiagnostic);

	/**
	 * The same generate, sized in kilometres. The unwrap a consumer presents is the
	 * globe's circumference, so this is how wide the finished map is; the terrain the
	 * seed produces is unchanged, it simply covers more ground, and distances stated
	 * in metres, such as how far apart cities stand, do not scale with it.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Generate")
	bool GenerateWorldOfSize(int64 Seed, int32 RegionalRasterSize, double MapWidthKilometres,
		FFantasyWorldSummary& OutSummary, FString& OutDiagnostic);

	/**
	 * The same generate with mountain building turned up. Orogeny is a gain on
	 * collision uplift inside the tectonic phase, so ranges rise where plates meet
	 * while ocean basins keep their depth; one is the recipe's own value and about
	 * ten puts the tallest peak level with the deepest ocean floor. It is a generator
	 * input, not a display exaggeration: erosion, rivers, biomes and where people can
	 * settle all answer to it.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Generate")
	bool GenerateWorldWithMountains(int64 Seed, int32 RegionalRasterSize, double MapWidthKilometres,
		double Orogeny, double ReliefMetres, FFantasyWorldSummary& OutSummary, FString& OutDiagnostic);

	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Generate")
	bool HasWorld() const;

	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Generate")
	FFantasyWorldSummary GetWorldSummary() const;

	/**
	 * Authoritative local height in Unreal centimetres at one globe direction. This is
	 * the same function the surface unwrap, foundations, roads and nests read, so a
	 * consumer cannot place geometry on a different terrain than it draws.
	 */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Sampling")
	double SampleHeightCentimetres(double LatitudeDegrees, double LongitudeDegrees) const;

	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Sampling")
	FFantasySurfaceSample SampleSurface(double LatitudeDegrees, double LongitudeDegrees) const;

	/**
	 * Sample the whole rectangular tangent unwrap at the given latitude resolution.
	 * Rows vertices span pole to pole and columns span the full longitude range, so the
	 * quads stay square; polar stretch is a property of the unwrap, not of the world.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Sampling")
	bool BuildSurfaceUnwrap(int32 LatitudeRows, FFantasyWorldSurface& OutSurface, FString& OutDiagnostic) const;

	/**
	 * Cities the generator founded, positioned on the same unwrap the surface uses.
	 * Empty until a world is generated; never invented when the catalogue is missing.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Places")
	bool GetCities(int32 LatitudeRows, TArray<FFantasyCityMarker>& OutCities, FString& OutDiagnostic) const;

	/** Regional roads between those cities, densified onto the sampled surface. */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Places")
	bool GetRoads(int32 LatitudeRows, TArray<FFantasyRoadPolyline>& OutRoads, FString& OutDiagnostic) const;

	/**
	 * Buildings the city plans reserved a node for, with the registry identity each
	 * one carries. These are planned slots, not footprints: the generator does not
	 * place walls, and a consumer that draws them should say so.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Places")
	bool GetPlannedBuildings(int32 LatitudeRows, TArray<FFantasyPlannedBuilding>& OutBuildings,
		FString& OutDiagnostic) const;

	/**
	 * The buildings the settlement planners actually placed: every plot of every city,
	 * hamlet and castle, with its authored size in metres, its heading and its own
	 * axes. Unlike GetPlannedBuildings these are footprints, not reserved nodes.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Places")
	bool GetSceneBuildings(int32 LatitudeRows, TArray<FFantasySceneBuilding>& OutBuildings,
		FString& OutDiagnostic) const;

	/**
	 * Every point the generator placed that is not a city, a road or a building:
	 * hamlets, fortresses, coastal landings, witch huts, ruins and habitat anchors.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Places")
	bool GetPlaceMarkers(int32 LatitudeRows, TArray<FFantasyPlaceMarker>& OutMarkers,
		FString& OutDiagnostic) const;

	/** Lab colour of a natural biome identity. */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Sampling")
	static FColor NaturalBiomeColor(int32 NaturalBiomeId);

	/**
	 * Resolve an asset identity through the registry table shipped with this plugin.
	 * A missing binding is reported, never replaced by an anonymous mesh.
	 */
	UFUNCTION(BlueprintCallable, Category = "FantasyWorldGenerator|Registry")
	FFantasyAssetBinding ResolveAsset(const FString& AssetId) const;

	/** Identities with no engine object path, so a host can surface them once. */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator|Registry")
	int32 CountUnboundAssets() const;

	/** Report what this build of the plugin implements. */
	UFUNCTION(BlueprintPure, Category = "FantasyWorldGenerator")
	FFantasyWorldGeneratorStatus GetStatus() const;

private:
	// Type-erased so the Core world and registry stay out of this public header and
	// out of the generated reflection code.
	TPimplPtr<FantasyWorldGeneratorRuntime::FWorldState> State;
};
