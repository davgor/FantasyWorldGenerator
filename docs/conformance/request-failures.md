---
conformance: 1
record: request-failures
tier: EXERCISED
summary: Refuses a malformed generate request with a versioned envelope naming the field, the value received, the bound or vocabulary violated, and a value that would work.
modules:
  - Sim/icarus_sim/terrain_errors.py
emits:
  - path: (not a world block)
    schema: Contracts/schemas/counter-kernel.schema.json
versions:
  - id: request-failure
    assert: 2
proof:
  - path: tests/test_failure_envelope.py
    establishes: every bounded control reports its own violation in both directions, a one-character typo names the control meant, a pinned control says it is pinned, a closed vocabulary is listed, a retired version is not retryable, and the detail tier is separable
  - path: tests/consumer_orchestrator.py
    establishes: an orchestrator recovers from the seven refusals a small model actually produces, using only what the envelope carries
decisions:
  - docs/decisions/025-controls-are-a-machine-contract.md
tickets: []
---

# Conformance: request-failures

## What it produces

A refused request raises `RequestError`, whose `document()` is a
`fantasy-world-generator.failure` envelope <!-- conformance:version request-failure=2 -->.
Beyond the code and message version 1 already carried, it names the field, echoes the value
received, states the bound or the closed vocabulary that was violated, and where one exists
offers a value that would be accepted. A caller can build its next request from the envelope
alone, without parsing prose.

## Entry points

Callers reach these; everything else in the module is a constructor detail.

| Symbol | Where | What a caller gets |
|---|---|---|
| `RequestError` | `terrain_errors` | the exception itself, a `ValueError` subclass |
| `RequestError.document(detail=True)` | `terrain_errors` | the envelope; `detail=False` gives the core five fields only |
| `nearest(name, candidates)` | `terrain_errors` | names a caller plausibly meant, best first |
| `unknown_field`, `out_of_range`, `wrong_type`, `invalid_choice`, `retired_version`, `over_capacity`, `cross_field` | `terrain_errors` | the seven refusal shapes the request boundary raises |

## Inputs it reads

Nothing from a world. A refusal is built from the control definition it was handed, which
in practice comes from `terrain_world.registry(3)` or a literal for the request-root fields.
The module imports only `difflib` and `math`.

## Artifacts it writes

No world block. The envelope is a return value, and the same shape the native core emits
from `Core/wire.cpp` `failure_json`.

**Invariant: `RequestError` subclasses `ValueError`.** Every existing handler at the CLI,
the lab server and the four leaf packages catches `ValueError`; if this stopped being one,
refusals that are currently reported would start escaping as tracebacks.

**Invariant: the code vocabulary is the eleven values already declared** in
`Contracts/schemas/counter-kernel.schema.json`, whose `failure` definition is
`additionalProperties: false`. The boundary uses three of them. Widening the enum is a
contract change, and because `Core/counter.hpp` makes `Error::what()` the code itself, a new
code would also silently change what a host prints.

**Invariant: the detail tier is separable at emit time.** `document(detail=False)` returns
exactly `schema`, `schema_version`, `code`, `message` and `field`. Whether `suggestion`
reduces a small model's retry count is an empirical question, and a field that cannot be
switched off cannot be measured.

## Where it runs

At every request boundary, before any world is built or adopted. `generate_request`
validates the request shape, the seed, the override names and every override value before it
constructs a `Config`, so a refusal costs milliseconds regardless of the world asked for. The
age, visitation, corruption, cleanse, nomad, moon, patch and time boundaries validate their
arguments and the world they were handed before they copy it.

Two shapes carry a distinction the others do not. `unsupported_api` marks a refusal no value
will fix, so a controller stops resending. `refused_by_world` marks a well-formed request the
world will not satisfy where it was asked -- a band on water, a god that does not exist here,
a patch wider than the planet. Every other refusal means send a better value; a caller that
cannot tell the two apart keeps correcting an argument that was never wrong.

## Versions asserted

The envelope is version 2 <!-- conformance:version request-failure=2 -->. Version 1 is
untouched and still emitted by `fantasy_world_generator.kernel_contract.KernelError` and by
the native counter proof.

## Proven by

`tests/test_failure_envelope.py` — 14 tests. The sweep walks every bounded control one step
past each end, over 300 refusals, and asserts each names its own field, echoes its value and
states its bound. A second sweep deletes and transposes a character in every control name and
asserts the original appears in the suggestions.

## Why it works this way

The caller is a local model packaged inside the game, with no one to ask. `Unknown override`
named no key and suggested nothing, which made it the most expensive message in the API: the
only recovery was to re-read documentation the model did not have.

Suggestions fold prefix and substring matches in ahead of `difflib`, rather than after,
because `difflib` alone is good on a typo and poor on a bare prefix — `rain` scores closer to
`radius` than to `rain_passes`, since it is shorter. A bare prefix is what a model produces
when it half-remembers a group name, so it is the case worth getting right.

A new module rather than a home in `terrain_world`: `icarus_sim` imports nothing from
`fantasy_world_generator`, and that arrow must not reverse. Two independent emitters of one
schema, bound by a shared contract rather than shared code, is how this repository already
binds Python to the C++ failure codes.

## Does not establish

- **That any message is accurate.** The tests assert an envelope names its field, echoes its
  value and states its bound. Whether the prose describes the real reason is not checked and
  cannot be.
- **That an LLM retries correctly.** No behavioural claim about any model is made or
  testable here; that measurement belongs to the evaluation harness, which is why the detail
  tier is switchable.
- **Nothing about the native side.** `Core/wire.cpp` still emits version 1 and
  `Core/counter.hpp` still makes `message` a copy of `code`, so an Unreal caller's diagnostic
  is a bare code today. Nothing here changes that.
- **Nothing about `GET /generate`.** `tools/terrain_lab.py` renders the envelope on every
  POST route, but the browser lab's query-string path still answers `send_error`, which is
  an HTML page. The lab's own JavaScript therefore still shows a hardcoded string rather
  than the reason.
- **Nothing about the native side.** `Core/wire.cpp` still emits version 1 and
  `Core/counter.hpp` still makes `message` a copy of `code`, so an Unreal caller's
  diagnostic is a bare code. Deliberately deferred with the rest of the engine work.
