# FantasyWorldGenerator plugin

Runtime Unreal code plugin owned by FantasyWorldGenerator and consumed by sibling
**UnrealWorldGen** (Unreal 5.8, Win64). See [decision 018](../../docs/decisions/018-unrealworldgen-dev-consumer.md)
and [Unreal integration](../../docs/unreal-integration.md) for the canonical boundary.

## What exists

- `FantasyWorldGenerator.uplugin`: one `Runtime` module, `Win64` allow list, `EnabledByDefault` false,
  `CanContainContent` false. No `/Game` path, content directory or game-specific reference.
- `Source/FantasyWorldGenerator/Public/FantasyWorldGeneratorFrame.h`: engine-independent source-to-Unreal frame
  (`U = (east, north, up) * 100`, unit axes permuted but unscaled) and generate-request
  validation (recipe 3, uint32 seed, raster 1..257, tectonic globe) reporting the Core
  failure codes `UNSUPPORTED_VERSION`, `STATE_CAPACITY` and `INVALID_INPUT`.
- `Source/FantasyWorldGenerator/Public/FantasyWorldGeneratorSubsystem.h`: `UFantasyWorldGeneratorSubsystem`, a thin
  `UEngineSubsystem` wrapper exposing the conversion, validation and a status struct.
- `Source/FantasyWorldGenerator/Private/FantasyWorldGeneratorCoreContract.cpp`: static asserts tying the mirror's
  constants to `Core/genesis.hpp` whenever Core is reachable.
- `Tests/frame_driver.cpp`: headless consumer for the frame rules, outside `Source/` so
  UnrealBuildTool does not compile it. Driven by `tests/test_plugin_frame.py`.

## What does not exist

No world generate, on-demand surface sampling, Landscape, water overlay, hub, asset-ID
registry materialization, or cooked-runtime claim. Those are [ML-03d](../../board/backlog/ML-03d.md)
and [ML-03e](../../board/backlog/ML-03e.md). `UFantasyWorldGeneratorSubsystem::GetStatus` reports
`bNativeGenerateAvailable` and `bUnrealQualified` as false so a host cannot mistake an
enabled plugin for a working generator.

This plugin has **not** been compiled by Unreal Build Tool, loaded by an editor, or cooked.
Source existence is not runtime acceptance.

## Core wrapping

`Core/` stays free of Unreal and UObject types. `FantasyWorldGenerator.Build.cs` resolves a Core
directory (vendored `Source/FantasyWorldGenerator/FantasyWorldGeneratorCore`, else `<plugin>/../../Core`), adds it
as a private include path, and reports `FANTASY_WORLD_GENERATOR_CORE_DIRECTORY_PRESENT` /
`FANTASY_WORLD_GENERATOR_CORE_GENESIS_PRESENT`. It compiles and links no Core translation unit, so the frame
and validation rules in `FantasyWorldGeneratorFrame.h` are a **temporary private mirror** of
`Core/genesis.{hpp,cpp}` and `Fixtures/unreal-frame-v1.json`. `FantasyWorldGeneratorCoreContract.cpp`
static-asserts Core's recipe, seed, grid and centimetre constants so the two cannot drift
silently.

ML-03e should compile the Core sources excluding `Core/tests` into this module and forward
`FantasyWorldGeneratorFrame.h` to Core rather than keeping two copies. Two things are needed first:

1. Core's request boundary is JSON-value based and transports offsets as exact whole metres or
   bounded decimal strings (`fantasy_world_generator::source_centimetres`), deliberately keeping floats out of
   the centimetre frame. An adapter converting sampled Landscape/foundation heights needs a
   numeric Core entry point rather than formatting a decimal string per vertex.
2. Core translation units must be verified to compile inside an Unreal module. The module
   already sets `bEnableExceptions` because Core reports failures as `fantasy_world_generator::Error`.

## Use from UnrealWorldGen

1. Build the archive: `python tools/package_plugin.py`.
2. Extract `FantasyWorldGenerator/` into `UnrealWorldGen/Plugins/`.
3. Enable `FantasyWorldGenerator` in `UnrealWorldGen.uproject`, then regenerate project files and build.

Step 3 has not been performed; it waits on the Unreal MCP editor owner (acceptance A3).
