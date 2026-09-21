"""Content-addressed world handles and the envelope a host returns for one operation.

A handle names one immutable version of a world. It is the sha256 of the bytes the
generator hands over -- the transfer form -- so a host that stores what it received can
name it without re-serialising anything, and two hosts holding the same version agree on
its name without sharing code.

Nothing here holds state and nothing here stores a world. The store belongs to the host,
which is Unreal or Electron, whichever gets built; this module only says what a version
is called, which bytes that name is taken over, and what one operation reports. The
separation is deliberate: `icarus_sim` stays a stateless producer that has never heard of
a handle, and the glue that does know about handles cannot reach back into it.

See `docs/decisions/026-world-handles-and-the-host-store.md` for the store contract a
host must satisfy, and `docs/conformance/world-handles.md` for what is proven.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional

from icarus_sim.terrain_errors import retired_version

# The rule that strips wall clock from a document. Imported rather than restated: it is
# the reason an exported world is byte-reproducible, and a second implementation of it
# would let the transfer form drift from the export form silently.
from .cli import _without_timings

STORE_CONTRACT_VERSION = 1
HANDLE_PREFIX = "w_"
HANDLE_DIGITS = 16

ENVELOPE_SCHEMA = "fantasy-world-generator.operation"

#: Every verb a host can be asked for, and what it does to the store.
#:
#: ``root`` starts a lineage, ``version`` produces a child of the world it was given, and
#: ``read`` answers a question without producing a version at all. ``report`` is the
#: top-level key that verb stamps its own account into, where it stamps one; most do not,
#: which is why the envelope leans on the operations record instead.
OPERATIONS = {
    "generate": {"kind": "root", "report": None},
    "advance-age": {"kind": "version", "report": None},
    "advance-time": {"kind": "version", "report": "time_advance"},
    "summon": {"kind": "version", "report": None},
    "depart": {"kind": "version", "report": None},
    "corrupt": {"kind": "version", "report": "corruption"},
    "cleanse": {"kind": "version", "report": "cleanse"},
    "nomad": {"kind": "version", "report": None},
    "found-settlement": {"kind": "version", "report": "settlement_founding"},
    "moon": {"kind": "read", "report": None},
    "patch": {"kind": "read", "report": None},
}

_MISSING = object()


# --------------------------------------------------------------------------- the name

def transfer_document(document: dict) -> dict:
    """The world as it crosses to a host: no profiling residue, no lab-only payload.

    Two things come off. `build_stages` is sixteen cumulative snapshots the browser lab's
    stage inspector reads and no consumer does -- 56% of the bytes on a measured
    size-17 world. `timing_ms` is wall clock, and it is the only reason two runs of one
    seed ever differed, which is why `cli` already strips it on the way out.

    Dropping both here is what makes the handle a function of the world rather than of
    the run: a world generated for profiling and the same world generated for a game
    carry the same name.
    """
    if not isinstance(document, dict):
        raise TypeError("a world document is an object, received %r" % type(document).__name__)
    return _without_timings({k: v for k, v in document.items() if k != "build_stages"})


def transfer_bytes(document: dict) -> bytes:
    """The exact bytes a handle is taken over, and the exact bytes to hand a host.

    Sorted keys and no whitespace so the rendering is a function of content and not of
    the order a producer happened to build its dict in. UTF-8 because names carry
    non-ASCII. `allow_nan=False` because NaN is not JSON: a world carrying one must fail
    here, at the boundary, rather than travel and fail somewhere that cannot say why.

    The canonical form and the wire form are the same form on purpose. A host that
    digests what it received and a generator that digests what it sent agree by
    construction, so cross-host parity needs no float-formatting negotiation -- only a
    host that *generates* natively has to reproduce these bytes, and that is the existing
    native-parity problem rather than a new one.
    """
    return json.dumps(transfer_document(document), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def handle(document: dict) -> str:
    """`w_` followed by the first 16 hex digits of sha256 over the transfer bytes."""
    digest = hashlib.sha256(transfer_bytes(document)).hexdigest()
    return HANDLE_PREFIX + digest[:HANDLE_DIGITS]


def is_handle(value: Any) -> bool:
    """Whether a value is shaped like a handle. Says nothing about a world existing."""
    return (isinstance(value, str) and value.startswith(HANDLE_PREFIX)
            and len(value) == len(HANDLE_PREFIX) + HANDLE_DIGITS
            and all(c in "0123456789abcdef" for c in value[len(HANDLE_PREFIX):]))


# --------------------------------------------------------------------------- staleness

def check_generator(document: dict, running: Any) -> None:
    """Refuse a world this generator will not read, in the vocabulary every refusal uses.

    A generated world is disposable until the first player-facing release (decision 023),
    so a store outlives the generator that filled it and a handle minted last week can
    name a world this build must not touch. `retired_version` is the right shape and
    already says the right thing -- regenerate rather than migrate -- and because it
    carries `retry=False` a controller stops resending instead of hunting for a value
    that would work.
    """
    held = document.get("generator_version")
    if held != running:
        raise retired_version("generator_version", held, (running,))


# --------------------------------------------------------------------------- the report

def changed_paths(before: dict, after: dict, depth: int = 2) -> list:
    """Dotted paths, to `depth` levels, whose contents differ between two versions.

    Two levels is the granularity the scripted consumers already speak -- they assert on
    `history.ages` and `settlements.sites` -- so a model reading an envelope sees the
    same names the reference trajectories do.

    This is the only account of a call that always exists. Four of the eight version
    verbs stamp no report block of their own, and for those the alternative is telling a
    caller that something happened without telling it what.

    Compared in the transfer form, not as handed in. Two versions are the same version
    when their transfer bytes match, so a path that cannot differ between two distinct
    versions is not a change: reporting `timing_ms` here would name the one key the
    handle is defined to ignore, on every single call.
    """
    out: list = []
    _diff(transfer_document(before), transfer_document(after), "", max(1, depth), out)
    return out


def _diff(before: dict, after: dict, prefix: str, depth: int, out: list) -> None:
    for key in sorted(set(before) | set(after)):
        mine, theirs = before.get(key, _MISSING), after.get(key, _MISSING)
        if mine is not _MISSING and theirs is not _MISSING and mine == theirs:
            continue
        if mine is _MISSING and theirs is _MISSING:  # pragma: no cover - set union
            continue
        path = prefix + key
        if depth > 1 and isinstance(mine, dict) and isinstance(theirs, dict):
            _diff(mine, theirs, path + ".", depth - 1, out)
        else:
            out.append(path)


def last_operation(document: dict) -> Optional[dict]:
    """The final `history.operations` entry, which is the one uniform per-call record.

    Every version-producing API appends one -- age, time, visitation, departure,
    corruption, cleanse, nomad and founding -- and they are the only thing all eight have
    in common. The per-API report blocks are richer and four of the eight have none.
    """
    operations = (document.get("history") or {}).get("operations") or []
    return operations[-1] if operations else None


def envelope(operation: str, after: dict, before: Optional[dict] = None) -> dict:
    """What a host returns for one call: a name, its parent, what moved, and the record.

    Never the world. A world is 2-100 MB and an envelope is kilobytes, which is the whole
    reason a handle exists: a caller whose context is finite can drive a world it can
    never hold.

    `before` is the world the call was given. Omit it only for `generate`, which has no
    parent -- `changed` is then empty, because nothing can differ from a world that did
    not exist. Reads produce no version and therefore no envelope; they answer with their
    own document.
    """
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise ValueError("unknown operation %r; known: %s"
                         % (operation, ", ".join(sorted(OPERATIONS))))
    if spec["kind"] == "read":
        raise ValueError("%r answers a question and produces no version, so it has no "
                         "envelope; return its own document" % operation)
    if spec["kind"] == "root" and before is not None:
        raise ValueError("%r starts a lineage and has no parent" % operation)
    if spec["kind"] == "version" and before is None:
        raise ValueError("%r transforms a world, so the world it was given is required "
                         "to say what changed" % operation)

    report_key = spec["report"]
    return {
        "schema": ENVELOPE_SCHEMA,
        "schema_version": STORE_CONTRACT_VERSION,
        "operation": operation,
        "handle": handle(after),
        "parent": handle(before) if before is not None else None,
        "generator_version": after.get("generator_version"),
        "changed": changed_paths(before, after) if before is not None else [],
        "operation_record": last_operation(after),
        "report": after.get(report_key) if report_key else None,
    }


def version_operations() -> Iterable[str]:
    """The verbs that produce a new version, in the order a host should list them."""
    return tuple(name for name, spec in OPERATIONS.items() if spec["kind"] == "version")
