# 028 — An age is five thousand years, and a quest does not cross one

On 2026-09-21 the owner ruled on how long an age lasts and on what happens to the quest board
when one turns. The two are one ruling: a quest does not survive an age turn *because* an age
is five thousand years, and most of the people alive in one are not alive in the next.

## What was there before

`terrain_time_schedule.AGE_YEARS` was `100.`, and its own comment says plainly that the number
was invented rather than discovered:

> An age had no duration before this module. Ages were ordinal — `history.ages` is a list and
> the age lottery samples `int(founding.end_year) * 360` for its moon day — so nothing in the
> generator said how long one lasts. A tick cannot route a long span into an age advance
> without an answer, so this is that answer, and it is new contract rather than a discovered
> constant: an age is a century.

That was the honest thing to write and the wrong number. It was never checked against the
owner's model of the world, because at the time nothing in the tree could contradict it.

## Decision

**1. `AGE_YEARS = 5000.`** An age is five thousand years. `AGE_DAYS` follows at 1,800,000.

**2. The ley per-year bounds follow the constant, and that is why this was safe.** The binding
invariant is unchanged in words and changed in arithmetic: a year-step composed over one whole
age must land in the age transition's own `0.65..1.35` band, so the exponent is `1/5000` rather
than `1/100`.

**No code edit was needed to achieve that, and the reason is the useful part.**
`terrain_time.py` already reads `LEY_AGE_LOW ** (1. / schedule.AGE_YEARS)` — it asks the
constant rather than restating its consequence — so the exponent moved on its own. The literal
`0.65 ** 0.01` existed only in two documents, and prose cannot recompute itself. An earlier
draft of this decision implied a manual numeric edit; there was none, and the correction
matters more than the original claim. Had that exponent been written out as `0.01`, changing
the age length would have composed to `0.65 ** 50` ≈ 2e-10 over one age — the magic layer
draining to zero through ordinary ticking, silently, with every individual step inside its
stated bounds and no test failing. This is the rule the repository already applies to grid
ceilings, arriving somewhere new: ask the real predicate, never restate it as a local constant.

Measured after the change: **0.650000000000018** and **1.349999999999356** composed over one
age. Measured with the exponent forced back to `1/100` against the new age length, which is the
regression this guards: **4.4225e-10** and **3,286,157.88**.

**3. A century is a `LONG` tick, not an age advance.** `band(days)` returns `AGE` at
`AGE_DAYS`, so a hundred-year span used to rebuild every derived layer, regenerate the cast and
clear the quest board. Under this ruling that span is one fiftieth of an age and moves the
living layer only. `ages_for` divides by the new `AGE_DAYS`, so a five-thousand-year span is
one age advance rather than fifty.

**4. Every open quest is reaped at an age turn, and the board is rebuilt from the new age's
hooks.** There is no durable cross-age quest anchor and none is wanted. A quest belongs to the
people who offered and populate it, and after five thousand years they are gone.

## Why the quest half needs code rather than a note

Reaping already *mostly* happens, by accident, and the accident is the defect. `_quest_step`
walks hook ids; an age transition regenerates `heroes` wholesale, so most hook ids vanish and
their quests close as `hook_gone`. Measured 2026-09-21 with all 49 open quests taken and one
age advanced: **39 closed, 10 survived**.

The ten survive because the regenerated cast re-mints positional uids — `hero-reeve-hamlet-0`,
`hero-sovereign-<city uid>` — as the same string, so `by_hook.get(hook_id)` finds a *different*
hook wearing the old id. What continues is not the old quest and not the new one. A quest's
`anchor`, `verb` and `stated_purpose` are written once when it opens and never refreshed, while
`_target_present` runs against whatever hook now holds the id and `giver_uid` names a person
who no longer exists. The survivor carries the old age's prose, the new age's target check, and
a giver from neither.

So the fix is not "keep reaping"; it is to stop depending on id disappearance. An age turn
closes every open quest because the age turned, under its own reason, whether or not some id
happened to be minted twice.

## Consequences worth stating plainly

- **This is seed-visible and changes what every long span does.** A world ticked with the old
  constant and one ticked with the new one diverge. Under
  [023](023-world-compatibility-policy.md) worlds are disposable until the first player-facing
  release, so this is a regeneration and not a migration.
- **`MAX_AGES_PER_REQUEST = 50` now means 250,000 years rather than 5,000.** Whether that cap
  is still the right one is a separate question this decision does not answer; it is a cost
  guard, and the cost of an age advance has never been measured directly at any size.
- **`0.65 ** 0.01` appears as a literal in `docs/conformance/time-advance.md`.** The record's
  sentence stays true and its numbers do not. Both move together or the record is false with a
  green checker standing behind it.
- **Nothing native is owed.** Under [027](027-native-port-deferred-to-a-full-redo.md) the
  `Core/` port is a full rewrite at the end of the project.

## What this does not decide

- **Whether age length should be per-world.** It stays a module constant. Making it a control
  is a larger change and nobody has asked for different worlds to run different age lengths.
- **What `history.ages` should say about duration.** Ages remain ordinal in the generated
  record; this constant is the tick's answer to "how long", not a new field in the world.
- **Whether the age band's cost guard is correctly sized.** See above.
