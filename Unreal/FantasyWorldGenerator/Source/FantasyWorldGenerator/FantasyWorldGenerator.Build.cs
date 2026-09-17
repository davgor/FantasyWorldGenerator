// Original material owned by David Gorden; see the repository LICENSE.

using System.IO;
using UnrealBuildTool;

public class FantasyWorldGenerator : ModuleRules
{
	public FantasyWorldGenerator(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		CppStandard = CppStandardVersion.Cpp20;

		// Core/ reports failures as standard C++ fantasy_world_generator::Error exceptions, so this
		// module must opt into exception handling before it can wrap that boundary.
		bEnableExceptions = true;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
		});

		// Core/ is engine-independent and must stay free of UObject types. Only an include
		// path is published here: Private/FantasyWorldGeneratorCoreContract.cpp reads genesis.hpp to
		// static-assert the shared constants, and no Core translation unit is compiled or
		// linked yet. TODO(ML-03e): compile the Core sources excluding Core/tests into this
		// module and delete the private mirror in Public/FantasyWorldGeneratorFrame.h.
		string CoreDirectory = ResolveFantasyWorldGeneratorCoreDirectory();
		bool GenesisPresent = CoreDirectory != null && File.Exists(Path.Combine(CoreDirectory, "genesis.cpp"));
		if (CoreDirectory != null)
		{
			PrivateIncludePaths.Add(CoreDirectory);
		}

		// Reported by the subsystem so a host can log what is actually linked instead of
		// assuming that an enabled plugin means native generate exists.
		PrivateDefinitions.Add("FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT=" + (CoreDirectory != null ? "1" : "0"));
		PrivateDefinitions.Add("FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT=" + (GenesisPresent ? "1" : "0"));
	}

	/// Vendored copy first, so a plugin copied into a project without the generator
	/// checkout still resolves; then the in-repository sibling tree at <plugin>/../../Core.
	private string ResolveFantasyWorldGeneratorCoreDirectory()
	{
		string[] Candidates =
		{
			Path.Combine(ModuleDirectory, "FantasyWorldGeneratorCore"),
			Path.Combine(PluginDirectory, "..", "..", "Core"),
		};
		foreach (string Candidate in Candidates)
		{
			if (File.Exists(Path.Combine(Candidate, "numeric.hpp")))
			{
				return Path.GetFullPath(Candidate);
			}
		}
		return null;
	}
}
