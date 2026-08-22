# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

"""Evaluate recorded semantic runtime outputs against cognitive calibration gold."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from runtime_scoring import (
    DEFAULT_BOOK_CARD_SCHEMA,
    REPO_ROOT,
    RuntimeValidationError,
    aggregate_cognitive,
    load_json_object,
    load_jsonl_objects,
    schema_validation_errors,
    score_adjudication_bundle,
    validate_cognitive_aggregate,
)
from validate_book_card import validate_cross_references

DEFAULT_BOOK_CARD = (
    REPO_ROOT / "workbench/breakthrough-advertising/book_card.draft.json"
)
DEFAULT_CASES = (
    REPO_ROOT / "calibration/books/breakthrough-advertising/cognitive/cases.jsonl"
)
DEFAULT_EXPECTED = (
    REPO_ROOT / "calibration/books/breakthrough-advertising/cognitive/expected.jsonl"
)


def records_by_case_id(
    records: Sequence[Mapping[str, Any]], label: str
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


def relation_ids(book_card: Mapping[str, Any]) -> set[str]:
    return {
        relation["id"]
        for structure in book_card["cognitive_structures"]
        for relation in structure["relations"]
    }


def compare_relation_outcomes(
    expected_failed: set[str],
    actual_outcomes: Mapping[str, str],
    all_relation_ids: set[str],
) -> dict[str, list[str]]:
    expected_passed = all_relation_ids - expected_failed
    actual_passed = {
        relation_id
        for relation_id, outcome in actual_outcomes.items()
        if outcome == "pass"
    }
    actual_failed = {
        relation_id
        for relation_id, outcome in actual_outcomes.items()
        if outcome == "fail"
    }
    unresolved = {
        relation_id
        for relation_id, outcome in actual_outcomes.items()
        if outcome in {"unresolved", "infrastructure_error"}
    }
    return {
        "false_pass_relation_ids": sorted(expected_failed & actual_passed),
        "false_fail_relation_ids": sorted(expected_passed & actual_failed),
        "unresolved_relation_ids": sorted(unresolved),
    }


def failed_path_unit_ids(aggregate: Mapping[str, Any]) -> set[str]:
    return {
        item["unit_id"]
        for item in aggregate["path_results"]
        if item["complete"] is False
    }


def numeric_metrics_match(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> bool:
    for metric_name in (
        "cognitive_relation_coverage",
        "complete_core_path_rate",
    ):
        actual_value = actual.get(metric_name)
        expected_value = expected.get(metric_name)
        if not isinstance(actual_value, (int, float)) or not isinstance(
            expected_value, (int, float)
        ):
            return False
        if not math.isclose(
            float(actual_value),
            float(expected_value),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            return False
    return True


def evaluate_runs(
    *,
    book_card_path: Path,
    cases_path: Path,
    expected_path: Path,
    runs_dir: Path,
    selected_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    book_card = load_json_object(book_card_path)
    card_errors = schema_validation_errors(
        book_card,
        load_json_object(DEFAULT_BOOK_CARD_SCHEMA),
        "book_card",
    )
    card_errors.extend(validate_cross_references(book_card))
    if card_errors:
        raise RuntimeValidationError(card_errors)

    cases_in_order = load_jsonl_objects(cases_path)
    cases = records_by_case_id(cases_in_order, "cases")
    expected = records_by_case_id(load_jsonl_objects(expected_path), "expected")
    if set(cases) != set(expected):
        errors = []
        if missing_expected := set(cases) - set(expected):
            errors.append(f"cases missing expectations: {sorted(missing_expected)!r}")
        if missing_cases := set(expected) - set(cases):
            errors.append(f"expectations missing cases: {sorted(missing_cases)!r}")
        raise RuntimeValidationError(errors)
    if selected_case_ids is not None:
        unknown_selected = selected_case_ids - set(cases)
        if unknown_selected:
            raise RuntimeValidationError(
                f"unknown selected case IDs {sorted(unknown_selected)!r}"
            )

    all_relation_ids = relation_ids(book_card)

    errors: list[str] = []
    case_results: list[dict[str, Any]] = []
    for case_record in cases_in_order:
        case_id = case_record["case_id"]
        if selected_case_ids is not None and case_id not in selected_case_ids:
            continue
        if case_id not in expected:
            errors.append(f"{case_id}: missing expected record")
            continue

        run_dir = runs_dir / case_id
        evidence_path = run_dir / "evidence-results.jsonl"
        judges_path = run_dir / "judge-results.jsonl"
        aggregate_path = run_dir / "cognitive-aggregate.json"
        missing_files = [
            str(path)
            for path in (evidence_path, judges_path, aggregate_path)
            if not path.is_file()
        ]
        if missing_files:
            errors.append(f"{case_id}: missing runtime files {missing_files!r}")
            case_results.append(
                {
                    "case_id": case_id,
                    "status": "missing",
                    "errors": [f"missing runtime files {missing_files!r}"],
                }
            )
            continue

        text_path_value = case_record.get("text_path")
        if not isinstance(text_path_value, str) or not text_path_value:
            detail = ["case text_path must be a non-empty string"]
            errors.extend(f"{case_id}: {item}" for item in detail)
            case_results.append(
                {"case_id": case_id, "status": "invalid", "errors": detail}
            )
            continue
        text_path = (REPO_ROOT / text_path_value).resolve()
        try:
            text_path.relative_to(REPO_ROOT)
            submission_text = text_path.read_text(encoding="utf-8")
            evidence = load_jsonl_objects(evidence_path)
            judges = load_jsonl_objects(judges_path)
            recomputed = score_adjudication_bundle(
                book_card, submission_text, case_id, evidence, judges
            )
            recorded = load_json_object(aggregate_path)
            validate_cognitive_aggregate(recorded)
        except (ValueError, OSError, UnicodeDecodeError, RuntimeValidationError) as exc:
            detail = (
                exc.errors if isinstance(exc, RuntimeValidationError) else [str(exc)]
            )
            errors.extend(f"{case_id}: {item}" for item in detail)
            case_results.append(
                {"case_id": case_id, "status": "invalid", "errors": detail}
            )
            continue

        case_errors: list[str] = []
        if recorded != recomputed:
            case_errors.append("recorded aggregate differs from recomputation")

        expected_failed_raw = expected[case_id].get("expected_changed_relation_ids")
        if not isinstance(expected_failed_raw, list) or not all(
            isinstance(item, str) for item in expected_failed_raw
        ):
            detail = ["expected_changed_relation_ids must be a string array"]
            errors.extend(f"{case_id}: {item}" for item in detail)
            case_results.append(
                {"case_id": case_id, "status": "invalid", "errors": detail}
            )
            continue
        expected_failed = set(expected_failed_raw)
        unknown_expected = expected_failed - all_relation_ids
        if unknown_expected:
            detail = [f"unknown expected relation IDs {sorted(unknown_expected)!r}"]
            errors.extend(f"{case_id}: {item}" for item in detail)
            case_results.append(
                {"case_id": case_id, "status": "invalid", "errors": detail}
            )
            continue
        expected_outcomes = {
            relation_id: ("fail" if relation_id in expected_failed else "pass")
            for relation_id in all_relation_ids
        }
        expected_aggregate = aggregate_cognitive(book_card, expected_outcomes, case_id)
        actual_outcomes = {
            item["relation_id"]: item["outcome"]
            for item in recomputed["relation_results"]
        }
        comparison = compare_relation_outcomes(
            expected_failed, actual_outcomes, all_relation_ids
        )
        if comparison["false_pass_relation_ids"]:
            case_errors.append(
                "damaged relations incorrectly passed "
                f"{comparison['false_pass_relation_ids']!r}"
            )
        if comparison["false_fail_relation_ids"]:
            case_errors.append(
                "stable relations incorrectly failed "
                f"{comparison['false_fail_relation_ids']!r}"
            )
        if comparison["unresolved_relation_ids"]:
            case_errors.append(
                f"unresolved relations {comparison['unresolved_relation_ids']!r}"
            )

        actual_failed_paths = failed_path_unit_ids(recomputed)
        expected_failed_paths = failed_path_unit_ids(expected_aggregate)
        if actual_failed_paths != expected_failed_paths:
            case_errors.append(
                f"failed path units expected {sorted(expected_failed_paths)!r}, "
                f"actual {sorted(actual_failed_paths)!r}"
            )
        if not numeric_metrics_match(
            recomputed["metrics"], expected_aggregate["metrics"]
        ):
            case_errors.append("aggregate cognitive metrics differ from gold")

        locator_error_count = sum(
            item["status"] == "locator_error" for item in evidence
        )
        abstain_count = sum(item["decision"] == "abstain" for item in judges)
        if case_errors:
            errors.extend(f"{case_id}: {item}" for item in case_errors)
        case_results.append(
            {
                "case_id": case_id,
                "status": "pass" if not case_errors else "fail",
                **comparison,
                "locator_error_count": locator_error_count,
                "judge_abstain_count": abstain_count,
                "expected_failed_path_unit_ids": sorted(expected_failed_paths),
                "actual_failed_path_unit_ids": sorted(actual_failed_paths),
                "errors": case_errors,
            }
        )

    totals = {
        "false_passes": sum(
            len(item.get("false_pass_relation_ids", [])) for item in case_results
        ),
        "false_fails": sum(
            len(item.get("false_fail_relation_ids", [])) for item in case_results
        ),
        "unresolved_relations": sum(
            len(item.get("unresolved_relation_ids", [])) for item in case_results
        ),
        "locator_errors": sum(
            item.get("locator_error_count", 0) for item in case_results
        ),
        "judge_abstains": sum(
            item.get("judge_abstain_count", 0) for item in case_results
        ),
    }
    return {
        "schema_version": "1.0",
        "book_id": book_card["book_id"],
        "case_count": len(case_results),
        "passed_case_count": sum(item["status"] == "pass" for item in case_results),
        "failed_case_count": sum(item["status"] != "pass" for item in case_results),
        "relation_decision_count": len(case_results) * len(all_relation_ids),
        "totals": totals,
        "cases": case_results,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare recorded semantic runtime outputs with cognitive calibration "
            "relation and path expectations."
        )
    )
    parser.add_argument("--book-card", type=Path, default=DEFAULT_BOOK_CARD)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        result = evaluate_runs(
            book_card_path=args.book_card,
            cases_path=args.cases,
            expected_path=args.expected,
            runs_dir=args.runs_dir,
            selected_case_ids=set(args.case_ids) if args.case_ids else None,
        )
    except RuntimeValidationError as exc:
        print("Semantic calibration evaluation could not start:", file=sys.stderr)
        for error in exc.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Semantic calibration report written: {args.output}")

    if result["errors"]:
        print(
            f"Semantic calibration failed: "
            f"{result['failed_case_count']}/{result['case_count']} cases",
            file=sys.stderr,
        )
        return 1
    print(
        f"Semantic calibration passed: "
        f"{result['passed_case_count']}/{result['case_count']} cases",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
