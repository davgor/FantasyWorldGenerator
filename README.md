# FantasyWorldGenerator

Independent MathLab simulation repository and future producer of the versioned Unreal plugin consumed by the separate anime game project.

## Start here

Read [PLAN.md](PLAN.md). It contains the source baseline and extraction scope, existing capability limits, ML-00–13 implementation tickets, shared Unreal package contract, ownership boundaries, acceptance gates and relevant world-system design.

The active implementation task is [ML-00](board/in-progress/ML-00.md): extract the existing MathLab from `davgor/icarusUnreal`, preserve provenance and dependencies, and verify a standalone baseline. The pinned Python reference remains importable as `icarus_sim`; new repository-level commands use the `fantasy_world_generator` facade.

Follow with ML-01/02 and the small ML-03 native-runtime/plugin proof. Ordinary reference/core development remains independent of the anime game's assets and character-creator progress.

## Status

The working tree contains an ML-00 extraction candidate and an export-only Python/JSON packaging candidate. Local reference tests and browser/export checks must pass, and clean-checkout CI must supply the final isolation evidence before ML-00 closes. No native kernel, Unreal plugin, cooked consumer, or immutable runtime package has been validated.

## Staged world lab

Run `python3 tools/terrain_lab.py --serve` for the sixteen-stage recipe 2 lab, including deep-time tectonics, eight leylines, 104 magical biome variants and two civilization ages. Use Previous/Next to inspect saved stages. [Behavior and replay contract](docs/terrain-world-layers.md).

## Local validation

Python 3.9+ and the standard library are sufficient for the reference tests. Packaging uses `setuptools`.

```bash
python3 tools/validate_repo.py
PYTHONPATH=Sim python3 -m fantasy_world_generator generate --seed 42 --size 33 --output Artifacts/world.json
PYTHONPATH=Sim python3 -m fantasy_world_generator asset-list --output Artifacts/fantasy-world-assets.json
```

See [the documentation map](docs/README.md), [extraction provenance](provenance/README.md), and [current ticket board](board/README.md).
