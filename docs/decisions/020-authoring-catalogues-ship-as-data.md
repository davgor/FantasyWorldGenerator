# 020 — Authoring catalogues ship as resolved data; the rules stay native

Porting placement into `Core/` on 2026-09-18 raised a question the earlier terrain work
never had to answer: the settlement, planner and nest rules read authored catalogues —
civilization traits, habitat rules, building packs, layout profiles, city shapes, nest
profiles. In Python those live in linked JSON registries with roughly 440 lines of
loader and validation around them.

## Decision

- The producer keeps authoring, linking and validation. `tools/export_catalogues.py`
  writes the settled result to `Contracts/catalogues/native-catalogues-v1.json`, and
  `tools/validate_repo.py --stage checks` fails when that file is stale.
- The native core reads that table (`Core/catalogue.cpp`, `Core/profiles.cpp`) instead
  of re-implementing the registry loader. The table travels in the plugin's `Data/`
  directory beside the asset registry and is staged into cooked builds.
- Catalogue data is real-number data, so it gets its own reader. The kernel's JSON
  domain still refuses floats; nothing about that contract changes.
- Every trait, biome preference and habitat rule the native side reads is compared
  against the Python oracle in `tests/test_native_world.py`. Parsing successfully is
  not evidence that the two implementations agree.

## Reason

This is not the forbidden path. [Decision 018](018-unrealworldgen-dev-consumer.md)
rules out generating a **world** from JSON, a Python sidecar or an embedded
interpreter: a world must come from a seed, in process. Authored catalogues are static
inputs to the rules, exactly like the asset-ID registry that decision already requires
to ship as a table. Re-implementing the authoring validators in C++ would add a second
place to change when a trait is added, with no runtime benefit.

## Consequences

- A catalogue edit reaches the native generator through a regenerated table, so the
  same review gate covers both implementations.
- The plugin manifest records the catalogue version, profile and entity counts and the
  source registry digest, so a consumer can tell which authoring revision it carries.
- Behaviour that is code, not data — scoring, habitat evaluation, layout, placement —
  is still ported and compared layer by layer.
