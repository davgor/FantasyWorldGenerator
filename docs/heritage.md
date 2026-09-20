# Heritage: key traits, culture and language

`civilizations.json` answers where a people can live. The 37 numeric fields listed in
`terrain_profiles.FIELDS` cover climate comfort, slope limits, water reach, food and college
siting, and every one of them is read by placement code.

Heritage answers what a people is *like*. It is a separate package, `Sim/heritage`, holding
three layers: seventeen categorical **key traits** per race, a **culture** derived from them,
and a **language genome** derived from culture and physiology.

## The chain

```
traits.races[parent_race]                     authored, complete, every axis present
  + traits.peoples[civilization]              authored, sparse delta
  -> derive_culture(traits)                   pure
  + overrides.culture[civilization]           authored, sparse
  -> derive_genome(culture, traits, lexicon)  pure
  + overrides.genome[civilization]            authored, sparse
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
4. Hand-tune in `policies/overrides.json` only where the derivation is wrong.
5. Increment the `revision` of every file changed.
6. Run `python -m unittest discover -s Sim/tests` with `PYTHONPATH=Sim`, then
   `python tools/export_catalogues.py` and the repository validator.

Each policy file carries its own revision, and `heritage_identity()` hashes the *resolved*
peoples rather than the source bytes — so a derivation edit that changes no output invalidates
nothing, while a one-character override that does change an output is caught.

## Known limits

- Name-space per tongue is a few hundred settlement names. Collisions resolve by bounded
  redraw, but more roots is the real fix, and the elven lexicon is the thinnest.
- Sibling tongues whose sound changes miss a given root can still coin the same personal name.
  Their root pools differ, so distributions diverge, but identical draws are possible.
- `forbidden_forms` guards against roots colliding into loaded English words. It is a substring
  check on the compound, because that is where the accident happens.
- Four dwarven branches share one soma, so their inventories are close and distinctness rests
  on the sound changes. `hill_dwarf` inherits uvulars its pastoral description does not suggest;
  its rules shift them away, but the inventory still lists them.

## Terminology

"Culture" already means something else in this repository. `terrain_humans.culture_groups` is a
road-connectivity grouping of cities with seed-local ids, and its own docstring says those ids
are not inferred ethnicities. Heritage's `culture` is per-civilization ethnography. They are
different objects sharing a word; heritage is addressed strictly by `civilization_id`.
