# NOMAD-SURVIVOR-SETTLEMENT - adopt refugee camps as settlements

## Requested behavior

A survivor band that reached its refuge and stayed is exactly how a hamlet starts. Today
that is recorded in `settlement_candidates` and **nothing adopts it**, so a world can carry
candidate settlements indefinitely without one ever becoming real.

Each candidate already carries `node`, `direction`, `migration_source_node`,
`migration_distance_m`, `population_estimate` and a prose `reason` naming the ruin fled and
the refuge reached - deliberately the same fields `founding.py` uses, so a founding pass can
adopt them directly.

## Why it was not built

Founding a settlement at stage sixteen means re-running settlement generation after every
downstream block has already read the settlements it produced. That invalidates the world to
add one hamlet.

## Proposed mechanism

Adopt candidates at the **start** of the next age transition instead, where the tail rebuild
happens anyway. A band that survived an age boundary with its refuge still standing is also
a better filter than one that merely arrived.

## Dependencies

`terrain_history.rebuild_tail`. Should be designed alongside NOMAD-FISSION, since both
concern what happens to a band across an age boundary.
