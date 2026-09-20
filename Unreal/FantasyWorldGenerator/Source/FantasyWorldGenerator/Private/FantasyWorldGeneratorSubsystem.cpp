// Original material owned by David Gorden; see the repository LICENSE.

#include "FantasyWorldGeneratorSubsystem.h"

#include "FantasyWorldGeneratorModule.h"
#include "FantasyWorldGeneratorRuntime.h"

#include "HAL/PlatformTime.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include <cmath>

#ifndef FANTASY_WORLD_GENERATOR_CORE_LINKED
#define FANTASY_WORLD_GENERATOR_CORE_LINKED 0
#endif
#ifndef FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT 0
#endif

#if FANTASY_WORLD_GENERATOR_CORE_LINKED
// The settlement planners read four shipped JSON catalogues; only their path setters
// are needed here, because scene.hpp owns the planning itself.
#include "castleplanner.hpp"
#include "cityshapes.hpp"
#include "settlementpresets.hpp"
#endif

namespace
{
	const TCHAR* RegistryFileName = TEXT("unreal-asset-registry-v1.json");
	const TCHAR* CatalogueFileName = TEXT("native-catalogues-v1.json");

	FString PluginDirectory()
	{
		const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("FantasyWorldGenerator"));
		return Plugin.IsValid() ? Plugin->GetBaseDir() : FPaths::ProjectPluginsDir() / TEXT("FantasyWorldGenerator");
	}

	FString DataPath(const TCHAR* FileName)
	{
		return FPaths::Combine(PluginDirectory(), TEXT("Data"), FileName);
	}

#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	/**
	    Tell the settlement planners where their four shipped JSON catalogues are.

	    Core derives no path from __file__, so a host names them once. They travel with
	    the plugin under Data/; an in-repository checkout falls back to the Sim tree
	    they are authored in, which is what the sibling Core/ include path already
	    assumes. Nothing is read here: the planner modules cache on (path, mtime, size)
	    and report a missing file through scene.buildings_status.
	*/
	void ConfigureSettlementCatalogues()
	{
		const FString Staged = FPaths::Combine(PluginDirectory(), TEXT("Data"));
		const FString Authored = FPaths::Combine(PluginDirectory(), TEXT(".."), TEXT(".."), TEXT("Sim"), TEXT("icarus_sim"));
		auto Locate = [&Staged, &Authored](const TCHAR* FileName)
		{
			const FString Candidate = FPaths::Combine(Staged, FileName);
			return FPaths::FileExists(Candidate) ? Candidate : FPaths::Combine(Authored, FileName);
		};
		// buildings.json is read from beside civilizations.json, as the reference does.
		fantasy_world_generator::settlementpresets::set_registry_path(
			std::string(TCHAR_TO_UTF8(*Locate(TEXT("civilizations.json")))));
		fantasy_world_generator::cityshapes::set_catalogue_path(
			std::string(TCHAR_TO_UTF8(*Locate(TEXT("city_shapes.json")))));
		fantasy_world_generator::castleplanner::set_castles_path(
			std::string(TCHAR_TO_UTF8(*Locate(TEXT("castles.json")))));
	}
#endif

#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	/** Core reports failures as fantasy_world_generator::Error; nothing else escapes. */
	FString CoreDiagnostic(const fantasy_world_generator::Error& Failure)
	{
		return FString(UTF8_TO_TCHAR(Failure.what()));
	}
#endif
}

void UFantasyWorldGeneratorSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	State = MakePimpl<FantasyWorldGeneratorRuntime::FWorldState>();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	// The registry travels with the plugin and is staged into cooked builds, so a
	// consumer resolves identities the same way in the editor and in a package.
	const FString Path = DataPath(RegistryFileName);
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		UE_LOG(LogFantasyWorldGenerator, Error, TEXT("Asset registry not found at %s; identities cannot be resolved."), *Path);
		return;
	}
	try
	{
		State->Registry = fantasy_world_generator::AssetRegistry::parse(std::string(TCHAR_TO_UTF8(*Text)));
		State->bRegistryLoaded = true;
		UE_LOG(LogFantasyWorldGenerator, Log, TEXT("Asset registry loaded: %d bindings, %d unbound."),
			static_cast<int32>(State->Registry.size()), static_cast<int32>(State->Registry.unbound().size()));
	}
	catch (const fantasy_world_generator::Error& Failure)
	{
		UE_LOG(LogFantasyWorldGenerator, Error, TEXT("Asset registry rejected (%s): %s"), *CoreDiagnostic(Failure), *Path);
	}
	// The authoring catalogue: without it the generator still makes terrain, and says
	// so, rather than placing civilizations from guessed traits.
	const FString CataloguePath = DataPath(CatalogueFileName);
	FString CatalogueText;
	if (!FFileHelper::LoadFileToString(CatalogueText, *CataloguePath))
	{
		UE_LOG(LogFantasyWorldGenerator, Warning,
			TEXT("Authoring catalogue not found at %s; worlds will have terrain but no civilizations."), *CataloguePath);
		return;
	}
	try
	{
		State->Catalogues = fantasy_world_generator::Catalogues::parse(std::string(TCHAR_TO_UTF8(*CatalogueText)));
		State->bCataloguesLoaded = true;
		UE_LOG(LogFantasyWorldGenerator, Log, TEXT("Authoring catalogue loaded: %d civilizations, registry %s."),
			static_cast<int32>(State->Catalogues.civilization_ids().size()),
			*FString(UTF8_TO_TCHAR(State->Catalogues.registry_sha256().c_str())));
	}
	catch (const fantasy_world_generator::Error& Failure)
	{
		UE_LOG(LogFantasyWorldGenerator, Error, TEXT("Authoring catalogue rejected (%s): %s"),
			*CoreDiagnostic(Failure), *CataloguePath);
	}
#endif
}

void UFantasyWorldGeneratorSubsystem::Deinitialize()
{
	State.Reset();
	Super::Deinitialize();
}

FVector UFantasyWorldGeneratorSubsystem::LocalMetresToUnreal(double EastMetres, double UpMetres, double NorthMetres)
{
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	const fantasy_world_generator::UnrealVector Converted =
		fantasy_world_generator::unreal_centimetres(fantasy_world_generator::Vec3{EastMetres, UpMetres, NorthMetres});
	return FVector(Converted.x_cm, Converted.y_cm, Converted.z_cm);
#else
	return FVector(EastMetres * 100.0, NorthMetres * 100.0, UpMetres * 100.0);
#endif
}

FVector UFantasyWorldGeneratorSubsystem::LocalUnitAxisToUnreal(FVector SourceEastUpNorth)
{
	// Unit axes only permute: scaling one by 100 would silently resize a building.
	return FVector(SourceEastUpNorth.X, SourceEastUpNorth.Z, SourceEastUpNorth.Y);
}

bool UFantasyWorldGeneratorSubsystem::ValidateGenerateRequest(int32 RecipeVersion, int64 Seed, int32 RegionalRasterSize,
	bool bGlobeShape, FString& OutStatusName, FString& OutDiagnostic)
{
	OutStatusName = TEXT("OK");
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	try
	{
		fantasy_world_generator::json::Value::Object Overrides;
		Overrides.emplace("size", fantasy_world_generator::json::Value(static_cast<std::int64_t>(RegionalRasterSize)));
		Overrides.emplace("shape", fantasy_world_generator::json::Value(bGlobeShape ? "globe" : "plane"));
		fantasy_world_generator::json::Value::Object Body;
		Body.emplace("recipe_version", fantasy_world_generator::json::Value(static_cast<std::int64_t>(RecipeVersion)));
		Body.emplace("seed", fantasy_world_generator::json::Value(static_cast<std::int64_t>(Seed)));
		Body.emplace("overrides", fantasy_world_generator::json::Value(std::move(Overrides)));
		fantasy_world_generator::generate_request(fantasy_world_generator::json::Value(std::move(Body)));
		return true;
	}
	catch (const fantasy_world_generator::Error& Failure)
	{
		OutStatusName = CoreDiagnostic(Failure);
		OutDiagnostic = FString::Printf(TEXT("generate request rejected: %s"), *OutStatusName);
		return false;
	}
#else
	OutStatusName = TEXT("CORE_NOT_LINKED");
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

bool UFantasyWorldGeneratorSubsystem::GenerateWorld(int64 Seed, int32 RegionalRasterSize,
	FFantasyWorldSummary& OutSummary, FString& OutDiagnostic)
{
	// Zero means the recipe's own size, which is what the first contract promised.
	return GenerateWorldOfSize(Seed, RegionalRasterSize, 0.0, OutSummary, OutDiagnostic);
}

bool UFantasyWorldGeneratorSubsystem::GenerateWorldOfSize(int64 Seed, int32 RegionalRasterSize,
	double MapWidthKilometres, FFantasyWorldSummary& OutSummary, FString& OutDiagnostic)
{
	// One is the recipe's own mountain building.
	return GenerateWorldWithMountains(Seed, RegionalRasterSize, MapWidthKilometres, 1.0, 255.0,
		OutSummary, OutDiagnostic);
}

bool UFantasyWorldGeneratorSubsystem::GenerateWorldWithMountains(int64 Seed, int32 RegionalRasterSize,
	double MapWidthKilometres, double Orogeny, double ReliefMetres, FFantasyWorldSummary& OutSummary,
	FString& OutDiagnostic)
{
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!State.IsValid())
	{
		OutDiagnostic = TEXT("subsystem is not initialised");
		return false;
	}
	const double Started = FPlatformTime::Seconds();
	try
	{
		fantasy_world_generator::GenerateRequest Request;
		Request.recipe_version = fantasy_world_generator::genesis_recipe;
		Request.seed = static_cast<std::int64_t>(Seed);
		Request.size = static_cast<std::int64_t>(RegionalRasterSize);
		if (MapWidthKilometres > 0.0)
		{
			// Width comes from the design radius and relief from its own input, so a
			// wider map keeps the same mountains rather than scaling them with it.
			Request.overrides = fantasy_world_generator::world_shape_overrides(
				MapWidthKilometres * 1000.0, ReliefMetres, Orogeny > 0.0 ? Orogeny : 1.0);
		}
		else if (Orogeny > 0.0 && Orogeny != 1.0)
		{
			Request.overrides = fantasy_world_generator::orogeny_overrides(Orogeny);
		}
		if (Request.seed < 0 || Request.seed > fantasy_world_generator::max_seed)
		{
			OutDiagnostic = TEXT("seed must be a uint32");
			return false;
		}
		if (Request.size < fantasy_world_generator::min_grid || Request.size > fantasy_world_generator::max_grid)
		{
			OutDiagnostic = TEXT("regional raster size is outside the supported range");
			return false;
		}
		// Generated into a local first: a failed request must not destroy the world a
		// host is already presenting.
		fantasy_world_generator::WorldEnvelope Generated = fantasy_world_generator::generate_world(Request);
		State->World = MoveTemp(Generated);
		State->bHasWorld = true;
		State->bPopulated = false;
		if (State->bCataloguesLoaded)
		{
			// Civilizations, their roads and the scene they put on the surface, then
			// the two deep-time transitions that make this the world's final state:
			// cities are lost, leylines evolve and what is left rebuilds around them.
			State->Populated = fantasy_world_generator::populate_world(State->World, State->Catalogues);
			for (int64 Age = 1; Age <= 2; ++Age)
			{
				fantasy_world_generator::AgeResult Transition;
				State->Populated = fantasy_world_generator::advance_age(State->World, State->Catalogues,
					State->Populated, Age, Transition);
			}
			// The settlement geometry is the reference's last stage and runs once, on
			// the world the ages have left behind: every city, hamlet and castle packed
			// in local metres, every plot a dimensioned footprint. It reports its own
			// failures through scene.buildings_status rather than throwing, so a
			// missing catalogue costs the buildings and not the world.
			ConfigureSettlementCatalogues();
			fantasy_world_generator::plan_settlement_buildings(State->World, State->Catalogues,
				State->Populated);
			if (!State->Populated.scene.buildings_status.empty())
			{
				UE_LOG(LogFantasyWorldGenerator, Warning, TEXT("No settlement buildings: %s"),
					UTF8_TO_TCHAR(State->Populated.scene.buildings_status.c_str()));
			}
			State->bPopulated = true;
		}
	}
	catch (const fantasy_world_generator::Error& Failure)
	{
		OutDiagnostic = FString::Printf(TEXT("native generate failed: %s"), *CoreDiagnostic(Failure));
		return false;
	}
	const fantasy_world_generator::WorldEnvelope& World = State->World;
	OutSummary = FFantasyWorldSummary();
	OutSummary.Seed = Seed;
	OutSummary.RecipeVersion = static_cast<int32>(World.config.world_recipe);
	OutSummary.RegionalSize = static_cast<int32>(World.size);
	OutSummary.GlobeRadiusCentimetres = World.effective.globe_radius * fantasy_world_generator::centimetres_per_metre;
	OutSummary.SeaLevelCentimetres = World.effective.sea_level * fantasy_world_generator::centimetres_per_metre;
	OutSummary.LandAreaSquareKilometres = World.land_km2;
	OutSummary.OceanAreaSquareKilometres = World.ocean_km2;
	OutSummary.LakeAreaSquareKilometres = World.lake_km2;
	OutSummary.bHasOcean = World.has_ocean;
	OutSummary.PlateCount = static_cast<int32>(World.plates.size());
	OutSummary.ArchipelagoCount = static_cast<int32>(World.archipelagos.size());
	OutSummary.GenerateMilliseconds = (FPlatformTime::Seconds() - Started) * 1000.0;
	return true;
#else
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

bool UFantasyWorldGeneratorSubsystem::HasWorld() const
{
	return State.IsValid() && State->bHasWorld;
}

FFantasyWorldSummary UFantasyWorldGeneratorSubsystem::GetWorldSummary() const
{
	FFantasyWorldSummary Summary;
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (HasWorld())
	{
		const fantasy_world_generator::WorldEnvelope& World = State->World;
		Summary.Seed = static_cast<int64>(World.config.seed);
		Summary.RecipeVersion = static_cast<int32>(World.config.world_recipe);
		Summary.RegionalSize = static_cast<int32>(World.size);
		Summary.GlobeRadiusCentimetres = World.effective.globe_radius * fantasy_world_generator::centimetres_per_metre;
		Summary.SeaLevelCentimetres = World.effective.sea_level * fantasy_world_generator::centimetres_per_metre;
		Summary.LandAreaSquareKilometres = World.land_km2;
		Summary.OceanAreaSquareKilometres = World.ocean_km2;
		Summary.LakeAreaSquareKilometres = World.lake_km2;
		Summary.bHasOcean = World.has_ocean;
		Summary.PlateCount = static_cast<int32>(World.plates.size());
		Summary.ArchipelagoCount = static_cast<int32>(World.archipelagos.size());
	}
#endif
	return Summary;
}

double UFantasyWorldGeneratorSubsystem::SampleHeightCentimetres(double LatitudeDegrees, double LongitudeDegrees) const
{
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		return 0.0;
	}
	const fantasy_world_generator::Vec3 Direction =
		fantasy_world_generator::globe_direction(LatitudeDegrees, LongitudeDegrees);
	return fantasy_world_generator::sample_height(State->World, Direction) * fantasy_world_generator::centimetres_per_metre;
#else
	(void)LatitudeDegrees; (void)LongitudeDegrees;
	return 0.0;
#endif
}

FFantasySurfaceSample UFantasyWorldGeneratorSubsystem::SampleSurface(double LatitudeDegrees, double LongitudeDegrees) const
{
	FFantasySurfaceSample Sample;
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		return Sample;
	}
	const fantasy_world_generator::SurfaceSample Source = fantasy_world_generator::sample_surface(
		State->World, fantasy_world_generator::globe_direction(LatitudeDegrees, LongitudeDegrees));
	Sample.HeightCentimetres = Source.height_m * fantasy_world_generator::centimetres_per_metre;
	Sample.NaturalBiomeId = static_cast<int32>(Source.natural_biome);
	Sample.WaterType = static_cast<int32>(Source.water_type);
	Sample.bRiver = Source.river;
	Sample.TemperatureCelsius = Source.temperature_c;
	Sample.Moisture = Source.moisture;
	Sample.SurfaceAssetId = FString::Printf(TEXT("terrain.biome.%03d"), Sample.NaturalBiomeId);
#else
	(void)LatitudeDegrees; (void)LongitudeDegrees;
#endif
	return Sample;
}

namespace
{
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	/** Place a globe direction on the presented unwrap, in Unreal centimetres. */
	FVector UnwrapPosition(const fantasy_world_generator::WorldEnvelope& World, int32 Rows,
		const fantasy_world_generator::Vec3& Direction, double HeightMetres)
	{
		const int32 Columns = 2 * (Rows - 1) + 1;
		const double RadiusCentimetres = World.effective.globe_radius * fantasy_world_generator::centimetres_per_metre;
		const double Spacing = PI * RadiusCentimetres / static_cast<double>(Rows - 1);
		const fantasy_world_generator::GlobeCoordinates Coordinates =
			fantasy_world_generator::unwrap_coordinates(Direction);
		const double Column = (Coordinates.longitude_degrees + 180.0) / 360.0 * static_cast<double>(Columns - 1);
		const double Row = (90.0 - Coordinates.latitude_degrees) / 180.0 * static_cast<double>(Rows - 1);
		const double HalfColumns = static_cast<double>(Columns - 1) / 2.0;
		const double HalfRows = static_cast<double>(Rows - 1) / 2.0;
		return FVector((Column - HalfColumns) * Spacing,
			(static_cast<double>(Rows - 1) - Row - HalfRows) * Spacing,
			HeightMetres * fantasy_world_generator::centimetres_per_metre);
	}

	/** The ground tangent basis under a globe direction, clamped to the frame's domain. */
	fantasy_world_generator::TangentFrame GroundFrame(const fantasy_world_generator::Vec3& Direction)
	{
		const fantasy_world_generator::GlobeCoordinates Coordinates =
			fantasy_world_generator::unwrap_coordinates(Direction);
		return fantasy_world_generator::tangent_frame(
			FMath::Clamp(Coordinates.latitude_degrees, -90.0, 90.0),
			FMath::Clamp(Coordinates.longitude_degrees, -180.0, 180.0));
	}

	/**
	    A building axis, which the generator gives as a globe-centred direction, as it
	    lies on the presented unwrap.

	    The unwrap is the shared Unreal frame: east is +X, north is +Y. A plot's width
	    and depth axes are already tangent at the plot, so their components in the
	    ground basis under it are the heading itself, and the pair stays a right angle
	    of unit vectors -- which a mesh needs and a finite difference across a plate
	    carree, stretched by 1/cos(latitude) east to west, would not give.
	*/
	FVector UnwrapAxis(const fantasy_world_generator::TangentFrame& Ground,
		const fantasy_world_generator::Vec3& Axis, const FVector& Fallback)
	{
		const FVector Flat(fantasy_world_generator::dot(Axis, Ground.east),
			fantasy_world_generator::dot(Axis, Ground.north), 0.0);
		// Zero only at a pole, where east and north are not defined and the caller's
		// default is a better answer than a direction picked out of the rounding.
		return Flat.SizeSquared() > 1.e-12 ? Flat.GetSafeNormal() : Fallback;
	}
#endif
}

bool UFantasyWorldGeneratorSubsystem::GetCities(int32 LatitudeRows, TArray<FFantasyCityMarker>& OutCities,
	FString& OutDiagnostic) const
{
	OutCities.Reset();
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		OutDiagnostic = TEXT("no world has been generated");
		return false;
	}
	if (!State->bPopulated)
	{
		OutDiagnostic = TEXT("no authoring catalogue is loaded, so this world has no civilizations");
		return false;
	}
	if (LatitudeRows < 3)
	{
		OutDiagnostic = TEXT("latitude rows must be at least 3");
		return false;
	}
	for (const fantasy_world_generator::CityAnchor& City : State->Populated.scene.cities)
	{
		FFantasyCityMarker marker;
		marker.Id = FString(UTF8_TO_TCHAR(City.id.c_str()));
		marker.PopulationProfile = FString(UTF8_TO_TCHAR(City.population_profile.c_str()));
		marker.AssetId = FString(UTF8_TO_TCHAR(City.asset_id.c_str()));
		marker.Position = UnwrapPosition(State->World, LatitudeRows, City.direction, City.height_m);
		const fantasy_world_generator::GlobeCoordinates Coordinates =
			fantasy_world_generator::unwrap_coordinates(City.direction);
		marker.LatitudeDegrees = Coordinates.latitude_degrees;
		marker.LongitudeDegrees = Coordinates.longitude_degrees;
		marker.Suitability = City.suitability;
		marker.bFoundingCapital = City.founding_capital;
		OutCities.Add(marker);
	}
	return true;
#else
	(void)LatitudeRows;
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

bool UFantasyWorldGeneratorSubsystem::GetRoads(int32 LatitudeRows, TArray<FFantasyRoadPolyline>& OutRoads,
	FString& OutDiagnostic) const
{
	OutRoads.Reset();
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		OutDiagnostic = TEXT("no world has been generated");
		return false;
	}
	if (!State->bPopulated)
	{
		OutDiagnostic = TEXT("no authoring catalogue is loaded, so this world has no roads");
		return false;
	}
	const double Radius = State->World.effective.globe_radius;
	for (const fantasy_world_generator::RegionalRoad& Road : State->Populated.scene.regional_roads)
	{
		FFantasyRoadPolyline polyline;
		polyline.Id = FString(UTF8_TO_TCHAR(Road.id.c_str()));
		polyline.BridgeCandidates = static_cast<int32>(Road.bridge_candidates.size());
		polyline.Positions.Reserve(Road.positions_m.size());
		for (const fantasy_world_generator::Vec3& Point : Road.positions_m)
		{
			// Scene positions are globe-centred metres; the unwrap needs the direction
			// and the radial height, which is the length above the reference sphere.
			const double Length = std::sqrt(Point[0] * Point[0] + Point[1] * Point[1] + Point[2] * Point[2]);
			const fantasy_world_generator::Vec3 Direction{Point[0] / Length, Point[1] / Length, Point[2] / Length};
			polyline.Positions.Add(UnwrapPosition(State->World, LatitudeRows, Direction, Length - Radius));
		}
		OutRoads.Add(polyline);
	}
	return true;
#else
	(void)LatitudeRows;
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

bool UFantasyWorldGeneratorSubsystem::GetPlannedBuildings(int32 LatitudeRows,
	TArray<FFantasyPlannedBuilding>& OutBuildings, FString& OutDiagnostic) const
{
	OutBuildings.Reset();
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		OutDiagnostic = TEXT("no world has been generated");
		return false;
	}
	if (!State->bPopulated)
	{
		OutDiagnostic = TEXT("no authoring catalogue is loaded, so this world has no city plans");
		return false;
	}
	if (LatitudeRows < 3)
	{
		OutDiagnostic = TEXT("latitude rows must be at least 3");
		return false;
	}
	const fantasy_world_generator::WorldEnvelope& World = State->World;
	for (std::size_t Index = 0; Index < State->Populated.plans.size(); ++Index)
	{
		const fantasy_world_generator::CityPlan& Plan = State->Populated.plans[Index];
		for (const fantasy_world_generator::BuildingOptionPlan& Option : Plan.options)
		{
			// Assets are drawn once per placed anchor, so the two lists line up; an
			// option with no asset choices reserves nodes without an identity and is
			// skipped rather than given a made-up one.
			const std::size_t Count = std::min(Option.anchors.size(), Option.assets.size());
			for (std::size_t Slot = 0; Slot < Count; ++Slot)
			{
				const fantasy_world_generator::PlanAnchor& Anchor = Option.anchors[Slot];
				FFantasyPlannedBuilding building;
				building.CityId = FString::Printf(TEXT("city-%d"), static_cast<int32>(Index));
				building.OptionId = FString(UTF8_TO_TCHAR(Option.option_id.c_str()));
				// The asset table namespaces building identities; the catalogue does not.
				building.AssetId = FString(TEXT("building.")) + FString(UTF8_TO_TCHAR(Option.assets[Slot].c_str()));
				const fantasy_world_generator::Vec3 Direction =
					fantasy_world_generator::direction(Anchor.x, Anchor.z, World.size);
				building.Position = UnwrapPosition(World, LatitudeRows, Direction,
					fantasy_world_generator::sample_height(World, Direction));
				building.DistanceToCityMetres = Anchor.distance_to_city_m;
				OutBuildings.Add(building);
			}
		}
	}
	return true;
#else
	(void)LatitudeRows;
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

bool UFantasyWorldGeneratorSubsystem::GetSceneBuildings(int32 LatitudeRows,
	TArray<FFantasySceneBuilding>& OutBuildings, FString& OutDiagnostic) const
{
	OutBuildings.Reset();
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		OutDiagnostic = TEXT("no world has been generated");
		return false;
	}
	if (!State->bPopulated)
	{
		OutDiagnostic = TEXT("no authoring catalogue is loaded, so this world has no settlements");
		return false;
	}
	if (LatitudeRows < 3)
	{
		OutDiagnostic = TEXT("latitude rows must be at least 3");
		return false;
	}
	if (!State->Populated.scene.buildings_status.empty())
	{
		// The planners read four shipped JSON catalogues. A world that could not reach
		// them is a populated world with no plots, and saying which file is missing is
		// worth more than an empty array that looks like a world without cities.
		OutDiagnostic = FString::Printf(TEXT("the settlement planners produced no buildings: %s"),
			UTF8_TO_TCHAR(State->Populated.scene.buildings_status.c_str()));
		return false;
	}
	const fantasy_world_generator::WorldEnvelope& World = State->World;
	OutBuildings.Reserve(static_cast<int32>(State->Populated.scene.buildings.size()));
	for (const fantasy_world_generator::SceneBuilding& Source : State->Populated.scene.buildings)
	{
		// Scene positions are globe-centred metres, the same as a regional road's, so
		// they take the same route onto the unwrap: a direction plus a surface height.
		const fantasy_world_generator::Vec3& Centre = Source.position_m;
		const double Length = std::sqrt(Centre[0] * Centre[0] + Centre[1] * Centre[1] + Centre[2] * Centre[2]);
		if (!(Length > 0.0))
		{
			continue;
		}
		const fantasy_world_generator::Vec3 Direction{Centre[0] / Length, Centre[1] / Length, Centre[2] / Length};
		// The radial height the scene emitted, not a fresh sample at the centre. The
		// planner stands a plot on the HIGHEST cell of its own footprint, from the same
		// sampled surface every other marker uses, so that a building on a slope rests
		// on the ground instead of sinking into the uphill half of it. Re-sampling the
		// centre here would undo that by up to several metres on steep ground.
		const double HeightMetres = Length - World.effective.globe_radius;
		FFantasySceneBuilding Building;
		Building.Id = FString(UTF8_TO_TCHAR(Source.id.c_str()));
		Building.SettlementKind = FString(UTF8_TO_TCHAR(Source.settlement_kind.c_str()));
		Building.SettlementId = FString(UTF8_TO_TCHAR(Source.settlement_id.c_str()));
		Building.AssetId = FString(UTF8_TO_TCHAR(Source.asset_id.c_str()));
		Building.Position = UnwrapPosition(World, LatitudeRows, Direction, HeightMetres);
		Building.DimensionsMetres = FVector(Source.width_m, Source.depth_m, Source.height_m);
		Building.RotationDegrees = Source.rotation_degrees;
		const fantasy_world_generator::TangentFrame Ground = GroundFrame(Direction);
		Building.WidthAxis = UnwrapAxis(Ground, Source.width_axis, FVector::ForwardVector);
		Building.DepthAxis = UnwrapAxis(Ground, Source.depth_axis, FVector::RightVector);
		OutBuildings.Add(Building);
	}
	return true;
#else
	(void)LatitudeRows;
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

bool UFantasyWorldGeneratorSubsystem::GetPlaceMarkers(int32 LatitudeRows,
	TArray<FFantasyPlaceMarker>& OutMarkers, FString& OutDiagnostic) const
{
	OutMarkers.Reset();
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		OutDiagnostic = TEXT("no world has been generated");
		return false;
	}
	if (!State->bPopulated)
	{
		OutDiagnostic = TEXT("no authoring catalogue is loaded, so this world has no settlements");
		return false;
	}
	if (LatitudeRows < 3)
	{
		OutDiagnostic = TEXT("latitude rows must be at least 3");
		return false;
	}
	const fantasy_world_generator::WorldEnvelope& World = State->World;
	auto Place = [&](const FString& Id, const TCHAR* Category, const FString& AssetId, const FString& Label,
		int64 X, int64 Z)
	{
		const fantasy_world_generator::Vec3 Direction = fantasy_world_generator::direction(X, Z, World.size);
		FFantasyPlaceMarker marker;
		marker.Id = Id;
		marker.Category = Category;
		marker.AssetId = AssetId;
		marker.Label = Label;
		marker.Position = UnwrapPosition(World, LatitudeRows, Direction,
			fantasy_world_generator::sample_height(World, Direction));
		OutMarkers.Add(marker);
	};
	const fantasy_world_generator::PopulatedWorld& Populated = State->Populated;
	for (const fantasy_world_generator::RuralSite& Site : Populated.humans.hamlets)
	{
		// A hamlet has no asset identity in the generator, so none is invented here.
		Place(FString(UTF8_TO_TCHAR(Site.id.c_str())), TEXT("hamlet"), FString(),
			FString(UTF8_TO_TCHAR(Site.role.c_str())), Site.x, Site.z);
	}
	for (const fantasy_world_generator::RuralSite& Site : Populated.humans.fortresses)
	{
		Place(FString(UTF8_TO_TCHAR(Site.id.c_str())), TEXT("fortress"), FString(),
			FString(UTF8_TO_TCHAR(Site.population_profile.c_str())), Site.x, Site.z);
	}
	for (const fantasy_world_generator::Port& Port : Populated.society.ports)
	{
		Place(FString(UTF8_TO_TCHAR(Port.id.c_str())), TEXT("port"), FString(),
			Port.trade_terminal ? TEXT("harbour") : TEXT("landing"), Port.x, Port.z);
	}
	for (const fantasy_world_generator::Landmark& Mark : Populated.society.landmarks)
	{
		Place(FString(UTF8_TO_TCHAR(Mark.id.c_str())), TEXT("landmark"), FString(),
			FString(UTF8_TO_TCHAR(Mark.kind.c_str())), Mark.x, Mark.z);
	}
	for (const fantasy_world_generator::Ruin& Ruin : Populated.ruins)
	{
		Place(FString(UTF8_TO_TCHAR(Ruin.id.c_str())), TEXT("ruin"),
			FString(UTF8_TO_TCHAR(Ruin.asset_id.c_str())),
			FString(UTF8_TO_TCHAR(Ruin.cause.c_str())), Ruin.x, Ruin.z);
	}
	// Two independent passes, kept apart by category: `animal` is a hunting ground,
	// `nest` a monster territory. They overlap on purpose -- the monsters hunt the
	// same game -- so a consumer must not treat one as excluding the other.
	const TPair<const TCHAR*, const fantasy_world_generator::NestResult*> Habitat[] = {
		{TEXT("animal"), &Populated.nests.animals},
		{TEXT("nest"), &Populated.nests.monsters}};
	for (const auto& Pass : Habitat)
	{
		for (const fantasy_world_generator::Nest& Nest : Pass.Value->sites)
		{
			// A habitat anchor carries a real identity: one registry row per species.
			Place(FString(UTF8_TO_TCHAR(Nest.id.c_str())), Pass.Key,
				FString(TEXT("creature.")) + FString(UTF8_TO_TCHAR(Nest.species_id.c_str())),
				FString(UTF8_TO_TCHAR(Nest.name.c_str())), Nest.x, Nest.z);
			FFantasyPlaceMarker& Marker = OutMarkers.Last();
			Marker.Tier = static_cast<int32>(Nest.tier);
			Marker.RangeMetres = Nest.range_m;
			Marker.bIsDen = Nest.den;
		}
	}
	return true;
#else
	(void)LatitudeRows;
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

FColor UFantasyWorldGeneratorSubsystem::NaturalBiomeColor(int32 NaturalBiomeId)

{
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	try
	{
		const std::array<int, 3> Channels = fantasy_world_generator::natural_biome_color(NaturalBiomeId);
		return FColor(static_cast<uint8>(Channels[0]), static_cast<uint8>(Channels[1]), static_cast<uint8>(Channels[2]), 255);
	}
	catch (const fantasy_world_generator::Error&)
	{
		// An unknown identity is visibly wrong rather than quietly plausible.
		return FColor(255, 0, 255, 255);
	}
#else
	(void)NaturalBiomeId;
	return FColor(255, 0, 255, 255);
#endif
}

bool UFantasyWorldGeneratorSubsystem::BuildSurfaceUnwrap(int32 LatitudeRows, FFantasyWorldSurface& OutSurface,
	FString& OutDiagnostic) const
{
	OutSurface = FFantasyWorldSurface();
	OutDiagnostic.Reset();
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!HasWorld())
	{
		OutDiagnostic = TEXT("no world has been generated");
		return false;
	}
	if (LatitudeRows < 3 || LatitudeRows > 1025)
	{
		OutDiagnostic = TEXT("latitude rows must be 3..1025");
		return false;
	}
	const fantasy_world_generator::WorldEnvelope& World = State->World;
	const int32 Rows = LatitudeRows;
	const int32 Columns = 2 * (Rows - 1) + 1;
	const double RadiusCentimetres = World.effective.globe_radius * fantasy_world_generator::centimetres_per_metre;
	// Square quads: the unwrap covers pi*R north to south and 2*pi*R east to west.
	const double Spacing = PI * RadiusCentimetres / static_cast<double>(Rows - 1);
	const double HalfRows = static_cast<double>(Rows - 1) / 2.0;
	const double HalfColumns = static_cast<double>(Columns - 1) / 2.0;
	OutSurface.Rows = Rows;
	OutSurface.Columns = Columns;
	OutSurface.SpacingCentimetres = Spacing;
	OutSurface.Positions.Reserve(Rows * Columns);
	OutSurface.Colors.Reserve(Rows * Columns);
	OutSurface.NaturalBiomeIds.Reserve(Rows * Columns);
	OutSurface.WaterTypes.Reserve(Rows * Columns);
	OutSurface.WaterSurfaceCentimetres.Reserve(Rows * Columns);
	OutSurface.TextureCoordinates.Reserve(Rows * Columns);
	double Lowest = TNumericLimits<double>::Max();
	double Highest = TNumericLimits<double>::Lowest();
	for (int32 Row = 0; Row < Rows; ++Row)
	{
		const double Latitude = 90.0 - 180.0 * static_cast<double>(Row) / static_cast<double>(Rows - 1);
		for (int32 Column = 0; Column < Columns; ++Column)
		{
			const double Longitude = -180.0 + 360.0 * static_cast<double>(Column) / static_cast<double>(Columns - 1);
			const fantasy_world_generator::Vec3 Direction = fantasy_world_generator::globe_direction(Latitude, Longitude);
			const fantasy_world_generator::SurfaceSample Sample = fantasy_world_generator::sample_surface(World, Direction);
			const double HeightCentimetres = Sample.height_m * fantasy_world_generator::centimetres_per_metre;
			// X follows east, Y follows north, Z is up: the north pole is at maximum Y.
			// The unwrap is centred on the origin so a consumer does not have to shift it.
			OutSurface.Positions.Emplace((static_cast<double>(Column) - HalfColumns) * Spacing,
				(static_cast<double>(Rows - 1 - Row) - HalfRows) * Spacing, HeightCentimetres);
			const std::array<int, 3> Channels = fantasy_world_generator::natural_biome_color(Sample.natural_biome);
			FColor Colour(static_cast<uint8>(Channels[0]), static_cast<uint8>(Channels[1]), static_cast<uint8>(Channels[2]), 255);
			if (Sample.river && Sample.water_type == 0)
			{
				// Rivers are painted on the sampled surface, not floating ribbons.
				Colour = FColor(70, 150, 200, 255);
			}
			OutSurface.Colors.Add(Colour);
			OutSurface.NaturalBiomeIds.Add(static_cast<int32>(Sample.natural_biome));
			OutSurface.WaterTypes.Add(static_cast<int32>(Sample.water_type));
			OutSurface.WaterSurfaceCentimetres.Add(
				Sample.water_surface_m * fantasy_world_generator::centimetres_per_metre);
			OutSurface.TextureCoordinates.Emplace(static_cast<double>(Column) / static_cast<double>(Columns - 1),
				static_cast<double>(Row) / static_cast<double>(Rows - 1));
			Lowest = FMath::Min(Lowest, HeightCentimetres);
			Highest = FMath::Max(Highest, HeightCentimetres);
		}
	}
	OutSurface.MinimumHeightCentimetres = Lowest;
	OutSurface.MaximumHeightCentimetres = Highest;
	OutSurface.Triangles.Reserve((Rows - 1) * (Columns - 1) * 6);
	for (int32 Row = 0; Row + 1 < Rows; ++Row)
	{
		for (int32 Column = 0; Column + 1 < Columns; ++Column)
		{
			const int32 TopLeft = Row * Columns + Column;
			const int32 TopRight = TopLeft + 1;
			const int32 BottomLeft = TopLeft + Columns;
			const int32 BottomRight = BottomLeft + 1;
			// Source winding reversed once, here, for Unreal's left-handed frame.
			OutSurface.Triangles.Add(TopLeft);
			OutSurface.Triangles.Add(BottomLeft);
			OutSurface.Triangles.Add(TopRight);
			OutSurface.Triangles.Add(TopRight);
			OutSurface.Triangles.Add(BottomLeft);
			OutSurface.Triangles.Add(BottomRight);
		}
	}
	return true;
#else
	(void)LatitudeRows;
	OutDiagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
	return false;
#endif
}

FFantasyAssetBinding UFantasyWorldGeneratorSubsystem::ResolveAsset(const FString& AssetId) const
{
	FFantasyAssetBinding Binding;
	Binding.AssetId = AssetId;
	Binding.Status = TEXT("unknown_identity");
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (!State.IsValid() || !State->bRegistryLoaded)
	{
		Binding.Status = TEXT("registry_missing");
		Binding.Diagnostic = TEXT("asset registry was not loaded; no identity can be resolved");
		return Binding;
	}
	const fantasy_world_generator::AssetBinding* Found = State->Registry.find(std::string(TCHAR_TO_UTF8(*AssetId)));
	if (Found == nullptr)
	{
		Binding.Diagnostic = TEXT("identity is not in the exhaustive catalogue registry");
		return Binding;
	}
	Binding.Kind = FString(UTF8_TO_TCHAR(Found->kind.c_str()));
	Binding.Status = FString(UTF8_TO_TCHAR(Found->status.c_str()));
	Binding.ObjectPath = FString(UTF8_TO_TCHAR(Found->path.c_str()));
	if (!Found->bound())
	{
		Binding.Diagnostic = FString::Printf(TEXT("identity has no engine binding: %s"),
			*FString(UTF8_TO_TCHAR(Found->reason.c_str())));
	}
#else
	Binding.Status = TEXT("registry_missing");
	Binding.Diagnostic = TEXT("This plugin build has no Core translation units; install the packaged plugin.");
#endif
	return Binding;
}

int32 UFantasyWorldGeneratorSubsystem::CountUnboundAssets() const
{
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	if (State.IsValid() && State->bRegistryLoaded)
	{
		return static_cast<int32>(State->Registry.unbound().size());
	}
#endif
	return 0;
}

FFantasyWorldGeneratorStatus UFantasyWorldGeneratorSubsystem::GetStatus() const
{
	FFantasyWorldGeneratorStatus Status;
	Status.bCoreIncludePathResolved = FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT != 0;
	Status.bCoreGenesisLinked = FANTASY_WORLD_GENERATOR_CORE_LINKED != 0;
	Status.bNativeGenerateAvailable = FANTASY_WORLD_GENERATOR_CORE_LINKED != 0;
#if FANTASY_WORLD_GENERATOR_CORE_LINKED
	Status.CoordinateContractVersion = static_cast<int32>(fantasy_world_generator::coordinate_version);
	Status.SupportedRecipeVersion = static_cast<int32>(fantasy_world_generator::genesis_recipe);
	Status.WorldContractVersion = static_cast<int32>(fantasy_world_generator::world_contract_version);
	Status.TerrainDetailVersion = static_cast<int32>(fantasy_world_generator::terrain_detail_version);
	if (State.IsValid() && State->bRegistryLoaded)
	{
		Status.bAssetRegistryLoaded = true;
		Status.AssetRegistryRows = static_cast<int32>(State->Registry.size());
		Status.AssetRegistryUnbound = static_cast<int32>(State->Registry.unbound().size());
		Status.AssetListSha256 = FString(UTF8_TO_TCHAR(State->Registry.asset_list_sha256().c_str()));
	}
#endif
	// Stays false until a packaged Win64 generate to materialize run is recorded.
	Status.bUnrealQualified = false;
	return Status;
}
