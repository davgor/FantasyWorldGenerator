# NOMAD-IRRUPTION-TRIGGER - swarms that erupt in bad years, not every year

## Observed behavior

An irruptive creature is one that is normally sparse and occasionally overwhelming. The
locust pattern: the solitary phase is the normal state, and gregarious swarming is a
response to violent environmental fluctuation, forming in marginal ground and marching when
local resources deplete.

Today every irruptive group is present in every year, because **there are no years**. The
class carries the right route shape - one march out of marginal ground toward the best
forage in reach - but no condition in time deciding whether it happens at all.

## Dependency, which is the whole point of this card

This needs the **time controls** work the user has queued. An irruption is a function of a
particular year being bad, and nothing in the generator currently distinguishes one year
from another. Building a trigger before that exists would mean inventing a calendar inside
the creature pass.

## Proposed mechanism, once years exist

Compare a year's forage at the group's start node against the local mean. Erupt when it
falls below a threshold; the march itself is already built. `seasonal_environment` supplies
the monthly grids and `terrain_seasons.seasonal_harvest` the growth curve.

## Related

`terrain_nomad_routes` day windows and `nomads.groups[].speed_m_per_day` were built so a
time-mover can interpolate a position for any day. This card is the other half of that.
