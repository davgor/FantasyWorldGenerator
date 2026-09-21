# 030 — Magnitude and identity conventions

## Status

Accepted 2026-09-21. **Numbered 030, not 024.** `PRODUCT-CONSUMER-VOCABULARY` asked for
`docs/decisions/024-magnitude-and-identity-conventions.md`; 024 was taken by
[Fallen claim decay](024-fallen-claim-decay.md) before this was written, and
`tools/docs_check.py`'s `check_numbering` is a hard error on a duplicate number because a
citation of "decision 024" would then be ambiguous.

Two conventions, C1 and C2. Both were agreed across several sessions on 2026-09-20 and
lived only in a scratch file under `AppData\Local\Temp`, pending an owner ruling. The
ruling for this sweep was *pick the more conservative option, implement it, and record the
rejected alternative so it can be reversed*. What was chosen and what was rejected is
written out under each convention below.

## Context

`tier` names four different quantities in this repository and `status` names six
vocabularies. Neither is a style complaint:

- Two of the four `tier`s are integers on overlapping ranges where one means danger
  (`beast_nests`, `wildlife`, `beast_movements`, 1–5) and one explicitly does not
  (`key_locations`, `key_location_plans`, 0–3, whose own description reads
  "PHYSICAL SCALE AND BUILD-OUT ONLY - never danger"). A consumer joining a creature to a
  key location on `tier` gets a plausible number and a wrong world, and is never told.
- A third is a float whose product with `REACH_SPACINGS_PER_TIER × settlement_spacing` is
  **metres** (`villains`), so it is a magnitude wearing the name of a rank.
- Ids renumber across an age boundary. Hamlet, fortress, plot, nest and culture ids are all
  rebuilt on an advance. `villains.schema.json` records what that cost once already: a tier
  ledger keyed to a culture id "silently resets and nothing can ever reach the band",
  because `humans.cultures` rebuilds its ids every age from whatever the roads happen to
  join.

The cost is paid by a reader, not by the generator, and it grows: roadmap phase 2 puts an
LLM in front of exported JSON, inferring meaning from field names. `tier` is the worst
possible field for that reader — four meanings, three of them numeric, and the wrong answer
is never an error.

## C1 — a magnitude field is named for its axis, and `tier` is retired for new fields

A field holding a magnitude is named for **what it measures**, not for the fact that it is
graded. `danger`, `build_out`, `standing`, `fame_band`, `reach_m` all say which question
they answer; `tier` says only that somebody ranked something.

Three parts, and the third is part of the convention rather than a caveat on it:

1. A new field that grades something is named for its axis.
2. `tier` is **retired for new fields**. A package that needs a graded quantity picks a name
   from its own domain.
3. **No shipped schema is renamed.** Every existing `tier` is in a published contract and
   several are in pinned tests and committed fixtures. The cost of the collision is
   confusion; the cost of the rename is every consumer, every fixture and every test that
   quotes a token.

Units belong in the name or in the description. `reach_m` is the pattern: the suffix carries
the unit, so no reader has to find the multiplication that turns a band into a distance.

**Chosen over — an enforced gate.** The stronger version of C1 fails the build when a new
schema declares a field named `tier`. It was rejected here as the less conservative option:
it is a change to `tools/`, it needs an exemption list for the five sites that legitimately
exist today, and an exemption list is the same maintenance burden as the convention with a
build break attached. **Reverse this by adding the check to `tools/docs_check.py` with the
five current sites listed as grandfathered**; the table in
[the consumer vocabulary](../consumer-vocabulary.md) is that list, already written.

## C2 — an id that crosses an age boundary keys to something the transition does not renumber

An identifier that must survive an age advance is derived from a thing the advance does not
rebuild — a terrain node, a city uid, the age it was created in — and never from a list
ordinal or from a culture id.

This is already the rule three packages arrived at independently, and each wrote it into its
own contract:

- `nomads.schema.json`: a band uid is "keyed to the terrain node, never to an ordinal or a
  culture id: those are renumbered by an age transition and a band has to survive one".
- `villains.schema.json`: a villain uid is `villain-<age>-<terrain node>`, "never to a
  settlement ordinal: hamlet, fortress, plot and nest ids are all renumbered on every age
  advance".
- `key-locations.schema.json`: ids are "derived from where the place is, never from where it
  landed in a list", and adds the clause that keeps this honest — **stable is not immortal.**
  A dangling key means the place is gone, not that something renumbered.

C2 records that as the rule rather than as three coincidences.

**Chosen over — a global identity registry.** The alternative was a world-level id table that
every block registers into, so an ordinal-keyed id could be translated across an advance.
Rejected: it makes every block depend on a new shared structure, it has to be written before
any of them can use it, and it would have to be right the first time. Deriving an id from
something stable costs nothing and each package can do it alone. **Reverse this by building
the registry**; C2's ids remain valid inputs to one.

## Consequences

- No code changes and no schema changes. Both conventions are forward-looking by
  construction, and C1 part 3 says so explicitly.
- The four live `tier`s and the six live `status` vocabularies stay exactly as they are. They
  are documented in [the consumer vocabulary](../consumer-vocabulary.md) instead, which is the
  half of `PRODUCT-CONSUMER-VOCABULARY` that a consumer actually reads.
- Neither convention is enforced by a gate, so both work exactly as long as people read them.
  That is the honest limitation, it is the reason each "chosen over" paragraph above names the
  reversal, and it is why the collision table is kept to collisions rather than grown into a
  general field glossary: a table that drifts becomes a fifth authority on `tier`.
