---
conformance: 1
record: encounter-index
tier: EXERCISED
summary: Indexes every travelling group by the node and month it can be met at, and says on each entry what kind of thing it is answering with - where it lives, whether it is animal, monster or people, and whether it flies.
modules:
  - Sim/icarus_sim/terrain_encounters.py
emits:
  - path: encounters
    schema: Contracts/schemas/encounters.schema.json
versions:
  - id: encounters
    assert: 2
proof:
  - path: Sim/tests/test_encounters.py
    establishes: that every entry carries the domain its species lives in, checked per entry against the catalogue rather than as a share; that a land query drops the water by a named set of uids without joining another block; that a shore species is walkable and a marine one is not; that animal, monster and people are all distinct on the entry; that a flyer is marked and nothing else is; that the occupancy and node indexes still resolve; and that limits states the threat histogram describes movers only
decisions: []
tickets:
  - board/done/CONTENT-ENCOUNTERS-ARE-FISH.md
---

# Conformance: encounter index

## What it produces

One entry per travelling group and one occupancy record per camp that group holds, with
`by_month` and `by_node` so "what is near here, and when" is a lookup rather than a scan
over every leg of every group. Nomad bands and travelling creatures go through the same
shape, so one consumer reads both.

Each entry says what it is, not only which species it is:

- `domain` — `land`, `ocean` or `lake`, on the word `key_locations` already uses for the
  same idea. A shore species is `land`, because `terrain_nests.suitability` refuses a shore
  medium every water cell and then asks for a coast, so a puffin colony is on the beach and
  a traveller walks to it.
- `class` — `animal`, `monster` or `people`, on the word `wildlife` and `beast_nests`
  already use. A nomad band is `people`.
- `airborne` — the species flies. Deliberately not a fourth domain: a roost is somewhere
  you can stand, and folding flight into `domain` would stop `domain == "land"` meaning
  reachable on foot.

On a reference world this splits 2,778 entries into 1,586 ocean, 1,184 land and 8 lake, so
a land query drops 57% of the index in one field test instead of a join back through
`beast_movements` to `beast_nests`.

## Entry points

`add_encounters(result, cfg)`, gated on `cfg.world_recipe` and `cfg.phase >= 16`. It runs
after `add_beast_movements` and after the nomad pass, because it indexes what they built.

## Inputs it reads

`nomads.groups` and `beast_movements.groups`, each group's `camps` with their arrive and
depart days, `DAYS_PER_YEAR` from `terrain_astrology`, and the creature catalogue through
`terrain_nests.profiles()` for the medium, class and `sky` flag of each species. It reads
no layer and no geometry: a camp already carries its node.

## Artifacts it writes

`result['encounters']`, validated by `Contracts/schemas/encounters.schema.json`, and
`result['timing_ms']['encounters']`.

## Where it runs

In process, inside generation, after the movement pass. The species lookup is built once
and cached.

## Versions asserted

| What | Value |
|---|---|
| `encounters` block and schema | <!-- conformance:version encounters=2 --> |

Version 2 added `domain`, `class` and `airborne`, and all three are required by the schema.
Additive in shape, but not additive in what the block can answer: under version 1 an entry
said only which species it was, so the question the block exists for — what is near here
that a party could walk to — could not be asked of the index at all. A consumer had to join
back through two blocks to drop the water, and on a world three quarters ocean that is most
of the index. `limits` also now states that static sites are not indexed, so the
`threat_tier` histogram describes travelling groups rather than the world's danger profile:
a world holding tier-five lairs produces, correctly, an index with no tier-five entry.

## Proven by

`Sim/tests/test_encounters.py`, against a hand-built block rather than a generated world.
That is the point of it. The claim is about a *split*, and a generated world is a bad
fixture for a split: it is 98.5% one disposition and roughly three quarters one domain, so
a share-based assertion passes for almost any mapping, including a constant one. The
fixture carries one group per medium and per class in equal numbers, and every assertion is
per entry against the catalogue, so a constant domain, a swapped one, or a lake folded into
the ocean fails on a named uid.

## Why it works this way

The domain is resolved from the species' authored medium rather than from the terrain under
the camp. A group's camps move; what it can live in does not, and a marine group camped at a
coastal node is still not something a party walks up to.

`kind` on an entry was already spent on the species id or the band classification, so the
class had nowhere to go and was being lost. Rather than mint a third spelling of
animal-versus-monster, the entry takes `class`, which is what `wildlife` and `beast_nests`
call it and what the profile document calls it.

## Does not establish

It does not index static sites. Only movers are indexed, so lairs — the most dangerous
things in the world, and the ones that hold still — are absent, and the `threat_tier`
histogram is not the world's danger profile. Whether to index them is a design decision and
a larger change than a field.

It does not establish anything about what a group is worth, what it wants, or what a party
should do about it. There are no objectives, stakes, rewards or difficulty here.

It does not account for two groups meeting each other, and it records occupancy at camps
only: a group in transit is derivable from its leg node path and its speed.

It does not establish that a stranded group is distinguishable from a routed one at the
entry. A stranded group appears with its start camp and a null day window, which reads as
"here, always"; carrying the reason is `board/backlog/CONTENT-BEAST-MOVEMENTS-STRANDED.md`.

It does not establish a native port. Under decision 027 that is deferred to a full rewrite.
