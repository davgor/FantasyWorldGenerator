# VILLAIN-SCHOOL-DRIFT — `source_school` disagrees across Python and C++ for villain causes

Owner: none. State: **fixed in the working tree, pending a native build.** Picked up by the
bug-hunt session; see "Resolution" at the foot of this card. Found in passing, not written by
anyone who owns it.

Reported while moving `CULTURE_SCHOOL` off `terrain_ruins.py`; the heritage session does not own
`Core/legacy.cpp` behaviour and the session whose work would surface this (SUPER-VILLAINS) has
closed. It needs a picker-up, not a reviewer.

## Requested behavior

`Core/legacy.cpp` and `Sim/icarus_sim/terrain_ruins.py` should choose the same magic school for
a ruin caused by a villain. Today they agree only by accident.

## The defect

`terrain_ruins.source_school` takes six parameters and returns the villain's own school when the
cause names a villain — `terrain_ruins.py:34`:

```python
if cause.startswith('villain'):
    return villain_school
```

and `terrain_history.py:249` supplies it:

```python
villain_school=chosen[3].get('school')
```

The native port takes **five** — `Core/legacy.cpp:31`:

```cpp
std::string source_school(const std::string& cause,const std::array<double,school_count>& potency,
                          const std::string& nest_family,const std::string& victor_culture,const std::string& god_school)
```

It has no `villain_school` parameter and no villain branch, so a villain-caused ruin falls
through to the region's dominant magic and then to the ruined culture's own school, exactly as
an unmagical cause does.

**The two implementations therefore agree only when `villain_school` is `None`.** When a villain
holds a school, Python scars the ground with the villain's school and C++ scars it with the
region's. A ruin seeds a leyline key point, so the divergence does not stay local: it moves
`terrain_leyline_history`, then magic density and biome variants, then every magic-gated habitat
in later ages.

## Why the suite is green

Seed 42 evidently never produces a villain-caused ruin carrying a school, so
`tests/test_native_world.py:456` — which compares `legacy['school']`, `intensity` and `basis` on
the finished reference world — passes and always has. The parity coverage is real; the input that
would exercise this path simply never occurs at the reference seed.

That makes this a latent divergence rather than a live one, and it makes it the kind that
surfaces on someone else's change rather than on the change that caused it.

## Who will surface it

The SUPER-VILLAINS work, which seats villains that end cities in their own name, is the most
likely trigger — it exists to produce exactly the input this path mishandles. Whoever picks that
up should read this card first.

## Proposed mechanism

Add `villain_school` as a sixth parameter to the native `source_school` and give it the same
branch, ordered identically to the reference — after the `divine` branch and before `war_`.
`ruin_legacy` in `Core/legacy.hpp:21` forwards it, and both call sites in `Core/ages.cpp`
(`:148`, `:207`) pass the villain's school where the Python caller does.

Then add a native comparison that exercises a villain cause with a non-null school, rather than
relying on the reference world to happen to contain one. The existing seed-42 assertion is the
integration backstop, not the unit of proof.

## Dependencies and unresolved decisions

- `Core/ages.cpp` is concurrently edited; the signature change touches it.
- Needs a `Core/` build to verify, which is currently a held run.
- Open: whether the villain's school should outrank the region's at all, or only when the villain
  is the proximate cause. This card assumes the Python behaviour is the intended one, because it
  is the reference oracle — but that is an assumption, not a decision anyone recorded.

## Sources consulted

`Sim/icarus_sim/terrain_ruins.py:24-41`, `Sim/icarus_sim/terrain_history.py:249`,
`Core/legacy.cpp:12-45`, `Core/legacy.hpp:17`, `Core/ages.cpp:148,207`,
`tests/test_native_world.py:456`.

## Files and assets in scope

`Core/legacy.cpp`, `Core/legacy.hpp`, `Core/ages.cpp`, `tests/test_native_world.py`. No Python
change: the reference is correct.

## Acceptance and evidence

A native comparison with a villain cause and a non-null school agrees with the Python oracle, and
the seed-42 ruin assertions do not move.

## Documentation impact

None expected; this restores intended behaviour rather than changing it. If the open question
above is resolved the other way, `docs/` gains a note on precedence order.

## Adversarial review and limitations

The fix is mechanical, but the ordering is not: `source_school` is a precedence chain, and
inserting the villain branch in the wrong position changes results for causes that are both
villain-named and war-named, if any such cause exists. Check the cause vocabulary before
assuming the branches are disjoint.

## Handoff

Found while moving `CULTURE_SCHOOL` out of `terrain_ruins.py` onto the heritage layer — the two
tables sit three lines apart in `Core/legacy.cpp` and share a root cause: hand-copied constants
and hand-ported signatures with nothing asserting they still match. `CULTURE_SCHOOL` now has a
source-level guard in `tests/test_heritage_registry_binding.py`; this one has no guard at all yet.


## Resolution — bug-hunt session

Applied exactly the mechanism this card proposed, and confirmed its premise first by reading both
sides rather than trusting the report.

`Core/legacy.cpp` `source_school` takes `villain_school` as a sixth parameter and branches on it
**after** `divine` and **before** `war_`, matching `terrain_ruins.source_school`'s order. The
cause vocabulary was checked before assuming the branches are disjoint, as this card's adversarial
note asks: the only `villain`-prefixed causes are the four `villain_<growth>` strings built in
`terrain_villains.causes()` from `GROWTH_BY_PRESSURE` and `DEFAULT_GROWTH` — `devouring`,
`spreading`, `hoarding`, `usurping`. None of them is also war-named, so the insertion point is
safe.

`ruin_legacy` forwards it in `Core/legacy.hpp` and `Core/legacy.cpp`, and both call sites in
`Core/ages.cpp` (`:148`, `:207`) pass `std::string()` explicitly. **No default argument**, on
purpose: `god_school` is already carried the same way — always empty natively, spelled out at
every call — and a defaulted parameter would let a future villain-capable native age omit it
silently, which is the exact failure this card exists to close.

Native behavior is provably unchanged: `WorldConfig::villain_rise` is `0.` (`Core/config.hpp:35`)
and `Core/config.hpp:37-38` records that nothing can be seated natively, so no `villain`-prefixed
cause is reachable in `Core/ages.cpp` at all. The new branch cannot fire. That makes this a
signature and structure repair, not a world change — and it is why it could be done without a
generated world in the loop.

**Not done, and it is the half that matters for proof:** the native comparison this card asks for,
exercising a villain cause with a non-null school rather than relying on the reference world to
contain one. Left undone deliberately — writing it without being able to compile or run it would
be a test nobody has seen fail, which is the failure mode this repository already names.

### What still needs running

No C++ toolchain is reachable from this session, so the change is **unbuilt**. It needs
`python -m unittest tests.test_native_world` (which compiles via `tests/native_cxx.py` and MSVC
through `vswhere`). Expect it to be green: the edit is a signature change plus an unreachable
branch. A compile error here is a typo, not a design problem.

The seed-42 ruin assertions at `tests/test_native_world.py:456` must not move. If they do, the
change is wrong and should be reverted rather than accommodated.

### The open question this card raised, still open

Whether the villain's school should outrank the region's at all is **not** resolved. The fix
assumes the Python side is the intended behaviour because it is the reference oracle, exactly as
this card assumed. Nobody has recorded that decision, and this change does not record it either —
it makes the two implementations agree, which is a separate and smaller claim.
