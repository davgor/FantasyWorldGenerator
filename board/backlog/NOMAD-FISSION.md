# NOMAD-FISSION - lineage fission for nomad bands

## Requested behavior

A wanderer clan that outgrows its range should split, and the child should inherit part of
the parent's ground rather than being placed fresh. `fission` is already a declared branch
kind in `Contracts/schemas/nomads.schema.json` and in `terrain_nomad_routes`, and
`parent_uid` already exists on every band. **Neither is ever populated**, so the vocabulary
promises something the generator does not do.

## Proposed mechanism

Segmentary lineage is the real mechanism: nested family, lineage, clan and tribe segments
split when population growth or conflict makes dividing the inherited range worthwhile, and
fuse again against an external threat. So the trigger should be a band's size against the
forage its round actually carries, not a flat probability.

A child band takes `parent_uid`, a share of the parent's camps, and a `fission` leg joining
the two rounds. Fusion - two bands merging under pressure - is the natural companion and is
not proposed here.

## Unresolved

Whether fission runs once at placement or at each age transition. Doing it per age makes a
clan's history legible but means band counts grow without a ceiling, and nothing currently
kills a band.

## Dependencies

None. Both the schema slot and the route builder already accommodate it.
