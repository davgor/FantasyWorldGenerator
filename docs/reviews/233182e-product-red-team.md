# Product red team — commit `233182e`

Persona: product. Reviewed 2026-09-20 against `233182e` ("next batch"), working tree clean.
Scope set by the coordinator session: **what a consumer actually receives versus what
`docs/conformance/` and `board/` claim it receives.** No product code was changed; nothing under
`Sim/`, `Core/`, `Contracts/` or `tools/` was written.

Verdict: **the generator has outrun its own contract.** Forty-eight top-level blocks are
published, ten are declared in the published envelope, eight have a schema of their own, and
thirty have neither. A document with an empty `config`, an empty `layers` and a four-key `recipe`
conforms to the published contract — no terrain grid, no settlements, no people — while the
product's own conformance test asserts that ten named sections must be present. Both are green in
the same file. Meanwhile the one place a consumer is told to look to find out what the product does
— `docs/conformance/` — contains one record describing four of one hundred and twenty-four modules,
and eight of that record's nine front-matter keys are read by nothing.

None of this is a bug. Every individual piece was built carefully and most of it is tested. The
product defect is that **the seam between producer and consumer is the only part of this
repository nobody owns**, and it is the seam the next three roadmap phases are made of.

---

## Placement warning — read before relying on this file

This document is at `docs/reviews/` because the coordinator session specified that path. One thing
is genuinely wrong with it and the coordinator should rule rather than inherit it:

**`docs/reviews/` did not exist in this repository before this file.** The local convention is an
`## Adversarial review and limitations` section inside the ticket — seven of the eight
`board/in-progress/` tickets carry one. `docs/reviews/<id>-*-red-team.md` is the *icarusUnreal*
convention. Importing it is a choice, not a formatting detail. Relocating this is a `git mv` plus
one index line, and I have written it to survive the move.

**A second concern was raised and is false; recording it because acting on it would have been
wrong.** The principal red team session reported that a document under `docs/reviews/` is invisible
to `tools/docs_check.py`, on the grounds that `ACTIVE_GLOBS` (`tools/docs_check.py:34`) lists
`docs/*.md` and that this is single-level. It is not. `matches()` (`tools/docs_check.py:73-75`) uses
`fnmatch.fnmatchcase`, where `*` matches `/` as happily as any other character, so `docs/*.md`
covers every markdown file at any depth under `docs/` — including `docs/catalogue/` today, and this
file. The empirical proof is that the first run of `docs_check.py` after this document was written
raised two CITE warnings **against this document**, at lines 155 and 156, which I then fixed. The
directory is covered, there is no relocation dodge, and `AGENTS.md`'s prohibition on widening a glob
is not being sidestepped by depth.

That correction belongs to the principal red team's gate-side write-up as much as to mine; I have
sent it to that session. It is a good illustration of this review's own subject, which is why it is
staying in the document rather than being quietly deleted: **a plausible reading of a glob was about
to become a recorded finding, and the thing that caught it was running the checker rather than
reasoning about it.**

---

## What I verified myself, and what I am relaying

Everything in **Findings** below was read in-tree at `233182e` by this session unless the line says
otherwise. I generated no world: the performance session has just measured size 17 at 70 s and
18.6 MB for 289 cells against recorded figures of 11 s / 30 MB at 16,641 cells, cost has stopped
tracking the raster, and nobody knows why yet. **No argument in this review rests on a published
performance figure, and none should until that resolves.**

Relayed, not verified by me, and marked at the point of use: the native suite's failure counts
(from `board/in-progress/SUPER-VILLAINS.md:170`, which is itself a first-hand report by the session
that ran it), and the `npc_roster`/`nomads` behavioural contracts in the coordinator's quest
handover dossier.

### The reference world has no terrain, and that qualifies every count below

Added after the review was written, following the user's ruling that 1025 is the correct grid
ceiling. The octave admission filter at `Sim/icarus_sim/terrain_tectonics.py:178` admits an octave
only while its `wavelength` still exceeds twice the grid step, and the grid step falls with size. I
recomputed it from the recipe-3 defaults (`globe_radius` 10000, `wavelength` 4300, `octaves` 5) and
then checked it against worlds already on disk. Both agree exactly:

| size | octaves admitted |
|---|---|
| 17 | **0 of 5** |
| 33 | 1 of 5 |
| 65 | 2 of 5 |
| 129 | 3 of 5 |
| 257 | 4 of 5 |
| 513 | **5 of 5** — first complete terrain |
| 1025 | 5 of 5 |

Thirteen world files under `Artifacts/` confirm it: every size-17 world carries
`resolved_octaves: 0`, every size-65 world carries 2, and **not one world in this repository has
more than two of its five octaves.** Meanwhile `Sim/icarus_sim/terrain_history.py:590` refuses age
advancement above size 257. Five octaves need 513. **A world could have all its terrain or all its
history, and never both** — which is what the ruling exists to fix.

The consequence for this review is direct and I would rather state it than have a reader find it:
**seed 42 at size 17, the world the conformance suite validates against, has no surface noise
whatsoever.** It is not merely the sparse end of the range, as Finding 6 originally put it — it is
the degenerate corner of the parameter space. Every capability this repository measures against that
world is measured on terrain that does not exist yet. That does not change Findings 1–5, which are
about contracts and documents rather than about generated content, but it sharpens Finding 6
considerably and it is the strongest available argument for the reachability reporting that finding
asks for.

Credit: the admission filter was solved by the session working the gamer lens and the arithmetic was
confirmed by the coordinator. I re-derived it here rather than relaying it.

**Anchors were re-verified after the findings were written.** Five `CITE` anchors went stale in this
tree within hours on 2026-09-19, and the principal red team warned that the performance and
time-advancement work is likely to move `terrain_history.py` again. Every line number cited below
was re-read at `233182e` after that warning: `terrain_history.py:398` still opens `STATE_KEYS`,
`terrain_nests.py:53` still holds the `1<=p['tier']<=5` guard, `terrain_villains.py:21` still
defines `REACH_SPACINGS_PER_TIER`, `:286` still writes `'fallen'`, and `docs_check.py:402` is still
the only `fm.get`. They will not stay true; **a reader acting on this review after the next wave
should re-check before quoting a line.**

---

## Finding 1 — the published world contract composes nothing

**Severity: blocking for any second consumer.**

`Sim/icarus_sim/terrain_history.py:406` defines `STATE_KEYS` with **47** top-level blocks.

| | count |
|---|---|
| top-level blocks published (`STATE_KEYS`) | 48 |
| declared in `Contracts/schemas/world-output.schema.json` | 10 |
| carrying a schema file of their own | 8 |
| **with neither an envelope declaration nor a schema** | **30** |

**The sharpest form of this is an internal contradiction, not an argument about coverage.**
`test_generated_world_exercises_every_versioned_section` asserts that a real world carries ten named
sections — `terrain`, `settlements`, `civilizations`, `city_plans`, `hamlet_plans`, `castle_plans`,
`world_scene`, `astrology`, `lunar_almanac`, `religion`. The published contract requires **none** of
them. The product's own conformance test and the contract its Unreal audience is told to build
against disagree about what a world is, in the same file, with both green. The test's docstring says
the quiet part — *"A conformance pass is only meaningful if the sections are actually present"* —
so the gap was known to whoever wrote it and closed in the test rather than in the contract.

The envelope declares seventeen properties in total, `required` is six
(`schema`, `schema_version`, `generator_version`, `config`, `layers`, `recipe`), and the root is
`additionalProperties: true`. One of those six has required contents of its own: `recipe` must carry
`version`, `seed`, `resolved` and `provenance`. `config` and `layers` declare no required keys at
all, so `{}` satisfies both.

So the minimal conforming world is this, and I validated it rather than inferring it:

```json
{"schema": "fantasy-world-generator.world", "schema_version": 2, "generator_version": 16,
 "config": {}, "layers": {}, "recipe": {"version": 3, "seed": 0, "resolved": {}, "provenance": {}}}
```

**That document has no terrain grid, no settlements, no people and no plans, and it conforms.** Not
"missing thirty-eight blocks" — missing everything, including the raster.

`tests/test_world_schema_conformance.py:34` validates a generated world against exactly that
document. The same suite then validates the eight reader-package blocks individually, each against
its own schema, each in its own test — which is real coverage, and is also the whole of it.

**Correction, recorded rather than quietly fixed.** The first version of this finding said a bare
six-key stub passes. It does not: `recipe`'s four required keys reject it, and I had reasoned from
the `required` list instead of validating a document. The SDET red team caught it and turned the
finding into three failing tests at `tests/test_world_schema_surface.py`. The corrected claim is
strictly worse for the product, which is the usual shape of these — but a reviewer who had tried my
original one-liner would have got a green and stopped reading. **This is the third time tonight that
reading an artifact beat reasoning about it, and the second time it was my error.**

So the repository has eight good contracts and no contract that says which contracts exist. A
consumer must learn out of band that `nomads` has a schema and `villains` does not, that
`key_locations` carries its own version and `wildlife` does not, and that a block's absence is
indistinguishable from a block that was never built.

**This corrects a statement in an existing card.** `board/backlog/VILLAINS-NO-SCHEMA.md` says of
the thirty-eight blocks undeclared by the envelope that "most of those have their own schema, which
is the intended arrangement." Eight of thirty-eight do. That card's own opening paragraph lists
exactly those eight and describes them correctly as *the blocks written by a separate reader
package*; the error is in generalising from them. The card's conclusion is unaffected and its
policy question — do core-emitted blocks get schemas, or do they live under the open root by
design? — is the right question. It is just a thirty-block question, not a six-block one.

The checker's own author already wrote the general form of this finding, at
`tools/docs_check.py:11-15`: *"verifying a block validates against its schema says nothing about
fields the schema never declared."* The gate knows. The contract still ships the gap.

→ `board/backlog/PRODUCT-BLOCK-REGISTRY.md`

---

## Finding 2 — worlds are disposable, and nobody owns that

**Severity: blocking for roadmap phases 2 and 3.**

Grepping the two canonical contract documents for regeneration requirements returns **eleven**
distinct statements. A sample, verbatim:

- `Contracts/README.md:12` — "earlier worlds must be regenerated rather than advanced";
  "Algorithm-8/9/10/11 worlds and retired generic human profile IDs require regeneration";
  "Recipes 1/2 and old age/save contracts are rejected and must be regenerated"
- `Contracts/README.md:22` — "Old worlds require regeneration."
- `docs/terrain-world-layers.md:24` — "Recipes 1 and 2 are retired and rejected: existing worlds
  must be regenerated. Seed compatibility with those recipes is intentionally broken"
- `docs/terrain-world-layers.md:142`, `:148`, `:190`, `:214`, `:216`, `:218`, `:234` — six more,
  each tied to a different schema or registry revision

Every one of these is individually defensible. A pre-release generator that breaks seed
compatibility to fix a biome migration is making the right trade. The product defect is the
aggregate and the silence around it:

**Searching `board/` for an owner of world or save migration, forward compatibility or backward
compatibility returns nothing.** Not an open ticket, not a deferred one, not a decision record
saying "deliberately not yet". `board/done/MIGRATION-CULTURES.md` is in-world population movement,
not save migration. The eleven statements are scattered across two documents as consequences of
other work; no document states the policy, and no ticket owns the consequence.

Why this is a product finding and not a shrug: the roadmap's phase 2 is an AI TTRPG text UI and
phase 3 is a 3D top-down game. Both imply a player, a campaign, and a world someone has invested
hours in. On current policy, **any generator change that moves any of a dozen version integers
destroys every existing world**, and the destruction is announced in a sentence inside a
paragraph about something else. The first time that happens to a player rather than to a test
fixture, it will not read as a careful pre-release trade.

I am not arguing for migration tooling now. Building it now would be wrong — the shapes are still
moving, and `VILLAINS-NO-SCHEMA` is right that freezing an unsettled shape is its own cost. I am
arguing that **"worlds are disposable until X" is a product decision that has never been made
out loud**, and that the absence is currently indistinguishable from an oversight. One decision
record costs an hour and converts eleven scattered consequences into one stated policy.

→ `board/backlog/PRODUCT-WORLD-DISPOSABILITY-DECISION.md`

---

## Finding 3 — a consumer cannot write one predicate for "is this thing dangerous" or "is this person alive"

**Severity: should-fix now, blocking once a second consumer exists.**

All four `tier` meanings verified in-tree:

| Site | Type | Meaning |
|---|---|---|
| `Sim/icarus_sim/terrain_nests.py:53` | int 1–5, raises outside the range | creature danger |
| `Sim/icarus_sim/terrain_villains.py:21,275` | float | standing — and `reach_m = tier * REACH_SPACINGS_PER_TIER * spacing`, so its product is **metres** |
| `Contracts/schemas/hero-generator.schema.json` | `string` enum | `notable` / `renowned` / `legendary` |
| `Sim/key_locations/__init__.py:58` | `int` 0–3 | physical build-out, and the docstring says **"never danger: read threat for that"** |

Two of these are integers on overlapping ranges where one means danger and the other explicitly
does not. One is a float that becomes a distance. One is a string. A consumer joining a creature to
a key location on `tier` gets a plausible number and a wrong world.

The living/dead axis is worse. A programmatic sweep of every `status` enum in `Contracts/schemas/`
finds **six vocabularies under one field name**: `ok`/`failed` at block level in five schemas;
`living`/`legend` for heroes; `alive`/`dead` for npcs; `complete`/`partial`/`unbuildable` for city,
hamlet and castle plan items; `complete`/`empty` for key-location plans; and `living`/`fallen` for
villains, **declared in no schema at all**.

Two consequences, both live:

1. **`complete` already appears in two of them**, meaning *this plan has contents* in one and *this
   item was fully placed* in the other. A consumer matching `status == 'complete'` across plan
   blocks is comparing two different questions, quietly.
2. **No single predicate answers "is this person still here."** The live token is `living`,
   **`alive`**, `living` — so `status == 'living'` is right twice and silently wrong once. The end
   token is `legend`, `dead`, `fallen`, and two of those three carry a judgement the other does not.

The proof it already bites is `Sim/npc_roster/__init__.py:190`, the only boundary crossing in the
repository, done by hand: `'alive' if person.get('status') == 'living' else 'dead'`. That expression
is the mapping between two published contracts, written once inside a private function and published
nowhere.

**Correction, recorded rather than deleted.** An earlier draft said an adapter matching the bare
string "reads a failed block as a living person." It cannot — block and person vocabularies are
disjoint. The SDET red team caught it and pinned the disjointness as a regression guard instead. The
honest finding is not that the confusion happens today but that **nothing prevents it, six
namespaces share one field name, and one pair has already collided.**

Worse, and relayed from SDET's `Sim/tests/test_villain_fall_reachability.py`: a villain's tier is
monotonically non-decreasing after seating, the fall test is `tier < hold`, and `villain_hold` is
declared `max 1.`, so a reign ends only above `1.0000000000000009` — empty by one epsilon, confirmed
across twenty swept runs with zero falls. **`villains.people[].status` can only ever hold `living`
in any buildable world, and its other value is declared in no contract.** A consumer writing
`if status == 'fallen'` is writing dead code that looks defensive and cannot discover that it is.

The coordinator's dossier proposes the fix as fleet conventions C1 (magnitude fields are named for
their axis; `tier` retired for new fields; no renames of shipped schemas) and C2 (an id crossing an
age boundary keys to something the transition does not renumber). **Both are correct and neither is
recorded anywhere a consumer can read.** They exist in a scratch file in another session's temp
directory, pending a user ruling. That is the finding: the conventions are already agreed and are
one power-cut from being lost.

→ `board/backlog/PRODUCT-CONSUMER-VOCABULARY.md`

---

## Finding 4 — a conformance record is a capability claim that almost nothing checks

**Severity: should-fix, and its cost grows nightly.**

`docs/conformance/` contains one record: `nomads.md`, plus `README.md`, `_template.md`,
`coverage.json` and `version-bindings.json`. `docs_check.py` reports "124 modules claimed or
declared"; that one record claims **four** of them. `coverage.json` lists **158** uncovered against
8 exempt, seeded 2026-09-19 and never re-seeded.

`docs/README.md` opens by telling the reader that conformance records are "the present-tense
breakdown of what this product does … Start there to learn what exists." `AGENTS.md` repeats it as
the first instruction of the repository. **Following that instruction today teaches a reader about
nomads.**

Of the nine front-matter keys a record carries, `tools/docs_check.py` reads exactly one. Line 402,
`fm.get('modules', [])`, is the only `fm.get` in the file. `record`, `tier`, `summary`, `emits`,
`versions`, `proof`, `decisions` and `tickets` are parsed for syntax at line ~354 and then never
read again. `versions:` looks enforced and is not — version checking runs off
`docs/conformance/version-bindings.json`, a separately hand-maintained file of fourteen bindings,
so a record's own `versions:` list can assert anything.

**The sharpened, falsifiable form, and I am taking it from the SDET session which is right:** as of
`233182e` no record tells a live lie. n = 1, and SDET checked both of `nomads.md`'s citations by
hand — `Contracts/schemas/nomads.schema.json` and `Sim/tests/test_terrain_nomads.py` both exist.
What SDET has *not* established, and I am not claiming, is that the proof test passes, that it
establishes what `establishes:` says, or that `tier: EXERCISED` is earned. Existence is not
exercise.

So the defect is not a false record. It is that **`proof:` is a load-bearing consumer-facing claim
with nothing behind it, on the night a dedicated session is adding records.** At n = 1 the fix is
an afternoon. At n = 30 it is an audit.

This is the claim side. The gate side — the mechanics by which a checker stays green while a record
is false — belongs to the principal red team session by agreement, and its first gate-side finding
is the relocation dodge quoted at the top of this document.

→ `board/backlog/PRODUCT-CONFORMANCE-PROOF-UNCHECKED.md`

---

## Finding 5 — the roadmap's runtime path is red and idle while the surface it must catch up to keeps growing

**Severity: blocking for ML-03, and it is getting worse without anyone deciding that it should.**

`PLAN.md` is explicit: "a rule is not advertised as runtime-supported until its native/core
implementation and plugin consumer conformance pass." The native path is the product; the Python
facade is, in `docs/unreal-integration.md`'s own words, "only an export/reference baseline."

Relayed from `board/in-progress/SUPER-VILLAINS.md:170`, a first-hand report by the session that ran
it and not verified by me: `tests/test_native_world.py` fails **89 / errors 4** at baseline, the
same 93 lines byte-for-byte with that session's work reverted, and the headline divergence is
`test_the_finished_world_matches_the_reference` asserting **`14 != 40`** cities — native produces
fourteen where the reference produces forty. Thirty-six of the failures are the stage 1–8 genesis
comparison.

Against that, `STATE_KEYS` went from 40 to 47 blocks in one evening (the dossier's §15; the
constant now holds 48). `heroes`, `story_web`, `npcs`, `key_locations`, `key_location_plans`,
`nomads`, `beast_movements`, `encounters`, `pending_ley_edits` and `settlement_candidates` are all
Python-side. `Core/*.cpp` mtimes are almost uniformly 2026-09-18, with one file touched on the
19th.

The product consequence is arithmetic, not judgement: **every block added to the Python reference
enlarges the parity debt that ML-03 exists to pay, and the debt is being added to faster than it is
being paid.** The board reads as a series of completions — NOMADS complete, KEY-LOCATIONS complete,
HERO-GUILD complete — and each of those is true of the reference layer and false of the runtime the
plan says is the product. Nothing on the board states the gap as a number or trends it.

I am not saying stop building Python. The reference layer is where the design gets found, and
finding it in C++ first would be a worse trade. I am saying the board currently lets a reader
conclude the product is nearly there, and the runtime that the roadmap defines as the product
produces fourteen cities out of forty.

→ `board/backlog/PRODUCT-RUNTIME-PARITY-LEDGER.md`

---

## Finding 6 — the catalogue advertises more than any world can show, and nothing measures the difference

**Severity: nit now; should-fix before any capability is marketed by number.**

- `board/backlog/BESTIARY-BRIMSTONE-BATS.md` — `brimstone-bats` clears every hard gate and then
  never reaches the 0.3 suitability floor on any cell, so it "can never be placed in any world."
  The card notes this was the shape of **seven of the seventeen** creatures added in one pass, and
  that it is silent: "the catalogue validates, the world generates, and the creature simply is not
  in it. Nothing raises."
- Relayed from the coordinator: 25 creatures are keyed to hidden schools locked at zero occurrence
  until a player exists.
- Relayed from the dossier: `nomads.groups[].legs` is empty; camps are start points only;
  `key_locations[].interior` is a chamber graph with no contents and no encounters.

Each is individually fine and most are individually ticketed. The product-level gap is that
**"authored" and "reachable" are different numbers and only the first one is ever reported.**
`key_locations` says 97 archetypes; seed 42 at size 17 yields 10 sites, size 33 yields 91 — and
the conformance world is the sparse end of the range, 47 land cells against 268. A reader of
`board/README.md` has no way to tell which of those numbers describes the product.

The good news is that the machinery already exists in one package and should be the pattern:
`key_locations` puts **every** archetype either in `sites` or in `diagnostics` with a reason, so
"this world has no lava tubes" is answerable rather than silent. Nothing else does that, and the
bestiary demonstrably needs it.

→ `board/backlog/PRODUCT-REACHABILITY-REPORT.md`

---

## Finding 7 — every world document advertises a grid range four times wider than any native consumer accepts

**Severity: blocking for the first external consumer.** Found by the principal red team session
while auditing the parity boundary and handed to me as consumer-contract rather than parity.
Verified independently in-tree here. That session has since filed
`board/backlog/PRINCIPAL-GRID-BOUND-PARITY.md`, which is the **primary** card — it carries the
history, the four-way disagreement, the blocked `validate_repo --stage repo-tests`, and the ruling
the user has to make. What follows is the consumer half only, and it is written to survive that
ruling either way.

Every generated world publishes its own parameter registry: `Sim/icarus_sim/terrain_world.py:279`
writes `'parameters': registry(version)` into `result['recipe']`, with a `provenance` map beside it.
That registry is the producer's statement of what it accepts, and it travels *inside the document
the consumer reads*.

It advertises `size` **3–1025** — `terrain_world.py:175` sets the bound, and `:274` enforces it
honestly: `raise ValueError('Grid maximum is 1025')`. The reference path really does serve it.

Every native consumer refuses above **257**:

- `Core/genesis.hpp:8` — `min_grid=3, max_grid=257`
- `Core/genesis.cpp:92` — `if(size<min_grid || size>max_grid) throw Error("STATE_CAPACITY");`
- `Unreal/.../FantasyWorldGeneratorSubsystem.cpp:237` — same constants, diagnostic
  `"regional raster size is outside the supported range"`

Both are 2ⁿ+1 grids, so the native side is **two doublings short** — sixteen times fewer cells at
the top of the advertised range. Nothing in `Contracts/` or `docs/unreal-integration.md` records
the divergence and **no version moves across it**, so a consumer comparing contract versions sees
agreement.

This is not the parity gap wearing a different hat. The parity gap is ML-03's and it is honest about
itself. This is the producer telling the consumer, in the document it hands over, that a request
will be accepted which the receiving path then refuses. `Contracts/capabilities-and-coordinates.md`
already has the right vocabulary for this — consumers "can require exact supported contract
versions", and native/editor/cooked capability requests are "explicitly rejected until those gates
pass." The capability descriptor knows how to say *not yet*. The parameter registry states one range
as though one producer existed.

The honest question underneath, which I have put in the card rather than answered: **is
`recipe.parameters` a contract at all?** It is undeclared by `world-output.schema.json`, it has no
schema, and it may have been lab UI metadata that merely got serialised. If so this finding shrinks
— but the remedy is then to say so, because a `min`/`max`/`provenance` structure inside a published
world reads as a contract to anyone who finds it, and Finding 1 is the reason nothing marks it
otherwise.

→ `board/backlog/PRODUCT-CAPABILITY-RANGE-DIVERGENCE.md`, after
`board/backlog/PRINCIPAL-GRID-BOUND-PARITY.md`

---

## Gate evasion check

- **Relocation is not a dodge — checked and refuted.** `docs/*.md` is an `fnmatch` pattern, not a
  single-level one, so depth under `docs/` changes nothing. See the placement warning above. I
  looked for this because it would have been the cheapest evasion available, and it is not there.
- **`proof:` costs nothing to satisfy.** A record can name any path; nothing opens it. The cheapest
  way to make a capability look exercised is to cite a test that exists.
- **`tier: EXERCISED` is self-assigned.** No check reads it. It is the single word a reader is most
  likely to trust and the one with the least behind it.
- **The uncovered allowlist is the honest part.** It may shrink and may not grow, a module created
  after the seed date fails on first sight, and adding to it requires a ticket. That ratchet is
  well designed and I found no way around it that does not also fail `COVERAGE`.

## What I did not attack

- **Correctness of any generator.** Not my lane; the code red team and the bug-hunt session have it.
- **Test honesty.** SDET's lane. One item handed to me is squarely theirs and I have left it:
  `board/backlog/VILLAIN-FALL-UNRECORDED.md:29` cites `Sim/tests/test_super_villains.py:52`, the
  anchor has drifted, and the coordinator reports the cited line asserts everyone is living and
  passes for the wrong reason. SDET is converting it into a failing test.
- **Performance.** Actively in dispute, owned by the performance session, and unsafe to build on.
- **Anything time-sensitive.** The time-advancement session is about to land two modules, five time
  bands, a liveness adapter and a deliberate output-changing claim decay. Findings 1, 3 and 4 are
  structural and should survive it; Finding 6's counts will not.

## Limitations of this review

This is a documents-and-emitters review. **I did not generate a world**, so every count above is a
count of what the code publishes and what the contracts declare, not of what a document contains.
If a block in `STATE_KEYS` is never actually emitted at stage 16, Finding 1's "30" is too high, and
the honest way to close that is one generated world diffed against the envelope — which the
performance situation currently makes expensive and which the coordinator has centralised.

The weakest finding here is 6, which reports an absence of measurement and is the kind of thing
that is cheap to say and easy to overvalue. The strongest is 2, and its strength is entirely in
the grep: eleven statements, zero owners.

Findings 1 and 4 both argue "a check exists and does less than a reader assumes." That is one
insight applied twice, and a reader entitled to discount it once should discount it twice.
