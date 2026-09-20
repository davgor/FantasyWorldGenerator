# CONTENT-AGE-SUFFIX-IN-NAMES — a generation-pass ordinal is player-facing text

Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 4).

## Observed behavior

Seed 42, size 17, `generator_version` 16. Heritage's morphemic namer has landed and the names are
good: `Durlbral`, `Froskor`, `Nordbrig`, `Wenbrig`, `Halbrig` for cities, `Frosnord`,
`Taelaeril`, `Thaltaur` for ruins, `Torang`, `Gundsirn`, `Mokhgund` for people. Three hours
earlier the same nine cities were `Cedar City` through `Ivy City`.

The disambiguator did not move with it. **Four of nine live settlements and four of fourteen
ruins carry a parenthetical generation age**: `Bargdum (Age 1)`, `Graflin (Age 2)`,
`Guntmek (Age 2)`, `Pikdum (Age 2)`, `Grafwin (Age 1)`, `Gulddum (Age 1)`, `Torsirl (Age 1)`,
`Ongbod (Age 1)`.

It then propagates into every derived string. **18 of 48 `key_locations` names carry it**,
including mid-phrase:

- `the fourth stone on the Gulddum (Age 1) road`
- `the bright hollow under Ongbod (Age 1)`
- `the march fort at Grafwin (Age 1)`
- `the aqueduct at Ongbod (Age 1)`

## Why it matters

"Age 1" is a fact about how the world was generated, not a fact about the world. A settlement
founded in the second age is just a settlement; the player has no access to the generation pass
and no way to read the parenthesis as anything but a bug.

It is also load-bearing in the wrong place. The suffix exists to disambiguate — before the
heritage swap the world held three live cities all named `Ivy City` — so removing the string
without replacing the disambiguation reintroduces collisions. On this world heritage's namer
already produces nine distinct stems with no collisions, which suggests the suffix is now
redundant rather than load-bearing, but that has been checked on one seed only.

`KEY-LOCATIONS` is a naming consumer by design (`docs/key-locations.md`; dossier §12), so it
inherits whatever settlements hand it. Fixing it at the settlement is the only fix that reaches
the derived names.

## Proposed mechanism

1. **Measure first.** Across a spread of seeds and sizes, count settlement-name collisions with
   the suffix removed. Heritage draws from each culture's own roots, so the collision rate is a
   property of the lexicon, not of this seed.
2. **If collisions are rare**, drop the suffix and let heritage re-draw on the rare clash — a
   second draw from the same genome is still a real name.
3. **If collisions are common**, disambiguate the way a world would: an epithet, a founder, a
   river, a modifier from the same lexicon. Heritage already glosses morphemes
   (`Bargdorn = wood-hold`), so a distinguishing morpheme is available.
4. Either way, keep the age on the record as a field. `settlements.sites[].founded_age` already
   exists; a consumer that wants to show it can.

## Dependencies and unresolved decisions

- Whether any consumer keys on the name string. Nothing should — uids are everywhere and every
  join in this document resolves through them — but it has not been audited.
- Heritage owns naming (`Sim/heritage/naming.py::settlement_name`). This card is an instruction
  to that package, not to `terrain_civilizations` or `key_locations`.
- Realm names are heritage's Phase B and are already tracked; this is the settlement surface.

## Acceptance and evidence

- No emitted string in a reference world contains a generation-pass ordinal.
- A behavioral test asserts that, over a spread of seeds, no settlement or derived name matches
  `(Age \d+)`.
- Settlement names remain distinct within a world, asserted by the same test.

## Adversarial review and limitations

One seed. The claim that heritage's names are distinct enough to drop the suffix rests on nine
settlements on one world and is the part of this card that most needs the measurement in step 1
before anything is deleted. The finding that the suffix reaches player-facing derived text does
not depend on it.
