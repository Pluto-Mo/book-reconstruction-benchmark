#!/usr/bin/env python3
# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

"""Replay frozen cognitive expectations through the deterministic aggregator.

This is an aggregation replay, not a semantic-Judge evaluation. Expected
relation labels are used as fixture verdicts so path propagation, weighting,
length checks, and failure handling can be tested before a Judge provider is
frozen.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from count_submission_chars import COUNTER_VERSION, count_text, evaluate_bounds
from runtime_scoring import (
    REPO_ROOT,
    RuntimeValidationError,
    aggregate_cognitive,
    load_json_object,
    load_jsonl_objects,
    validate_cognitive_aggregate,
)

DEFAULT_BOOK_CARD = (
    REPO_ROOT / "workbench/breakthrough-advertising/book_card.draft.json"
)
DEFAULT_CASES = (
    REPO_ROOT / "calibration/books/breakthrough-advertising/cognitive/cases.jsonl"
)
DEFAULT_EXPECTED = (
    REPO_ROOT / "calibration/books/breakthrough-advertising/cognitive/expected.jsonl"
)


def _records_by_case_id(
    records: Iterable[Mapping[str, Any]], label: str
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []
    for record in records:
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{label}: record has no valid case_id")
            continue
        if case_id in indexed:
            errors.append(f"{label}: duplicate case_id {case_id}")
            continue
        indexed[case_id] = record
    if errors:
        raise RuntimeValidationError(errors)
    return indexed


def _all_relation_ids(book_card: Mapping[str, Any]) -> set[str]:
    return {
        relation["id"]
        for structure in book_card["cognitive_structures"]
        for relation in structure["relations"]
    }


def _failed_concrete_path_ids(
    book_card: Mapping[str, Any], failed_relation_ids: set[str]
) -> set[str]:
    return {
        path["id"]
        for structure in book_card["cognitive_structures"]
        for path in structure["paths"]
        if failed_relation_ids.intersection(path["relation_ids"])
    }


def _expected_metric_value(
    case_id: str,
    metric_name: str,
    expectation: Any,
    prior_metrics: Mapping[str, Mapping[str, float]],
) -> float:
    if expectation == "reference_ceiling":
        return 1.0
    if isinstance(expectation, str) and expectation.startswith("stable_vs_"):
        baseline_id = expectation.removeprefix("stable_vs_")
        if baseline_id not in prior_metrics:
            raise RuntimeValidationError(
                f"{case_id}: metric {metric_name} references unavailable baseline "
                f"{baseline_id}"
            )
        return prior_metrics[baseline_id][metric_name]
    if isinstance(expectation, str) and "/" in expectation:
        numerator_text, denominator_text = expectation.split("/", maxsplit=1)
        try:
            numerator = int(numerator_text)
            denominator = int(denominator_text)
        except ValueError as exc:
            raise RuntimeValidationError(
                f"{case_id}: invalid metric fraction {expectation!r}"
            ) from exc
        if denominator <= 0:
            raise RuntimeValidationError(
                f"{case_id}: metric fraction denominator must be positive"
            )
        return numerator / denominator
    raise RuntimeValidationError(
        f"{case_id}: unsupported expected metric value {expectation!r}"
    )


def run_replay(
    book_card_path: Path = DEFAULT_BOOK_CARD,
    cases_path: Path = DEFAULT_CASES,
    expected_path: Path = DEFAULT_EXPECTED,
) -> dict[str, Any]:
    book_card = load_json_object(book_card_path)
    case_records = load_jsonl_objects(cases_path)
    expected_records = load_jsonl_objects(expected_path)
    cases = _records_by_case_id(case_records, "cases")
    expected = _records_by_case_id(expected_records, "expected")

    errors: list[str] = []
    if set(cases) != set(expected):
        missing_expected = sorted(set(cases) - set(expected))
        missing_cases = sorted(set(expected) - set(cases))
        if missing_expected:
            errors.append(f"cases missing expectations: {missing_expected!r}")
        if missing_cases:
            errors.append(f"expectations missing cases: {missing_cases!r}")

    relation_ids = _all_relation_ids(book_card)
    prior_metrics: dict[str, Mapping[str, float]] = {}
    case_results: list[dict[str, Any]] = []

    for case_record in case_records:
        case_id = case_record.get("case_id")
        if not isinstance(case_id, str) or case_id not in expected:
            continue
        expected_record = expected[case_id]
        case_errors: list[str] = []

        changed_relations_raw = expected_record.get("expected_changed_relation_ids")
        if not isinstance(changed_relations_raw, list) or not all(
            isinstance(item, str) for item in changed_relations_raw
        ):
            case_errors.append("expected_changed_relation_ids must be a string array")
            changed_relations: set[str] = set()
        else:
            changed_relations = set(changed_relations_raw)
        unknown_relations = changed_relations - relation_ids
        if unknown_relations:
            case_errors.append(
                f"unknown changed relation IDs {sorted(unknown_relations)!r}"
            )

        outcomes = {
            relation_id: ("fail" if relation_id in changed_relations else "pass")
            for relation_id in relation_ids
        }
        aggregate = aggregate_cognitive(book_card, outcomes, case_id)
        try:
            validate_cognitive_aggregate(aggregate)
        except RuntimeValidationError as exc:
            case_errors.extend(exc.errors)

        actual_failed_paths = _failed_concrete_path_ids(book_card, changed_relations)
        expected_failed_paths_raw = expected_record.get("expected_changed_path_ids")
        if not isinstance(expected_failed_paths_raw, list) or not all(
            isinstance(item, str) for item in expected_failed_paths_raw
        ):
            case_errors.append("expected_changed_path_ids must be a string array")
            expected_failed_paths: set[str] = set()
        else:
            expected_failed_paths = set(expected_failed_paths_raw)
        if actual_failed_paths != expected_failed_paths:
            case_errors.append(
                f"path propagation mismatch: expected {sorted(expected_failed_paths)!r}, "
                f"actual {sorted(actual_failed_paths)!r}"
            )

        actual_metrics = aggregate["metrics"]
        expected_metrics = expected_record.get("expected_metrics")
        if not isinstance(expected_metrics, dict):
            case_errors.append("expected_metrics must be an object")
        else:
            for metric_name in (
                "cognitive_relation_coverage",
                "complete_core_path_rate",
            ):
                actual_value = actual_metrics[metric_name]
                if not isinstance(actual_value, float):
                    case_errors.append(f"{metric_name} unexpectedly unresolved")
                    continue
                try:
                    expected_value = _expected_metric_value(
                        case_id,
                        metric_name,
                        expected_metrics.get(metric_name),
                        prior_metrics,
                    )
                except RuntimeValidationError as exc:
                    case_errors.extend(exc.errors)
                    continue
                if not math.isclose(
                    actual_value, expected_value, rel_tol=0.0, abs_tol=1e-12
                ):
                    case_errors.append(
                        f"{metric_name}: expected {expected_value}, actual {actual_value}"
                    )

        hard_constraints = expected_record.get("hard_constraints")
        counted_chars: int | None = None
        actual_within_bounds: bool | None = None
        if not isinstance(hard_constraints, dict):
            case_errors.append("hard_constraints must be an object")
        else:
            if hard_constraints.get("counter_version") != COUNTER_VERSION:
                case_errors.append("counter_version mismatch")
            text_path_value = case_record.get("text_path")
            if not isinstance(text_path_value, str) or not text_path_value:
                case_errors.append("case text_path must be a non-empty string")
            else:
                text_path = (REPO_ROOT / text_path_value).resolve()
                try:
                    text_path.relative_to(REPO_ROOT)
                    text = text_path.read_text(encoding="utf-8")
                except (ValueError, OSError, UnicodeDecodeError) as exc:
                    case_errors.append(f"cannot read case text: {exc}")
                else:
                    counted_chars = count_text(text)["nonwhitespace_codepoints"]
                    maximum = hard_constraints.get("max_chars")
                    if maximum is not None and (
                        not isinstance(maximum, int) or isinstance(maximum, bool)
                    ):
                        case_errors.append(
                            "hard_constraints.max_chars must be integer or null"
                        )
                    else:
                        bound_result = evaluate_bounds(counted_chars, None, maximum)
                        actual_within_bounds = (
                            True if bound_result is None else bound_result
                        )
                        if actual_within_bounds != hard_constraints.get(
                            "expected_within_bounds"
                        ):
                            case_errors.append(
                                "hard-constraint result differs from expectation"
                            )

        if not case_errors:
            prior_metrics[case_id] = {
                "cognitive_relation_coverage": actual_metrics[
                    "cognitive_relation_coverage"
                ],
                "complete_core_path_rate": actual_metrics["complete_core_path_rate"],
            }
        else:
            errors.extend(f"{case_id}: {error}" for error in case_errors)

        case_results.append(
            {
                "case_id": case_id,
                "status": "pass" if not case_errors else "fail",
                "failed_relation_ids": sorted(changed_relations),
                "failed_path_ids": sorted(actual_failed_paths),
                "nonwhitespace_codepoints": counted_chars,
                "within_bounds": actual_within_bounds,
                "metrics": actual_metrics,
                "errors": case_errors,
            }
        )

    return {
        "schema_version": "1.0",
        "replay_type": "expected-label aggregation replay",
        "semantic_judge_exercised": False,
        "book_id": book_card.get("book_id"),
        "case_count": len(case_results),
        "passed_count": sum(item["status"] == "pass" for item in case_results),
        "failed_count": sum(item["status"] == "fail" for item in case_results),
        "cases": case_results,
        "errors": errors,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay calibration relation labels through the deterministic cognitive "
            "aggregator. This does not call or evaluate a semantic Judge."
        )
    )
    parser.add_argument("--book-card", type=Path, default=DEFAULT_BOOK_CARD)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result = run_replay(args.book_card, args.cases, args.expected)
    except RuntimeValidationError as exc:
        print("Calibration replay could not start:", file=sys.stderr)
        for error in exc.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Calibration replay written: {args.output}")

    if result["errors"]:
        print(
            f"Calibration replay failed: {result['failed_count']}/{result['case_count']} cases",
            file=sys.stderr,
        )
        for error in result["errors"]:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        f"Calibration aggregation replay passed: "
        f"{result['passed_count']}/{result['case_count']} cases",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
