# Red team review — principal engineer lens — `233182e`

Reviewed 2026-09-20 against commit `233182e`, with a live re-verification pass after the 1025 grid
ruling landed and the fix began arriving in the working tree.

**Lens.** Contracts and invariants, the Python ↔ `Core/` parity boundary, version discipline, gate
integrity, and whether completion claims are backed by evidence actually run. Line-level logic
belongs to the code red team, test honesty to SDET, and consumer-facing contract to the product red
team. On the one shared seam — record claims that no machine check enforces — the code session holds
the gate mechanics and this review holds invariant truth.

**None of the findings below are world-content findings.** They are document, gate and contract
findings, so the octave admission filter result — that a size-17 world resolves zero of five octaves
and has no surface noise at all — does not qualify any of them, and no raster needs to be quoted
against them. That filter does qualify content reviews, and the distinction is worth stating rather
than leaving a reader to work out.

**Verdict:** one blocking defect made `validate_repo` non-terminating on committed code and is still
only half fixed; the first conformance record — the template for roughly 120 more — states a
determinism invariant that is false; and the front matter those records advertise their evidence
through is read by nothing.

---

## B1 — The grid ceiling was widened at the entry points and carried to no consumer

**Filed as `board/backlog/PRINCIPAL-GRID-BOUND-PARITY.md`, which carries the full evidence and the
sweep list. Summarised here.**

`21df9aa` widened the Python ceiling from 257 to 1025 in `terrain_world.py` alone. `Core/`, the
shared fixture and the native tests were not moved, so the reference and the port disagreed. The
consequences were a failing parity test, a *passing* test at another consumer asserting the old
ceiling, and a fixture case that stopped being invalid and therefore generated a world instead of
raising — turning `--stage repo-tests` from a suite that fails into one that does not finish.

The contract form of it is the part that outlives the specific numbers: `registry()` is not only an
entry-point constant, it is published inside every generated world. `terrain_world.py` writes
`'parameters':registry(version)` into the recipe block, so a consumer reads the advertised range out
of the document it was handed rather than from an endpoint it could be told to ignore. Verified by
generating a world and reading `recipe.parameters.size.max` back.

**The user ruled 1025.** At the time of writing the producer side has landed uncommitted —
`Core/genesis.hpp`, `terrain_patch.py` and `terrain_history.py` all now carry 1025 — and the test and
fixture side has not, so the non-termination survives and one further test has newly broken. The
card holds the current state, the must-move list, and a do-not-touch list.

**The one thing to carry forward past this ticket.** The divergence survived review because the
parity test was a *text* match — `assertIn('max_grid=257', genesis)` — standing in for a value
comparison against the Python reference. A text match cannot notice that the thing it is comparing
against has moved. That assertion should become a value comparison, or the same class of defect
recurs the next time either side changes.

## B2 — `docs/conformance/nomads.md` states a determinism invariant that is false

The record says seeds derive through `child_seed(cfg.seed, 'nomads-v1', nomad_variation)` with
per-entity domains `nomad-class-<uid>`, `nomad-camp-<uid>` and `nomad-route-<uid>`, and argues that
because streams are keyed by a string domain, a feature drawing only from new domains cannot perturb
an existing stream.

Verified twice, the second time as an exhaustive sweep for every form of randomness rather than a
search for one function:

- Those three domain strings appear nowhere in any Python file in the repository. Their only
  occurrences are the two documents that assert them and one board card quoting the sentence.
- `terrain_nomads.py` constructs exactly **one** RNG, on the domain `'nomads-v1'`, and draws from it
  at three sites — a rate comparison, a cumulative `_pick` walk, and a size `randint`. One sequential
  stream.
- `terrain_nomad_routes.py` imports both `random` and `child_seed` and calls **neither**.
- `terrain_nomad_effects.py` draws no randomness at all.
- `terrain_nomad_api.py` does use per-node domains, but on the request path — not the class, camp or
  route domains the record names.

**The record's argument is not merely unsupported, it is inverted.** Under a single sequential
stream, a draw inserted anywhere in nomad generation shifts every subsequent draw — exactly the
perturbation the record promises cannot happen. The document tells a future author that an unsafe
change is safe.

`docs_check` is green on this and is **right** to be: every symbol resolves, the modules exist, the
version markers match. `AGENTS.md` says as much — a green run "proves nothing about whether the
record is true". The gate is behaving as documented; the record is the defect.

Blocking because of position rather than blast radius. `nomads.md` is the only record in the
repository and the worked example beside `_template.md`, and `AGENTS.md` names determinism first
among the binding invariants a record must not misstate. Roughly 120 more records will be written
against this pattern. `docs/nomads.md` carries the same sentence and needs the same correction.

SDET is quoting this sentence in its own ley-queue card; it should be corrected once, not twice.

## S1 — `proof:`, `tier:` and the front-matter `versions:` list are read by nothing

`docs_check.py` reads exactly **one** front-matter key. `fm.get('modules', [])` is the only
`fm.get` call in the file, and the strings `proof` and `tier` do not appear in it at all. So a
record's `proof:` names a test that nothing confirms exists, runs, or covers it; `tier: EXERCISED` is
self-assigned and unread; and the front-matter `versions:` block is not the thing enforced —
enforcement runs off the `<!-- conformance:version -->` prose markers plus the separately
hand-maintained `version-bindings.json`.

A reader reasonably takes `proof:` for a machine-checked link to evidence. It is a comment. That
matters more than usual here because the conformance ticket states these records are the acceptance
spec for the native port — something will be validated against claims that nothing validates.

At n=1 records no record actually lies: both of `nomads.md`'s citations resolve. The finding is that
the claim is load-bearing with nothing behind it, on the night the records are being written. At n=1
the fix is an afternoon; at n=30 it is an audit. The timing is the argument, and it expires.
(Falsifiable framing from SDET and the product session.)

## S2 — Optimisations defended by half a proof, while the other half cannot run

Relayed and **not independently verified here** — recorded as second-hand deliberately, because
inheriting a number silently is the failure this review exists to catch. The perf session's own
profile put `fill_cities` at 46.2%, `age_transition` at 39.4% and `add_nests` at 9.0%, while the four
optimisations committed in `233182e` target producers totalling under a quarter of one percent; and
`city_planner.py` emits no `timing_ms` at all, so the most expensive producer in the generator has
never reported a number. The session disclosed this itself.

**The part this review does assert is the shape of the evidence.** A reverse-apply byte comparison
catches a behaviour change but *assumes* determinism. `validate_repo`'s double-generate catches
nondeterminism but cannot catch a behaviour change. They are complementary halves; neither is
sufficient alone; and per B1 the half that would have supplied the other could not run. A change
defended by half a proof, while the other half is broken by an unrelated commit, is not defended.

## S3 — Five stale citation anchors, none blocking

`CITE` findings are warnings, so a citation may rot while the gate stays green — and four of the five
went stale within hours of being written. Two consequences. The advice to cite a distinctive
substring rather than a line number should be written down rather than passed between sessions. And
the claim that a green run proves a record "points at things that exist" is weaker than it sounds,
because the check that a citation points at *what it claims* does not block.

## Nits

Exactly two markdown files match neither the active nor the frozen glob set and are therefore
unchecked: `board/templates/task.md` and `Unreal/FantasyWorldGenerator/README.md`. There is no
"unclassified document" finding to surface them. The template is arguably fine; the plugin README
describes shipped behaviour and is worth claiming.

---

## Gate evasion check

**A finding I reported and then withdrew, kept here because the failure mode is the point.**

I claimed the checker's `docs/*.md` pattern was single-level, so a document one directory deeper
would escape every check — no link check, no citation check, no version markers. That is false.
`docs_check.py` matches with `fnmatch.fnmatchcase`, where `*` crosses `/`, so `docs/` is covered at
every depth and `docs/catalogue/` always was. A sweep of the tree finds only the two files in the
nits above outside both sets.

The claim reached two other sessions and became a coordinator ruling before anyone ran it. The
coordinator confirmed it using `pathlib.Path.match`, which does **not** cross `/` — so a wrong
premise acquired the appearance of independent verification. The product session settled it in one
step: wrote a file into the supposedly unchecked directory, ran the checker, and watched it raise
warnings against the new file.

**Two sessions agreeing is not two verifications when both reasoned and neither ran.** Every finding
in this review therefore carries a command that was executed. That rule immediately caught its
author: the checker flagged a stale citation in the card filed for B1, the first fix failed, and the
real mechanism had to be found by experiment — every identifier-like backticked token on a line is
tested against *every* citation on that line, so a citation needs a line to itself.

It caught one more thing worth recording. Sweeping for remaining `257` literals after the ruling
turned up two that are a *different* 257 — the tile raster limit in `height-tile.schema.json` and the
vertex guard in `terrain_patch.py`, both derived from a patch's span and spacing and unrelated to the
world grid. A mechanical rewrite would have silently widened a published tile contract nobody ruled
on. Same literal, different concept.

Remaining live evasion routes belong to the code red team under the agreed seam — the `exempt` ledger
path, and the coverage ratchet that is dead code because its only caller passes no base. The scale
that makes the ratchet matter is this review's: the ledger declares **158 uncovered modules** against
124 `Sim/` modules and 46 `Core/` stems, with **4** modules claimed by the single existing record —
**90.3% of `Sim/` unclaimed**, all deferred to two tickets. "The allowlist may only shrink" is what
makes a list that size tolerable, and nothing that runs enforces it.

## Stack-specific attacks

- **Python ↔ `Core/` parity** — B1, and the text-match assertion that let it through.
- **Determinism and replay** — B2, and S2's half-proof.
- **Unreal adapter** — not exercised. No engine evidence gathered and none claimed; per `AGENTS.md`
  a passing Python test does not prove an importer works. The subsystem inherits B1 by compiling
  `Core/`.

## What this review did not do

- Did not review `Sim/` line-level logic or test honesty; those belong to other sessions.
- Did not verify S2's profile numbers independently, and says so where they appear.
- Did not run the full suite. B1 made `--stage repo-tests` non-terminating, which is itself the
  finding. A green number obtained by skipping the hanging test would be the exact evasion this
  review is looking for.
- Did not edit `Sim/`, `Core/`, `Contracts/` or `tools/`. Review-only by agreement with the agent
  coordinator; the board card is the handoff.
