# VILLAIN-FALL-UNRECORDED — a villain's fall is written onto a record that is then discarded

Owner: none. State: **implemented in the working tree, pending a multi-age run.** Found and
closed by the bug-hunt session; see "Resolution" at the foot. SUPER-VILLAINS, which wrote it,
has closed.

## The defect

`terrain_villains.advance()`, at the unseating branch:

```python
villain['status'] = 'fallen'
villain['log'].append({'age': age, 'event': 'fell', 'concentration': round(pressed, 6)})
tiers[rid] = tier * FRAGMENT_SHARE
living.pop(rid)
```

`villain` **is** `living[rid]` — the same object, taken by `living.get(rid)` at the top of the
branch. The two lines that record the fall mutate it, and `living.pop(rid)` then drops it. The
block is written from `living` alone:

```python
block['people'] = [living[k] for k in sorted(living)]
```

So neither the `fallen` status nor the `fell` log entry ever reaches the world document. Both
writes are unobservable.

`status` is consequently a field that can only ever hold one value. `Sim/tests/test_super_villains.py:52`
asserts exactly that — `person['status'] == 'living'` for everyone in `people` — which is true,
and true for the wrong reason: not because the model keeps only living villains deliberately,
but because the record that would say otherwise is thrown away three lines after being written.

## Why this is a defect and not a design

The design *is* to drop them. `docs/super-villains.md:52` says the fall releases tier back to the
region and that the successor squabble is the tier fragment — the region persists, the person does
not. Nothing here argues with that.

The defect is that the code states an intent it does not carry out. Two lines read as "the record
is marked fallen and kept"; a reader who trusts them writes a consumer that looks for
`status == 'fallen'` and finds nothing, ever. That is the same failure `NPC-TOMBSTONES.md`
describes for people, and the same one the coordinator flagged for `_attach_npcs` popping before
`attach`: state written for a tombstone design that does not exist yet.

There is a real capability gap underneath it. A player who outlasts or kills a villain leaves a
world with **no trace it ever stood** — no name, no reign length, no held nodes, nothing the
story layer can refer back to. The wells it sank and the claims it made persist as orphans:
`well-villain-3-412` stays in the ley network with no record of who sank it, and
`claim-villain-3-412` stays on a villain record that no longer exists. `key_locations.core.world.villain_holdings`
reads claims off `villains.people`, so those claims stop influencing placement the age their
holder falls, while the well they reference stays in the world.

## Proposed mechanism

**Superseded.** This card originally offered two options — delete the dead writes, or keep fallen
villains under a separate `block['fallen']` key. The second was wrong and is withdrawn. Taking
this card as a pair with `NPC-TOMBSTONES.md`, as the coordinator asked, turned up a settled house
shape that neither card had looked for, and it decides the question.

### The shape is already decided, three times over

Every population block in this repository that has ever had to represent someone who stopped
existing uses **one list with a status field, and makes consumers filter**:

- `hero_generator` — `status: living | legend` in `heroes.people`, declared as an enum in
  `Contracts/schemas/hero-generator.schema.json`. `legend` is the remembered dead. Fifteen call
  sites inside the package filter on it explicitly.
- `npc_roster` — `status: alive | dead` in `npcs.people`. **`npcs.people` already contains dead
  records today**: `Sim/npc_roster/__init__.py:190` folds a hero into the roster as `dead` when
  the cast says they are not living.
- `story_web` — `Sim/story_web/__init__.py:66` reads the cast as
  `[p for p in ... if p.get('status') == 'living']`. The filter is the consumer's job and the
  packages already treat it that way.

So `NPC-TOMBSTONES` is not introducing a shape; it is extending one its own block already uses for
a subset of its people. And `terrain_villains` was **written for that shape** — `status: 'living'`
is set at seating and `status: 'fallen'` at the fall. The field exists, the vocabulary exists, and
only `living.pop(rid)` defeats it. The fix is to stop discarding the record, not to invent a
container for it.

### The mechanism

Keep the fallen villain in `block['people']` with `status: 'fallen'`, exactly as the code already
tries to. Add `fell_age` beside the existing `log` entry. Delete nothing.

`block['people'] = [living[k] for k in sorted(living)]` becomes a merge of the living and the
newly fallen, ordered so the sort stays stable and deterministic.

### What that costs, and it is the whole job

Eight production sites read `villains.people`. Under the current code every one of them is
reading a list that is living-only by construction. The moment a fallen villain stays in the
list, each is reading something different, so **each needs a decision in the same change**. This
is the part that makes it a real change rather than a two-line fix:

| Site | Today | Required |
|---|---|---|
| `terrain_villains.advance():153` | `living = {v['region']: dict(v) for v in block['people']}` | **Must filter.** Without it a fallen villain is reloaded as living next age — it resurrects. |
| `terrain_villains.outlook():240` | `seated = {v['region'] for v in block['people']}` | **Must filter.** Otherwise a fallen region reports `seated: true` and its `stalled` flag inverts. |
| `terrain_history.py:214` | `[v for v in ... if v.get('reach_m')]` | **Must filter.** `reach_m` is updated *before* the fall check, so a fallen villain keeps a live-looking reach and would feed `war_outlook`. |
| `terrain_history.py:381` → `build()` | filters `tier < SUPER_TIER` | Safe by coupling only — a fallen villain is below `hold` (.7) and so below `SUPER_TIER` (1.0). Filter at the call anyway; the safety is incidental, not stated. |
| `terrain_villains.causes()` | filters `tier < SUPER_TIER` | Same incidental safety. **This one is load-bearing for determinism**: a fallen villain that reached `city_fate`'s lottery would move worlds. |
| `terrain_corruption.py:138,159,161` | `watching` / `_host` | **Must filter.** A hidden god must not reach for a villain that no longer stands. |
| `terrain_nomads.py:191` | claims loop | **Decision, not a filter.** See below. |
| `key_locations/core/world.py:99` | `villain_holdings` | **Decision, not a filter.** See below. |

The last two are the open question this card already raised, now sharpened: a fallen villain's
claims currently vanish with it, silently. Filtering preserves today's behaviour exactly and is
the safe default; not filtering is a deliberate choice that held ground outlives its holder. Either
is defensible. Doing it by accident is not, and that is what happens if the merge lands without
touching them.

### One thing to fix while the pair is open

The three blocks use three vocabularies for one axis: `living|legend`, `alive|dead`,
`living|fallen`. A consumer joining two of them cannot write one predicate. This is the same class
as `VOCABULARY-VILLAIN-TWO-AXES.md` and worth settling while both cards are being answered — but
it is a schema change on two published contracts, so it is a **recommendation to route**, not
something either card should do on its way past.

## Dependencies and unresolved decisions

- The merge adds records to a block that has **no schema at all** (`VILLAINS-NO-SCHEMA.md`) and
  two live consumers. Sequence behind it, so the shape is described before it grows.
- `terrain_history.py` carries two of the eight required filters and is cycled by KEY-LOCATIONS.
  **The change is atomic or it is wrong**: landing the merge without those two filters moves
  worlds. Needs a claim through the coordinator before any of it starts.
- Open, and genuinely undecided: whether a fallen villain's `claims` should keep steering
  `key_locations` placement and the nomad cultist gate. Ground does not obviously forget when its
  holder dies — but the current code says it does, silently, and nobody chose that.
- Retention is open here exactly as it is in `NPC-TOMBSTONES.md`: carrying every villain that ever
  stood grows the block without bound across ages. Both cards should take the same answer, and it
  should be authored in policy rather than hardcoded in either.

## Sources consulted

`Sim/icarus_sim/terrain_villains.py:140-202`, `Sim/tests/test_super_villains.py:52`,
`docs/super-villains.md:43-52`, `Sim/key_locations/core/world.py:92-103`,
`Sim/icarus_sim/terrain_nomads.py:191-195`, `board/backlog/NPC-TOMBSTONES.md`.

## Files and assets in scope

`Sim/icarus_sim/terrain_villains.py`, `Sim/icarus_sim/terrain_history.py` (claimed — two filters), `Sim/icarus_sim/terrain_corruption.py`, `Sim/icarus_sim/terrain_nomads.py`, `Sim/key_locations/core/world.py`, `Sim/tests/test_super_villains.py`, `docs/super-villains.md`.

## Acceptance and evidence

Option 1: no dead write remains and the docstring says what happens. Option 2: a world advanced
past a villain's fall carries that villain in `fallen` with its final tier, `people` still
contains only the living, and the existing suite is unchanged.

Either way it needs an age advance far enough for a seated villain to drop below `villain_hold`,
which is **not** something seed 42 does at the default `villain_rise` of zero. That run request
belongs with the coordinator.

## Adversarial review and limitations

The claim that the writes are unobservable rests on `villain` and `living[rid]` being the same
object. They are: `living` is built with `{v['region']: dict(v) for v in block['people']}`, the
copy happens once at load, and `living.get(rid)` returns that copy rather than a second one.
Re-check this if anyone changes how `living` is built.

Not reviewed here: whether a region whose anchor is taken by a rival in `regions()`' dedupe can
strand a living villain that the loop never visits again — its tier would freeze and it would
never fall. That is a separate suspicion, not a finding, and it needs a multi-age run to confirm.

## Handoff

Found during a read-only review of the newest code in the tree, requested by the coordinator
because SUPER-VILLAINS closed leaving no verification requests. Two other cards came out of the
same pass: `CORRUPTION-LEGACY-BASIS.md` (fixed) and `VILLAINS-NO-SCHEMA.md`.


## Resolution — bug-hunt session

Implemented as the reconciled mechanism above, atomically across six files, with
`Sim/icarus_sim/terrain_history.py` claimed through the coordinator for the duration.

**Two decisions came from the user rather than being assumed:** a fallen villain's claims keep
steering placement and the cultist gate ("held ground outlives its holder"), and there is no
retention horizon. Both are recorded in `docs/super-villains.md` under "What a fall leaves
behind".

### What changed

- `terrain_villains.is_standing()` / `standing()` — the predicate. Absent status reads as
  standing, so records written before any of this still resolve.
- The fall now stamps `status`, `fell_age` and the log entry onto a record that is **kept**.
  `block['people']` is the living in their existing region-anchor order, then the fallen by
  `(fell_age, uid)` — so a world in which nobody has fallen serialises exactly as it did before.
- Seven consumers made explicit: `advance`, `outlook`, `causes`, `build`, two in
  `terrain_history`, and `_host`/`validate_corruption` in `terrain_corruption`.
- **`advance()` still returns the standing cast, not the block.** This mattered more than it
  looks: that return flows into `resolve_wars`, whose `_villain_pressure` reads `reach_m` with no
  status test of its own, and a fallen villain keeps the reach it had when it fell. Returning the
  block would have pressed cities together on behalf of someone who no longer stands.
- `terrain_nomads` and `key_locations.villain_holdings` are deliberately **not** filtered for
  claims. `villain_holdings` does drop a fallen villain's own seat position: the claim persists,
  the person does not stand there.

### The mark — the user's ruling, and the shape it changed

Mid-implementation the user ruled: *"lets make sure the villain has left their mark if they indeed
left a mark. Kinda like how we record folks who died in age transitions. In truth we should
probably have a good record of the dead, since the world has a finite population."*

That points at the **ruin pattern**, not the status-flag pattern, and the two are not the same
thing. A status flag says someone is not here. `terrain_history:363` says who they were, when they
ended, why, and what they left. So the retained roster entry stays — it is what keeps `people`
honest about who holds ground — and a second, durable record sits beside it:

`villains.fallen`, mirroring `ruins` beside `settlements.sites`. Each mark carries an id derived
from the uid, `fell_age`, `born_age`, `reigned_ages`, the parts of the reign worth carrying
(`school`, `growth`, `held_nodes`, `claims`, `well`, `god`, log) and a `left` block naming the
ruins it caused, claims it staked, well it sank and nodes it held. `tier` and `reach_m` are
deliberately **absent**: both describe a grip it no longer has.

`left.ruins` is read back out of `result['ruins']` by `evidence.villain_uid` rather than
accumulated on the villain — same reason the region is anchored to a ley node. Anything hung on a
live record is lost when that record is rebuilt; ruins are already durable and already carry the
attribution.

**"If they indeed left a mark" is honoured literally.** A villain that reached the band and caused
nothing gets no record at all — what it leaves is the decayed tier the land already keeps. A
monument for someone who did nothing makes the record of the dead less useful, not more.

**No `asset_id`, unlike a ruin, and this was a deliberate refusal.** A ruin stands on the ground
and needs a marker in the exhaustive asset list. A fallen villain's holdings are already placed:
its wells are ley nodes, its claims are claims. Giving the mark an asset would add an identity the
catalogue must carry with nothing standing at it — and would drag the asset registry and its
compiler into a change that has no business touching them.

**Retention is now settled by precedent rather than by argument.** `result['ruins']` is
initialised once and never pruned. "Keep everything" is not a new policy invented for the dead; it
is the one the world already runs for its dead cities. A finite population makes the dead a
knowable set rather than an unbounded stream — the argument for recording them properly, not
against.

### The influence hook

Raised by the time-advancement session while this was being written, and taken: over a long span,
unfiltered full-strength claims mean placement reflects who *ever* held power rather than who
holds it, and no memory ceiling fixes that.

So steering strength is a **number on the claim** — `influence`, with `holder_status` and
`holder_fell_age` beside it — rather than a boolean. `FALLEN_CLAIM_INFLUENCE` is `1.0`, which
makes retention the only behavioural change; `terrain_nomads` multiplies cultist strength by it,
and `key_locations` can read it off the claim without importing anything, which matters because
it is a leaf package.

**The decay value itself is not decided and this card did not decide it.** The argument for
decaying is the one `FRAGMENT_SHARE` already makes for tier. It belongs with whoever settles the
tick cadence.

### Three bugs found by writing the tests

All three mine, all caught within a minute of writing the assertion that exposed them:

1. `advance()` bound a local named `standing`, which made the module-level helper unreachable for
   the entire function — `UnboundLocalError` on the first call. Renamed to `seated_count`.
2. `turmoil()` bound the same name. Harmless today; a `TypeError` the day anyone calls
   `standing()` inside it. Renamed to `standing_threat`.

3. `reigned_ages` used `int(villain.get('born_age') or age)`. **Age 0 is falsy**, and the first
   age is exactly when a villain is most likely to have risen — so every villain seated at age 0
   reported a reign of zero ages however long it actually held. Replaced with an explicit `is
   None` test.

The first two are the same bug: a helper named for a state collides with locals named for that
state. The third is the ordinary falsy-zero trap, and it is worth noting that it lived in code
written specifically to record history accurately, which is where an off-by-a-reign is least
visible and least acceptable.

### Evidence

`Sim/tests/test_super_villains.FallTests` — **eight** tests, synthetic world, **0.001 s**. Built
synthetically on purpose: nothing at the default `villain_rise` of zero ever produces a fall, and
a generated world that does costs minutes, which is exactly why this survived.

They cover the fall being recorded, the fallen not rising again, exclusion from every standing
question including the fate lottery, the ordering guarantee for a world where nobody falls, the
claim carrying its holder state and influence, a marked villain's record and its absent `tier`,
`reach_m` and `asset_id`, a villain that marked nothing leaving no monument, and the record of the
dead surviving three further ages neither dropped nor duplicated.

`test_a_region_that_concentrates_enough_raises_one` was scoped to `standing()` — it asserted
everyone in `people` was `living` and passed for the wrong reason, which this card named as the
defect sitting on top of the defect.

### What still needs running

A **multi-age run at `villain_rise > 0`** deep enough to produce a real fall, plus
`test_super_villains`, `test_corruption`, `test_terrain_nomads` and `test_key_locations`. Nothing
here has been run beyond the five new tests and syntax checks. `docs_check` and
`verify_provenance` are green; none of the six files is provenance-pinned.

### Limitation

The synthetic world exercises `advance` directly. It does **not** prove the block survives an age
transition through `terrain_history`, where `STATE_KEYS` carries `villains` across — that needs
the real run. The retention decision was also made against the current age cadence, before the
time-advancement session existed; a tick that can cross fifty ages in one call may deserve a
different answer, and that session has been told the decision is open to challenge.
