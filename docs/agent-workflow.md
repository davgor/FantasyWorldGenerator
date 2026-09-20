# Agent development workflow

## Start or resume

Read `AGENTS.md`, this file, and the canonical document for the behavior being changed. Inspect the working tree before editing. State the intended outcome, public contracts affected, and acceptance checks.

## Implement and verify

For simulation, catalogue, CLI, and schema changes, begin with a behavioral test that fails for the intended reason. Preserve deterministic ordering and serialization. Increment a schema or recipe version when a consumer could otherwise misread changed semantics.

Keep the mathematical package independent of Unreal. Test an Unreal adapter in the actual editor when one is introduced; source existence and valid JSON alone are not runtime acceptance.

## Conformance

Run `python tools/docs_check.py` before you start, so you find inherited drift before
your own change is blamed for it.

Find the record that claims the module you are changing. `python tools/docs_check.py
--list-uncovered` prints what no record claims yet, and the `modules:` front matter of
each record in `docs/conformance/` covers the rest. Exactly one record owns a module; if
two would, decide which owns it rather than describing it twice.

A new module must be claimed. One that lands unclaimed fails the next run, and there is
no version of that failure that belongs to someone else. If the record genuinely cannot
be written yet, add the module to the `uncovered` list in
`docs/conformance/coverage.json` with the ticket that will remove it. That list may
shrink and may not grow.

When a version moves, update its `<!-- conformance:version id=N -->` marker and the
sentence beside it, and add a binding to `docs/conformance/version-bindings.json` if
none covers it. If the value is emitted from more than one site, the checker reports the
disagreement rather than guessing — declare the authoritative site.

Behavior change with no capability change: change no record, and write the reason in the
handoff. Do not make meaningless prose edits to satisfy a checkbox.

## Documentation and review

Update canonical docs alongside behavior. Record consequential compatibility choices in a short decision document if they cannot be explained locally. Review changes adversarially for replay compatibility, finite JSON values, bounded inputs, path safety, catalogue completeness, and misleading integration claims.

## Closeout

Run `python tools/validate_repo.py`. Its `checks` stage runs `tools/docs_check.py`, so a passing validator means the documents point at real files and their version markers match the code. It does not mean anyone read them. Report completed behavior, exact verification, which conformance records changed and why, known limitations, and the next concrete integration action. Do not commit, push, or publish unless the user requests it.

