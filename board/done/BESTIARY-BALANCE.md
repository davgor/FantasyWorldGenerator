# BESTIARY-BALANCE — Tier review and a padded book of critters and monsters

Status: done, 2026-09-18. Follows the two-pass habitat work that gave every creature a
danger tier (profile document version 1 → 2).

## Requested behavior

Review the monster tiers now that tiers exist, balance the book, and pad it with
critters and monsters of every kind: the monster catalogue was dense at the top.

## What was found

A tier is a share of the world divided among its members (`tier_density` in
`Sim/icarus_sim/terrain_nests.py`), so the catalogue's own shape decides how often a
player meets the rare thing. The first tier pass derived tier from `size` with a
per-family offset, which left the book top-heavy:

| class | tier 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| monster, before | 21 | 24 | 56 | 46 | 45 |
| monster, after | 72 | 81 | 81 | 56 | 43 |
| animal, before | 114 | 35 | 29 | 11 | 0 |
| animal, after | 174 | 62 | 50 | 19 | 0 |

Sixteen of twenty-one draconic rows sat at tier five (every drake was a dragon), and
three families (holy, fey, fantastic) had no campaign threat at all.

## What changed

- **32 rows re-tiered** against the definitions in `docs/terrain-world-layers.md`
  (1 harmless, 2 can hurt you, 3 kills the careless, 4 kills the prepared, 5 a
  campaign threat): lantern dragonets 3→1; needle, burrow and reed drakes 3→2; pack
  and sailback drakes to 3; basilisk drakes, wyverns, lindworms and amphipteres 5→4;
  skeletons and zombies 3→2; revenants and vampires 3→4; liches 3→5; soot vermin 2→1;
  ash scavengers 3→2; contract devils 3→4; judgment titan 4→5; pilgrim tortoises 4→3;
  kraken, leviathan and abyssal krakens 4→5; reefback leviathans and islandback
  grazers 4→3; root titans, salt colossi, avalanche giants and river serpents 5→4;
  hags 2→3; Wild Hunt riders 3→4; wandering hollow hills 4→5.
- **141 monsters added**, weighted to tiers one to three, across all nine families:
  vermin, sprites, hounds, drakes, swarms and the like, plus water rows for every
  family so the per-medium sea budget divides. **116 real animals added**: the everyday
  creatures the roster lacked (rats, mice, voles, cats, feral and wild dogs, possums,
  skunks, weasels, mongooses, monkeys and apes, pandas and other bears, deer, wild
  goats and sheep, camels, kangaroos), and the thin roles (amphibians, venomous
  snakes, scavengers, shore animals, monitors and crocodiles) and megafauna
  (elephants, rhinoceroses, hippopotamus, water buffalo, gaur). Every monster family
  now spans all five tiers.
- `docs/catalogue/creatures.json` gained a name and description for each row; the
  coverage test requires the two files to name the same creatures.
- New behavioral test `test_the_book_is_a_pyramid_too`: both books widest at tier
  one, tiers one and two outnumbering four and five, every monster family spanning
  tiers one to five. It failed against the version-1 book (21 not greater than 45).
- Regenerated `Contracts/catalogues/native-catalogues-v1.json` (638 nest profiles)
  and `Contracts/catalogues/unreal-asset-registry-v1.json` (1441 bindings); the
  asset-list test now pins 638 creature identities. Provenance revision records
  added for the four extracted files touched.

## Evidence (seed 42, size 33, the nest suite's worlds)

| world | animals placed, tiers 1–5 | monsters placed, tiers 1–5 | species placed |
| --- | --- | --- | --- |
| recipe world, 40 km2 | 230: 176 / 43 / 9 / 2 / 0 | 26: 13 / 7 / 4 / 2 / 0 | 76 animals, 16 monsters |
| wide world, ×3 surface | 706: 535 / 121 / 35 / 15 / 0 | 94: 49 / 28 / 10 / 4 / 3 | 146 animals, 36 monsters |

The most-placed monster on the wide world holds 12 of 94 territories (bladefish); the
first draft of version 2 had one species holding 29 of 84, because it was the only
tier-one marine monster and inherited the whole tier-one sea. Campaign threats on the
wide world: abyssal krakens, forest dragons, thunderhead beasts.

Verification: `Sim/tests/test_terrain_nests.py` 14/14; `tests/test_asset_list.py`
7/7; `tests/test_native_world.py` 14/14, so the C++ core places all 638 profiles
anchor for anchor with the reference; `tools/export_catalogues.py --check`,
`tools/build_asset_registry.py --check` and `tools/verify_provenance.py` pass.

## Limitations and adversarial notes

- **Every seed's placement moves.** The tier budget is divided among whoever
  qualifies, so a world generated against version 1 does not replay against version
  2. The ML-03e packaged habitat counts predate this book.
- **The sea belongs to the fantastic family.** Every other family's water monster
  requires ley potency at or above 0.025, and the weighted score averages that potency
  with fishing productivity; ley is low at sea, so those rows rarely clear the 0.3
  suitability floor. The added non-ley water beasts divide the share; magical sea
  monsters in numbers need that gating revisited, which is authoring, not a rule change.
- **Baseline failures, not touched here.** `tools/validate_repo.py` stages `checks` and
  `artifacts` pass. `sim-tests` runs 272 tests with 11 failing and `repo-tests` runs
  103 with 1 failing, all from the in-flight uncommitted work rather than this book:
  nine raise `Retired rural report; regenerate for the derived fortress demand` on age
  advancement (castle, city and hamlet planner age tests, the biome contract replay,
  three age-API tests, the threat refresh, and the registry-change test that expected a
  different message); `test_pipeline_after_beasties_and_ages` expects threat report
  version 1 and finds 2; `test_generated_world_satisfies_the_published_world_schema`
  expects settlements version 14 and finds 15; and
  `test_ruins_remove_hamlets_and_create_nodes` counts 17 weave nodes where it expects
  22 with city fate patched, so the nest catalogue plays no part in it.
- Profiles remain artistic first-pass parameters. Descriptions are one line each and
  claim no behavior the generator implements.

## Handoff

Re-cook the ML-03e consumer when the next packaged evidence is due; the habitat counts
in that ticket are from the version-1 book. Consider a per-medium ley floor for water
monsters if the sea should carry undead, aberrant or primordial threats at scale.
