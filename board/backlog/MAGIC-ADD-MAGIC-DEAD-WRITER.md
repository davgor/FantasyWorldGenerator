# MAGIC-ADD-MAGIC-DEAD-WRITER — delete it or leave it, but do not connect it

Owner: none. State: open, unowned. **This card's instruction is the opposite of what the code
looks like it needs.** Read the instruction before the evidence.

## The instruction

`terrain_magic.add_magic` is an unreachable second writer of the `magic` block. There are exactly
two safe actions:

- **delete** `add_magic` and its unused import, or
- **leave both alone.**

**Wiring it in is the single move that breaks worlds**, and it is precisely the move a tidiness
pass makes, because an imported-but-unused symbol reads as an oversight someone forgot to finish.
It is not an oversight. It is a dead writer whose deadness is load-bearing.

## Why connecting it breaks worlds

`add_magic` writes a **version 1** `magic` block. `generate_networks` in
`terrain_leyline_history.py` writes a **version 4** one, with `school_order`, the twelve-school
taxonomy and the four hidden schools.

Neither merges. **Each replaces the whole block.** So if `add_magic` were ever reached on a
generation path, whichever ran second would silently discard the other's entire block — and if
that were `add_magic`, the resulting world would carry a `magic` block with no `school_order`, no
twelve-school contract and no hidden schools. Every downstream reader of school order, every
biome variant keyed to a school index, and the corruption API's only route into a hidden school
all read that block.

The failure would be silent. Nothing raises; the block is simply a different, older shape.

## The reachability proof

Verified independently by this session with an AST walk over `Sim/`, `tools/` and both test
trees, matching call sites on both `func.id` and `func.attr`:

```
defs      : Sim/icarus_sim/terrain_magic.py:39
imports   : Sim/icarus_sim/terrain_leyline_history.py:10
CALLS     : NONE
as string : none      <- no getattr / dispatch-by-name route
attr refs : none      <- no module.add_magic reference
```

The last two lines are the part worth keeping. A call-site walk alone does not prove a Python
symbol is unreachable: a name reached through `getattr(module, 'add_magic')` or a
dispatch table keyed by string appears in neither `func.id` nor `func.attr`. There is no such
route here — `'add_magic'` occurs as a string constant nowhere in the tree — so the conclusion is
sound, but it is sound for a reason the walk itself does not establish.

Also checked outside Python, since the lab drives generation from the browser: no reference in any
`.html`, `.js`, `.json` or `.md` in the repository except
`docs/conformance/version-bindings.json`, which records the same suppression and states the same
caveat.

So `generate_networks` is the sole writer of `magic`, and the version-1 write at
`terrain_magic.py:74` is dead code.

## What this card is not

**Not an arbitration defect.** It was first reported as "two subsystems own `magic` with no
arbitration, and which one lands depends on the path taken". That framing is wrong and was
withdrawn by the session that raised it: there is no contest to arbitrate, because one of the two
writers is never invoked. A card that says "arbitrate the two writers" would send someone to make
them cooperate — which means connecting the dead one, which is the one forbidden move.

The distinction matters enough to state plainly: the same code, described two ways, yields
opposite instructions.

## Proposed mechanism

If deleting: remove `add_magic` from `terrain_magic.py` and its import from
`terrain_leyline_history.py:10`. Nothing else references either. This is a pure subtraction and
cannot move a world, because the code it removes never ran.

If leaving: add a comment at the `def` saying it is a superseded version-1 writer that must not be
reached, and why. **The comment is worth more than the deletion**, because the hazard is a future
reader's reasonable-looking fix, and deleting removes the evidence that the hazard was considered.

Either way, `docs/conformance/version-bindings.json` already carries the suppression note and
should be updated in the same change if the symbol goes.

## Dependencies and unresolved decisions

- Open: delete or annotate. Deleting is cleaner; annotating is safer against rediscovery. Whoever
  owns the magic block should choose — this card does not, because it is the kind of choice that
  looks obvious from outside and usually is not.
- If anything ever legitimately needs a second `magic` writer, this card is void and the two need
  real arbitration **before** that work starts, not after.

## Sources consulted

`Sim/icarus_sim/terrain_magic.py:39,74`, `Sim/icarus_sim/terrain_leyline_history.py:10`,
`docs/conformance/version-bindings.json:10`, plus an independent AST reachability walk across
`Sim/`, `tools/`, `tests/` and `Sim/tests/`.

## Files and assets in scope

`Sim/icarus_sim/terrain_magic.py`, `Sim/icarus_sim/terrain_leyline_history.py`,
`docs/conformance/version-bindings.json`.

## Acceptance and evidence

Either the symbol and its import are gone and `add_magic` appears nowhere in the repository, or
the `def` carries a comment a reader cannot miss saying not to connect it. In both cases the AST
walk above still reports zero call sites.

## Documentation impact

`docs/conformance/version-bindings.json` holds the shadow note today. If the symbol is deleted,
that note becomes a record of something that no longer exists and should say so rather than be
removed — the reasoning is the valuable part.

## Adversarial review and limitations

The reachability claim is as strong as static analysis gets in Python and no stronger. It rules
out call sites, attribute access, and dispatch by string literal. It does **not** rule out a name
assembled at runtime (`getattr(mod, 'add_' + 'magic')`) or an `exec`. No such construction exists
in this codebase and it would be bizarre if one did, but the proof is "no plausible route" rather
than "no possible route", and anyone acting on it should know which of the two they have.

Three sessions have now independently reached the same conclusion by the same method, which raises
confidence in the answer without raising it in the method.

## Handoff

Flagged to this session by both the conformance and coordinator sessions *before* it could be
carded as an arbitration bug — specifically because a session doing static review for dead and
inert code is the most likely one to reach for the tidy-up that breaks it. Re-verified here rather
than accepted, with the string-dispatch and non-Python routes added to the check.
