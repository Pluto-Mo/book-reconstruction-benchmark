#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from count_submission_chars import COUNTER_VERSION, count_text


SCHEMA_VERSION = "calibration-mutation-v1"


class MutationError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_repo_path(repo_root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise MutationError(f"{label} must be a non-empty repository-relative path")
    path = (repo_root / value).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise MutationError(f"{label} escapes repository root: {value}") from exc
    return path


def require_unique_marker(text: str, marker: Any, label: str) -> str:
    if not isinstance(marker, str) or not marker:
        raise MutationError(f"{label} must be a non-empty string")
    occurrences = text.count(marker)
    if occurrences != 1:
        raise MutationError(f"{label} must occur exactly once; found {occurrences}")
    return marker


def apply_replace_once(text: str, operation: dict[str, Any]) -> str:
    old = require_unique_marker(text, operation.get("old"), "replace_once.old")
    new = operation.get("new")
    if not isinstance(new, str):
        raise MutationError("replace_once.new must be a string")
    return text.replace(old, new, 1)


def apply_swap_blocks(text: str, operation: dict[str, Any]) -> str:
    first_start = require_unique_marker(
        text, operation.get("first_start"), "swap_blocks.first_start"
    )
    second_start = require_unique_marker(
        text, operation.get("second_start"), "swap_blocks.second_start"
    )
    after_second = require_unique_marker(
        text, operation.get("after_second"), "swap_blocks.after_second"
    )
    first_index = text.index(first_start)
    second_index = text.index(second_start)
    after_index = text.index(after_second)
    if not first_index < second_index < after_index:
        raise MutationError(
            "swap_blocks markers must appear in first_start, second_start, "
            "after_second order"
        )
    return (
        text[:first_index]
        + text[second_index:after_index]
        + text[first_index:second_index]
        + text[after_index:]
    )


def apply_operations(text: str, operations: Any) -> str:
    if not isinstance(operations, list) or not operations:
        raise MutationError("operations must be a non-empty list")
    result = text
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise MutationError(f"operation {index} must be an object")
        operation_type = operation.get("type")
        if operation_type == "replace_once":
            result = apply_replace_once(result, operation)
        elif operation_type == "swap_blocks":
            result = apply_swap_blocks(result, operation)
        else:
            raise MutationError(f"operation {index} has unknown type: {operation_type}")
    return result


def build_variant(spec_path: Path, repo_root: Path) -> dict[str, Any]:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MutationError(f"spec not found: {spec_path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MutationError(f"invalid spec {spec_path}: {exc}") from exc
    if not isinstance(spec, dict):
        raise MutationError(f"spec must be an object: {spec_path}")
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise MutationError(
            f"{spec_path}: schema_version must be {SCHEMA_VERSION}"
        )

    baseline_path = resolve_repo_path(
        repo_root, spec.get("baseline_text_path"), "baseline_text_path"
    )
    output_path = resolve_repo_path(
        repo_root, spec.get("output_text_path"), "output_text_path"
    )
    try:
        baseline_bytes = baseline_path.read_bytes()
    except FileNotFoundError as exc:
        raise MutationError(f"baseline not found: {baseline_path}") from exc
    actual_baseline_sha256 = sha256_bytes(baseline_bytes)
    if spec.get("baseline_sha256") != actual_baseline_sha256:
        raise MutationError(
            f"{spec_path}: baseline SHA-256 mismatch: expected "
            f"{spec.get('baseline_sha256')}, actual {actual_baseline_sha256}"
        )
    try:
        baseline_text = baseline_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MutationError(f"baseline is not valid UTF-8: {baseline_path}") from exc

    output_text = apply_operations(baseline_text, spec.get("operations"))
    if output_text == baseline_text:
        raise MutationError(f"{spec_path}: operations produced no change")
    output_bytes = output_text.encode("utf-8")
    output_sha256 = sha256_bytes(output_bytes)
    output_count = count_text(output_text)["nonwhitespace_codepoints"]

    expected_sha256 = spec.get("expected_output_sha256")
    if expected_sha256 is not None and expected_sha256 != output_sha256:
        raise MutationError(
            f"{spec_path}: expected output SHA-256 {expected_sha256}, "
            f"generated {output_sha256}"
        )
    expected_count = spec.get("expected_nonwhitespace_codepoints")
    if expected_count is not None and expected_count != output_count:
        raise MutationError(
            f"{spec_path}: expected count {expected_count}, generated {output_count}"
        )

    return {
        "case_id": spec.get("case_id"),
        "spec_path": spec_path,
        "output_path": output_path,
        "output_bytes": output_bytes,
        "output_sha256": output_sha256,
        "nonwhitespace_codepoints": output_count,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize deterministic calibration variants from mutation specs."
    )
    parser.add_argument("spec", nargs="+", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify existing outputs instead of writing them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output that differs from the generated bytes.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check and args.force:
        print("--check and --force cannot be used together", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    try:
        variants = [build_variant(path.resolve(), repo_root) for path in args.spec]
        for variant in variants:
            output_path = variant["output_path"]
            output_bytes = variant["output_bytes"]
            if args.check:
                try:
                    existing = output_path.read_bytes()
                except FileNotFoundError as exc:
                    raise MutationError(f"output not found: {output_path}") from exc
                if existing != output_bytes:
                    raise MutationError(f"output differs from generated variant: {output_path}")
            else:
                if output_path.exists() and output_path.read_bytes() != output_bytes and not args.force:
                    raise MutationError(
                        f"refusing to overwrite changed output without --force: {output_path}"
                    )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(output_bytes)
    except MutationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    result = {
        "counter_version": COUNTER_VERSION,
        "mode": "check" if args.check else "materialize",
        "variants": [
            {
                "case_id": variant["case_id"],
                "spec_path": str(variant["spec_path"]),
                "output_path": str(variant["output_path"]),
                "output_sha256": variant["output_sha256"],
                "nonwhitespace_codepoints": variant["nonwhitespace_codepoints"],
            }
            for variant in variants
        ],
    }
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

