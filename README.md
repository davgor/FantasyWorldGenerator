# FantasyWorldGenerator

Independent MathLab simulation repository and producer of the versioned Unreal plugin consumed by the separate anime game project.

## Start here

Read [PLAN.md](PLAN.md). It contains the source baseline and extraction scope, existing capability limits, ML-00–13 implementation tickets, shared Unreal package contract, ownership boundaries, acceptance gates and relevant world-system design.

The first implementation task is **ML-00: extract the existing MathLab from `davgor/icarusUnreal`, preserve provenance and dependencies, and verify a standalone baseline**. The destination repository already exists; do not create another one. The plan identifies the creature-catalogue dependency outside `Sim/` that must be retained or deliberately replaced with an equivalent pinned fixture.

Follow with ML-01/02 and the small ML-03 native-runtime/plugin proof. Ordinary reference/core development remains independent of the anime game's assets and character-creator progress.

## Status

This repository currently contains the planning handoff. MathLab source extraction, implementation, Unreal package building and release publication are future tasks. A published plan is not evidence that those features are implemented or validated.
