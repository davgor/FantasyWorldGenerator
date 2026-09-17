// Original material owned by David Gorden; see the repository LICENSE.
//
// Engine-independent mirror of the FantasyWorldGenerator source-to-Unreal boundary
// documented in docs/unreal-integration.md and Fixtures/unreal-frame-v1.json.
//
// This header deliberately contains no Unreal, UObject or Python dependency so the
// same rules can be compiled and checked headlessly (tests/test_plugin_frame.py).
//
// TODO(ML-03e): Core/genesis.{hpp,cpp} is the authoritative implementation of this
// mapping and of generate-request validation, and these rules are a mirror of it.
// Core transports request offsets as exact whole metres or bounded decimal strings
// (fantasy_world_generator::source_centimetres) so no float rounding enters the centimetre frame;
// the doubles below are the engine-side path for sampled positions. Replacing the
// mirror needs a numeric Core entry point in addition to the JSON one, so that an
// Unreal adapter converts sampled heights without formatting decimal strings.
// Private/FantasyWorldGeneratorCoreContract.cpp static-asserts the shared constants whenever Core
// is reachable, so the two cannot drift silently.

#pragma once

#include <cstdint>

namespace FantasyWorldGenerator
{
	/** Source local tangent sample in metres: +east, +up, +north, with east x up = north. */
	struct FLocalMetres
	{
		double East = 0.0;
		double Up = 0.0;
		double North = 0.0;
	};

	/** Unreal world position in centimetres: X is east, Y is north, Z is up. */
	struct FUnrealCentimetres
	{
		double X = 0.0;
		double Y = 0.0;
		double Z = 0.0;
	};

	/** Coordinate/unit contract version this mirror implements. */
	inline constexpr std::int64_t CoordinateContractVersion = 1;

	/** Metre-to-Unreal-centimetre factor. Lengths are scaled exactly once, here. */
	inline constexpr double UnrealCentimetresPerMetre = 100.0;

	/** U = (east, north, up) * 100. Source (X, Y, Z) is never copied into an FVector. */
	inline constexpr FUnrealCentimetres LocalMetresToUnrealCentimetres(const FLocalMetres& Local)
	{
		return FUnrealCentimetres{
			Local.East * UnrealCentimetresPerMetre,
			Local.North * UnrealCentimetresPerMetre,
			Local.Up * UnrealCentimetresPerMetre};
	}

	/** Unit east/up/north axes only permute to (east, north, up); they are not scaled. */
	inline constexpr FUnrealCentimetres LocalUnitAxisToUnreal(const FLocalMetres& Axis)
	{
		return FUnrealCentimetres{Axis.East, Axis.North, Axis.Up};
	}

	// Mirrors fantasy_world_generator::genesis_recipe, fantasy_world_generator::max_seed, fantasy_world_generator::min_grid, fantasy_world_generator::max_grid.

	/** Recipe 3 is the only supported generator recipe; earlier recipes are retired. */
	inline constexpr std::int64_t SupportedRecipeVersion = 3;

	/** Unreal supplies a random uint32 seed. */
	inline constexpr std::int64_t MaximumSeed = 4294967295;

	/** Regional raster samples per side. */
	inline constexpr std::int64_t MinimumRasterSize = 1;
	inline constexpr std::int64_t MaximumRasterSize = 257;

	enum class EGenerateRequestStatus : std::uint8_t
	{
		Valid = 0,
		RetiredRecipeVersion,
		SeedOutOfRange,
		RasterSizeOutOfRange,
		RetiredShape,
	};

	struct FGenerateRequest
	{
		std::int64_t RecipeVersion = SupportedRecipeVersion;
		std::int64_t Seed = 0;
		std::int64_t RasterSize = 129;
		bool bGlobeShape = true;
	};

	inline constexpr EGenerateRequestStatus ValidateGenerateRequest(const FGenerateRequest& Request)
	{
		if (Request.RecipeVersion != SupportedRecipeVersion)
		{
			return EGenerateRequestStatus::RetiredRecipeVersion;
		}
		if (Request.Seed < 0 || Request.Seed > MaximumSeed)
		{
			return EGenerateRequestStatus::SeedOutOfRange;
		}
		if (Request.RasterSize < MinimumRasterSize || Request.RasterSize > MaximumRasterSize)
		{
			return EGenerateRequestStatus::RasterSizeOutOfRange;
		}
		if (!Request.bGlobeShape)
		{
			return EGenerateRequestStatus::RetiredShape;
		}
		return EGenerateRequestStatus::Valid;
	}

	inline constexpr bool IsGenerateRequestValid(const FGenerateRequest& Request)
	{
		return ValidateGenerateRequest(Request) == EGenerateRequestStatus::Valid;
	}

	/** Diagnostic wording for logs. Stable failure codes belong to the Core contract. */
	inline const char* DescribeGenerateRequestStatus(EGenerateRequestStatus Status)
	{
		switch (Status)
		{
		case EGenerateRequestStatus::Valid:
			return "valid";
		case EGenerateRequestStatus::RetiredRecipeVersion:
			return "retired recipe version; recipe 3 is required";
		case EGenerateRequestStatus::SeedOutOfRange:
			return "seed must be an unsigned 32-bit value";
		case EGenerateRequestStatus::RasterSizeOutOfRange:
			return "regional raster size must be 1..257 samples per side";
		case EGenerateRequestStatus::RetiredShape:
			return "recipe 3 generates a tectonic globe; planar shapes are retired";
		}
		return "unknown generate-request status";
	}

	/** Short stable name for the status, for host-side diagnostics and tests. */
	inline const char* GenerateRequestStatusName(EGenerateRequestStatus Status)
	{
		switch (Status)
		{
		case EGenerateRequestStatus::Valid:
			return "valid";
		case EGenerateRequestStatus::RetiredRecipeVersion:
			return "retired_recipe_version";
		case EGenerateRequestStatus::SeedOutOfRange:
			return "seed_out_of_range";
		case EGenerateRequestStatus::RasterSizeOutOfRange:
			return "raster_size_out_of_range";
		case EGenerateRequestStatus::RetiredShape:
			return "retired_shape";
		}
		return "unknown_status";
	}

	/**
	 * Failure code the Core contract raises for the same rejection, so a host reports
	 * one vocabulary whether the mirror or Core validated the request.
	 */
	inline const char* GenerateRequestFailureCode(EGenerateRequestStatus Status)
	{
		switch (Status)
		{
		case EGenerateRequestStatus::Valid:
			return "";
		case EGenerateRequestStatus::RetiredRecipeVersion:
			return "UNSUPPORTED_VERSION";
		case EGenerateRequestStatus::RasterSizeOutOfRange:
			return "STATE_CAPACITY";
		case EGenerateRequestStatus::SeedOutOfRange:
		case EGenerateRequestStatus::RetiredShape:
			return "INVALID_INPUT";
		}
		return "INVALID_INPUT";
	}
}
