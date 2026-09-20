# Documentation map

- [Conformance records](conformance/README.md) are the present-tense breakdown of what this product does: every module claimed by exactly one record, stating what it produces, what it emits, at what version, and what proves it. Start there to learn what exists; the documents below explain why it behaves as it does. `board/` is the change log.
- [Repository plan](../PLAN.md) is the canonical roadmap, ownership, package, and acceptance handoff.
- [Simulation and world layers](terrain-world-layers.md) is the canonical generator behavior contract.
- [Unified globe scene](unified-world-scene.md) defines leyline variation, city/world junctions and global placements.
- [The moon](astrology.md) defines the lunar cycle, its almanac and clock hooks, temporary ley surges and ruin legacies.
- [Time advance](time-advance.md) defines the clock a live world runs on: the calendar and `world_clock`, the bands an elapsed span selects, why a span of an age or longer is answered with an age advancement and a cost estimate rather than a tick, the quest lifecycle, the one liveness predicate, and the invariant that a span cut differently produces the same world.
- [Pantheon](pantheon.md) defines the god catalogue, cosmologies, faiths and the visitation API that lets the orchestrator summon a god.
- [Hidden schools](hidden-schools.md) defines the twelve-school taxonomy: the four schools the world does not know, why they are appended rather than inserted, and why generation can never raise one.
- [Super villains](super-villains.md) defines the antagonists that operate on a different order than the kings around them: tier as continuous reach, the turmoil that raises it, and the fate lottery they take cities through.
- [Corruption](corruption.md) defines the four hidden gods, the encounters gate that decides whether one acts, the four failure modes, and the cleansing that is also how a walking god is opposed.
- [Continuous terrain data](continuous-terrain.md) defines shared physical heights and resolved tile exports.
- [Final-world city planner](city-planner.md) defines ordered building filling, worker housing and the lab city view.
- [Final-world hamlet planner](hamlet-planner.md) defines independent rural packing, dedicated hamlet building IDs and lab hamlet view.
- [Final-world castle planner](castle-planner.md) defines independent fortification modules, wall networks and bailey layouts from fortress pins.
- [Historical city shapes](city-shapes.md) defines the sourced shape catalogue and location-based planner selection.
- [Civilization master registry](civilizations.md) is the canonical authoring guide for entities, generation rules and construction libraries.
- [Hero guild planning](hero-guild.md) defines opt-in demographic, party, service and accommodation calculations with explicit configurable rates.
- [Hero generator](hero-generator.md) defines the separate cast package: people precipitated from ruins and wars, alignment-then-archetype selection, personas, and the `heroes` export.
- [Story web](story-web.md) defines the separate story-web package: every living hero's trope spokes, the deterministic weight equation, the offered resting hook, bound acts with options and threads, and the `story_web` export.
- [Heritage](heritage.md) defines the separate heritage package: seventeen categorical key traits per race, the culture derived from them, the language genome derived from culture and physiology, the morphemic naming those genomes drive, and the authored appearance layer - stature, palettes, features and art direction per subrace - that the concept-art, sprite and model pipelines read.
- [NPC roster](npc-roster.md) defines the separate people package: one record per staffed post, the bounded quest-giver earmark, the alive/dead state and the `npcs` export.
- [Key locations](key-locations.md) defines the separate places package: ninety-seven catalogue archetypes across eleven families, percentile-relative placement, derived state and occupant, the succession pass that produces dungeons without a dungeon archetype, chains and clusters for the places that are wrong placed alone, tier-2 interior chamber graphs, and the `key_locations` export.
- [Nomads](nomads.md) defines the travelling bands the land raises once the simulation settles: the six classifications, the hard geographic gate each one must pass before any weight is drawn, why a candidate satisfying none raises nobody, and the `nomads` export.
- [Beast movement](beast-movement.md) defines the creatures that do not hold ground: the five movement classes on the creature catalogue, why an undead with a grave nests at it and one without wanders, and the `beast_movements` and `encounters` exports.
- [Standalone civilizations](decisions/016-standalone-civilizations.md) defines human entities, cultural habitat rules and city classifications.
- [Heritage chain](decisions/021-heritage-chain.md) records why the categorical race layer is a leaf package rather than a registry section, and what that keeps still.
- [Terrain FantasyWorldGenerator](terrain-math-lab.md) records the mathematical model and its evolution.
- [Unreal integration](unreal-integration.md) defines the engine boundary, UnrealWorldGen consumer, and current limitations.
- [Unreal Editor MCP](unreal-mcp.md) is the UnrealWorldGen editor bridge; Unity MCP is not a substitute.
- [Publishing](publishing.md) defines release artifacts and the exhaustive asset-list policy.
- [Agent workflow](agent-workflow.md) defines implementation and evidence standards.
- [World asset catalogue](catalogue/world-assets/README.md) contains the inherited production briefs.
- [Human civilization blocks](catalogue/human-civilization-blocks.md) define non-housing city layout requirements and provisional metre-scale measurements for the later catalogue rebuild.
- [Hamlet building blocks](catalogue/hamlet-blocks.md) define dedicated rural structure IDs and cottage housing separate from city blocks.
- [Castle building blocks](catalogue/castle-blocks.md) define fortification modules and bailey services for the independent castle planner.
- [Extraction provenance](../provenance/README.md) defines source-hash preservation and licensing limitations.
- [Contracts](../Contracts/README.md) index versioned schemas and generic capability inputs.
- [Capabilities and coordinates](../Contracts/capabilities-and-coordinates.md) defines producer negotiation, physical units, globe/local projections and portable coordinate fixtures.
- [Kernel contracts](../Contracts/kernel-v1.md) defines exact numeric/identity/failure rules and the bounded counter proof, separate from generated worlds.
- [Ticket board](../board/README.md) identifies active and queued implementation work.

## Decision records

Why a choice was made, and what it ruled out. Two of these are also indexed above where
they double as the canonical description of a subsystem.

- [001 Reference and facade boundary](decisions/001-reference-and-facade-boundary.md) — keeping the extracted Python oracle behind a new publishing facade.
- [002 Export artifact is not a runtime package](decisions/002-export-artifact-is-not-runtime-package.md)
- [014 MathLab biome gate](decisions/014-mathlab-biome-gate.md)
- [015 Explicit biome states](decisions/015-explicit-biome-states.md) — retiring legacy biome and save compatibility.
- [016 Standalone civilizations](decisions/016-standalone-civilizations.md)
- [017 Civilization master registry](decisions/017-civilization-master-registry.md) — the one a bare "decision 017" means.
- [018 UnrealWorldGen dev consumer](decisions/018-unrealworldgen-dev-consumer.md)
- [019 Runtime surface, not Landscape](decisions/019-runtime-surface-not-landscape.md) — why no `ALandscape` actor exists.
- [020 Authoring catalogues ship as data](decisions/020-authoring-catalogues-ship-as-data.md)
- [021 Heritage chain](decisions/021-heritage-chain.md)
- [022 Private source-inclusive package policy](decisions/022-private-package-distribution.md) — renumbered from a second 017; earlier references to "decision 017" for distribution mean this one.
- [023 World compatibility policy](decisions/023-world-compatibility-policy.md) — worlds are disposable and no migration is owed, until phase 2, the first player-facing consumer.
- [025 Controls are a machine contract](decisions/025-controls-are-a-machine-contract.md) — every published control carries a description and a unit, and the catalogue ships as generated data the native core and the packaged plugin read.
- [024 Fallen claim decay](decisions/024-fallen-claim-decay.md) — a fallen villain's claim fades over ages and its record does not, so a world advanced across many ages is not governed by its dead.

Numbers 003 to 013 were allocated in the source repository and did not come across with
the extraction. The gap is inherited, not a set of missing records.
