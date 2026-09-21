# Time advance: the clock the world runs on

Once a world is live, it advances by elapsed time the caller names. Three seconds, thirty
years or five thousand — the request is the same shape and only the span differs. This is
the layer that makes the world keep living after the game begins.

## The calendar

Time is a real number of days since founding year 0, on the moon's calendar: 24-hour days,
30-day months, 12-month years, so 360 days to the year. That is the same scale
[the moon](astrology.md) already uses, so a tick and `POST /world/moon` cannot disagree
about what time it is.

**An age is 5,000 years.** Ages had no duration before this capability: `history.ages` is a
list, and the age lottery samples the founding year for its moon day, so nothing in the
generator said how long one lasts. A tick cannot route a long span into an age advance
without an answer. `terrain_time_schedule.AGE_YEARS` is that answer and it is new contract,
not a discovered constant — see
[028 An age is five thousand years](decisions/028-an-age-is-five-thousand-years.md), which
also rules that a quest does not cross one.

It is one number with two consequences, and both move with it. It decides what counts as a
tick: a century is 1/50th of an age and moves the living layer only. And the per-year ley
drift bounds are derived from it, so an age length changed on its own would drain the magic
layer through ordinary ticking — see **Leylines** below.

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
quests the player has played. `commit` is read by the age band and by the work ceiling:
it means *yes, I have seen the price and I will pay it*.

## Bands

The span selects a band. A band is a name for how big a span is and roughly what a span
that size touches — it is not a filter, and what actually runs is decided by which cadence
boundaries fall inside the window.

| Band | Span | What runs |
|---|---|---|
| `instant` | under a day | typically nothing but the clock and the lunar surge |
| `day` | a day to a season | quests, encounters, beast movements, nomad routes |
| `season` | a season to two years | the above, plus seasonal food, ley drift, nomad reclassification and its write-backs, villain outlook |
| `long` | two years to an age | the same cadences, over a longer span — a century is here |
| `age` | an age (5,000 years) or more | not a tick — see below |

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

## Five thousand years is one age advancement

A span of one age or longer is answered with an age advancement, not a tick, because that
is what it is. Five thousand years is exactly one of them. By default the call does not
advance anything: it returns the world unchanged with a report naming how many ages the
span is worth and what they would cost.

```json
{"band": "age", "ages": 1, "committed": false,
 "cost_estimate": {"ages": 1, "per_age_seconds": ..., "total_seconds": ...,
                   "peak_mb": ..., "measured": false,
                   "basis": "extrapolated by cell count from age advances timed directly ..."}}
```

The figures are computed from the world's own grid size, so no fixed numbers are quoted
here: a stated example would be a cost figure with no seed, size or machine attached, and
would be wrong for every world but one.

Send `commit: true` to actually advance. A caller asking for five thousand years has no
idea whether that is a second or an hour, and the estimate is how it finds out before
paying. `measured` says whether the figure came from this world's own recorded
`age_advance_total`, divided by the ages that call actually advanced, or from the
reference measurement below.

An age advance **has** now been timed directly — 34.3 to 39.4 seconds at size 17 and 181.8
seconds at size 33, seed 42 through phase 16, on a contended development machine, so upper
bounds. It used to extrapolate from *generation* cost recorded at size 129, which priced a
different pass from constants that had gone stale in both halves; the memory figure was
wrong by two orders of magnitude at the one size anybody generates. Nothing is measured
above size 33 and everything beyond it is a cell-count extrapolation.

A span is rarely a whole number of ages. The remainder is **ticked**, not dropped: 5,030
years is one age advance plus a thirty-year tick, and equals 5,000 years followed by 30. Any
`leyline_edits` and `resolutions` ride that remainder rather than being validated and
discarded — which means a resolution cannot name a quest of the age being left behind,
because the board the remainder sees belongs to the age that arrived.

**When the age boundary refuses.** `age_gate` calls `validate_age_world` and reports
whatever it refuses, in its own words, rather than restating its rules. An earlier version
hard-coded a grid ceiling of 257 and attributed it to that function — a ceiling that had
already been raised to 1025 and that the function never contained — so every world from 258
to 1025 was refused a span it would have advanced happily. Asking the real predicate is the
only form of this that cannot go stale again.

**A ceiling that is this module's own:** a request is capped at 50 ages, because each age
rebuilds every derived layer and an unbounded span is an unbounded loop. That refusal
carries the cost estimate, so a caller learns the size of what it asked for. Fifty ages is
now a quarter of a million years; whether that is still the right ceiling is an open
question decision 028 deliberately does not answer.

## The work ceiling, which is not about the age band at all

Every guard above lives in the age band, and decision 028 moved the boundary of that band
from a century to five thousand years. So the span a game actually drives — a decade, a
century, a millennium — fell on the side with no estimate, no gate and no refusal, however
long it was. `advance({'years': 4999})` is **1,804,646 cadence steps**, and it used to run
them without saying anything first.

A request that would execute more than `MAX_TICK_STEPS` steps **as a tick** is now reported
instead, with what it would cost, at any band:

```json
{"band": "long", "steps": 1804646, "elapsed_days": 1799640.0, "committed": false,
 "blocked": {"code": "STATE_CAPACITY", "field": "elapsed",
             "suggestion": {"kind": "clamp", "value": {"days": 199439.0}},
             "cost_estimate": {"steps": 1804646, "elapsed_years": 4999.0,
                               "total_seconds": ..., "peak_mb": ...}}}
```

`commit: true` runs it anyway, so nothing that worked before is now impossible — but a
caller that used to get a world back for a long span now gets a report unless it says so.
The suggestion is in **days** because days are what the request carries; clamping `elapsed`
to a step count, which the generic capacity refusal would have suggested, is not a request
this API can accept.

Only the steps a request will actually tick are counted. A span of whole ages is delegated
to `advance-age` and is not ticked, so only the remainder after those ages is priced, and
the question is asked before the first age turns — a span of ages plus an unaffordable
remainder is reported whole rather than advancing half of itself and then stopping.

The ceiling is an absolute count of steps and deliberately not a fraction of an age: how
much work a machine can afford does not change when the calendar is redefined. It also does
not scale with the world, and the estimate beside it does — a step costs about three times
as much on a size-33 world as on a size-17 one, so a large world is expensive at any span.
Steps are a proxy for cost rather than cost, because a coalesced pass runs once per call
however many crossings it had while the daily quest sweep runs every day.

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
   own `0.65..1.35` raised to `1/AGE_YEARS` — `1/5000`, so `0.65 ** 0.0002` ≈ 0.99991385 and
   `1.35 ** 0.0002` ≈ 1.00006002 — and an age of year-steps composes to the same band as one
   age step rather than applying an age-sized shock once a year. **The exponent is derived
   and must never be written as a literal.** The pair that composes correctly over a century
   composes to `0.65 ** 50`, about 2e-10, over an age: the magic layer drains to zero through
   ordinary ticking, silently, with every individual step inside its stated bounds.
3. `evaluate_networks` — the expensive globe pass — runs at most once per request, and only
   when the base field actually moved or a player edited it.

## Quests

The tick owns quest **lifecycle**; it does not own quest content and does not decide play.

`quests.quests[]` carries one entry per hook in `heroes.quest_hooks`, keyed on `hook_id`,
with the contract's `anchor` and `verb` taken from fields the hook already has — `verb` from
the hook's own field at `heroes` version 2, falling back to `actual_effect.action` for an
older world, where a ley quest has no verb to read. An offer
opens when the world first sees it and expires when its window passes, when its giver is no
longer present, or when its target is gone. Difficulty is **not** emitted here: that belongs
to the quest generator, and `heroes.quest_hooks[].difficulty` is where it is published.

**A quest does not cross an age.** Five thousand years pass, `heroes` is regenerated
wholesale, and the people who offered and populate an offer are gone, so an age turn closes
every quest still `offered` or `taken` with `closed_reason: 'age_turned'`, logs each
closure, retires the previous age's rows and rebuilds the board from the new age's hooks.
`quest_id` therefore names one age's offer: an id seen before and after a turn is two
different quests.

`age_turned` is not `hook_gone` and a consumer should not collapse them — one says this hook
left the block while the world stood, the other says the world moved on. The reaping used to
be the first standing in for the second, and it only mostly worked: the regenerated cast
re-mints positional uids such as `hero-reeve-hamlet-node-<n>` as the same string, so a quest whose
id was minted twice carried on with the old age's `anchor`, `verb` and `stated_purpose`
against a hook nobody wrote it for and a `giver_uid` naming nobody. The seven closing
reasons — `expired`, `giver_gone`, `target_gone`, `hook_gone`, `age_turned`, `resolved`,
`abandoned` — are published as an enum in `Contracts/schemas/read-quests.schema.json`.

`POST /world/advance-age` does not reap: it turns an age without a clock, so it has no day
to close a quest on. Only `advance-time`'s age band closes a board.

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

- A world persisted by the CLI has `timing_ms` stripped, and 32 producers across 18
  modules write into it unguarded. The key is made present where such a world *re-enters* —
  `terrain_history.adopt_world` for the six request APIs that take a caller's world through
  it, and `terrain_time`'s own `_timing` because it makes its own private copy. That is the
  contract rather than a mitigation, and guarding the 32 producers individually is
  deliberately not done. Verified 2026-09-21 across every `POST /world/*` route;
  `board/done/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md`.
- No native `Core/` port. A world advanced in Python and one advanced natively are not
  claimed to agree, because the native side has no time advance.
- Irruptive swarms answer to the clock as of 2026-09-21 — `board/done/NOMAD-IRRUPTION-TRIGGER.md`.
  One caveat that belongs to this module rather than to that one: a pass running inside the
  cadence loop sees `world_clock` as it was *before* the span, because the advanced clock is
  written after the loop. `beast_movements` is built for the year the span started in, so a
  multi-year advance is off by the span. Handing each cadence step its own day would close
  it.
- An age advance has been timed only at sizes 17 and 33 (34.3-39.4 s and 181.8 s, seed 42
  through phase 16, 2026-09-21, on a contended machine). Above that, an estimate for a world
  that has not advanced before is an extrapolation by cell count, and the memory figure is
  worse than the seconds figure: it takes its own smaller reference size because the larger
  reading came back visibly trimmed, and it over-states as it scales up. `cost_estimate`
  carries `basis` and `peak_mb_precision` saying exactly that.
- A quest's `taken` state is honoured here and written elsewhere: `POST /world/quest` takes
  and abandons offers, so a `state` can change with no elapsed time in between and a
  consumer caching a board between ticks is stale. See
  [actor-scale writes](conformance/actor-scale-writes.md).
- An age turn reaps the quest board, but only through `advance-time`. A caller that turns
  ages through `POST /world/advance-age` directly carries its board across unchanged.
