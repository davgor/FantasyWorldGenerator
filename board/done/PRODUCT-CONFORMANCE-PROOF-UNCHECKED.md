# PRODUCT-CONFORMANCE-PROOF-UNCHECKED — eight of nine record keys are read by nothing, while a session adds records

> **CLOSED 2026-09-21.** Every front-matter key is now read. `emits[].schema` and
> `proof[].path` must resolve, a proof path must be a file one of the three suites
> discovers, `versions[].assert` must equal the integer the code emits, `tier` must be one
> of the four words `docs/conformance/README.md` declares, `record` must equal its
> filename stem, and `tickets`/`decisions` warn rather than fail because cards move.
> Fourteen cases in `tests/test_docs_check.py`, each written before the check and each
> failing for its own reason first.
>
> **The card's population of one was already stale when this was picked up: there are nine
> records, not one, and a tenth arrived while the work was in flight.** Every citation in
> all nine resolves, so nothing was lying — the card's own falsifiable form held.
>
> Two things were found that the card did not have, and they are the sharper half:
>
> 1. **Five of the eight keys were not merely unread, they were unparseable.** The front
>    matter parser kept the first line of a `- ` item and silently dropped every
>    continuation line under it, so `schema:`, `assert:` and `establishes:` did not exist
>    as far as any reader was concerned. `emits:` parsed to `['path: nomads']`. A check
>    reading those keys had to start by making them readable. `key: []` was worse than
>    unread: it parsed as the two-character string `[]`, so iterating it yielded `[` and
>    `]` and would have reported two missing files named after brackets.
> 2. **Coverage was never checked, so the gate could not fail on a folder it could not
>    see.** Five documents matched no glob at all. Every markdown file must now match
>    `ACTIVE_GLOBS`, `FROZEN_GLOBS` or a new `UNCHECKED_GLOBS` that carries a written
>    reason per glob, and every run prints what it did not examine and how many frozen
>    documents it read without link-checking. The other direction is checked too: a glob
>    matching no document warns, because a folder that moves leaves its glob behind and
>    takes its documents out of the gate silently.
>
> The two globs that claimed nothing were `board/templates/task.md` — the template every
> new card is copied from — and `Unreal/FantasyWorldGenerator/README.md`, which links five
> documents across two folders with `../../` paths, which is the exact shape that dies when
> a card moves. Both are now active. `Artifacts/*.md` is declared unchecked with its reason.
>
> One correction landed in the documentation rather than the code: `README.md`'s evidence
> table said "anything above `DECLARED` must cite `file::test_name`, and the checker
> resolves the citation". The checker resolved nothing, and `::test_name` is not the form
> any record uses. A stated rationale the code does not have is worse than none, so the
> sentence now says what is actually resolved and `_template.md` carries the same table
> key by key.
>
> Not done, and deliberately: the stretch goal of proving a proof test **passes**. What
> landed is that it is a file a suite discovers. Existence is not exercise, and the
> distinction is written into `README.md` where readers are.
>
> ## The gate's own test suite was the sharpest instance of the card's thesis
>
> Closed here rather than filed as residue, because it is the same defect one level up: a
> checker whose test suite can silently revert two shared contract files, and can leave a
> broken record inside the folder it checks, is a green gate proving less than it appears
> to. Filed as **M4** in `docs/reviews/233182e-code-red-team.md`, whose root-cause reading
> is right — the gap was a missing seam, not a careless test.
>
> Three tests rewrote a **real committed file** and restored it in `tearDown` from bytes
> captured at `setUp`. That is a read-then-write across an arbitrarily long window: any of
> the four other sessions writing the same file inside it has its edit reverted with no
> error and no diff to notice. The two files were `docs/conformance/version-bindings.json`
> and `provenance/extraction-manifest.json` — the most contended in the repository, and the
> manifest has already been corrupted once tonight by two sessions racing on it. A fourth
> wrote `docs/conformance/_probe.md` with an invalid UTF-8 byte; a run was interrupted,
> `tearDown` never fired, and it sat in the checked tree for twenty minutes failing the gate
> in two different ways and being reported twice as somebody else's defect.
>
> What landed:
>
> - `all_markdown` skips dot-directories as a rule rather than naming `.git`, `.venv` and
>   `node_modules` one at a time. Negative fixtures now live in `.conformance-probe/`, which
>   is inside the root so `rel()` resolves and invisible to a concurrent run of the gate.
>   **Verified by stranding a fixture there deliberately: the gate stayed green.**
> - Fourteen checks moved off the subprocess and onto that directory, calling the check
>   directly. `check_provenance_decisions` gained an optional path so a test can hand it a
>   manifest of its own; that was the missing seam. `check_coverage`'s three tests mirror
>   the real folder into the probe, so the ledger and every real record are still the
>   subject and only the folder being written to is not.
> - `setUpModule` sweeps every path this suite can create before the first test, so an
>   interrupted run costs the next run rather than whoever is standing at the closeout.
> - `Restores` lost its `save()` helper entirely. There is no longer anything in the file
>   to reach for that would rewrite a committed file.
> - Each converted check gained a control asserting it can *pass*, because a check whose
>   fixture cannot be made clean reports a defect it invented.
>
> After: `docs/conformance/_probe.md` is never written by any test; the two contended files
> are never written at all; two tests still create a new file in the tree
> (`Sim/icarus_sim/zz_probe_module.py` and a duplicate decision number), which is inherent —
> their subject is the real tree walk — and neither can revert anyone's work. The module
> runs in 12 s rather than 54 s.
>
> One more shared-tree defect fell out of it: the gate died mid-run with a
> `FileNotFoundError` traceback when another session moved a card between `all_markdown`
> listing it and the reader opening it, reporting nothing at all for that run. A vanished
> document is now a `VANISHED` warning and the run continues.

Owner: none. State: **closed**. Found by the product red team auditing
`233182e`; sharpened by the SDET red team, whose reframing is adopted below.

## Requested behavior

`tools/docs_check.py` reads the front-matter keys a reader relies on. Minimum viable: `emits[].schema`
and `proof[].path` must resolve to files that exist, and a record naming a module that no longer
exists must fail. Stretch, and the one that matters most: `proof[].path` must name a test the suite
actually runs.

## The defect

`docs_check.py` reads exactly one front-matter key. Line 402, `fm.get('modules', [])`, is the only
`fm.get` in the file. The other eight — `record`, `tier`, `summary`, `emits`, `versions`, `proof`,
`decisions`, `tickets` — are parsed for syntax at line ~354 and then never read again.

`versions:` looks enforced and is not. Version checking runs off
`docs/conformance/version-bindings.json`, a separately hand-maintained file of fourteen bindings, so
a record's own `versions:` list can assert any integer it likes and stay green.

`tier: EXERCISED` is self-assigned. It is the single word a reader is most likely to trust and it
has the least behind it.

### The falsifiable form, which is not the one I started with

**As of `233182e` no record tells a live lie.** `docs/conformance/` holds exactly one record —
`nomads.md` — and the SDET session checked both of its citations by hand: `emits[0].schema`
(`Contracts/schemas/nomads.schema.json`, 13,286 bytes) and `proof[0].path`
(`Sim/tests/test_terrain_nomads.py`, 12,861 bytes) both exist. What is **not** established, and is
not claimed here: that the proof test passes, that it establishes what `establishes:` says it
establishes, or that `tier: EXERCISED` is earned. Existence is not exercise.

So the card is not "a record cites a nonexistent test." It is: **`proof:` is a load-bearing
consumer-facing claim with nothing behind it, on the night a dedicated session is adding records.**
At n = 1 the fix is an afternoon. At n = 30 it is an audit. This card dates itself deliberately.

### The scale a reader should see

`docs_check.py` reports "124 modules claimed or declared". The one record claims **four** of them.
`docs/conformance/coverage.json` lists **158** uncovered against 8 exempt, seeded 2026-09-19 and
never re-seeded.

Against that, `docs/README.md` opens by telling the reader that conformance records are "the
present-tense breakdown of what this product does … Start there to learn what exists", and
`AGENTS.md` repeats it as the first instruction of the repository. Following that instruction today
teaches a reader about nomads.

## Why it matters

A conformance record is the only artifact in this repository that makes a *present-tense capability
claim to a consumer*. Every other document is either a design rationale or a change log. The
record's contract with its reader is "this is what the product does now, and here is the test that
proves it." Seven-ninths of that contract is decoration.

The uncovered-module count is not itself the defect — it is honest, it ratchets correctly, and a
module created after the seed date fails on first sight. That design is good. The defect is that the
records which *do* exist are trusted more than the checker can justify, and the gap widens with each
one added.

## Proposed mechanism

In `tools/docs_check.py`, alongside the existing `modules` claim check:

- `emits[].schema` and `proof[].path` resolve, or `HARD` finding.
- `modules[]` entries exist, or `HARD` finding. (Currently a record claiming a deleted module is
  caught only indirectly, via the coverage diff.)
- `tickets[]` and `decisions[]` resolve, or `SOFT` finding — these drift legitimately as tickets
  move between `backlog/`, `in-progress/` and `done/`, so a hard failure would punish the move.
- `tier` is drawn from a closed vocabulary declared in one place, with each value's meaning written
  next to it.

The stretch goal — proving `proof[].path` names a test the suite runs — is a bigger change and
should be its own slice. Existence is the ninety-percent win and it is cheap.

## Dependencies and unresolved decisions

- **`tools/` is not this card's to edit.** The code red team is auditing `tools/docs_check.py`,
  `tests/test_docs_check.py` and `docs/conformance/**` at the moment; this is a gap report routed to
  whoever holds that file.
- Overlaps by design with the principal red team session, which owns the **gate side** — the
  mechanics by which the checker stays green while a record is false. This card is the **claim
  side**: what a consumer wrongly relies on. Take them together. One gate-side candidate has already
  been checked and refuted rather than filed: `ACTIVE_GLOBS` (`tools/docs_check.py:34`) uses
  `docs/*.md`, which looks single-level but is an `fnmatch` pattern evaluated by `matches()`
  (`tools/docs_check.py:73-75`), where `*` matches `/`. Documents at any depth under `docs/` are
  checked. There is no relocation dodge.
- Should be sequenced **before** the conformance strategy session lands more records, not after.

## Sources consulted

`tools/docs_check.py:1-18,34,354,402,640`; `docs/conformance/` full listing (one record,
`_template.md`, `README.md`, `coverage.json`, `version-bindings.json`);
`docs/conformance/nomads.md` front matter; `docs/conformance/version-bindings.json` (14 bindings);
`docs/conformance/coverage.json` (158 uncovered, 8 exempt); `docs/README.md:1`; `AGENTS.md`.
Citation-resolution check for `nomads.md` relayed from the SDET red team session, with its stated
limits preserved.

## Files and assets in scope

`tools/docs_check.py`; `tests/test_docs_check.py` gains a case per new finding kind;
`docs/conformance/_template.md` gains the `tier` vocabulary.

## Acceptance and evidence

A record citing a nonexistent schema fails. A record citing a nonexistent proof path fails. A record
claiming a deleted module fails. Each has a test in `tests/test_docs_check.py` that fails for the
stated reason before the check is added — the SDET session is the executable-proof lane and this is
its shape.

## Documentation impact

`docs/conformance/README.md` should state plainly what a green run does and does not establish. The
module docstring of `docs_check.py` already does this well (`:7-9` — "A record can pass every check
here and describe behavior the product no longer has") and that sentence deserves to be where
readers are, not only where authors are.

## Adversarial review and limitations

**The strongest objection is that this card argues from a population of one.** It does, and it says
so. There is no evidence of harm at `233182e` because there is not enough surface for harm to have
occurred yet. A reader entitled to say "come back when a record is actually wrong" is being
reasonable, and the only counter is the timing: records are being added tonight, and the cost of
this fix is monotonically increasing.

**The second objection is that `docs_check.py` never claimed to do this.** True, and its docstring
is unusually honest about it — `:7-9` explicitly disclaims semantic approval. So the defect is not
that the tool lies. It is that `docs/README.md` and `AGENTS.md` point readers at records as the
authority on what the product does, while the only machine-enforced property of a record is which
modules it claims. **The tool is honest and the surrounding documentation is not.**

**Where this card could be wrong:** if the conformance strategy session has already scoped exactly
this, it is a duplicate and should be closed against theirs rather than merged. I did not reach that
session. `board/in-progress/CONFORMANCE-DOCS.md` is the place to check first.

**One thing this card deliberately does not ask for:** it does not ask for more records. Whether the
158 uncovered modules should be covered, and how fast, is the conformance strategy session's
question and a different trade entirely.

## Handoff

Found by grepping `tools/docs_check.py` for front-matter key reads and finding exactly one, then
tracing `versions:` to `version-bindings.json` and establishing that the record's own list is never
consulted. Reframed from "records may be lying" to "nothing would stop the next one" after the SDET
session established n = 1 with both citations resolving — that correction is theirs and it made the
card falsifiable. Full reasoning in `docs/reviews/233182e-product-red-team.md`, Finding 4 — note
that document's own placement warning, which is an instance of this same class.
