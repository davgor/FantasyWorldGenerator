# CONTENT-AGE-SUFFIX-IN-NAMES — a generation-pass ordinal is player-facing text

> **Re-tested 2026-09-21 against the tree — CONFIRMED, claim reproduces.** **2,323 strings** carry `(Age N)`, including names such as `"Fenweg (Age 1)"`.
> Measured on `Fixtures/sample-world-v1.json` (seed 42, **size 33**, generator 16) unless the evidence
> names a file; the card's own figures are size 17 and are not superseded by these.
> [Reconciliation](../../docs/reviews/2026-09-21-board-tree-reconciliation.md).


Owner: none. State: **open — step 1 measured 2026-09-21, and it selects step 3, not step 2.
The implementation is blocked on one fenced line.** See
[Step 1, measured](#step-1-measured-2026-09-21) and [Blocked on](#blocked-on) below.
Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 4).

Sibling: [CONTENT-CITY-SUFFIX-DEAD-READERS](CONTENT-CITY-SUFFIX-DEAD-READERS.md) — the same
subject at the opposite end. This card is the disambiguator that is live and should not be;
that one is the retired `' City'` disambiguator that five places still read for.

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

## Step 1, measured (2026-09-21)

The measurement this card asks for in step 1, taken. **It selects step 3. The card's own
argument above — "heritage's namer already produces nine distinct stems, which suggests the
suffix is now redundant" — is wrong, and the limitation the card names at its foot is the thing
that was actually wrong.**

Counting `(Age N)` in the reference world, `Fixtures/sample-world-v1.json` (seed 42, size 33,
generator 16, recipe 3): **2,245 strings** carry it, spread over twelve top-level blocks —
`build_stages` 1135, `heroes` 799, `story_web` 81, `npcs` 69, `key_locations` 35, `debug_stats`
31, `settlements` 24, `threat_assessments` 24, `city_plans` 24, `world_economy` 9, `history` 7,
`ruins` 7. 24 of its 35 live settlements and 7 of its 38 ruins carry it. It reaches
`story_web` mid-phrase, exactly as the card says:
`Brenyaki Who Holds the fortress above Norddan (Age 2)`.

Now the part that decides the fix. Stripping the suffix and counting collisions:

| world | settlements | collisions among settlements | collisions once ruins are pooled in |
| --- | --- | --- | --- |
| seed 42, size 33 (the reference world) | 35 | none | `Korham` — one live city and one ruin |
| seed 42, size 17, phase 16 | 12 | **`Wenbrig` — two live settlements** | same |
| seed 7, size 17, phase 16 | 11 | none | `Nordsal` — one live city and one ruin |
| seed 1, size 17, phase 16 | 15 | none | `Nardum` — one live city and one ruin |
| seed 99, size 17, phase 16 | 15 | none | none |

**Four of the five worlds measured collide. One of them puts two live settlements under one
name the moment the suffix comes off.** That is the collision the suffix exists to prevent, and
it is not rare enough to answer with "let heritage re-draw on the rare clash" alone — a re-draw
has to be triggered by something that can see the clash, and nothing currently can.

One thing the glosses make plain, and it is not what the card assumed. Every collision measured
is a **homograph across two different tongues**, not a repeated draw within one: `Wenbrig` is
*deep-stone* in `human_large_island` and *wind-bridge* in `human_cold`; `Nardum` is *fire-hall*
in `gnome` and something a dwarven ruin has carried since age 0. The card reasons about "nine
distinct stems" as though the risk were one lexicon repeating itself. The real risk is twelve
lexicons built from a shared root set landing on the same surface form, and that does not get
rarer as the namer gets better.

Why nothing can. `terrain_settlements._settlement_names` resolves collisions against a `taken`
set built inside one call, over the nodes selected for the age being generated, walking them in
node order. Two things sit outside that set:

- **Ruins.** A settlement that died in an earlier age keeps its name in `ruins[]`, and nothing
  puts that name in `taken`. This is the `Korham`, `Nordsal` and `Nardum` case above: a live
  city drawing a name a dead one already holds. Seed 1 shows it plainly — the gnome city
  `surface-city-2-86-gnome` is founded in age 2 as `Nardum (Age 2)`, while the dwarven
  `surface-city-0-119-dwarf`, destroyed in age 1, has been `Nardum` since age 0.
- **Survivors, and this one is worse, because the redraw fires and is then undone.** A
  survivor's name is restored by `carry_survivor` (`CARRIED_SURVIVOR_KEYS` includes `'name'`)
  *after* naming has run. So if a city founded this age sits on a lower-numbered node than a
  survivor and draws the survivor's name, it is the **survivor** that sees `taken` and redraws
  — and the copy-back then overwrites that redraw with the historical name, putting both cities
  back under one name. The suffix on the newer city is all that has been hiding it.

  This is the `Wenbrig` case, and the two records say so exactly:

  | | uid | node | founded_age | gloss |
  | --- | --- | --- | --- | --- |
  | survivor | `surface-city-0-95-human_large_island` | 95 | 0 | deep-stone |
  | founded in age 2 | `surface-city-2-42-human_cold` | **42** | 2 | wind-bridge |

  Node 42 is named first, takes `Wenbrig`; node 95 finds it taken and redraws; the copy-back
  puts `Wenbrig` back on node 95. Note the glosses: these are two different words in two
  different tongues that happen to be spelled alike — a homograph, not a repeated name — which
  is a perfectly good thing for a world to contain and still leaves a player with two cities
  called `Wenbrig`. Whatever replaces the ordinal has to separate them.

Either way the suffix has been covering for a `taken` set that does not span ages, which is why
it is applied to every city founded after age 0 rather than only to the ones that clash.

Cited by symbol rather than by line: `terrain_settlements.py` was rewritten by another session
while this was being measured and every line number in it moved.

So the fix is two parts, not one:

1. `_settlement_names` takes the names already spoken for — the survivors' historical names and
   the ruins' — and seeds `taken` with them, so its existing bounded re-draw resolves a
   cross-age clash the same way it already resolves a within-age one. Seeding is not enough on
   its own: a survivor's node must be *held* at its historical name rather than redrawn, or the
   copy-back undoes the redraw and the clash comes straight back. The party that must move is
   the city founded this age. This is the card's step 3, done with the machinery step 2 assumed
   was already there.
2. `terrain_history.remember_cities` stops appending the ordinal:
   `if 'uid' not in city and age>0:city['name']+=f' (Age {age})'` (`terrain_history.py:265`)
   is the single line that emits it, and `city.setdefault('founded_age',age)` on the next line
   already keeps the age on the record as step 4 asks.

Both parts must land together. Part 1 alone changes nothing the card is about; part 2 alone
reintroduces the collisions.

## Blocked on

`Sim/icarus_sim/terrain_history.py` is fenced to another live session, and the one line that
emits the suffix is in it. `Sim/icarus_sim/terrain_settlements.py` is not fenced but is
provenance-pinned, so part 1 needs a revision row in `provenance/extraction-manifest.json`,
which the orchestrator serialises.

Landing this invalidates `Fixtures/sample-world-v1.json` — 2,245 strings in it move — so the
rebuild has to be sequenced with it.

## Scope note: this is settlements only

The argument that heritage's namer is distinct enough to carry a world without a disambiguator
holds for settlements and is **false for people**. Personal-name distribution changed on
2026-09-21 by design: the commonest heartland given name now lands on roughly 34% of a people
(was 3.3%), the top five on 77% (was 31%), effective diversity 49 → 5.8. A size-65 world puts
hundreds of identical person-name strings in one roster. People need a byname — patronymic,
trade or toponym — and nothing generates one. That is a separate problem and not this card's.

## Adversarial review and limitations

The step 1 measurement is five worlds: the committed size-33 reference world and four size-17
phase-16 worlds. Five is enough to refute "collisions do not happen" — four of them collide —
and it is a thin basis for a rate. All of them are recipe 3; sizes 65 and 129 were not measured
and cost roughly an order of magnitude more per world, and more settlements per world can only
raise the collision rate, not lower it.

Seeds 42, 1 and 99 were measured against the tree after a concurrent session's rewrite of
`terrain_settlements.py` and `city_planner.py`; the seed-7 figure was taken before it, and an
earlier attempt at seeds 1 and 99 aborted mid-rewrite on
`ImportError: cannot import name 'FOUNDED_BY'`. The seed-42 collision reproduces on both sides
of that rewrite.

The original limitation stands corrected rather than removed: the claim that heritage's names
are distinct enough was indeed the part of this card that most needed measuring, and it did not
survive it. The finding that the suffix reaches player-facing derived text does not depend on
it and is confirmed at 2,245 strings.

## Measured 2026-09-21 — the uniqueness guarantee cannot see the failure

Two hypotheses were raised for why live cities collide once `(Age N)` is stripped. One is
refuted and one is worse than stated.

**Refuted: `_settlement_names` is not called per age.** It has exactly one production call
site, `Sim/icarus_sim/terrain_settlements.py:925`. Every other call in the tree is in
`Sim/tests/test_heritage_consumers.py`. So the redraw's `taken` set is not scoped per call
in a way that lets a later age collide with an earlier one — there is no second call.

**The real gap: `test_names_within_one_world_are_unique` samples a band where the failure
cannot occur.** At `Sim/tests/test_heritage_consumers.py:66-72` it builds 40 nodes with
`peoples = ['dwarf'] * 40` — **one tongue**. It therefore tests that a single lexicon does
not repeat itself, and passes.

Every collision actually measured is a **homograph across two different tongues**:
`Wenbrig` is *deep-stone* in `human_large_island` and *wind-bridge* in `human_cold`;
`Nardum` is *fire-hall* for a gnome city and the name a dwarven ruin has carried since age 0.
Twelve lexicons built from a shared root set land on the same surface form. A one-people
fixture cannot produce that, so the test is structurally incapable of failing on the defect
the suffix is hiding — it is green, and it is green for a reason unrelated to the claim it
appears to make.

This also decides the card's central argument. It reasons that the suffix is droppable
because the namer now produces enough distinct names — i.e. that the risk is one lexicon
repeating and therefore shrinks as the namer improves. Cross-tongue homography **does not
shrink** with a better namer; it is a property of twelve lexicons sharing a root set. The
suffix is load-bearing, and the fix is uniqueness across tongues, ruins and survivors —
not a better draw.

**Before this card is worked, `test_names_within_one_world_are_unique` needs a mixed-people
fixture.** Written as it is, it will keep passing through the change and prove nothing.
