---
conformance: 1
record: template
tier: DECLARED
summary: One present-tense sentence. What this capability does, not how it came to.
modules: []
emits: []
versions: []
proof: []
decisions: []
tickets: []
---

# Conformance: template

## Front matter, and what the checker does with each key

Every key above is read by `tools/docs_check.py`. None of them is decoration and none is
free text you can leave approximate.

| Key | Checked as |
|---|---|
| `conformance` | must be `1`; this gate reads schema 1 |
| `record` | must equal the filename stem, so a record cited by name is findable by it |
| `tier` | must be one of `DECLARED`, `REACHABLE`, `EXERCISED`, `PARITY` — the closed vocabulary in [README](README.md#evidence-tiers). Nothing else is a tier |
| `summary` | must be present and non-empty |
| `modules` | each must exist, and exactly one record may claim each one |
| `emits[].schema` | must exist, or be written `none` or a parenthesised phrase saying plainly that there is none |
| `versions[].id` | must name a binding in `version-bindings.json`, and `assert:` must equal the integer that binding resolves from the code |
| `proof[].path` | must exist **and** be a file one of the three suites discovers: `Sim/tests/test_*.py`, `tests/test_*.py`, `tests/consumer_*.py` |
| `proof[].establishes` | must be present; a proof citation that does not say what it proves is a filename |
| `tickets`, `decisions` | warn when a path does not resolve — cards move between folders and a hard failure would punish the move |

Write `key: []` for an empty list. A continuation line under a `- ` item belongs to that
item, so `schema:`, `assert:` and `establishes:` go one indent deeper than the `- ` they
qualify, and nothing else does.

Copy this file, rename it to the capability's noun, and delete every instruction line.
Keep the nine headings, in this order, in every record. A heading with nothing under it
is a finding, not a placeholder — if a section genuinely does not apply, say so in one
sentence and why.

## What it produces

One paragraph, present tense. What a caller gets. No history, no roadmap, no dates.

## Entry points

A table of the symbols a caller actually reaches for, not every public name. Curated on
purpose: a transcription of every `def` in the package is a worse-formatted `help()`.

| Symbol | Where | What a caller gets |
|---|---|---|

## Inputs it reads

The blocks, layers, catalogues and config this depends on. Name what must already exist
in the world for this to run at all.

## Artifacts it writes

The key it writes, its schema, how its ids are formed, and whether they survive an age
transition. State the determinism guarantee here and mark it as an invariant.

Record here any fact that looks incidental and is load-bearing — the kind an optimiser
rationalises away because it reads like an accident. A worked example: a school with no
nodes and no edges sums to integer zero, and `strength * -math.expm1(-0)` yields
negative zero, which serialises as `-0.0`. The four hidden schools take that path in
every world, so a short-circuit of the empty case that returns plain `0.0` changes the
bytes. If a fact like that is only discoverable by breaking it, it belongs in the
record.

## Where it runs

The stage, gate or trigger. One or two sentences. If it runs at more than one attach
site, say so — that is where replay bugs live.

## Versions asserted

Every version integer as a marker, never as bare prose, so the checker can compare it
against the code, written as `<!-- conformance:version <id>=<n> -->`. Add the binding to
`version-bindings.json` if one does not exist yet.

## Proven by

Test file, and in one clause what it establishes. Anything claimed above tier `DECLARED`
must cite the file under `proof:`. The checker resolves that the file exists and that a
suite discovers it; it does not run the test and it does not read this clause. Do not cite
a suite that merely compiles or imports the code.

## Why it works this way

The reasoning, carried over when this record absorbed its subsystem document. Why this
mechanism and not the obvious alternative. This is the section that makes the record
worth reading rather than merely correct.

## Does not establish

Mandatory, at least one bullet, and write it before the sections above rather than
after. If you cannot say what the evidence fails to establish, you do not yet understand
it well enough to say what it does. Name untested paths, authored constants presented as
derived, and anything that is true only at the seed someone happened to check.
