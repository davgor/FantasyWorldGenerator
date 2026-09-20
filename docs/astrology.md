# The moon: astrology schema 1, lunar almanac 1

One moon, not tidally locked, whose two hemispheres carry the eight magic schools. Three seeded integer-day cycles beat against each other, so the rhythm is fully replayable from the exported parameters yet long enough to read as chaos. Leyline strength surges and ebbs with the moon; the exported ley grids stay the base field and the surge is a multiplier a consumer applies at a moment in time. Ruins seed key points; gods may exist, sleep, or be summoned (see [pantheon](pantheon.md)).

Reference: `Sim/icarus_sim/terrain_astrology.py` (moon), `terrain_ruins.py` (ruin legacies). The C++ mirror is `Core/astrology.cpp`.

## The body

| Hemisphere | Moon latitude | Quarters at longitude 0°, 90°, 180°, 270° |
|---|---|---|
| Still (order) | +45° | radiant, water, earth, umbral |
| Restless (chaos) | −45° | weave, fire, air, infernal |

Region centres are unit vectors in the moon frame (`y` is the polar axis). They are derived from the school order, like the mutation threshold, and are exported under `astrology.moon.regions`.

## Calendar and cycles

`hours_per_day` 24, `days_per_month` 30, `months_per_year` 12. Day 0 is founding year 0 and hour 0 is sunrise. Time `t` is a real number of days; the simulation only ever samples integer days and uses integer modulo for them.

Seeded once per world from `child_seed(seed, 'astrology-v1')`, in this draw order: synodic period `randint(26, 34)`; spin period `randint(15, 63)` redrawn up to eight times until coprime with the synodic; nod period `randint(17, 37)` redrawn until coprime with both; one offset `randint(0, P-1)` per cycle; `tilt_max = uniform(10, 35)` degrees. `great_year_days` is the least common multiple of the three periods.

| Cycle | Meaning | Angle |
|---|---|---|
| synodic | phase; the sun's direction `s = (cos α, 0, sin α)` | `α = 2π·f_synodic`, 0 full, π new |
| spin | which meridian faces the world | `β = 2π·f_spin` about the polar axis |
| nod | which hemisphere leans toward the world | `γ = tilt_max·sin(2π·f_nod)`; positive leans Still |

with `f_k(t) = ((t + offset_k) mod period_k) / period_k`.

## Tide

For a school's region `c0`: rotate by the spin about `y`, lean by the nod about `z`, then `visible = max(0, x)`, `lit = max(0, x·cos α + z·sin α)` and

`tide_school(t) = clamp(.7 + 1.1 · visible · lit, .5, 1.8)`.

A region on the far side or in shadow ebbs to 0.7. A region centred on the facing meridian under a full moon with a favourable lean surges near 1.77. A new moon dims all eight at once (a **hollow night**). The nod decides which hemisphere's four schools run hot for a fortnight. Only `sin`, `cos`, products, sums, `min` and `max` are used, never `pow`, so the C++ mirror reproduces it.

## Day and night hooks

`elongation_degrees = 360·f_synodic`; `moonrise_hour = 24·f_synodic` after sunrise (full moon rises at sunset, new moon with the sun); `illumination = (1 + cos α)/2`; `leaning` is `still` when `γ ≥ 0`, else `restless`. All are closed-form from `astrology.moon`, and `astrology.formulas` restates every expression above as text for consumers that do not read this document.

## Exports

- `astrology` (static, written at the Leylines stage): `version`, `calendar`, `moon` (`periods`, `offsets`, `tilt_max_degrees`, `great_year_days`, `hemispheres`, `regions`, ranges), `formulas`, `method`, `limits`. The limits line is also appended to `warnings`.
- `lunar_almanac` (refreshed whenever the reported year can change): `reported_year` (`settlements.founding.end_year`, else 0 with `reported_year_source: epoch`), `now` (day, phase fraction, elongation, illumination, moonrise hour, leaning, per-school tide), `months[12]` (the same for each month's first day plus `mean_tide` over its 30 days), `events` sorted by day then kind (`full_moon`, `new_moon`, `surge` with school and tide ≥ 1.6, `hollow_night` when every school ≤ 0.75, `still_ascendant`, `restless_ascendant`), and `next_grand_alignment_day` (the next day all three cycles restart together, or null). No per-day table is exported; consumers evaluate the formulas.
- `magic.networks[<school>].surged_strength = strength × tide_school(now.day)` and `magic.lunar_surge {day, factors}`: the leyline strengths visibly mutate in the published world while node and line intensities stay the base.
- Layer `lunar_sensitivity` in 0..1: `clamp(.2 + .5·Σ instability_school + .3·shore)` where shore is 1 on lakes and the coastal exposure elsewhere. Unstable ground and shores sway most.

Consumer formula for a field at time `t`: `ley_school(t) = ley_school × (1 + lunar_sensitivity × (tide_school(t) − 1))`.

## Controlling the moon from the API

The moon is an input, not only a seed:

- **Generation** (`POST /world/generate` overrides): `moon_variation` reseeds the moon independently of the world; `moon_synodic_days`, `moon_spin_days`, `moon_nod_days` and `moon_tilt_degrees` pin a cycle or the lean (zero means seeded; a pinned value must sit inside the seeded range, so the age boundary's structural checks still hold). Pinning one cycle never moves another: the draws happen in the same order and only the pinned value is replaced, with its offset folded into the new period. `astrology.moon.controls` records what was pinned. `lunar_influence` scales how far surges sway the age lottery.
- **Query** (`POST /world/moon`, `terrain_astrology.lunar_request`): stateless. Give `day` (real days since founding year 0) or `year`, `month`, `day_of_month` and `hour`; the answer carries phase, elongation, illumination, moonrise hour, leaning, per-school tide, the surged strength of every network, the year's events and the next grand alignment. It is the same closed form the almanac uses, so an orchestrator driving a clock stays consistent with the export.
- **Age API** (`POST /world/advance-age`): optional `moon_day` names the day the age turns for that request; otherwise the founding year decides. Recorded in `history.operations`.
- **Visitation API** (`POST /world/summon`): optional `day` names the arrival day (which also decides the hemisphere the Turning Moon brings).

Not controllable yet, and noted for later: a per-god festival calendar beyond the almanac feasts, and a runtime clock inside the Unreal plugin (the plugin receives the parameters and formulas; the game owns the clock).

## Temporary surges in the simulation

World option `lunar_influence` (default 0.5, range 0..1, group Moon). At each age transition the age day is `int(founding.end_year) × 360` from the founding report **before** the transition. At a city cell `f_school = 1 + lunar_influence × lunar_sensitivity × (tide_school(age_day) − 1)`, and the fate lottery reads potencies `ley_school × f_school` before dominance, ley pressure and the self-destruction weight. A surge at the wrong moment is what kills a city; the field itself is not rewritten, and the permanent 0.65–1.35 evolution of intensities is unchanged. `history.ages[].moon` records the day, phase, leaning and per-school tide; a school-cause ruin carries `evidence.moon_tide`. Standing threat assessments and wars use base potencies: the assessment is standing, the surge is momentary. `lunar_influence: 0` reproduces a world without lunar sway.

## Ruin legacies

Every ruin leaves a key point in one school, resolved in `terrain_ruins.ruin_legacy`:

1. **Source of destruction.** A school cause leaves that school; magical self-destruction leaves Weave; a nest family maps `infernal→infernal, undead→umbral, aberrant→weave, fey→weave, holy→radiant, unholy→infernal, draconic→fire, primordial→` the strongest of fire, water, earth, air at the ruin (ties keep school order), `fantastic→` none; a war leaves the victor's culture school; a divine cause leaves the god's school.
2. **Region.** The dominant school at the ruin (same threshold and margin as biome mutation) when the source has no magic of its own.
3. **Culture.** The ruined people's own school: maritime, cold, tidekin and frosthold water; desert fire; large-island air; rainforest, dwarf and hill dwarf earth; heartland radiant; elf and gnome weave.

Intensity follows city class (small 1.5, medium 2.5, capital 3.5); self-destruction keeps at least 2.5; a divine cause is 4. The node id is the ruin id plus `-key`; ruins export `legacy {school, intensity, basis}` and keep `new_node_school`. The tables are code constants mirrored in `Core/ages.cpp`; the civilization registry is their future home.

## Lab

The month select drives a Moon readout (illumination, moonrise hour, leaning, top school, that month's events, the great year). "Moonlit magic" scales the displayed `ley_*` and `magic_density` grids by the month's mean tide and `lunar_sensitivity`. Ruin cards name the legacy school and the surge in force when the city fell.

## Limits

Artistic astronomy: one body reduced to phase, rise hour, spin and lean. No altitude, no latitude dependence, no solar eclipses, no water tides. The age lottery samples one day per age. Legacy tables are constants, not registry fields. Previously exported worlds lack the contract and must be regenerated before age advancement or a visitation. No asset identities are added.
