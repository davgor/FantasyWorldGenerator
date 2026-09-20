# BIOME-TUNDRA-SNOW-UNREACHABLE — moved to board/done/, closed 2026-09-20

Redirect notice, not a card. The ticket is closed and lives at
[board/done/BIOME-TUNDRA-SNOW-UNREACHABLE.md](../done/BIOME-TUNDRA-SNOW-UNREACHABLE.md).

The user ruled on 2026-09-20 (ruling 0.2) that biomes `1 tundra` and `6 snow` are tombstoned,
not deleted: the rows, their ids and their catalogue positions survive, the classifier keeps
emitting both labels, and only art commissioning stops. Forty-six production rows that named a
tombstoned id were re-pointed onto `15 boreal_forest`, `16 cold_tundra` and `17 land_ice`, which
between them had no production art at all before the change. The closed card carries the
evidence, the per-row justification, and a correction: the "zero survivors" proof the card was
filed with is wrong, and the tombstone rests on no world containing these labels rather than on
the classifier being unable to emit them.

This file exists only so that markdown links written while the card was open keep resolving;
`board/backlog/*.md` and `board/README.md` are both link-checked, so a bare move turns every
inbound reference into a hard error. Delete it once the last inbound link points at `board/done/`.
