# Hero guild planning v1

This additive planning calculator is separate from generated city/world state.
`fantasy_world_generator.hero_guild.calculate(request, policy=None)` estimates
membership, activity, service and beds for one existing core guild hall. It does
not create NPCs, change population, place buildings or allocate housing. People are materialized separately and read-only by the [NPC roster](npc-roster.md).

Policies live in packaged `hero_guild_policies.json`, keyed by exact civilization
ID with schema version and authored revision. Every current civilization has an
explicit policy. The initial resident rate is zero for each: hero demographics
are not silently invented. Callers may supply a complete policy to explore a
scenario. Increment policy revision for authored edits. These policies do not
modify the existing civilization registry or its saved-world identity.

A request has exactly `civilization_id`, `city_block`, `population`,
`visiting_heroes_requested`, `available_jobs`, `already_housed_resident_heroes`
and `available_visitor_beds`. The first two resolve an existing city preset.
All counts are exact nonnegative integers no larger than 1,000,000,000; booleans,
floats and strings are rejected. `city_block` is small_city, medium_city or
capital_city. A capital title has no demographic multiplier. Population counts
existing permanent residents, including any resident heroes, not visitors.

A policy has exactly `resident_rate_numerator`, `resident_rate_denominator`,
`max_resident_heroes`, `max_visiting_heroes`, `party_size`, `max_active_parties`,
`heroes_per_service_worker` and `max_additional_staff`. Counts use the same bounds;
denominator and heroes_per_service_worker must be positive, party_size is 1–64,
and numerator cannot exceed denominator. Rates use integer rational arithmetic.
Initial capacity values are provisional scenario limits, not historical claims
or automatic population targets; all policy fields are returned in the result.

Formulas, applied in this order:

- Resident heroes = min(max_resident_heroes, floor(population * numerator / denominator)).
- Accepted visitors = min(visiting_heroes_requested, max_visiting_heroes). Excess is reported as unserved visitor demand, not admitted residents.
- Present heroes = residents + accepted visitors. Active parties = min(floor(present / party_size), max_active_parties, available_jobs). Each job activates one full party; remaining heroes are inactive. This is a simultaneous planning snapshot, not time-based quest simulation.
- The selected preset must contain one unconditional core guild hall with a fixed cook/bartender roster of two city workers. They are already counted by the city planner. Required extra staff = max(0, ceil(present / heroes_per_service_worker) - 2), capped by max_additional_staff. Service shortfall = max(0, present - (2 + extra_staff) * heroes_per_service_worker).
- Resident hero beds still needed = residents - already_housed_resident_heroes (the supplied housed count cannot exceed the calculated residents). New staff beds = extra_staff. Additional permanent bed demand is their sum, excluding the two existing hall workers.
- Temporary bed demand = accepted visitors; shortfall = max(0, visitors - available_visitor_beds). Visitors never contribute to permanent bed demand. Beds are a conservative overnight capacity assumption even for active parties.

The host must identify resident heroes already covered by its population/housing
plan and supply their housed count. Do not add the resident hero count to total
population or blindly add these beds to another complete population estimate.
Extra service staff are assumed distinct from heroes and the existing hall
workers; actual staffing assignment, recruitment, households and construction
remain future work. The calculator does not assert that requested staff can be
recruited from the current population.

The result declares `fantasy-world-generator.hero-guild-plan`, schema version 1,
policy source/revision, the full selected policy and normalized input, population,
party, service and accommodation breakdowns. No new asset IDs are emitted. The
existing world/recipe/civilization/asset schemas and generator RNG are unchanged.
Unknown civilizations, unsupported policy versions, malformed counts, an
incompatible hall roster and unknown/extra fields fail explicitly.

The structural [result schema](../Contracts/schemas/hero-guild-plan.schema.json) is included in reference contract artifacts. Semantic accounting and strict integer-token validation remain the API’s responsibility. The producer advertises `hero_guild_planning: 1` for Python only.
