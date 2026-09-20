---
modules: []
---

# Coordinator roll-up — adversarial sweep, 2026-09-19/20

Cross-session synthesis for the sweep that ran from `233182e` to `651ab00`. The six lens
reviews stand on their own; this records what only the coordinator saw — findings that
crossed sessions, findings held out of the board by user instruction, the corrections that
killed wrong claims, and the method failures that produced them.

**Status key.** `[verified]` — I reproduced it myself, or the owning session proved it by
running rather than reading. `[owner-verified]` — the owning session ran it, I did not
re-run. `[open]` — not established.

---

## 0. Resume here

The sweep paused at `651ab00` with five rulings outstanding and two investigations unfinished.
Nothing below is blocked on anything except a decision or a quiet machine.

**Decisions first — three of these unblock work that is already written and ready:**

1. **Disposable worlds?** Unblocks `BESTIARY-LAND-ICE-NO-ANIMALS`, which is complete: 8 numeric
   keys, weights chosen. Nothing else stands in its way. **Read §1's note first** — the only
   evidence that the layer regression *is* a regression lives in the artifacts a cleanup
   would delete.
2. **Tombstone or retire biomes 1 and 6?** Tombstoning needs no disposability answer and is now
   a one-row edit to `Sim/icarus_sim/biomes.json`, because the data-ization landed.
3. **Land the corruption fix now, or wait for `SUPER-VILLAINS`?** And does `cleanse_request`
   get the mirror? The argument for now: it is seed-affecting only where corruption acts, and
   corruption cannot act today because no super villains exist, so the blast radius is
   currently **zero**. This is the cheapest moment the fix will ever have.
   (`MAGIC-CORRUPTION-NEVER-REACHES-GROUND`)
4. **Should monsters feel biome-specific?** Design intent. No code before it is answered.
5. **Is this world's fauna Earth's?** 311 real species always instantiate, 369 invented ones
   never do.

**Then two investigations, both cheap once the machine is quiet:**

- **Native root causes.** 68 FAIL / 8 ERROR, unexplained. Run `test_native_world` alone,
  **8 ERRORs first** — an exception in a parity comparison is likely a shape or key mismatch
  and a different family from the assertion failures.
- **Determinism outside seed 42 size 17, villain paths live.** Needs `villain_rise > 0`, not a
  large grid — villain paths execute at size 17.

**One defect needs an owner and has none:** the broken age-advance round trip (§3). It is not
a one-line fix; see the framing there.

**Two findings exist only as review sections, not as cards**, because the code lens's filing
hold was never lifted by its user and a peer relaying a wind-down does not lift it. Both are
constraints rather than defects and neither exists anywhere else — the suite runner orphaning
its child on interrupt, and the showcase cost. They are in
[`233182e-code-red-team.md`](233182e-code-red-team.md), written to convert directly to cards.

**One tree-hygiene item:** commit `3b3137f "perf work"` swept 30 files and 5,114 insertions
from six sessions under a two-word message, including five test files with sixteen
deliberately failing tests that their author had chosen not to commit. Nothing is wrong in the
files; they are attributed to a commit that does not describe them. No history was rewritten.

---

## 1. Needs a user decision

| Question | Why it blocks | Card |
|---|---|---|
| Are saved worlds disposable until a named milestone? | Gates the land-ice fix, which is otherwise ready. Also gates any regeneration after the grid widen. | `PRODUCT-WORLD-DISPOSABILITY-DECISION` |
| Retire biomes 1 and 6, or make the ecology pass respect them? | Two of thirteen published biomes cannot exist. Tombstoning is cheap and needs no disposability answer. | `BIOME-TUNDRA-SNOW-UNREACHABLE` |
| Should monsters feel biome-specific at all? | Design intent. No code should be written before it is answered. | `BESTIARY-MONSTERS-BIOME-BLIND` |
| Is this world's fauna Earth's? | 311 real Earth species always instantiate; 369 invented monsters never do. No rename table resolves it. | in the content review |
| Are 11.6 km mountains the intent at five octaves? | Phase-5 measurement, before erosion and water. Nobody has seen a five-octave world. | open design question, deliberately unfiled |

**A note bearing on the first row.** The only record of what `island_habitat` and
`freshwater_distance` looked like before they regressed is a five-day-old generator-9 world
under `Artifacts/`. I dismissed that document as stale; it turned out to be the control.
Those thirteen worlds are the only version history those layers have — a cleanup would have
left the regression looking like a standing defect. [verified]

---

## 2. The regression (highest priority defect)

Two published layers collapsed between generator 9 and generator 16, on the same seed, size
and phase, while the features they describe still exist. [verified]

```
                         gen 9/17    gen 16/17    gen 16/33
island_habitat  nonzero      2           0            0
freshwater_dist nonzero      5           0            1  (max 2388.49)
freshwater_dist == -1      248         239          810
readers.cells land/water  39/201       47/193      268/724
ocean_archipelagos           3           3            3
```

- **Lead with `island_habitat`.** Zero at both generator-16 rasters against 2 at generator 9,
  no sentinel involved, and no stray cell for a reviewer to point at.
- `freshwater_distance` is **not** identically zero — one cell at size 33 carries 2388.49.
  State it as counts, or the claim dies on that cell.
- **Bisect hint:** `-1` still marks water correctly at the right counts in both versions. The
  layer was not dropped and its water handling did not break — only the land-side computation
  stopped producing values.
- **Cheapest probe:** `settlements.sites[].freshwater_distance_m`. Forty numbers, no grid
  traversal. It is a faithful derived copy of the layer, **not** independent evidence — I
  claimed it contradicted the layer and it does not; zero settlements differ in any document.
- **Downstream:** this is why `holy_well` places with its defining requirement unenforced.

---

## 3. Confirmed defects by area

### Contracts and tests — 6 cards, all filed and indexed
- Villain fall branch is dead code in every buildable configuration; a stranded villain can
  never fall. Villain `status` (`living|fallen`) has **no published schema** at all.
- `pending_ley_edits` has no consumer; the producer appends and the block rides in
  `STATE_KEYS`, so the first hidden-school unlock starts an accumulator nothing clears.
- Site ids are list ordinals re-sorted every age, across four fields.
- The world contract requires 6 keys and declares 10 of the 48 blocks `STATE_KEYS` carries —
  a document with no terrain, settlements or people conforms.
- Thirteen properties named `status`, twelve with enums, five vocabularies, plus one
  unconstrained bare string. The only translation between two published contracts is a
  private expression at `npc_roster/__init__.py:190`.
- Three rejection tests used "one above the current limit" as their sentinel; raising the
  ceiling turned all three into legal work. **The repair re-arms the trap at 1026.**

### Determinism and the gate
- `validate_repo` never parses the world document — all four comparisons are `read_bytes()`.
- The artifacts stage hardcoded `--size 17`, where **zero of five octaves resolve**, so the
  multi-octave surface path had no determinism coverage. `perlin3` itself does still run via
  six unfiltered call sites, so float determinism *was* covered. [verified]
- `test_terrain_metrics.py:107` is a green test generating **seed 42 size 17** — the artifacts
  configuration exactly — asserting the noise layer is identically zero. The project already
  proved the guarded world was flat.
- **Fixed** in `4713f9a`/`da83b34`: a 513/phase-5 byte-compared pair plus an assertion that
  `resolved_octaves == octaves`, alongside the existing pair.

### Content and placement
- **Four causes wear one symptom** (archetypes placing nothing), ordered by what a fix needs:
  1. **Domain/field mismatch** — `salt_mine`, `salt_pans`, `whaling_station` are `domain: land`
     but gate on `salinity` / `fishing_productivity`, which are **identically zero on every
     land cell** and saturated on water. Unplaceable by construction; resolution-independent.
     The archetype is wrong, not the world. Cheapest fix on the board. [verified]
  2. **Area-scaled rounding** — the five tier-3 wonders report `wanted: 0` against 24–289
     candidates. Percentile-gated, so **1025 will not produce one.** The known
     "never round an area-scaled count" trap, recurring in a package written after it.
  3. **Tail calibration** — `volcanic` land max is 0.0286, below `geyser_basin`'s 0.05 floor;
     all qualifying cells at size 17 are water. The field fires; the gate/domain pairing fails.
  4. **Spacing squeeze** — dominant, 60 of 98 at size 17.
- **Flat difficulty gradient.** A tier-5 apex monster and a tier-1 prey animal both sit at a
  median **6.45 km** from the nearest settlement. The generator states a 3:1 danger-proportional
  rule in a comment; the raster produces a 0 km difference. Zero clearance violations — nothing
  malfunctions, the radius is simply below the grid.
  - Clearance is sub-cell only **below size 129**. Three regimes; 129–257 bites at the top and
    not the bottom, which will mislead. The surviving claim is structural: **a binary cutoff is
    the wrong shape and cannot produce a monotone ramp at any resolution.**
  - The weaker formula (`/3`, `terrain_nests.py:245`) governs `wildlife` — 4,065 sites, the
    layer players meet. The stronger (`:272`) governs 301 monster sites never instantiated.
- **Variety:** 10 of 97 key-location archetypes at size 17, `waystone` 38 of 48. Only 9 of 97
  place what they asked for; 60 squeezed by spacing, 13 rounded away.

### Biomes and fauna
- **Land ice (17) is in 0 of 21 role tables.** `biome_weight`'s `table.get(str(id), 0.)` makes
  absent mean excluded, so all 311 animals score 0.0 and all 369 monsters fall through to 1.0 —
  the ice is monster territory by accident, while nineteen authored polar species score zero on
  the only biome that is theirs. Fix is **8 numeric keys**, weights specified, each strictly
  below that role's tundra weight. [verified]
- **Biomes 1 and 6 cannot exist in a finished world** — `classify()` assigns them, the ecology
  pass overwrites both in 8820 of 8820 swept cases, confirmed absent from all twelve worlds on
  disk. Retirement is **not** a delete: `VARIANT_NAMES` indexes `NATURAL_BIOMES` positionally
  and `biome_variant` is a flat index into the 156-entry cross product. **Tombstone.** [verified]
- **10 commissioned assets target *only* unreachable ground**, with 36 more over-scoped rather
  than wasted. (My earlier figure of 49 was the union and does not survive an argument; 10 is
  the number that does.) All ten are snow and ice — `MAT-027` Fresh snow, `MAT-028` Compacted
  dirty snow, `MAT-030` Tundra moss and lichen, `GEO-025` Snow drift, `GEO-026` Ice ledge,
  `GEO-027` Icicle cluster and four others. **They should be re-pointed at biomes 16 and 17,
  which are reachable, not binned** — the finding is a re-target, not a write-off. [verified]
- **0 of 680 profiles carry their own `biome_weights`** — the documented per-species override is
  entirely unused. Habitat is a 21-way role choice.
- Monster gating is magical, not terrain: `ley_umbral` 75, `ley_weave` 71, `ley_primordial` 70;
  `moisture` leads score terms at 220; relief tail is `mountain` 9, `volcanic` 6, `depth` 5.
  Only **42 of 369** carry any relief weight — corrected down from a claim of 267.
- **Desert is not a defect.** Absent below size 65 only because the grid cannot produce a dry
  cell (moisture min 0.589 at 17, 0.223 at 65). *Anyone who had retuned its thresholds against a
  size-17 world would have broken warm worlds permanently.* [verified]

### Round trip and hidden schools

- **The documented age-advance round trip is broken and untested.** The CLI strips `timing_ms`
  deliberately (`cli.py:30`, with `--include-timings` at `:69` warning that keeping it makes the
  output non-reproducible), because byte-reproducibility is what `validate_repo` enforces. Then
  `terrain_biomes.py:100` writes into `result['timing_ms']` unguarded, so `advance_age_request`
  on a persisted document raises `KeyError` before doing any work — while `terrain_history.py`
  tells the user to persist and re-submit. The tests never catch it because they advance
  in-memory worlds that still carry the key. [verified]
  - **Proved by running both paths**, not inferred from the strip: default (stripped) raises
    `KeyError`; `--include-timings` advances fine, same seed, size and phase. So the statement
    is not "a write is unguarded" but **a world is either reproducible or advanceable, never
    both**.
  - The design question is settled in the tree: `cli.py` says timings "are a profiling aid, not
    part of the interchange contract." A persisted world is *not* meant to carry timing, so the
    fix is every writer tolerating absence. A `setdefault` at the site that happens to be
    reached first leaves the next one armed.
  - Filed as `TIME-PERSISTED-WORLD-CANNOT-ADVANCE`, cross-linked to `TIME-ADVANCE`.
  - This is the **third** defect tonight caused by the determinism guarantee interacting badly
    with something else, after the size-17 artifacts world and the ceiling sentinels.
- **RULED, DO NOT RE-OPEN: the gate is correct.** The user ruled that converting a node to a
  forbidden school is a *villain trigger*, not a player leyline edit, and that the generator
  must never produce a hidden school independently. So `terrain_history.py:741` refusing all
  four hidden schools on ordinary edits is working as designed, and a generated world topping
  out at `biome_variant` index 103 is correct. The session that found it nearly filed it as a
  bug before the ruling came. What remains is **B3 below**: corruption can seat a node and the
  ground never wears it. The evidence below is kept because it maps the route, not because the
  gate is a defect.
- Twelve ley
  layers are created and 156 variants published, but the maximum `biome_variant` index used is
  103 — exactly the top of the known block, zero hidden-school variants. Running all twelve
  schools through the gate: `weave`, `umbral`, `fire` pass; `blood`, `void`, `rot`, `eldritch`
  are **refused** at `terrain_history.py:741`, which validates edits against `KNOWN_SCHOOLS`.
  So an age skip cannot seat a hidden school. [verified]
  - The consumer is ready — injecting a synthetic `ley_blood` field produced `ocean.blood`,
    `desert.blood`, `grassland.blood`. The machinery handles twelve; one gate refuses four.
  - **Three independent producer gaps**, found from two directions by two sessions that did not
    know about each other: this gate, `terrain_corruption.corrupt()` (a standalone API wired
    into nothing), and `pending_ley_edits` with no applier (`SDET-LEY-QUEUE-NO-APPLIER`).
  - Card deliberately not written until the user says whether the gate is a deliberate lock or
    an oversight — that decides bug card versus feature card.

### Native
- **98 ok, 68 FAIL, 8 ERROR, 2 skipped.** Six methods, at least four subsystems — city layout,
  hinterlands, ports, nests, per-people fields, budgets, founded cities, 39 individual cities.
  **Root causes unread.** The earlier "five failures, all the SCHOOLS lag" account was wrong and
  I let it stand too long. The 8 ERRORs are exceptions, likely a different family from the 68
  assertion failures — not asserted. [open]

### Performance and scale
- **City count tracks the raster at ~0.035 × cells**, so a phase-16 world at 513 is on the order
  of nine thousand cities and hours of planning. **This, not the ceiling, is what blocks a full
  513 world.** Extrapolated from two points.
- Peak relief at five octaves is **11.6 km** on a 31,831 m radius, phase 5, before erosion.
- `test_showcase` builds a **338,680,135-byte** bundle at **2,258 MB** peak, >25 min in one test
  method. CI pays the same cost.
- **The suite runner orphans its child on interrupt** — 2.2 GB and 894 MB ghosts both survived a
  stop. This is how a machine ends up saturated by runs nobody believes are running.

---

## 4. The grid ceiling (ruled: 1025) — what it did and did not deliver

Landed in `4713f9a`, comment corrected in `da83b34`, scoped in `651ab00`.

```
plate   17    33    65   129   257   513  1025
 3-4     1     2     3     4     5     5     5
 5-16    0     1     2     3     4     5     5    <- contains the default 12
17-48    0     0     1     2     3     4     5
```

- Octave admission is a function of **grid size and plate count**. The radius cancels
  (`wavelength/step = 1.6(n-1)/(2*pi*sqrt(count))`), confirmed empirically at four radii.
- **34 of 46 legal plate counts contradict the middle row.** Legal range is 3..48.
- **"1025 adds no octave over 513" is false for 32 of 46** — in the 17..48 band, 513 resolves
  four and 1025 is the first size resolving five. True at the default.
- No world on disk has more than **2 of 5** octaves. The conformance reference world has zero.
- Age advancement was the only thing capped; generation always allowed 1025.

---

## 5. Held, not filed

One session's user instructed it to hold. **Thirteen findings are drafted and deliberately not
on the board**, no space reserved. Its two measurement results carry confounds it stated itself:

- **Containment** — seed 42's vocabulary is a *prefix* of seed 73's on three of seven axes.
  Seed 73 has **2.2× the land**, which makes containment more likely *by construction*, so the
  confound is a plausible complete explanation and one asymmetric pair cannot separate them.
- **Tier-0 inversion** — 79% → 85% signposts as land doubles. **Two points**, same confound.
  Not a trend. Flagged by its author as the finding people will most want to be true.

Its mechanism findings carry no such hedge and stand: sub-cell clearance, octave admission, the
wonder rounding.

---

## 6. Method findings

The dominant defect class, in the code and in our own analysis:
**a predicate that returns a plausible answer to a question nobody asked.** None of these
errored; none looked wrong on the page.

| Instance | Right where you looked |
|---|---|
| `path.endswith('status')` | until `route_status` and `plan_status` |
| `pathlib.Path.match` for an `fnmatch` glob | `*` crosses `/` in one and not the other |
| counting `id` where the field is `kind` | ids are unique by construction |
| a 680-row table counted as 1360 entries | `id` and `name` each counted |
| `assertIn('max_grid=257', ...)` as equality | `'max_grid=257' in 'max_grid=2570'` is True |
| `\b` through a heredoc → literal `0x08` | the regex matched nothing, and read correctly |
| `height > 0` for a domain test | the generator selects on `water_type` via `readers.cells` |
| exclusive time by suppressing nested calls | exact for any producer that runs once |
| plate counts 9–16 to prove invariance | every sample inside the one band where it holds |
| `add_nests` call sites in one file | 4 sites and 10 executions tree-wide |

**Rules that came out of it, in order of usefulness:**

1. **If the run is cheap, the run is the answer.** A cheap run beats any amount of careful
   reading. Three sessions corrected each other on `add_nests` while all three kept reading;
   one wrapper and 70 seconds settled it.
2. **When a block defines its own selector, import it.** Do not reimplement a domain, filter
   or eligibility test you are auditing.
3. **Sweep the declared legal range, not a plausible neighbourhood** — and find the range in
   the code. Mine was four lines from the code under test and I never looked.
4. **Printing the evidence is not reading it.** Twice tonight someone published the data that
   refutes their own claim and read the adjacent column instead.
5. **Read a cancellation proof for exactly what it cancels.** Radius really did drop out; it
   got silently extended to plate count, which it never covered.
6. **Agreement is evidence only to the extent the methods differ.** Three forms: both reasoned
   and neither ran it; both executed but shared a wrong selector; both executed correctly over
   the same unrepresentative sample. "Four sessions derived it independently" collapsed into
   one derivation with four witnesses. *Ask what a peer varied, not just what they ran.*
7. **Counts are immune to contention; timings are not.** Counts, call graphs, digests and byte
   comparisons never need to queue. Only wall time, peak memory and per-producer shares do.
   This is a **scheduling** rule as much as a method one: half of what was queued for a quiet
   machine never needed one, the call graph that ended three rounds of wrong reasoning cost
   seventy seconds on a saturated box, and three sessions kept producing structural evidence
   through an hour in which no clean timing could be taken. The coordinator serialised work
   that did not need serialising.
8. **Execution count is not cost.** `city_fate` runs 13 times — most-executed instrumented
   function in the generation, absent from the producer list, entirely inside the frame under
   suspicion — and costs 1.4 ms. It had every surface feature of a hidden term. The hidden
   term was `add_nests` at 49.2%, in a frame nobody was looking at.

**Conventions worth keeping:** one session owns the index; every card names what it did *not*
establish; record findings you dropped so they are not re-found; state a falsification
condition; a peer relay does not override a user instruction.

---

## 7. My own errors

Recorded because several reached the user before they were caught.

- **Inferred process ownership from a process table** and issued instructions on it. Told a
  session to kill a probe that never existed; it discarded a legitimate measurement on my word.
- **Declared the machine clear four times without verifying it.** It was saturated
  continuously; an artifacts stage started 24 seconds after I told one session the window was
  empty. Every release was mine, issued from a picture I could not see.
- **Reported sub-cell clearance as unhedged mechanism.** False above size 129 — the sizes the
  new ceiling makes attractive.
- **Reported the containment result without foregrounding that the confound cuts toward it.**
- **Claimed the settlement field contradicted its layer.** It does not; zero settlements differ
  in any document. I reached for a second witness without checking it was independent.
- **Claimed the octave table was invariant across plate counts** on a sample drawn entirely
  from the interior of the one band where it holds, and nearly had a correct comment in the
  tree replaced with a wrong one.
- **Asserted "1025 adds no octave over 513"** while pasting the table that refutes it into
  three messages.
- **Reported three `add_nests` call sites** having grepped one file, inheriting a framing.
- **Propagated a creature tier range, a world scale off by 10×, and coverage arithmetic**
  wrong, earlier in the sweep.
- **Let "five failures, all the SCHOOLS lag" stand** as the native account when it was 68.

---

## 8. Open, unverified, or queued

- Native root causes — 8 ERRORs first, then the 68 assertion failures as separate families.
- SDET's phase-16 cost ladder at 33/65/129 — wall clock and peak RSS, no producer attribution.
  Blocked on a quiet machine that has not arrived.
### The profile split — resolved, and the original was wrong by a factor of five

Measured with a stack-based instrument reporting its own coverage (**41 of 41 producers
wrapped, none uninstrumented**). Seed 42, size 17, phase 16, contended box. Wall 71,028 ms,
accounted 70,292, unaccounted 735. [owner-verified]

```
34,968 ms  49.2%  add_nests          x10
31,712 ms  44.6%  fill_cities        x1
 1,691 ms   2.4%  fill_hamlets       x1
   503 ms   0.7%  add_settlements    x10   (inside apply_world_scale)
   346 ms   0.5%  fill_castles       x1
   205 ms   0.3%  add_world_society  x8
    26 ms   0.0%  age_transition     x2    <- exclusive
     1.4 ms       city_fate          x13
```

- **`add_nests` is 49.2% and was published as 9.0%.** `add_nests` + `fill_cities` = 93.9%.
- **`age_transition` is a scheduler, not a producer** — 26 ms exclusive, down from the 29,414 ms
  the old instrument charged it. **99.9% of its credited time belonged to its children.**
- **`city_fate` was the named candidate and is 1.4 ms** — 0.002% of the run, despite being the
  most-executed instrumented function at 13 runs. I named it as the likely hidden term on the
  strength of its execution count. **Execution count is not cost**, and this is the cleanest
  refutation of that instinct available: the hidden term was `add_nests` all along, hidden in a
  different frame than either of us was looking at.
- **`terrain_area.apply_world_scale` is a producer whose name says otherwise** — it raises
  humans, colleges, seasonal food, world society and nests inside a function named for
  rescaling coordinates. That is where 5 of the 10 `add_nests` executions live, and why
  grepping `terrain_history` could never have found them. Those five cost **~25 ms combined**
  and are genuine no-ops at phases 1–5. [verified]
- **The real cost localises to five executions at ~7 s each** — one at stage 13, four inside
  `age_transition`.
- **Control moved, and the movement is explained rather than excused.** `fill_cities` fell 8.0%
  because the old profile predates `422f9c3`, the height-only sampler change that targeted
  exactly the city and hamlet grids. Corroborated by `fill_hamlets` at −7.8% — same patch, same
  proportion, independently — while `fill_castles` moved −3.1% on an untouched sampler, which
  is the contention floor. A control cannot be null across a code change.
- **A lead, offered as a lead.** Within one `age_transition`, `add_nests` runs twice — directly
  at `terrain_history.py:322` and again via `rebuild_tail` at `:307` (called from `:379`). Four
  of the five expensive executions are in that frame. The world does change between them, so
  redundancy is **not** claimed; but if one of the two per age is avoidable it is roughly 14 s
  of a 71 s run. Wants whoever owns the nest contract, not a performance pass guessing.
- `PERF-CITY-COUNT-TRACKS-RASTER` cites the old shares and is being corrected, with each
  measurement marked with its tree so nobody reconciles a pre-`422f9c3` number against a post.
- Adding to §6: **an instrument must report its own blind spots.** Both the call-graph script
  and the fixed profiler state their coverage explicitly rather than leaving it inferred from
  the absence of a warning. A survey that cannot say what it missed will always report full
  coverage.
- Biome frequency table — wants a phase-16 world at 129 or 257.
- Determinism outside seed 42 size 17, with villain paths live.
- Coverage magnitude — needs re-running; records were added during the sweep.

---

## 9. Rulings obtained during the sweep, and what not to re-open

These were given verbally during the run and were written down nowhere. They are recorded here
because each one, if lost, turns a correct behaviour back into a plausible-looking bug.

**Design rulings on magic schools:**

- Eight schools are expected in a generated world; twelve are reachable only post-generation,
  and unlikely.
- Villain triggers bring hidden-school nodes into existence after generation.
- Converting a node to a forbidden school must be a capability that exists.
- The generator must never produce a forbidden school independently.

**Settled — do not re-open. Each would look like a defect to a fresh reader:**

1. **Desert is not a defect.** It is absent from small worlds because the moisture minimum
   falls monotonically with the raster (0.589 at size 17, 0.457 at 33, 0.294–0.223 at 65) and
   desert appears exactly when it crosses ~0.3. *Anyone who retunes the desert thresholds
   against a size-17 world breaks warm worlds permanently.*
2. **The gate at `terrain_history.py:741` is correct.** It refuses all four hidden schools on
   ordinary leyline edits, which is what the rulings above require. One session nearly filed
   it as a bug before the ruling arrived.
3. **A generated world producing only eight schools is correct.** Max `biome_variant` index
   103, exactly the top of the known block. Working as designed.

**Still a real gap, and not covered by those rulings:** corruption can seat a hidden-school
node and the ground never wears it. `terrain_corruption.py` contains **zero** references to
`evaluate_networks`, `add_biome_variants`, `refresh_environment` or any `ley_` field. The chain
was proved by running it: seat a node and `ley_blood` stays 0.000 with zero hidden cells; call
`evaluate_networks` and it reaches 1.129; call `add_biome_variants` and a hidden cell appears.
Only the connecting call is missing. [verified]

