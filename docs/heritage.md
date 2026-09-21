# Heritage: key traits, culture, language and appearance

`civilizations.json` answers where a people can live. The 37 numeric fields listed in
`terrain_profiles.FIELDS` cover climate comfort, slope limits, water reach, food and college
siting, and every one of them is read by placement code.

Heritage answers what a people is *like*. It is a separate package, `Sim/heritage`, holding
four layers: seventeen categorical **key traits** per race, a **culture** derived from them,
a **language genome** derived from culture and physiology, and an authored **appearance** —
the body, for concept art, sprites and models.

## The chain

```
traits.races[parent_race]                     authored, complete, every axis present
  + traits.peoples[civilization]              authored, sparse delta
  -> derive_culture(traits)                   pure
  + overrides.culture[civilization]           authored, sparse
  -> derive_genome(culture, traits, lexicon)  pure
  + overrides.genome[civilization]            authored, sparse

appearance.races[parent_race]                 authored, complete, every block present
  + appearance.peoples[civilization]          authored, sparse delta
```

Three parent races carry a complete base. Twelve civilizations carry deltas from it. **Every
subrace bears a unique culture**, so there are twelve cultures and twelve languages, grouped
into three families.

The base is the *unmarked member*: `human_heartland`, `elf` and `dwarf` have empty deltas, so
every other entry reads as its difference from its archetype.

Derivation is a pure function and overrides are a sparse patch on top. Adding a people yields a
plausible culture and language for free; anything the derivation gets wrong can be hand-tuned
without abandoning it. An override that restates the derived value is a load error, so the
override file stays a list of real decisions rather than a slow copy of the output.

## Two rules that keep this from becoming a second registry

**The trait and culture layers contain no numbers.** This is enforced at load, not by
convention. It makes it structurally impossible to author a second `resource_weight` beside the
real one, which is the failure `PLAN.md` warns about. Consumers that need a number from a
culture keep the number in their own policy file and map from the culture *enum*.

**Heritage owns no identifiers.** Every key is a `civilization_ids()` or `parent_races` key.
`tests/test_heritage_registry_binding.py` asserts set equality in both directions, so a people
added on one side without the other fails the repository suite.

Heritage is a leaf package: it never imports `icarus_sim`, the same contract `story_web`
states for itself. `resolve()` is therefore handed a parent race rather than looking one up,
and it carries no seed logic — callers pass their own deterministic draw. The cost of that
independence is two restated enums, the civilization ids and the eight known magic schools, and
the binding test is what pays it.

**Introducing this package did not invalidate a single saved world.** `registry_identity()` is
a sha256 over the whole resolved registry document and `terrain_history` refuses to advance a
world whose registry hash moved. Holding these tables outside `civilizations.json` keeps that
hash still, and a test asserts it.

That guarantee covers the package's *existence*, and it no longer covers the current tree.
Publishing heritage into the world document raised the `civilizations` block from version 2 to 3,
and `terrain_history` gates replay on that version, so **worlds generated before this change are
rejected on age advance and must be regenerated**. The registry hash has not moved; the version gate has. Read the guarantee as "adding these tables cost nothing", not as "nothing has
changed" - `docs/civilizations.md` already warns that a seed alone is insufficient after authored
rules change.

## The body

`appearance.json` is the fourth layer and the one exception to the rule above: it carries
numbers. It may, because a body has measurements and nothing else in the repository states
them. `civilizations.json` measures habitat and never anatomy, so a number here cannot become
a second copy of one the placement code reads — which is the only thing the no-numbers rule
was ever protecting.

It is authored rather than derived, in the same base-and-delta shape as the traits: a parent
race carries a complete body and each subrace extends it. Derivation would be dishonest here.
A skin range, an ear form and a way of dressing are new information, not consequences of the
seventeen axes, and a generator that invented them from `body_scale` would produce three
bodies wearing twelve names.

Eight blocks, ordered from what a modeller needs first to what a concept artist needs last:

| block | holds | what reads it |
| --- | --- | --- |
| `frame` | height and mass bands per sex, build, dimorphism | model scale, collision, the per-NPC draw |
| `proportion` | heads tall, shoulder, leg and hand ratios | rig proportions, sprite silhouette |
| `coloration` | skin, hair and eye: a weighted hex palette and a note on how it is distributed | material tint, concept palette |
| `features` | face shape, ear, eye, nose, brow, jaw, lips, teeth, skin, markings | head mesh, portrait art |
| `grooming` | scalp texture, facial hair, body hair, styles | hair cards, sprite variants |
| `life_stages` | onset year and height fraction for four stages, plus a span | child and elder sprite sets |
| `attire` | layering, materials, dye character, signature item, footwear | costume concepting |
| `art_direction` | the silhouette, what it reads as, and what to avoid | the prompt itself |

A band is `min`/`mean`/`max`/`sd`, so a caller can draw one NPC from the population it
describes, and a palette weight is a population frequency. **Both are population parameters.
The per-individual weighting the game engine applies sits on top of them and is not authored
here.**

### A handle and the English beside it

`broad_high_bridge` tells a concept artist nothing about a dwarf's nose. So the two blocks an
artist works from directly carry both halves, and carry them in one value:

```json
"nose": {
  "form": "broad_high_bridge",
  "note": "Big, and meant to be. Broad across the bridge and broad at the wings, starting
           high between the brows with no dip at all, so brow and nose form one continuous
           ridge straight down the centre of the face. ..."
},
"skin": {
  "note": "Narrower than the human range and pushed toward the warm reds. Ruddy ochre is
           commonest by a long way ...",
  "swatches": [{"name": "ruddy_ochre", "hex": "#c98f68", "weight": 0.34}, ...]
}
```

The `form` is the join key and the prompt fragment; the `note` is what a person or a model
actually reads. They are one value rather than two blocks on purpose — a prose block sitting
beside a token block is two registries of the same fact, and the day someone edits one of
them is the day they disagree. A delta replaces the pair together, so a subrace cannot
inherit a description that no longer matches its form.

Elsewhere the token rule still holds: `grooming`, `attire` and `frame` are handles, and
`art_direction.silhouette` and `.reads_as` are standalone prose. A `note` under `PROSE_MIN`
characters is a load error, which is what stops a token being pasted in as a description.

### What binds a body to its traits

Two envelopes, both in `policy.py` beside `phonemes.GATES` for the reason those are there —
they are physical constraints, not authoring taste:

- `BODY_SCALE_HEIGHT_M` gives each `body_scale` value a height envelope the authored band has
  to lie inside. The `compact` ceiling is 1.34 m and the `small` ceiling is 1.26 m, so **no
  people under the dwarf parent race can be authored taller than 4 ft 5 in** — 1.3462 m. That
  is a property of the loader rather than a promise in a comment.
- `LIFESPAN_TEMPO_YEARS` does the same for `life_stages.max_years` against `lifespan_tempo`.

Both are checked on the *resolved* body by `check_resolved_appearance`. A race base is
complete and is checked at load; a subrace delta cannot be judged until it has been merged
onto what it inherits, so it is checked inside `resolve`. One implementation and two call
sites: a second merge inside `policy.py` is exactly the drift a sparse layer invites.

Categorical values are held to a token rather than to a closed enum, with two exceptions —
`facial_hair` and `sexual_dimorphism` — where a wrong value produces the wrong art silently
instead of a missing field. Appearance vocabulary is art direction and grows with the world;
closing all of it would mean a code edit for every new nose.

### Where it ships

Appearance goes out through `Contracts/catalogues/native-catalogues-v1.json` and through
`heritage.resolve`, and **not** through the world document.
`terrain_civilizations.heritage_of` still publishes traits, culture, genome and provenance
only, so the `civilizations` block stays at version 3 and no saved world is rejected on age
advance. A body is identical in every world from every seed, no generation step reads one,
and paying a world-document version bump to copy static data into every save is the wrong
trade. A consumer holding a world joins to the catalogue on `civilization_id`.

The `heritage` hash inside that block does move, because `heritage_identity` hashes the
resolved peoples and a resolved people now carries a body. Nothing gates on that hash — only
`registry_identity` gates age advance — so it reports the change without rejecting anything.

## The seventeen axes

**Soma** — articulatory, drives the phoneme inventory:
`body_scale`, `vocal_tract`, `breath_capacity`, `hearing_band`, `lifespan_tempo`, `dentition`.

**Register** — habitat acoustics, drives prosody and script:
`speech_environment`, `carrying_register`, `writing_surface`.

**Social** — drives culture:
`kinship`, `authority`, `mobility`, `memory_mode`, `craft_focus`, `outsiders`, `magic_stance`,
`magic_school`.

`Sim/heritage/policy.py` holds the allowed values; an unknown one is a load error.
`craft_focus` is the only list-valued axis and takes exactly two distinct crafts.

Soma axes gate the phoneme inventory through `phonemes.GATES`. Blunt dentition removes the
interdentals; a narrow vocal tract removes the uvulars and adds palatals; a low-weighted
hearing band collapses the sibilant series. These are physical constraints, so they live in
code rather than in an authoring table, and additions accumulate while removals win.

`magic_school` absorbs what was `terrain_ruins.CULTURE_SCHOOL`, a hand-written dict mirrored
verbatim and unsynchronised in `Core/legacy.cpp`. The axis reproduces all twelve of its values
exactly, which is asserted in the binding test. Hidden schools are refused: nobody holds a
stance toward a school no world can raise.

## Language families

A family owns a root set. Each branch applies an ordered list of sound changes to it.

```
dwarven  stone = khas
  dwarf            (no changes)        khas
  frosthold_dwarf  kh->q, nd->nt, a->o qos
  gnome            kh->k, rn->rl, ...  kas
  hill_dwarf       kh->h, u->o, ...    has
```

Sibling tongues are cognate because they *are* cognate; distinctness comes from the rules, not
from twelve hand-written lexicons. Rules apply in order and may feed each other, and each rule
is a single left-to-right pass that treats a multi-letter phoneme as atomic — without that, a
rule `s -> sh` matches the `s` inside an existing `sh` and turns `mush` into `mushh`.

Settlement names are morphemic and glossable, assembled from roots by a weighted template:

```
Bargdorn   wood-hold     (dwarf)
Borgdorn   wood-hold     (frosthold_dwarf)
Halmar     wood-harbour  (human_maritime)
Lainduin   green-river   (elf)
```

Passing a `terrain_slot` lets a name echo the ground it stands on. The gloss is returned beside
the name and costs nothing to ignore, so a consumer naming several thousand NPC posts never
builds one.

Personal names are dithematic — two meaning-bearing elements, like Thor-bjorn — so they gloss
the same way places do: `Guntmerk` is *deep-ice*, `Thalnaur` is *deep-fire*. The element pairs
deliberately exclude `site`, which is what a settlement is built from, so a person and a town do
not read as the same kind of word. A branch's sound changes apply to coined names too; without
that, two siblings sharing a soma generate identical names.

The phonotactic path remains for a caller holding a genome but no lexicon. It draws syllable by
syllable under the tongue's real template, which is what makes malformed output like `Caelioaes`
unconstructible rather than merely unlikely.

### The stock: which of those names a people uses

`person_name` says what a tongue *can* build. It does not say what a people calls its children,
and for a long time nothing did — every reachable name was equally likely. A heartland genome
composes 88 of them, so each landed on about one person in ninety. At the scale a roster works
at, thirteen thousand people in a size-65 world, that reads wrong in both directions: no name is
common enough to be met twice, and none is rare enough to be worth remarking, so a rare name
cannot mark a foreigner, an old family or an affectation.

Real naming is far more concentrated. In the English poll tax returns of the late fourteenth
century one man in three was a John and the five commonest names covered about four fifths of
all men, with a long tail of forms borne by one person each. `name_stock` and `stock_name`
reproduce that shape:

```python
stock = heritage.name_stock(resolved, heritage.lexicon())   # seedless, build once per people
name, gloss = heritage.stock_name(stock, draw)              # two draws, whichever branch
```

| | drawn flat | on the stock | England, late 14thC |
|---|---|---|---|
| commonest name | 3.3% | 34.3% | 35% |
| top five | 31% | 76.6% | 79% |
| effective number of names | 49 | 5.8 | ~6 |
| forms borne by one person | none | a tail | a tail |

Three decisions inside it are worth knowing:

- **The stock is seedless.** Rank is a property of the culture, not of the world: `Eldsel` is a
  common heartland name in every world the way John was common in every English county. It is
  ordered by authored template weight, then length, then spelling, so it needs no seed — which
  this package could not supply anyway, since it carries no seed logic by design.
- **The head is held apart.** Ordering by length alone put the whole heartland head on one root
  — `Eldsel`, `Frosel`, `Nersel`, `Versel` — and the elves on `-naur` four times over, which is
  worse than the flat draw it replaces: four fifths of a people would share not just a few names
  but a few sounds. The five commonest names are filled greedily from rank order, skipping any
  that reuses a root already standing in the head. What is skipped falls to the body of the
  stock rather than out of it.
- **The tail is morphemic, not phonotactic.** A rare name is still two roots joined, because the
  syllable path coins `Wopagup` and `Yoroochaat` and a tail built from it would read as
  generator noise exactly where a reader is meant to look. What makes it rare is the *pairing*:
  the role pairs neither the personal nor the settlement templates spend. Excluding the
  settlement set is what keeps a rare person from reading as a town.

What this does not do is tell two people with the same name apart. At this concentration the
commonest heartland name lands on hundreds of people in one world, and distinguishing them is
the job of a byname — a patronymic, a trade, a home town — which nothing generates yet.

## What `resolve` will and will not guess

The two arguments are treated differently, deliberately:

- **An unknown civilization resolves to its parent base.** This is the "a new people arrives
  with a plausible culture and tongue already attached" property, and it is what lets a test
  inject a synthetic entity and drive the whole pipeline through it.
- **An unknown or missing parent race raises `ValueError`.** There is no default. A parent race
  selects the language *family*, so guessing one does not produce an approximate name, it
  produces a name in the wrong language — and the silent `or 'human'` fallback that used to do
  exactly that is the defect this layer was built to remove.

That asymmetry matters to callers that cannot always supply a parent. `Sim/npc_roster` is one:
its own contract says a guessed parent is a wrong tongue, so it leaves such people unnamed and
counts them rather than asking heritage to invent one. **A caller that cannot supply a parent
race should leave the name empty, not substitute a default.**

## Authoring

1. Add the civilization to `civilizations.json` first; heritage keys off its id.
2. Add a sparse delta under `peoples` in `policies/traits.json`. Only name axes that differ
   from the parent base; restating an inherited value is an error. An unlisted people resolves
   to its parent base, so this step is optional and the result is still complete.
3. Add a branch under the matching family in `policies/lexicon.json` with its sound changes and
   any coinages of its own.
4. Add a delta under `peoples` in `policies/appearance.json`. Every civilization needs an
   entry, even an empty one: unlike traits, an absent people is a load error, because a
   subrace silently wearing its archetype's body is a wrong answer nobody notices until the
   art comes back looking like its parent.
5. Hand-tune in `policies/overrides.json` only where the derivation is wrong.
6. Increment the `revision` of every file changed.
7. Run `python -m unittest discover -s Sim/tests` with `PYTHONPATH=Sim`, then
   `python tools/export_catalogues.py` and the repository validator. The export is not
   optional for an appearance edit: the catalogue is the channel the art pipeline reads, and
   `--check` runs inside the validator's `checks` stage.

Each policy file carries its own revision, and `heritage_identity()` hashes the *resolved*
peoples rather than the source bytes — so a derivation edit that changes no output invalidates
nothing, while a one-character override that does change an output is caught.

## Known limits

- Name-space per tongue is a few hundred settlement names. Collisions resolve by bounded
  redraw, but more roots is the real fix, and the elven lexicon is the thinnest.
- Sibling tongues whose sound changes miss a given root can still coin the same personal name.
  Their root pools differ, so distributions diverge, but identical draws are possible. **The
  stock makes this louder rather than quieter**: concentration puts the collision in the head
  where it is heard. `dwarf` and `gnome` share three of their five commonest names, and so do
  `human_heartland` and `human_rainforest`. Cognate peoples sharing common names is defensible
  — John was John either side of a border — but it is a consequence worth knowing before
  reading it as a bug, and more roots or more sound changes are the fix on either reading.
- `forbidden_forms` guards against roots colliding into loaded English words. It is a substring
  check on the compound, because that is where the accident happens.
- Four dwarven branches share one soma, so their inventories are close and distinctness rests
  on the sound changes. `hill_dwarf` inherits uvulars its pastoral description does not suggest;
  its rules shift them away, but the inventory still lists them.
- A `coloration` palette is four or five weighted swatches. That is a coarse stand-in for a
  real population's distribution and will read as banding if a consumer picks swatches
  without interpolating between them.
- `attire` is one costume per subrace, with no class, rank, season or trade variation. A city
  of them drawn straight from this table is a city in uniform; the intended fix is a
  per-NPC layer on the engine side, not more rows here.

## Terminology

"Culture" already means something else in this repository. `terrain_humans.culture_groups` is a
road-connectivity grouping of cities with seed-local ids, and its own docstring says those ids
are not inferred ethnicities. Heritage's `culture` is per-civilization ethnography. They are
different objects sharing a word; heritage is addressed strictly by `civilization_id`.
