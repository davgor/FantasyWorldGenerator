# PRODUCT-CAPABILITY-RANGE-DIVERGENCE — every world document advertises a grid range four times wider than any native consumer accepts

> **CLOSED 2026-09-21.** The premise was that every world document advertises a grid range wider than any native consumer accepts. The widen landed in `4713f9a` with `Core/genesis.hpp` at 1025, so the range stopped diverging; and with the native port deferred to a full redo ([027](../../docs/decisions/027-native-port-deferred-to-a-full-redo.md)) there is no native consumer to diverge from. The card's own “what survives the close” paragraph is not native and has been filed rather than lost: [PRODUCT-PARAMETER-PROVENANCE](../done/PRODUCT-PARAMETER-PROVENANCE.md).


Owner: performance session. State: **resolved in principle, awaiting the change that closes it.**
Found by the principal red team session and handed to the product red team as consumer-contract
rather than parity; verified independently in-tree at `233182e` by this session.

> **2026-09-20 ruling: the ceiling is 1025.** The Python reference path was right. The merge
> instruction recorded below resolves in that direction, so **this card closes into the widen**, not
> separately: the registry advertising 3–1025 becomes correct the moment the native side honours it.
> Per the coordinator, the performance session owns the Python widen at
> `Sim/icarus_sim/terrain_history.py:590` and the `Core/` port as **one change**, because a
> seed-changing Python edit without its native port recreates this same divergence pointing the
> other way. **Do not implement any part of this card separately.**
>
> Two 257s are deliberate and stay: the interactive lab limit at `tools/terrain_lab.py:99`, whose
> 1025-CLI / 257-interactive split is already stated in `docs/terrain-math-lab.md`, and the
> per-patch vertex bound. Two were flagged undecided and are not this card's to rule: the world-size
> test inside the patch path, and the tile schema.
>
> **What survives the close, and should be carried into the widen rather than lost with the card:**
> `recipe.parameters` is a single-producer statement published inside every generated world
> (`Sim/icarus_sim/terrain_world.py:340-345`: the guard that accepts `size`, then the
> publish of `recipe.parameters` four lines later). After the widen, `size` agrees — but nothing stops the
> next parameter from diverging the same way, and a consumer still has no way to tell which producer
> path a published bound describes. If the widen does not address that, it is worth one line in the
> handoff saying so deliberately.

**Read `board/backlog/PRINCIPAL-GRID-BOUND-PARITY.md` first — it is the primary card and this one is
deliberately narrower.** That card establishes the history (per it, `21df9aa` "checkpoint",
2026-09-19 22:32 widened the ceiling at the entry points), that the answer differs at four places,
that it blocks `validate_repo --stage repo-tests` for every concurrent session, and that **whether
the ceiling is 257 or 1025 is the user's call**. None of that is re-argued here and this card takes
no position on it.

## Requested behavior

**Whichever ceiling wins**, the parameter registry a consumer reads out of a generated world states
which producer path a bound applies to. A UE client that builds a request from `recipe.parameters`
is not refused by the subsystem that receives it.

This survives the ruling in either direction, which is why it is a separate card. If the ceiling
becomes 257 everywhere, `size` agrees and the general defect remains: `recipe.parameters` is a
single-producer statement published to a two-producer world, and `size` is merely the instance that
diverged loudly enough to be noticed. If the ceiling becomes 1025, native cannot serve it for some
time and the registry must say so rather than implying otherwise.

## The defect

Every generated world publishes its own parameter registry. `Sim/icarus_sim/terrain_world.py:345`
writes `'parameters': registry(version)` into `result['recipe']`, alongside a `provenance` map
naming each parameter as `override` or `default`. That registry is the consumer-facing statement of
what the producer accepts, and it is inside the document, not in a separate negotiation.

It advertises **`size` 3–1025**:

- `Sim/icarus_sim/terrain_world.py:187` — `bounds={... 'size':(3,1025) ...}`, written into each
  definition's `min`/`max` by the loop at `:203`.
- `Sim/icarus_sim/terrain_world.py:340` — `if type(raw['size']) is not int or raw['size']>1025:
  raise ValueError('Grid maximum is 1025')`. The reference path genuinely accepts it.

Every native consumer refuses above **257**:

- `Core/genesis.hpp:8` — `constexpr std::int64_t ... min_grid=3, max_grid=257`.
- `Core/genesis.cpp:92` — `if(size<min_grid || size>max_grid) throw Error("STATE_CAPACITY");`
- `Unreal/FantasyWorldGenerator/.../FantasyWorldGeneratorSubsystem.cpp:237` — gates on the same two
  constants and returns `"regional raster size is outside the supported range"`.

Both are 2ⁿ+1 grids; the reference accepts 2¹⁰+1 and the native path 2⁸+1, so **the native side is
two doublings short** — sixteen times fewer cells at the top of the advertised range. Nothing in
`Contracts/`, `docs/unreal-integration.md` or `docs/capabilities-and-coordinates.md` records the
divergence, and **no version moves across it**: a consumer comparing contract versions sees
agreement.

## Why this is a consumer-contract defect and not a parity bug

The parity gap is real and belongs to ML-03. This card is about a different thing: **the producer
tells the consumer, in the document it hands it, that a request will be accepted which the consumer
path then refuses.** A UE client reading `recipe.parameters.size.max` and offering a size slider up
to 1025 is doing exactly what the registry invites, and the failure surfaces as a runtime diagnostic
string rather than as a contract mismatch.

`Contracts/capabilities-and-coordinates.md` establishes the right pattern for this and it is not
being used here: consumers "can require exact supported contract versions", and "requests for
native, editor import or cooked runtime capabilities are explicitly rejected until those gates
pass." The capability descriptor knows how to say "not yet". The parameter registry has no such
vocabulary and states one range as if one producer existed.

## Proposed mechanism

Cheapest honest fix, and the one to do first: **the registry states which path a bound applies to.**

```json
"size": {"min": 3, "max": 1025, "native_max": 257,
         "note": "native and cooked consumers reject above native_max (STATE_CAPACITY)"}
```

A consumer negotiating for the native path reads `native_max`; the lab and the reference path keep
1025. Nothing is narrowed and no existing request breaks.

The alternative — clamp the registry to 257 — is worse in both directions: it removes a range the
reference genuinely serves and the lab genuinely uses, and it hides the gap instead of stating it.

Whichever is chosen, the divergence gets a sentence in `docs/unreal-integration.md` under the
current-boundary limitations, where a consumer author is already reading.

## Dependencies and unresolved decisions

- **Blocked on `PRINCIPAL-GRID-BOUND-PARITY`.** That card carries the ruling (257 or 1025), the
  four-way disagreement and the blocked `--stage repo-tests`. Sequence it first; this card is the
  follow-on that survives either ruling.
- **Merge instruction, symmetric — whoever closes these should not do the work twice.** Agreed
  between the two red-team sessions that filed them:
  - **If the ruling is 1025**, or if the fix otherwise labels the bound by producer path, close
    **this card** as absorbed into `PRINCIPAL-GRID-BOUND-PARITY`.
  - **If the ruling is 257**, that card shrinks to a mirroring exercise once the constants agree,
    and the durable half is this card's framing — `recipe.parameters` is a single-producer
    statement published into a two-producer world, and `size` was only the loudest instance. In
    that case close **that card** into this one.
  - Either way one card survives and it is the one carrying the general defect, not the one
    carrying the instance.
- **Does not belong to this card**: raising `max_grid`, deciding whether native should reach 1025,
  or fixing the failing tests. Those are ML-03's and the principal card's.
- **Open, and it is the principal red team's question rather than mine**: whether the divergence
  should have moved a contract version when it appeared.
- Interacts with `PRODUCT-BLOCK-REGISTRY`: `recipe.parameters` is itself an undeclared structure
  under the envelope's open root, so today there is nothing to validate a `native_max` field
  against either.

## Sources consulted

*Line numbers re-resolved against the live file on 2026-09-20; `terrain_world.py` is
under concurrent edit, so re-check before quoting them.*


`Sim/icarus_sim/terrain_world.py:169-212,340-351`; `Core/genesis.hpp:8`;
`Core/genesis.cpp:92`; `Unreal/FantasyWorldGenerator/Source/FantasyWorldGenerator/Private/FantasyWorldGeneratorSubsystem.cpp:230-241`;
`Contracts/capabilities-and-coordinates.md` (via `docs/unreal-integration.md` "Current boundary").
Relayed from the principal red team and **not** verified here: `tests/test_native_genesis.py:84`
failing `1025 != 257`, and the `{"size":258}` case in `Fixtures/unreal-frame-v1.json:21` no longer
raising but instead generating, still running at a 60 s cap.

## Files and assets in scope

`Sim/icarus_sim/terrain_world.py` registry construction; `docs/unreal-integration.md` limitations;
possibly `Contracts/capabilities-and-coordinates.md` if the descriptor is the better home than the
in-world registry. No `Core/` or Unreal change — the constants are correct for what they gate.

## Acceptance and evidence

A consumer can determine, from the world document alone, the largest `size` the native path will
accept. A test asserts the registry's native bound equals `Core/genesis.hpp`'s `max_grid`, so the
two cannot drift again silently — that assertion is the deliverable, not the JSON field.

## Documentation impact

`docs/unreal-integration.md` gains the limitation. If the bound moves into the capability
descriptor instead, `Contracts/capabilities-and-coordinates.md` gains it and the in-world registry
gains a pointer.

## Adversarial review and limitations

**The strongest objection: nobody has been bitten.** There is one native consumer, it is in-house,
and its author knows the constant. The answer is that the whole point of publishing a registry is to
serve a consumer who does *not* know — and the roadmap's phase 3 is exactly that consumer. A
contract that is only safe because its reader already knows the answer is not doing any work.

**The second objection, which has force: is `recipe.parameters` actually a contract?** It is
undeclared by `world-output.schema.json`, it has no schema, and it may have been intended as lab
UI metadata that merely happens to be serialised into the world. If that is its real status, then
this card is smaller — but the remedy is then to *say so*, because a `min`/`max`/`provenance`
structure inside a published world document reads as a contract to anyone who finds it, and nothing
marks it otherwise. Either way the current state is the one that misleads.

**Verification limits:** I did not run the native suite or generate a world. Every line above was
read in-tree at `233182e` and the anchors re-checked after a concurrent-edit warning. The two
test-level facts are marked relayed.

## Handoff

Found by the principal red team session while auditing the Python↔`Core/` parity boundary, and
handed over on the grounds that the consumer-facing half is a contract defect rather than a parity
one — correctly, in my view. That session keeps the parity boundary and the broken-test side. Both
halves should be read together. Full product context in
`docs/reviews/233182e-product-red-team.md`, Finding 7.
