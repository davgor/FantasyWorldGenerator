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

## Documentation impact

`docs/npc-roster.md` (the limitations section states this gap explicitly and must be rewritten when it closes), the schema's `status` description (which currently says absence means gone), and a short decision record: a block that is no longer a pure function of the current world is a genuine contract change and deserves one.
