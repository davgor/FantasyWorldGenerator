// Original material owned by David Gorden; see the repository LICENSE.

#include "FantasyWorldGeneratorSubsystem.h"

#ifndef FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT 0
#endif
#ifndef FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT
#define FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT 0
#endif

FVector UFantasyWorldGeneratorSubsystem::LocalMetresToUnreal(double EastMetres, double UpMetres, double NorthMetres)
{
	const FantasyWorldGenerator::FUnrealCentimetres Converted =
		FantasyWorldGenerator::LocalMetresToUnrealCentimetres(FantasyWorldGenerator::FLocalMetres{EastMetres, UpMetres, NorthMetres});
	return FVector(Converted.X, Converted.Y, Converted.Z);
}

FVector UFantasyWorldGeneratorSubsystem::LocalUnitAxisToUnreal(FVector SourceEastUpNorth)
{
	const FantasyWorldGenerator::FUnrealCentimetres Permuted = FantasyWorldGenerator::LocalUnitAxisToUnreal(
		FantasyWorldGenerator::FLocalMetres{SourceEastUpNorth.X, SourceEastUpNorth.Y, SourceEastUpNorth.Z});
	return FVector(Permuted.X, Permuted.Y, Permuted.Z);
}

bool UFantasyWorldGeneratorSubsystem::ValidateGenerateRequest(int32 RecipeVersion, int64 Seed, int32 RegionalRasterSize,
	bool bGlobeShape, FString& OutStatusName, FString& OutDiagnostic)
{
	FantasyWorldGenerator::FGenerateRequest Request;
	Request.RecipeVersion = RecipeVersion;
	Request.Seed = Seed;
	Request.RasterSize = RegionalRasterSize;
	Request.bGlobeShape = bGlobeShape;

	const FantasyWorldGenerator::EGenerateRequestStatus Status = FantasyWorldGenerator::ValidateGenerateRequest(Request);
	OutStatusName = UTF8_TO_TCHAR(FantasyWorldGenerator::GenerateRequestStatusName(Status));
	OutDiagnostic = UTF8_TO_TCHAR(FantasyWorldGenerator::DescribeGenerateRequestStatus(Status));
	return Status == FantasyWorldGenerator::EGenerateRequestStatus::Valid;
}

FFantasyWorldGeneratorStatus UFantasyWorldGeneratorSubsystem::GetStatus()
{
	FFantasyWorldGeneratorStatus Status;
	Status.CoordinateContractVersion = static_cast<int32>(FantasyWorldGenerator::CoordinateContractVersion);
	Status.SupportedRecipeVersion = static_cast<int32>(FantasyWorldGenerator::SupportedRecipeVersion);
	Status.bCoreIncludePathResolved = FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT != 0;
	Status.bCoreContractChecked = FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT != 0;
	Status.bCoreGenesisLinked = false; // No Core translation unit is compiled into this module yet.
	Status.bNativeGenerateAvailable = false;
	Status.bUnrealQualified = false;
	return Status;
}
