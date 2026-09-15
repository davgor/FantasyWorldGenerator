# Portable contracts

- `schemas/` contains export-only JSON envelopes for generated genesis data and the exhaustive potential-state asset list.
- `catalogues/world-assets.json` is a pinned semantic requirement input used to enumerate materials, vegetation, structures, effects, people roles, animation, and audio that supported generator states may require.

These files do not contain Unreal object paths or prove that game-owned assets exist. ML-01 will add the stable taxonomy, IDs, units, versions, numeric rules, capability description, and conformance fixtures needed by the native runtime.


The world envelope accepts recipe versions 1 and 2. Recipe 2 uses generation algorithm 7, phase schema 2, magic schema 3, terrain schema 5, and history schema 1. Its ordered build-stage deltas, eight-network intensity inputs, core-plus-school biome catalogue and ruin provenance are documented in [the canonical behavior contract](../docs/terrain-world-layers.md). Existing recipe 0/1 arrays and IDs are preserved.
