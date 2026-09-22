# Porting notes: the substrate a reimplementation has to reproduce

[Decision 027](decisions/027-native-port-deferred-to-a-full-redo.md) rules that `Core/` is a
prototype, is not a parity target, and will be **rewritten from scratch** at the end of the
project. It also says the Python records "remain the acceptance spec for whoever scopes the
port."

This document exists because of a gap in that arrangement. A large part of what a porter needs
is not in `Sim/` and not in `docs/conformance/` — it is in comments inside `Core/`, the tree
027 says will be deleted. `Core/pyrandom.hpp`, `Core/pyrandom.cpp`, `Core/globe.hpp` and
`Core/castleplanner.cpp` carry knowledge that was expensive to acquire and is recorded nowhere
else. When `Core/` goes, that knowledge goes with it unless it lives here.

Everything below is a property of **CPython**, not of this repository's algorithms. None of it
is visible by reading `Sim/` alone, and all of it is load-bearing: determinism, seed replay and
byte reproducibility are binding invariants under `AGENTS.md`.

Measured against the tree at `4e65893`, 2026-09-21, on CPython 3.12.10.

## 1. The interpreter version is part of the contract

**Builtin `sum()` over floats became Neumaier-compensated in CPython 3.12.** It is not a
faster loop; it returns different values. `Sim/icarus_sim/terrain_globe.py` runs that path per
cell, and `Sim/icarus_sim/terrain_nests.py` carries an in-code comment recording that an
explicit accumulator gives "a different (less accurate) value by about one ULP and silently
changes generated worlds on some seeds."

`math.hypot`'s algorithm also changed inside the 3.9–3.13 range.

`pyproject.toml` and `setup.py` currently declare `requires-python = ">=3.9"`. **That is wrong
and should be `>=3.12`** — worlds generated on 3.9 are not the worlds this repository's
documents measure. A port must state which interpreter it is reproducing, and reproduce
Neumaier compensation explicitly rather than using its language's `std::accumulate`.

`Core/globe.hpp` already declares a `Sum` accumulator for exactly this reason, and roughly
forty call sites annotate it. That is the half of the problem that was solved.

## 2. The random stream, not the random values

Every `random.Random` call is a CPython **algorithm**, not a number. A port reproduces the
algorithm or it produces a different world. Call sites under `Sim/`, excluding tests:

| Method | Sites |
|---|---:|
| `.random()` | 53 |
| `.uniform()` | 33 |
| `.randint()` | 19 |
| `.choice()` | 16 |
| `.randrange()` | 11 |
| `.gauss()` | 3 |
| `.shuffle()` | 2 |
| `.choices()` | 2 |
| `.sample()` | 1 |

Four specific traps, each verified in the current tree:

**`sample()` picks between two algorithms by population size.** `Core/pyrandom.hpp` records
that the selection-set branch and the pool branch "consume completely different word
sequences, so the choice is part of the stream and not an optimisation we may make
differently", and that both branches occur in this generator — a large city takes one, a small
or heavily clipped site takes the other. Implementing one branch produces correct-looking
worlds that diverge on size.

**`gauss()` caches a spare between calls, and a rejected loop iteration carries it.**
`Sim/icarus_sim/terrain_tectonics.py:32` draws three values (`rng.gauss(0,1) for _ in
range(3)`), may `continue` on rejection, then draws three more. Three is odd, so the spare
alignment survives the rejected iteration. A `gauss` implemented without the persistent spare
gives a different planet, not a different ULP.

**Four different seed-derivation idioms are live**, and only the first is described in any
conformance record:

| Idiom | Where |
|---|---|
| `sha256(...)[:4]` big-endian → int | `Sim/world_geometry/seeds.py:15` |
| `sha256(...)[:8]` big-endian → int | `Sim/icarus_sim/city_planner.py:256` |
| `sha256(...)[:8] / 2**64` → float weight | `Sim/icarus_sim/city_shapes.py:158` |
| 64-char **hex string** passed to `random.Random` | `Sim/icarus_sim/castle_planner.py:160` |

The last is a genuinely different seeding path — `random.Random(str)` hashes the string rather
than using an integer directly. `Core/castleplanner.cpp` hand-rolls SHA-512 solely to
reproduce it.

**Argument evaluation order is load-bearing in one place.**
`Sim/icarus_sim/terrain_recipes.py:22` builds a `Config(...)` whose keyword arguments draw from
three interleaved RNG streams — `rng.uniform`, `weather.uniform`, `magic.randint`,
`magic.uniform` — inside a single call expression. Python evaluates arguments left to right;
C++ does not specify the order. **Caveat:** `seed_config` runs only when `auto_parameters` is
set and `world_recipe` is falsy, and recipe 3 forbids that combination, so this path is dead
today. It is recorded here because reviving the automatic-parameter path without knowing this
would produce a silently different world.

## 3. Rounding and float formatting reach published bytes

**161 non-test `round()` calls** under `Sim/`. Python's `round(x, n)` is
correctly-rounded-to-decimal with banker's (half-to-even) ties. `std::round`, and the common
`floor(x * 1e4 + 0.5)` idiom, are neither. Published surface heights go through this.

**Five sites hash `json.dumps(...)` output into a SHA-256 that ships inside the world**
(`city_planner.py:57`, `city_shapes.py:149`, `castle_planner.py:39`, and others). That means
Python's shortest-round-trip float `repr` is inside a published digest. A port must reproduce
`repr(float)` exactly — not "print enough digits". Note the sites do not all use the same
separators, so the exact `json.dumps` arguments at each site are part of the contract.

## 4. Container ordering

Dict insertion order and `sorted()` stability are load-bearing in places. `PYTHONHASHSEED` is
pinned nowhere in the repository; string-keyed set iteration is believed safe only because the
sampled sites funnel through `sorted()` or `min()`. **No test asserts this and no document
claims it.** A porter should treat every set iteration over strings as suspect and check the
site.

Both planners order sites by `str(uid)`, so `"10" < "9"`. Deterministic, and portable only if
the porter knows not to sort numerically.

## 5. What the build has to promise

The repository specifies **no floating-point build flags anywhere**. A search for `fp:`,
`ffast-math`, `ffp-contract`, `fma`, `/O2` or `x87` across `tests/`, `tools/`, `Core/`,
`Unreal/` and `docs/` returns nothing outside one test harness comment.

`tests/native_cxx.py` records that the MSVC build must use `/MD`, not the default static CRT,
"because CPython calls ucrtbase.dll and the static CRT's `pow()` disagrees with it by one ulp."
The same file's non-MSVC branch passes no float flags at all — and GCC and Clang contract to
FMA by default, so that path was never bit-exact and nothing says so.

A porter's first three questions — which libm, `/fp:precise` or not, `-ffp-contract=off` —
have no answer in this repository. **They need one before the port starts.**

## 6. Undocumented execution switches

`ICARUS_CITY_WORKERS` (`city_planner.py`, and read again by `hamlet_planner.py`, so one
variable controls both) changes execution path and appears in **zero** `.md` or `.json` files
in the repository. No single place enumerates the complete non-config input set.

A second switch, `FANTASY_WORLD_PROFILE`, was advertised by a dead function in
`terrain_profile.py` that nothing called and that contradicted its own conformance record. It
was removed on 2026-09-21 rather than documented, so `ICARUS_CITY_WORKERS` is now the only
undocumented execution switch.

Related and unresolved: `Sim/fantasy_world_generator/__main__.py` has no `if __name__ ==
"__main__"` guard, and `multiprocessing.get_start_method()` is `spawn` on this machine. The
pooled planner path cannot be used by a caller that generates at import time, which is what
that file does. So `python -m fantasy_world_generator generate` takes the serial planners here
while a fork platform takes the pooled ones — and the byte-reproducibility gate in
`tools/validate_repo.py` runs through that entry point. **Whether pooled and serial output must
be byte-identical has not been ruled on**, and no test compares them.

## What this document is not

- **Not a port plan.** It is the list of things that are invisible until they are wrong.
- **Not complete.** It covers the substrate, not the algorithms. The algorithms are in `Sim/`
  and, for the quarter of modules that have one, in `docs/conformance/`.
- **Not tested.** Nothing here is asserted by a test. Section 1's claim was demonstrated by
  shadowing `sum` and observing 457 of 1089 TPI cells move on a size-33 field; the rest is
  read from source and from `Core/` comments. A reader should re-verify before relying on any
  line of it.
- **Not a reason to keep `Core/`.** Decision 027 stands. This document exists so that deleting
  `Core/` costs nothing but the code.
