# Shared civilization building blocks

Layout design revision 1, stored under `structure_blocks.common` in buildings.json. [Canonical structured data](../../Sim/icarus_sim/buildings.json).

This is the shared city layout requirements source for the next planner pass and the later production catalogue rebuild. It contains **80 non-housing structure requirements in 11 functional blocks**. A requirement can share a building with another service; it is not a demand for 80 separate buildings in every city. Existing production IDs are reuse candidates only, and do not define the new design.

This non-housing library excludes homes, apartments, noble residences and dormitories. The separate worker-house profile now supplies planner housing. Inns describe their service space; barracks describe their muster and equipment space. Their sleeping accommodation will be planned with housing. Institutional treatment and custody spaces remain part of their respective services.

## Measurement contract

All dimensions are **provisional game-design values in metres** for a medium-city planning pass, not surveyed historical measurements, final meshes or proven performance limits.

- Each row records footprint width, depth and above-grade height in `dimensions_m`.
- `clearance_m` records front/rear/left/right space outside that footprint. `plot_m` includes those clearances and is the map reservation.
- Width follows local X along the frontage; depth follows local Z away from the front; height follows local Y. Rotate footprint, clearance and access together.
- A compound footprint already contains its named workyard. An open-area height of zero does not remove props, vegetation or terrain.
- Linear structures use width across the path and depth along it. Streets and walls are path segments; bridges carry an illustrative span. Join ends without per-building setbacks. Grade, corners, junctions, abutments and span feasibility still need a layout resolver.
- Access widths are external route clearances. They do not specify door widths, gate passage heights, internal routes or cart turning circles.
- Setbacks are initial map reservations, not fire, sanitation or magical safety guarantees. Water flow, flood levels, slope, underground space, windmill rotor clearance and hazard separation need site-specific checks.
- There is no random scaling. Larger or smaller versions and shared-use footprints need deliberate recipes. Housing and population capacities remain deferred.
- Source metres convert to Unreal centimetres at the future adapter boundary by multiplying by 100.

For example, a **14 Ã— 20 Ã— 12 m civic hall** reserves an **18 Ã— 29 m plot**, including 6 m front access, 3 m rear clearance and 2 m on each side. A **6 m-wide street** uses a **10 m repeat length** and reserves a **10 m-wide corridor**, including 2 m verges on either side.

## City composition and scale

**Core** means provide the service in an ordinary human city, potentially through a shared building or supplied alternative. **Conditional** requires the listed terrain, resource, trade or defense conditions. **Specialist** depends on a city's role, wealth, institutions or future systems. These are planning priorities, not executable placement flags.

Each civilization now has explicit small, medium and capital building quantities in the [master registry](../civilizations.md). These are provisional class budgets. Future placement must reconcile them with population, production throughput, trade, geography and city budget. Repeat neighborhood services as required; do not duplicate a landmark simply because population rises. Civic hall/court/records, temple/infirmary, inn/tavern, market/notice space and gatehouse/guardhouse are candidate shared arrangements. Shared buildings must explicitly allocate space and capacity rather than count the same floor area twice.

Keep water intakes separate from waste and dirty industry. Connect deliveries to market, food stores, workshops and gates. Preserve open circulation through squares. Place docks only on usable shores, mills only with supported power, and extraction sites only on actual resources. The city depends on its surrounding supply area; farms and quarries do not belong in every urban block.

The reusable module families are hall, workshop, storehouse, service yard/outbuilding, market, mill, fortification, linear infrastructure, waterfront, open space, landmark and specialist structures. They reduce unique art needs while preserving different functional roles. Human materials and style can vary without changing these requirements.

## Structure inventory

Dimensions below are **width Ã— depth Ã— height**; plots are **width Ã— depth**, all in metres. The JSON also contains purpose, prerequisites, placement guidance, access widths and reuse candidates for every row.

### Water and sanitation

- **Public well** (`building.well`, core): 3 Ã— 3 Ã— 3 m; plot 7 Ã— 9 m. Supply drinking and household water.
- **Cistern and collection court** (`building.cistern`, conditional): 8 Ã— 10 Ã— 3 m; plot 12 Ã— 19 m. Store collected or delivered water.
- **Public water point** (`building.water_point`, core): 4 Ã— 4 Ã— 2 m; plot 8 Ã— 10 m. Distribute water and provide fire-response access.
- **Drains and culverts** (`building.drainage`, core): 1 Ã— 10 Ã— 0 m; plot 2 Ã— 10 m. Route runoff away from buildings and roads.
- **Public latrines** (`building.latrine`, core): 6 Ã— 4 Ã— 3 m; plot 10 Ã— 10 m. Provide sanitation for markets and public facilities.
- **Waste collection yard** (`building.waste_yard`, core): 16 Ã— 20 Ã— 3 m; plot 28 Ã— 32 m. Collect refuse and night soil for removal.
- **Bathhouse and washhouse** (`building.bathhouse`, specialist): 14 Ã— 18 Ã— 6 m; plot 18 Ã— 24 m. Support bathing and laundry.

### Food processing and storage

- **Granary** (`building.granary`, core): 10 Ã— 14 Ã— 9 m; plot 14 Ã— 23 m. Store grain reserves.
- **Bakery and communal oven** (`building.bakery`, core): 8 Ã— 10 Ã— 6 m; plot 12 Ã— 19 m. Turn flour into bread.
- **Watermill** (`building.watermill`, conditional): 10 Ã— 14 Ã— 9 m; plot 22 Ã— 26 m. Process grain using water power.
- **Windmill** (`building.windmill`, conditional): 12 Ã— 12 Ã— 18 m; plot 24 Ã— 24 m. Process grain using wind power.
- **Hand-milling shelter** (`building.hand_mill`, conditional): 6 Ã— 8 Ã— 4 m; plot 10 Ã— 14 m. Provide milling where powered mills are unavailable.
- **Butchery and slaughter yard** (`building.butchery`, conditional): 12 Ã— 16 Ã— 5 m; plot 24 Ã— 28 m. Process available livestock into meat.
- **Smokehouse and salting store** (`building.preservation_house`, conditional): 8 Ã— 10 Ã— 5 m; plot 12 Ã— 19 m. Preserve surplus food.
- **Brewery** (`building.brewery`, specialist): 12 Ã— 16 Ã— 8 m; plot 16 Ã— 25 m. Produce beverages for trade and local consumption.
- **Cool store and root cellar** (`building.root_cellar`, core): 8 Ã— 10 Ã— 2 m; plot 12 Ã— 19 m. Store vegetables and other perishables.

### Trade and visiting services

- **Market square** (`building.market_square`, core): 30 Ã— 40 Ã— 0 m; plot 34 Ã— 49 m. Exchange food, goods and services.
- **Market stalls and covered hall** (`building.market_shelter`, core): 6 Ã— 12 Ã— 5 m; plot 10 Ã— 21 m. Provide sheltered trading space.
- **Warehouse** (`building.warehouse`, core): 12 Ã— 20 Ã— 9 m; plot 16 Ã— 29 m. Store traded goods.
- **Inn service hall** (`building.inn`, conditional): 12 Ã— 16 Ã— 6 m; plot 16 Ã— 25 m. Serve travelers with meals and reception.
- **Tavern** (`building.tavern`, specialist): 10 Ã— 12 Ã— 6 m; plot 14 Ã— 18 m. Provide food, drink and a gathering place.
- **Stable and farrier yard** (`building.stable`, conditional): 16 Ã— 20 Ã— 5 m; plot 20 Ã— 29 m. Support visiting and working animals.
- **Cart yard and wagon shelter** (`building.cart_yard`, core): 20 Ã— 24 Ã— 5 m; plot 24 Ã— 33 m. Load, park and maintain delivery carts.
- **Weigh house and toll office** (`building.weigh_house`, conditional): 6 Ã— 8 Ã— 5 m; plot 10 Ã— 17 m. Inspect cargo, weights and collected dues.

### Crafts and building trades

- **Smithy** (`building.smithy`, core): 10 Ã— 14 Ã— 6 m; plot 14 Ã— 23 m. Repair tools and work metal.
- **Carpenter and wheelwright yard** (`building.carpenter`, core): 14 Ã— 18 Ã— 6 m; plot 18 Ã— 27 m. Make and repair timber components and carts.
- **Mason and construction yard** (`building.mason`, core): 20 Ã— 24 Ã— 5 m; plot 24 Ã— 33 m. Prepare and stage building materials.
- **Pottery and kiln** (`building.pottery`, conditional): 12 Ã— 16 Ã— 6 m; plot 24 Ã— 28 m. Produce vessels and ceramic goods.
- **Weaver and tailor workshop** (`building.weaver`, core): 8 Ã— 12 Ã— 6 m; plot 12 Ã— 21 m. Produce and repair textiles and clothing.
- **Tannery and leatherworking yard** (`building.tannery`, conditional): 18 Ã— 24 Ã— 5 m; plot 30 Ã— 36 m. Process hides and leather.
- **Dyehouse** (`building.dyeworks`, specialist): 12 Ã— 16 Ã— 6 m; plot 24 Ã— 28 m. Finish textiles.
- **Fuel and materials depot** (`building.fuel_depot`, core): 16 Ã— 20 Ã— 5 m; plot 28 Ã— 32 m. Stage fuel and repair supplies.
- **Smelter and furnace yard** (`building.smelter`, conditional): 20 Ã— 24 Ã— 10 m; plot 32 Ã— 36 m. Refine ore before smithing.

### Government and administration

- **Civic hall** (`building.civic_hall`, core): 14 Ã— 20 Ã— 12 m; plot 18 Ã— 29 m. Coordinate administration and public meetings.
- **Court and records office** (`building.court`, core): 12 Ã— 16 Ã— 9 m; plot 16 Ã— 22 m. Resolve disputes and retain civic records.
- **Treasury and tax store** (`building.treasury`, conditional): 8 Ã— 10 Ã— 6 m; plot 12 Ã— 19 m. Secure collected goods and currency.
- **Guild hall** (`building.guildhall`, core): 12 Ã— 18 Ã— 10 m; plot 16 Ã— 27 m. Provide guild gathering space with a kitchen and bar.
- **Proclamation and notice space** (`building.notice_space`, core): 4 Ã— 6 Ã— 0 m; plot 8 Ã— 12 m. Make civic decisions and local information visible.

### Care and public safety

- **Infirmary and healer's house** (`building.infirmary`, core): 12 Ã— 18 Ã— 7 m; plot 16 Ã— 27 m. Provide treatment and short-term care.
- **Apothecary and herb garden** (`building.apothecary`, conditional): 10 Ã— 14 Ã— 5 m; plot 14 Ã— 20 m. Prepare and store remedies.
- **Isolation ward** (`building.isolation_house`, conditional): 10 Ã— 16 Ã— 5 m; plot 22 Ã— 28 m. Separate infectious patients when needed.
- **Fire equipment shed** (`building.fire_shed`, core): 6 Ã— 8 Ã— 4 m; plot 10 Ã— 17 m. Store buckets, ladders and response equipment.

### Faith and remembrance

- **Neighborhood shrine** (`building.shrine`, conditional): 3 Ã— 4 Ã— 4 m; plot 7 Ã— 10 m. Provide a small local place of worship.
- **Temple and assembly court** (`building.temple`, core): 16 Ã— 24 Ã— 16 m; plot 20 Ã— 33 m. Support communal worship and ceremonies.
- **Cemetery and funerary shelter** (`building.cemetery`, core): 30 Ã— 40 Ã— 3 m; plot 34 Ã— 46 m. Provide burial and funerary services.
- **Crypt or mausoleum** (`building.crypt`, specialist): 8 Ã— 12 Ã— 5 m; plot 12 Ã— 18 m. Provide enclosed interment.
- **Great temple or cathedral** (`building.great_temple`, specialist): 30 Ã— 50 Ã— 35 m; plot 34 Ã— 59 m. Serve a major religious center.

### Defense and security

- **Guardhouse** (`building.guardhouse`, core): 8 Ã— 10 Ã— 7 m; plot 12 Ã— 19 m. Coordinate patrols and hold watch equipment.
- **Barracks service and muster block** (`building.barracks`, conditional): 14 Ã— 20 Ã— 7 m; plot 18 Ã— 29 m. Organize garrison equipment and deployment.
- **Armory** (`building.armory`, conditional): 10 Ã— 14 Ã— 7 m; plot 14 Ã— 23 m. Secure arms and armor.
- **Training and muster yard** (`building.training_yard`, conditional): 24 Ã— 32 Ã— 0 m; plot 28 Ã— 41 m. Provide space for drills and assembly.
- **Holding cells** (`building.holding_cells`, core): 8 Ã— 10 Ã— 5 m; plot 12 Ã— 16 m. Hold detainees for civic justice.
- **Gatehouse** (`building.gatehouse`, conditional): 14 Ã— 12 Ã— 14 m; plot 18 Ã— 21 m. Control a defended road entrance.
- **Walls and wall walks** (`building.wall`, conditional): 3 Ã— 10 Ã— 7 m; plot 7 Ã— 10 m. Create a continuous defended perimeter.
- **Watch and wall towers** (`building.tower`, conditional): 8 Ã— 8 Ã— 16 m; plot 12 Ã— 14 m. Provide observation and defend approaches.
- **Defensive ditch and palisade** (`building.ditch_palisade`, conditional): 10 Ã— 10 Ã— 4 m; plot 14 Ã— 10 m. Provide lower-cost perimeter defenses.
- **Keep and defensive courtyard** (`building.keep`, specialist): 24 Ã— 30 Ã— 24 m; plot 28 Ã— 39 m. Provide a protected command point and refuge.

### Streets and transport

- **Streets and alleys** (`building.street`, core): 6 Ã— 10 Ã— 0 m; plot 10 Ã— 10 m. Connect plots and city services.
- **Public squares and courtyards** (`building.square`, core): 20 Ã— 24 Ã— 0 m; plot 24 Ã— 33 m. Provide gathering and circulation space.
- **Stairs and ramps** (`building.stairs_ramps`, conditional): 4 Ã— 10 Ã— 0 m; plot 8 Ã— 10 m. Connect different ground levels.
- **Retaining walls and terraces** (`building.retaining_wall`, conditional): 1.5 Ã— 10 Ã— 3 m; plot 5.5 Ã— 10 m. Support construction on slopes.
- **Bridge** (`building.bridge`, conditional): 6 Ã— 20 Ã— 1.5 m; plot 10 Ã— 20 m. Carry routes across water or gaps.
- **Dock and quay** (`building.dock`, conditional): 8 Ã— 24 Ã— 2 m; plot 12 Ã— 33 m. Transfer people and cargo to water routes.
- **Boatyard and repair slip** (`building.boatyard`, conditional): 24 Ã— 36 Ã— 8 m; plot 36 Ã— 48 m. Repair and construct supported watercraft.
- **Property walls, fences and gates** (`building.boundary_wall`, core): 0.5 Ã— 10 Ã— 2 m; plot 4.5 Ã— 10 m. Define service yards and protected plots.

### Knowledge and fantasy specialization

- **School and study hall** (`building.school`, specialist): 10 Ã— 16 Ã— 7 m; plot 14 Ã— 22 m. Support organized teaching.
- **Library and archive** (`building.library`, specialist): 12 Ã— 18 Ã— 10 m; plot 16 Ã— 24 m. Store books and specialist records.
- **Alchemy and magical laboratory** (`building.laboratory`, specialist): 12 Ã— 16 Ã— 8 m; plot 16 Ã— 25 m. Provide specialist research and experimentation.
- **Observatory** (`building.observatory`, specialist): 10 Ã— 10 Ã— 18 m; plot 14 Ã— 16 m. Provide celestial observation facilities.
- **Ward anchors and ward posts** (`building.ward_anchor`, specialist): 3 Ã— 3 Ã— 5 m; plot 7 Ã— 9 m. Reserve sites for supported protective magic.
- **Magical workforce infrastructure** (`building.magical_worksite`, specialist): 20 Ã— 24 Ã— 10 m; plot 32 Ã— 36 m. Reserve work space for future magical labor systems.
- **Major magical anchor precinct** (`building.magic_well`, specialist): 30 Ã— 30 Ã— 16 m; plot 42 Ã— 42 m. Reserve a strategic site for a future Magic Well.

### Supporting outskirts

- **Farm workyard and barn** (`building.farmstead`, conditional): 24 Ã— 30 Ã— 8 m; plot 28 Ã— 39 m. Support surrounding agricultural production.
- **Kitchen gardens and orchards** (`building.garden_orchard`, conditional): 20 Ã— 30 Ã— 0 m; plot 24 Ã— 39 m. Provide supported local crops.
- **Livestock pens and fodder store** (`building.livestock_yard`, conditional): 20 Ã— 24 Ã— 5 m; plot 24 Ã— 33 m. Support animals supplying the city.
- **Timber extraction and seasoning yard** (`building.timber_yard`, conditional): 24 Ã— 32 Ã— 6 m; plot 28 Ã— 41 m. Prepare timber from a managed source.
- **Quarry worksite** (`building.quarry`, conditional): 40 Ã— 50 Ã— 0 m; plot 52 Ã— 62 m. Supply suitable building stone.
- **Clay pit and brickworks** (`building.clay_pit`, conditional): 30 Ã— 40 Ã— 8 m; plot 42 Ã— 52 m. Supply clay and fired construction materials.
- **Mine entrance and ore yard** (`building.mine`, conditional): 18 Ã— 24 Ã— 6 m; plot 30 Ã— 36 m. Connect the city to supported ore production.
- **Charcoal burning yard** (`building.charcoal_yard`, conditional): 20 Ã— 24 Ã— 4 m; plot 32 Ã— 36 m. Produce charcoal for eligible industries.

## Integration boundary

This versioned design input is now consumed by the final-world city planner and exhaustive asset compiler as schematic measured plots. See [the planner contract](../city-planner.md). Existing production packs remain separate art candidates.

The later layout integration should resolve dimensions, routes, shared facilities, conditional requirements, terrain and budgets before materializing structures. When any new structure becomes a reachable generator asset, update the exhaustive asset compiler, coverage tests and production catalogue together. New catalogue rows alone must not create water, food, ore, animals, inhabitants, magic protection or Unreal content.

Future damaged, construction and ruin variants need explicit coverage at that integration step. Knowledge/magic blocks include planned capabilities and must not be interpreted as functioning systems today.

## Staffing

Each structure now has an operating roster with minimum, target and maximum distinct workers and city/hinterland housing location. Presets multiply these by quantities and separate conditional facilities. See the [staffing contract](../civilizations.md#staffing-and-worker-housing-registry-schema-3-revision-3). Household sizes remain deferred; the final-world planner places four-worker shared houses.

Every city-size preset now includes one core guild hall, staffed by one cook and one bartender. Hero-guild calculations are tracked in [HERO-GUILD](../../board/backlog/HERO-GUILD.md).
