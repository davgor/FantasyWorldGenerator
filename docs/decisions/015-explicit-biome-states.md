# 015 — Retire biome compatibility before downstream consumption

The user authorized a clean start on 2026-09-15, including retirement of old recipe/save compatibility. This supersedes the normal seed-preservation policy for this migration only.

Recipe 3 / generator 8 / terrain 6 removes the five legacy phenotype categories. Natural IDs remain stable and sparse. Explicit natural-core × school states drive population preferences, food multipliers, building selection and production asset selectors. Current APIs reject recipe 1/2 and old age-world contracts; there is no save upgrader. Regenerate old worlds. Recipe 3 determinism, phase isolation and replay remain required.

Profile and building-pack schema 2, world/asset-list envelope schema 2, and production catalogue schema 2 expose the new semantics. Food factors are exact variant overrides followed by the existing local magic-risk loss. This changes settlement counts, food balances and subsequent history by design. Existing physical, conservation, habitat-safety and deterministic tests remain applicable; old phenotype assertions are replaced by explicit-state behavioral coverage.

Historical extracted source hashes remain intact in provenance. Revised destination hashes identify these intentional changes and reference this decision. No Unreal assets or engine integrations are modified or validated.
