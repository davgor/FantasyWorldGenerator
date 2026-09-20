// Original material owned by David Gorden; see the repository LICENSE.
//
// Engine-facing value types for the FantasyWorldGenerator runtime boundary. The rules
// themselves live in Core/ and are compiled into this module; nothing here restates
// them. Distances crossing this boundary are already Unreal centimetres: the single
// metre-to-centimetre conversion happens inside the module, and the source axes are
// permuted to Unreal's left-handed Z-up frame at the same point.

#pragma once

#include "CoreMinimal.h"

#include "FantasyWorldGeneratorTypes.generated.h"

/**
 * What this build of the plugin actually implements, so a host logs facts instead of
 * assuming that an enabled plugin implies native generate or a qualified cooked runtime.
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

	/** Envelope contract version a consumer can require before reading a world. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 WorldContractVersion = 0;

	/** Continuous-terrain definition version behind the detailed samples. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 TerrainDetailVersion = 0;

	/** True when a Core/ include path was resolved at build time. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bCoreIncludePathResolved = false;

	/** True when the Core genesis translation units are compiled into this module. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bCoreGenesisLinked = false;

	/** True when in-process world generate is available without Python or a sidecar. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bNativeGenerateAvailable = false;

	/** True once the asset-ID registry table has been loaded from the plugin. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bAssetRegistryLoaded = false;

	/** Binding slots in the loaded registry: one per exhaustive-catalogue identity. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 AssetRegistryRows = 0;

	/** Identities that deliberately have no engine object path yet. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 AssetRegistryUnbound = 0;

	/** Content hash of the exhaustive asset list the registry was compiled from. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString AssetListSha256;

	/** False until a packaged Win64 generate to materialize run is recorded by digest. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bUnrealQualified = false;
};

/** Seed, resolved configuration and headline measurements of a generated world. */
USTRUCT(BlueprintType)
struct FFantasyWorldSummary
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int64 Seed = 0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 RecipeVersion = 3;

	/** Regional climate raster size; not the placement surface. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 RegionalSize = 0;

	/** Physical globe radius in Unreal centimetres. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double GlobeRadiusCentimetres = 0.0;

	/** Sea level in Unreal centimetres, on the same datum as sampled heights. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double SeaLevelCentimetres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double LandAreaSquareKilometres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double OceanAreaSquareKilometres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double LakeAreaSquareKilometres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bHasOcean = false;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 PlateCount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 ArchipelagoCount = 0;

	/** Wall-clock cost of the in-process generate. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double GenerateMilliseconds = 0.0;
};

/**
 * One rectangular tangent unwrap of the globe, ready to become a mesh. Positions are
 * Unreal centimetres with X east, Y north and Z up; heights come from the same
 * on-demand detailed sampling function foundations, roads and nests use, never from a
 * bilinear read of the coarse regional raster. Triangle winding is already reversed
 * for Unreal's left-handed frame.
 */
USTRUCT(BlueprintType)
struct FFantasyWorldSurface
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 Rows = 0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 Columns = 0;

	/** Uniform horizontal vertex spacing in centimetres. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double SpacingCentimetres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<FVector> Positions;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<FColor> Colors;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<int32> NaturalBiomeIds;

	/** 0 dry, 1 ocean, 2 lake. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<int32> WaterTypes;

	/** Height of the water's own surface at each vertex, in Unreal centimetres. Equal
	 *  to the vertex height on dry ground, so a consumer can draw a sea plane instead
	 *  of painting the seabed. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<double> WaterSurfaceCentimetres;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<int32> Triangles;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<FVector2D> TextureCoordinates;

	/** Lowest and highest sampled vertex in centimetres, for an honest flatness check. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double MinimumHeightCentimetres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double MaximumHeightCentimetres = 0.0;
};

/** One resolved asset-ID binding, or an explicit reason there is no object path. */
USTRUCT(BlueprintType)
struct FFantasyAssetBinding
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString AssetId;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Kind;

	/** bound, placeholder, unbound, or unknown_identity. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Status;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString ObjectPath;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Diagnostic;

	bool IsResolvable() const { return Status == TEXT("bound") || Status == TEXT("placeholder"); }
};

/** A city the generator founded, placed on the presented unwrap. */
USTRUCT(BlueprintType)
struct FFantasyCityMarker
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString PopulationProfile;

	/** Registry identity for whatever stands here; resolved like any other asset. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString AssetId;

	/** Position on the unwrap in Unreal centimetres, on the sampled surface. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector Position = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double LatitudeDegrees = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double LongitudeDegrees = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double Suitability = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bFoundingCapital = false;
};

/** One building a city plan reserved a node for.

    This is the district plan's reserved slot: which building stands on which grid
    node, with no footprint of its own. The drawn building, with its real size and
    heading, is FFantasySceneBuilding; a consumer that wants geometry wants that one.
*/
USTRUCT(BlueprintType)
struct FFantasyPlannedBuilding
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString CityId;

	/** The pack's building option, e.g. leader_homes. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString OptionId;

	/** Registry identity, already namespaced for the asset table. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString AssetId;

	/** Position on the unwrap in Unreal centimetres, on the sampled surface. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector Position = FVector::ZeroVector;

	/** Walking distance from the city node, in metres, as the plan measured it. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double DistanceToCityMetres = 0.0;
};

/** One building the settlement planners actually placed, with its real footprint.

    This is the drawn building, not the reserved slot FFantasyPlannedBuilding carries:
    the city, hamlet and castle planners pack every settlement in local metres, and
    each plot comes back with an authored size, a heading and its own axes. A consumer
    can stand a mesh on this without inventing any of the three.
*/
USTRUCT(BlueprintType)
struct FFantasySceneBuilding
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Id;

	/** city, hamlet or castle. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString SettlementKind;

	/** The settlement this belongs to, as the generator names it. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString SettlementId;

	/** Registry identity, already namespaced, e.g. building.water_point. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString AssetId;

	/** Centre on the unwrap, in Unreal centimetres, on the sampled surface. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector Position = FVector::ZeroVector;

	/** Real authored size in METRES. This is the thing that was never carried before. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector DimensionsMetres = FVector::ZeroVector;

	/** Heading on the ground, degrees, as the planner chose it. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double RotationDegrees = 0.0;

	/** The building's own axes on the unwrap, unit length, for orienting a mesh. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector WidthAxis = FVector::ForwardVector;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector DepthAxis = FVector::RightVector;
};

/** Anything the generator placed that is a point on the map rather than a structure.

    Hamlets, fortresses, coastal landings, witch huts, ruins and habitat anchors all
    arrive through one call, each tagged with its category. Only some categories carry
    an asset identity: a ruin and a creature nest do, while a hamlet or a landing has
    none in the generator, so a consumer that draws them must present them as its own
    markers rather than as registry-bound content.
*/
USTRUCT(BlueprintType)
struct FFantasyPlaceMarker
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Id;

	/** hamlet, fortress, port, landmark, ruin or nest. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Category;

	/** Registry identity where the generator gives one, otherwise empty. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString AssetId;

	/** What this is, in the world's own words: a species name, a cause of ruin. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Label;

	/** Position on the unwrap in Unreal centimetres, on the sampled surface. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FVector Position = FVector::ZeroVector;

	/**
	    Danger to a player, 1 to 5, on the creature categories; zero on everything else.

	    1 harmless, 2 can hurt you, 3 kills the careless, 4 kills the prepared,
	    5 a campaign threat.
	*/
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 Tier = 0;

	/**
	    How far the claim reaches, in metres; zero where the category has no range.

	    For an animal this is the hunting ground it may be met across, for a monster
	    the territory it holds. It is a static claim on ground, not a patrol or a
	    spawn radius.
	*/
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double RangeMetres = 0.0;

	/**
	    True when the marker is a place you can find and raid rather than only a range.

	    Dens and lairs are findable; a herd, roost or shoal is met, not visited.
	*/
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bIsDen = false;
};

/** One regional road, already densified onto the sampled surface. */
USTRUCT(BlueprintType)
struct FFantasyRoadPolyline
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString Id;

	/** Unwrap positions in Unreal centimetres, following the ground. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	TArray<FVector> Positions;

	/** River crossings along the route: bridge candidates, not engineered bridges. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 BridgeCandidates = 0;
};

/** A point on the generated surface, read through the shared sampling function. */
USTRUCT(BlueprintType)
struct FFantasySurfaceSample
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double HeightCentimetres = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 NaturalBiomeId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	int32 WaterType = 0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	bool bRiver = false;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double TemperatureCelsius = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	double Moisture = 0.0;

	/** Terrain surface asset identity for this biome, resolvable through the registry. */
	UPROPERTY(BlueprintReadOnly, Category = "FantasyWorldGenerator")
	FString SurfaceAssetId;
};
