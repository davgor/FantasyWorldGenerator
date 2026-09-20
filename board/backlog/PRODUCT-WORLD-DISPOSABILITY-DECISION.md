# PRODUCT-WORLD-DISPOSABILITY-DECISION — moved to board/done/, closed 2026-09-20

Redirect notice, not a card. The ticket is closed and lives at
[board/done/PRODUCT-WORLD-DISPOSABILITY-DECISION.md](../done/PRODUCT-WORLD-DISPOSABILITY-DECISION.md).

The user ruled on 2026-09-20 that generated worlds are disposable until the first
player-facing release. The record is
[023 World compatibility policy](../../docs/decisions/023-world-compatibility-policy.md).
Anything still sequenced behind "the disposability question" is unblocked.

This file exists only so that markdown links written while the card was open keep resolving,
and `board/backlog/*.md` and `board/README.md` are both checked, so a bare move turns
`tools/docs_check.py` red. Four live links point here — `BESTIARY-LAND-ICE-NO-ANIMALS.md`,
`BESTIARY-MONSTERS-BIOME-BLIND.md` and two lines of `board/README.md` — plus one in
`board/done/BIOME-TUNDRA-SNOW-UNREACHABLE.md`, which is frozen and unchecked.
`PERF-CITY-COUNT-TRACKS-RASTER.md` and `PRODUCT-RUNTIME-PARITY-LEDGER.md` mention the card
without linking it and both still call the question unruled, which is now false.

**Delete this file once those references have been retargeted at `../done/`.** It is a
redirect with no content of its own, and `board/backlog/` is not where a closed ticket belongs.
