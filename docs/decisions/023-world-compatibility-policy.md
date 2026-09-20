# 023 — World compatibility policy: worlds are disposable

On 2026-09-20 the user ruled on the question raised by
[PRODUCT-WORLD-DISPOSABILITY-DECISION](../../board/done/PRODUCT-WORLD-DISPOSABILITY-DECISION.md):
**generated worlds are disposable.** That card found a policy applied everywhere and stated
nowhere — a regeneration requirement written into the contract documents once per subsystem
revision, each one individually defensible, with no owner and no record above them. This is the
record it asked for.

## Decision

**A generated world is a disposable artifact. Any change to the generator may invalidate every
saved world, and no migration is owed.**

A seed-breaking or save-invalidating change is therefore routine. It does not need its own
ruling, it does not need a migration path, and it does not need to be deferred to a quieter
release. It still needs its native `Core/` port in the same change, and it still needs its
regeneration statement in the document that owns the subsystem.

## The milestone at which this changes

This policy holds until the first release with a real player-facing consumer. That is **phase 2
of the product roadmap — the AI TTRPG text UI — and it is not ML-13.**

ML-13 is an engine-integration milestone. It has no player who has spent hours inside a world,
and tying the policy to it would buy compatibility for consumers that do not need it while
delaying it for the one that will. Phase 2 is the first point at which discarding a world
discards somebody's time rather than somebody's test fixture.

At phase 2 this record is superseded. Whoever opens that phase either writes the decision that
replaces this one, or owns world migration with a first slice scoped. **Shipping a player-facing
build while this record is still current is the failure this record exists to prevent.**

Note that the roadmap phase numbering is the product owner's and is recorded in the originating
card rather than in `PLAN.md`, whose table is organised by ML milestone. Anyone reconciling the
two should treat the card as the source for "phase 2".

## What a consumer may rely on today

- **A world replays deterministically from its exported `Config`, under the same generator.**
  That is stated in the canonical behavior contract, [terrain-world-layers](../terrain-world-layers.md):
  recipe 3 replays from its exported configuration, including world options. It is the whole
  guarantee.
- **Nothing across generators.** Not the seed, not the schema integers, not the set of blocks,
  not the ids inside a block. A seed names an input to one build of this code; it does not name a
  world.
- **Nothing about a persisted document surviving a round trip.** A world written by the CLI
  cannot currently be advanced at all — see
  [TIME-PERSISTED-WORLD-CANNOT-ADVANCE](../../board/backlog/TIME-PERSISTED-WORLD-CANNOT-ADVANCE.md).
  Disposability is not a licence to leave that broken. It is the reason it stayed invisible.

## The one compatible-change pattern this repository has found

An additive block that carries its own schema and leaves replay identical **does not force
regeneration.** The case is recorded on the contract page: key locations use their own schema and
catalogue revision, and the block "is additive and carries its own schema, so a consumer that
does not read it is unaffected and a world generated without it replays identically"
([the portable contracts page](../../Contracts/README.md), the world-envelope paragraph).

**Copy that shape.** The test is not "did I add a key" but "does a world generated without this
block still replay byte-identically" — which `key_locations` answered by running it: seed 42 with
and without the block gave byte-identical `layers`, `settlements`, `ruins` and `history`
([KEY-LOCATIONS](../../board/done/KEY-LOCATIONS.md), under Acceptance evidence). A block that
consumes an RNG stream, adds a draw or reorders an existing one is not additive, however cleanly
its output is separated.

This is a pattern to prefer, not a rule that is enforced. Enforcing it needs the block registry
[PRODUCT-BLOCK-REGISTRY](../../board/backlog/PRODUCT-BLOCK-REGISTRY.md) asks for. Describing it
is what a decision record can do.

## Where the regeneration statements live

So a future reader finds them without the grep. Counted at `7d94bf5`: **eighteen statements
across fifteen lines, in two documents.**

| document | lines carrying a statement | statements |
|---|---|---|
| `Contracts/README.md` | 2 | 4 |
| `docs/terrain-world-layers.md` | 13 | 14 |

In `Contracts/README.md` they are the world-envelope paragraph, which carries three on its own
(earlier worlds regenerated rather than advanced; algorithm-8/9/10/11 worlds and retired generic
human profile IDs; recipes 1/2 and old age/save contracts), and the Arctic registry paragraph,
which carries one. In `docs/terrain-world-layers.md` they are attached one per subsystem
revision, from the retirement of recipes 1 and 2 down through the algorithm-10 to algorithm-14
statements, with the registry-identity paragraph carrying two.

Reproduce the list with `grep -ni regenerat` over those two files. Four of the hits are not
requirements and are excluded from the count: the lab navigating without regeneration, its
display controls, its "Regenerate this seed" button, and the sentence about a configuration
regenerating through its own constructor.

**No line numbers are given here on purpose.** Both documents are edited whenever a subsystem
revises, and a line table inside the record written to stop people grepping is the first thing
that rots. The count and the grep reproduce; a line number does not.

**The originating card reported eleven, and its enumeration omitted five statements** of exactly
the same kind, and counted the registry-identity line as one where it carries two. The undercount
is itself an argument for this record: a policy discoverable only by grep gets miscounted by the
person who went looking for it on purpose.

All eighteen stay where they are. Each is true and each is local to the subsystem whose revision
caused it. What changes is that they now have a policy above them instead of being eighteen
independent surprises.

## Reason

A pre-release generator that breaks seed compatibility to fix a biome migration is making the
right trade, and the contract documents say so in as many words. The defect was never any one of
those statements; it was the aggregate. A policy with eighteen instances and zero statements is
indistinguishable from an oversight, and the cost lands on whoever first assumes the opposite.

The alternative — owning world migration now — buys compatibility for a set of consumers that is
currently empty, at the price of a migration path on every schema integer. That is months of work
to protect test fixtures.

## Consequences

- **This authorises nothing about data on disk.** Worlds under `Artifacts/` are evidence, not
  user data, and several are the only before-picture this repository has: the generator 9-to-16
  regression in island habitat and freshwater distance was visible only because a five-day-old
  world had not been cleaned up. *Disposable* means not owed a migration. It does not mean safe
  to delete.
- **Work that was blocked on this ruling is unblocked** — the land-ice weights, the monster biome
  tables and the city-count retune each named this question as their only blocker. Biome
  tombstoning never needed it and still does not; it was already decoupled by keeping the rows in
  place.
- **No behavior changes and none should.** A later revision of this record that quietly acquires
  a migration mechanism has replaced a policy with a project.
