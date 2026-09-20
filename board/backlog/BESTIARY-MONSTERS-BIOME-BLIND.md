# BESTIARY-MONSTERS-BIOME-BLIND - biome identity does not steer a single monster

## Observed behavior

`biome_weight` (`Sim/icarus_sim/terrain_nests.py`) reads the species' own `biome_weights`,
falls back to its role's table, and returns `1.` when it finds neither.

**All 369 monsters have neither.** Not one carries a `role` (the field is `None` for every
monster - `roles()` is validated only for `class == 'animal'`), and not one carries its own
`biome_weights`. Running the real function:

```
every monster, every one of the 13 biomes -> exactly 1.0
```

A related fact from the same measurement: **0 of 680 profiles** carry their own
`biome_weights`. The documented per-species override exists and is entirely unused, so habitat
preference is a 21-way role choice for animals and nothing at all for monsters.

## Why it matters

Monsters are not undifferentiated - `suitability()` scores them on `weights` and gates them on
`requires` over habitat and ley fields - but **biome identity contributes nothing**. A creature
is no more likely to be found in a rainforest than on a glacier for any reason having to do
with the biome itself.

That interacts badly with how thin the terrain steering already is. Of the 369, only 42 carry
any relief-derived weight at all; the hard gates are overwhelmingly magical (`ley_umbral` 75,
`ley_weave` 71, `ley_primordial` 70, against `mountain` 11, `volcanic` 6, `depth` 8). So monster
placement is very largely a ley-field story, and the two ways it could have become
place-specific - terrain and biome - are one thin and one absent.

**These are two independent gaps, not one.** If monsters are ever meant to feel biome-specific,
both have to close; closing either alone will not produce it.

The clearest consequence today is [BESTIARY-LAND-ICE-NO-ANIMALS](BESTIARY-LAND-ICE-NO-ANIMALS.md):
because biome `17` is in no role table, animals score `0.` there while monsters score `1.`, so
the ice sheet is pure monster territory. That is the accidental monster default and the animal
exclusion meeting in one place. Related in shape:
[CONTENT-ENCOUNTERS-ARE-FISH](CONTENT-ENCOUNTERS-ARE-FISH.md), where what the player meets is
decided by where the world happens to have surface rather than by authored intent.

## Current state

Unfixed and, unlike the land-ice card, **not obviously a defect**. Terrain-and-ley gating may be
the intended design for monsters - a creature bound to charged ground rather than to a climate
is a defensible fantasy premise, and it is how the hidden schools already work.

What is not defensible is that the behaviour arises from a **fallback** rather than a decision.
`1.` is what the code returns when it finds no table, so "monsters ignore biome" is currently
indistinguishable from "nobody has authored monster biome preferences yet". No reader can tell
which, and nothing records an intent.

## Proposed fix

A ruling first, then at most one of:

- **Affirm it.** Document at `biome_weight` that monsters are deliberately biome-agnostic and
  steered by `weights`/`requires` alone. Costs nothing, changes no world, and removes the
  ambiguity. Consider having the catalogue loader assert the absence, so a monster that later
  acquires a stray `biome_weights` is caught rather than silently honoured.
- **Author preferences.** Give monster families biome tables the way animals have roles. This is
  seed-changing and needs its `Core/` port in the same change; sequence it behind
  [PRODUCT-WORLD-DISPOSABILITY-DECISION](PRODUCT-WORLD-DISPOSABILITY-DECISION.md).

Do not do both, and do not close this by adding tables to a handful of monsters - a partial pass
would make the fallback genuinely ambiguous rather than merely undocumented.

Separately, decide whether the unused per-species `biome_weights` override stays. It is
documented behaviour with zero call sites in the data; either author against it or remove the
branch.

## Not owned

Pre-existing. Surfaced by the biome review of 2026-09-20.
