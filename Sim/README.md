# Portable terrain reference

`icarus_sim/terrain_*` is the preserved engine-independent mathematical reference, originally ported from IcarusAI and extended with layered-world recipe 1. The extraction supports Python 3.9+ and uses only the standard library; it has no Unity or Unreal dependency.

Run `python3 tools/validate_repo.py` from the standalone repository root. Launch the browser lab with `python3 tools/terrain_lab.py --serve`. The default is a full tectonic globe with Random and Parameters modes. See [layered world documentation](../docs/terrain-world-layers.md) for recipes, aquatic habitats, independent leylines, sky surfaces and supply diagnostics.

This is the mathematical reference, not an Unreal runtime plugin. World time/events and legacy appearance-envelope modules from the old Sim tree were not included in this terrain-only port. Their design is retained in the historical docs; ML-01–03 own the new contract, bounded kernel, and runtime-plugin proof.
