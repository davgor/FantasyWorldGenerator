# 024 — A fallen villain's claim fades; the record does not

## Status

Accepted, 2026-09-20. Seed-visible: a world containing a fallen villain places
differently than it did when `FALLEN_CLAIM_INFLUENCE` was `1.0`.

## Context

Two decisions were taken separately and are individually right.

**Claims outlive their holder.** Ground a villain took stays taken, and the places that
grew around it do not become unremarkable because it died. `key_locations.villain_holdings`
drops a fallen villain's own seat position and keeps its claims, and `terrain_nomads` reads
the claim for the cultist gate. Neither filters on holder status.

**What `influence` actually reaches.** One consumer, `terrain_nomads.py:284`, which scales
the cultist gate's strength by `claim['claim'].get('influence', 1.)`. `key_locations`
consumes the *claim* — a fallen holder's ground still anchors placement — but it does not
read `influence` at all, so this decision does not change where key locations are put. An
earlier draft of this record said it did; that was wrong. The decay changes the cultist
gate, and the field is stamped on the claim so any future consumer inherits it without a
join.

**Retention is keep-everything.** A fallen villain stays in `villains.people` with
`status: 'fallen'` and a `fell_age`, and a durable mark is appended to `villains.fallen`.
Nothing is pruned, because a world that forgets what stood in it cannot be asked about its
own history.

The compound effect is not visible from either decision. With both in force and no decay,
every villain that ever rose steers placement and the cultist gate **forever, at full
strength**. The living cast's claims become a shrinking minority of the claims actually
governing the world, and placement stops reflecting who holds power and starts reflecting
who ever held it.

This is unbounded in *behaviour*, not in bytes. A memory ceiling does not fix it, and no
test that advances a single age can see it: it needs a span of many ages, which is exactly
what `TIME-ADVANCE` introduced. The hook was deliberately left in place when the fall pair
landed — `influence` was made a number rather than a boolean, set to `1.0`, with a comment
saying the value belonged to whoever settled the tick cadence.

## Decision

A fallen villain's claim decays. The record does not.

```
influence(n) = 0.6 * 0.6**n ,  zeroed below 0.05
n = ages since the holder fell

n          0     1     2     3     4     5
influence  .60   .36   .216  .130  .078  0
```

`terrain_villains.claim_influence` is the single definition. The value is stamped onto the
claim at the fall and restamped on every subsequent age transition, so consumers read it
off the claim and never join against the holder — which matters because `key_locations` is
a leaf package and cannot import `icarus_sim`.

Below the floor the value is exactly `0.`, not a small fraction, so a consumer scaling by
it stops being nudged rather than being nudged imperceptibly forever.

## Why these numbers

`FRAGMENT_SHARE = .35` already decays a *region's tier* when its villain falls, for the
same stated reason: a region's grip fades when its holder goes. Claim influence is the same
principle applied to the same event, so it is geometric and anchored to the fall rather
than to wall-clock or to the world's age count.

`0.6` rather than `0.35`: a claim should outlive its holder long enough to be the thing the
decision promises. At `0.35` a claim is under a tenth of its strength within two ages and
"ground stays taken" stops being true in any observable way. At `0.6` a claim still presses
meaningfully for three ages and is gone by six, which is the shape of a fading legacy rather
than an erasure or a monument.

An age is a century (`terrain_time_schedule.AGE_YEARS`), so six ages is roughly six hundred
years of simulated time. That is the horizon over which the world forgets who held a piece
of ground, and it is a deliberate figure rather than a fallout of the arithmetic.

## Alternatives rejected

**Leave it at 1.0.** The failure is real and only grows with the span a caller can now ask
for. Leaving it would have meant shipping a clock whose longest spans produce worlds
governed entirely by the dead.

**A horizon on the record — prune claims, or villains, past some age.** Rejected. It
contradicts the retention decision, and it destroys the history the fall pair was built to
keep. Fading influence and deleting the record are different things, and only one of them
was asked for.

**Decay per year rather than per age.** Rejected. A claim is stamped at an age boundary and
the fall is an age-boundary event; a per-year rule would need a day-stamp that worlds
generated before the clock do not carry, and `holder_fell_age` is present on every claim
that has one. Per-age decay works identically whether a world was advanced by ticks or by
age advances, which per-year decay would not.

**Filter fallen claims out entirely at the consumers.** Rejected as a re-litigation: it is
the "claims do not outlive the holder" answer, which was asked and answered the other way.

## Consequences

- A world with a fallen villain gates nomad cultists differently than it did before this
  change — that is the whole of the seed-visible surface today, because the cultist gate is
  `influence`'s only reader. Existing saved worlds are not migrated; they carry whatever
  `influence` was stamped when they were advanced, and the next age transition restamps them
  onto the new curve.
- `Core/` has no port of this. The native side does not implement villain falls, so there
  is no parity claim to break here and none to make.
- If the balance reads wrong in play, the knob is `FALLEN_CLAIM_INFLUENCE` and
  `CLAIM_DECAY_PER_AGE` together, and moving either is another seed-visible change.
