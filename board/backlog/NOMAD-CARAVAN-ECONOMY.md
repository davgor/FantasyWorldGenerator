# NOMAD-CARAVAN-ECONOMY - make caravan throughput mean something

## Observed behavior

Roads that a merchant band actually rides carry `caravan_riders` and `caravan_throughput`.
**Nothing reads either field.** It is a share of road nodes ridden, not a modelled cargo
volume, and it does not reach `seasonal_food`, `transport` or `world_economy`.

So a world can have a caravan circuit running between two markets and the markets are no
better off for it, which is the opposite of why caravans exist.

## Proposed mechanism

`terrain_seasons.simulate_food` already trades between road neighbours with finite
throughput, winter penalties, transport loss and a material cost per shipment. A ridden road
should raise that edge's monthly capacity, or lower its price, in proportion to the bands
riding it.

## Unresolved

Whether a caravan adds capacity or merely uses it. Adding capacity risks a feedback loop -
richer markets support more caravans support richer markets - and the food model has no
damping for that today.

## Dependencies

`terrain_seasons`, `terrain_society`. Changes generated economy output, so it retires
existing worlds and needs a version bump.
