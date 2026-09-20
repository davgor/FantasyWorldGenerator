---
modules: []
---

# End-of-day handoff — 2026-09-20, against `7d94bf5`

Successor to `docs/reviews/651ab00-coordinator-roll-up.md`. That document is now stale in four
places that a fresh reader will act on; §3 here says which and why. This one records the state of
the tree at the close of 2026-09-20, after a day in which **two sessions edited it concurrently and
nothing was committed**. It has been audited against the live tree after assembly, and the audit's
corrections are folded in — where a number below differs from an earlier brief, the number below is
the re-measured one.

**Status key.**
`[ran]` — this writer or the audit executed it, after every capture closed.
`[capture]` — one of four independent read-only captures ran it; the count of agreeing captures is
given where they overlap.
`[read]` — read out of a file in the tree, not executed.
`[relayed]` — comes from a session brief only. No capture verified it. Treat as a lead.
`[open]` — not established by anyone.

**Almost nothing in this document is a measurement this writer took of the simulation.** The suites
were run by four captures between 12:23 and 12:40 CDT; the cheap gates, the line citations and the
three resume-item suites were re-run afterwards and are marked `[ran]`. Where captures disagree the
disagreement is stated, with the belief, in §8.

---

## 0. Tree state — read this before touching anything

| | start of captures | close of assembly |
|---|---|---|
| HEAD | `7d94bf5cbd5ff90f1f4ea9bed135ce20a3f08dd7` | `7d94bf5cbd5ff90f1f4ea9bed135ce20a3f08dd7` |
| dirty paths | 133 (12:23:28) | 136 (12:41:32) |

HEAD did not move all day — it was committed at 01:42 and is a sound start-of-day reference.
**Everything both sessions did today is uncommitted working-tree state on top of it**: at the close,
37 paths of it untracked, 93 modified, 5 deleted, 1 renamed. `[capture]` ×4, `[ran]` at the close.

Those 136 exclude this document, which did not exist yet when they were counted. Once it landed,
`git status` reads **137**, 38 of them untracked, and the 137th is this file. A fresh `git status`
showing 137 is therefore not the tree moving under you. `[ran]`

Re-read at 13:07:48 after the last suite finished: HEAD `7d94bf5`, 136 dirty paths, unchanged from
12:43:35. Session B's newest write is still the time-advance conformance record at 12:37:34. **The
quiet window is thirty minutes, not eleven.** `[ran]`

The tree moved under every capture. Session B's last observed writes were at 12:34 and 12:37; the
newest changed files are `Sim/icarus_sim/terrain_time.py` (12:34:27),
`Sim/icarus_sim/terrain_time_schedule.py` (12:34:21), `Sim/tests/test_time_advance.py` (12:34:35),
`docs/time-advance.md` (12:37:31) and `docs/conformance/time-advance.md` (12:37:34). `[ran]`

Thirty quiet minutes is still not an idle signal. Check mtimes before assuming otherwise.

---

## 1. Resume here

Four things, each already scoped. The first is now **discharged** — its results are below rather
than its instructions.

**1. Discharged: the three suites session B's last writes invalidated are green.**
`Sim/tests/test_time_advance.py` was 34 tests when two captures measured it, and was rewritten at
12:34:35. Re-run at 13:00 against the rewritten file: **37 tests, 37 pass, 147.136 s**.
`Sim/tests/test_corruption.py`, re-run after B's 12:21 corruption landing: **31 tests, 31 pass,
463.502 s**. `tools/verify_provenance.py`, re-run after the 12:21:18 rewrite of the pinned
`Sim/icarus_sim/terrain_patch.py`: **exit 0, 79 files**. All three resume-item-1 suites are green
and the item is discharged unless the clock modules move again. *Falsified if* the clock modules'
mtimes have moved since 13:07, in which case repeat. `[ran]`

**2. Fix the native parity harness, do not hunt a bug in `Core/astrology.cpp`.**
The one native failure everybody has been calling a real port divergence is a **phase mismatch in
the comparison**. **The layer is `lunar_sensitivity`** — written by the astrology module, not a
layer named astrology — and the failure is the subtest `layer='lunar_sensitivity'` inside
`test_native_world_reproduces_the_reference_world_for_one_seed`. Grep for that name, not for
"astrology", when you go to exclude or re-phase it. The native `world` driver operation calls
`generate_world` and never advances an age; the Python oracle is a full `generate_request` whose
history refreshes that layer twice. A probe over one oracle run found six recomputes, snapshots 0–3
bit-identical, and a base-stage-versus-post-age gap at cell `[0][0]` of
`0.002732700729678461` — **bit-for-bit the number
the test reports**. The printed tolerance `1.0005335334775148e-06` reproduces exactly as
`1e-06 + 1e-09 * 0.5335334775149114`, confirming the assertion's reference operand is the post-age
value. Fix: compare that layer from the `ages` operation, or exclude it from the base-world
comparison. `[capture]` ×1, with a probe; ×2 disagree — see §8. *Falsified if* a matched-phase
comparison still diverges, which nothing currently tests.

**3. Land `terrain_recipes.derive_water`'s river-threshold cap.**
One line, in a provenance-pinned file, and the cheapest genuine defect on the board. The absolute
arm reads `max(.01,min(1,area/110))` at
`Sim/icarus_sim/terrain_recipes.py:57` — capped at 1 km² against the 48.27 km² a 200 km world
actually resolves, 48× too small. It is dead code on recipe 3 because the request path derives its
own threshold, and it is a loaded gun the moment `auto_parameters` is reached: it returns rivers to
near-total saturation. Either scale it by `terrain_scale.runoff_scale(circumference)` or delete the
function. Needs a provenance revision row (§7 T1). `[capture]` ×2

**4. Board hygiene, fifteen minutes, high value.**
Seven cards filed today are absent from `board/README.md` — `PERF-SHOWCASE-TEST-COST`,
`PERF-SUITE-RUNNER-ORPHANS-CHILD`, `PLAYER-FOUNDED-SETTLEMENTS`, `SCALE-METRE-CONSTANTS-COLLAPSE`,
`BIOME-EXPOSED-ROCK-NEEDS-RELIEF`, `BIOME-MARSH-IS-THE-RIVER-MASK` and
`SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE` (0 occurrences each). The README still lists TIME-ADVANCE
and TIME-LIVENESS as "queued behind the current wave" when both cards read delivered.

**Two** cards exist at two paths each, both redirect-stub-plus-real-card:
`BIOME-TUNDRA-SNOW-UNREACHABLE.md` (1,217-byte stub in `backlog/`, 18,202-byte card in `done/`) and
`PRODUCT-WORLD-DISPOSABILITY-DECISION.md` (1,328-byte stub in `backlog/`, 10,508-byte card in
`done/`). Other cards link to both paths. Four cards should move to `done/`:
`SDET-WORLD-SCHEMA-SURFACE` (it says so itself), `NOMAD-CORRUPTION-CONTRACT`, TIME-ADVANCE,
TIME-LIVENESS. `[capture]` ×2, stub pair `[ran]`

**What is NOT a resume item, and why.** Do not re-run the full `Sim` discovery pass yet. The
figure in circulation — 13 failures / 200 errors — straddled session B rewriting twenty-plus files
and is unattributable; three captures declined to re-take it for the same reason. It is worth
taking, on a quiet box, now that B has been quiet for thirty minutes. `[capture]` ×4

---

## 2. What shipped today, by ruling

Eight user rulings were applied by session A. All eight are verified landed.

**0.1 — Worlds are disposable.** `docs/decisions/023-world-compatibility-policy.md` exists and
records the ruling against card `PRODUCT-WORLD-DISPOSABILITY-DECISION`, whose real card is now in
`board/done/` — with a redirect stub left behind in `board/backlog/`, see §1 item 4. A generated
world is a disposable artifact; no migration is owed. `[capture]` ×2

**0.2 — Tombstone biomes 1 (tundra) and 6 (snow); re-point the cold assets.**
`terrain_biome_catalogue.UNREACHABLE_BIOMES` is `frozenset({1, 6})`; `natural_catalogue()` returns
13 and `reachable_natural_catalogue()` returns 11. Both rows keep their positions and carry
`reachable: false` beside an `unreachable_note` naming the ruling by date and stating that the
ground is covered by 16 `cold_tundra` and 17 `land_ice`. That note lives in the source registry, at
`Sim/icarus_sim/biomes.json:23` and again at :70. It is **not** in what the accessor emits — those
rows still carry only id, core, name, color and asset_id — so do not expect to find the note by
calling the accessor. The rows are retained deliberately, because `biome_variant` is a flat index
into the 13×12 cross product and deleting a row renumbers every saved world.
`natural_catalogue()` itself is measured untouched, and **the reason is recorded rather than
reconstructed**, contrary to what the draft said. It is the docstring of the accessor, at
`Sim/icarus_sim/terrain_biome_catalogue.py:83-88`, where `terrain_history` compares the two biome
dicts against it for equality, so they are world-output bytes and a key added there would be a
schema change — which is why the tombstone got its own accessor instead. `[capture]` ×2, registry
row and docstring `[ran]`

**The asset re-point is 63 rows, not the forty-six the closed card states** — 46 named a tombstoned
`biome_ids` entry and 19 named a tombstoned `biome_variant_ids` entry, union exactly 63, with 0 rows
still naming a tombstone. The catalogue is 492 assets before and after: 0 added, 0 removed.
`[capture]` ×2

**0.3 — Super villains exist; the simulation ends with promotions.** `SUPER_TIER = 1.` at
`Sim/icarus_sim/terrain_villains.py:23`, with `promote()` at
`Sim/icarus_sim/terrain_villains.py:439`. The stage gate and the advance path are at
`Sim/icarus_sim/terrain_history.py:550` and at :825 — generation stage 15, and the final age of an
`advance_age_request`. `villain_rise`'s default moved **0 → 0.5**, so a default world now ships a
`villains` block; `villain_rise: 0.` remains a real off switch. Measured on a default seed-42 size-17
generation: 4 people, 4 standing, 0 fallen, 4 carrying a `promoted` log event, all at tier exactly
1.0, ceiling 4 over 10 regions at density 3. The highest **unseated** region sits at tier 0.520 —
accumulation alone would have seated nobody, which is the argument `promote()` makes for existing.
`Sim/tests/test_super_villains.py` is 24/24 green. `[capture]` ×3

**The native half of this ruling is not started** — see §5(a) item 7, and read §4.2 before quoting
any parity number, because the parity suite pins villains off.

**0.4 — Monsters should feel biome-specific.** All 369 monster profiles carry their own
`biome_weights`, each naming all 11 reachable biomes with a nonzero weight; the 311 animals carry
none and resolve theirs through the `roles` table. Separately, every one of the 680 profiles carries
a nonempty `weights` map of terrain and ley fields — 333 name one field, 323 two, 24 three, led by
moisture (334 rows), wetland (89) and fishing_productivity (78) — plus temperature bands, and 380
carry a nonempty `requires`, of which 328 are monsters and 52 are animals. (The draft gave 328 as a
figure about all 680; it is the monster subset. Re-measured at the close.) Independently: **0 of 369 monsters carried `biome_weights` at HEAD and 369 of 369
carry one now**, and every monster table names every live biome, because an absent key is exclusion
rather than neutrality. `terrain_nests.profiles()` now raises on a monster without one, and
`Core/profiles.cpp` mirrors the requirement in the native loader, so the old `return 1.` fallback is
unreachable for the shipped catalogue on both sides. `[capture]` ×3, corrected `[ran]`

**0.5 — Non-Earth is monster, Earth is animal; monsters bear an animal likeness.** The partition is
exact and clean across all 680: `real=False` with a `likeness` = **369**; `real=True` with no
`likeness` = **311**; both mixed combinations = **0**. 98 distinct likeness anchors, 41 used exactly
once, top anchors `chimpanzee` 52, `western-gorilla` 35, `slug` 21. 12 monsters carry a
`likeness_secondary`. `[capture]` ×3
**The open half:** `likeness` and `likeness_traits` are read by **zero lines** of `.py`, `.js`,
`.cpp` or `.hpp` in the tree. They do reach the generated exports, so an out-of-tree asset generator
can read them — but nothing carries a likeness onto a placed site or into the exhaustive asset list.
If the ruling meant the asset and animation generators should resolve a monster to its animal
without loading the profile catalogue, that binding has not been built. `[capture]` ×1

**0.x — File the two findings the code lens held back.**
`board/backlog/PERF-SUITE-RUNNER-ORPHANS-CHILD.md` and `board/backlog/PERF-SHOWCASE-TEST-COST.md`,
filed 10:07 and 10:08. Both state in their State line that they were found auditing `233182e` and
held off the board while that review was in flight. `[capture]` ×1

**2.0 — Fix the `island_habitat` / `freshwater_distance` regression.** Confirmed live on a seed-42
size-17 phase-12 world at the 200 km default, counting every grid cell with `water_type <= 0`: 50
land cells, `island_habitat` nonzero on 1 (max 1.0, no longer identically zero),
`freshwater_distance` nonzero on 17 (max 20,745.1 m), `rain_river` on 33 of 50 rather than on every
land cell. `effective_config.river_threshold_km2` resolves to **48.270567981093244 km²**, exactly the
figure the derivation's docstring quotes. The island floor is now
`float(component_area<land_total*.15)` at
`Sim/icarus_sim/terrain_ecology.py:148`, with the absolute 3 km² arm dropped and mirrored in
`Core/ecology.cpp`. Pinned by `Sim/tests/test_layer_scale_regression.py`, 7/7 green.

Through that pinned test's own `sphere_grid` helper, which drops the two poles, the same world reads
47 land cells, island habitat on 1, freshwater distance on 15 and rain river on 32 — and 32/47 =
0.6809 is the seed-42 fraction that suite's docstring records. **State which convention you are
using before quoting either set.** `[capture]` ×3, conventions `[ran]`

**3.0 — Land ice gets critters and plants; every roster biome reachable through seed-driven
generation.** 10 of 21 role tables gained a `"17"` key, each weighted strictly below that role's own
`"16"` where one exists, and those 10 are exactly the roles whose weights changed: `ambush_predator`,
`apex_predator`, `bird_of_prey`, `bird_other`, `herbivore`, `large_herbivore`, `marine_mammal`,
`mustelid_small`, `small_prey`, `waterfowl`. **191 of 311 animals** now resolve a land-ice weight
through their role. Pinned by `Sim/tests/test_biome_habitat_coverage.py` (4/4, including
`test_land_ice_stays_below_cold_tundra`) and `Sim/tests/test_biome_reachability.py` (8/8, including
`test_every_surviving_biome_has_a_generated_world`). Both suites run at phase 10, on the recorded
equivalence that the biome layer stops changing after stage 9. `[capture]` ×3

**A danger gradient shipped alongside them**, closing the nests half of
`CONTENT-NO-DIFFICULTY-GRADIENT`: a continuous rate multiplier with a floor of 0.2, wired live inside
the placement lambda and mirrored in `Core/nests.cpp`. It is a ratio of squares rather than an
exponential, specifically so that no last bit depends on the linked libm. Measured at the 200 km
default, span 5,381.7 m: tier 1 runs 1.000 at a settlement's doorstep to 0.202 far out, tier 5 runs
0.200 to 0.998, tier 3 is flat at 0.600, crossover at exactly one span. **That span is computed from
the design radius, not from the radius the world document publishes** — see T8 before reproducing it.
`[capture]` ×2

**Also landed, not on the ruling list:** the world contract widened from 6 required keys to 16 and
from 17 declared properties to 54; `Contracts/schemas/villains.schema.json` was published;
`pending_ley_edits` was removed entirely (the only surviving references are historical prose and
assertions that it stays absent); `Sim/key_locations/catalogue.json` went revision 2 → 3 with five
tier-3 wonders raised off a silent `per_1000_km2: 0.0`; and `tools/validate_repo.py` now parses the
world document instead of only byte-comparing it. `[capture]` ×2, revision 3 `[ran]`

---

## 3. The four findings that changed the picture

Each of these overturns something a reader of the previous roll-up will believe.

### 3.1 The layer regression was the planet, not the code

`board/reviews` and the roll-up's §2 lead with "two published layers collapsed between generator 9
and generator 16", with a gen-9/gen-16 table and a bisect hint. **That framing is refuted in the
tree.** `board/backlog/SCALE-METRE-CONSTANTS-COLLAPSE.md:17` states it flatly: recomputing the island
rule against all twelve worlds under Artifacts reproduces the published layer cell-for-cell for
generators 8 through 16 alike. The variable was the world's **width**, not the generator's version —
commit `21df9aa` moved the default world from 11.15 km around to 200 km and left behind every
constant authored in absolute metres. `[read]`, `[capture]` ×2

This matters beyond the two layers, because it is a **class**: the constant does not error, it stops
discriminating. A published layer becomes a constant and every consumer downstream reads a field
that is the same everywhere. Two members are fixed (island floor, river threshold); five are open
and two more are latent — see §5. The roll-up's §2 bisect hint should be struck; it sends a reader
to bisect a generator version that is not the variable.

### 3.2 The corruption card was refuted the same day it was filed

`MAGIC-CORRUPTION-NEVER-REACHES-GROUND` claimed corruption seats a hidden-school node and never
recomputes the derived fields. It does recompute: the call is `rebuild_tail`, indirect, and runs all
three of the passes the card said were missing. The card's evidence was a grep for the callee's name
inside the caller's file — true that the file holds zero references, false that the call is therefore
absent. The card is in `board/done/`, marked REFUTED, and what was found in its place is
`CORRUPTION-OPPOSING-A-REVEALED-GOD-CRASHES`: the crash is closed, the design question is open.
`[read]`, `[capture]` ×2

The generalisable half is the method, not the defect: **a grep for a callee's name inside a caller's
file cannot establish that a call is missing.** The same near-miss bit an independent capture today
in a different place — see §8.

### 3.3 The native ERRORs were a rendering crash, not a failure family

`board/backlog/NATIVE-PARITY-HARNESS-SHAPE.md:124` records it. Every one of the ERRORs was a
`RecursionError` raised inside unittest's own diff rendering for a 1089-element `assertEqual` —
measured standalone, two 1089-element float lists take about seven minutes to reach a 1000-frame
recursion limit.

**The count itself is contested.** That card's section heading and the previous roll-up say eight,
while the card's own Measured residual says six, and
`tests/test_native_world.py:851` records "fifty-five mismatched grids and six RecursionErrors".
**Six is the better-sourced figure**: it comes from the test module itself rather than from a prose
heading, and it is the figure consistent with the 68 failures / 6 errors baseline quoted in §4.2.

So the assertion found a real divergence, spent minutes on it, and then crashed while explaining it:
layer name gone, mismatch count gone, a difflib stack trace printed under the heading ERROR. **It was
read as a distinct family needing its own investigation and cost a review cycle.** The harness now
routes whole-layer comparisons through a comparator using exactly the same predicate, reporting the
count and the first six differing cells. `[read]`

Consequence for the reader: the roll-up's standing instruction to run `test_native_world` alone and
take the ERRORs first is a wild goose chase. There are zero errors now, confirmed by four
independent runs. `[capture]` ×4

### 3.4 Desert was never broken, and the evidence for saying so was itself wrong

`docs/reviews/651ab00-coordinator-roll-up.md:455` records the ruling and, at :459, the correction
appended the same day. Both halves matter. The ruling stands — **do not retune the desert thresholds
against a small world** — but the monotonic moisture table given as its mechanism was measured on the
retired ~11 km world documents, not on this tree; at raster 17 here desert appears in 222 of 232
seeds. The restatement is the durable form: a knob tuned against a degenerate corner damages the
configurations that work, whether or not the corner is still degenerate. `[read]`

The biome that genuinely is unreachable at the default raster is `5 exposed_rock`, and it is carded
with its mechanism and its measured cost rather than fixed. See §5(b).

---

## 4. Test and gate state, exactly

This is the section most likely to be misread. **Red is not the same as broken here.** Three suites
are deliberately red by design, one pins a long-standing unfixed defect, and only the native parity
suite carries anything that could be called new.

### 4.1 Gates — all six steps of the checks stage pass

The brief in circulation says four gates. The `checks` stage runs **six**. `[capture]` ×1, `[ran]`
for the fifth row.

| # | Gate | Exit | Final line |
|---|---|---|---|
| 1 | `build_asset_registry.py --check` | 0 | Unreal asset registry current: 1707 bindings |
| 2 | `export_catalogues.py --check` | 0 | 13 profiles, 12 entities, 7 building packs, 680 nest profiles |
| 3 | `export_controls.py --check` | 0 | 209 controls (1 inert, 201 open, 7 pinned), 21 honoured natively |
| 4 | `verify_provenance.py` | 0 | 79 extracted files from `d551767cb1c3bd259bb00f56be1e52c2182c5ec3` |
| 5 | `docs_check.py` | 0 | 201 documents, 128 modules claimed or declared; 9 warnings |
| 6 | `compileall -q` over Sim and tools | 0 | (silent) |

`validate_repo.py --stage checks` exits 0. `[capture]` ×1
The third gate is a **session-B addition** nobody's brief listed. It passes.

**This document is itself inside the checked set** — `docs/*.md` is an fnmatch glob and `*` crosses
`/`, so adding it moves row 5 to **202 documents**. It was written to add zero warnings, and that was
verified by running the checker, not reasoned about. See T5.

**`docs_check` REFUTES the state everybody was handed.** The claim was "exits 1 with exactly three
COVERAGE errors, one per session-B module". It exits **0**, with zero ERROR lines of any kind. All
four captures agree, and it was re-run at the close: 201 documents, 128 modules claimed or declared,
9 CITE warnings, not blocking. What is measured is that figure against **185 documents and 124
modules at HEAD**; the attribution below is the reconstruction of how the gap closed. Session B
closed its own coverage gap: `docs/time-advance.md`, `docs/conformance/time-advance.md` and
`docs/conformance/request-failures.md` are new, `docs/conformance/nomads.md` was extended, and two new
decision records landed — `024-fallen-claim-decay.md` and `025-controls-are-a-machine-contract.md`.
`[capture]` ×4, `[ran]`

**The 9 warnings are 5 pre-existing plus 4 new, and this was proved rather than reasoned** — one
capture extracted HEAD into a scratchpad with `git archive` and ran the checker there, getting
exactly 5 warnings over 185 documents and 124 modules. The audit reproduced that archive proof
independently, so nobody needs to take it a third time. All 9 are CITE line-drift: today's edits
moved cited lines out from under still-correct citations. **None is a code defect.** The four new
ones are in `Core/README.md`, `NATIVE-PARITY-HARNESS-SHAPE.md`, `PRODUCT-CAPABILITY-RANGE-DIVERGENCE.md`
and `SDET-VILLAIN-FALL-UNREACHABLE.md`, drifting through `terrain_world.py`, `terrain_villains.py`
and `world_driver.cpp` — files both sessions touched today, so do not attribute them to a session
without a per-hunk diff. `[capture]` ×1, `[ran]`

### 4.2 `tests/test_native_world.py` — 15 tests, 10 failures, 0 errors

The shape is confirmed by four independent runs, reproduced by the audit, and reproduced a third
time by the final verification pass: 15 tests, 10 failures, **0 ERROR lines**, and every value in
the table below bit for bit, plus the tenth failure's `0.002732700729678461` against its
`1.0005335334775148e-06` tolerance. **The wall time is not**: the same 15 tests with the same 10
failures were measured at 282.249 s, 304.552 s and 314.628 s on a box carrying up to eight
concurrent Python suites, and at **267.622 s** on a quiet one — which is the contention effect in
§8.3 shown directly rather than argued. `[capture]` ×4, shape and table `[ran]`

**This suite does not test the default world.** The oracle is pinned to `villain_rise: 0.` at
`tests/test_native_world.py:125-133`, with a comment saying Core has no villain model at all. Ruling
0.3 made villains default-on at 0.5, so the 15/10/0 result describes a **villainless** world and says
nothing about what `generate_request` now produces by default. Anyone quoting the parity number as
coverage of today's generator is quoting a different configuration. `[read]`

**Nine float-tail failures.** Six are last-ulp on normal-magnitude values; three are cancellation-
amplified rather than last-bit.

| Subtest | Field | Native | Reference |
|---|---|---|---|
| hamlet-8 | delivered_food | 119.4796596384166 | 119.47965963841659 |
| hamlet-23 | delivered_food | 73.80779080233194 | 73.80779080233195 |
| hamlet-28 | delivered_food | 69.37921574905258 | 69.37921574905259 |
| hamlet-49 | delivered_food | 930.4443830989644 | 930.4443830989643 |
| hamlet-73 | delivered_food | 0.747715875008961 | 0.7477158750089608 |
| hamlet-17 | irrigation_benefit | 2.5324759650446893e-12 | 2.5324763987255583e-12 |
| hamlet-48 | irrigation_benefit | 2.0421143664961505e-09 | 2.042114255473848e-09 |
| hamlet-56 | irrigation_benefit | 2.3539637350467046e-07 | 2.3539637356018162e-07 |
| war-2-0 | pressure | 0.8019473845702728 | 0.801947384570273 |

**Do not file "nine last-ulp floats" as one family.** `hamlet-48` is a relative divergence of 5.4e-8
and `hamlet-56` of 2.4e-10 — eight and six orders worse than an ulp. Their absolute gaps are tiny,
but the mechanism is catastrophic cancellation amplifying an upstream rounding difference, and the
card records the same reading. Which term of the farming arithmetic carries it is `[open]`.
`[capture]` ×2

**The tenth is a harness phase mismatch, not a port divergence.** See §1 item 2. Two captures
classified it as a real divergence from the assertion text alone; the one that instrumented the
oracle refuted them. Believe the probe. `[capture]` ×1 with a probe, ×2 disagree

**Two things the harness answered in passing.** The new access-path column added to the native driver
was built to tell a routing divergence apart from arithmetic inside one edge; **no access assertion
failed**, so the six-hamlet question is arithmetic, not routing. And the `dominant_magic` divergence
that `NATIVE-PARITY-HARNESS-SHAPE` records as a real one — 33 of 1089 cells — **did not reproduce**.
That card is stale on that point, and with it the hypothesis that the astrology divergence travels
with it through the aged ley networks. `[capture]` ×2

### 4.3 Deliberately red — these are working as intended

Do not make these green as a side effect. Each was written to fail against the tree that introduced
it, each has a card, and in two cases the card states the expected result verbatim. All four
reproduced with the stated shape and the stated reason when the audit re-ran them.

- **`Sim/tests/test_site_id_stability.py` — 5 tests, 3 fail.** Module docstring says outright that
  these are expected to fail. Card `SDET-SITE-ID-ORDINALS`: "defect still open; the test that pins it
  was repaired so that it CAN go green. No product change." The 2 greens are the harness controls,
  which must pass. Failures pin a castellan uid renumbering across an age
  (`hero-castellan-fortress-0` becoming `...-1`, and the old uid naming ground at a different node
  pair). `[capture]` ×2, `[ran]`
- **`Sim/tests/test_villain_fall_reachability.py` — 6 tests, 1 control passes, 5 fail, 0.003 s, no
  world generated.** The card states that expected result word for word and the run reproduces it
  exactly. Headline: `1.0000000000000009 not less than or equal to 1.0` — **no legal `villain_hold`
  inside the declared range can end a reign.** `[capture]` ×2, `[ran]`
- **`tests/test_status_vocabulary.py` — 7 tests, 3 fail**, all three in the vocabulary test class.
  All three are the card's designed assertions. One got **worse because the board's own ask was
  satisfied**: publishing the villains schema made the overload finding name two tokens where it
  named one. Two of the three are structurally unsatisfiable as written — they compare a module dict
  literal against itself — and the card is honest about it. `[capture]` ×2, `[ran]`

A wording trap in two of those docstrings: "every test here is expected to fail" is loose. The
harness-control class in each module is a control that is *supposed* to be green. Its passing is
correct, not an unexpected green.

### 4.4 Long-standing red, not a regression

**`Sim/tests/test_terrain_nests.py` — 16 tests, 2 failures.** These pin an unfixed defect on
`BESTIARY-PYRAMID-RETUNE`, and `board/in-progress/SUPER-VILLAINS.md` records them proven pre-existing
against an untouched baseline copy that fails identically.
- `test_pyramid_and_overlap`: `184 not greater than 267` on beast nests, where the card recorded
  204 against 301.
- `test_population_scales_with_the_ground`: wildlife 11,832 against 13,919, ratio 0.392 against a
  required 0.7–1.4 band, where the card recorded 13,751 / 14,849 at the same area.

The observed counts (184/267 and 11,832/13,919) differ from the card's recorded ones (204/301 and
13,751/14,849). The catalogue grew today, which would explain it, but **nobody re-ran the two-arm
comparison against a baseline copy** — see §8. `[open]`

The mechanism is a design contradiction, not a tuning miss. A candidate is refused by any placed lair
of equal-or-greater tier at
`Sim/icarus_sim/terrain_nests.py:337`, so a tier-1 lair is refused by everything and a tier-5 only by
other tier-5s — the pyramid inverts. The comment above it and the published `method` string at
`Sim/icarus_sim/terrain_nests.py:345` both claim the opposite: that lesser monsters live inside a
greater territory. **The published string should be corrected whether or not the rule changes**;
that is separable from the ruling and is the cheapest item in §5(a).

### 4.5 Green and load-bearing

| Suite | Result |
|---|---|
| `test_biome_habitat_coverage` | 4/4 |
| `test_biome_reachability` | 8/8 |
| `test_cult_leyline_writes` | 8/8 |
| `test_terrain_scale` | 22/22 |
| `test_layer_scale_regression` | 7/7 |
| `test_super_villains` | 24/24 |
| `tests/test_world_schema_surface` | 4/4 |
| cheap contract set (5 modules) | 50 tests, 47 pass, 3 fail — all 3 the designed reds above `[relayed]` |

Every other row in that table was re-run at the close and reproduced. **The last row did not, and is
the one row here you cannot reproduce**: the five modules it totals are named nowhere in this
document or in the tree — there is no such set in `validate_repo`, whose stages are `checks`,
`sim-tests`, `repo-tests` and `artifacts`. Rebuild the set yourself or drop the row; do not quote
50/47/3 as if it were a gate.

`Sim/tests/test_time_advance.py` — **37/37**, re-run after the 12:34:35 rewrite, 147.136 s then and
149.874 s at the final audit. `[ran]`
`Sim/tests/test_corruption.py` — **31/31, 463.502 s**, re-run after B's 12:21 landing. `[ran]`

### 4.6 Not run, by instruction

`tests/test_showcase.py` — a 338 MB bundle at 2.2 GB peak, over 25 minutes inside one test method,
and itself the subject of `PERF-SHOWCASE-TEST-COST`. A full `Sim` discovery run — see §1.

---

## 5. Open work, prioritised

### (a) Actionable now — proven mechanism, scoped fix

1. **The 1 km² river-threshold cap** — §1 item 3. One line, pinned file, dead today, catastrophic
   when reached.
2. **The ceiling sentinel still armed at 1026** — the literal is carried at
   `Sim/tests/test_terrain_patch.py:61`. Two lines; the replacement is written out in
   `SDET-CEILING-SENTINELS`. The trap is that "one above the current limit" stops being a rejection
   the moment the limit moves; it already turned a 0.1 s rejection into a 48 s generation once.
3. **The published nest `method` string** — §4.4. It ships a claim to every consumer that the code
   contradicts.
4. **`TIME-PERSISTED-WORLD-CANNOT-ADVANCE`** — `advance_age_request` on a CLI-written world. The
   unguarded write into the timings dict is at
   `Sim/icarus_sim/terrain_biomes.py:100`. Session B added a **local mitigation for the tick only**,
   and its own docstring says the general fix must audit every writer. **Read, not run:** the age band
   of the time API hands the caller's world straight through with no mitigation, and its only coverage
   asserts the day band — so the age band on a stripped world should still raise. *Falsify by* popping
   the timings key from a generated world and calling the time-advance request with a 100-year span
   and commit set. `[capture]` ×1
5. **`SDET-SITE-ID-ORDINALS` slice one** — the countryside castellan and reeve wells, moving all four
   identity fields together and keying on the terrain node with the anchor spelled out. The card
   already corrects a wrong-file report: the producer is the humans recorder, not the settlements
   module, checked rather than assumed. Blast radius is mapped and includes two provenance-pinned
   edits, and the npc-roster test literals are explicitly **do not touch**. `[capture]` ×1
6. **`SCALE-METRE-CONSTANTS-COLLAPSE`, the remaining five** — the 180 m wetland margin (see (b)),
   `water_reach` 400–650 m and `college_water_reach` 600–850 m across all 13 population profiles
   against measured freshwater distances up to 20,745 m, the 80 m flood decay (left unscaled
   deliberately), and the 250 m nest clearance. Plus two latent: a reach clamp that binds silently at
   3.2% of headroom with no error and no log line, and the fact that `Core/` never adopted the
   circumference constant at all — **do not "fix" Core's own threshold; it is correct on Core's
   world.** `[capture]` ×1
7. **SUPER-VILLAINS S9 — the native port — is not started.** `board/in-progress/SUPER-VILLAINS.md:3`
   says so outright. There is no `Core/villains.*` file at all; a repo-wide grep for the word in
   `Core/` returns only `config.hpp`, `legacy.cpp` and `legacy.hpp`. At :95 the card records that
   S9's parity at nonzero `villain_rise` needs the native driver's test entry point to accept option
   overrides, and calls that **unscoped**. **This is the largest unlanded piece of ruling 0.3**, it
   is why §4.2's suite runs villainless, and no earlier brief listed it as open work. `[read]`

### (b) Blocked on a user ruling — ask these exactly

1. **Exposed rock.** *Accept that the default raster produces ten of the eleven natural biomes and
   that raster 33 is the recorded floor for a world that must contain all eleven — or move the
   default relief, knowing the measured cost?* The mechanism is arithmetic, not a threshold: the
   centred-difference baseline is two meridional steps, so a 38° grade needs a 9,766 m rise against a
   1,667 m default relief. Measured: the biome appears in **0 of 232 seeds at raster 17, 2 of 12 at
   33, 6 of 6 at 65**; raising relief to 3,600 m buys rock in 2 of 32 default worlds while
   quadrupling it at raster 65, pushing maximum land grades to 80°, and **making every world narrower
   than 194.8 km ungenerable**. `[capture]` ×1 — see §8 for a phrasing ambiguity in the source.
2. **Marsh.** *Derive the 180 m wetland margin from circumference (≈3,229 m at 200 km), making marsh
   a wetland margin instead of a river mask?* The cutoff admits **0 of 944 undirected edges at raster
   17 and 0 of 3,936 at 33** — shortest edge 2,423.6 m — so the relaxation does nothing and marsh
   lands only on cells that are themselves water or river, confirmed 5 for 5 on generated worlds.
   The world's own published method string still promises land within 180 m of mapped water. Four
   gates so nobody applies it believing it is free: seed-changing; the biomes module is
   provenance-pinned; the native mirror must land in the same change and **one of its three sites is
   a partial line continuing on the next**, so a one-line patch silently matches nothing; and the
   reachability witness table must be re-measured rather than weakened. `[capture]` ×1
3. **Villain fall.** *Decay the ledger toward current concentration, or test the fall against current
   concentration and leave tier as the accumulator?* And separately: *a villain whose region anchor
   stops being produced — must it fall, or must it remain reachable by the loop?* The tests pass
   under either shape. Note the well-anchoring stranding route **is** fixed — the prefix is declared
   at `Sim/icarus_sim/terrain_villains.py:188` and excluded at
   `Sim/icarus_sim/terrain_villains.py:203` — and it turned none of the five red tests green; it only
   changed which stranding route the outlook contradiction arrives by. `[capture]` ×2
4. **Liveness vocabulary.** *Publish a liveness mapping — a sibling keyword on each person-level
   status, or a token rename?* Three vocabularies across heroes, npcs and villains, and one plan
   token already means two things. Changing any enum is a consumer-visible interchange change needing
   a version move. **The code-level answer now exists** in session B's liveness predicate and could be
   lifted straight into a contract; it is an internal adapter, not a published contract, so the card's
   complaint about consumers is untouched. `[capture]` ×1
5. **World schema.** *Should every block be required, or merely declared? And how is a phase-gated
   block's conditional requirement expressed?* The two tests were deliberately split along that line.
6. **Cleanse on a revealed god.** *Refuse, or drain all of that god's corruption records?* No cleanse
   schema exists to constrain the answer, and the drain is index-based with no defined aggregate
   report shape.
7. **City count / settlement density** — `PERF-CITY-COUNT-TRACKS-RASTER`. Seed-changing across eight
   blocks and needs its native port. A ruling, not an implementation.
8. **`HERITAGE-GEOMETRY`** — do traits touch geometry at all.
9. **`PRODUCT-CONSUMER-VOCABULARY` C1/C2** — two fleet conventions that exist only in a scratch file
   and need a home in `docs/decisions/`.
10. **The thirteen held player findings** — still off the board on standing user instruction. **Ask
    before filing any of them.**

### (c) Paperwork and unrun measurement

- Board hygiene — §1 item 4, now seven missing cards and two redirect stubs.
- **Amend the previous roll-up.** Its §0 "ERRORs first" instruction and its §2 gen-9/gen-16 framing
  are actively misleading; §3.1 and §3.3 here supply the replacements.
- `Contracts/README.md:12` is stale by two revisions — it claims key locations use catalogue revision
  1; the catalogue is at **3** (97 archetypes, verified at the close) and the value is emitted into
  every world document. There is **no version binding for it**, which is exactly the drift class the
  bindings file exists to catch. This predates today; today's edit to that file widened the gap
  without fixing it. `[capture]` ×1, revision `[ran]`
- **`docs/conformance/request-failures.md:116-118` is stale against its own code.** Its "Does not
  establish" section reads "Only `generate_request` is converted. The age, visitation, corruption,
  nomad, lunar and patch boundaries still raise bare `ValueError`" — all six now import
  `terrain_errors`. The document's mtime (12:07) predates that module's (12:19). `docs_check`
  reads front matter and filenames, not claims in prose, so **nothing catches this** — the same gap
  §6 records for a decision-record path written inside a Python comment. `[ran]`
- `VILLAINS-NO-SCHEMA` reads "open, unowned" but the schema was published today. Retire or re-scope.
- 9 stale CITE warnings, eight of them on board cards (seven in `backlog/`, one in
  `board/in-progress/SUPER-VILLAINS.md:190`); the ninth is `Core/README.md:235`. Cheap, non-blocking.
- Unrun, all cheap on a quiet box: the phase-16 cost ladder at 33/65/129; determinism outside seed 42
  size 17 with villain paths live (needs a nonzero rise, **not** a large grid); coverage magnitude;
  the full `Sim` discovery pass; and the pyramid two-arm comparison at another seed and raster.

---

## 6. The concurrent-session situation

**Nothing is committed.** 136 dirty paths on top of `7d94bf5`, two sessions' work interleaved,
attribution available only by content and by diff. `[ran]`

**Session A** landed the eight rulings in §2 plus the schema, ley-queue and key-location work.
**Session B** built, in this order: a world clock (four new modules plus a 37-test suite, a lab route
and two documents); a control catalogue generated from the parameter registry into a packaged JSON,
a contract catalogue and a native bounds include; a structured failure envelope with seven refusal
shapes, now imported by eight `icarus_sim` modules — `terrain_world`, `terrain_history`,
`terrain_visitation`, `terrain_corruption`, `terrain_nomad_api`, `terrain_astrology`, `terrain_patch`
and `terrain_time` — plus `terrain_time_schedule`; a fallen-claim decay; a fixture-sentinel gate
inside `validate_repo`; and four new version bindings (14 → 18). `[capture]` ×2, envelope `[ran]`

Four facts about B's work that a reader will otherwise re-derive:

- **The control catalogue found a real defect in passing.** Replacing Core's hand-written bounds
  table with the generated include revealed that 4 of the 20 shared rows had drifted — plate count,
  belt width, settlement spacing and support reach — and that a reach control resolves to 17,938.9 m
  at the 200 km default against an old 10,000 ceiling, so **the reference producer's own default
  world could not be requested through Core's JSON boundary.** Confirmed in B's own words in the
  native genesis diff. `[capture]` ×1, `[ran]`
- **The clock's determinism argument is that the RNG domain is keyed by absolute simulated time and
  never by tick ordinal**, so a thirty-year advance equals two fifteen-year advances byte for byte.
  A calendar year of 360 days is the moon's; **a hundred-year age is new contract nobody has
  ratified.** `[capture]` ×1
- **B found two defects in its own work by running rather than reasoning**: a warnings list shared
  across passes made a span differ by how it was cut, and running every crossing rebuilt the
  encounter index 360 times over thirty years. Both are fixed; both are worth carrying as method.
  `[capture]` ×1
- **A seventh card, `SEASONS-WHOLESALE-EXCEPT-ITS-LAST-LINE`, landed at 12:37 and matters to the
  clock.** `terrain_seasons.add_seasonal_food` replaces its own seasonal-food block wholesale, but
  its last line appends to the world-level shared warnings list. Run once at generation that is
  invisible; run on a cadence — which `terrain_time` now does, once per season — and the warnings
  list becomes a tally of how many times the pass ran. It is absent from `board/README.md`. `[read]`

### What actually collides

- **The decision-record collision does not exist.** The coordinator's brief said B's villain module
  cites a fallen-claim decay record numbered 022 that collides with 023. It cites **024**, and a
  repo-wide grep for the 022 form of that name returns **zero hits**; 022 is the
  private-package-distribution record with an mtime that predates today entirely. Session B
  renumbered it before anyone looked. **Nothing to renumber. Verify before acting.** `[capture]` ×1,
  `[ran]`
  The durable lesson is what the gates would and would not have caught: the numbering check compares
  *filenames* and would have caught two records sharing a leading number, and the provenance-decision
  check reads only manifest rows. **Nothing in the repo checks a decision-record path written inside
  a Python comment.** Had B written the wrong number in the comment and the right one on disk, the
  tree would have stayed green.
- **Two files carry both sessions and neither clobbered the other.** In the villains module, A owns
  the promotion function and the well-node exclusion, B owns the decay constants and their use; the
  two are independent — A changes who is seated, B changes what a dead villain's claim still does.
  Both coexist, the module imports, and its suite is 24/24. In the history module, A owns the
  promotion wiring and the ley-queue removal, B owns the failure-envelope adoption. `[capture]` ×2
- **The decay is seed-visible and said so in source**, and exactly one test asserted the old value —
  **B updated it**. No test anywhere still asserts 1.0. Stale prose remains in the super-villains
  document and three board cards, which still say the value is 1.0 and the decision is unmade. Prose-
  stale, not blocking; there is no semantic check that would catch it. `[capture]` ×1
- **The heritage appearance layer is attributed to B on the brief's say-so alone.** It matches none
  of A's eight rulings and is not part of B's stated clock scope, and no decision doc, board card or
  provenance row names it. **Confirm with B before relying on that attribution.** `[capture]` ×1

### Is the tree safe to commit?

**Not yet, in this order:**

1. **B was still writing eleven minutes before this document first closed**, and the quiet window is
   now thirty minutes. Any commit taken without confirming B is done snapshots a half-landed feature.
   This is the blocker; the rest are secondary.
2. **Two logically atomic changes are split across tracked and untracked files.** The modified
   `validate_repo` invokes an untracked tool that reads an untracked catalogue and writes two more
   untracked outputs; a commit without staging untracked paths ships a validator that cannot run. The
   same shape applies to the villains schema, which is untracked while the validator parses every
   schema in that directory. **Stage everything or nothing.** `[capture]` ×1
3. The native parity suite is red at 10, of which nine are float tail and one is the harness artifact
   in §1 item 2 — and it is measured with villains off. Document them as known.
4. Stale prose and 9 CITE warnings mislead a reader without blocking a gate.

---

## 7. Traps

**T1 — 79 provenance-pinned files.** The manifest pins them against source commit
`d551767cb1c3bd259bb00f56be1e52c2182c5ec3`. The set includes essentially every `terrain_*.py`
generator module, the nest and city JSON catalogues, fifteen terrain test modules, the canonical
world-asset catalogue and all eighteen of its documentation mirrors, the lab tooling, and four
imported LAB evidence cards. *How to apply:* before editing one, append a revision row carrying date,
previous hash, new hash, reason and normally a decision path **that must exist** — the decision check
is HARD — then update the entry's top-level hash. The verifier hashes the file's bytes and raises on
a mismatch. `[capture]` ×2

**T2 — the previous hash must be computed by reverse-applying your own edit in memory.** Hashing the
file off disk captures other sessions' concurrent edits and silently claims them under your reason.
**Nothing enforces this** — the verifier never reads that field. It is discipline, and today proves
the hazard is live: session B rewrote a pinned module at 12:21 while a capture was reading it.
Capture the hash and mtime before editing a shared file and re-check both immediately before writing;
changed twice means it is under active construction. `[capture]` ×1

**T3 — three byte-identical copies of the world-asset catalogue.** Packaged, canonical, and
documentation mirror; the validator compares all three as bytes. Currently identical. Edit one, copy
to the other two byte for byte. The mirror is also pinned, so it needs a manifest revision too.
`[capture]` ×1

**T4 — two generated artifacts that must never be hand-edited.** The native catalogue bundle is the
**only** channel through which Core reads nest profiles, and it ships to Unreal; the Unreal asset
registry is generated from the asset list. Change the authoring registry, then regenerate. Both have
`--check` gates in the checks stage. `[capture]` ×1

**T5 — the documentation checker has four sharp edges.** It reads **only** the `modules` front-matter
key for coverage; other keys do not affect it. Its globs are **fnmatch, so `*` crosses `/`** —
nesting a document deeper under `docs/` does not exempt it, and this document is itself active for
that reason. Its CITE rule attaches **every** backticked identifier on a line to **every** citation on
that line and warns unless one appears within three lines of the target: **one citation per line, and
no unrelated backticked identifier sharing it.** A citation line carrying no backticked identifier is
skipped entirely. And a **new module under `Sim/` fails coverage** — HARD — unless a conformance
record claims it or the allowlist (158 entries, ratcheted against a merge base) lists it with a
ticket. Test files are exempt. `[capture]` ×2, `[ran]` for the skip-on-no-identifier behaviour

**T6 — line endings are per file and provenance hashes worktree bytes.** The attributes file sets
text auto and then carries **80** `-text` overrides across 100 lines. Of the 79 pinned files, **31
are CRLF and 48 LF**; of the 30 pinned `.md` files, two are CRLF —
`docs/catalogue/world-assets/README.md` and `docs/terrain-math-lab.md` — and 28 are LF. Patch pinned
files at byte level, never with a tool that may normalise, and check the attribute before you do.
`[capture]` ×1, counts `[ran]`

**T7 — world generation costs, measured today rather than quoted, on a contended box** (seed 42,
size 17, recipe 3): phase 9 **0.27 s**, phase 10 **0.37 s**, phase 13 **6.94 s**, phase 16
**84.65 s** — re-measured at the close as **0.23 / 0.33 / 5.82 / 72.98 s**. Treat the figures as a
ladder, not a property of the tree; §8.3 applies to them exactly as it does to the native suite's
wall time. The guidance survives either reading: *never iterate on a phase-16 world.* Develop at phase
9 or 10, confirm at 13, budget a minute and a half per phase-16 call. A phase-10 world answers any
biome-layer question — that equivalence is recorded and load-bearing in the reachability suite's
docstring. `[capture]` ×1, re-measurement `[ran]`

**T8 — `tier` means five unrelated things.** Key-location tier is **physical scale and build-out, not
danger** — read the threat field for danger. Creature tier is an integer 1–5 danger band. Villain tier
is a **float that also sets reach in metres**. Hero tier is a string enum. And conformance records use
it for an evidence floor. `camp` collides similarly. Never write a cross-block checker that keys on
`tier`; name the block every time you use the word. `[capture]` ×1

**T8b — `globe_radius` means two different numbers on the same default world.** The **design** radius
is **31,830.99 m** (circumference exactly 200 km), and that is what the nests module hands the reach
scale, giving the 5,381.7 m danger span quoted in §2. The world document's own
`effective_config` publishes `globe_radius` as **179,388.90337493608 m** (circumference 1,127 km).
Reproduce the span from the document and you get **30,329.3 m** — wrong, silently. The design figure
is recorded explicitly at `board/done/BIOME-TUNDRA-SNOW-UNREACHABLE.md:240`. This is the same
one-word-two-meanings hazard as `tier`, and it bit this document's own §2 numbers. `[ran]`

**T9 — the key-locations difficulty gradient is a different mechanism from the nests one.** Threat is
computed *after* placement and nothing in the placement or field code reads it, so there is no term
to bite; and that package's clearance keys on `tier`, which there means scale. The fix needs something
placement can know **before** it places. That is a dependency, not a tuning question. `[capture]` ×1

---

## 8. What this document does not establish

- **Whether the two ports agree on the astrology layer at a matched phase.** The probe established
  only that the Python layer moves by up to 0.0758 across the two age transitions and that this fully
  accounts for the reported failure. No test compares the post-age native layer against the post-age
  Python one, so **a genuine numeric divergence could still be hiding behind the phase artifact**.
  Fixing the harness is a prerequisite to answering this, not a substitute for it.
- **Anything about parity on a world with villains.** §4.2's suite pins them off and S9 is not
  started, so the entire native port is untested against today's default configuration.
- **Which arithmetic term carries the cancellation** in the three irrigation failures.
- **Attribution of the 4 new CITE warnings** to a session. No per-hunk diff was run.
- **The current full-`Sim` discovery figure**, the showcase suite's state, the phase-16 cost ladder,
  the determinism run with villain paths live, and the pyramid two-arm comparison. All unrun.
- **Whether the nest-pyramid failures still reproduce against a baseline copy today.** Captures relied
  on the recorded proof in two cards rather than re-running the two-arm comparison, and the observed
  counts have moved since those cards were written. The claim that the catalogue's growth explains
  the move is inference — see §4.4.
- **Whether the pyramid card's "as shipped" baseline was taken on the post-ruling catalogue.** Mtime
  ordering says yes; the card does not say so, and its own original observation differs enough that
  the next agent must not assume the two are comparable.
- **Whether the heritage appearance layer is session B's.** See §6.
- **Whether the ley-width forms stay in agreement under a non-default world scale.** They are
  bit-identical at the default — 17.938890337493607 on both sides — but the Python divides the
  physical radius by a reference constant while the native side multiplies the design radius by the
  world scale, and **that scale is an open control with a range spanning six orders of magnitude**.
  Nobody generated a world with it overridden. See T8b for the pair of radii this hazard produces.
- **Whether a stranded villain occurs in a generated world.** Proven at the unit level; the multi-age
  run that would confirm it against real data has never been taken.
- **The 420-day living-world finding has no record anywhere.** Greps across every document in the tree
  return nothing. It exists only in a session transcript and **will be lost unless someone files it.**
  Any channel accounting quoting its 4/6/10 split is quoting the transcript, not a source.
- **Three incompatible native baselines are in circulation, all quoted and none re-measured**: 68
  FAIL / 8 ERROR in `docs/reviews/651ab00-coordinator-roll-up.md:42`; 68 failures / 6 errors / 653 s
  in `NATIVE-PARITY-HARNESS-SHAPE.md`; and 89 failures / 4 errors with a byte-identical revert control
  at `board/in-progress/SUPER-VILLAINS.md:170`. **The 68/6 figure is the best-sourced of the three**,
  because the parity card's Measured residual agrees with the count recorded inside the test module
  itself (§3.3), while the 68/8 form appears only in prose headings and the 89/4 pair was taken on a
  different tree with villains newly default-on. All three were taken on trees that have since moved;
  today's shape is 15 tests, 10 failures, 0 errors, villainless.

### Where the captures disagree, and what this writer believes

1. **The astrology failure's class.** Two captures called it a real divergence bounded to the age
   transitions; one instrumented the oracle and called it a harness phase mismatch; one called it
   real and also noted the hypothesis linking it to a divergence that no longer reproduces. **Believe
   the probe**, because it reproduced the reported number bit-for-bit from an independent path and
   because the two disagreeing captures read only the assertion text.
2. **Whether all nine float failures are last-ulp.** One capture said all nine; two said the three
   irrigation ones are cancellation-amplified, with the relative gaps to show it. **Believe the
   two**, and the parity card agrees.
3. **Wall time for the native suite.** 282.249 s, 304.552 s and 314.628 s across four captures.
   **Two captures report 282.249 s to the millisecond** — that is one measurement with two readers,
   not two measurements. **None of the three is a property of the tree**; all were taken on a box
   carrying up to eight concurrent suites. The same caveat now attaches to T7.
4. **The exclusion line for the well-node prefix.** Three captures give three line numbers. The
   declaration is at `Sim/icarus_sim/terrain_villains.py:188`
   and the exclusion at `Sim/icarus_sim/terrain_villains.py:203`.
   Verified by reading both lines. `[ran]`
5. **The wetland edge count.** One capture reports 0 of 944 undirected edges at raster 17; a card
   reports 0 of 1888 directed. **These reconcile**, and the shortest-edge figure of 2,423.6 m is
   identical in both. The 1888 figure is in `SCALE-METRE-CONSTANTS-COLLAPSE.md:28` and at :64, **not**
   in the marsh card — `BIOME-MARSH-IS-THE-RIVER-MASK.md:34` reports 944. State whichever you use,
   and say which document it came from.
6. **Dirty-path count at the close.** Captures report 135 and 136 at times minutes apart. Both are
   correct for their moment. The number is a clock reading, not a fact about the tree.

**A phrasing ambiguity worth flagging:** the exposed-rock capture writes that the biome "is absent
from 0 of 232 seeds at raster 17", immediately before "present in 2 of 12 at 33". Read literally those
contradict. The ruling text and the pinned test both require the reading used in §5(b) — it is
**present in 0 of 232 at raster 17**. Confirm against the card before quoting the number.

### Method findings — these generalise further than the defects

1. **Agreement is not verification when the methods do not differ.** Four captures "confirmed" the
   native suite; two of them report the same wall time to the millisecond, and three of the four
   classified the astrology failure from the same assertion string. One probe overturned all of them.
   *Ask what a peer varied, not just what they ran.*
2. **A near-miss grep answers a different question than the one you asked.** One capture nearly filed
   a port asymmetry because a grep for an assignment pattern returned exactly one hit — the real
   assignment is a **subscript**, and the refresh is called from three places. The same shape produced
   the refuted corruption card in §3.2: a grep for a callee's name inside a caller's file, where the
   call is indirect. Match by exact identity, and run the real predicate.
3. **A pipe can destroy the evidence you ran the command for.** Two captures piped a suite through
   `tail` and lost 3 of 10 failure identities, which is why the failure table in §4.2 comes from the
   one that did not. Cheap to avoid, expensive to re-take at five minutes a run.
4. **Contention splits measurements.** Counts, digests, call graphs and assertion values survived a
   box running eight concurrent suites. Wall time and peak memory did not. **Take the structural half
   now and queue only what genuinely needs a quiet machine.**
5. **mtime alone attributes nothing when two sessions interleave.** Today's writes alternate minute by
   minute across the same files. Attribute by content and by diff, or say you did not.
6. **A test written to fail that passes is a defect in the test** — and a control that shares the
   failure mode guards nothing. Two modules here declare "every test is expected to fail" while
   containing a control class that must be green. Read the class, not the docstring.
7. **A count quoted from a prose heading loses to a count recorded by the code.** The eight-versus-six
   ERROR figure and the 34-versus-37 test count both travelled for a day as headings and briefs while
   the module said otherwise. Re-read the producer.
8. **An instrument must report its own blind spots.** Carried forward from the previous roll-up and
   still the rule that matters most: a survey that cannot say what it missed will always report full
   coverage.

### Errors that reached a reader, recorded so they stop travelling

- **The coordinator reported a decision-record collision that does not exist.** The claim, relayed to
  the user earlier today, was that session B cited a fallen-claim decay record numbered 022 which
  collided with 023. The citation is **024**, a repo-wide grep for the 022 form of that name returns
  **zero hits**, and 022 is an unrelated record predating today. B had already renumbered it. Nothing
  needs renumbering, and the wrong claim cost a reader a verification cycle. It is written here
  because it reached the user; §6 records the durable half, which is that no gate would have caught
  the inverse error. `[ran]`
- **The draft of this document carried nine numbers that did not reproduce.** The nest catalogue's
  biome weights (369, not 680, and a histogram that was over a different field entirely), the
  time-advance test count (37, not 34), the untracked-path count (37, not 36), the CITE warnings on
  board cards (eight, not six), the attributes-file override count (80, not "roughly twenty"), the
  pinned-file line-ending split, the ERROR count, the phase cost ladder, and the land-cell convention
  behind ruling 2.0. All are corrected above. The pattern in every case is a figure carried from a
  brief instead of re-taken.
- **A card was named as the source of a figure it does not contain.** The 1888-edge count was
  attributed to the marsh card; it is in the metre-constants card. The reconciliation was right and
  the attribution was wrong, which is the more dangerous combination, because the reasoning survives
  inspection while the source does not.
- **Two inferences were written as findings** and are now marked: what closed the coverage gap
  (§4.1), and why the nest-pyramid numbers moved (§4.4). A third was mis-marked in the other
  direction: the draft called the reason `natural_catalogue()` is untouched an inference, and it is
  not one — the reason is written out in the source docstring, which §2 ruling 0.2 now cites. **An
  inference marker is a claim too, and this one was wrong.** Found by opening the file the draft
  said held no answer.
- **A line was nearly cited from a capture without opening it.** Three captures gave three different
  line numbers for the same exclusion; one of them was right. Every `path:line` in this document was
  re-read at the close, and two capture-supplied ones were wrong. The audit re-read all fourteen of
  the surviving ones against the live tree; none failed.
- **Four captures were treated as four witnesses until their timings were compared.** Two are one
  measurement. The confidence markers in §4 were rewritten after that.
- **This writer ran none of the simulation measurements in the original draft.** The figures marked
  `[ran]` were executed by this writer or by the audit after every capture closed: the documentation
  checker, the three resume-item suites, the key-locations revision, the git state, the byte-level
  counts and the citation lines. Everything else is second-hand and marked. If a number here matters
  to a decision, re-take it.
