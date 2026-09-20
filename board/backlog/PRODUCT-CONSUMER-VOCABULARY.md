# PRODUCT-CONSUMER-VOCABULARY — `tier` means four things, `status` means two at two depths, and the conventions that fix it live in a temp file

Owner: none. State: open, unowned. Found by the product red team auditing `233182e`; the collision
inventory is the coordinator session's and is cited rather than reproduced.

## Requested behavior

Two things, in this order:

1. **Record the fleet conventions.** C1 (magnitude fields are named for their axis; `tier` is
   retired for new fields; no renames of shipped schemas) and C2 (an id that crosses an age
   boundary keys to something the age transition does not renumber) exist, are agreed by several
   sessions, and are written down only in a scratch file in another session's temp directory,
   pending a user ruling. Move them into `docs/decisions/`.
2. **Publish a consumer vocabulary table** — one document naming every field whose name collides
   across blocks, what each instance means, its type, and which one a joining consumer wants.

## The defect

### `tier` — four live meanings, all verified in-tree at `233182e`

| Site | Type | Meaning |
|---|---|---|
| `Sim/icarus_sim/terrain_nests.py:53` | int 1–5, raises outside the range | creature danger |
| `Sim/icarus_sim/terrain_villains.py:21,275` | float | standing — `reach_m = tier * REACH_SPACINGS_PER_TIER * spacing`, so its product is **metres** |
| `Contracts/schemas/hero-generator.schema.json` | `string` enum | `notable` / `renowned` / `legendary` |
| `Sim/key_locations/__init__.py:58` | `int` 0–3 | physical build-out, and the docstring says **"never danger: read threat for that"** |

Two are integers on overlapping ranges where one means danger and the other explicitly does not.
One is a float that becomes a distance when multiplied. One is a string. A consumer joining a
creature to a key location on `tier` gets a plausible number and a wrong world, silently.

### `status` — one field name, six published vocabularies, and no single liveness predicate

Every `status` enum in `Contracts/schemas/`, swept programmatically:

| Vocabulary | Declared in |
|---|---|
| `ok` · `failed` | `hero-generator`, `npc-roster`, `story-web`, `key-locations`, `key-location-plans` (block level) |
| `living` · `legend` | `hero-generator` — `people[]`, `dreads[]` |
| `alive` · `dead` | `npc-roster` — `people[]` |
| `complete` · `partial` · `unbuildable` | `world-output` — city, hamlet and castle plan items |
| `complete` · `empty` | `key-location-plans` |
| `living` · `fallen` | **villains — declared in no schema at all** |

**The defect is not value confusion between a block and a person.** An earlier draft of this card
said an adapter matching the bare string "reads a failed block as a living person". It cannot: the
person and block vocabularies are disjoint, so a value match is safe there today. That claim was
wrong and is corrected here rather than deleted, because a reviewer who tried it would have got a
green and stopped reading.

**The defect is that one field name carries six namespaces and nothing keeps them apart.** Two
concrete consequences, both live:

1. **`complete` already appears in two different `status` vocabularies.** `key-location-plans`
   uses it for *this plan has contents* (against `empty`); the three plan sections of
   `world-output` use it for *this item was fully placed* (against `partial` / `unbuildable`). A
   consumer matching `status == 'complete'` across plan blocks is comparing two different
   questions. This is the one place where value-matching is already unsafe, and it is unsafe
   quietly.
2. **A consumer cannot write one predicate for "is this person still here."** The live token is
   `living` for heroes, **`alive`** for npcs, `living` for villains — so `status == 'living'` is
   right twice and silently wrong once. The end token is `legend`, `dead`, `fallen`: three words,
   three blocks, and `legend` and `fallen` carry a judgement `dead` does not, so a consumer cannot
   even map them without first deciding what a legend is.

**The evidence that this already bites is in the tree.** `Sim/npc_roster/__init__.py:190` is the
only place in the repository that crosses the boundary, and it does it by hand:
`'alive' if person.get('status') == 'living' else 'dead'`. That expression *is* the mapping between
two published contracts. It is written once, inside a private function, and published nowhere. Every
downstream consumer has to rediscover it.

### `villains.people[].status` can only ever hold one value

Relayed from the SDET red team, which stands behind it and has it under test at
`Sim/tests/test_villain_fall_reachability.py` (6 tests, 1 control passing, 5 failing):

Seating requires `tier >= SUPER_TIER` (1.0). After seating, the only writes to the tier ledger add a
product of two non-negative factors, at three writer sites, all inside `advance()` — so tier is
monotonically non-decreasing. The fall test is `tier < hold`, and `villain_hold` is declared
`min 0., max 1.`, so a fall requires `hold > 1.0`. Bisected against a villain seated at exactly 1.0,
the weakest the model can produce: **a reign ends only above `villain_hold` = 1.0000000000000009.**
The reachable set is empty by one epsilon. Swept across the declared range crossed with
`villain_rise` 0 → max, 25 quiet ages each: twenty runs, zero falls, tier monotone in all twenty.

So `villains.people[].status` is a field that **can only ever hold `living`** in any world that can
be built, and its other value is declared in no contract. `Sim/icarus_sim/terrain_villains.py:286`
writes `'fallen'` and nothing can reach it. A consumer writing `if status == 'fallen'` is writing
dead code that looks defensive — **and it cannot discover that**, because there is no villains
schema to tell it the value exists and no world that will ever show it one. That is the intersection
of this card with `VILLAINS-NO-SCHEMA` and it is worse than either alone.

### The rest, relayed from the coordinator's collision inventory

`camps` three ways (ruin squatters, static · nomad waypoints, mobile · a quest `clear_camp` kind);
`culture` two ways (`terrain_humans.culture_groups` is a road-connectivity grouping of cities whose
docstring says the ids are "not inferred ethnicities", against heritage's per-civilization
ethnography); ids that renumber across ages, where the cast builds `hero-castellan-fortress-36` on
the ordinal fortress id while `npc_roster` keys the same place by terrain node — two keys that read
alike in different number spaces.

## Why it matters more than a naming complaint

The repository's answer to "what does a consumer join on" is currently *read four packages*. That is
affordable for one consumer written by the people who built the producers. It is not affordable for
roadmap phase 2, where the consumer is an LLM reading exported JSON and inferring meaning from field
names. **`tier` is the worst possible field for that reader**: four meanings, all plausible, three
of them numeric, and the wrong answer is never an error.

## Proposed mechanism

- `docs/decisions/024-magnitude-and-identity-conventions.md` — C1 and C2 as stated, with the reason
  each was proposed (C1 because `tier` already has four live meanings; C2 because three sessions hit
  id renumbering independently and `humans.cultures` rebuilding its ids every age already caused one
  silent accumulation reset). **No renames of shipped schemas** is part of the convention, not a
  caveat on it.
- `docs/consumer-vocabulary.md` — the collision table, at `docs/` top level so `docs_check.py`'s
  `docs/*.md` glob actually covers it. One row per colliding name, one column for "which one you
  want if you are joining", and the `status`-at-two-depths trap called out explicitly because it is
  the one that fails silently rather than loudly.
- Cross-reference from `Contracts/README.md`, which is where a consumer starts.

Deliberately **not** proposed: renaming any shipped field. Every one of these is in a published
schema and several are in pinned tests. The cost of the collision is confusion; the cost of the
rename is every consumer and every fixture.

## Dependencies and unresolved decisions

- **C1 and C2 are pending a user ruling** per the coordinator. This card cannot close before that
  ruling and should not pre-empt it; it asks for them to be recorded once ruled.
- Whether the vocabulary table lives in `docs/` or in `Contracts/` is a real question — it is a
  consumer document, and `Contracts/` is what a consumer is pointed at. `docs/` is proposed only
  because `docs_check.py` covers it and `Contracts/*.md` is not in `ACTIVE_GLOBS`. Whoever takes
  this should check that rather than trusting it.
- Interacts with `PRODUCT-BLOCK-REGISTRY`: the registry is where a per-block field glossary would
  eventually hang.

## Sources consulted

`Sim/icarus_sim/terrain_nests.py:53-54,96-100`; `Sim/icarus_sim/terrain_villains.py:21,173,275,282,286`;
`Sim/key_locations/__init__.py:58`; `Sim/npc_roster/__init__.py:190` (the only boundary crossing);
a programmatic sweep of every `status` enum across all fourteen files in `Contracts/schemas/`,
which is how the six vocabularies and the `complete` overlap were found; the coordinator session's
quest handover dossier §4 and §1 (collision inventory and conventions C1/C2, relayed);
`board/backlog/VILLAINS-NO-SCHEMA.md`, which reaches the `tier`-as-metres finding independently.

Relayed from the SDET red team and under test there rather than verified here: the villain fall
reachability argument and its twenty-run sweep (`Sim/tests/test_villain_fall_reachability.py`), and
the disjointness guard (`tests/test_status_vocabulary.py`).

## Files and assets in scope

New `docs/decisions/024-magnitude-and-identity-conventions.md`; new `docs/consumer-vocabulary.md`;
pointer lines in `Contracts/README.md` and `docs/README.md`. No schema and no code changes.

## Acceptance and evidence

A consumer author can answer "which `tier` is this and can I compare it to that one" from one table.
The `status` two-depth trap is stated in the document that a consumer reads, not only in the schema
that encodes it. `docs_check.py` passes, including the decision numbering check
(`tools/docs_check.py:268`) and the decision-index link check (`:257`).

## Documentation impact

Entirely documentation, which is also the risk — see below.

## Adversarial review and limitations

**The honest objection: a table is not a fix.** Nothing about writing `docs/consumer-vocabulary.md`
stops the next package from adding a fifth `tier`. Only C1 does that, and C1 is a convention with no
enforcement, so it works exactly as long as people read it. A stronger version of this card would
add a check — for instance, failing when a new schema declares a field named `tier` — and that is
worth considering, but it is a gate change and belongs to whoever owns `tools/`.

**The second objection: the collisions are already known.** They are — by the coordinator, by
`VILLAINS-NO-SCHEMA`, and by several sessions that hit them independently tonight. That is the
argument for the card rather than against it. The knowledge is distributed across ephemeral
sessions and one temp file; **the sessions end and the file is in `AppData\Local\Temp`.**

**Where this card is weakest:** it proposes two new documents in a repository whose stated problem
is that its documents outrun their checks. If the vocabulary table is written and then drifts, it
becomes a fifth authority on `tier`. Mitigation is to keep it to the collision table only — not a
general field glossary — so that it changes only when a collision is added or removed.

## Handoff

`tier` and `status` were verified in-tree by this session at `233182e`; `camps`, `culture` and the
id-renumbering cases are relayed from the coordinator's dossier and are marked as such above. Full
reasoning in `docs/reviews/233182e-product-red-team.md`, Finding 3 — note that document's own
placement warning.
