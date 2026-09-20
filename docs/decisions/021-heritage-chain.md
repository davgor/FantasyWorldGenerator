# 021 — Heritage ships as its own leaf package, not as a registry section

## Decision

The categorical layer describing what a people is like — seventeen key traits, a derived
culture, a derived language genome — lives in `Sim/heritage`, a leaf package with its own
policy documents and revisions. It adds no bytes to `Sim/icarus_sim/civilizations.json`.

Derivation is derive-plus-override: traits are authored, culture is a pure function of traits,
the genome is a pure function of culture and physiology, and each derived layer may be patched
by a sparse override file. An override that restates the derived value is a load error.

## Why not a section of the civilization registry

The registry was the obvious home. `civilization_registry.py:159` already lists the sections
each entity owns, and adding an eleventh is a two-line change on the Python side.

It was rejected because of what `registry_identity()` costs. That function
(`civilization_registry.py:307-310`) hashes the whole *resolved* registry document, and
`terrain_history.py:558-559` refuses to advance a saved world whose registry hash has moved.
Adding bytes to `civilizations.json` therefore **invalidates every saved world in existence**,
on the day the data lands, for a layer that no placement code reads yet. A sibling linked file
does not escape this either: `_resolve` merges the linked document before hashing.

Two further costs pointed the same way:

- A categorical field inside the `population` block is a **native parse failure**, not an
  ignored field. `Core/profiles.cpp:256` handles profile fields with
  `profile.traits.emplace(key, catalogue::number(trait.second))` as its *default branch*. The
  identity strings that already cross (`kind`, `environment`, `allocation_group`,
  `structure_blocks`) survive only because they are read as explicitly named fields at
  `:246-252`. A new string key reaches `number()` and throws. The widely-held belief that the
  untyped `map<string,double>` absorbs any new trait holds only for numerics.
- `terrain_profiles.py` is provenance-pinned and computes a `definition_hash` over each whole
  profile, so one added field re-hashes all thirteen and costs a manifest revision.

By contrast a top-level key in the *exported* catalogue is free: `Catalogues::parse`
(`Core/profiles.cpp:218`) reads the document only through named lookups and has no
strict-schema pass, so an export can land ahead of the C++ that reads it.

## Why this is not a fifth parallel catalogue

`PLAN.md:63` warns against two independently edited catalogues sharing semantic ids, and race
data had already forked four ways: `terrain_ruins.CULTURE_SCHOOL` with an unsynchronised twin
in `Core/legacy.cpp`, `alignment.json` `civilization_bias`, `pantheon.json` `affinities`, and
`hero_guild_policies.json`. A fifth table would make that worse unless it is the place the
others converge.

Three structural rules make that convergence safe rather than aspirational:

1. **Heritage owns no identifiers.** Every key is a `civilization_ids()` or `parent_races` key,
   asserted in both directions by `tests/test_heritage_registry_binding.py`.
2. **The trait and culture layers contain no numbers**, enforced at load. It is therefore not
   possible to author a second `resource_weight` beside the real one. The separation from the
   registry's 37 numeric fields is structural, not a matter of discipline.
3. **Heritage is a leaf.** It never imports `icarus_sim`, matching the contract `story_web`
   states at `__init__.py:6`. `resolve()` takes a parent race rather than looking one up, and
   the package carries no seed logic — callers pass their own draw.

The price of leafness is two restated enums, the civilization ids and the eight known magic
schools. The binding test is what pays it, and deleting that test is what would let the layer
drift.

## Identity

`heritage_identity()` hashes the **resolved** twelve peoples, not the source bytes. A
derivation-rule edit that changes no output therefore invalidates nothing, while a
one-character override that does change an output is caught. This is deliberately unlike
`registry_identity()`, which hashes the authoring document including fields nothing reads; the
heritage tables will be edited far more often, and a hash that fires on every touch would be
ignored within a week.

Age advancement is **not** gated on the heritage identity until a consumer reads it, and when
it is the gate gets its own message so a rejection says which catalogue moved.

## Consequences

- No saved world is invalidated by this layer *existing*. A test asserts `registry_identity()`
  is unchanged with heritage present. Publishing the layer is a separate matter: the
  `civilizations` block went 2 -> 3 and `terrain_history` gates replay on it, so worlds generated
  before that bump are rejected on age advance. The placement decision avoided an unnecessary
  invalidation, not every possible one.
- `terrain_ruins.CULTURE_SCHOOL` is retired in favour of the `magic_school` key trait. The
  twelve resolved values are identical to the constant, so ruin legacies and the leylines they
  seed do not move. The historical values are pinned literally in the binding test, because a
  derived mapping compared against itself proves nothing.
- `Core/legacy.cpp` still holds its own literal copy. Routing it through the exported catalogue
  needs a `Catalogues&` plumbed into `ruin_legacy`, which touches `Core/ages.cpp`; until then a
  source-level test asserts the two tables still agree, and retires itself when the literal goes.
- Heritage does not hot-reload, unlike the registry. Packaged resources carry no stat to key a
  cache on, and the tables are immutable at runtime.
