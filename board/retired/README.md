# Retired tickets

Cards here are **not done and will not be done as written.** Neither finished nor refused.
They arrive here for one of two reasons, and the distinction matters when you read one:
the premise they were scoped against no longer holds (the port cards), **or** the premise
still holds and reproduces but the owner took the card out of the backlog anyway (the four
held-by-ruling cards). A card of the second kind is still a true description of the tree.

They are kept for their scoping notes, their measurements and their adversarial notes, which
are often the only record of how something was established.

Nothing in this folder is a hold on anything. A card here must not be cited as a blocker,
a dependency, or evidence that a capability is incomplete.

## 2026-09-21 — four cards removed from the backlog by owner instruction

Four cards were taken out of `backlog/` by owner instruction on 2026-09-21. None was refused and
none was finished. Two were **already measured and already ruled on**, so completing them would have
overridden a ruling rather than cleared a ticket. The other two were **awaiting a decision that was
never given** — they left the backlog without their question being answered, and this folder does
not answer it for them.

- [BIOME-EXPOSED-ROCK-NEEDS-RELIEF](BIOME-EXPOSED-ROCK-NEEDS-RELIEF.md) — measured, ruled, deliberately not fixed.
- [BIOME-MARSH-IS-THE-RIVER-MASK](BIOME-MARSH-IS-THE-RIVER-MASK.md) — measured, never applied, and never ruled against; its own fix is headed “NOT to be applied without a ruling” and no ruling was made.
- [HERITAGE-GEOMETRY](HERITAGE-GEOMETRY.md) — was awaiting an owner decision and **still is**. It left the backlog; the question it asks was not answered, and nothing here records an answer.
- [MAGIC-ADD-MAGIC-DEAD-WRITER](MAGIC-ADD-MAGIC-DEAD-WRITER.md) — its own instruction is "delete it or leave it, but do not connect it." Leaving it is the resulting outcome. **“Do not connect it” remains a standing constraint** that outlives the card, because `docs/conformance/version-bindings.json` suppresses the second writer on exactly that unreachability.

Their measurements are good and are the only record of how several biome and trait facts were
established. Cite them for that. Do not cite them as blockers.

## 2026-09-21 — the native `Core/` port

Every *port* card in this folder was retired by one owner ruling: **the native port is
deferred wholesale to the end of the project and will be a full rewrite against
functionality that does not exist yet.** Each of these cards describes porting, mirroring
or measuring the tree as it stands, and that is not the tree that will be ported. The
ruling is recorded at
[027 The native port is deferred to a full redo](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md).

[NATIVE-PARITY-HARNESS-SHAPE](NATIVE-PARITY-HARNESS-SHAPE.md) joined them on 2026-09-21, later than
the rest and by correction rather than by plan: it was left in the backlog by mistake, because its
state line reads as bookkeeping and its residual turned out to be entirely native parity. Its one
non-native item, a stale asset registry, was already closed when checked.

If the port is scoped again, scope it fresh against whatever the Python reference is at
that time. Read these for what they noticed, not for what they instruct.
