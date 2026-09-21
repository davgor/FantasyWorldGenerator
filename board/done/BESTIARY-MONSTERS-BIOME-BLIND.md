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

The clearest consequence today is [BESTIARY-LAND-ICE-NO-ANIMALS](BESTIARY-LAND-ICE-NO-ANIMALS.md) - also now done:
because biome `17` is in no role table, animals score `0.` there while monsters score `1.`, so
the ice sheet is pure monster territory. That is the accidental monster default and the animal
exclusion meeting in one place. Related in shape:
[CONTENT-ENCOUNTERS-ARE-FISH](CONTENT-ENCOUNTERS-ARE-FISH.md), where what the player meets is
decided by where the world happens to have surface rather than by authored intent.

## Current state

**DONE, 2026-09-20.** The user ruled (0.4) that monsters should feel more biome-specific, and
(0.1) that worlds are disposable, which unblocked the seed change. The second option below was
taken, at the per-species seam rather than the family seam. All 369 monsters now carry their own
`biome_weights`, authored from an eleven-family template with explicit per-species overrides for
the twenty-four species that were winning a tier everywhere. Both loaders now **refuse** a
monster with no table, so the `1.` fallback is unreachable for the shipped catalogue rather than
merely unused.

The card's own closing question - *"decide whether the unused per-species `biome_weights`
override stays"* - is answered: it stays, and it is now the mechanism for the whole monster
half. Animals keep resolving through their feeding role. The two halves deliberately use
different mechanisms, because animals are role-coherent in a way monsters are not.

Originally unfixed and, unlike the land-ice card, **not obviously a defect**. Terrain-and-ley gating may be
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

## Why per-species and not per-family

The family axis is clean - eleven families, no monster without one - and it was the obvious
seam. It is also nearly inert, for a reason worth writing down: **a family multiplier cancels
within its family.** Thirteen of the eighteen species that currently top a (biome, tier) draw
slot are the same family, `fantastic`, and most of them carry a single habitat weight and no ley
gate, so they qualify almost everywhere and win on occurrence alone. Multiplying all fifty-eight
`fantastic` monsters by the same number reorders none of them. The measured difference was a
family table changing the favourite in two of forty land slots against ten of forty for
per-species overrides.

So the family table is the template, and the twenty-four slot-owners carry hand-written deltas
on top of it. The expanded tables are what ships, not the template: nothing resolves through a
fallback at runtime.

## The trap this had to avoid, and the rule that avoids it

`biome_weight` returns **0.0 for an absent key**. The moment monsters get any table at all,
every biome a monster's table fails to name becomes forbidden ground for it - so a naive,
hand-sized table of five or six plausible biomes per family does not make monsters
biome-specific, it deletes them. Measured beforehand: such a table removes about a quarter of
the placeable catalogue on the small reference world and only about a twentieth on a large one,
so a table validated on a big world silently empties the world every conformance run uses.
Omitting ocean alone would delete every aquatic territory, which is three quarters of all nests.

The rule is therefore raster-independent and asserted in a test: **every monster table names
every live biome.** A weight may be small; it may not be missing. The floor across the whole
catalogue is 0.15.

## Measured, before and after

Seed 42, phase 13, three generations in one process so nothing else in the tree could move
underneath the comparison. `A` is the old catalogue, `B` the new tables, `C` the new tables plus
the danger ramp that landed with them.

```
size 33   monster sites       A 885   B 861   C 869      (-1.8%, no collapse)
          distinct species    A 134   B 119   C 110
          mean authored preference of a placed monster for the biome it is on,
          judged for all three by the same new tables:
                              A 0.544 B 0.591 C 0.595     (+9.4%)
size 17   monster sites       A 237   B 220   C 223       (-5.9%)
```

The count does not collapse, and that is structural rather than lucky: the tier budget is
`tier_density * ground / tier_room`, and `tier_room` sums the same weights, so a biome table
redistributes a tier over the ground and cannot change how many of that tier a world holds. The
only way to lose monsters is to empty a whole `(tier, medium)` bucket, which naming every live
biome makes impossible.

The honest cost is the middle row: distinct species per world falls from 134 to 110. That is the
change working - a specialist now beats a generalist on its own ground, so fewer species win
more slots - but it is a real narrowing of the variety a single world shows, and it is the
number to watch if the tables are ever sharpened further.

What did **not** move much is the cast of the ice sheet, and the reason is worth recording: the
temperature range on a profile was already doing most of the biome's work. Land ice held frost
owls, frost sprites and glacier dragons before this change too. The tables removed the
siege tortoises and most of the basilisks and brought the woolly mammoths in.

## Not owned

Pre-existing. Surfaced by the biome review of 2026-09-20. Executed 2026-09-20 under user rulings
0.1 and 0.4.
