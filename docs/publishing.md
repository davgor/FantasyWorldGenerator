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
