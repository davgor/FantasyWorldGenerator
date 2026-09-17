# FantasyWorldGenerator

Independent MathLab simulation repository and future producer of the versioned Unreal plugin consumed by the separate anime game project.

## Start here

Read [PLAN.md](PLAN.md). It contains the source baseline and extraction scope, existing capability limits, ML-00–13 implementation tickets, shared Unreal package contract, ownership boundaries, acceptance gates and relevant world-system design.

The extraction is complete; see [ML-00 evidence](board/done/ML-00.md) and the [current board](board/README.md). The pinned Python reference remains importable as `icarus_sim`; repository-level commands and portable contract helpers use the `fantasy_world_generator` facade.

ML-01/02 and the scoped ML-03a typed C++ counter proof are complete. ML-03b/c add native JSON/numeric conformance and a reproducible source proof bundle. **ML-03 (in progress)** is Unreal setup: native world generate ([ML-03d](board/backlog/ML-03d.md)), then `.uplugin` / UnrealWorldGen importer / packaged generate loop ([ML-03e](board/backlog/ML-03e.md)). Ordinary reference/core development remains independent of the anime game's assets and character-creator progress.

## Status

The repository contains the standalone world generator, portable contract fixtures and a [bounded Python counter kernel](Contracts/kernel-v1.md) proving candidate evaluation, idempotent effects and checkpoint/resume. A [C++ counter core](Core/README.md) shares its JSON/numeric fixtures and can be built from an isolated source proof bundle. The opt-in [hero guild planner](docs/hero-guild.md) estimates membership, activity, service and beds without changing generated cities. This kernel is separate from generated worlds and does not implement general gameplay systems. Unreal plugin, cooked UnrealWorldGen generate loop and immutable hosted release qualification remain open. Distribution is [private and owner-controlled](LICENSE).

## Staged world lab

Run `python3 tools/terrain_lab.py --serve` for the sixteen-stage recipe 3 lab, including deep-time tectonics, eight leylines, 104 magical biome variants and two civilization ages. Use Previous/Next to inspect saved stages. Old recipe/save compatibility is retired: regenerate worlds for the natural-core and explicit magical-state contract. [Behavior and replay contract](docs/terrain-world-layers.md).

## Local validation

Python 3.9+ and the standard library are sufficient for the reference tests. Packaging uses `setuptools`.

```bash
python3 tools/validate_repo.py
PYTHONPATH=Sim python3 -m fantasy_world_generator generate --seed 42 --size 33 --output Artifacts/world.json
PYTHONPATH=Sim python3 -m fantasy_world_generator asset-list --output Artifacts/fantasy-world-assets.json
PYTHONPATH=Sim python3 -m fantasy_world_generator capabilities --output Artifacts/capabilities.json
```

See [the documentation map](docs/README.md), [extraction provenance](provenance/README.md), and [current ticket board](board/README.md).
