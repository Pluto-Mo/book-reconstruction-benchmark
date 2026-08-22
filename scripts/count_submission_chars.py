#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


COUNTER_VERSION = "nonwhitespace-codepoints-v1"
UNICODE_WHITESPACE_PROFILE = "Unicode-White_Space-stable-v1"

# The Unicode White_Space property. Pinning the set avoids Python-version
# differences in str.isspace() and makes verifier results reproducible.
WHITE_SPACE_CODEPOINTS = frozenset(
    {
        *range(0x0009, 0x000E),
        0x0020,
        0x0085,
        0x00A0,
        0x1680,
        *range(0x2000, 0x200B),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    }
)


def count_text(text: str) -> dict[str, int]:
    raw_codepoints = len(text)
    whitespace_codepoints = sum(
        1 for character in text if ord(character) in WHITE_SPACE_CODEPOINTS
    )
    return {
        "raw_codepoints": raw_codepoints,
        "whitespace_codepoints": whitespace_codepoints,
        "nonwhitespace_codepoints": raw_codepoints - whitespace_codepoints,
    }


def evaluate_bounds(
    nonwhitespace_codepoints: int,
    minimum: int | None,
    maximum: int | None,
) -> bool | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and nonwhitespace_codepoints < minimum:
        return False
    if maximum is not None and nonwhitespace_codepoints > maximum:
        return False
    return True


def build_result(
    path: Path,
    text: str,
    minimum: int | None,
    maximum: int | None,
) -> dict[str, Any]:
    counts = count_text(text)
    return {
        "counter_version": COUNTER_VERSION,
        "unicode_whitespace_profile": UNICODE_WHITESPACE_PROFILE,
        "path": str(path),
        "encoding": "utf-8",
        "normalization": "none",
        "scope": "entire_submission_file",
        **counts,
        "min_chars": minimum,
        "max_chars": maximum,
        "within_bounds": evaluate_bounds(
            counts["nonwhitespace_codepoints"], minimum, maximum
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Count non-whitespace Unicode code points in an entire UTF-8 "
            "submission file."
        )
    )
    parser.add_argument("submission", type=Path)
    parser.add_argument("--min-chars", type=int)
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    if args.min_chars is not None and args.min_chars < 0:
        parser.error("--min-chars must be non-negative")
    if args.max_chars is not None and args.max_chars < 0:
        parser.error("--max-chars must be non-negative")
    if (
        args.min_chars is not None
        and args.max_chars is not None
        and args.min_chars > args.max_chars
    ):
        parser.error("--min-chars cannot exceed --max-chars")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        text = args.submission.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Submission not found: {args.submission}", file=sys.stderr)
        return 2
    except UnicodeDecodeError as exc:
        print(f"Submission is not valid UTF-8: {exc}", file=sys.stderr)
        return 2

    result = build_result(
        args.submission,
        text,
        args.min_chars,
        args.max_chars,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 1 if result["within_bounds"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
