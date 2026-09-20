# Code red team — `233182e`

Lens: **the code as written, the documents that claim to describe it, and the gaps** —
logic errors, unreachable values, state mutated behind a reader's back; plus whether the
project's own gates actually run, and whether its canonical documents are true.

Brief, verbatim: *"Most of the app is vibecoded, I need a through red team of the code, the
conformance docs, and gaps."*

Baseline **`233182e`**. Two findings were repaired during the session; their repairs were
verified at **`3b3137f`** and are marked **[FIXED]**. Anchors were verified against
`233182e` (28/28), then re-verified after the repair landed: **21 ok, 7 drifted**, all seven
in files the performance session rewrote. Anchors below are corrected to `3b3137f`.

**Verification vocabulary.** *Verified* = run or read here, reproducible. *Observed* = seen
in a run whose conditions are stated. *Unread* = known to exist, cause not established.
Nothing below is inferred-but-unchecked.

---

## The largest unexplained thing in the sweep

### H4 — native parity divergence is far wider than the previous account **[root causes UNREAD]**

**The previous account — "five native test failures, all the twelve-versus-eight
`SCHOOLS`/`school_names()` lag" — is wrong and should not be requoted.** It stood for
several hours and the next person should not have to rediscover that.

Observed at `233182e`, `repo-tests` with two modules quarantined (below):

```
98 ok, 68 FAIL, 8 ERROR, 2 skipped
```

Every failure is in `test_native_world.NativeWorldTests`. Six distinct methods:

```
test_stage_nine_magic_and_environment_match_the_reference     24 FAIL + 6 ERROR subtests
test_the_finished_world_matches_the_reference                  1 FAIL + 39 per-city subtests
test_city_layout_plans_match_the_reference                     FAIL
test_hinterlands_ports_and_nests_match_the_reference           FAIL
test_per_people_fields_budget_and_founded_cities_match_the_reference   FAIL
test_native_world_reproduces_the_reference_world_for_one_seed  FAIL
```

The magic stage alone is **31 layer subtests** — ten `ley_*`, eight `instability_*`, six
`zone_*`, four `magic_*`, `dominant_magic`, and `lunar_sensitivity` twice. Not twelve.

A school-name count **cannot** explain city layout planning, hinterlands, ports, nests,
per-people fields, budgets, founded cities, or **39 individual cities** failing byte
comparison against the reference (`surface-city-2-830-gnome`,
`surface-city-2-781-human_cold`, and so on). That is **at least four subsystems**, not one
cause.

**Two cautions, both load-bearing:**

1. **The run did not finish.** It was stopped inside
   `test_showcase.test_bundle_is_fresh_reproducible_and_traceable` to return 2.7 GB and two
   cores to a saturated machine. The counts above are as-of-stop, not final.
2. **The assertion text has not been read.** unittest prints tracebacks only at the end of
   a run, so stopping it forfeited them. This is **scope**, not root cause.

The trade was correct twice over: the machine was saturated by six concurrent runs, and the
tree was mid-edit at the time, so those tracebacks would have been unattributable anyway.

### The resumed run, specified

Do not re-derive this.

1. Run **`test_native_world` alone**, on a **quiet machine** — nothing else generating
   worlds, no other suite, no lab server holding a port.
2. **Read the 8 ERRORs first.** An exception in a parity comparison is most likely a shape
   or key mismatch, which would put those six in a **different family** from the 68
   assertion failures. That is a hypothesis to test, not a conclusion.
3. Expect **at least four families**. Resist unifying them under one story — the temptation
   to do so is exactly what produced the wrong previous account.
4. Report what the messages say, not what they seem to mean.

**Quarantined from that run, and why:**

- `test_native_genesis` — was non-terminating at `233182e` (B1). **Fixed**; no longer needs
  quarantine.
- `test_docs_check` — mutates the live tree (M4). Keep it quarantined while any other
  session is writing.

---

## Blocking

### B1 — `validate_repo` could not complete; the suite never terminated **[FIXED]**

`21df9aa` widened the Python world-grid ceiling 257 → 1025 at `terrain_world.py` and left
three mirrors behind: `Core/genesis.hpp` (`max_grid=257`), `Fixtures/unreal-frame-v1.json`
(`size: 258` under `invalid_generate`), and `tests/test_native_genesis.py` (asserting the
literal text `max_grid=257`). That commit touched **sixteen** `Core/` files — not neglect
of the native side, just the one constant mirroring the bound it moved.

The test was weaker still than "asserts literal text", a point sharpened during the repair
and worth keeping: the old form used `assertIn`, which is **containment, not identity**. A
native ceiling of `2570` contains the substring `max_grid=257` and would have passed,
because the old value is a prefix of the new one. A divergence could have survived with
both assertions green.

Two tests went red in different ways. The accepts-bounds test failed fast. The
rejects-fixtures test **did not terminate**: `generate_request` is not a validator —
`terrain_world.py:204` imports `generate` — so once the size-258 fixture stopped being
rejected, the test built a 258² world inside the suite. Measured, with everything else
rejecting instantly for contrast:

```
size    2  rejected 0.03s      size 1026  rejected 0.00s
size    0  rejected 0.00s      size  258  still running at 20s, and at 60s
size   -1  rejected 0.00s
```

Neither test is compiler-gated, so CI hit it too: `timeout-minutes: 30` meant the
`repo-tests` leg burned half an hour and died by timeout, reading as flaky infrastructure
rather than a contract break.

**"Nobody ran `validate_repo`" and "this defect exists" are one event, not two.** Anyone
who tried would have watched it sit there and concluded the suite was slow.

**Repair, verified rather than taken on report.** User ruled 1025 correct.
`Core/genesis.hpp` is now `max_grid=1025`; `terrain_history.py:590` (age advance) and
`terrain_patch.py:95` (world gate) both moved to `>1025`; the fixture sentinel moved from
`258` to `1026`. `terrain_patch.py:27` correctly keeps 257 — that is per-patch vertices,
not world grid. The test no longer asserts literal text: it parses
`(min_grid|max_grid)=([0-9]+)` and compares **values** against `registry(3)['size']`, so
neither ceiling can move alone. Checked independently:

```
byte scan of test_native_genesis.py   0 suspicious bytes (no stray control characters)
regex vs Core/genesis.hpp             {'min_grid': 3, 'max_grid': 1025}
registry(3)['size']                   {'min': 3, 'max': 1025}
remaining 'max_grid=257' at :89       inside a comment, not an assertion
```

**Residual, not a finding.** `generate_request` still validates **and** generates. Today
`invalid_generate` holds only fast-rejecting values so nothing is exposed — but the shape
that caused B1 survives: **one added *valid* fixture in a loop rebuilds the symptom under a
different cause**, and the function's name gives no warning that iterating fixtures through
it generates a world per case.

---

## High

### H1 — the coverage ratchet has never executed, in any code path

`check_coverage` guards the entire ratchet behind `if ratchet_base:` (`docs_check.py:433`).
The only caller in the repository is `validate_repo.py:75`, which runs `tools/docs_check.py`
with **no arguments**; CI only ever calls `validate_repo.py --stage <stage>`. So
`args.ratchet_base` is always `None` and `COVERAGE-RATCHET` is dead code.

`board/in-progress/CONFORMANCE-DOCS.md:81` says the ratchet "reports itself skipped rather
than passing silently." It does not — the `print('COVERAGE-RATCHET skipped...')` at `:445`
lives *inside* the same guard, so it prints nothing and checks nothing. The card describes a
degraded mode strictly better than reality.

AGENTS.md's "the allowlist may only shrink" has **zero** machine enforcement. The ticket
requirement (`COVERAGE-TICKET`) is enforced; the shrink-only rule is not.

### H2 — conformance front matter is one-ninth enforced

`front_matter()` is called once (`docs_check.py:401`) and read on exactly one line:
`fm.get('modules', [])` (`:402`). Nothing else. `record:`, `tier:`, `summary:`, `emits:`,
`versions:`, `proof:`, `decisions:` and `tickets:` are parsed and discarded.

A record may therefore cite a schema that does not exist, name a proof test that does not
exist, assert a version integer nothing compares, claim `tier: BULLETPROOF`, and disagree
with its own filename — all green. `docs/conformance/README.md` says "Front matter carries
the machine-checked claims," true of one key in nine. Versions are really checked through
`version-bindings.json` plus `<!-- conformance:version -->` markers; the `versions:` block
is a decorative duplicate. `nomads.md`'s five cited paths all exist today, so this is a
missing guard rather than live breakage.

### H3 — the only conformance record states a determinism invariant that is false

`nomads.md`, under **"Determinism is an invariant"**:

> Seeds derive through `child_seed(cfg.seed, 'nomads-v1', nomad_variation)`, with per-entity
> domains `nomad-class-<uid>`, `nomad-camp-<uid>` and `nomad-route-<uid>`.

First clause true. **The per-entity domains do not exist** — not in those modules, not
anywhere in the repository. What runs:

```
terrain_nomads.py:397   rng = random.Random(child_seed(cfg.seed,'nomads-v1',variation))   ONE stream
terrain_nomads.py:422   rng.random()
terrain_nomads.py:447   _pick(rng, shares, total)   ->  draw = rng.random() * total
terrain_nomads.py:450   rng.randint(low, high)
terrain_nomad_routes.py:34   imports child_seed, never calls it. Zero Random() in the file.
terrain_nomad_effects.py     no randomness at all.
```

The record then reasons: *"Because streams are keyed by a string domain, a feature drawing
only from new domains cannot perturb an existing stream."* Correct about a per-entity
design; **false about this module**. One sequential stream means any change to the number or
order of draws shifts every draw after it.

Two corroborating details. The unused `child_seed` import in `terrain_nomad_routes.py` is
the fingerprint of a scheme that was planned, documented, and not built. And
`CLASSIFICATIONS` is annotated **append-only**, which reads as a safety guarantee — but
`_pick` computes `draw = rng.random() * total`, so appending changes `total` and remaps the
same draw to a different band. **Appending is world-changing.**

**Why this outranks H1 and H2.** Those are holes in the mechanism. This is the mechanism
working exactly as designed and still shipping a false invariant — `docs_check` is green on
this record and *should* be, because every symbol it cites exists. AGENTS.md predicted it
verbatim: *"A green `docs_check.py` ... proves nothing about whether the record is true."*
That sentence came true on the first record written under it, in its invariant section, in
the document that is the template for roughly 120 more.

The rest of the record is strong — 30 mechanical checks pass: every entry-point symbol
exists at module top level, `CLASSIFICATIONS` order matches exactly, the phase-16 gate is
real, `nomads-v1` is real, `test_terrain_nomads.py` has exactly the 22 methods claimed, and
both `STATE_KEYS` and the lab's `historyStateKeys` contain `nomads`. **A good document with
one wrong section is the hardest kind to catch, and the reason record review cannot be
delegated to the checker.**

### H5 — the determinism guard covered a world with no surface relief **[FIXED]**

`validate_repo.artifacts()` generated two worlds at `--seed 42 --size 17` and byte-compared
them. The octave filter admits octave *k* iff `wavelength/2**k >= 2*step` where
`step = 2πr/(n-1)`. Solved from `default_config(3)`:

```
size    17  ->  0 of 5 octaves   k=[]        <- what the artifacts stage generated
size    33  ->  1 of 5
size    65  ->  2 of 5
size   129  ->  3 of 5
size   257  ->  4 of 5
size   513  ->  5 of 5                       <- first complete terrain
size  1025  ->  5 of 5
```

At size 17 `frequencies` is **empty**: the multi-octave accumulation never executes, the
`.5**k` falloff and `ridge` term never run, and the surface-noise contribution is
identically zero.

*Narrowed from an initial overstatement:* `perlin3` **is** still called. Eight call sites,
only two octave-filtered (`terrain_globe.py:110`, `terrain_tectonics.py:186`). Plate noise,
biomes, ecology and settlements all run, so the `pow()`/ulp hazard **is** exercised. The
accurate claim is that the **multi-octave surface-noise path** is untested, not that
`perlin3` is never called.

**The sharp part: the project already detected this and said so.**
`terrain_tectonics.py:212` emits `"Only 0/5 surface-noise octaves resolved; fine layers
omitted."` `resolved_octaves` is exported in the world document, resolved in
`terrain_scale.py:91`, folded into metrics at `terrain_metrics.py:261`, tabulated as an
`oct` column in `tools/terrain_metrics.py:36`, displayed to the user at
`tools/terrain_lab.html:97`, and ported to C++. And `Sim/tests/test_terrain_metrics.py:107`
contains a **green, passing test** asserting that at `seed=42, size=17` — character for
character the artifacts configuration — the noise layer is all zeros.

The guard could not see any of it: **`validate_repo` never parses the world document.** All
four comparisons are `read_bytes()` (`:57, :63, :94, :105`); the only `json.loads` is on a
schema at `:54`. A byte comparison cannot notice a self-declared warning inside the bytes it
is comparing.

**Repair: both halves, as specified.** The size-17 phase-16 pair stays, and a
513/phase-5 byte-compared pair was added beside it asserting `resolved_octaves == octaves`,
costing about four minutes. Asserting alone would have turned the gate honestly red while
leaving determinism covering nothing; moving the size alone would have lost the invariant.
Perf's 513 run reports 126.3 s, 5 of 5 octaves, zero non-finite values across
height/base/structure/continental, and `json.dumps(allow_nan=False)` succeeding.

*For anyone re-deriving the table:* radius cancels along the real derivation.
`terrain_recipes.py:23` sets `wavelength = radius*1.6/sqrt(plate_count)` and
`terrain_area.py:30` scales radius and wavelength by the same factor, so
`wavelength/step = 1.6*(n-1)/(2π*sqrt(count))`. Swept across plate counts 9, 11, 12, 14, 16
— **the table is identical across all five**. The trap is pairing one planet's radius with
another's wavelength, which is what `test_design_radius_not_physical_radius` warns about by
holding wavelength fixed while moving radius.

### H6 — the raised ceiling is unreachable for a full world; city count scales with the raster

City count tracks the raster at roughly **0.035 × cells**. At 513 that is about **9,000
cities**, each requiring a planning pass. So the 513/phase-5 determinism pair added above is
affordable, but a **full phase-16 world at 513 is not**.

This matters more than the bound itself. The 1025 ruling made complete terrain *reachable* —
five octaves need 513, and age advancement previously refused above 257, so no world in this
project's history has carried its full octave stack. But terrain completeness and world
completeness now sit on opposite sides of a cost wall: 513 gives five octaves and ~9,000
cities; 257 gives a tractable world with four fifths of its terrain. **The gate moved; the
barrier did not.** Whether city count should scale with the raster at all — rather than with
habitable area, population, or a cap — is the open design question.

**Gate adopted:** the 1025 bound is not closed until a world has generated at 513 with five
octaves firing. Phase 5 is done; a deeper phase is not.

---

## Medium

### M1 — two-level front matter silently loses its second key
`emits:\n  - path: nomads\n    schema: ...` parses to `['path: nomads']`; the `schema:` line
is discarded. Same for `proof:` (`establishes:` lost) and `versions:` (`assert:` lost) — the
exact shape `nomads.md` and `_template.md` use. **This is why H2 is not a quick fix:**
consumers cannot be added until the parser can represent the data.

### M2 — the front matter parser crashes where it should report
`modules: Sim/a.py` followed by an indented `  - Sim/b.py` raises
`AttributeError: 'str' object has no attribute 'append'` instead of a `CLAIM-SYNTAX`
finding — `setdefault` returns the existing string and `.append` is called on it. Same bug
class as the `UnicodeDecodeError`-instead-of-`ENCODING` one already fixed: the naive-read
hazard inside the tool built to catch it. Trigger is a natural authoring move — converting a
single-module record to multi-module and leaving the first module inline. Seven malformed
shapes probed; the other six degrade quietly.

### M3 — compiler detection is split; two of five native modules are blind to MSVC
```
compiler_command()   ->  test_native_genesis.py:23, test_native_wire.py:29, test_native_world.py:112
shutil.which only    ->  test_native_counter.py:39, test_native_package.py:37
```
`native_cxx.compiler_command()` falls back to vswhere and finds MSVC;
`shutil.which('clang++') or shutil.which('g++')` never will. **Demonstrated live in one run
on one machine:** `test_native_counter` and `test_native_package` skipped claiming "requires
a C++17 compiler" while `test_native_wire` compiled C++ and passed in the same process. Two
of five native modules silently unverified on Windows, reported as an environment
limitation. This also explains an apparent disagreement between sessions about whether
native tests run here: they do, for three of five.

### M4 — `test_docs_check` mutates the live source tree
It writes `Sim/icarus_sim/zz_probe_module.py`, `docs/conformance/_probe.md` and a duplicate
`docs/decisions/0NN-*.md`, and **mutates two real committed files** —
`docs/conformance/version-bindings.json` and `provenance/extraction-manifest.json` —
restoring them in `tearDown` from bytes captured at `setUp`.

**Root cause is a missing seam, not a careless test:** `docs_check.py` resolves `ROOT` from
`__file__` with no injection point, so its own negative tests have no way to exercise it
except against the real tree.

Two hazards. A hard kill between write and restore leaves the tree mutated — a corrupted
provenance manifest is a quiet, non-obvious breakage. And with concurrent sessions sharing
one tree, a `tearDown` restoring from pre-edit bytes would **silently revert another
session's real work**, with no crash and nothing in a diff to show it happened. `233182e`
was exactly the bulk-`git add` shape that would have committed the probe files.

**Keep it quarantined while any other session is writing.**

### M5 — the suite orphans its child process on interrupt
Stopping a background task killed the wrapper and left the real work running, **twice, on
two different runners**:

```
export_showcase.py                     2,258 MB   survived the stop
unittest discover -s Sim/tests           894 MB   survived the stop
```

**Not specific to `export_showcase`** — interrupting any suite here leaves the child alive,
and nothing reports the survivor. This is how a machine ends up saturated by runs everyone
believes they already stopped, which is the state this one was found in: at one point six
concurrent python processes were generating worlds, including **three separate sessions
running the same sim-tests suite**.

Stop survivors explicitly by PID, matched on your own exact command line — on a shared
machine the process list is full of other sessions' work and killing the wrong one destroys
a peer's run silently.

**Showcase cost, measured, undocumented anywhere:** bundle **338,680,135 bytes**;
`export_showcase.py` child peaked at **2,258 MB resident and still climbing** at roughly
**twenty-five minutes inside a single test method**. It takes `--allow-dirty`. **CI runs the
same exporter in its build job**, so the cost is paid there too. That last clause is what
makes it a card rather than a note.

### M6 — octave index reuse: correct today, one edit from silently wrong
*(Found by the Gamer lens; verified here, with two additions.)*

`terrain_tectonics.py:178` filters `range(cfg.octaves)`; `:185` enumerates the **filtered**
list and uses that index for both the amplitude `.5**k` and the seed `detail_seed+k*1013`.
Safe only because `wavelength/2**k` decreases monotonically, so the predicate always removes
a **suffix** and surviving positions coincide with their original `k`. Any predicate that
drops a middle octave silently shifts amplitude and seed together — a world change with no
exception and no failing test. Same shape as the sparse-id-as-array-offset bug.

**Addition 1 — the two sites are not interchangeable.** `terrain_tectonics.py:185` seeds
from `detail_seed+k*1013`; `terrain_globe.py:109` seeds from `cfg.seed+k*1013`. The filter
expression is character-identical; the seed base is not. **Deduplicating them naively
changes worlds.**

**Addition 2 — behaviour-preserving fix.** Carry the original index rather than re-derive
it: `[(k, 2**k/cfg.wavelength) for k in range(cfg.octaves) if ...]` then
`for k, f in frequencies`. Byte-identical today, immune to any future predicate. Both sites,
preserving the two seed bases.

*Citation trap:* for `shape=globe, tectonics=1`, `generate_base` dispatches to
`generate_tectonics`, so the filter that actually runs is `terrain_tectonics.py:178`, **not**
`terrain_globe.py:102`.

---

## Low

- **L1 — `Core/` is enforced one-directionally.** `universe` in `check_coverage` is
  Python-only, so ledger entries must resolve to real files but real `Core/` files are never
  required to be *in* the ledger. 46 = 46 today by care, not construction. Trigger is named
  in the conformance README: the native port is being redone for the Unreal import.
- **L2 — `core_stems()` uses `iterdir()`**, so it is top-level-only. `Core/tests/*.cpp` are
  excluded correctly but by accident. A future `Core/sub/x.cpp` leaves the stem universe
  silently, and a record claiming it fails with the misleading "claimed Core stem does not
  exist."
- **L3 — five stale `CITE` anchors**, all confirmed drifted; `VILLAINS-NO-SCHEMA.md:82`
  points at a blank line. Five stale citations within hours of being written is itself a
  finding about the mechanism's half-life: **line numbers in board cards are a decaying
  asset.** An anchor checker that re-verifies citations before filing costs minutes and
  catches all of them — this review's own anchors were re-verified that way (21 ok, 7
  drifted, all seven in files the repair touched).
- **L4 — `Artifacts/*/index.html` carry a stale `historyStateKeys`** missing `nomads`,
  `astrology`, `religion`, `heroes`, `story_web`, `npcs` and `key_locations`. Generated
  output drifted from `tools/terrain_lab.html`.

---

## Checked and cleared — not findings

Recorded because a red team that reports only defects gives a false picture of the code.

- **Determinism hygiene in `Sim/` is genuinely strong.** Zero set iteration, zero wallclock
  reads, zero `hash()`/`id()`, zero `os.environ` reads in generation paths, zero bare
  `except`, zero mutable default arguments, zero `list(set(...))`. All 40 RNG sites are
  seeded `random.Random(child_seed(...))` with a domain string; **no module-level `random.*`
  calls anywhere**. Every `.pop()` is on a list, not a set.
- **The villain-fall widening was handled correctly.** `people` now carries fallen villains;
  every consumer was chased and the author had already added `standing()` filters at exactly
  the two sites needing them (`terrain_corruption.py:141,163`). `terrain_corruption.py:277`
  iterates unfiltered and is **right** to — it is a uid lookup for write-back.
- **`coverage.json` is internally perfect.** 124 Sim non-test modules = 112 uncovered + 8
  exempt + 4 covered; 46 `Core/` stems all resolve to real `.cpp`/`.hpp`. Zero phantoms,
  zero duplicates, zero real modules unaccounted for, and all 8 exempt notes factually true
  (verified by AST walk). Coverage is 4/124 = 3.2%, which is **carded, not a defect**.
- **`VILLAIN-FALL-UNRECORDED.md` is correctly labelled** — its header states "implemented in
  the working tree, pending a multi-age run." Nearly filed as a stale card; the header is
  honest.
- **The `artifacts` stage really does byte-compare two generated worlds**, not just the asset
  list. Its weakness was the configuration (H5), not the mechanism.

---

## Method notes, for whoever runs the next one

- **Every finding got stronger by getting narrower.** Two of mine were wrong in their wide
  form and right in the narrow one: "perlin3 is never called" (it is called; the
  *multi-octave path* is not), and "46 phantom ledger entries" (they were C++
  translation-unit stems, all resolving). A finding that dies on a `grep` is worse than no
  finding.
- **Audit relayed numbers, not just code.** Several figures circulating between sessions did
  not survive checking — a module count that did not sum, a native failure scope understated
  by roughly six times, a claim that two tests "pinned zero octaves as correct behaviour"
  when one was a predictor-mirror test and the other used a different wavelength. **A wrong
  number travels further than a wrong finding.**
- **Verify a written file by executing it, not by reading it back.** A regex written through
  a heredoc had its `\b` collapse into a literal `0x08`; the file looked correct and matched
  nothing. Reading shows the character you meant, not the byte on disk. Byte-scan when it
  matters.
- **Never measure a moving tree.** A suite reading a tree another session is rewriting
  produces failures that cannot be assigned to a cause — not slow, *unattributable*. Check
  `git status` and mtimes before trusting any run, and before blaming yourself for a result.
