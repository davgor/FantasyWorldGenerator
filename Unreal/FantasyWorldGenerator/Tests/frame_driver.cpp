// Original material owned by David Gorden; see the repository LICENSE.
//
// Headless test consumer for the engine-independent parts of FantasyWorldGenerator. It lives
// outside Source/ so UnrealBuildTool never compiles it into the module. It is driven by
// tests/test_plugin_frame.py against Fixtures/unreal-frame-v1.json.
//
// This proves the mirrored rules, not an Unreal build, editor load or cooked runtime.

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "FantasyWorldGeneratorFrame.h"

namespace
{
	double Number(const char* Text)
	{
		return std::strtod(Text, nullptr);
	}

	long long Integer(const char* Text)
	{
		return std::strtoll(Text, nullptr, 10);
	}

	int Report(const FantasyWorldGenerator::FUnrealCentimetres& Value)
	{
		std::printf("%.17g %.17g %.17g\n", Value.X, Value.Y, Value.Z);
		return 0;
	}
}

int main(int ArgumentCount, char** Arguments)
{
	const char* const Operation = ArgumentCount > 1 ? Arguments[1] : "";
	if (std::strcmp(Operation, "unreal_cm") == 0 && ArgumentCount == 5)
	{
		return Report(FantasyWorldGenerator::LocalMetresToUnrealCentimetres(
			FantasyWorldGenerator::FLocalMetres{Number(Arguments[2]), Number(Arguments[3]), Number(Arguments[4])}));
	}
	if (std::strcmp(Operation, "unit_axis") == 0 && ArgumentCount == 5)
	{
		return Report(FantasyWorldGenerator::LocalUnitAxisToUnreal(
			FantasyWorldGenerator::FLocalMetres{Number(Arguments[2]), Number(Arguments[3]), Number(Arguments[4])}));
	}
	if (std::strcmp(Operation, "validate_generate") == 0 && ArgumentCount == 6)
	{
		FantasyWorldGenerator::FGenerateRequest Request;
		Request.RecipeVersion = Integer(Arguments[2]);
		Request.Seed = Integer(Arguments[3]);
		Request.RasterSize = Integer(Arguments[4]);
		Request.bGlobeShape = Integer(Arguments[5]) != 0;
		const FantasyWorldGenerator::EGenerateRequestStatus Status = FantasyWorldGenerator::ValidateGenerateRequest(Request);
		const bool Valid = Status == FantasyWorldGenerator::EGenerateRequestStatus::Valid;
		std::printf("%s %s\n", FantasyWorldGenerator::GenerateRequestStatusName(Status),
			Valid ? "-" : FantasyWorldGenerator::GenerateRequestFailureCode(Status));
		return Valid ? 0 : 2;
	}
	std::fprintf(stderr, "usage: frame_driver unreal_cm|unit_axis east up north\n"
		"       frame_driver validate_generate recipe seed size globe\n");
	return 64;
}
