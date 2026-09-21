# Publishing and asset-list policy

Every push to `main` produces one export-only workflow artifact named `fantasy-world-generator-reference`. It contains Python wheel/source distributions, JSON schemas, and `fantasy-world-assets.json`. Pull requests build the same payload and verify that it is reproducible before merge.

Validation runs as four parallel jobs (`checks`, `sim-tests`, `repo-tests`, `artifacts`) selected with `python tools/validate_repo.py --stage <name>`; every stage re-runs the cheap structural and provenance checks first so a partial run still fails fast. The `artifacts` stage proves both the asset list and a generated world are byte-reproducible across two separate runs. World documents are therefore exported compact, without wall-clock `timing_ms` and without the browser lab's `build_stages` snapshots; `fantasy-world generate --include-build-stages`, `--include-timings` and `--pretty` restore each of those when a human or the lab needs them.

Showcase bundles embed a whole world per page and are committed to the portfolio repository on every `main` merge. `tools/export_showcase.py` warns above GitHub's 50 MB advisory file size and refuses to publish above the 100 MB hard limit, because that history is permanent and GitHub Pages caps a site at 1 GB.

The reference payload also contains `contracts/capabilities.json`, emitted by `fantasy-world capabilities`. This versioned descriptor distinguishes supported Python/JSON contracts from unavailable native/editor/cooked capabilities and includes the coordinate/unit conventions. Its canonical source is packaged in the wheel; see [capability negotiation and coordinate fixtures](../Contracts/capabilities-and-coordinates.md).

Portable conformance inputs ship under `contracts/fixtures/`, including the [kernel-v1](../Contracts/kernel-v1.md) numeric, envelope and bounded-counter examples. The root `LICENSE` records private owner-controlled distribution; it does not authorize redistribution of third-party or Epic material. No immutable engine-qualified runtime release is produced by this reference workflow.

The asset list is a capability catalogue, not a generated-world inventory. Its normalized `assets` array is the union of:

- every terrain/biome surface the simulator can emit, including every natural-core × magic-school combination (104 recipe 3 variants);
- the city-ruins marker, whose generated instance retains its source culture and destruction cause;
- every real or fantasy creature profile eligible for a habitat anchor;
- every building asset choice reachable through any settlement building pack;
- every inherited environment production item, including materials, plants, trees, fungi, water, effects, structures, props, people, animation, and audio.

Entries may be planned rather than runtime-ready. `status`, `source`, selectors, and metadata preserve that distinction. A downstream importer must handle missing/non-ready content explicitly and must not interpret catalogue membership as proof that an Unreal asset exists.

Asset-list schema 2 is scoped to recipe 3, includes 13 natural surfaces and all 104 mutations, and excludes retired phenotype surfaces. Natural IDs and exact variant IDs form an OR selector; missing biome selectors are unrestricted, empty selectors match nothing. The compiler sorts normalized identities, rejects collisions, and emits a SHA-256 content digest. Generated timestamps are omitted so the output is byte-reproducible for the same source revision. CI records the merge commit in workflow metadata rather than changing catalogue bytes.

The workflow uploads mutable-retention build evidence to GitHub Actions; it does not publish an immutable Unreal package, publish to PyPI, or create a GitHub Release. It must never be labeled runtime- or cooked-validated. ML-03 records Unreal 5.8.2 as the requested engine target. [ML-03e](../board/retired/ML-03e.md) requires a local packaged Win64 generate → materialize run and an exact package digest before an asset-production handoff; GitHub-hosted cook automation may follow that digest. Python lab HTTP is not an Unreal publication path. Placeholder Unreal bindings use the exhaustive asset-list registry, not one sampled world.

## Portfolio samples on GitHub Pages

After each push/merge to this repository's `main`, the export workflow validates the repository,
regenerates three recipe-3, 65-grid worlds (seeds 42, 73, 108), and pushes only the frozen
published directory `public/mathlab/` to
[davgor.github.io](https://github.com/davgor/davgor.github.io). That path is the existing GitHub Pages
URL, not the product name; moving it would break the live showcase. That commit triggers the portfolio's
normal Pages deployment, including browser tests. No cron or cross-repository personal token is used.
Pull requests build and test the same samples but cannot publish. Manual workflow dispatch can retry
publication. No-change exports do not create empty commits. The showcase is the FantasyWorldGenerator
section at [/mathlab/](https://davgor.github.io/mathlab/) and links back here.

`tools/export_showcase.py` owns the sample recipes and uses `tools/fantasy-world-generator-showcase.html` for the selector.
Publication requires a clean source checkout. `--allow-dirty` is an explicit local-verification mode: its manifest records `source_dirty: true`, `publication_ready: false`, and the pages say “Uncommitted local preview.” The normal publication command still rejects uncommitted source. Run `python tools/export_showcase.py` to build `Artifacts/showcase`.
Manifest format 3 records the exact generator commit, source-file hashes, recipes/overrides and HTML
hashes. Wall-clock measurements are omitted as empty timing maps in these presentation exports for
reproducibility on the same Python runtime. Recipe 3 samples use the current biome contract and must be regenerated from earlier samples. Generated snapshots are committed to the portfolio and
included in its Pages artifact, so its code and live site can be traced to the source revision.

Pages cannot run Python. Inspection, layers and JSON export work from saved data; generation and local
patch and age-advancement controls are hidden. A failed generator build never updates the portfolio. A failed Pages build
leaves the previous deployment live. This is not an Unreal runtime or packaged-game integration.

### Publishing credential and recovery

`PORTFOLIO_DEPLOY_KEY` is an Actions secret holding a dedicated SSH key with write access only to
`davgor/davgor.github.io`. Its public key is registered as a write-enabled deploy key on that repository.
The workflow stages only the generated `public/mathlab` directory (frozen published path) and uses a normal fast-forward push;
concurrent portfolio edits cause failure rather than being overwritten. Re-run the source workflow to
retry against the latest portfolio commit. Push runs are serialized without cancellation so older
sample runs cannot overtake newer ones. Manual retries check that their source revision is still main.

To revoke publishing, remove that portfolio deploy key and source repository secret. To rotate it,
register a replacement dedicated key and replace the secret. Missing credentials fail publication with
an actionable error; validation and artifact builds still run. The private key never enters an artifact.

## Civilization references

Generation algorithm 9 uses standalone civilization entities. Building references in the exhaustive asset list include sorted `civilization_ids`, intersecting pack and option eligibility. Existing asset identities and production jobs remain shared candidates; no culture-specific art is implied. See [decision 016](decisions/016-standalone-civilizations.md).

## Final-world city plans

The [city planner](city-planner.md) adds versioned measured plots and worker housing after simulation. The exhaustive asset list includes 82 additional schematic potential identities (80 measured services and two housing types); these are not production art. Terrain recipe and algorithm remain unchanged.

Algorithm 16 suspends sky islands. The Shattered Coast sample retains ocean archipelagos and coastal communities; its retired sky overrides are removed.

## Local plugin source archive

`tools/package_plugin.py` creates a deterministic content-addressed ZIP under `Artifacts/unreal/` containing the `Unreal/FantasyWorldGenerator/` source tree, the engine-independent `Core/` sources vendored into the module so UnrealBuildTool compiles world genesis into it, the asset-ID registry table under `Data/`, the private license inside the copied plugin folder, and a manifest with per-file hashes. Plugin code is source-only: assets, build products, `.uasset`/`.umap` files, Python and `/Game` content references are rejected rather than packaged; engine object paths live in the registry table, which a consumer re-points at its own art. Its manifest records `genesis: native-core`, engine 5.8 / Win64, `native_generate: available`, `core_vendored: true`, the registry row count and asset-list digest, `unreal_qualified: false` and `unreal_cooked_runtime: false`. `--install <project>` copies the same bytes into a consumer project. A reproducible archive is an integrity identifier, not an engine-qualified release: that needs the cooked Win64 digest recorded by `tools/cook_consumer.py`. The existing reference workflow does not build or upload it.

## Local native source proof

`tools/package_native.py` creates a deterministic content-addressed source ZIP under `Artifacts/native/`. It includes the bounded C++ core, wire/numeric fixtures, contract schema, private license and an isolated headless consumer script. Its manifest declares `unqualified-source-only`; hashes do not make it an engine-qualified release. `tools/qualify_native.py` runs from an extracted bundle and records source integrity, actual compiler/platform and fixture results, explicitly with `unreal_qualified: false`. See [the native workflow](../Core/README.md). No native archive is uploaded or published by the existing reference workflow.
