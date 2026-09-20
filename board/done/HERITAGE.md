# Heritage: race key traits, derived culture, derived language genome

Owner: local. State: complete for Phases A, B and D. No delegates.

Phase C (trait-driven geometry) was **not** built and is a reviewed open question with the
user — see `board/backlog/HERITAGE-GEOMETRY.md`. The native mirrors this work will eventually
need are queued in `board/backlog/HERITAGE-NATIVE-MIRRORS.md` and belong to the port phase.

## Delivered

- **`Sim/heritage`, a leaf package** holding three layers: seventeen categorical key traits per
  race, a culture derived from them, and a language genome derived from culture and soma.
  Derive-plus-override throughout — traits are authored, the other two layers are computed and
  then patched by sparse override files, so adding a people yields a plausible culture and
  tongue for free while anything can still be hand-tuned. Six soma axes gate the phoneme
  inventory physically; three register axes drive prosody and script; eight social axes drive
  culture. The three archetypes carry empty deltas, so every other people reads as its diff.
- **Twelve languages in three families, related by ordered sound changes over a shared root
  set** — one small table per family rather than twelve hand-written lexicons. `khas` "stone"
  surfaces as `khas`/`qos`/`kas`/`has` across the four dwarven tongues. Place and personal
  names are morphemic and glossable: `Bargdorn` is *wood-hold*, `Guntmerk` is *deep-ice*.
- **`terrain_ruins.CULTURE_SCHOOL` absorbed** into the `magic_school` key trait, retiring a
  hand-written dict that had an unsynchronised twin in `Core/legacy.cpp`. All twelve values are
  reproduced exactly, so ruin legacies and the leylines they seed did not move.
- **Heritage published into the world document** under `civilizations`, which is already a
  history state key — so `terrain_history.STATE_KEYS` and the pinned `tools/terrain_lab.html`
  were never touched and the silent stage-scrubber hazard could not fire. Block version 2 → 3,
  with `world-output.schema.json` and the replay gate following.
- **Hero naming re-keyed from parent race to `civilization_id`.** Keyed on the parent race, a
  desert human and a cold human drew from one table, and tidekin, gnome, hill_dwarf and
  frosthold_dwarf silently received *human* names. All four now have their own. Realms gain a
  native `name` beside the English `english_name`.
- **Settlement naming replaced.** The 24-word English list indexed by founding order is gone.
  Names key on node and coordinates, run in node order so collision redraws are canonical, and
  carry a gloss. One provenance revision row on `terrain_settlements.py`.
- Resolved heritage exported to `Contracts/catalogues/native-catalogues-v1.json` as a top-level
  block, which an existing native binary ignores, so it shipped ahead of any C++ reading it.
- `docs/heritage.md`, `docs/decisions/021-heritage-chain.md`, `docs/README.md`.

## Acceptance evidence

- **131 tests green** across `Sim/tests/test_heritage.py` (37), `test_heritage_consumers.py`
  (17), `tests/test_heritage_registry_binding.py` (15), `test_terrain_ruins.py` (5) and the
  regenerated `test_hero_generator.py` (28) and `test_story_web.py` (29).
- **The trait and culture layers provably carry no numbers**, asserted across all twelve
  resolutions. This is the structural answer to `PLAN.md:63` — it is not possible to author a
  second `resource_weight` beside the real one.
- **`registry_identity()` is byte-identical with heritage present**, asserted directly. The
  package's existence invalidated nothing, which is why it is a package and not an eleventh
  entity section.
- **Ids and the eight known magic schools are locked to the registry in both directions**, the
  price of heritage being a leaf that cannot import them.
- **The `magic_school` axis reproduces the retired `CULTURE_SCHOOL` exactly**, pinned against
  the historical twelve values literally rather than against itself.
- **Settlement names do not move when an unrelated city is founded**, and **naming is
  independent of founding order** — the latter tested by naming the same world twice with the
  sequence reversed. Neither property was achievable with `names[k % 24]`.
- Sibling distinctness asserted, not eyeballed: no two of the twelve share a place-name series.
- `verify_provenance.py` green on all 79 files; `export_catalogues.py --check` green.
- The full `Sim/tests` suite was **not** run here — verification was consolidated centrally
  while the tree settled.

## Limitations and next action

- **Pre-existing worlds must be regenerated.** The Phase A guarantee that no saved world was
  invalidated covered the package *existing*; publishing it raised `civilizations` 2 → 3 and
  `terrain_history` gates replay on that version. Compounds with the SUPER-VILLAINS `history`
  2 → 3 landed the same night.
- **`Core/scene.cpp` still names cities from the 24-word list**, so the native parity test will
  report a city-name difference until the port phase runs. Sequenced, not accidental — but it
  must not be allowed to mask a real failure beside it in a long red run.
- **Name-space per tongue is a few hundred settlement names.** Collisions resolve by bounded
  redraw; more roots is the real fix, and the elven lexicon is the thinnest.
- Sibling tongues whose sound changes miss a given root can still coin the same personal name.
  Root pools differ, so distributions diverge, but identical draws are possible.
- `heritage.resolve` raises on an unknown or missing **parent race** while falling back for an
  unknown **civilization**. Deliberate, and now a published contract documented in
  `docs/heritage.md`, because a parent selects the language family and guessing one yields a
  name in the wrong language rather than an approximate one.
- Absorption items 3 and 4 — `alignment.json` `civilization_bias` and `pantheon.json`
  `affinities` — remain separate tickets.
- One cosmetic defect surfaced but not caused by this work: an epithet template fills
  `{school}` lowercase mid-phrase, giving forms like `Keeper of the fire Stone`. It belongs to
  the epithet tables in `policies/names.json`.

**Next action:** none here. Phase C awaits the user's decision on whether heritage should touch
geometry at all; my recorded reading is that it should not.
