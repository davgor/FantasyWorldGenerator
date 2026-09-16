# Historical city shape catalogue

Owner: local agent. Status: complete.

- A1: Research distinct historical morphologies with primary institutional sources and embed attribution/evidence separately from proposed game parameters.
- A2: New city_shapes.json stores at least 16 varied patterns, terrain eligibility, preference weights, orientation/housing guidance and seeded variation ranges.
- A3: A standalone validated selector proves location gating, repeatable variety and no unsafe fallback; document missing footprint/geometry integration. Existing generation and assets remain unchanged.

Behavioral tests observed failing before implementation. Research: UNESCO/ICOMOS heritage records and Cornell's John Reps collection. Full source URLs and notes are in JSON and docs/city-shapes.md. Local evidence under Artifacts/city-shapes. No commits, publishing, Unreal changes or runtime-layout integration requested in this slice.

## Accepted evidence

A1-A3 verified. Sixteen patterns from fourteen source records; fifteen enabled by default and the Renaissance extension opt-in. Each includes evidence/adaptation notes, hard site gates, preference weights, street/outline anchors, housing-fill instructions and variable parameters. No race restrictions. The selector supports deterministic weighted choice, local repetition penalties and no-match handling; it does not generate geometry.

162 simulation tests and 15 repository tests passed (177 total), including six new city-shape tests. Showcase export is reproducible; exhaustive asset output unchanged. The initial asset comparison used the platform default decoding on UTF-8 text and misread accented names; repeating with explicit UTF-8 confirmed equality. Lab smoke, compileall and git diff checks passed. Examples for inland, port, ridge and river sites saved under Artifacts/city-shapes.

Required python3 validator is unavailable through the Windows alias; Python fallback stops at the pre-existing unrelated Contracts/catalogues/world-assets.json provenance mismatch. Only scoped canonical-doc provenance updated. No engine integration claimed.

Next action: derive footprint-scale location inputs from terrain and water masks, then generate connected streets/plots and fit measured civilization services before housing fill. Include shape-catalogue identity in runtime replay contracts when integrated. No commits, publication or Unreal changes.
