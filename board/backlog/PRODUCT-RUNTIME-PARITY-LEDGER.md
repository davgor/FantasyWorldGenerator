# PRODUCT-RUNTIME-PARITY-LEDGER — the board reads as nearly done; the runtime the plan calls the product makes 14 cities out of 40

Owner: none. State: open, unowned. Found by the product red team auditing `233182e`. The native
failure numbers are **relayed**, not reproduced by this session — see limitations.

## Requested behavior

One number on the board, kept current: how much of the Python reference the native path reproduces.
Every "complete" claim states which layer it is complete in. A reader of `board/README.md` can tell
the difference between a capability the reference has and a capability the product has.

## The defect

`PLAN.md` is explicit: "a rule is not advertised as runtime-supported until its native/core
implementation and plugin consumer conformance pass." `docs/unreal-integration.md` opens by calling
the native kernel and thin Unreal plugin the long-term runtime boundary and the Python/JSON facade
"only an export/reference baseline."

**Relayed from `board/in-progress/SUPER-VILLAINS.md:170`**, a first-hand report by the session that
ran it: `tests/test_native_world.py` fails **89 / errors 4** at baseline; a scratch copy with that
session's six files reverted fails identically, 93 `FAIL:`/`ERROR:` lines byte-for-byte the same
set; thirty-six of the failures are `test_native_world_reproduces_the_reference_world_for_one_seed`,
the stage 1–8 genesis comparison; and the headline divergence is
`test_the_finished_world_matches_the_reference` asserting **`14 != 40`** cities — native producing
fourteen where the reference produces forty.

Against that, `Sim/icarus_sim/terrain_history.py:398` now holds **48** blocks, up from 40 at the
start of the previous evening. `heroes`, `story_web`, `npcs`, `key_locations`, `key_location_plans`,
`nomads`, `beast_movements`, `encounters`, `pending_ley_edits` and `settlement_candidates` are all
Python-side. `Core/*.cpp` modification times are almost uniformly 2026-09-18, with one file
(`Core/ages.cpp`) touched on the 19th.

The product consequence is arithmetic rather than judgement: **every block added to the Python
reference enlarges the parity debt that ML-03 exists to pay, and the debt is growing faster than it
is being paid.**

## Why it matters

`board/README.md` currently reads as a sequence of completions — HERO-GUILD complete, KEY-LOCATIONS
complete, NOMADS complete, ML-00/01/02 complete, ML-03a/b/c complete. Every one of those is true.
Every one of them is true *of the reference layer*, and `PLAN.md` says the reference layer is not
the product.

A reader — the user planning the next phase, a future session picking up the board cold, or the
downstream game team — cannot currently tell from the board that the runtime produces fourteen
cities where the reference produces forty. Nothing on the board states the gap as a number, and
nothing trends it. `board/README.md` mentions ML-03e and ML-03f as queued work; neither entry
carries the baseline's state.

This is not an argument to stop building Python. The reference layer is where the design gets found
and finding it in C++ first would be a worse trade — `ML-03d`'s existence and sequencing already say
so. It is an argument that **the board's vocabulary of "complete" has quietly detached from the
plan's definition of "supported"**, and that the detachment is invisible to anyone not holding both
documents at once.

## Proposed mechanism

Cheapest useful version, and the one to do first:

- A `## Native parity` line in `board/README.md` (the coordinator's file — hand it the line), stating
  the current native suite result and its date, and the headline divergence. Three sentences.
- A convention: a ticket that lands a new top-level block states, in its handoff, whether the block
  is reference-only. Most will be, and that is fine — the point is that the count is derivable.

Larger version, if it earns its cost later: a generated parity ledger — blocks in `STATE_KEYS` versus
blocks the native path emits — produced by the same run that produces the native suite result. That
is only worth building once the native suite is green enough for the number to move.

Explicitly **not** proposed: gating Python work on native parity. That would be the wrong trade and
this card should not be read as arguing for it.

## Dependencies and unresolved decisions

- **`board/README.md` is the coordinator's.** Four sessions wanted it on 2026-09-19. This card asks
  for a line to be handed over, not written directly.
- Unresolved, and above this card's pay grade: whether the native path is still the product. Core's
  mtimes say nothing has moved natively in two days while the reference gained eight blocks. If the
  answer is "native is deferred to phase 3", that is a legitimate and possibly correct decision — it
  is just not a recorded one, and it interacts directly with
  `PRODUCT-WORLD-DISPOSABILITY-DECISION`.
- The native baseline is escalated to the user and unresolved per the coordinator. This card should
  not pre-empt that resolution; it asks only that the state be visible while it is unresolved.

## Sources consulted

`PLAN.md` §"Independent ticket sequence" (ML-03 row and the paragraph after it);
`docs/unreal-integration.md:1-10,"Push to Unreal"`; `board/in-progress/SUPER-VILLAINS.md:108,170`
(relayed); `Sim/icarus_sim/terrain_history.py:398`; `Core/` modification times;
`board/README.md` (ML-03d/e/f paragraphs); `tests/test_native_world.py:461` (test exists at the
named line — its result was not reproduced here).

## Files and assets in scope

`board/README.md` gains a parity line, via the coordinator. `board/templates/task.md` may gain a
reference-only prompt in the handoff section. No code.

## Acceptance and evidence

A reader of `board/README.md` alone can state the current native parity position and its date. A new
top-level block landing without a reference-only statement in its handoff is visible as an omission.

## Documentation impact

`board/README.md`. Possibly one sentence in `docs/unreal-integration.md` pointing at where the
current state is recorded, since that document describes the boundary but not its health.

## Adversarial review and limitations

**I did not run the native suite.** Every failure number above is relayed from
`board/in-progress/SUPER-VILLAINS.md:170`. It is a careful first-hand report — it distinguishes
baseline from caused-by-this-work by reverting through asserted anchors and comparing the failure
sets byte-for-byte, which is better evidence than most — but it is one session's report at one
moment, and `tools/docs_check.py` currently emits a stale-CITE warning against a different citation
in that same ticket (`:190`). **Anyone acting on this card should re-run the suite first.** If the
numbers have moved, the card's shape survives and its figures do not.

**The strongest objection:** this is a reporting card, and reporting cards are how a board grows
ceremony. If the native baseline is about to be fixed, the line is obsolete before it is written.
The defence is that it has not moved in two days and is escalated and unresolved — but that is an
argument from a short window, and two days is not much.

**The second objection, which I think is right:** the real finding here may not be the missing
number at all, but the unrecorded decision underneath it — is native still the product? This card
reports a symptom of that and says so. If the user answers the underlying question, this card
shrinks to a line of bookkeeping, which is the outcome to hope for.

## Handoff

Found by reading `PLAN.md`'s definition of runtime-supported against `board/README.md`'s completion
language, then checking `Core/` mtimes and the `STATE_KEYS` growth on the same tree. Full reasoning
in `docs/reviews/233182e-product-red-team.md`, Finding 5 — note that document's own placement
warning.
