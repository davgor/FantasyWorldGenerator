# Beast movement: the creatures that do not hold ground v1

A finished world carries a `beast_movements` block and an `encounters` index. The nest
passes place every creature as if it lived somewhere, and most do. This covers the ones
that do not.

Reference: `Sim/icarus_sim/terrain_beast_movement.py`, `terrain_encounters.py`,
`terrain_nest_profiles.json` (the `movement` field), the
[beast schema](../Contracts/schemas/beast-movements.schema.json) and
[encounter schema](../Contracts/schemas/encounters.schema.json),
`Sim/tests/test_creature_movement.py`.

## Thesis

"Wanders" is not one behaviour. A herd following the grass, a swarm erupting out of ground
that stopped feeding it, a wolf pack shadowing a herd, and a corpse with nowhere to lie are
four different mechanisms that happen to share an outcome. Collapsing them into one flag
would make every moving thing move the same way, which is the failure this is built to
avoid.

So the creature catalogue declares a `movement` class per species. **The default is
`nester`**, so the 663 creatures that already worked keep working; 594 of the current 680
still hold ground.

| Class | What drives it | Route |
|---|---|---|
| `nester` | a den, a range, or a grave to hold | none — the existing `range_m` territory |
| `migratory` | the green wave: warm-season pasture high and open, cold-season ground low and sheltered | seasonal round through a calving camp |
| `irruptive` | marginal ground stops supporting them | one march toward the best forage in reach |
| `follower` | something else's movement | derived from a host's circuit |
| `drifter` | no grave to return to | a circuit between the ruins that made them |

## The undead rule

The split between `drifter` and `nester` among the undead is a rule, not a tag:

> **An undead with a grave nests at it. An undead without one wanders.**

Skeletons, tomb wardens, barrow wights, cairn wolves and ossuary spiders are raised from
burials and hold them. Zombies, wraiths, road shades and the wild hunt have no resting
place — violent ends, unburied dead, nothing to go back to — so they drift. This is why a
barrow wight was added to the catalogue in the same pass as five wandering dead: the
contrast belongs in the data, not only in this paragraph.

## Followers close the loop

A follower does not search for a route; it **derives** one from a host, which may be a
creature group or a nomad band. Predators shadow herds, scavengers trail caravans.

Host choice is biased by role rather than by distance alone. A plain nearest-host rule got
this wrong in one direction: herds outnumber bands roughly forty to one, so with distance
alone nothing ever followed a caravan. Scavengers now prefer people, hunters prefer herds,
and the bias shortens effective distance rather than overriding reach — a preferred host
wins from further away, but an unreachable one never gets through.

## Encounters

`encounters` answers one question: **what travelling thing is near here, at this time of
year, and what is it.** It indexes nomad bands and creature groups through the same shape,
with `by_month` and `by_node` so a consumer answers in a lookup rather than a scan over
every leg of every group.

It is an index, not a quest generator. No objectives, stakes, rewards or difficulty — those
belong to whatever eventually consumes it, and inventing them now would be guessing at a
contract that does not exist.

Occupancy is recorded at **camps**, where a group dwells, not along legs. A group in transit
is derivable from its leg node path and its speed; where it is camped is the thing you
cannot derive.

## Determinism

`child_seed(cfg.seed, 'beast-movement-v1', nomad_variation)`, on its own domain, so nothing
here perturbs an existing stream. Groups are built from an ordered site list and the
`beast_movement_share` option thins it deterministically — a share, not a cap, so the count
stays proportional to the ground rather than to whatever happened to be placed first.

Speeds are absolute metres per day by creature size, for the same reason nomad speeds are:
a gait belongs to the animal, not the world. Every reach is a multiple of settlement
spacing.

## Limitations

A group is one site rather than a modelled population. Nothing breeds, starves, is eaten, or
merges with another group, and a herd does not shrink when a follower attaches to it.

Followers pick the nearest eligible host once and never change host. Irruptions have no
trigger condition in time — a swarm that should only erupt in a bad year is present in every
year, because there are no years yet.

Circuits are static. A group whose route could not be built is reported as `stranded` with
its start camp rather than dropped; on a small world that can be a third of them, mostly
creatures whose seasonal or haunt targets were not reachable.

Wildlife is dense enough that routing every eligible site produces hundreds of groups on a
small world. `beast_movement_share` exists to thin that, and defaults to keeping all of
them.
