# NOMAD-CORRUPTION-CONTRACT - an applier contract with no surviving author

## The problem

Cultist bands of a **hidden** school (blood, void, rot, eldritch) cannot write their own
leyline edits: `advance_age_request` rejects any edit whose school is outside
`KNOWN_SCHOOLS` (`terrain_history.py:677`). So they queue their intent into a generic
top-level `pending_ley_edits` block, which `terrain_corruption` is expected to drain.

**That applier contract was agreed with the super-villains session, which has since closed.**
It will never be confirmed by its author. This is the one part of the nomads work that
nobody currently working can verify.

## The contract as agreed

Recorded in the `terrain_nomad_effects` module docstring, and repeated here so it survives a
refactor of that file:

- entries carry `school`, `kind`, `id`, `intensity`, `requested_by`, `god_id`, `age`
- **endpoints by node id, never by index** - a node removed between write and apply
  renumbers every later edge, a bug that was found and fixed in `depart_god`
- hidden schools only; a known school is written directly by the nomad pass and must be
  rejected if it appears in the queue
- intensity bounded zero to four
- the applier sorts by `(school, id)` before applying, so two bands requesting in a
  different order cannot produce two different worlds
- ordering within a rebuild: villain and corruption edits first, then nomads, because
  cultists expand an influence that must already exist

## Current state

The nomad side is built and tested. `pending_ley_edits` is emitted **only when non-empty**,
so its presence means something is genuinely queued rather than being a buffer to interpret.
`tests/test_world_schema_conformance.py::test_nomad_write_backs_are_reported_rather_than_silent`
asserts that no known school appears in the queue and that intensities are in range.

**No applier has been observed draining it**, because no world in testing produced a
hidden-school cultist - the four hidden schools are locked at zero occurrence until a player
unlocks them.

## Next action

Confirm against `terrain_corruption` whether it implements this contract. If it does not,
either add the applier there or move it into the nomad pass - but decide, rather than leaving
a queue that nothing drains.
