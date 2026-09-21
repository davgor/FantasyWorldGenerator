# NOMAD-CARAVAN-ECONOMY - make caravan throughput mean something

> **RETIRED 2026-09-21 by owner ruling — both levers were built, measured and found ineffective.**
> An agent implemented the price lever, instrumented `simulate_food`'s `min()` and counted which of
> its four terms binds each executed shipment over a four-year run: **capacity 449, exportable 59,
> need 6, and `budget` — the only term `price` appears in — zero.** Over the three ridden edges,
> capacity binds 88 of 88. Delivered food was identical to six significant figures at 10%, 25% and
> 40% discount; only `material_cost` moved, 78.21 → 77.79.
> It then built the *rejected* capacity lever too. Capacity does move food, and the feedback loop the
> card feared **cannot close** in current code (`add_nomads` gates on population and never on
> coverage; `add_seasonal_food` does not mutate population; `terrain_settlements.py:1034` replaces
> `roads` wholesale each age turn). But doubling capacity on ridden edges moves delivered food
> **+1.5% and raises total shortage**, because greedy direct-neighbour trade is not an optimal
> multi-hop solver and more capacity on 3 of 25 edges reshuffles who goes short.
> **The root cause is scale: trade is 47.1 units against 8,419 units of annual demand — 0.56% —
> with 3,510 units of shortage standing.** The most aggressive version of this card's own mechanism
> changes about 0.008% of demand. Either lever satisfies the card's title and not its argument.
> The owner ruled that a 0.56% trade layer is intended, so no caravan feature can be visible through
> `seasonal_food` and this card cannot succeed as written. The code was reverted cleanly —
> `terrain_seasons.py` hashes back to its recorded manifest bytes and owes no revision row.
> The worked edit, the binding-term census and both sweep tables are preserved below.
> Nothing here is a blocker.

**Not built, and the reason changed on 2026-09-21.** The provenance pin that first blocked
it was lifted by the orchestrator. It was then implemented, measured, and **reverted**: both
levers the card proposes were built and instrumented, and neither makes the markets better
off. The blocker is no longer access to the file. It is that **trade is 0.56% of demand in
this economy**, so nothing routed through `simulate_food` can matter.

`Sim/icarus_sim/terrain_seasons.py` is back to its recorded manifest bytes
(`0db8aa57…7180c`, verified by hash), so **no manifest revision row is owed.**

## Observed behavior

Roads that a merchant band actually rides carry `caravan_riders` and `caravan_throughput`.
**Nothing reads either field.** It is a share of road nodes ridden, not a modelled cargo
volume, and it does not reach `seasonal_food`, `transport` or `world_economy`.

So a world can have a caravan circuit running between two markets and the markets are no
better off for it, which is the opposite of why caravans exist.

## Premise, re-measured

Holds. One writer (`terrain_nomad_effects.apply_caravan_trade`, lines 152–153) and no reader
in `Sim/`, `tests/`, `tools/` or the lab. The fields are populated on a real world, so this
is a dead output rather than an empty one: seed 42 size 33 has 25 roads, 1 merchant band and
**3 ridden roads**. Seed 42 at size 17 raises no merchants, so size 33 is the smallest world
that exercises it.

**`caravan_throughput` was exactly 1.0 on all three.** It is `shared_nodes /
len(route.nodes)`, and a caravan routed between two markets walks the whole road between
them, so it saturates rather than spreading over a range. Anything pricing against it must
not assume a graded quantity; on the evidence it is close to a boolean.

## The unresolved question, answered — and then falsified

The card asks whether a caravan **adds capacity or merely uses it**. First answer, on a
priori reasoning: *lower the price, do not raise capacity*, because capacity is the term
carrying the feedback risk the card names and price cannot close that loop while the tonnage
ceiling and the buyer's `transport_budget` are untouched.

**That reasoning was sound and the lever is inert.** Measured on seed 42 size 33 by counting
which of the four terms in `simulate_food`'s

```
sent = min(exportable[seller], remaining, need/efficiency, budgets[buyer]/price/efficiency)
```

actually binds each executed shipment, over the full four-year run:

| | shipments bound by that term |
|---|---|
| `capacity` (`remaining`) | **449** |
| `exportable` | 59 |
| `need` | 6 |
| **`budget`** (the only term price appears in) | **0** |

Over the three ridden edges alone, capacity binds **88 of 88**. The budget term binds
nothing anywhere, so a price discount loosens a constraint that was never holding anything
back. Confirmed end to end — delivered food identical to six significant figures at a 10%,
25% and 40% discount:

| lever | delivered | annual shortage | shipments |
|---|---|---|---|
| nothing | 24.354 | 2926.558 | 127 |
| price −10% | 24.354 | 2926.558 | 127 |
| price −25% | 24.354 | 2926.558 | 127 |
| price −40% | 24.354 | 2926.558 | 127 |
| capacity +15% | 24.408 | 2926.725 | 127 |
| capacity +35% | 24.481 | 2926.948 | 127 |
| capacity +60% | 24.571 | 2927.226 | 127 |
| capacity +100% | 24.715 | 2927.672 | 127 |

Price moves one column only: total `material_cost` falls 78.21 → 77.79 at a 25% discount.
The buyer pays 0.5% less for exactly the same tonnage. That is a bookkeeping change, not an
economy.

## Why the rejected lever is not the answer either

Capacity does move food, and the feedback risk the card feared **does not exist in the
current code** — which was worth establishing and is recorded here so nobody re-derives it:
`terrain_nomads` gates merchants on `population_of(site)` and never on food coverage;
`add_seasonal_food` states that proposed population is not mutated; and
`terrain_settlements` replaces `result['roads']` wholesale at every age turn, so the previous
age's riders do not even survive into the next age's food model. The loop cannot close.

It is still not worth taking, for a reason that has nothing to do with feedback:

- Doubling capacity on the ridden edges moves delivered food from 24.354 to 24.715, **+1.5%
  of the trade layer**.
- The trade layer is **47.1 units against 8419 units of annual demand — 0.56%**, with 3510
  units of shortage standing.
- So the most aggressive version of the card's own mechanism changes about **0.008% of
  demand**, and it *raises* total shortage slightly, because greedy direct-neighbour trade
  is not an optimal multi-hop solver — the block's own `limits` says so — and more capacity
  on 3 of 25 edges reshuffles which city goes short rather than feeding anyone.

Shipping either lever satisfies the card's title and not its argument. The markets would
still be no better off, which is the exact defect being reported.

## What this card actually needs

The finding is one layer down from where the card points it. Reaching the markets through
`seasonal_food` cannot work while trade is half a percent of demand, so this is two pieces of
work, neither of them "wire the field in":

- **The trade layer is negligible and that may itself be the defect.** 0.56% of demand moved
  between road neighbours, against a 42% coverage gap. Either that is intended — in which
  case no caravan feature can ever be visible through it, and this card should be retired —
  or the direct-neighbour, one-month-donor-reserve, no-re-export model is under-trading and
  that is a `terrain_seasons` card of its own. **Someone should rule on which.**
- **The other two consumers were never available.** The card names `transport` and
  `world_economy` beside `seasonal_food`. Both are written by
  `Sim/icarus_sim/terrain_society.py:274-275`, which was fenced to another session, so
  neither was tested. If trade matters anywhere it is more likely to matter there, and that
  is where this should be re-scoped to look first.

## The edit, worked out, if the ruling comes back "do it anyway"

1. In `terrain_seasons.add_seasonal_food`, at the per-edge record:
   `ridden = min(1., max(0., float(road.get('caravan_throughput') or 0.)))`, then scale
   `capacity` (not `price`) by `(1 + CARAVAN_CAPACITY_LIFT * ridden)`. **Capacity is the
   only term that binds these edges.** An unridden road multiplies by exactly 1.0, which is
   exact, so a world nobody rides is bit-for-bit unchanged.
2. **Ordering, which is the subtlety and was measured rather than assumed.**
   `add_seasonal_food` runs inside `civilization()` at phase 9 and caravans are placed at
   phase 16, so generation never sees the field. An age advance does not see it either:
   `terrain_settlements.py:1034` replaces `result['roads']` wholesale inside
   `rebuild_tail`, clearing the caravan keys before the food model runs. **The only path
   where it bites is a tick** — roads are read-only below the age band, so the fields
   persist, and `seasonal_food` (90-day cadence, rank 2) reads what the previous
   `nomad_effects` (360-day cadence, rank 7) left. Last year's riders, this year's
   shipping, which is self-damping and correct.
3. `seasonal_food.version` 1 → 2, with a binding, because the block stops being a pure
   function of the road network. `terrain_seasons.py` is claimed by no conformance record
   (`docs_check --list-uncovered`), so landing it means giving it one or extending
   `docs/conformance/nomads.md`, whose "Does not establish" section currently states that
   caravan throughput is consumed by nothing.
4. A behavioural test needs size 33 or larger. It goes in `Sim/tests/test_terrain_nomads.py`
   and not `Sim/tests/test_terrain_seasons.py`, which is provenance-pinned.

## Dependencies

`terrain_seasons` (pin lifted 2026-09-21; the file is back to its recorded bytes and owes no
revision row). `terrain_society` — named in the original card, untouched by the mechanism
above, and fenced. Would change generated economy output on the tick path only, so it
retires ticked worlds rather than generated ones.
