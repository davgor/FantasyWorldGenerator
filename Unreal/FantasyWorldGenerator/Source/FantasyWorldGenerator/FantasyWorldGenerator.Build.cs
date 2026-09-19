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
			// IPluginManager locates the registry table that ships beside this module.
			"Projects",
		});

		// Core/ is engine-independent and must stay free of UObject types. The packaged
		// plugin vendors it under FantasyWorldGeneratorCore/, where UnrealBuildTool compiles
		// the translation units with this module; an in-repository checkout resolves the
		// sibling Core/ tree for includes so the header contract still compiles there.
		string CoreDirectory = ResolveFantasyWorldGeneratorCoreDirectory(out bool Vendored);
		bool GenesisPresent = CoreDirectory != null && File.Exists(Path.Combine(CoreDirectory, "genesis.cpp"));
		if (CoreDirectory != null)
		{
			PrivateIncludePaths.Add(CoreDirectory);
		}

		// The asset-ID registry travels with the plugin and must be staged into a cooked
		// build: a missing table is a diagnostic, never an anonymous placeholder spawn.
		foreach (string DataFile in new string[] {"unreal-asset-registry-v1.json", "native-catalogues-v1.json"})
		{
			string Staged = Path.Combine(PluginDirectory, "Data", DataFile);
			if (File.Exists(Staged))
			{
				RuntimeDependencies.Add(Staged);
			}
		}

		// Reported by the subsystem so a host logs what is linked instead of assuming that
		// an enabled plugin means native generate exists.
		PrivateDefinitions.Add("FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT=" + (CoreDirectory != null ? "1" : "0"));
		PrivateDefinitions.Add("FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT=" + (GenesisPresent ? "1" : "0"));
		PrivateDefinitions.Add("FANTASY_WORLD_GENERATOR_CORE_LINKED=" + (Vendored && GenesisPresent ? "1" : "0"));
	}

	/// Vendored copy first: those translation units are inside the module and are compiled
	/// and linked. Otherwise the in-repository sibling tree at <plugin>/../../Core supplies
	/// headers only, which is enough to check the contract but not to generate a world.
	private string ResolveFantasyWorldGeneratorCoreDirectory(out bool Vendored)
	{
		string VendoredDirectory = Path.Combine(ModuleDirectory, "FantasyWorldGeneratorCore");
		if (File.Exists(Path.Combine(VendoredDirectory, "numeric.hpp")))
		{
			Vendored = true;
			return Path.GetFullPath(VendoredDirectory);
		}
		Vendored = false;
		string SiblingDirectory = Path.Combine(PluginDirectory, "..", "..", "Core");
		if (File.Exists(Path.Combine(SiblingDirectory, "numeric.hpp")))
		{
			return Path.GetFullPath(SiblingDirectory);
		}
		return null;
	}
}
