# VILLAIN-SCHOOL-DRIFT — `source_school` disagrees across Python and C++ for villain causes

Owner: none. State: open, unowned. Found in passing, not written by anyone who owns it.

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
`ruin_legacy` in `Core/legacy.hpp:17` forwards it, and both call sites in `Core/ages.cpp`
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
