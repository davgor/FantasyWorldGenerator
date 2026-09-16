# Portable kernel contracts v1

ML-01c/d define a new kernel boundary; ML-02 implements its first bounded counter transition. This does not replace recipe-3 terrain generation, its SHA-derived child seeds, Python `random.Random` streams, floating geography, age API or saved-world contract. No generated state can reference a new asset. World/asset envelopes and generator/seed versions remain unchanged.

## Numeric and random-stream contract (ML-01c)

Authoritative kernel values are integers in `[-9007199254740991, 9007199254740991]` (the exact binary64 integer domain). Time, revisions, epochs and counters are nonnegative. Simulation time is absolute integer milliseconds; the kernel never reads wall time or rounds fractional seconds. Callers must supply already-resolved integer ticks. Addition is checked before committing effects; values never wrap or saturate. Native implementations must use at least signed 64-bit storage with checked domain limits. Equality and threshold decisions are exact; there is no authoritative floating tolerance.

Random stream version 1 is an indexed SHA-256-based pseudorandom-word generator, not the legacy world's PRNG. `kernel_numeric.random_word(seed, stream, index, version=1)` is a pure function. The seed is exactly 16 lowercase hexadecimal digits representing an unsigned 64-bit word. Stream names match `[a-z][a-z0-9._-]{0,63}`; indices are integers from 0 through 9007199254740991. There is no global RNG state or implicit counter advance, and indices cannot wrap.

Hash this byte sequence with SHA-256, take its first eight bytes in network/big-endian order, and return 16 lowercase hexadecimal digits:

```text
ASCII "MathLab/stream/v1" + NUL
+ 8 seed bytes (big endian)
+ 1 unsigned byte giving the ASCII stream-name length
+ stream-name ASCII bytes
+ 8 index bytes (big endian)
```

Recommended separate domains are `terrain`, `architecture`, `ecology`, `structure-presentation` and `cosmetics`. Other valid names are separate domains, not aliases. Calling or changing one stream does not advance another. Domains partition the input namespace; this is not a cryptographic security API or a claim that different names can never produce equal truncated words. Persist seed, stream version/name and next index with any future rule that uses these words. The counter rule itself consumes no randomness.

`unit_float(word)` maps a hexadecimal word to `(word >> 11) / 2^53`, yielding a binary64 value in [0,1). This is an explicit optional sampling conversion, not permission to store floats in authoritative kernel snapshots. Any rule needing a different numeric model needs its own versioned decision. Coordinate-v1 fixture tolerances remain separate from this integer kernel contract.

## Canonical JSON and hashes

`canonical_bytes(value, version=1)` emits compact ASCII JSON, with keys ordered by Unicode scalar/code-point order, no whitespace and no final newline. Arrays preserve their order; event arrays are explicitly normalized by the counter rule before serialization. Strings have no Unicode normalization: composed and decomposed spellings remain distinct. Quotes/backslashes and controls use JSON escapes, non-ASCII characters use lowercase `\u` escapes, and non-BMP scalars use surrogate-pair escapes. Slash is not escaped. Unpaired surrogates are rejected. These are project-specific canonical rules, not a claim of RFC 8785 compliance.

The value domain is null, booleans, bounded integers, Unicode scalar strings, arrays and string-keyed objects. Floats—including 1.0, -0.0, NaN and infinity—are rejected. Integer JSON `-0` decodes as zero. Strings/numeric booleans are never coerced to integers. `digest(value)` is the lowercase SHA-256 of those exact canonical bytes.

`canonical_loads` accepts UTF-8 bytes without a BOM, rejects duplicate object keys, rejects floating/exponent numeric tokens and nonstandard constants, and applies the same value constraints. Noncanonical whitespace/key ordering may be read and then normalized. Integer tokens are length-checked before conversion. Limits are 1 MiB for encoded input/output, 4096 UTF-8 bytes per string/key, depth 32 (root depth zero), and 16384 value/key nodes. Cycles and non-JSON Python objects fail. The parser does not claim a hard real-time deadline, but input and resulting state sizes are bounded.

[`Fixtures/kernel-numeric-v1.json`](../Fixtures/kernel-numeric-v1.json) contains independently authored canonical strings and stream byte frames. Expected hashes/words were obtained using `openssl dgst -sha256`, without importing the new oracle. Test cases include Unicode key ordering, stream separation, zero/max float conversion, integer limits and rejected encodings. The Python reference and native numeric implementation run these same vectors; native SHA tests also cover block/padding boundaries and a one-million-byte input.

## Identity, envelopes and failures (ML-01d)

Structural envelopes are in [`schemas/counter-kernel.schema.json`](schemas/counter-kernel.schema.json). Version 1 includes `mathlab.counter-state`, `mathlab.counter-event`, `mathlab.counter-command`, `mathlab.counter-candidate`, and `mathlab.failure`. State also declares `rules_version: 1` and `numeric_version: 1`. Unknown schema IDs or versions are rejected; there is no migration or fallback. Extra or missing fields are invalid. Standard JSON Schema cannot enforce every lexical/accounting rule: the strict decoder and semantic oracle remain required, including rejection of floating integer-valued tokens such as 1.0.

IDs are ASCII strings with a type prefix (`world:`, `actor:`, `event:`, `counter:`), followed by `[a-z0-9][a-z0-9._-]{0,63}`. The host allocates a stable unique world ID and preserves it with saves. Actor, event and target IDs are scoped by that world; they are not display names, array indices, UObject pointers or derived from presentation details. The first rule supports only `counter:main`. A wrong world or unsupported target fails. Actor IDs identify already accepted host facts: the kernel does not authenticate an actor or establish ownership of arbitrary resources.

Event identity is `(world_id, event_id)` for the lifetime of the retained state. Reusing that identity with different actor, target, time, delta or any other event field is a conflict. Receipts retain the complete event and its resulting counter value, not just an invocation count or a lossy hash. No receipt is evicted to make room. Capacity exhaustion requires a future reviewed retention/migration contract; IDs must not silently become reusable. Display-name changes and actor materialization cannot change these identities.

`KernelError` carries a stable `code`; `document()` returns the versioned failure envelope. Human-readable message text is diagnostic and may change. Codes are:

- `INVALID_INPUT`: malformed shape/type, inconsistent checkpoint accounting/order, invalid IDs or canonical encoding.
- `UNSUPPORTED_VERSION`: unknown schema identity or contract/rule/numeric version.
- `UNKNOWN_ID`: wrong world or unsupported counter target.
- `STALE_REVISION`: evaluated/current state mismatch or an incompatible expected revision.
- `AUTHORITY_MISMATCH`: command epoch does not match the snapshot epoch.
- `CONFLICTING_EVENT`: one event identity has different payloads.
- `INTERVAL_CONFLICT`: time rewind, out-of-interval new work, changing a pending target or inserting work into an accepted interval.
- `WORK_BUDGET`: budget is not an integer in 1–64.
- `STATE_CAPACITY`: too many command events or retained/pending receipts.
- `NUMERIC_OVERFLOW`: applying the complete interval or advancing revision would exceed the numeric domain.
- `INVALID_CANDIDATE`: commit data does not match re-evaluation of its captured base and command.

Failures do not mutate caller state. Error codes do not promise that blindly retrying is useful: the host must refresh state, correct input or resolve capacity as appropriate. The prior terrain/coordinate helpers retain their existing `ValueError` APIs; this structured failure contract applies to the new kernel only.

## Bounded accepted-counter proof (ML-02)

This is a headless reference proof, not a resource economy, damage solver, job system or live world importer. It creates no art requirements. `counter_kernel.initialize(world_id, authority_epoch=0)` creates time/revision/counter zero with no receipts. It does not load or overwrite storage; the host must never use fresh initialization to replace an existing occupied world.

An accepted event specifies schema/version, world/event/actor/target IDs, integer `time_ms` and positive integer `delta`. A command specifies schema/version, world ID, authority epoch, expected revision, target time, effect budget and events. At most 64 input entries are accepted. Identical entries collapse; conflicting duplicates fail. Events sort by `(time_ms, event_id)` in ASCII order, independent of input order.

`evaluate(snapshot, command)` validates the entire accepted interval first, including all eventual additions and receipt capacity. It then prepares at most `budget` new increments. It never mutates the input. The result is a frozen `Candidate` containing immutable canonical byte envelopes for the base snapshot, normalized command, proposed snapshot and newly produced receipts/effects, plus `work_used`. `dump_candidate` / `load_candidate` provide the versioned JSON transport envelope and validate it by re-evaluation.

For a fresh interval, unseen events must lie in `(completed_time_ms, target_time_ms]`. Up to 256 receipts may be retained, counting accepted pending work. The budget limits new effects, not parsing or integrity checking: validation/commit re-evaluation also scans bounded state. There is no hidden loop over elapsed milliseconds. An empty interval can advance directly to its target. Revisions increment once per changed committed candidate, including an empty time advance, and never wrap.

If the effect budget ends first, `pending` stores the fixed target and remaining sorted events. Completed `time_ms` stays unchanged. The next command must use the current revision and same target; it may omit events or repeat already accepted identical ones, but may not insert new events. The last effect completes the interval and advances time to the target. Different budget partitions yield identical counters, receipts and completed time, while commit counts/revisions legitimately differ.

Pending states are resumable work checkpoints: their counter and receipts can include work after completed time. Persist them coherently, but do not present them as a fully completed gameplay interval. Gameplay publication/materialization should wait for `pending: null`; retained receipts give the host stable effect IDs for any later delivery. The proof does not provide a network outbox or exactly-once external side effects.

An identical completed-event delivery with a target no later than completed time and an expected revision no newer than current is a no-op acknowledgement, even after later intervals. It cannot rewind time or apply an effect twice. A future expected revision still fails. Authority must always match, and conflicting payloads are rejected before the no-op path. Other stale commands fail; partial-interval resumes require refreshed state. Retrying a previously prepared candidate against its exact already-committed result is also a no-op.

`commit(current_snapshot, candidate)` re-evaluates the captured base/command, rejects altered candidate data, and compares the complete current snapshot with the captured base or exact proposed result. It returns commit data only; it does not write a file, lock a database or arbitrate concurrent callers. The host must atomically compare the authoritative revision/base and durably store the resulting snapshot, receipts and outbound work together before exposing completion. On durable write failure discard the candidate and retry from unchanged committed state. Epoch changes/handover, receipt compaction and actor authentication remain host/future work.

`dump_snapshot` and `load_snapshot` validate schema, versions, finite integer domain, monotonic ordering, unique identities, counter/receipt accounting, pending interval bounds and capacity. Saving/loading a checkpoint does not need an in-memory kernel session. Integrity validation is not a signature proving that input events were authorized; storage and accepted gameplay facts must come from the authoritative host.

[`Fixtures/counter-kernel-v1.json`](../Fixtures/counter-kernel-v1.json) independently specifies a three-event interval: +5 and +3 at tick 2, +2 at tick 7, target 10. Budget 1 yields counter 5, time 0 and two pending events. Resume budget 2 yields counter 10, time 10 and three receipts. Tests cover order changes, duplicate/conflicting events, stale state/epoch, rejected late insertion, full-interval overflow validation, failed/duplicate commit, altered candidates, capacity, canonical snapshots and a fresh-process resume.

## Scope and compatibility

The capability descriptor advertises `kernel_numeric`, `counter_kernel`, `counter_state_json`, `counter_command_json` and `counter_candidate_json` version 1 for the Python reference. It still rejects native/Unreal/cooked support. Core snapshot/event/rule changes require explicit new versions and fixtures; no silent reinterpretation of saved state is allowed. Successful Python tests establish this bounded proof only, not native execution, durable storage, engine materialization, cooked packaging or general persistent-world behavior.

## Native typed proof (ML-03a)

[`Core/`](../Core/README.md) implements the same counter transition with signed 64-bit storage and checked safe-integer limits. Typed fixture inputs are compiled into a C++17 executable; its checkpoint and completion bytes match the shared fixture and Python canonical encoding. Native cases also cover ordering, retries, conflicting IDs, stale revision/epoch, interval insertion, capacity, overflow, candidate alteration and invalid versions. No Unreal/Python runtime is needed by the executable.

ML-03b adds strict JSON decoding, candidate transport and SHA-256 indexed streams in `Core/json.*`, `Core/wire.*` and `Core/numeric.*`. The wire driver rejects duplicate keys, fractional/exponent numbers, unsafe integers, invalid UTF-8/surrogates and oversized inputs. Shared numeric vectors, fresh-process Python/native candidate exchange, randomized deterministic JSON comparisons and capacity-bound transitions establish the scoped counter/numeric conformance. The public contract versions remain 1; native structs remain outside the wire/ABI contract. Error message wording may differ; stable failure codes and valid canonical output are shared.

ML-03c adds a deterministic, content-addressed source proof bundle and an isolated headless consumer; see `Core/README.md`. Its manifest is explicitly unqualified source, and its local build report records tested source hashes and compiler/platform. This is not an immutable hosted release or Unreal/cooked qualification. No existing generator seed, schema, asset state or world behavior changes.
