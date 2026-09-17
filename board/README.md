# FantasyWorldGenerator ticket board

- `in-progress/` contains active work with recorded scope and evidence.
- `backlog/` contains reviewed, dependency-ordered work that is not yet active.
- `done/` contains imported historical LAB evidence and completed local tickets.

ML-00–03 have concrete local tickets. ML-03 is the Unreal setup epic: (1) `.uplugin` + in-process native world generate, (2) UnrealWorldGen importer, (3) packaged generate → materialize. Slices: [ML-03d](backlog/ML-03d.md) then [ML-03e](backlog/ML-03e.md). ML-04–13 remain roadmap epics in `PLAN.md` and must be decomposed into bounded behavioral slices before implementation.

HERO-GUILD’s opt-in planning calculator is complete. ML-00, ML-01 (including a/b/c/d), ML-02 and the scoped ML-03a headless C++ proof are complete. ML-03 is active. ML-03b/c are complete. Native recipe-3 generate, detailed sampling, Unreal-axis fixtures and catalogue registry coverage are queued as [ML-03d](backlog/ML-03d.md). The UnrealWorldGen pass is [ML-03e](backlog/ML-03e.md): hub, registry placeholders, terrain contact, packaged Win64 digest. Decision 018 forbids a Python sidecar. Hosted CI/immutable channel may remain on parent ML-03 after that digest.
