# Time advance: the clock the world runs on

Once a world is live, it advances by elapsed time the caller names. Three seconds, thirty
years or five thousand — the request is the same shape and only the span differs. This is
the layer that makes the world keep living after the game begins.

## The calendar

Time is a real number of days since founding year 0, on the moon's calendar: 24-hour days,
30-day months, 12-month years, so 360 days to the year. That is the same scale
[the moon](astrology.md) already uses, so a tick and `POST /world/moon` cannot disagree
about what time it is.

**An age is 100 years.** Ages had no duration before this capability: `history.ages` is a
list, and the age lottery samples the founding year for its moon day, so nothing in the
generator said how long one lasts. A tick cannot route a long span into an age advance
without an answer. `terrain_time_schedule.AGE_YEARS` is that answer and it is new contract,
not a discovered constant.

`world_clock` carries it: `{version, day, age, epoch_day, derived_from}`. A world generated
before the clock existed is read at its founding year, so adopting a clock does not move a
world's position in time.

## The API

`POST /world/advance-time`, or `terrain_time.advance_time_request(body)`. Time API **1**.
Stateless, like `advance-age` and `summon`: a world goes in, a new world comes out, and the
caller persists it. The caller's object is never modified.

```json
{"api_version": 1, "world": {...}, "elapsed": {"years": 30},
 "leyline_edits": [], "resolutions": [], "commit": false, "moon_day": null}
```

`elapsed` names exactly one of `seconds`, `days` or `years`. `leyline_edits` are the same
player edits `advance-age` accepts, applied before the span runs. `resolutions` closes
quests the player has played. `commit` is read only by the age band.

## Bands

The span selects a band. A band is a name for how big a span is and roughly what a span
that size touches — it is not a filter, and what actually runs is decided by which cadence
boundaries fall inside the window.

| Band | Span | What runs |
|---|---|---|
| `instant` | under a day | typically nothing but the clock and the lunar surge |
| `day` | a day to a season | quests, encounters, beast movements, nomad routes |
| `season` | a season to two years | the above, plus seasonal food, ley drift, nomad reclassification and its write-backs, villain outlook |
| `long` | two years to an age | the same cadences, over a longer span |
| `age` | an age or more | not a tick — see below |

**The band names the size of a span; it does not decide what may run.** What runs is
whatever cadence boundaries fall inside the window, and nothing else. The earlier design
filtered cadences by band, which silently and *permanently* dropped crossings when a span
was cut finer than its band: a game ticking a month at a time never ran ley drift, nomad
reclassification, seasonal food or the villain outlook once, and a game ticking by the
second advanced nothing but its clock. The window is half-open at the start, so nothing
skipped was ever revisited. A sub-day span usually runs nothing because it usually crosses
nothing — and when it does step over a day boundary, running that day's quest sweep is
correct rather than a violation.

Cadences fire on their own periods: quests daily, encounters and movements and routes
monthly, seasonal food each season, ley drift and nomads and villain outlook yearly.

A pass that **replaces its block wholesale** runs once per call, at its last crossing:
every earlier run would be overwritten by it, so a thirty-year span rebuilds the encounter
index once rather than three hundred and sixty times. Passes that **accumulate** — quests,
whose expiry carries forward, and ley drift, which compounds — run every step. The cadence
order is dependency order, producers before consumers, because `add_encounters` reads the
blocks `add_nomads` and `add_beast_movements` write.

## Five thousand years is an age advancement

A span of one age or longer is answered with an age advancement, not a tick, because that
is what it is. By default the call does not advance anything: it returns the world
unchanged with a report naming how many ages the span is worth and what they would cost.

```json
{"band": "age", "ages": 50, "committed": false,
 "cost_estimate": {"ages": 50, "per_age_seconds": ..., "total_seconds": ...,
                   "peak_mb": ..., "measured": false,
                   "basis": "extrapolated from generation cost ..."}}
```

The figures are computed from the world's own grid size, so no fixed numbers are quoted
here: a stated example would be a cost figure with no seed, size or machine attached, and
would be wrong for every world but one.

Send `commit: true` to actually advance. A caller asking for five thousand years has no
idea whether that is a second or an hour, and the estimate is how it finds out before
paying. `measured` says whether the figure came from this world's own recorded
`age_advance_total`, divided by the ages that call actually advanced, or from an
extrapolation of *generation* cost. An age advance has never been timed directly at any
size.

A span is rarely a whole number of ages. The remainder is **ticked**, not dropped: 150
years is one age advance plus a fifty-year tick, and equals 100 years followed by 50. Any
`leyline_edits` and `resolutions` ride that remainder rather than being validated and
discarded.

**When the age boundary refuses.** `age_gate` calls `validate_age_world` and reports
whatever it refuses, in its own words, rather than restating its rules. An earlier version
hard-coded a grid ceiling of 257 and attributed it to that function — a ceiling that had
already been raised to 1025 and that the function never contained — so every world from 258
to 1025 was refused a span it would have advanced happily. Asking the real predicate is the
only form of this that cannot go stale again.

**A ceiling that is this module's own:** a request is capped at 50 ages, because each age
rebuilds every derived layer and an unbounded span is an unbounded loop. That refusal
carries the cost estimate, so a caller learns the size of what it asked for.

## Refusals

Refusals raise `terrain_errors.RequestError` (a `ValueError` subclass), carrying the field,
the value received, what was expected and a suggested value, the same as the other request
boundaries.

The age band's refusals are the exception: they are returned in `time_advance.blocked`
rather than raised, because the cost estimate is the half of the answer worth having. They
carry the same envelope document — whatever `validate_age_world` refused, or this module's
own fifty-age cap — so a caller branches on the same fields either way.

## Determinism

**The RNG domain is keyed by simulated time, never by tick ordinal or call count.** Every
cadence fires on an absolute step index `floor(day / period)` measured from the epoch, and
a call executes exactly the indices in `(now, now + elapsed]` — half-open at the start,
closed at the end. No draw is made per call.

The consequence is the guarantee that matters: **the same span cut differently produces the
same world.** Thirty years in one call equals two calls of fifteen; a year equals four
seasons. `Sim/tests/test_time_advance.py` asserts it by byte comparison of the serialised
world, excluding wall-clock timings and the operation log — two calls honestly record two
operations.

Steps run in absolute-time order, ties broken by the pinned cadence order. Ordering by
subsystem instead would diverge the moment a call boundary landed inside it.

Replay is unchanged in shape: `Config` reproduces genesis, and `history.operations` records
every advance, edit and resolution since.

## Leylines

Three separate things, and conflating them is the classic error here:

1. `surged_strength` is a closed form of the day. Free, and recomputed on every call
   including the instant band. A hidden school takes no surge and carries no
   `surged_strength` key at all.
2. Base `intensity` drifts on a yearly cadence. The per-year bounds are the age transition's
   own `0.65..1.35` raised to `1/100`, so a century of year-steps composes to the same band
   as one age step rather than applying an age-sized shock a hundred times.
3. `evaluate_networks` — the expensive globe pass — runs at most once per request, and only
   when the base field actually moved or a player edited it.

## Quests

The tick owns quest **lifecycle**; it does not own quest content and does not decide play.

`quests.quests[]` carries one entry per hook in `heroes.quest_hooks`, keyed on `hook_id`,
with the contract's `anchor` and `verb` taken from fields the hook already has. An offer
opens when the world first sees it and expires when its window passes, when its giver is no
longer present, or when its target is gone. Difficulty is **not** emitted here: that belongs
to the quest generator.

Outcomes arrive from the game through `resolutions`:

```json
{"resolutions": [{"quest_id": "hook-...", "outcome": "completed"}]}
```

A completed hook whose declared effect is a ley change applies it, because the hook states
the school and the delta itself. Every other kind is recorded and nothing else — inventing
a world consequence the hook does not declare would be the world deciding what the player
did.

## Liveness

Four blocks answer "is this person still here" in three vocabularies: `heroes` and `dreads`
use `living`/`legend`, `npcs` uses `alive`/`dead`, `villains` uses `living`/`fallen`.
`terrain_liveness.liveness(record, block)` is one predicate over all of them. It is
read-only and migrates nothing; the per-package predicates stay authoritative and it
delegates to `terrain_villains.is_standing` rather than restating the villain rule.

Two things it exists to survive: a record with no `status` reads as **present**, because a
record written before its package recorded departure described someone who stood; and
dispatch is on the block a record came from, never on the shape of the record, because
`hero_generator` and `npc_roster` both write a block-level `status` of `ok`/`failed` under
the same key name as a person-level `living`/`legend`.

## What a tick may not touch

Terrain, water, climate, civilizations, settlements, roads, ruins, every plan, and the ley
*geometry* are read-only below the age band. The villain **cast** is read-only too: a
villain rises, holds or falls at an age boundary and nowhere else, because `advance` reads
the threat assessment an age inherited and raising one mid-tick would let a villain be
raised by its own damage. Only `villains.outlook` is refreshed.

Everything on that list may be rebuilt by the age band, which is an age advance and does not
pretend otherwise.

## Limitations

- A world persisted by the CLI has `timing_ms` stripped, and several passes write into it
  unguarded. `terrain_time` makes the key present before running anything so a persisted
  world can tick at all. That is a mitigation; the contract question is
  `board/backlog/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md`.
- No native `Core/` port. A world advanced in Python and one advanced natively are not
  claimed to agree, because the native side has no time advance.
- Irruptive swarms still appear in every year. The trigger they need now has a clock to
  hang on; see `board/backlog/NOMAD-IRRUPTION-TRIGGER.md`.
- An age advance has never been timed directly, at any size, so an estimate for a world
  that has not advanced before is extrapolated from generation cost.
- A quest's `taken` state is honoured if a caller writes it into the document it persists,
  but there is no request field that sets it: the API has no "the player accepted this"
  channel yet. Until there is, a game that wants an accepted quest to stop expiring must
  write `state: 'taken'` itself.
