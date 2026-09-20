# Super villains: villains schema 1

Every figure the generator otherwise produces is a point in the world — a person attached to a city, named after events that already happened. Kings, guild masters, Dreads and the player all feel the same size because structurally they are.

A super villain is a **field**: a reach in metres with falloff, like a ley network or a divine visitation. It causes wars and city fates in its own name rather than being named after them.

This is the continuation of [PLAN.md](../PLAN.md) §21, which shipped as a heading with no body. Reference: `Sim/icarus_sim/terrain_villains.py`; the option registry in `terrain_world.py`; the lottery hook in `terrain_history.city_fate`.

`villain_rise` defaults to `0.5` and a default world ends with super villains standing in it. Setting it to zero is still a real off switch rather than a quiet one: no `villains` block is written at all, so the option is invisible in the output rather than merely inert in it.

**The rate alone could never have delivered that, which is why there are two mechanisms.** A generation runs exactly two age transitions, and at seed 42 size 17 the most concentrated region reaches tier 1.198 only at `villain_rise` 1.0 — the declared maximum — so no value below 0.834536 seats anybody by accumulation alone. Turning the rate up far enough to seat one would make every intervening age lurch. So the rate stays the campaign ramp, and `terrain_villains.promote()` is the arrival: on the final age of a generation, and on the final age of an `advance_age_request`, the most concentrated regions take the seats the ceiling allows. A promoted villain enters at exactly `SUPER_TIER`, the bottom of the band, because one that has just crossed the line is a threat that is growing rather than one that has arrived. The pass is idempotent — a region already holding a standing villain is skipped and the ceiling counts who is already seated — so advancing an already-promoted world changes nothing.

How many stand is phase- and age-dependent, never a constant: it is `ceil(regions / villain_density)`, and a world carries 9 regions after two ages at phase 16 against 11 at phase 14. Read the count off `villains.outlook.ceiling`, not off a remembered number.

## Tier is reach, and it is continuous

"Super villain" is not a flag that flips. It is a band on a curve a region climbs:

```
reach_m = tier × 4 × settlement_spacing
```

Three things follow, and they are the whole design:

- **The ramp is the pacing.** One that has just crossed the band is a threat that is *growing*, not one that has arrived. The peace after a player kills one comes from the successor genuinely being weak, not from a cooldown holding anything back. No respite mechanic exists because none is needed.
- **The player chooses their price.** Intervene early and it is cheap; wait and it is not. The growth is exported, so this is a decision rather than a surprise.
- **Pretenders stall at the line.** When the number at or above the band equals the ceiling, nobody else may cross — they sit at `0.999`, waiting for the seat to empty. Succession, with no succession system.

## Turmoil is one budget with two uses

*Diffuse* turmoil makes minor villains, which `hero_generator` already does continuously from every ruin, war and schism. *Concentrated* turmoil raises tier.

A city's turmoil is read straight from `threat_assessments` v3, so nothing new measures it:

```
turmoil = clamp(regional_threat + 0.3 × war_risk + 0.3 × war_hunger)
```

The forecast counts as well as the scars, because a region about to fight is concentrating as surely as one that already has. A region's **concentration** is the mean across its cities — the mean is what separates "one bad city" from "a region coming apart" — and each age adds `villain_rise × concentration` to that region's tier.

## The anchor, and why it is not a culture

A region is a `humans.cultures` group, which is something the world decided rather than something this module invented. But **a culture's id is rebuilt every age** from whatever the roads join that age, so it cannot carry anything across one: keyed to a culture, tier accumulation silently resets and nothing can ever reach the band. That is not a hypothetical — it is what the first implementation did, and it produced 26 orphaned tier keys for nine regions.

So a region is anchored to the **nearest ley node**, whose ids persist and are only ever appended to. Where a world has no magic at all it falls back to the seat city's uid, which survivors also carry forward. The villain is keyed to that same anchor, never to a city: anything hung on a city dict that is not in the survivor key tuple is dropped silently at the next age transition.

## Rising, holding, falling

| | |
|---|---|
| **Rise** | tier reaches `1.0` and the ceiling has room |
| **Ceiling** | `ceil(regions / villain_density)`, at least one |
| **Hold** | tier stays at or above `villain_hold` (default `0.7`) |
| **Fall** | below `villain_hold`; the region keeps `0.35` of its tier |

The band to stay sits below the band to rise. That hysteresis is what makes a reign long once established and stops anything flickering across the line. When a villain falls, the region keeps a fraction of its tier rather than resetting: the concentration **releases** rather than vanishing, which is the successor squabble.

### What a fall leaves behind

Two records, because they answer two questions.

**The roster stays honest.** A fallen villain is kept in `villains.people` with `status: 'fallen'` and a `fell_age`, so `people` becomes the list of everyone who ever held a region rather than a list of who holds one now.

**The mark is the durable one.** A villain that actually did something to the world gets a record in `villains.fallen`, in the same shape a ruined city gets one in `ruins`: an id derived from its uid, `fell_age`, `born_age` and `reigned_ages`, the parts of its life worth carrying (`school`, `growth`, `held_nodes`, `claims`, `well`, `god`, its log) and a `left` block naming the ruins it caused, the claims it staked, the well it sank and the nodes it held. `tier` and `reach_m` are deliberately absent: both describe a grip it no longer has.

**"If it indeed left a mark" is a condition, not a formality.** A villain that reached the band, took no city, staked no claim and sank no well did not mark the world, and gets no record. What it leaves is what it always left — the decayed tier the region keeps, which is the successor squabble. Inventing a monument for it would make the record of the dead less useful, not more.

The mark carries **no `asset_id`**, unlike a ruin. A ruin is a thing standing on the ground and needs a marker in the exhaustive asset list. A fallen villain's holdings are already placed — its wells are ley nodes, its claims are claims — so an asset here would be an identity the catalogue has to carry with nothing standing at it.

`villains.fallen` is appended and never pruned, exactly as `ruins` is. There is no retention horizon and that is not a new policy: it is the one the world already runs for its dead cities. The world has a finite population, so its dead are a knowable set rather than an unbounded stream — which is the argument for recording them properly rather than the argument against.

That makes `people` a list of everyone who ever held a region, not a list of who holds one now. **Every reader that means "who stands right now" must say so** — `terrain_villains.standing()` is the predicate, and absent status reads as standing so older records still resolve. This is the same shape `heroes.people` uses for `legend` and `npcs.people` uses for `dead`: one list, a status field, and the reader filters.

The ground a villain took does **not** revert. Its claims stay on the map and keep steering key-location placement and the nomad cultist gate, because held ground outlives its holder. Its own seat position does not: the claim persists, the person does not stand there any more.

How *hard* a fallen villain's claims still press is a separate question from whether they persist, and it is deliberately a number — `influence` on the claim, `FALLEN_CLAIM_INFLUENCE` in the module — rather than a boolean. It decays: `0.6` at the fall and `0.6` of that again each further age, reported as exactly zero once it falls below `0.05`. The argument is the one `FRAGMENT_SHARE` already makes for tier — a region's grip fades when its holder goes, and a world that never decays it eventually places by who *ever* held power rather than by who holds it. The record is never pruned; only the pressure fades. Settled with the tick cadence, because only a span crossing many ages makes the failure visible: see [decision 024](decisions/024-fallen-claim-decay.md). `terrain_nomads`' cultist gate is the only reader of the field today.

## Growth decides how it is fought

The pressure that raised a villain decides how its reach expands, and therefore the counter-play:

| Growth | Raised by | Counter-play |
|---|---|---|
| `devouring` | war pressure | deny cities, fortify |
| `spreading` | nest pressure | containment |
| `hoarding` | ley pressure | contest the nodes |
| `usurping` | no dominant pressure | fragile early, and it makes enemies |

**The sim owns this field.** `hero_generator` runs at stage 16, after the sim, and never writes back — but reach grows *during* ages, which is sim-side. So the sim writes `growth`, and the hero generator reads it to pick the matching escalation of the archetype card a person already carries. One direction of dependency, no circularity, and the package boundary holds.

## Taking a city

A seated villain appends a cause to `city_fate`'s lottery, exactly as `divine_lottery` does — appended, never inserted, because the selector walk is order-sensitive. Weight falls off with distance and is spent at `1.5 × reach_m`; the villain never takes its own seat.

The ruin records `villain_uid`, `growth`, `tier`, `distance_m`, `reach_m` and `school`, and its legacy carries the school the villain **holds**, not the region's own. A villain holding nothing falls through to the region and then the culture, exactly as an unmagical cause does.

## The outlook

`villains.outlook` is the counterpart of `war_outlook`. That one tells "they are coming" from "we once fought"; this one tells a region that is about to produce something from one that is merely violent, and names who is stalled at the line. Per region: `concentration`, `tier`, `to_threshold`, `seated`, `stalled`, plus the world's `ceiling` and `standing`. It exists so an orchestrator can pace content instead of guessing.

## Limits

Export, not behaviour. A villain's reach and growth are recorded intent; nothing here plans, negotiates or moves. There is no native port: `Core/config.hpp` mirrors the three options with an honest comment saying the native age lottery does not draw them, so only zero is reproduced natively.
