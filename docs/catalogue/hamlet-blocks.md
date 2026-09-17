# Hamlet building blocks

Layout design revision 1, stored under `structure_blocks.rural` in [`buildings.json`](../../Sim/icarus_sim/buildings.json). These IDs are **separate from urban city blocks** so later Unreal art can diverge.

This library covers **12 non-housing rural structures** plus linear `building.hamlet_track`. Housing uses `housing_profiles.hamlet_house` (`building.hamlet_house`), not city worker houses or apartments.

## Measurement contract

All dimensions are **provisional game-design values in metres**. Axes, plot/clearance rules and metre-to-Unreal conversion match the [shared city block contract](human-civilization-blocks.md#measurement-contract).

## Priorities and role filters

- **Core** — ordinary support hamlet services.
- **Conditional** — shrine, meeting, cart and smith sheds; coastal landing and net shed when `navigable_shore` applies.
- Planner role tags (not city terrain checks): `farming_support` for barn/farmyard, `resource_support` for staging yard. Coastal roles (`harbor`, `fishing`, `landing`, `harbor + fishing`) satisfy `navigable_shore`.

## Inventory

Dimensions are **width × depth × height**; plots are **width × depth**, metres.

### Core

- **Hamlet well** (`building.hamlet_well`): 2 × 2 × 2 m; plot 4 × 6 m.
- **Hamlet latrine** (`building.hamlet_latrine`): 3 × 3 × 2 m; plot 5 × 7 m.
- **Hamlet food store** (`building.hamlet_food_store`): 4 × 6 × 3 m; plot 6 × 11 m.
- **Hamlet barn** (`building.hamlet_barn`, farming): 6 × 8 × 5 m; plot 10 × 14 m.
- **Hamlet farmyard** (`building.hamlet_farmyard`, farming): 10 × 12 × 4 m; plot 14 × 18 m.
- **Hamlet staging yard** (`building.hamlet_staging_yard`, resource): 6 × 6 × 3 m; plot 10 × 11 m.
- **Hamlet track** (`building.hamlet_track`, linear): 3 × 8 × 0 m; plot 5 × 8 m. Path segments, not a rectangular building plot.

### Conditional

- **Hamlet shrine** (`building.hamlet_shrine`): 4 × 4 × 4 m; plot 6 × 9 m.
- **Hamlet meeting shed** (`building.hamlet_meeting_shed`): 6 × 8 × 4 m; plot 8 × 13 m.
- **Hamlet cart shed** (`building.hamlet_cart_shed`): 6 × 8 × 3 m; plot 8 × 13 m.
- **Hamlet smith shed** (`building.hamlet_smith_shed`): 5 × 6 × 4 m; plot 7 × 11 m.
- **Hamlet landing** (`building.hamlet_landing`, coastal): 4 × 8 × 2 m; plot 8 × 14 m.
- **Hamlet net shed** (`building.hamlet_net_shed`, coastal): 4 × 6 × 3 m; plot 6 × 11 m.

### Housing

- **Hamlet cottage** (`building.hamlet_house`): 5 × 6 × 4 m; plot 9 × 12 m; **2** worker beds. No apartment densification in hamlet planner v1.
