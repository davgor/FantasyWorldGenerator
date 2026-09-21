"""Regenerate Fixtures/world-handle-v1.json, the cross-host parity fixture for handles.

A handle is only a shared name if two implementations derive it the same way. This writes
the cases a second implementation checks itself against: tiny documents whose transfer
bytes are written out in full, so an implementer compares the serialisation before
comparing the digest and learns which of the two is wrong.

Run from the repository root: python tools/build_world_handle_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

from fantasy_world_generator import world_handle as wh  # noqa: E402
from fantasy_world_generator.cli import world_document  # noqa: E402

TARGET = ROOT / "Fixtures" / "world-handle-v1.json"

# Seed 42 at size 17 is the reference configuration the consumer suites use. Phase 4
# rather than 16 so the case costs a tenth of a second to check rather than seventy
# seconds: this case pins the rule against a real generated document, and a richer world
# exercises more producers but not more of the rule.
WORLD_REQUEST = {"recipe_version": 3, "seed": 42, "overrides": {"size": 17, "phase": 4}}

CASES = [
    ("empty", {}),
    ("scalars", {"a": 1, "b": "two", "c": True, "d": None}),
    # Written with keys out of order on purpose: the handle must not depend on it.
    ("key order", {"z": 1, "m": {"y": 2, "b": 3}, "a": 4}),
    ("timing at depth", {"a": 1, "timing_ms": {"total": 3.5},
                         "b": {"timing_ms": 9, "c": [{"timing_ms": 1, "d": 2}]}}),
    ("build stages", {"a": 1, "build_stages": [{"state": {"layers": [1, 2, 3]}}]}),
    # build_stages is dropped at the top level only. A block that happens to carry the
    # same key deeper is content, not lab payload, and must survive.
    ("nested build stages", {"a": {"build_stages": [1]}}),
    ("non-ascii", {"name": "Ceskykrumlov — Květná 街"}),
    # The float case is the parity case. Every value here is a formatting decision a
    # second implementation has to make the same way, and the four at the end straddle
    # the exponent thresholds where Python switches notation.
    ("floats", {"whole": 1.0, "negative zero": -0.0, "repr": 0.1 + 0.2,
                "below the high threshold": 1e15, "at the high threshold": 1e16,
                "above the low threshold": 1e-4, "at the low threshold": 1e-5}),
    ("nesting", {"a": [[], [{}], [{"b": [1, [2, [3]]]}]]}),
]

REJECTED = [
    ("nan", {"a": float("nan")}, "NaN is not JSON; a world carrying one must fail at the "
                                 "boundary rather than travel"),
    ("infinity", {"a": float("inf")}, "same rule as NaN"),
]


def main() -> int:
    cases = []
    for name, document in CASES:
        payload = wh.transfer_bytes(document)
        cases.append({
            "name": name,
            "document": document,
            "transfer_bytes": payload.decode("utf-8"),
            "transfer_length": len(payload),
            "handle": wh.handle(document),
        })

    rejected = []
    for name, document, why in REJECTED:
        try:
            wh.transfer_bytes(document)
        except ValueError as exc:
            rejected.append({"name": name, "document_note": name, "why": why,
                             "raises": type(exc).__name__})
        else:  # pragma: no cover - a regression in the encoder, not a normal path
            raise SystemExit("%s was accepted; allow_nan=False is not in force" % name)

    document = world_document(WORLD_REQUEST)
    profiled = world_document(WORLD_REQUEST, build_stages=True, timings=True)

    fixture = {
        "fixture": "world-handle",
        "version": 1,
        "note": ("Parity cases for the world-handle rule. Regenerate with "
                 "tools/build_world_handle_fixture.py. A second implementation should "
                 "match transfer_bytes first and the handle second; matching the digest "
                 "while missing the bytes means agreeing by luck."),
        "rule": {
            "algorithm": "sha256",
            "prefix": wh.HANDLE_PREFIX,
            "digits": wh.HANDLE_DIGITS,
            "drop_top_level": ["build_stages"],
            "drop_any_depth": ["timing_ms"],
            "encoding": ("JSON with sorted keys, separators ',' and ':', no whitespace, "
                         "UTF-8, non-ASCII unescaped, NaN and Infinity rejected"),
            "float_format": ("Python repr, which is what json.dumps writes: the shortest "
                             "decimal that reads back as the same double, laid out "
                             "CPython's way. Scientific when the decimal point position "
                             "is at or below -4 or above 16, positional otherwise; a "
                             "positional result always carries a fractional part; "
                             "negative zero keeps its sign; an exponent is written with "
                             "a sign and at least two digits. So 1e+16 and 1e-05 and "
                             "1000000000000000.0 and 1.0 and -0.0, all pinned by the "
                             "'floats' case."),
            "float_format_implementations": [
                "Core/castlegeometry.cpp python_repr (std::to_chars shortest)",
                "Core/cityshapes.cpp py_repr (precision search)",
            ],
            "float_format_note": ("Two native implementations of this rule already "
                                  "exist and agree. A host porting the handle should "
                                  "reuse one of them: a third implementation of one "
                                  "rule is how they start disagreeing."),
        },
        "cases": cases,
        "rejected": rejected,
        "world": {
            "request": WORLD_REQUEST,
            "handle": wh.handle(document),
            "transfer_length": len(wh.transfer_bytes(document)),
            "generator_version": document.get("generator_version"),
            "profiling_is_invisible": {
                "note": ("The same request generated with build_stages and timings must "
                         "produce the same handle; that is what makes the name a "
                         "function of the world rather than of the run."),
                "handle_with_profiling": wh.handle(profiled),
            },
        },
    }

    TARGET.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("wrote %s (%d cases, %d rejections)"
          % (TARGET.relative_to(ROOT).as_posix(), len(cases), len(rejected)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
