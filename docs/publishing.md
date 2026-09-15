# Publishing and asset-list policy

Every push to `main` produces one export-only workflow artifact named `fantasy-world-generator-reference`. It contains Python wheel/source distributions, JSON schemas, and `fantasy-world-assets.json`. Pull requests build the same payload and verify that it is reproducible before merge.

The asset list is a capability catalogue, not a generated-world inventory. Its normalized `assets` array is the union of:

- every terrain/biome surface the simulator can emit, including every natural-core × magic-school combination (104 recipe 2 variants);
- the city-ruins marker, whose generated instance retains its source culture and destruction cause;
- every real or fantasy creature profile eligible for a habitat anchor;
- every building asset choice reachable through any settlement building pack;
- every inherited environment production item, including materials, plants, trees, fungi, water, effects, structures, props, people, animation, and audio.

Entries may be planned rather than runtime-ready. `status`, `source`, selectors, and metadata preserve that distinction. A downstream importer must handle missing/non-ready content explicitly and must not interpret catalogue membership as proof that an Unreal asset exists.

The compiler sorts normalized identities, rejects collisions, and emits a SHA-256 content digest. Generated timestamps are omitted so the output is byte-reproducible for the same source revision. CI records the merge commit in workflow metadata rather than changing catalogue bytes.

The workflow uploads mutable-retention build evidence to GitHub Actions; it does not publish an immutable Unreal package, publish to PyPI, or create a GitHub Release. It must never be labeled runtime- or cooked-validated. ML-03 will select the Unreal version, toolchain, consumer, immutable artifact channel, and compatibility manifest before runtime publication begins.

## Portfolio samples on GitHub Pages

After each push/merge to this repository's `main`, the export workflow validates the repository,
regenerates three recipe-2, 65-grid worlds (seeds 42, 73, 108), and pushes only `public/mathlab/` to
[davgor.github.io](https://github.com/davgor/davgor.github.io). That commit triggers the portfolio's
normal Pages deployment, including browser tests. No cron or cross-repository personal token is used.
Pull requests build and test the same samples but cannot publish. Manual workflow dispatch can retry
publication. No-change exports do not create empty commits. The showcase replaces the old MathLab
section at [/mathlab/](https://davgor.github.io/mathlab/) and links back here.

`tools/export_showcase.py` owns the sample recipes and uses `tools/mathlab-showcase.html` for the selector.
It requires a clean source checkout. Run `python tools/export_showcase.py` to build `Artifacts/showcase`.
Manifest format 2 records the exact generator commit, source-file hashes, recipes/overrides and HTML
hashes. Wall-clock measurements are omitted as empty timing maps in these presentation exports for
reproducibility on the same Python runtime. Simulation arrays, seeds and interchange versions remain
unchanged; normal lab exports are unaffected. Generated snapshots are committed to the portfolio and
included in its Pages artifact, so its code and live site can be traced to the source revision.

Pages cannot run Python. Inspection, layers and JSON export work from saved data; generation and local
patch and age-advancement controls are hidden. A failed generator build never updates the portfolio. A failed Pages build
leaves the previous deployment live. This is not an Unreal runtime or packaged-game integration.

### Publishing credential and recovery

`PORTFOLIO_DEPLOY_KEY` is an Actions secret holding a dedicated SSH key with write access only to
`davgor/davgor.github.io`. Its public key is registered as a write-enabled deploy key on that repository.
The workflow stages only the generated `public/mathlab` directory and uses a normal fast-forward push;
concurrent portfolio edits cause failure rather than being overwritten. Re-run the source workflow to
retry against the latest portfolio commit. Push runs are serialized without cancellation so older
sample runs cannot overtake newer ones. Manual retries check that their source revision is still main.

To revoke publishing, remove that portfolio deploy key and source repository secret. To rotate it,
register a replacement dedicated key and replace the secret. Missing credentials fail publication with
an actionable error; validation and artifact builds still run. The private key never enters an artifact.
