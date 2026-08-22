#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from count_submission_chars import COUNTER_VERSION, count_text, evaluate_bounds


LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
REQUIRED_AUDIT_COUNTS = (
    ("relations_passed", "relations_total"),
    ("mandatory_paths_passed", "mandatory_paths_total"),
    ("panel_edges_passed", "panel_edges_total"),
    ("constitutive_cases_passed", "constitutive_cases_total"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contains_id(value: Any, target_id: str) -> bool:
    if isinstance(value, dict):
        if value.get("id") == target_id:
            return True
        return any(contains_id(item, target_id) for item in value.values())
    if isinstance(value, list):
        return any(contains_id(item, target_id) for item in value)
    return False


def parse_manifest(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[str]]:
    records: list[tuple[int, dict[str, Any]]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [], [f"manifest not found: {path}"]
    except UnicodeDecodeError as exc:
        return [], [f"manifest is not valid UTF-8: {exc}"]

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_number}: record must be a JSON object")
            continue
        records.append((line_number, value))
    if not records and not errors:
        errors.append("manifest contains no records")
    return records, errors


def resolve_repo_file(repo_root: Path, relative_path: Any, label: str) -> tuple[Path | None, str | None]:
    if not isinstance(relative_path, str) or not relative_path:
        return None, f"{label} must be a non-empty repository-relative path"
    candidate = (repo_root / relative_path).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return None, f"{label} escapes repository root: {relative_path}"
    if not candidate.is_file():
        return None, f"{label} not found: {relative_path}"
    return candidate, None


def validate_record(
    record: dict[str, Any],
    line_number: int,
    repo_root: Path,
    expected_book_card_sha256: str,
    expected_discourse_card_sha256: str,
    discourse_card: Any,
) -> list[str]:
    prefix = f"line {line_number}"
    errors: list[str] = []

    if record.get("schema_version") != "length-run-v1":
        errors.append(f"{prefix}: schema_version must be length-run-v1")

    run_id = record.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append(f"{prefix}: run_id must be a non-empty string")

    text_path, path_error = resolve_repo_file(
        repo_root, record.get("text_path"), f"{prefix} text_path"
    )
    if path_error:
        errors.append(path_error)
        return errors

    assert text_path is not None
    data = text_path.read_bytes()
    actual_sha256 = sha256_bytes(data)
    if record.get("text_sha256") != actual_sha256:
        errors.append(
            f"{prefix}: text_sha256 mismatch: expected {record.get('text_sha256')}, "
            f"actual {actual_sha256}"
        )

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{prefix}: text is not valid UTF-8: {exc}")
        return errors

    counter = record.get("counter")
    if not isinstance(counter, dict):
        errors.append(f"{prefix}: counter must be an object")
    else:
        if counter.get("version") != COUNTER_VERSION:
            errors.append(
                f"{prefix}: counter.version must be {COUNTER_VERSION}"
            )
        minimum = counter.get("min_chars")
        maximum = counter.get("max_chars")
        if minimum is not None and (not isinstance(minimum, int) or minimum < 0):
            errors.append(f"{prefix}: counter.min_chars must be null or non-negative int")
        if maximum is not None and (not isinstance(maximum, int) or maximum < 0):
            errors.append(f"{prefix}: counter.max_chars must be null or non-negative int")
        if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
            errors.append(f"{prefix}: counter.min_chars cannot exceed max_chars")

        counts = count_text(text)
        actual_count = counts["nonwhitespace_codepoints"]
        if counter.get("nonwhitespace_codepoints") != actual_count:
            errors.append(
                f"{prefix}: nonwhitespace count mismatch: expected "
                f"{counter.get('nonwhitespace_codepoints')}, actual {actual_count}"
            )
        if (minimum is None or isinstance(minimum, int)) and (
            maximum is None or isinstance(maximum, int)
        ):
            actual_within_bounds = evaluate_bounds(actual_count, minimum, maximum)
            if counter.get("within_bounds") is not actual_within_bounds:
                errors.append(
                    f"{prefix}: within_bounds mismatch: expected "
                    f"{counter.get('within_bounds')}, actual {actual_within_bounds}"
                )

    actual_latin_count = len(LATIN_LETTER_RE.findall(text))
    if record.get("latin_letter_count") != actual_latin_count:
        errors.append(
            f"{prefix}: latin_letter_count mismatch: expected "
            f"{record.get('latin_letter_count')}, actual {actual_latin_count}"
        )

    gold_versions = record.get("gold_versions")
    if not isinstance(gold_versions, dict):
        errors.append(f"{prefix}: gold_versions must be an object")
    else:
        if gold_versions.get("book_card_sha256") != expected_book_card_sha256:
            errors.append(f"{prefix}: book_card_sha256 does not match current card")
        if gold_versions.get("discourse_card_sha256") != expected_discourse_card_sha256:
            errors.append(f"{prefix}: discourse_card_sha256 does not match current card")
        panel_id = gold_versions.get("panel_id")
        if not isinstance(panel_id, str) or not contains_id(discourse_card, panel_id):
            errors.append(f"{prefix}: panel_id not found in discourse card: {panel_id}")

    reference_audit = record.get("reference_audit")
    if not isinstance(reference_audit, dict):
        errors.append(f"{prefix}: reference_audit must be an object")
    else:
        for passed_key, total_key in REQUIRED_AUDIT_COUNTS:
            passed = reference_audit.get(passed_key)
            total = reference_audit.get(total_key)
            if not isinstance(passed, int) or not isinstance(total, int):
                errors.append(f"{prefix}: {passed_key} and {total_key} must be ints")
            elif passed < 0 or total <= 0 or passed > total:
                errors.append(f"{prefix}: invalid audit count {passed}/{total}")

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a length-run JSONL manifest against repository files."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    manifest = args.manifest.resolve()

    records, errors = parse_manifest(manifest)
    book_dir = manifest.parent
    book_card_path = book_dir / "book_card.draft.json"
    discourse_card_path = book_dir / "discourse_card.draft.json"

    try:
        book_card_bytes = book_card_path.read_bytes()
    except FileNotFoundError:
        errors.append(f"book card not found beside manifest: {book_card_path}")
        book_card_bytes = b""
    try:
        discourse_card_bytes = discourse_card_path.read_bytes()
        discourse_card = json.loads(discourse_card_bytes.decode("utf-8"))
    except FileNotFoundError:
        errors.append(f"discourse card not found beside manifest: {discourse_card_path}")
        discourse_card_bytes = b""
        discourse_card = {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid discourse card: {exc}")
        discourse_card_bytes = b""
        discourse_card = {}

    book_card_sha256 = sha256_bytes(book_card_bytes)
    discourse_card_sha256 = sha256_bytes(discourse_card_bytes)
    seen_run_ids: set[str] = set()

    for line_number, record in records:
        run_id = record.get("run_id")
        if isinstance(run_id, str):
            if run_id in seen_run_ids:
                errors.append(f"line {line_number}: duplicate run_id: {run_id}")
            seen_run_ids.add(run_id)
        errors.extend(
            validate_record(
                record,
                line_number,
                repo_root,
                book_card_sha256,
                discourse_card_sha256,
                discourse_card,
            )
        )

    result = {
        "manifest": str(manifest),
        "records": len(records),
        "valid": not errors,
        "errors": errors,
    }
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

