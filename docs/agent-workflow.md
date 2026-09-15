# Agent development workflow

## Start or resume

Read `AGENTS.md`, this file, and the canonical document for the behavior being changed. Inspect the working tree before editing. State the intended outcome, public contracts affected, and acceptance checks.

## Implement and verify

For simulation, catalogue, CLI, and schema changes, begin with a behavioral test that fails for the intended reason. Preserve deterministic ordering and serialization. Increment a schema or recipe version when a consumer could otherwise misread changed semantics.

Keep the mathematical package independent of Unreal. Test an Unreal adapter in the actual editor when one is introduced; source existence and valid JSON alone are not runtime acceptance.

## Documentation and review

Update canonical docs alongside behavior. Record consequential compatibility choices in a short decision document if they cannot be explained locally. Review changes adversarially for replay compatibility, finite JSON values, bounded inputs, path safety, catalogue completeness, and misleading integration claims.

## Closeout

Run `python3 tools/validate_repo.py`. Report completed behavior, exact verification, known limitations, and the next concrete integration action. Do not commit, push, or publish unless the user requests it.

