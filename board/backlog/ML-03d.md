# ML-03d — Native in-process world genesis for Unreal

## Requested behavior

Port recipe-3 **world** genesis into `Core/` so the Unreal plugin can generate in process. This slice exists because the native core is still the bounded counter; Python world JSON is not the generate API. Freeze the native API only after it includes the visualization envelope **and** the sampling/frame/registry contracts UnrealWorldGen will keep:

- On-demand detailed surface samples (continuous terrain / height-tile contract), not only a `size`-cell regional raster
- Natural biome IDs and lab RGB colors; mutation colors where catalogues supply them
- Water masks for a blue landscape layer
- `world_scene` buildings with metre width/depth/height, positions, and exported axes
- Street and regional-road polylines on the **detailed** surface, with shared junction points
- Nest / habitat anchors on that surface
- Source-to-Unreal mapping fixtures: east→Unreal +X, north→Unreal +Y, up→Unreal +Z, lengths ×100, unit axes unscaled, winding reverse
- Asset-ID registry schema: every exhaustive-catalogue identity has a binding slot (path or explicit missing)

Python `POST /world/generate` remains the reference oracle and the browser lab. It is not an Unreal dependency.

Default first native generate: recipe 3, size 65 regional climate, tectonic globe, **plus** detail sampling at the display/contact resolution used by ML-03e. Interactive regional cap stays 257. Reject unsupported recipe/schema versions.

## Proposed mechanism

Keep Unreal types out of `Core/`. Versioned generate request/result, sample-surface, and registry-table documents. Match existing kernel style: finite JSON, deterministic ordering.

Implement incrementally **headlessly**:

1. Request validation and capability/version reporting.
2. Coordinate fixtures for the Unreal permutation (cardinals, elevation, seam/pole) against the oracle.
3. On-demand height/mask samples vs tile/patch/city foundation fixtures (same function as [continuous terrain](../../docs/continuous-terrain.md)).
4. Regional classification + colors vs pinned Python fixtures.
5. Water cells.
6. `world_scene` footprints and roads; contact tests: foundation corners/centres on sampled height; road samples on grade; junctions coincide; seam-adjacent equality.
7. Nest anchors on the sampled surface.
8. Registry coverage: one row per exhaustive asset-list ID.

Each step starts with a behavioral test that fails for the missing output. Do not approximate Python; version numeric divergence. Public operations: describe capabilities; generate genesis; sample surface; report seed/config/digest. No HTTP in Core.

## Dependencies and unresolved decisions

This slice is epic item 1’s native generate. Epic items 2–3 (importer, packaged loop) are ML-03e and stay blocked until this envelope, sampling contract, axis fixtures, and catalogue registry coverage are proven headlessly.

Settled by [decision 018](../../docs/decisions/018-unrealworldgen-dev-consumer.md) and [Unreal integration](../../docs/unreal-integration.md).

Open: native vs Python numeric thresholds; display sample density vs 4 m city surfaces; PRNG contract if streams cannot match bit-for-bit.

## Sources consulted

- Astra 2026-09-16: axis mapping, detailed contact, registry, cooked handoff (cooked owned by ML-03e).
- `PLAN.md` PK02–04/08/10; capabilities v1; world-output schema; unified globe scene; continuous terrain.

## Files and assets in scope

`Core/`, `Contracts/` / `Fixtures/` (generate, coordinates-unreal permutation, registry coverage), native packaging/qualify tools and tests, docs listed above. No Unreal maps or `.uasset` edits.

## Acceptance and evidence

- Tests precede each layer. Isolated native qualify runs without Unreal.
- Same seed: visualization fields match reviewed Python fixtures within the numeric contract.
- Surface samples match height-tile/patch identities at shared indices; city foundation heights match planner exports.
- Cardinal/elevation fixtures pass for the Unreal mapping without placing Unreal types in Core (pure centimetre vectors).
- Registry table covers 100% of exhaustive asset-list IDs; missing bindings are explicit, not omitted.
- Unsupported versions fail explicitly.
- This ticket does not cook Unreal.

## Documentation impact

Decision 018, Unreal integration, capabilities “future Unreal boundary,” this ticket, parent ML-03, ML-03e.

## Adversarial review and limitations

- A 65-grid globe raster cannot stand in for local streets or foundations.
- Sky islands stay disabled. Live simulation (jobs, residue, age advance) is out of scope.
- Registry rows may point at a shared placeholder path; they still must exist per ID.

## Handoff

Do not open UnrealWorldGen implementation until the above tests pass. Next: [ML-03e](ML-03e.md).
