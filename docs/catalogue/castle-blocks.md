# Castle building blocks

Layout design revision 1, stored under `structure_blocks.castle` in [`buildings.json`](../../Sim/icarus_sim/buildings.json). These IDs are **separate from urban and rural libraries** and are consumed only by the [castle planner](../castle-planner.md).

Typology kits and join rules live in [`castles.json`](../../Sim/icarus_sim/castles.json).

## Measurement contract

All dimensions are **provisional game-design values in metres**. Axes, plot/clearance rules and metre-to-Unreal conversion match the [shared city block contract](human-civilization-blocks.md#measurement-contract). Curtain `depth` is the repeat length along the wall path; `width` is wall thickness.

## Inventory

Dimensions are **width × depth × height**; plots are **width × depth**, metres.

### Fortification modules

- **Curtain wall segment** (`building.curtain_segment`): 3 × 10 × 8 m; plot 7 × 10 m.
- **Castle corner tower** (`building.corner_tower`): 8 × 8 × 14 m; plot 12 × 12 m.
- **Wall-walk stair** (`building.wall_stair`): 4 × 6 × 8 m; plot 6 × 9 m.
- **Postern gate** (`building.postern`): 6 × 8 × 8 m; plot 10 × 14 m.
- **Barbican gatehouse** (`building.barbican`): 14 × 16 × 14 m; plot 18 × 28 m.
- **Drawbridge** (`building.drawbridge`): 6 × 14 × 2 m; plot 10 × 18 m.
- **Bailey courtyard** (`building.bailey_court`): 36 × 44 × 0 m; plot 36 × 44 m.

### Bailey services

- **Keep tower** (`building.keep_tower`): 16 × 16 × 24 m; plot 24 × 24 m. Command landmark without an embedded courtyard.
- **Great hall** (`building.great_hall`): 12 × 24 × 10 m; plot 16 × 31 m.
- **Castle chapel** (`building.castle_chapel`): 8 × 12 × 9 m; plot 12 × 17 m.
- **Castle barracks** (`building.castle_barracks`): 12 × 18 × 7 m; plot 16 × 25 m.
- **Castle armory** (`building.castle_armory`): 8 × 12 × 7 m; plot 12 × 18 m.
- **Castle well** (`building.castle_well`): 3 × 3 × 3 m; plot 7 × 7 m.

City `building.keep` / `building.wall` / `building.gatehouse` remain city-budget reuse candidates and are not placed by this planner.
