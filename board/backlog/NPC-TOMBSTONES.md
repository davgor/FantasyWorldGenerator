# NPC-TOMBSTONES — Carry the roster's dead across an age advance

## Requested behavior

The `npcs` block must remember the people it used to hold. Today a person whose city is ruined by an age advance simply stops appearing: there is no tombstone, no cause, no record that they ever existed. A consumer holding a uid across the advance cannot tell "this person died" from "this person never existed" from "the producer renamed the key", and the only correct reading is that an absent uid means gone.

That was an accepted limitation when [NPC-ROSTER](../done/NPC-ROSTER.md) shipped, on the grounds that `status` is birth state and a runtime owns death in its own save. It is now load-bearing for a second package: the nomads work resolves a band's `refuge_uid` against `sites | ruins` precisely because a band's `basis` can outlive the roster records it points at. A quest anchored on "recover what he was carrying" needs the corpse addressable, which the quest work asked for explicitly and this block cannot currently provide.

## Proposed mechanism

`npc_roster.attach` reads the **incoming** `npcs` block as prior state before it is popped, diffs it against the new derivation, and carries forward every uid the new one no longer produces as `status: 'dead'` with a `died_age` and a typed `cause`.

The wiring detail that decides whether this works at all: `_attach_npcs` in `terrain_history.py` currently pops the previous block before calling `attach`, copied from `_attach_heroes`. It must read the prior block first, then pop, then attach — a verbatim copy of the cast's helper silently defeats the whole design.

Causes are derivable from what the world already exports: `site_ruined` when the site moved into `world['ruins']` (which retain `uid`, `name`, `city_class` and `civilization_id`), and `post_removed` when the site survives but the plot is gone. Add `carried: true` to a carried record, `prior_age` to the block so a consumer can tell a first derivation from a continued one, and `carried` / `vanished` counters to `summary`.

## Dependencies and unresolved decisions

- Determinism is preserved: a fresh generation from the same seed produces the same sequence of prior blocks, and `tools/validate_repo.py` generates a seed-42 size-17 world twice with no prior block on either, so the byte-compare gate is unaffected. Confirm this rather than assume it.
- `_validate` must **reject** a prior block whose `version` it does not understand rather than silently dropping the dead. Silently discarding a tombstone is the failure this ticket exists to prevent.
- Open: whether a carried record keeps its `important` earmark. A dead quest giver is still addressable as a corpse but must never be offered, so the earmark and the offer may need separating.
- Open: retention. Carrying every person who ever lived grows the block without bound across many ages; a horizon (drop after N ages, or keep only the earmarked dead) is probably wanted, and the choice should be authored in policy rather than hardcoded.
- Not in scope: runtime death. Nothing here kills anyone the world did not kill.

## Sources consulted

`Sim/npc_roster/**` and `docs/npc-roster.md` (the limitation as shipped), `Sim/icarus_sim/terrain_history.py` (the plan rebuild and the pop-before-attach trap in both attach helpers), the nomads card (`refuge_uid` against `sites | ruins`), and the quest work's request that a corpse stay addressable.

## Acceptance and evidence

- A two-age world whose city is ruined in the second age: its people are present with `status: 'dead'`, `cause: 'site_ruined'` and the correct `died_age`, and a uid held from the first age still resolves.
- A surviving post keeps its uid and stays alive across the advance; a removed plot marks its occupant dead rather than vanished.
- An unreadable or unversioned prior block fails loudly instead of dropping the dead.
- Replay stays byte-identical and `validate_repo`'s double-generate comparison still passes.
- The retention rule, whatever it becomes, is exercised by a test that runs enough ages to trigger it.

## Paired with VILLAIN-FALL-UNRECORDED — shape reconciliation

Added by the bug-hunt session. The coordinator asked for these two to be answered together, since
both ask the same question: what persists when someone stops existing. Reading them as a pair
produced two corrections, one to each card.

**This card's mechanism is right, and it is less of a change than it says it is.** The opening
claim — "there is no tombstone, no cause, no record that they ever existed" — is true for a person
whose site was ruined, and **not** true of the block in general. `npcs.people` already carries
records with `status: 'dead'` today: `Sim/npc_roster/__init__.py:190` writes
`'status': 'alive' if person.get('status') == 'living' else 'dead'` when it folds the cast in. So
the dead already live in this list, for one subset of people, with the field this card proposes.

That reframes the work. It is not "make the block stop being a pure function of the world" as a
new property — it is already not one, for heroes. It is extending an existing exception to the
people the block derives itself. The decision record this card asks for is still worth writing,
but it records a widening rather than a first crossing.

**The house shape is settled and neither card needed to invent it.** Three blocks already do this
the same way — one list, a status field, consumers filter:

- `hero_generator`: `status: living | legend`, enum-declared in `hero-generator.schema.json`.
- `npc_roster`: `status: alive | dead`, as above.
- `story_web`: `Sim/story_web/__init__.py:66` filters the cast on `status == 'living'`.

`VILLAIN-FALL-UNRECORDED` originally proposed a separate `fallen` key for villains. That is
**withdrawn** — it would have made a fourth shape for the same axis. Both cards now propose
in-list status, which is what `terrain_villains` already half-implements.

**One thing the pair should settle that neither card can settle alone:** the three blocks use
three vocabularies for one axis — `living|legend`, `alive|dead`, `living|fallen`. A consumer
joining two of them cannot write a single predicate for "is this person still here". Worth
routing as its own decision while both cards are open; it is a schema change on two published
contracts, so neither card should do it in passing.

**Retention is one answer, not two.** This card raises the unbounded-growth problem and suggests a
horizon authored in policy. The villain card inherits exactly the same problem. Whatever horizon
is chosen should apply to both, and be written once — two separately-chosen horizons for the same
question is how the vocabulary above happened.

**The wiring trap this card identifies is real and is not villain-specific.** `_attach_npcs` popping
before `attach` is the shape, but all four helpers do it — `_attach_heroes`, `_attach_story_web`,
`_attach_key_locations` and `_attach_key_location_plans` pop their block before calling. Any of
them that later needs prior state inherits the same defeat. Worth fixing as a pattern when the
first one genuinely needs it, rather than four times separately.

*(Unrelated correction found while reading the attach helpers: `_attach_npcs`'s docstring says "It
runs last because it reads `heroes`". It runs third of five, at both call sites. It does read
`heroes`, and heroes does run first, so the behaviour is correct and only the sentence is wrong.
Not worth its own card; fold it into whichever change touches this helper next.)*

## Documentation impact

`docs/npc-roster.md` (the limitations section states this gap explicitly and must be rewritten when it closes), the schema's `status` description (which currently says absence means gone), and a short decision record: a block that is no longer a pure function of the current world is a genuine contract change and deserves one.
